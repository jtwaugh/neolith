//! The central board view: camera controls, picking, the editor tools'
//! pointer handling, settlement pieces and the paint callback.

use crate::app::{Gpu, Session, Tool};
use crate::board::camera::{self, View};
use crate::board::relief::Relief;
use crate::board::lines;
use crate::board::renderer::{BoardRenderer, Globals, LineMesh};
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

/// Pan inertia decays with this time constant: a coast travels the
/// release speed times this.
const PAN_COAST_SECS: f64 = 0.16;
/// A coast goes at most this share of the distance the drag moved.
const PAN_COAST_SHARE: f64 = 0.5;

/// Most board pixels per egui point on the web while the camera is still,
/// and while it moves (see `board_view`). `?still=` and `?moving=` in the
/// page's URL override them, to tune on a phone.
#[cfg(target_arch = "wasm32")]
const WEB_BOARD_DENSITY: [f32; 2] = [1.5, 1.0];
/// The board stays at its moving density this long after the camera last
/// moved, so a scroll wheel's separate ticks don't flicker between the two.
const MOVING_HOLD_SECS: f64 = 0.2;
/// While the camera moves, the river lines are rebuilt for a zoom only once
/// the distance has changed by this factor (otherwise every 3%).
const MOVING_LINE_STEP: f64 = 1.15;

/// The board's density cap [still, moving], in pixels per point.
fn board_density() -> [f32; 2] {
    static D: std::sync::OnceLock<[f32; 2]> = std::sync::OnceLock::new();
    *D.get_or_init(|| {
        #[cfg(target_arch = "wasm32")]
        let ([still, moving], get) = (WEB_BOARD_DENSITY, crate::perf::query_param);
        // Natively the board is drawn at full density unless
        // NEOLITH_BOARD_DENSITY / NEOLITH_MOVING_DENSITY cap it, e.g. to
        // measure a phone's board on a desktop (see perf.rs).
        #[cfg(not(target_arch = "wasm32"))]
        let ([still, moving], get) = ([f32::INFINITY, f32::INFINITY], |k: &str| {
            std::env::var(if k == "still" { "NEOLITH_BOARD_DENSITY" } else { "NEOLITH_MOVING_DENSITY" }).ok()
        });
        let num = |k: &str, d: f32| get(k).and_then(|v| v.parse::<f32>().ok()).filter(|v| *v > 0.1).unwrap_or(d);
        let still = num("still", still);
        [still, num("moving", moving).min(still)]
    })
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
    /// Where the look-at point was when the current pan began.
    pan_from: Option<LonLat>,
    glide: Option<Glide>,
    /// Where the pointer last was over the board. A touch lifts the pointer
    /// in the same frame as the tap's release, so the click is placed here.
    last_cursor: Option<DVec2>,
    /// A two-finger gesture (pinch, twist, tilt) is in progress.
    gesture: bool,
    /// The opening view was fitted to a tall board, or the user has moved
    /// the camera (after which it is theirs).
    framed: bool,
    /// What the last frame drew, kept so the agent harness can read it.
    pub drawn: Drawn,
    /// When the camera last moved (the board is drawn smaller just after).
    moved_at: Option<f64>,
    /// Sea and region names shown last frame (label hysteresis).
    geo_shown: std::collections::HashSet<String>,
    /// What the uploaded piece/river/lake triangles were built from.
    piece_key: Option<PieceKey>,
    line_key: Option<LineKey>,
    /// The year the uploaded history layer was worked out for ([`scene::history_year`]).
    history_year: Option<neolith_core::Year>,
    /// Which rivers the uploaded river field was built for ([`lines::flowing`]).
    flowing: Option<Vec<Option<bool>>>,
    /// The year (and rivers switch) `flowing` was last checked for.
    flowing_year: Option<(neolith_core::Year, bool)>,
}

/// The inputs of the piece, river and lake triangles. Rivers and lakes are
/// read-only and the projection is fixed for a session (and `BoardInput`
/// is created with the session), so neither needs to be in the key.
struct PieceKey {
    pieces: Vec<Piece>,
    /// Abandoned sites, drawn but never labelled or picked ([`Piece::ruin_of`]).
    ruins: Vec<Piece>,
    /// Compared by identity: the session builds a new `Relief` when heights change.
    relief: Arc<Relief>,
    morph: f64,
    dist: f64,
}

impl PartialEq for PieceKey {
    fn eq(&self, o: &Self) -> bool {
        self.pieces == o.pieces && self.ruins == o.ruins && Arc::ptr_eq(&self.relief, &o.relief) && self.morph == o.morph && self.dist == o.dist
    }
}

/// The inputs of the river and lake lines: the snapshot (they are drawn
/// for its year) and the camera distance rounded as [`lines::build_dist`]
/// does.
struct LineKey {
    rivers: bool,
    snapshot_gen: u64,
    relief: Arc<Relief>,
    morph: f64,
    dist: f64,
}

impl PartialEq for LineKey {
    fn eq(&self, o: &Self) -> bool {
        self.rivers == o.rivers
            && self.snapshot_gen == o.snapshot_gen
            && Arc::ptr_eq(&self.relief, &o.relief)
            && self.morph == o.morph
            && self.dist == o.dist
    }
}

impl BoardInput {
    /// No drag or stroke in progress.
    pub fn is_idle(&self) -> bool {
        self.drag.is_none() && self.stroke.is_none()
    }

    /// The camera is still gliding or coasting after a pan.
    pub fn camera_moving(&self) -> bool {
        self.glide.is_some() || (self.drag.is_none() && self.velocity.length() > 0.02)
    }

    /// Stops any glide or coast (the camera was set directly).
    pub fn stop_camera(&mut self) {
        self.glide = None;
        self.velocity = DVec2::ZERO;
    }

    pub fn glide_to(&mut self, from: LonLat, to: LonLat, now: f64) {
        self.glide = Some(Glide { from, to, start: now });
        self.velocity = DVec2::ZERO;
    }
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
    /// The offscreen target's size, and the part of it drawn this frame.
    size: [u32; 2],
    drawn: [u32; 2],
}

impl egui_wgpu::CallbackTrait for BoardPaint {
    fn prepare(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        _screen: &egui_wgpu::ScreenDescriptor,
        _encoder: &mut wgpu::CommandEncoder,
        _resources: &mut egui_wgpu::CallbackResources,
    ) -> Vec<wgpu::CommandBuffer> {
        // Offscreen colour + depth pass, submitted ahead of egui's own pass;
        // skipped when the board hasn't changed since the last one.
        self.renderer.lock().unwrap().render_if_changed(device, queue, self.size, self.drawn, &self.globals);
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

/// Camera distance from which only famous sites keep their pieces.
const FAR_PIECES_DIST: f64 = 0.9;

/// Whether "fill screen" holds the camera in. Only on the flat board: on
/// the globe, zooming out shows the rest of it, under fog, in its table.
fn fills(style: &BoardStyle, morph: f64) -> bool {
    style.fill_screen && morph >= 0.5
}

/// Screen-space segment (base, top) of a piece, if it faces the camera.
/// Visible-piece indices from most to least important: the selected
/// settlement, then famous sites by renown, then size tier and population,
/// then settlement id (stable while panning).
fn piece_priority(s: &Session, visible: &[(usize, Piece)]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..visible.len()).collect();
    order.sort_by_key(|&k| {
        let (i, p) = &visible[k];
        let renown = s.renown.get(*i).copied().flatten().map_or(0, |f| f.renown);
        (s.settlement != Some(*i), std::cmp::Reverse((renown, p.rank(), p.population)), s.world.settlements[*i].id)
    });
    order
}

/// Below this hex radius on screen (points) only the hovered or selected
/// settlement is named: the far view is for the map, not a carpet of names.
const LABEL_MIN_HEX_PX: f64 = 8.0;

pub fn board_view(ui: &mut egui::Ui, s: &mut Session, style: &BoardStyle, gpu: &Gpu, now: f64, dt: f64) {
    let _span = crate::perf::span("board view");
    let rect = ui.available_rect_before_wrap();
    let resp = ui.allocate_rect(rect, Sense::click_and_drag());
    let size = DVec2::new(rect.width() as f64, rect.height() as f64);
    if size.x < 8.0 || size.y < 8.0 {
        return;
    }
    let grid = s.world.grid.clone();
    // The camera's field of view is vertical, so a tall (phone) board shows
    // the globe's rim and empty table above it: start closer in instead.
    if !s.input.framed && size.x < size.y {
        s.input.framed = true;
        s.camera.dist *= (size.x / size.y).max(0.45).sqrt() * 0.85;
        s.camera.clamp(&grid);
    }
    // As drawn: the editor shows flat tiles (see board_style below).
    s.update_relief(&scene::BoardStyle { art_blend: style.art_blend && !s.editor, ..*style });
    let relief = s.relief.clone();
    let local = |p: Pos2| DVec2::new((p.x - rect.left()) as f64, (p.y - rect.top()) as f64);
    let (modifiers, press_origin, scroll, pinch) =
        ui.input(|i| (i.modifiers, i.pointer.press_origin(), i.smooth_scroll_delta.y as f64, i.zoom_delta() as f64));
    let live_cursor = resp.interact_pointer_pos().or(resp.hover_pos()).map(local);
    if live_cursor.is_some() {
        s.input.last_cursor = live_cursor;
    }
    // On a touch screen the release (and so the click) arrives with the
    // pointer already gone: fall back to where the finger lifted.
    let cursor = live_cursor.or_else(|| (resp.clicked() || resp.double_clicked()).then_some(s.input.last_cursor).flatten());
    let multi = ui.input(|i| i.multi_touch()).filter(|_| resp.contains_pointer() || s.input.gesture);
    let mut repaint = false;

    // ---- two-finger gestures: pinch zooms about the fingers, twist turns
    // the board, moving both fingers up or down tilts it ------------------
    if let Some(m) = multi {
        if !s.input.gesture {
            // The first finger's pan (or stroke) ends where the second lands.
            if let Some(Drag::Paint) = s.input.drag {
                if let Some(stroke) = s.input.stroke.take() {
                    s.finish_stroke(stroke.cmd);
                }
            }
            s.input.drag = None;
            s.input.lasso.clear();
            s.input.lasso_preview = None;
            s.input.gesture = true;
            s.input.framed = true;
        }
        s.input.velocity = DVec2::ZERO;
        s.input.glide = None;
        let centre = local(m.center_pos);
        let anchor = s.camera.view(&s.proj, s.morph, size).pick_relief(centre, &relief);
        s.camera.dist /= (m.zoom_delta as f64).max(0.01);
        let fill = fills(style, s.morph).then_some((&s.proj, s.morph, size, style.fill_margin as f64));
        s.camera.orbit(-m.rotation_delta as f64, m.translation_delta.y as f64 * 0.006, &grid, fill);
        s.camera.clamp(&grid);
        if let Some(ll) = anchor.filter(|ll| grid.hex_at(*ll).is_some()) {
            camera::grab(&mut s.camera, &s.proj, s.morph, size, &grid, &relief, ll, centre);
        }
        repaint = true;
    } else if s.input.gesture && !ui.input(|i| i.any_touches()) {
        s.input.gesture = false;
    }

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
        s.input.velocity *= (-dt / PAN_COAST_SECS).exp();
        repaint = true;
    }
    s.camera.clamp(&grid);

    // ---- zoom towards the cursor ---------------------------------------
    if multi.is_none() && resp.contains_pointer() && (scroll != 0.0 || pinch != 1.0) {
        let anchor = cursor.and_then(|c| s.camera.view(&s.proj, s.morph, size).pick_relief(c, &relief).map(|ll| (c, ll)));
        s.input.framed = true;
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
    if resp.drag_started() && !s.input.gesture {
        let origin = press_origin.map(local).or(cursor).unwrap_or(size / 2.0);
        let view = s.camera.view(&s.proj, s.morph, size);
        let pan = |view: &View| view.pick_relief(origin, &relief).map(|grabbed| Drag::Pan { grabbed });
        s.input.velocity = DVec2::ZERO;
        s.input.glide = None;
        s.input.framed = true;
        s.input.pan_from = Some(s.camera.target);
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
                let fill = fills(style, s.morph).then_some((&s.proj, s.morph, size, style.fill_margin as f64));
                s.camera.orbit(-d.x as f64 * 0.006, d.y as f64 * 0.006, &grid, fill);
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
            // Only a drag that was still moving on release coasts, and it
            // coasts at most half as far again as the drag itself moved the
            // board (a quick flick no longer flings the camera five times
            // further than the hand went).
            Some(Drag::Pan { .. }) => {
                let v = s.input.velocity.length();
                let moved = s.input.pan_from.map_or(0.0, |f| {
                    DVec2::new(s.camera.target.lon - f.lon, s.camera.target.lat - f.lat).length()
                });
                let coast = v * PAN_COAST_SECS;
                if v < 1.0 || moved <= 0.0 {
                    s.input.velocity = DVec2::ZERO;
                } else if coast > PAN_COAST_SHARE * moved {
                    s.input.velocity *= PAN_COAST_SHARE * moved / coast;
                }
                s.input.pan_from = None;
            }
            _ => {}
        }
    }

    // ---- the frame's view; pieces; hover --------------------------------
    s.camera.clamp(&grid);
    if fills(style, s.morph) {
        s.camera.clamp_to_fill(&s.proj, &grid, s.morph, size, style.fill_margin as f64);
    }
    let view = s.camera.view(&s.proj, s.morph, size);
    let year = s.year();
    let pieces_span = crate::perf::span("pieces");
    let visible: Vec<(usize, Piece)> = s
        .world
        .settlements
        .iter()
        .enumerate()
        .filter(|(_, st)| st.exists_at(year))
        // Far out, only the famous sites (and the selected one) keep a
        // piece: hundreds of tiny ones read as noise over the map.
        .filter(|(i, _)| s.camera.dist < FAR_PIECES_DIST || s.settlement == Some(*i) || s.renown.get(*i).is_some_and(|r| r.is_some()))
        .map(|(i, _)| (i, Piece::for_site(&s.world, i, year, s.renown.get(i).copied().flatten())))
        .collect();
    // Ruins of abandoned sites: as many as the living, by the same rule.
    let ruins: Vec<Piece> = (0..s.world.settlements.len())
        .filter(|&i| s.camera.dist < FAR_PIECES_DIST || s.renown.get(i).is_some_and(|r| r.is_some()))
        .filter_map(|i| Piece::ruin_of(&s.world, i, year, s.renown.get(i).copied().flatten()))
        .collect();
    let frames: Vec<PieceFrame> =
        visible.iter().map(|(_, p)| scene::piece_frame(p, &s.proj, &relief, s.morph, s.camera.dist)).collect();
    let on_screen: Vec<Option<ScreenPiece>> = frames.iter().map(|f| scene::piece_on_screen(&view, f)).collect();
    // Label priority; every piece is drawn, only labels are thinned out.
    let order = piece_priority(s, &visible);
    drop(pieces_span);

    let hovering = (resp.contains_pointer() || cursor.is_some()) && s.input.drag.is_none() && !s.input.gesture;
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
        // Move the hover flag texel by texel; a full state upload (when one
        // is already due this frame) picks up `s.hover` itself.
        if !s.state_dirty {
            let mut r = s.renderer.lock().unwrap();
            for (id, on) in [(s.hover, false), (hover, true)] {
                if let Some(id) = id {
                    let (c, row) = grid.col_row(id);
                    r.set_flag(&gpu.queue, c as u32, row as u32, scene::FLAG_HOVER, on);
                }
            }
        }
        s.hover = hover;
    }

    // ---- clicks ----------------------------------------------------------
    if resp.double_clicked() && matches!(s.tool, Tool::Select) {
        if let Some(hex) = s.hover {
            s.glide_to(grid.centre(hex), now);
        }
    } else if resp.clicked() {
        if let Some(k) = piece_hover {
            // A piece takes priority over the hex underneath.
            s.settlement = Some(visible[k].0);
            s.side_tab = crate::panels::SideTab::Selected;
            s.sheet = true;
        } else {
            match (s.tool, s.hover) {
                (Tool::Select, Some(hex)) => {
                    // A hex click replaces a selected settlement.
                    s.inspected = Some(hex);
                    s.settlement = None;
                    s.side_tab = crate::panels::SideTab::Selected;
                    s.sheet = true;
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
    // ---- is the camera moving? While it is, the board is drawn smaller
    // and the river lines rebuilt less often (see below).
    let in_motion = matches!(s.input.drag, Some(Drag::Pan { .. } | Drag::Orbit))
        || s.input.gesture
        || s.input.camera_moving()
        || (resp.contains_pointer() && (scroll != 0.0 || pinch != 1.0))
        || s.morph_anim.is_some();
    if in_motion {
        s.input.moved_at = Some(now);
    }
    let since_moved = s.input.moved_at.map_or(f64::INFINITY, |t| now - t);
    let moving = since_moved < MOVING_HOLD_SECS;

    let upload_span = crate::perf::span("uploads");
    if s.state_dirty {
        let state = scene::state_texels(&grid, &s.snapshot, &s.hillshade, &s.world.landform, &s.world.survey, Some(&s.selection), s.input.lasso_preview.as_ref(), s.hover);
        s.renderer.lock().unwrap().upload_state(&gpu.queue, &state);
        s.state_dirty = false;
    }
    if s.evidence_dirty {
        let texels = scene::evidence_texels(&grid, &s.overlay_codes());
        s.renderer.lock().unwrap().upload_evidence(&gpu.queue, &texels);
        s.evidence_dirty = false;
    }
    // What people have done to the land by now (clearings, fields).
    let history_year = scene::history_year(year);
    if s.input.history_year != Some(history_year) {
        let _span = crate::perf::span("history");
        let texels = scene::history_texels(&s.world, history_year);
        s.renderer.lock().unwrap().upload_history(&gpu.queue, &texels);
        s.input.history_year = Some(history_year);
    }
    let pieces: Vec<Piece> = visible
        .iter()
        .enumerate()
        .map(|(k, (i, p))| Piece { highlighted: piece_hover == Some(k) || s.settlement == Some(*i), ..p.clone() })
        .collect();
    // Rebuild the piece triangles, and separately the river and lake ones,
    // only when their inputs change. Panning, the clock between river fades
    // and epochs, and panel repaints keep them.
    let key = PieceKey { pieces, ruins, relief: relief.clone(), morph: s.morph, dist: s.camera.dist };
    if s.input.piece_key.as_ref() != Some(&key) {
        let _span = crate::perf::span("piece mesh");
        let verts = scene::piece_vertices(&[&key.ruins[..], &key.pieces[..]].concat(), &s.proj, &relief, s.morph, s.camera.dist);
        let mut renderer = s.renderer.lock().unwrap();
        renderer.upload_pieces(&gpu.device, &gpu.queue, &verts);
        renderer.upload_camps(&gpu.queue, &scene::camp_texels(&grid, &key.pieces));
        drop(renderer);
        s.input.piece_key = Some(key);
    }
    let line_key = LineKey {
        rivers: style.rivers,
        snapshot_gen: s.snapshot_gen,
        relief: relief.clone(),
        morph: s.morph,
        // While the camera moves, a zoom has to change the lines' width by
        // more before they are rebuilt (each build costs several ms, more
        // on a phone); they catch up when it stops.
        dist: match &s.input.line_key {
            Some(k) if moving && (lines::build_dist(s.camera.dist) / k.dist).ln().abs() < MOVING_LINE_STEP.ln() => k.dist,
            _ => lines::build_dist(s.camera.dist),
        },
    };
    if s.input.line_key.as_ref() != Some(&line_key) {
        let _span = crate::perf::span("line mesh");
        let mut line_mesh = LineMesh::default();
        if style.rivers {
            let board = lines::Board { proj: &s.proj, relief: &relief, t: s.morph, cam_dist: line_key.dist };
            lines::rivers(&mut line_mesh, &s.world.rivers, &s.world.lakes, &s.snapshot, &board);
        }
        s.renderer.lock().unwrap().upload_lines(&gpu.device, &gpu.queue, &line_mesh);
        s.input.line_key = Some(line_key);
    }
    // The river field only changes when a river starts, stops or turns
    // seasonal, not with every year or camera move.
    if s.input.flowing_year != Some((year, style.rivers)) {
        let flowing = if style.rivers { lines::flowing(&s.world.rivers, year) } else { Vec::new() };
        if s.input.flowing.as_ref() != Some(&flowing) {
            let field = lines::river_field(&s.world.rivers, &flowing, &grid);
            s.renderer.lock().unwrap().upload_river_field(&gpu.queue, &field);
            s.input.flowing = Some(flowing);
        }
        s.input.flowing_year = Some((year, style.rivers));
    }

    drop(upload_span);

    // The board's offscreen resolution, in pixels. On the web it is capped
    // below a high-DPI screen's density (the blit upscales it linearly): the
    // board shader is per-pixel heavy, browsers' GPU budgets are tighter and
    // 2× density costs ~1.8× the pixels of 1.5×. While the camera moves it
    // is drawn smaller still, which motion hides: a phone's GPU then keeps
    // up with a pan or pinch, and the board sharpens the moment it stops.
    // Native renders at full density.
    let [still_density, moving_density] = board_density();
    let ppp = ui.ctx().pixels_per_point();
    let pixels = |density: f32| {
        let d = ppp.min(density);
        [(rect.width() * d).round().max(1.0) as u32, (rect.height() * d).round().max(1.0) as u32]
    };
    let px = pixels(still_density);
    let drawn = if moving {
        if !in_motion {
            // Come back for the sharp frame once the hold is over.
            ui.ctx().request_repaint_after(std::time::Duration::from_secs_f64(MOVING_HOLD_SECS - since_moved));
        }
        pixels(moving_density)
    } else {
        px
    };
    // Editing wants the whole map sharp and its colours as painted.
    // The editor paints hexes, so it shows the crisp hex board: no ground field or smooth relief.
    let board_style = scene::BoardStyle {
        depth: if s.editor { 0.0 } else { style.depth },
        art_blend: style.art_blend && !s.editor,
        ..*style
    };
    // Level of detail follows the full-density size, so the terrain art
    // doesn't thin out while the camera moves and pop back when it stops.
    let globals = scene::globals(&view, &board_style, s.mode, &grid, &s.mesh, px[1] as f32);
    ui.painter().add(egui_wgpu::Callback::new_paint_callback(
        rect,
        BoardPaint { renderer: s.renderer.clone(), globals, size: px, drawn },
    ));

    // ---- overlays ---------------------------------------------------------
    let to_screen = |p: DVec2| Pos2::new(rect.left() + p.x as f32, rect.top() + p.y as f32);
    let painter = ui.painter_at(rect);
    if s.input.lasso.len() > 1 {
        let mut pts: Vec<Pos2> = s.input.lasso.iter().map(|p| to_screen(*p)).collect();
        pts.push(pts[0]);
        painter.line(pts, Stroke::new(1.5, Color32::from_rgb(120, 200, 255)));
    }
    // Settlement name labels, in two passes. First the hovered and selected
    // pieces and the famous sites ([`crate::renown`]), which are placed
    // before any geography name so a river can't evict Göbekli Tepe; then
    // the geography, routed around them; then every other site, around
    // both. Names are cleaned of catalogue codes, one label per name, and
    // placed by collision alone, in priority order.
    let labels_span = crate::perf::span("labels");
    const MAX_LABELS: usize = 150;
    let hex_px = scene::hex_px(&view, &grid, s.camera.dist);
    let names_on = hex_px >= LABEL_MIN_HEX_PX;
    let fame: Vec<Option<crate::renown::Renowned>> =
        visible.iter().map(|(i, _)| s.renown.get(*i).copied().flatten()).collect();
    // How far out a famous name stays: renown 3 at every zoom, 2 from half
    // the usual hex size, 1 with everything else.
    let fame_shown = |r: u8| names_on || r >= 3 || (r >= 2 && hex_px >= LABEL_MIN_HEX_PX * 0.5);
    // Each piece's body (and its star) on screen. A name keeps off every
    // piece but its own, so a neighbour's name never sits on Jericho's stone.
    let bodies: Vec<Option<egui::Rect>> = (0..visible.len())
        .map(|k| {
            let p = on_screen[k]?;
            let r = p.radius_px.max(2.0) as f32;
            let (b, t) = (to_screen(p.base), to_screen(p.top));
            let star = if visible[k].1.starred() { 1.4 * r } else { 0.0 };
            Some(egui::Rect::from_two_pos(b, t).expand2(egui::vec2(r, 0.0)).union(egui::Rect::from_center_size(t, egui::vec2(2.0 * r, 2.0 * (r + star)))))
        })
        .collect();
    // The gap around an ordinary site name: wide at regional zoom, closing
    // in as the view nears single hexes. The names are placed in a fixed
    // priority order, so the same ones win wherever the view is panned.
    let close = ((hex_px - LABEL_MIN_HEX_PX) / (48.0 - LABEL_MIN_HEX_PX)).clamp(0.0, 1.0) as f32;
    let spacing = egui::vec2(70.0 - 50.0 * close, 40.0 - 28.0 * close);
    struct Placed {
        i: usize,
        pos: Pos2,
        align: Align2,
        name: String,
        font: FontId,
        rect: egui::Rect,
    }
    let place = |k: usize, placed: &[egui::Rect], named: &[String], forced: bool| -> Option<Placed> {
        let body = bodies[k]?;
        let (i, piece) = &visible[k];
        let emphasised = piece_hover == Some(k) || s.settlement == Some(*i);
        let renown = fame[k].map_or(0, |f| f.renown);
        let name = match (fame[k], crate::labels::settlement_label(&s.world.settlements[*i].name)) {
            (Some(f), _) => f.entry().name.clone(),
            (None, Some(n)) => n,
            (None, None) if emphasised => s.world.settlements[*i].name.clone(),
            (None, None) => return None,
        };
        if !emphasised && (piece.inferred || named.iter().any(|n| n.eq_ignore_ascii_case(&name))) {
            return None;
        }
        let size = match (emphasised, renown) {
            (true, _) | (_, 3) => 17.0,
            (_, 2) => 15.5,
            _ => 14.0,
        };
        let font = crate::labels::serif(size);
        let g = painter.layout_no_wrap(name.clone(), font.clone(), Color32::WHITE).size();
        // Under the piece first, like a nameplate; then beside it (level
        // with the piece's middle, not its star); then above.
        let mid = on_screen[k].map_or(body.center().y, |p| to_screen((p.base + p.top) * 0.5).y);
        let anchors = [
            (Align2::CENTER_TOP, egui::pos2(body.center().x, body.bottom() + 1.0)),
            (Align2::LEFT_CENTER, egui::pos2(body.right() + 4.0, mid)),
            (Align2::RIGHT_CENTER, egui::pos2(body.left() - 4.0, mid)),
            (Align2::CENTER_BOTTOM, egui::pos2(body.center().x, body.top() - 1.0)),
        ];
        // Ordinary names keep a wider gap (`spacing`), so a crowded region
        // shows its leading sites rather than a carpet; famous names only
        // need air.
        let gap = if forced { egui::vec2(4.0, 4.0) } else { spacing };
        let fits = |r: egui::Rect, against_pieces: bool| {
            let padded = r.expand2(gap);
            rect.contains_rect(r)
                && !placed.iter().any(|q| q.intersects(padded))
                && !(against_pieces && bodies.iter().enumerate().any(|(j, b)| j != k && b.is_some_and(|b| b.intersects(r))))
        };
        let at = |(align, pos): (Align2, Pos2)| (align, pos, align.anchor_size(pos, g).expand(2.0));
        let chosen = if emphasised {
            Some(at(anchors[0]))
        } else {
            anchors.iter().map(|a| at(*a)).find(|(_, _, r)| fits(*r, true)).or_else(|| {
                // A famous name is shown even over a neighbour's piece.
                let first = at(anchors[0]);
                (forced && fits(first.2, false)).then_some(first)
            })
        }?;
        Some(Placed { i: *i, pos: chosen.1, align: chosen.0, name, font, rect: chosen.2 })
    };
    let mut labels: Vec<Placed> = Vec::new();
    let mut placed: Vec<egui::Rect> = Vec::new();
    let mut named: Vec<String> = Vec::new();
    let first_pass = piece_hover.into_iter().chain(order.iter().copied().filter(|&k| Some(k) != piece_hover));
    for k in first_pass {
        let (i, _) = &visible[k];
        let emphasised = piece_hover == Some(k) || s.settlement == Some(*i);
        if !emphasised && !fame[k].is_some_and(|f| fame_shown(f.renown)) {
            continue;
        }
        if let Some(p) = place(k, &placed, &named, true) {
            placed.push(p.rect.expand(4.0));
            named.push(p.name.clone());
            labels.push(p);
        }
    }
    let mut drawn = Drawn {
        rect: Some(rect),
        pieces: (0..visible.len())
            .filter_map(|k| on_screen[k].map(|p| (visible[k].0, to_screen(p.base), to_screen(p.top))))
            .filter(|(_, b, _)| rect.contains(*b))
            .collect(),
        labels: Vec::new(),
        piece_hover: piece_hover.map(|k| visible[k].0),
        geo: crate::labels::draw_geography(
            &painter,
            rect,
            &view,
            &relief,
            &s.world,
            &s.snapshot.terrain,
            year,
            s.camera.dist,
            &mut s.input.geo_shown,
            &placed,
        ),
    };
    // Region, sea and mountain names are broad and faint, and a famous name
    // is drawn over them; the rest of the sites keep off every geography name.
    placed.extend(drawn.geo.iter().map(|g| g.bounds));
    if names_on {
        for &k in &order {
            if labels.len() >= MAX_LABELS {
                break;
            }
            let (i, _) = &visible[k];
            if fame[k].is_some() || piece_hover == Some(k) || s.settlement == Some(*i) {
                continue;
            }
            if let Some(p) = place(k, &placed, &named, false) {
                placed.push(p.rect.expand(4.0));
                named.push(p.name.clone());
                labels.push(p);
            }
        }
    }
    for p in labels {
        drawn.labels.push((p.i, p.rect));
        crate::labels::haloed_text(&painter, p.pos, p.align, &p.name, p.font, Color32::WHITE);
    }

    s.input.drawn = drawn;
    drop(labels_span);
    crate::perf::overlay(&painter, rect);

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
        if ui.input(|i| i.has_touch_screen()) {
            "Pinch: zoom · Twist: turn · Two fingers up/down: tilt · Tap: inspect"
        } else {
            "Drag: move · Right-drag / Ctrl-drag: orbit · Scroll: zoom · Double-click: go to hex"
        },
        FontId::proportional(11.0),
        Color32::from_white_alpha(120),
    );

    // The selected settlement's record is in the sidebar (panels::selected);
    // it closes when the clock leaves the settlement's lifetime.
    if s.settlement.is_some_and(|i| !s.world.settlements[i].exists_at(year)) {
        s.settlement = None;
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
