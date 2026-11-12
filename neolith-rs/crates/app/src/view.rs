//! The central board view: camera controls, picking, the editor tools'
//! pointer handling, settlement pieces and the paint callback.

use crate::app::{Gpu, Session, Tool};
use crate::board::camera::{self, View};
use crate::board::relief::Relief;
use crate::board::renderer::{BoardRenderer, Globals};
use crate::board::scene::{self, BoardStyle, Piece, PieceFrame, ScreenPiece};
use eframe::{egui_wgpu, wgpu};
use egui::{Align2, Color32, FontId, PointerButton, Pos2, Sense, Stroke};
use glam::DVec2;
use neolith_core::geom::point_in_polygon;
use neolith_core::{fill, pencil, Command, GridSpec, LonLat, Selection};
use std::sync::{Arc, Mutex};

enum Drag {
    Pan { grabbed: LonLat },
    Orbit,
    Paint,
    Lasso,
}

struct StrokeState {
    cmd: Command,
    visited: Selection,
    last: DVec2,
}

struct Glide {
    from: LonLat,
    to: LonLat,
    start: f64,
}

/// Pointer-interaction state of the board view.
#[derive(Default)]
pub struct BoardInput {
    drag: Option<Drag>,
    stroke: Option<StrokeState>,
    /// The lasso path being drawn, in viewport points.
    lasso: Vec<DVec2>,
    lasso_preview: Option<Selection>,
    /// Pan inertia, degrees per second.
    velocity: DVec2,
    glide: Option<Glide>,
    /// What the last frame drew, kept so the agent harness can read it.
    pub drawn: Drawn,
}

/// A record of the board as drawn in the last frame (window points).
#[derive(Default, Clone)]
pub struct Drawn {
    pub rect: Option<egui::Rect>,
    /// Settlements on screen: index into `world.settlements`, base and top of the piece.
    pub pieces: Vec<(usize, Pos2, Pos2)>,
    /// Settlement names drawn as labels, with the label's rectangle.
    pub labels: Vec<(usize, egui::Rect)>,
    pub piece_hover: Option<usize>,
    /// Geography names drawn (seas, regions, mountains, rivers, lakes).
    pub geo: Vec<crate::labels::DrawnLabel>,
}

struct BoardPaint {
    renderer: Arc<Mutex<BoardRenderer>>,
    globals: Globals,
    size: [u32; 2],
}

impl egui_wgpu::CallbackTrait for BoardPaint {
    fn prepare(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        _screen: &egui_wgpu::ScreenDescriptor,
        encoder: &mut wgpu::CommandEncoder,
        _resources: &mut egui_wgpu::CallbackResources,
    ) -> Vec<wgpu::CommandBuffer> {
        // Offscreen colour + depth pass, recorded ahead of egui's own pass.
        self.renderer.lock().unwrap().render(device, queue, encoder, self.size, &self.globals);
        Vec::new()
    }

    fn paint(
        &self,
        _info: egui::PaintCallbackInfo,
        pass: &mut wgpu::RenderPass<'static>,
        _resources: &egui_wgpu::CallbackResources,
    ) {
        self.renderer.lock().unwrap().blit(pass);
    }
}

/// Hexes whose centre projects inside the screen-space lasso `path`.
/// With `visible_only`, hexes hidden behind the curve of the board are
/// excluded by checking that the ray through the centre hits that hex first.
pub fn lasso_select(grid: &GridSpec, view: &View, relief: &Relief, path: &[DVec2], visible_only: bool) -> Selection {
    let mut sel = Selection::new(grid.len());
    if path.len() < 3 {
        return sel;
    }
    let poly: Vec<[f64; 2]> = path.iter().map(|p| [p.x, p.y]).collect();
    let (mut lo, mut hi) = (path[0], path[0]);
    for p in path {
        lo = lo.min(*p);
        hi = hi.max(*p);
    }
    for id in grid.ids() {
        let Some(px) = view.project_relief(grid.centre(id), relief) else { continue };
        if px.x < lo.x || px.y < lo.y || px.x > hi.x || px.y > hi.y || !point_in_polygon(&poly, [px.x, px.y]) {
            continue;
        }
        if visible_only && view.pick_relief(px, relief).and_then(|ll| grid.hex_at(ll)) != Some(id) {
            continue;
        }
        sel.insert(id);
    }
    sel
}

fn segment_distance(p: DVec2, a: DVec2, b: DVec2) -> f64 {
    let ab = b - a;
    let t = if ab.length_squared() > 0.0 { ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0) } else { 0.0 };
    (p - (a + ab * t)).length()
}

/// Screen-space segment (base, top) of a piece, if it faces the camera.
/// Visible-piece indices from most to least important: the selected
/// settlement, then population, then settlement id (stable while panning).
fn piece_priority(s: &Session, visible: &[(usize, Piece)]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..visible.len()).collect();
    order.sort_by_key(|&k| {
        let (i, p) = &visible[k];
        (s.settlement != Some(*i), std::cmp::Reverse(p.population), s.world.settlements[*i].id)
    });
    order
}

/// How close the camera must be before a settlement of this size is named.
fn label_dist(population: u32) -> f64 {
    match population {
        // No population on record: named only close in.
        0 => 0.15,
        1..=999 => 1.0,
        1000..=2999 => 1.6,
        _ => 2.4,
    }
}

pub fn board_view(ui: &mut egui::Ui, s: &mut Session, style: &BoardStyle, gpu: &Gpu, now: f64, dt: f64) {
    let rect = ui.available_rect_before_wrap();
    let resp = ui.allocate_rect(rect, Sense::click_and_drag());
    let size = DVec2::new(rect.width() as f64, rect.height() as f64);
    if size.x < 8.0 || size.y < 8.0 {
        return;
    }
    let grid = s.world.grid.clone();
    s.update_relief(style);
    let relief = s.relief.clone();
    let local = |p: Pos2| DVec2::new((p.x - rect.left()) as f64, (p.y - rect.top()) as f64);
    let (modifiers, press_origin, scroll, pinch) =
        ui.input(|i| (i.modifiers, i.pointer.press_origin(), i.smooth_scroll_delta.y as f64, i.zoom_delta() as f64));
    let cursor = resp.interact_pointer_pos().or(resp.hover_pos()).map(local);
    let mut repaint = false;

    // ---- camera animation: double-click glide and pan inertia ----------
    if let Some(g) = &s.input.glide {
        let p = ((now - g.start) / 0.45).clamp(0.0, 1.0);
        let e = p * p * (3.0 - 2.0 * p);
        s.camera.target = LonLat::new(g.from.lon + (g.to.lon - g.from.lon) * e, g.from.lat + (g.to.lat - g.from.lat) * e);
        if p >= 1.0 {
            s.input.glide = None;
        }
        repaint = true;
    } else if s.input.drag.is_none() && s.input.velocity.length() > 0.02 {
        s.camera.target.lon += s.input.velocity.x * dt;
        s.camera.target.lat += s.input.velocity.y * dt;
        s.input.velocity *= (-dt / 0.16).exp();
        repaint = true;
    }
    s.camera.clamp(&grid);

    // ---- zoom towards the cursor ---------------------------------------
    if resp.contains_pointer() && (scroll != 0.0 || pinch != 1.0) {
        let anchor = cursor.and_then(|c| s.camera.view(&s.proj, s.morph, size).pick_relief(c, &relief).map(|ll| (c, ll)));
        s.camera.dist *= (-scroll * 0.0025).exp() / pinch.max(0.01);
        s.camera.clamp(&grid);
        if let Some((c, ll)) = anchor {
            if grid.hex_at(ll).is_some() {
                camera::grab(&mut s.camera, &s.proj, s.morph, size, &grid, &relief, ll, c);
            }
        }
        s.input.glide = None;
    }

    // ---- drags -----------------------------------------------------------
    let orbit_mod = modifiers.ctrl || modifiers.command;
    if resp.drag_started() {
        let origin = press_origin.map(local).or(cursor).unwrap_or(size / 2.0);
        let view = s.camera.view(&s.proj, s.morph, size);
        let pan = |view: &View| view.pick_relief(origin, &relief).map(|grabbed| Drag::Pan { grabbed });
        s.input.velocity = DVec2::ZERO;
        s.input.glide = None;
        s.input.drag = if resp.dragged_by(PointerButton::Secondary) || (resp.dragged_by(PointerButton::Primary) && orbit_mod) {
            Some(Drag::Orbit)
        } else if resp.dragged_by(PointerButton::Middle) {
            pan(&view)
        } else if resp.dragged_by(PointerButton::Primary) {
            match s.tool {
                Tool::Pencil => {
                    s.input.stroke =
                        Some(StrokeState { cmd: Command::new("Pencil"), visited: Selection::new(grid.len()), last: origin });
                    Some(Drag::Paint)
                }
                Tool::Lasso => {
                    s.input.lasso = vec![origin];
                    Some(Drag::Lasso)
                }
                Tool::Select | Tool::Fill => pan(&view),
            }
        } else {
            None
        };
    }
    if let (Some(drag), Some(c)) = (&s.input.drag, cursor) {
        match drag {
            Drag::Pan { grabbed } => {
                let before = s.camera.target;
                camera::grab(&mut s.camera, &s.proj, s.morph, size, &grid, &relief, *grabbed, c);
                if dt > 0.0 {
                    let v = DVec2::new(s.camera.target.lon - before.lon, s.camera.target.lat - before.lat) / dt;
                    s.input.velocity = s.input.velocity.lerp(v, 0.35);
                }
            }
            Drag::Orbit => {
                let d = resp.drag_delta();
                s.camera.yaw -= d.x as f64 * 0.006;
                s.camera.pitch += d.y as f64 * 0.006;
                s.camera.pitch_pref = s.camera.pitch;
                s.camera.clamp(&grid);
            }
            Drag::Paint => {
                let view = s.camera.view(&s.proj, s.morph, size);
                if let Some(mut stroke) = s.input.stroke.take() {
                    // Sample along the segment so fast drags leave no gaps.
                    let steps = ((c - stroke.last).length() / 3.0).ceil().max(1.0) as usize;
                    for k in 0..=steps {
                        let p = stroke.last.lerp(c, k as f64 / steps as f64);
                        let Some(hex) = view.pick_relief(p, &relief).and_then(|ll| grid.hex_at(ll)) else { continue };
                        let Some(value) = s.paint_value() else { continue };
                        if stroke.visited.insert(hex) {
                            let cmd = pencil(&s.world, [hex], value, s.year(), s.key_mode);
                            s.apply_live(&cmd);
                            stroke.cmd.edits.extend(cmd.edits);
                        }
                    }
                    stroke.last = c;
                    s.input.stroke = Some(stroke);
                }
            }
            Drag::Lasso => {
                if s.input.lasso.last().is_none_or(|l| (*l - c).length() > 2.5) {
                    s.input.lasso.push(c);
                    let view = s.camera.view(&s.proj, s.morph, size);
                    s.input.lasso_preview = Some(lasso_select(&grid, &view, &relief, &s.input.lasso, false));
                    s.state_dirty = true;
                }
            }
        }
    }
    if resp.drag_stopped() {
        match s.input.drag.take() {
            Some(Drag::Paint) => {
                if let Some(stroke) = s.input.stroke.take() {
                    s.finish_stroke(stroke.cmd);
                }
            }
            Some(Drag::Lasso) => {
                let view = s.camera.view(&s.proj, s.morph, size);
                let picked = lasso_select(&grid, &view, &relief, &s.input.lasso, true);
                if modifiers.alt {
                    s.selection.subtract(&picked);
                } else if modifiers.shift {
                    s.selection.union_with(&picked);
                } else {
                    s.selection = picked;
                }
                s.input.lasso.clear();
                s.input.lasso_preview = None;
                s.state_dirty = true;
            }
            // Only a drag that was still moving on release coasts.
            Some(Drag::Pan { .. }) if s.input.velocity.length() < 1.0 => s.input.velocity = DVec2::ZERO,
            _ => {}
        }
    }

    // ---- the frame's view; pieces; hover --------------------------------
    s.camera.clamp(&grid);
    if style.fill_screen {
        s.camera.clamp_to_fill(&s.proj, &grid, s.morph, size, style.fill_margin as f64);
    }
    let view = s.camera.view(&s.proj, s.morph, size);
    let year = s.year();
    let visible: Vec<(usize, Piece)> = s
        .world
        .settlements
        .iter()
        .enumerate()
        .filter(|(_, st)| st.exists_at(year))
        .map(|(i, st)| {
            let piece = Piece { pos: st.pos, population: st.population_at(year).unwrap_or(0), highlighted: false };
            (i, piece)
        })
        .collect();
    let frames: Vec<PieceFrame> =
        visible.iter().map(|(_, p)| scene::piece_frame(p, &s.proj, &relief, s.morph, s.camera.dist)).collect();
    let on_screen: Vec<Option<ScreenPiece>> = frames.iter().map(|f| scene::piece_on_screen(&view, f)).collect();
    // Label priority; every piece is drawn, only labels are thinned out.
    let order = piece_priority(s, &visible);

    let hovering = resp.contains_pointer() && s.input.drag.is_none();
    let piece_hover = cursor.filter(|_| hovering).and_then(|c| {
        (0..visible.len())
            .filter_map(|k| {
                let p = on_screen[k]?;
                let d = segment_distance(c, p.base, p.top);
                (d <= ((p.top - p.base).length() * 0.45).max(p.radius_px).max(8.0)).then_some((k, d))
            })
            .min_by(|x, y| x.1.total_cmp(&y.1))
            .map(|(k, _)| k)
    });
    let hover = if hovering && piece_hover.is_none() {
        cursor.and_then(|c| view.pick_relief(c, &relief)).and_then(|ll| grid.hex_at(ll))
    } else if s.input.drag.is_some() {
        s.hover
    } else {
        None
    };
    if hover != s.hover {
        s.hover = hover;
        s.state_dirty = true;
    }

    // ---- clicks ----------------------------------------------------------
    if resp.double_clicked() && matches!(s.tool, Tool::Select) {
        if let Some(hex) = s.hover {
            s.input.glide = Some(Glide { from: s.camera.target, to: grid.centre(hex), start: now });
            s.input.velocity = DVec2::ZERO;
        }
    } else if resp.clicked() {
        if let Some(k) = piece_hover {
            // A piece takes priority over the hex underneath.
            s.settlement = Some(visible[k].0);
        } else {
            match (s.tool, s.hover) {
                (Tool::Select, Some(hex)) => {
                    s.inspected = Some(hex);
                    if s.editor && modifiers.shift {
                        if s.selection.contains(hex) {
                            s.selection.remove(hex);
                        } else {
                            s.selection.insert(hex);
                        }
                    } else {
                        s.selection.clear();
                        s.selection.insert(hex);
                    }
                }
                (Tool::Select | Tool::Lasso, None) => {
                    s.inspected = None;
                    s.selection.clear();
                    s.settlement = None;
                }
                (Tool::Lasso, Some(_)) => s.selection.clear(),
                // The paint tools do nothing in a read-only map mode (elevation).
                (Tool::Pencil, Some(hex)) => {
                    if let Some(value) = s.paint_value() {
                        let cmd = pencil(&s.world, [hex], value, s.year(), s.key_mode);
                        s.apply(cmd);
                    }
                }
                (Tool::Fill, Some(hex)) => {
                    if let Some(value) = s.paint_value() {
                        // Returns an empty command when the value already matches.
                        let cmd = fill(&s.world, hex, value, s.year(), s.key_mode);
                        s.apply(cmd);
                    }
                }
                _ => {}
            }
            s.state_dirty = true;
        }
    }

    // ---- upload and paint ------------------------------------------------
    if s.state_dirty {
        let state = scene::state_texels(&grid, &s.snapshot, &s.hillshade, &s.world.landform, Some(&s.selection), s.input.lasso_preview.as_ref(), s.hover);
        s.renderer.lock().unwrap().upload_state(&gpu.queue, &state);
        s.state_dirty = false;
    }
    let pieces: Vec<Piece> = visible
        .iter()
        .enumerate()
        .map(|(k, (i, p))| Piece { highlighted: piece_hover == Some(k) || s.settlement == Some(*i), ..p.clone() })
        .collect();
    let mut verts = scene::piece_vertices(&pieces, &s.proj, &relief, s.morph, s.camera.dist);
    if style.rivers {
        verts.extend(scene::river_vertices(&s.world.rivers, year, &s.proj, &relief, s.morph, s.camera.dist));
        verts.extend(scene::lake_vertices(&s.world.lakes, year, &s.proj, &relief, s.morph, s.camera.dist));
    }
    s.renderer.lock().unwrap().upload_pieces(&gpu.device, &gpu.queue, &verts);

    let ppp = ui.ctx().pixels_per_point();
    let px = [(rect.width() * ppp).round().max(1.0) as u32, (rect.height() * ppp).round().max(1.0) as u32];
    let globals = scene::globals(&view, style, s.mode, &grid, &s.mesh, px[1] as f32);
    ui.painter().add(egui_wgpu::Callback::new_paint_callback(
        rect,
        BoardPaint { renderer: s.renderer.clone(), globals, size: px },
    ));

    // ---- overlays ---------------------------------------------------------
    let to_screen = |p: DVec2| Pos2::new(rect.left() + p.x as f32, rect.top() + p.y as f32);
    let painter = ui.painter_at(rect);
    if s.input.lasso.len() > 1 {
        let mut pts: Vec<Pos2> = s.input.lasso.iter().map(|p| to_screen(*p)).collect();
        pts.push(pts[0]);
        painter.line(pts, Stroke::new(1.5, Color32::from_rgb(120, 200, 255)));
    }
    // Settlement name labels: bigger places are named from further out, in
    // priority order, and a label that would overlap one already placed is
    // skipped. The hovered piece goes first so its name always shows.
    const MAX_LABELS: usize = 150;
    let label_order = piece_hover.into_iter().chain(order.iter().copied().filter(|&k| Some(k) != piece_hover));
    let mut placed: Vec<egui::Rect> = Vec::new();
    let mut drawn = Drawn {
        rect: Some(rect),
        pieces: (0..visible.len())
            .filter_map(|k| on_screen[k].map(|p| (visible[k].0, to_screen(p.base), to_screen(p.top))))
            .filter(|(_, b, _)| rect.contains(*b))
            .collect(),
        labels: Vec::new(),
        piece_hover: piece_hover.map(|k| visible[k].0),
        geo: crate::labels::draw_geography(&painter, rect, &view, &relief, &s.world, &s.snapshot.terrain, year, s.camera.dist),
    };
    // Settlement names: cleaned of catalogue codes, one label per name; places
    // with no recorded population only close in (any place is named when
    // hovered or selected).
    let mut named: Vec<String> = Vec::new();
    for k in label_order {
        if placed.len() >= MAX_LABELS {
            break;
        }
        let Some(p) = on_screen[k] else { continue };
        let (i, piece) = &visible[k];
        let emphasised = piece_hover == Some(k) || s.settlement == Some(*i);
        if !emphasised && s.camera.dist >= label_dist(piece.population) {
            continue;
        }
        let full = &s.world.settlements[*i].name;
        let name = match crate::labels::settlement_label(full) {
            Some(n) => n,
            None if emphasised => full.clone(),
            None => continue,
        };
        if !emphasised && named.iter().any(|n| n.eq_ignore_ascii_case(&name)) {
            continue;
        }
        let font = crate::labels::serif(if emphasised { 16.0 } else { 14.0 });
        let galley = painter.layout_no_wrap(name.clone(), font.clone(), Color32::WHITE);
        let pos = to_screen(p.top) + egui::vec2(0.0, -4.0);
        let r = Align2::CENTER_BOTTOM.anchor_size(pos, galley.size()).expand(2.0);
        if !emphasised && (!rect.contains_rect(r) || placed.iter().any(|q| q.intersects(r))) {
            continue;
        }
        placed.push(r);
        named.push(name.clone());
        drawn.labels.push((*i, r));
        painter.text(pos + egui::vec2(1.0, 1.0), Align2::CENTER_BOTTOM, &name, font.clone(), Color32::from_black_alpha(190));
        painter.text(pos, Align2::CENTER_BOTTOM, &name, font, Color32::WHITE);
    }

    s.input.drawn = drawn;

    // Curved ↔ Flat toggle in the corner.
    let flat = s.morph_target() > 0.5;
    let toggle = egui::Rect::from_min_size(rect.left_top() + egui::vec2(10.0, 10.0), egui::vec2(132.0, 26.0));
    let label = if flat { "Switch to curved" } else { "Switch to flat" };
    if ui.put(toggle, egui::Button::new(label)).on_hover_text("Morph between the curved board and the flat editing layout").clicked() {
        s.toggle_flat(now);
        repaint = true;
    }
    painter.text(
        rect.left_bottom() + egui::vec2(10.0, -8.0),
        Align2::LEFT_BOTTOM,
        "Drag: move · Right-drag / Ctrl-drag: orbit · Scroll: zoom · Double-click: go to hex",
        FontId::proportional(11.0),
        Color32::from_white_alpha(120),
    );

    // Settlement popup.
    if let Some(i) = s.settlement {
        let st = &s.world.settlements[i];
        if !st.exists_at(year) {
            s.settlement = None;
        } else {
            let anchor = visible
                .iter()
                .position(|(j, _)| *j == i)
                .and_then(|k| on_screen[k])
                .map(|p| to_screen(p.top))
                .unwrap_or(rect.center());
            let pos = Pos2::new(
                (anchor.x + 14.0).clamp(rect.left() + 4.0, rect.right() - 200.0),
                (anchor.y - 30.0).clamp(rect.top() + 44.0, rect.bottom() - 110.0),
            );
            let mut open = true;
            egui::Window::new(st.name.as_str())
                .id(egui::Id::unique("settlement_popup"))
                .open(&mut open)
                .collapsible(false)
                .resizable(false)
                .fixed_pos(pos)
                .show(ui.ctx(), |ui| {
                    ui.label(format!("Founded {}", st.founded));
                    match st.population_at(year) {
                        Some(n) => ui.label(format!("Population in {year}: {n}")),
                        None => ui.weak("No population record yet"),
                    };
                });
            if !open {
                s.settlement = None;
            }
        }
    }

    if repaint || s.input.drag.is_some() {
        ui.ctx().request_repaint();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::board::camera::Camera;
    use crate::board::projection::Projection;

    fn grid() -> GridSpec {
        GridSpec { cols: 190, rows: 139, origin_lon: -16.464168425, origin_lat: 75.858035103, w: 0.5773502691896262, h: 0.5 }
    }

    #[test]
    fn lasso_around_one_hex_selects_it() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let mut cam = Camera::initial(&g);
        cam.dist = 0.4;
        let id = g.hex_at(cam.target).unwrap();
        for t in [0.0, 1.0] {
            let view = cam.view(&proj, t, DVec2::new(1000.0, 700.0));
            let c = view.project(g.centre(id)).unwrap();
            let r = 6.0;
            let path = [c + DVec2::new(-r, -r), c + DVec2::new(r, -r), c + DVec2::new(r, r), c + DVec2::new(-r, r)];
            let sel = lasso_select(&g, &view, &Relief::flat(&g), &path, true);
            assert_eq!(sel.iter().collect::<Vec<_>>(), vec![id], "t={t}");
        }
    }

    #[test]
    fn lasso_excludes_hexes_hidden_by_curvature() {
        // From a low angle at the south edge the far (northern) hexes are over
        // the horizon; a lasso over the whole viewport must not select them.
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let mut cam = Camera::initial(&g);
        cam.target = LonLat::new(25.0, 8.0);
        cam.pitch = camera::PITCH_MIN;
        cam.dist = 0.6;
        let size = DVec2::new(1000.0, 700.0);
        let view = cam.view(&proj, 0.0, size);
        let path = [DVec2::ZERO, DVec2::new(size.x, 0.0), size, DVec2::new(0.0, size.y)];
        let all = lasso_select(&g, &view, &Relief::flat(&g), &path, false);
        let visible = lasso_select(&g, &view, &Relief::flat(&g), &path, true);
        assert!(visible.count() > 100);
        assert!(visible.count() < all.count(), "{} vs {}", visible.count(), all.count());
        let north = g.id_at(95, 0);
        assert!(!visible.contains(north));
    }
}
