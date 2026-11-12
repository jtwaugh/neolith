//! egui screens and panels: start screen, top bar, timeline, tool palette,
//! inspector, board-style window.

use crate::app::{NeolithApp, Screen, Session, Tool, DEFAULT_START_YEAR};
use crate::board::scene::{ArtMode, BoardStyle, Material};
use crate::clock::{SPEED_MAX, SPEED_MIN};
use crate::palette;
use egui::{vec2, Align2, Color32, FontId, Rect, RichText, Sense, Stroke};
use neolith_core::{
    elevation, pencil, Command, Edit, HexId, KeyMode, Koeppen, MapMode, PopDensity, Prop, RiverClass, RiverState, Terrain, Value, World,
    Year, NO_DATA, NO_ELEVATION,
};

/// A small colour swatch.
fn swatch(ui: &mut egui::Ui, v: Value) {
    swatch_rgb(ui, palette::colour(v));
}

fn swatch_rgb(ui: &mut egui::Ui, [r, g, b]: palette::Rgb) {
    let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
    ui.painter().rect_filled(rect, 3.0, Color32::from_rgb(r, g, b));
    ui.painter().rect_stroke(rect, 3.0, Stroke::new(1.0, ui.visuals().weak_text_color()), egui::StrokeKind::Inside);
}

impl NeolithApp {
    pub fn start_screen(&mut self, ui: &mut egui::Ui) {
        let Some(session) = &mut self.session else { return };
        let (min, max) = session.clock.range();
        let mut start = false;
        egui::CentralPanel::default().show(ui, |ui| {
            ui.vertical_centered(|ui| {
                ui.add_space(ui.available_height() * 0.22);
                ui.label(RichText::new("Neolithic Deities").size(44.0).strong());
                ui.add_space(6.0);
                ui.label("A map-staring game set in the Neolithic.");
                ui.add_space(4.0);
                ui.weak(format!(
                    "{} hexes · {} keyframes ({} – {}) · {} settlements",
                    session.world.grid.len(),
                    session.keyframes.len(),
                    min,
                    session.keyframes.last().copied().unwrap_or(min),
                    session.world.settlements.len()
                ));
                ui.add_space(28.0);
                ui.horizontal(|ui| {
                    // Centre the row by hand: label + drag value + era + button.
                    let row = 330.0;
                    ui.add_space(((ui.available_width() - row) / 2.0).max(0.0));
                    ui.label("Start year");
                    self.start_year = self.start_year.clamp(min.0, max.0);
                    ui.add(
                        egui::DragValue::new(&mut self.start_year)
                            .range(min.0..=max.0)
                            .speed(10.0)
                            .custom_formatter(|v, _| format!("{}", v.abs() as i64))
                            .custom_parser(|s| s.trim().trim_start_matches('-').parse::<f64>().ok().map(|v| -v.abs())),
                    );
                    ui.label(if self.start_year < 0 { "BCE" } else { "CE" });
                    ui.add_space(12.0);
                    if ui.add(egui::Button::new(RichText::new("Start").size(16.0)).min_size(vec2(90.0, 28.0))).clicked() {
                        start = true;
                    }
                });
                if self.start_year != DEFAULT_START_YEAR && ui.small_button("Reset to 7500 BCE").clicked() {
                    self.start_year = DEFAULT_START_YEAR;
                }
            });
        });
        if start {
            session.clock.set_year(Year(self.start_year));
            self.screen = Screen::Main;
        }
    }

    pub fn main_screen(&mut self, ui: &mut egui::Ui, now: f64, dt: f64) {
        let ctx = ui.ctx().clone();
        self.shortcuts(&ctx);
        self.top_bar(ui, now);
        self.timeline(ui);
        let Some(session) = &mut self.session else { return };
        if session.editor {
            egui::Panel::left("tools").resizable(false).exact_size(210.0).show(ui, |ui| tools_panel(ui, session));
        }
        egui::Panel::right("inspector")
            .resizable(true)
            .default_size(270.0)
            .min_size(220.0)
            .show(ui, |ui| inspector(ui, session));
        if self.show_style {
            style_window(&ctx, &mut self.show_style, &mut self.style, session);
        }
        egui::CentralPanel::default().frame(egui::Frame::NONE).show(ui, |ui| {
            crate::view::board_view(ui, session, &self.style, self.gpu.as_ref().unwrap(), now, dt);
        });
        if let Some(rect) = session.input.drawn.rect {
            legend_card(&ctx, rect, session);
        }
    }

    fn shortcuts(&mut self, ctx: &egui::Context) {
        use egui::{Key, KeyboardShortcut, Modifiers};
        let Some(s) = &mut self.session else { return };
        if ctx.egui_wants_keyboard_input() {
            return;
        }
        let redo = KeyboardShortcut::new(Modifiers::COMMAND | Modifiers::SHIFT, Key::Z);
        let undo = KeyboardShortcut::new(Modifiers::COMMAND, Key::Z);
        let (do_redo, do_undo, space) = ctx.input_mut(|i| {
            let r = i.consume_shortcut(&redo) || i.consume_key(Modifiers::COMMAND, Key::Y);
            (r, i.consume_shortcut(&undo), i.consume_key(Modifiers::NONE, Key::Space))
        });
        if s.editor && do_redo {
            s.redo();
        } else if s.editor && do_undo {
            s.undo();
        }
        if space && !s.editor {
            s.clock.playing = !s.clock.playing;
        }
    }

    fn top_bar(&mut self, ui: &mut egui::Ui, now: f64) {
        let ctx = ui.ctx().clone();
        let (mut open, mut save) = (false, false);
        egui::Panel::top("top").show(ui, |ui| {
            let Some(s) = &mut self.session else { return };
            ui.horizontal(|ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("Open world…").clicked() {
                        open = true;
                        ui.close();
                    }
                    let label = if cfg!(target_arch = "wasm32") { "Download world.bin" } else { "Save world as…" };
                    if ui.button(label).clicked() {
                        save = true;
                        ui.close();
                    }
                });
                ui.separator();
                ui.label("Map:");
                for mode in MapMode::MENU {
                    if ui.selectable_label(s.mode == mode, mode.label()).clicked() {
                        s.mode = mode;
                    }
                }
                ui.separator();
                ui.label("Terrain art:").on_hover_text(
                    "Trees, peaks, shores and other terrain illustrations inside the hexes (visible when zoomed in)",
                );
                for art in ArtMode::ALL {
                    ui.selectable_value(&mut self.style.terrain_art, art, art.label());
                }
                ui.separator();
                ui.toggle_value(&mut self.style.relief, "Relief").on_hover_text(
                    "Raise each tile to its height: land elevation, lakes at their level, the sea at sea level \
                     (exaggeration in Board style)",
                );
                ui.separator();
                let mut editor = s.editor;
                ui.selectable_value(&mut editor, false, "Game");
                ui.selectable_value(&mut editor, true, "Editor");
                if editor != s.editor {
                    s.set_editor(editor);
                }
                ui.separator();
                ui.toggle_value(&mut self.show_style, "Board style");
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let name = s.file_name.rsplit(['/', '\\']).next().unwrap_or(&s.file_name);
                    ui.weak(format!("{name}{}", if s.unsaved { " • unsaved edits" } else { "" }));
                    if let Some((msg, t)) = &self.status {
                        if now - t < 6.0 {
                            ui.separator();
                            ui.label(msg);
                        }
                    }
                });
            });
        });
        if open {
            self.files.open_dialog(&ctx);
        }
        if save {
            self.save(&ctx);
        }
    }

    /// Bottom bar: play/pause, speed, the year scrubber and the readout.
    fn timeline(&mut self, ui: &mut egui::Ui) {
        let Some(s) = &mut self.session else { return };
        egui::Panel::bottom("timeline").show(ui, |ui| {
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                let label = if s.clock.playing { "Pause" } else { "Play" };
                let play = ui.add_enabled(!s.editor, egui::Button::new(label).min_size(vec2(72.0, 24.0)));
                if play.on_disabled_hover_text("The clock is paused in editor mode").clicked() {
                    let (_, max) = s.clock.range();
                    if !s.clock.playing && s.year() >= max {
                        let (min, _) = s.clock.range();
                        s.clock.set_year(min); // replay from the start
                    }
                    s.clock.playing = !s.clock.playing;
                }
                ui.add(
                    egui::Slider::new(&mut s.clock.years_per_sec, SPEED_MIN..=SPEED_MAX)
                        .logarithmic(true)
                        .custom_formatter(|v, _| format!("{v:.0}"))
                        .suffix(" yr/s"),
                )
                .on_hover_text("Speed: years per second");
                ui.separator();
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.add_sized(
                        vec2(96.0, 20.0),
                        egui::Label::new(RichText::new(s.year().to_string()).strong().size(15.0)),
                    );
                    scrubber(ui, s);
                });
            });
            ui.add_space(2.0);
        });
    }
}

/// The year scrubber: a track with tick marks at the keyframes. Dragging
/// (in either direction) sets the year through the same clock as playback.
fn scrubber(ui: &mut egui::Ui, s: &mut Session) {
    let (min, max) = s.clock.range();
    let width = ui.available_width().max(80.0);
    let (rect, resp) = ui.allocate_exact_size(vec2(width, 34.0), Sense::click_and_drag());
    let track = Rect::from_min_max(rect.left_center() + vec2(8.0, -2.0), rect.right_center() + vec2(-8.0, 2.0));
    let span = (max.0 - min.0).max(1) as f32;
    let x_of = |y: Year| track.left() + (y.0 - min.0) as f32 / span * track.width();
    if let Some(pos) = resp.interact_pointer_pos() {
        if resp.dragged() || resp.clicked() || resp.is_pointer_button_down_on() {
            let f = ((pos.x - track.left()) / track.width()).clamp(0.0, 1.0);
            s.clock.set_year(Year(min.0 + (f * span).round() as i32));
        }
    }
    let visuals = ui.visuals();
    let p = ui.painter_at(rect);
    p.rect_filled(track, 2.0, visuals.widgets.inactive.bg_fill);
    let x_now = x_of(s.year());
    p.rect_filled(Rect::from_min_max(track.min, egui::pos2(x_now, track.bottom())), 2.0, visuals.selection.bg_fill);
    let mut last_label_x = f32::NEG_INFINITY;
    for k in &s.keyframes {
        let x = x_of(*k);
        p.line_segment(
            [egui::pos2(x, track.top() - 5.0), egui::pos2(x, track.bottom() + 5.0)],
            Stroke::new(1.5, visuals.text_color()),
        );
        if x - last_label_x > 46.0 {
            p.text(
                egui::pos2(x.clamp(rect.left() + 14.0, rect.right() - 14.0), rect.bottom()),
                Align2::CENTER_BOTTOM,
                format!("{}", -k.0),
                FontId::proportional(9.5),
                visuals.weak_text_color(),
            );
            last_label_x = x;
        }
    }
    p.circle_filled(egui::pos2(x_now, track.center().y), 7.0, visuals.strong_text_color());
    p.circle_filled(egui::pos2(x_now, track.center().y), 4.5, visuals.selection.bg_fill);
    resp.on_hover_text("Drag to scrub. Ticks mark keyframes (years BCE).");
}

/// Left panel (editor mode): tools, the typed palette, selection, undo/redo.
fn tools_panel(ui: &mut egui::Ui, s: &mut Session) {
    ui.add_space(6.0);
    ui.strong("Tools");
    ui.horizontal_wrapped(|ui| {
        for (tool, label, hint) in [
            (Tool::Select, "Select", "Click a hex to inspect and select it (Shift-click adds). Drag to move the board."),
            (Tool::Pencil, "Pencil", "Click or drag to paint the palette value. One drag is one undo step."),
            (Tool::Fill, "Fill", "Flood-fill the connected region that shares the clicked hex's value."),
            (Tool::Lasso, "Lasso", "Drag around hexes to select them. Shift adds, Alt removes."),
        ] {
            ui.selectable_value(&mut s.tool, tool, label).on_hover_text(hint);
        }
    });
    ui.weak("Pan: middle-drag · Orbit: right-drag");

    ui.add_space(8.0);
    ui.strong("Keyframe");
    let mut insert = s.key_mode == KeyMode::InsertAtYear;
    ui.checkbox(&mut insert, "Insert keyframe at current year")
        .on_hover_text("Off: edits change the keyframe in effect.\nOn: edits create a keyframe at the current year.");
    s.key_mode = if insert { KeyMode::InsertAtYear } else { KeyMode::InEffect };
    let key = s.edit_key();
    let exists = s.keyframes.binary_search(&key).is_ok();
    ui.label(if exists {
        RichText::new(format!("Editing keyframe: {key}"))
    } else {
        RichText::new(format!("New keyframe at {key}")).color(ui.visuals().warn_fg_color)
    });

    ui.add_space(8.0);
    ui.horizontal(|ui| {
        let undo = ui.add_enabled(s.history.can_undo(), egui::Button::new("Undo"));
        if undo.on_hover_text(s.history.undo_label().unwrap_or("Nothing to undo")).clicked() {
            s.undo();
        }
        let redo = ui.add_enabled(s.history.can_redo(), egui::Button::new("Redo"));
        if redo.on_hover_text(s.history.redo_label().unwrap_or("Nothing to redo")).clicked() {
            s.redo();
        }
    });

    ui.add_space(8.0);
    ui.strong("Selection");
    ui.label(format!("{} hexes", s.selection.count()));
    ui.horizontal(|ui| {
        if ui.button("All").clicked() {
            s.selection.select_all();
            s.state_dirty = true;
        }
        if ui.button("None").clicked() {
            s.selection.clear();
            s.state_dirty = true;
        }
        let paint = s.paint_value();
        if ui.add_enabled(!s.selection.is_empty() && paint.is_some(), egui::Button::new("Paint")).on_hover_text("Paint the palette value onto every selected hex").clicked() {
            if let Some(value) = paint {
                let mut cmd = pencil(&s.world, s.selection.iter(), value, s.year(), s.key_mode);
                cmd.label = "Paint selection";
                s.apply(cmd);
            }
        }
    });

    ui.add_space(8.0);
    ui.strong(format!("Palette — {}", s.mode.label()));
    let Some(mode) = s.mode.prop() else {
        // Elevation comes from the pipeline (ETOPO1) and is not editable here.
        ui.weak("Read-only: from ETOPO1 via the pipeline. Switch map mode to paint.");
        egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, elevation_legend);
        return;
    };
    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        for v in mode.values() {
            let selected = s.paint[mode.index()] == v;
            ui.horizontal(|ui| {
                swatch(ui, v);
                if ui.selectable_label(selected, v.label()).clicked() {
                    s.paint[mode.index()] = v;
                    if s.tool == Tool::Select {
                        s.tool = Tool::Pencil;
                    }
                }
            });
        }
    });
}

/// The legend for the current map mode, floating over the board's lower-left
/// corner. Terrain and Köppen list the values present this year, most common
/// first; Population is the whole ramp; Elevation the bands.
fn legend_card(ctx: &egui::Context, board: Rect, s: &Session) {
    const MAX_ROWS: usize = 12;
    let frame = egui::Frame::popup(&ctx.global_style()).fill(Color32::from_black_alpha(190)).corner_radius(6.0);
    egui::Area::new(egui::Id::unique("legend"))
        .order(egui::Order::Foreground)
        .pivot(Align2::LEFT_BOTTOM)
        .fixed_pos(board.left_bottom() + vec2(10.0, -30.0))
        .show(ctx, |ui| {
            frame.show(ui, |ui| {
                ui.set_max_width(260.0);
                egui::CollapsingHeader::new(RichText::new(format!("Legend · {}", s.mode.label())).strong())
                    .id_salt("legend-open")
                    .default_open(true)
                    .show(ui, |ui| {
                        let counts = |layer: &[u8], skip_water: bool| {
                            let mut n = [0usize; 256];
                            for (i, v) in layer.iter().enumerate() {
                                if !(skip_water && s.snapshot.terrain[i] == Terrain::Water as u8) {
                                    n[*v as usize] += 1;
                                }
                            }
                            let mut present: Vec<(u8, usize)> =
                                (0..=255u8).filter(|v| *v != NO_DATA && n[*v as usize] > 0).map(|v| (v, n[v as usize])).collect();
                            present.sort_by(|a, b| b.1.cmp(&a.1));
                            present
                        };
                        let sea_row = |ui: &mut egui::Ui| {
                            ui.horizontal(|ui| {
                                swatch_rgb(ui, palette::SEA_COLOUR);
                                ui.label("Sea and lakes");
                            });
                        };
                        let more = |ui: &mut egui::Ui, n: usize| {
                            if n > MAX_ROWS {
                                ui.weak(format!("… and {} rarer", n - MAX_ROWS));
                            }
                        };
                        match s.mode {
                            MapMode::Terrain => {
                                let present = counts(&s.snapshot.terrain, false);
                                for (v, _) in present.iter().take(MAX_ROWS) {
                                    if let Some(val) = Value::from_u8(Prop::Terrain, *v) {
                                        ui.horizontal(|ui| {
                                            swatch(ui, val);
                                            ui.label(val.label());
                                        });
                                    }
                                }
                                more(ui, present.len());
                            }
                            MapMode::Koeppen => {
                                let present = counts(&s.snapshot.koeppen, true);
                                for (v, _) in present.iter().take(MAX_ROWS) {
                                    if let Some(k) = Koeppen::new(*v) {
                                        ui.horizontal(|ui| {
                                            swatch(ui, Value::Koeppen(k));
                                            ui.label(RichText::new(k.code()).monospace());
                                            ui.label(k.description());
                                        });
                                    }
                                }
                                more(ui, present.len());
                                sea_row(ui);
                            }
                            MapMode::Pop => {
                                for p in PopDensity::ALL.iter().rev() {
                                    ui.horizontal(|ui| {
                                        swatch(ui, Value::Pop(*p));
                                        ui.label(Value::Pop(*p).label());
                                    });
                                }
                                sea_row(ui);
                            }
                            MapMode::Elevation => elevation_legend(ui),
                        }
                    });
            });
        });
}

/// Elevation bands, highest land first, then water from shallow to deep.
fn elevation_legend(ui: &mut egui::Ui) {
    for b in (0..elevation::BAND_COUNT).rev() {
        if b == elevation::LAND_BAND - 1 {
            ui.add_space(4.0);
        }
        ui.horizontal(|ui| {
            swatch_rgb(ui, palette::elevation(b));
            ui.label(elevation::band_label(b).unwrap_or_default());
        });
    }
}

/// Right panel: the hovered or selected hex, its current values and each
/// property's keyframe table (editable in place with typed dropdowns).
fn inspector(ui: &mut egui::Ui, s: &mut Session) {
    ui.add_space(6.0);
    let Some(hex) = s.inspected.or(s.hover) else {
        ui.strong("Inspector");
        ui.weak("Hover or click a hex.");
        return;
    };
    let pinned = s.inspected == Some(hex);
    let (col, row) = s.world.grid.col_row(hex);
    let centre = s.world.grid.centre(hex);
    ui.horizontal(|ui| {
        ui.strong(format!("Hex {}", hex.geojson_id()));
        ui.weak(if pinned { "selected" } else { "hover" });
        if pinned && ui.small_button("x").on_hover_text("Deselect").clicked() {
            s.inspected = None;
        }
    });
    ui.weak(format!("col {col}, row {row} · {:.2}°, {:.2}°", centre.lon, centre.lat));
    ui.add_space(4.0);

    let year = s.year();
    let mut edit: Option<Command> = None;
    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        for prop in Prop::ALL {
            ui.horizontal(|ui| match s.world.value_at(hex, prop, year) {
                Some(v) => {
                    swatch(ui, v);
                    ui.label(format!("{}: {}", prop.label(), v.label()));
                }
                None => {
                    ui.weak(format!("{}: no data before the first keyframe", prop.label()));
                }
            });
        }
        ui.horizontal(|ui| match s.world.elevation[hex.index()] {
            NO_ELEVATION => {
                ui.weak("Elevation: no data in this file");
            }
            z => {
                swatch_rgb(ui, palette::elevation(s.snapshot.elevation[hex.index()]));
                ui.label(format!("Elevation: {z} m"))
                    .on_hover_text("Median of the ETOPO1 cells in the hex, relative to today's sea level");
            }
        });
        if let Some(l) = s.world.landform[hex.index()] {
            ui.label(format!("Landform: {}", l.label())).on_hover_text(
                "From the share of the hex's ETOPO1 cells that are mountain (Kapos et al. 2000 bands) \
                 and its median elevation; static",
            );
        }
        for l in &s.world.lakes {
            if let Some(shape) = l.shape_at(year) {
                if shape.contains(centre) {
                    ui.label(format!("Lake: {} ({:.0} m)", l.name, shape.level));
                }
            }
        }
        let rivers = rivers_in_hex(&s.world, hex, year);
        let class = s.world.river[hex.index()].at(year).and_then(RiverClass::from_u8).unwrap_or(RiverClass::None);
        ui.horizontal_wrapped(|ui| {
            if rivers.is_empty() {
                ui.weak("River: none");
            } else {
                let list: Vec<String> = rivers.iter().map(|(n, st)| format!("{n} ({})", st.name())).collect();
                ui.label(format!("River ({}): {}", class.name(), list.join(", ")));
            }
        });
        ui.add_space(6.0);
        ui.separator();
        ui.strong("Keyframes");
        for prop in Prop::ALL {
            let in_effect = s.world.key_in_effect(hex, prop, year);
            egui::CollapsingHeader::new(prop.label()).id_salt(("keys", prop.index())).default_open(Some(prop) == s.mode.prop()).show(
                ui,
                |ui| {
                    egui::Grid::new(("keygrid", prop.index())).num_columns(2).striped(true).show(ui, |ui| {
                        for (key, value) in s.world.keys(hex, prop) {
                            let text = RichText::new(key.to_string());
                            ui.label(if in_effect == Some(key) { text.strong() } else { text })
                                .on_hover_text(if in_effect == Some(key) { "In effect at the current year" } else { "" });
                            if s.editor {
                                let mut chosen = value;
                                egui::ComboBox::from_id_salt(("key", prop.index(), key.0))
                                    .selected_text(value.label())
                                    .width(150.0)
                                    .show_ui(ui, |ui| {
                                        for v in prop.values() {
                                            ui.selectable_value(&mut chosen, v, v.label());
                                        }
                                    });
                                if chosen != value {
                                    edit = Some(Command {
                                        label: "Edit keyframe",
                                        edits: vec![Edit { hex, key, before: Some(value), after: chosen }],
                                    });
                                }
                            } else {
                                ui.horizontal(|ui| {
                                    swatch(ui, value);
                                    ui.label(value.label());
                                });
                            }
                            ui.end_row();
                        }
                    });
                    if s.editor && s.world.key_value(hex, prop, year).is_none() {
                        if let Some(current) = s.world.value_at(hex, prop, year).or(prop.values().first().copied()) {
                            if ui.small_button(format!("+ keyframe at {year}")).clicked() {
                                edit = Some(Command {
                                    label: "Insert keyframe",
                                    edits: vec![Edit { hex, key: year, before: None, after: current }],
                                });
                            }
                        }
                    }
                },
            );
        }
        ui.add_space(6.0);
        egui::CollapsingHeader::new("Raw JSON").id_salt("raw").show(ui, |ui| {
            let mut text = raw_json(&s.world, hex);
            ui.add(egui::TextEdit::multiline(&mut text).code_editor().desired_width(f32::INFINITY).interactive(false));
        });
    });
    if let Some(cmd) = edit {
        s.apply(cmd);
    }
}

/// Names and states of the rivers flowing through `hex` at `year`, one entry
/// per river (its stretches merged).
pub fn rivers_in_hex(world: &World, hex: HexId, year: Year) -> Vec<(String, RiverState)> {
    let mut out: Vec<(String, RiverState)> = Vec::new();
    for r in &world.rivers {
        let state = r.state_at(year);
        if state == RiverState::Absent || out.iter().any(|(n, _)| *n == r.name) {
            continue;
        }
        let c = world.grid.centre(hex);
        let near = r.points.iter().any(|p| (p.lon - c.lon).abs() < 3.0 && (p.lat - c.lat).abs() < 3.0);
        if near && crate::board::scene::river_spline(&r.points, 0.03).iter().any(|p| world.grid.hex_at(*p) == Some(hex)) {
            out.push((r.name.clone(), state));
        }
    }
    out
}

/// The hex in the `combined_map.geojson` property shape, for debugging.
pub fn raw_json(world: &World, hex: HexId) -> String {
    let map = |prop: Prop, f: &dyn Fn(Value) -> String| {
        let items: Vec<String> =
            world.keys(hex, prop).into_iter().map(|(y, v)| format!("    \"{}\": {}", y.0, f(v))).collect();
        format!("{{\n{}\n  }}", items.join(",\n"))
    };
    let koeppen = |v: Value| match v {
        Value::Koeppen(k) => k,
        _ => unreachable!(),
    };
    format!(
        "{{\n  \"id\": {},\n  \"terrain\": {},\n  \"climate\": {},\n  \"koeppen\": {},\n  \"population_density\": {}\n}}",
        hex.geojson_id(),
        map(Prop::Terrain, &|v| match v {
            Value::Terrain(t) => format!("\"{}\"", t.name()),
            _ => unreachable!(),
        }),
        map(Prop::Koeppen, &|v| format!("\"{}\"", koeppen(v).code())),
        map(Prop::Koeppen, &|v| format!("{:.1}", koeppen(v).index() as f64)),
        map(Prop::Pop, &|v| match v {
            Value::Pop(p) => format!("{:?}", p.value()),
            _ => unreachable!(),
        }),
    )
}

/// The "board style" panel: everything about the look that is cheap to
/// compare live rather than decide up front.
fn style_window(ctx: &egui::Context, open: &mut bool, style: &mut BoardStyle, s: &mut Session) {
    egui::Window::new("Board style").open(open).resizable(false).default_pos([260.0, 60.0]).show(ctx, |ui| {
        egui::Grid::new("style").num_columns(2).show(ui, |ui| {
            ui.label("View");
            ui.checkbox(&mut style.fill_screen, "Fill the screen").on_hover_text(
                "Keep the board covering the whole view at every zoom. Off: see the whole board as a tabletop piece",
            );
            ui.end_row();
            ui.label("Edge room");
            ui.add_enabled(style.fill_screen, egui::Slider::new(&mut style.fill_margin, 0.0..=0.45).custom_formatter(|v, _| format!("{:.0}%", v * 100.0)))
                .on_hover_text("How much of the view, on each side, may show the map's edge when zoomed out");
            
            ui.label("Curvature");
            let mut curvature = 1.0 - s.morph;
            if ui.add(egui::Slider::new(&mut curvature, 0.0..=1.0).custom_formatter(|v, _| format!("{:.0}%", v * 100.0))).changed() {
                s.morph = 1.0 - curvature;
                s.morph_anim = None;
            }
            ui.end_row();
            ui.label("Edge material");
            ui.horizontal(|ui| {
                for m in Material::ALL {
                    ui.selectable_value(&mut style.material, m, m.label());
                }
            });
            ui.end_row();
            ui.label("Frame lip");
            ui.checkbox(&mut style.frame_lip, "Raised border");
            ui.end_row();
            ui.label("Thickness");
            ui.add(egui::Slider::new(&mut style.thickness, 0.004..=0.06));
            ui.end_row();
            ui.label("Grout");
            ui.add(egui::Slider::new(&mut style.grout, 0.0..=1.0));
            ui.end_row();
            ui.label("Bevel");
            ui.add(egui::Slider::new(&mut style.bevel, 0.0..=1.0));
            ui.end_row();
            ui.label("Region borders");
            ui.add(egui::Slider::new(&mut style.borders, 0.0..=1.0));
            ui.end_row();
            ui.label("Relief");
            ui.add_enabled(style.relief, egui::Slider::new(&mut style.relief_exaggeration, 1.0..=40.0).suffix("×"))
                .on_hover_text("Vertical exaggeration of the tile heights");
            ui.end_row();
            ui.label("Hillshade");
            ui.add(egui::Slider::new(&mut style.hillshade, 0.0..=1.0))
                .on_hover_text("Shade land hexes by their elevation gradient, lit from the north-west");
            ui.end_row();
            ui.label("Terrain art");
            ui.add_enabled(style.terrain_art != ArtMode::Off, egui::Slider::new(&mut style.art_strength, 0.0..=1.0));
            ui.end_row();
            ui.label("Biome edges");
            ui.add_enabled(style.terrain_art != ArtMode::Off, egui::Checkbox::new(&mut style.art_blend, "Blend, with shores"));
            ui.end_row();
            ui.label("Saturation");
            ui.add(egui::Slider::new(&mut style.saturation, 0.0..=1.3));
            ui.end_row();
            ui.label("Quantise light");
            ui.add(egui::Slider::new(&mut style.quantise, 0.0..=12.0).step_by(1.0).custom_formatter(|v, _| {
                if v < 0.5 { "off".to_string() } else { format!("{v:.0} levels") }
            }));
            ui.end_row();
            ui.label("Lighting");
            ui.checkbox(&mut style.flat_lighting, "Flat (exact colours)");
            ui.end_row();
            ui.label("Rivers");
            ui.checkbox(&mut style.rivers, "Rivers and lake shores");
            ui.end_row();
        });
        if ui.button("Reset").clicked() {
            *style = BoardStyle::default();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::{GridSpec, Koeppen, PopDensity, Terrain};

    #[test]
    fn raw_json_shape() {
        let grid = GridSpec { cols: 2, rows: 2, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let mut w = World::empty(grid);
        w.set_key(HexId(0), Year(-9000), Value::Terrain(Terrain::SemiDesert));
        w.set_key(HexId(0), Year(-9000), Value::Koeppen(Koeppen::new(15).unwrap()));
        w.set_key(HexId(0), Year(-9000), Value::Pop(PopDensity::P1_0));
        let json = raw_json(&w, HexId(0));
        assert!(json.contains("\"id\": 1"));
        assert!(json.contains("\"-9000\": \"Semi-Desert\""));
        assert!(json.contains("\"-9000\": \"Cfb\""));
        assert!(json.contains("\"-9000\": 15.0"));
        assert!(json.contains("\"-9000\": 1.0"));
    }
}
