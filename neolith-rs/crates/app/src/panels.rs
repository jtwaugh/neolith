//! egui screens and panels: start screen, top bar, timeline, tool palette,
//! inspector, board-style window.

use crate::app::{NeolithApp, Screen, Session, Tool, DEFAULT_START_YEAR};
use crate::board::scene::{ArtMode, BoardStyle, Material};
use crate::clock::SPEEDS;
use crate::palette;
use egui::{vec2, Align2, Color32, FontId, Rect, RichText, Sense, Stroke};
use neolith_core::{
    elevation, evidence, farming, forager, pencil, productivity, residuals, Command, Cover, Edit, HexId, KeyMode, Koeppen, MapMode, PopDensity, Prop, RiverClass, RiverState, Terrain, Value, World,
    Year, NO_DATA, NO_ELEVATION,
};

/// The right sidebar's tabs.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum SideTab {
    /// The selected settlement or hex (or the one under the cursor).
    #[default]
    Selected,
    Chronicle,
    /// The board's look.
    Map,
}

impl SideTab {
    pub const ALL: [SideTab; 3] = [SideTab::Selected, SideTab::Chronicle, SideTab::Map];
    pub fn label(self) -> &'static str {
        match self {
            SideTab::Selected => "Selected",
            SideTab::Chronicle => "Chronicle",
            SideTab::Map => "Map",
        }
    }
}

/// Narrower than this (in points) the app takes its phone layout.
const COMPACT_WIDTH: f32 = 720.0;

/// A phone-sized screen: the sidebar becomes a sheet, the bars condense.
pub fn is_compact(ctx: &egui::Context) -> bool {
    ctx.content_rect().width() < COMPACT_WIDTH
}

/// Once the app has seen a touch, makes buttons and other targets big enough
/// for a finger (egui's defaults are sized for a mouse).
fn touch_style(ctx: &egui::Context) {
    if !ctx.input(|i| i.has_touch_screen()) || ctx.global_style().spacing.interact_size.y >= 32.0 {
        return;
    }
    ctx.global_style_mut(|st| {
        st.spacing.interact_size.y = 32.0;
        st.spacing.button_padding = vec2(10.0, 6.0);
        st.spacing.item_spacing = vec2(10.0, 8.0);
        st.spacing.scroll.bar_width = 12.0;
    });
}

/// The Selected tab: the open settlement's record, else the hex inspector.
fn selected(ui: &mut egui::Ui, s: &mut Session, now: f64) {
    let year = s.year();
    let Some(i) = s.settlement.filter(|&i| s.world.settlements[i].exists_at(year)) else {
        s.settlement = None;
        inspector(ui, s, now);
        return;
    };
    let pos = s.world.settlements[i].pos;
    let (mut close, mut go) = (false, false);
    ui.horizontal(|ui| {
        ui.heading(RichText::new(&s.world.settlements[i].name).size(17.0));
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            close = ui.small_button("×").on_hover_text("Close (Esc)").clicked();
            go = ui.small_button("Go to").on_hover_text("Move the map to this settlement").clicked();
        });
    });
    // The tabs stay put above the scrolling body.
    let tab = crate::site_record::tab_strip(ui);
    egui::ScrollArea::vertical().id_salt(("settlement_record", tab.label())).auto_shrink([false, false]).show(ui, |ui| {
        crate::site_record::show(ui, &s.world, i, year, tab);
    });
    if go {
        s.glide_to(pos, now);
    }
    if close {
        s.settlement = None;
    }
}

/// A small colour swatch.
fn swatch(ui: &mut egui::Ui, v: Value) {
    swatch_rgb(ui, palette::colour(v));
}

fn swatch_rgb(ui: &mut egui::Ui, [r, g, b]: palette::Rgb) {
    let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
    ui.painter().rect_filled(rect, 3.0, Color32::from_rgb(r, g, b));
    ui.painter().rect_stroke(rect, 3.0, Stroke::new(1.0, ui.visuals().weak_text_color()), egui::StrokeKind::Inside);
}

/// A small hatched square, for the survey-intensity legend row.
fn hatch_swatch(ui: &mut egui::Ui) {
    let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
    let p = ui.painter_at(rect);
    p.rect_filled(rect, 3.0, Color32::from_gray(150));
    let ink = Stroke::new(1.5, Color32::from_gray(50));
    for k in -2..=2 {
        let o = k as f32 * 5.0;
        p.line_segment([rect.left_bottom() + vec2(o, 0.0), rect.right_top() + vec2(o, 0.0)], ink);
    }
}

impl NeolithApp {
    pub fn start_screen(&mut self, ui: &mut egui::Ui) {
        let Some(session) = &mut self.session else { return };
        let (min, max) = session.clock.range();
        let mut start = false;
        // The start controls stay in view below the scrolling splash text.
        egui::Panel::bottom("start_bar").show(ui, |ui| {
            ui.vertical_centered(|ui| {
                ui.add_space(10.0);
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
                ui.add_space(4.0);
                if ui.link(RichText::new("Credits & data sources").small()).clicked() {
                    crate::credits::open(ui.ctx());
                }
                ui.add_space(8.0);
            });
        });
        egui::CentralPanel::default().show(ui, |ui| {
            egui::ScrollArea::vertical().auto_shrink(false).show(ui, |ui| {
                let w = ui.available_width().min(crate::splash::COLUMN);
                ui.horizontal(|ui| {
                    ui.add_space(((ui.available_width() - w) / 2.0).max(0.0));
                    ui.vertical(|ui| {
                        ui.set_width(w);
                        crate::splash::show(ui, w);
                        ui.add_space(24.0);
                    });
                });
            });
        });
        crate::credits::show(ui.ctx());
        if start {
            session.clock.set_year(Year(self.start_year));
            self.screen = Screen::Main;
        }
    }

    pub fn main_screen(&mut self, ui: &mut egui::Ui, now: f64, dt: f64) {
        let ctx = ui.ctx().clone();
        self.shortcuts(&ctx);
        touch_style(&ctx);
        let compact = is_compact(&ctx);
        self.top_bar(ui, now, compact);
        self.timeline(ui, compact);
        crate::credits::show(&ctx);
        let Some(session) = &mut self.session else { return };
        if compact {
            // A phone: no editor (its tool palette needs the width), and the
            // sidebar is a sheet over the bottom of the board, opened by a
            // tap on the map or the Info button.
            if session.editor {
                session.set_editor(false);
            }
            let style = &mut self.style;
            if session.sheet {
                let max = (ctx.content_rect().height() * 0.6).max(160.0);
                egui::Panel::bottom("sheet")
                    .resizable(true)
                    .default_size((ctx.content_rect().height() * 0.38).min(max))
                    .min_size(110.0)
                    .max_size(max)
                    .show(ui, |ui| {
                        ui.add_space(4.0);
                        ui.horizontal(|ui| {
                            for tab in SideTab::ALL {
                                ui.selectable_value(&mut session.side_tab, tab, tab.label());
                            }
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                if ui.button("Close").clicked() {
                                    session.sheet = false;
                                }
                            });
                        });
                        ui.separator();
                        // The legend folds away: a phone's sheet is short.
                        egui::Panel::bottom("sheet_legend").resizable(false).show(ui, |ui| {
                            egui::CollapsingHeader::new("Legend").id_salt("sheet_legend_fold").show(ui, |ui| {
                                ui.set_max_height(ui.ctx().content_rect().height() * 0.25);
                                legend(ui, session, style.survey);
                            });
                        });
                        match session.side_tab {
                            SideTab::Selected => selected(ui, session, now),
                            SideTab::Chronicle => chronicle(ui, session, now),
                            SideTab::Map => map_tab(ui, style, session),
                        }
                    });
            }
            egui::CentralPanel::default().frame(egui::Frame::NONE).show(ui, |ui| {
                crate::view::board_view(ui, session, &self.style, self.gpu.as_ref().unwrap(), now, dt);
            });
            return;
        }
        if session.editor {
            egui::Panel::left("tools").resizable(false).exact_size(210.0).show(ui, |ui| tools_panel(ui, session));
        }
        // The right sidebar: tabs for what is selected, the chronicle and the
        // map's look, with the legend docked underneath. Nothing floats over
        // the board.
        let style = &mut self.style;
        egui::Panel::right("inspector")
            .resizable(true)
            .default_size(290.0)
            .min_size(240.0)
            .show(ui, |ui| {
                egui::Panel::bottom("legend_dock").resizable(false).show(ui, |ui| legend(ui, session, style.survey));
                ui.add_space(6.0);
                ui.horizontal(|ui| {
                    for tab in SideTab::ALL {
                        ui.selectable_value(&mut session.side_tab, tab, tab.label());
                    }
                });
                ui.separator();
                match session.side_tab {
                    SideTab::Selected => selected(ui, session, now),
                    SideTab::Chronicle => chronicle(ui, session, now),
                    SideTab::Map => map_tab(ui, style, session),
                }
            });
        egui::CentralPanel::default().frame(egui::Frame::NONE).show(ui, |ui| {
            crate::view::board_view(ui, session, &self.style, self.gpu.as_ref().unwrap(), now, dt);
        });
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
        // Escape closes what is selected: the settlement first, then the hex.
        if ctx.input_mut(|i| i.consume_key(Modifiers::NONE, Key::Escape)) {
            if s.settlement.is_some() {
                s.settlement = None;
            } else if s.inspected.is_some() {
                s.inspected = None;
                if !s.editor {
                    s.selection.clear();
                }
                s.state_dirty = true;
            }
        }
        if !s.editor {
            const KEYS: [Key; 5] = [Key::Num1, Key::Num2, Key::Num3, Key::Num4, Key::Num5];
            let pressed = ctx.input_mut(|i| KEYS.iter().position(|k| i.consume_key(Modifiers::NONE, *k)));
            if let Some(step) = pressed {
                s.clock.set_speed_step(step);
            }
        }
    }

    fn top_bar(&mut self, ui: &mut egui::Ui, now: f64, compact: bool) {
        let ctx = ui.ctx().clone();
        let (mut open, mut save) = (false, false);
        egui::Panel::top("top").show(ui, |ui| {
            let Some(s) = &mut self.session else { return };
            if compact {
                // One row: the menu, the map mode and the sheet button. The
                // rest of the bar's settings live in the menu.
                ui.horizontal(|ui| {
                    ui.menu_button("Menu", |ui| {
                        if ui.button("Open world…").clicked() {
                            open = true;
                            ui.close();
                        }
                        if ui.button("Download world.bin").clicked() {
                            save = true;
                            ui.close();
                        }
                        ui.separator();
                        ui.label("Terrain art");
                        ui.horizontal(|ui| {
                            for art in ArtMode::ALL {
                                ui.selectable_value(&mut self.style.terrain_art, art, art.label());
                            }
                        });
                        ui.toggle_value(&mut self.style.relief, "Relief");
                        if ui.button("Board style").clicked() {
                            s.side_tab = SideTab::Map;
                            s.sheet = true;
                            ui.close();
                        }
                        if ui.button("Chronicle").clicked() {
                            s.side_tab = SideTab::Chronicle;
                            s.sheet = true;
                            ui.close();
                        }
                        ui.separator();
                        if ui.button("Credits & data").clicked() {
                            crate::credits::open(ui.ctx());
                            ui.close();
                        }
                    });
                    map_mode_picker(ui, s);
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.toggle_value(&mut s.sheet, "Info");
                    });
                });
                if s.mode == MapMode::Evidence {
                    ui.horizontal(|ui| evidence_picker(ui, s));
                }
                if let Some((msg, t)) = &self.status {
                    if now - t < 6.0 {
                        ui.weak(msg);
                    }
                }
                return;
            }
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
                    ui.separator();
                    if ui.button("Credits & data…").clicked() {
                        crate::credits::open(ui.ctx());
                        ui.close();
                    }
                });
                ui.separator();
                ui.label("Map:");
                map_mode_picker(ui, s);
                if s.mode == MapMode::Evidence {
                    evidence_picker(ui, s);
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
                let mut map_tab = s.side_tab == SideTab::Map;
                if ui.toggle_value(&mut map_tab, "Board style").on_hover_text("The board's look, in the sidebar's Map tab").changed() {
                    s.side_tab = if map_tab { SideTab::Map } else { SideTab::Selected };
                }
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
    fn timeline(&mut self, ui: &mut egui::Ui, compact: bool) {
        let Some(s) = &mut self.session else { return };
        egui::Panel::bottom("timeline").show(ui, |ui| {
            ui.add_space(4.0);
            if compact {
                // Two rows: the controls and the year, then the scrubber at
                // full width (a thumb needs the length).
                ui.horizontal(|ui| {
                    let label = if s.clock.playing { "Pause" } else { "Play" };
                    if ui.add(egui::Button::new(label).min_size(vec2(72.0, 0.0))).clicked() {
                        let (min, max) = s.clock.range();
                        if !s.clock.playing && s.year() >= max {
                            s.clock.set_year(min);
                        }
                        s.clock.playing = !s.clock.playing;
                    }
                    let step = s.clock.speed_step();
                    egui::ComboBox::from_id_salt("speed")
                        .selected_text(format!("{:.0} yr/s", SPEEDS[step]))
                        .width(84.0)
                        .show_ui(ui, |ui| {
                            for (i, v) in SPEEDS.iter().enumerate() {
                                if ui.selectable_label(i == step, format!("{v:.0} yr/s")).clicked() {
                                    s.clock.set_speed_step(i);
                                }
                            }
                        });
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(RichText::new(s.year().to_string()).strong().size(15.0));
                    });
                });
                ui.add_space(2.0);
                scrubber(ui, s);
                ui.add_space(4.0);
                return;
            }
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
                // Five fixed speed steps, as pips (keys 1–5).
                let step = s.clock.speed_step();
                ui.spacing_mut().item_spacing.x = 3.0;
                for (i, v) in SPEEDS.iter().enumerate() {
                    let on = i <= step;
                    let (r, resp) = ui.allocate_exact_size(vec2(11.0, 20.0), Sense::click());
                    let visuals = ui.visuals();
                    let fill = if on { visuals.selection.bg_fill } else { visuals.widgets.inactive.bg_fill };
                    let h = 7.0 + 2.5 * i as f32;
                    let pip = Rect::from_min_max(egui::pos2(r.left() + 1.0, r.bottom() - h), egui::pos2(r.right() - 1.0, r.bottom()));
                    ui.painter().rect_filled(pip, 2.0, if resp.hovered() { visuals.widgets.hovered.bg_fill } else { fill });
                    if resp.on_hover_text(format!("Speed {}: {v:.0} years/s · key {}", i + 1, i + 1)).clicked() {
                        s.clock.set_speed_step(i);
                    }
                }
                ui.spacing_mut().item_spacing.x = 8.0;
                ui.weak(format!("{:.0} yr/s", SPEEDS[step]));
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
        // These layers come from the pipeline and are not editable here.
        if s.mode == MapMode::Npp {
            ui.weak("Read-only: from the climate model via the pipeline. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, productivity_legend);
        } else if s.mode == MapMode::Biodiversity {
            ui.weak("Read-only: derived from productivity. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, biodiversity_legend);
        } else if s.mode == MapMode::Expected {
            ui.weak("Read-only: derived from productivity, climate, rivers and the spread of farming. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, expected_legend);
        } else if s.mode == MapMode::Missing {
            ui.weak("Read-only: residuals from the pipeline. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, missing_legend);
        } else if s.mode == MapMode::Evidence {
            ui.weak("Read-only: speculative layers from isostyle. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| evidence_legend(ui, s));
        } else {
            ui.weak("Read-only: from ETOPO1 via the pipeline. Switch map mode to paint.");
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, elevation_legend);
        }
        return;
    };
    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        for v in mode.palette() {
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

/// The classes of one layer the legend lists, in class-code order (the
/// palette's order): every class any keyframe holds, so a row never appears,
/// vanishes or changes place as the years pass. `true` where the class has
/// hexes this year; the rest are drawn grey.
fn legend_rows<T: Copy>(ui: &egui::Ui, s: &Session, salt: &str, timelines: &[neolith_core::Timeline<T>], code: impl Fn(T) -> u8, now: &[u8], skip_water: bool) -> Vec<(u8, bool)> {
    // Classes ever present: scanned again only when the snapshot changes
    // (a new epoch, a new file or an edit).
    let id = egui::Id::unique(("legend-ever", salt));
    let key = (s.file_name.clone(), s.snapshot_gen);
    let cached = ui.data(|d| d.get_temp::<std::sync::Arc<((String, u64), [bool; 256])>>(id)).filter(|c| c.0 == key);
    let ever = match cached {
        Some(c) => c.1,
        None => {
            let mut ever = [false; 256];
            for t in timelines {
                for (_, v) in t.keys() {
                    ever[code(*v) as usize] = true;
                }
            }
            ui.data_mut(|d| d.insert_temp(id, std::sync::Arc::new((key, ever))));
            ever
        }
    };
    let mut present = [false; 256];
    for (i, v) in now.iter().enumerate() {
        if !(skip_water && s.snapshot.terrain[i] == Terrain::Water as u8) {
            present[*v as usize] = true;
        }
    }
    (0..=255u8).filter(|v| *v != NO_DATA && (ever[*v as usize] || present[*v as usize])).map(|v| (v, present[v as usize])).collect()
}

/// A legend row; grey when the class has no hexes this year.
fn legend_row(ui: &mut egui::Ui, v: Value, present: bool, text: impl FnOnce(&mut egui::Ui)) {
    ui.horizontal(|ui| {
        if !present {
            ui.set_opacity(0.35);
        }
        swatch(ui, v);
        text(ui);
    })
    .response
    .on_hover_text(if present { "On the map this year" } else { "Not on the map this year" });
}

/// The legend for the current map mode, docked at the foot of the sidebar
/// (collapsible). Terrain and Köppen list every class the map ever holds, in
/// a fixed order, greying those absent this year; Population is the whole
/// ramp; the read-only layers their bands.
fn legend(ui: &mut egui::Ui, s: &Session, survey: bool) {
    ui.add_space(4.0);
    egui::CollapsingHeader::new(RichText::new(format!("Legend · {}", s.mode.label())).strong())
        .id_salt("legend-open")
        .default_open(true)
        .show(ui, |ui| {
            let sea_row = |ui: &mut egui::Ui| {
                ui.horizontal(|ui| {
                    swatch_rgb(ui, palette::SEA_COLOUR);
                    ui.label("Sea and lakes");
                });
            };
            // A long list (Köppen has some 25 classes) scrolls in place
            // rather than pushing the record off the sidebar.
            let max = ui.ctx().content_rect().height() * 0.42;
            egui::ScrollArea::vertical().id_salt("legend-scroll").max_height(max).auto_shrink([false, true]).show(ui, |ui| {
            match s.mode {
                MapMode::Terrain => {
                    for (v, present) in legend_rows(ui, s, "terrain", &s.world.terrain, |t| t as u8, &s.snapshot.terrain, false) {
                        if let Some(val) = Value::from_u8(Prop::Terrain, v) {
                            legend_row(ui, val, present, |ui| {
                                ui.label(val.label());
                            });
                        }
                    }
                }
                MapMode::Ground => {
                    // One row per cover in view now (from the terrain layer).
                    let mut shown = [false; Cover::ALL.len()];
                    for v in s.snapshot.terrain.iter() {
                        if let Some(c) = Terrain::from_u8(*v).and_then(Terrain::cover) {
                            shown[c as usize] = true;
                        }
                    }
                    for c in Cover::ALL {
                        ui.horizontal(|ui| {
                            swatch_rgb(ui, palette::cover(c));
                            let label = RichText::new(c.label());
                            ui.label(if shown[c as usize] { label } else { label.weak() });
                        });
                    }
                    ui.horizontal(|ui| {
                        swatch_rgb(ui, palette::terrain(Terrain::Water));
                        ui.label("Sea and lakes");
                    });
                }
                MapMode::Koeppen => {
                    let rows = legend_rows(ui, s, "koeppen", &s.world.koeppen, |k| k.index(), &s.snapshot.koeppen, true);
                    for (v, present) in rows {
                        // The ocean class is the sea row below.
                        if let Some(k) = Koeppen::new(v).filter(|k| *k != Koeppen::OCEAN) {
                            legend_row(ui, Value::Koeppen(k), present, |ui| {
                                ui.label(RichText::new(k.code()).monospace());
                                ui.label(k.description());
                            });
                        }
                    }
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
                MapMode::Npp => {
                    if s.world.npp.is_empty() {
                        ui.weak("This file has no productivity layer.");
                    } else {
                        productivity_legend(ui);
                        sea_row(ui);
                    }
                }
                MapMode::Expected => {
                    if s.world.npp.is_empty() {
                        ui.weak("This file has no productivity layer to derive it from.");
                    } else {
                        expected_legend(ui);
                        sea_row(ui);
                    }
                }
                MapMode::Biodiversity => {
                    if s.world.npp.is_empty() {
                        ui.weak("This file has no productivity layer to derive it from.");
                    } else {
                        biodiversity_legend(ui);
                        sea_row(ui);
                    }
                }
                MapMode::Evidence => {
                    evidence_legend(ui, s);
                    sea_row(ui);
                }
                MapMode::Missing => {
                    if s.world.residuals.is_none() {
                        ui.weak("This file has no missing-sites table.");
                    } else {
                        missing_legend(ui);
                        sea_row(ui);
                    }
                }
                MapMode::Ancestry => {
                    crate::ancestry_view::legend(ui, s);
                    sea_row(ui);
                }
            }
            });
            // The Ancestry mode keeps the hatch for one meaning: no genome.
            if survey && !s.world.survey.is_empty() && s.mode != MapMode::Ancestry {
                ui.separator();
                ui.horizontal(|ui| {
                    hatch_swatch(ui);
                    ui.label("Few dated sites of any period");
                })
                .response
                .on_hover_text("Hatched land has little fieldwork behind it: an absence of sites there is not evidence of an absence of people.");
            }
        });
    ui.add_space(2.0);
}

/// The evidence layers in picker order: by group (in file order), and
/// within a group the stand-alone layers first, then each set's members
/// together. Returns (group, [(set, [layer index])]).
pub fn evidence_menu(layers: &[neolith_core::EvidenceLayer]) -> Vec<(&str, Vec<(&str, Vec<usize>)>)> {
    let mut out: Vec<(&str, Vec<(&str, Vec<usize>)>)> = Vec::new();
    for (i, l) in layers.iter().enumerate() {
        let g = match out.iter().position(|(g, _)| *g == l.group) {
            Some(g) => g,
            None => {
                out.push((&l.group, Vec::new()));
                out.len() - 1
            }
        };
        let sets = &mut out[g].1;
        match sets.iter().position(|(set, _)| *set == l.set) {
            Some(k) => sets[k].1.push(i),
            None if l.set.is_empty() => sets.insert(0, (&l.set, vec![i])),
            None => sets.push((&l.set, vec![i])),
        }
    }
    out
}

/// The layer picker beside the map selector in Evidence mode.
/// The map modes as the picker lists them: a heading, then each mode with
/// one line on what it shows. Every [`MapMode::MENU`] entry appears once.
const MAP_MODE_GROUPS: [(&str, &[(MapMode, &str)]); 4] = [
    (
        "Land",
        &[
            (MapMode::Terrain, "The biome of each hex: forest, steppe, desert, ice, water"),
            (MapMode::Ground, "The same land as photographed ground: grass, moss, sand, rock, snow, forest floor"),
            (MapMode::Koeppen, "Köppen climate class, from the climate model"),
            (MapMode::Elevation, "Height above today's sea level, and depth of water"),
        ],
    ),
    (
        "Living things",
        &[
            (MapMode::Npp, "How much plants grow in a year"),
            (MapMode::Biodiversity, "Species richness expected at that productivity"),
        ],
    ),
    (
        "People",
        &[
            (MapMode::Expected, "How many people the land would carry: foragers, then farmers once farming arrives"),
            (MapMode::Missing, "Sites each hex would have if nothing hid them, less the sites known"),
            (MapMode::Ancestry, "Whose ancestry ancient genomes carry, where genomes exist; unsampled land is left unknown"),
        ],
    ),
    ("Evidence", &[(MapMode::Evidence, "Speculative layers from the evidence atlas: pick one beside this menu")]),
];

/// Why a mode can't be shown with this world file, if it can't.
fn map_mode_unavailable(mode: MapMode, world: &World) -> Option<&'static str> {
    match mode {
        MapMode::Evidence if world.evidence.is_empty() => {
            Some("This world file has no evidence layers (add them with neolith-convert --attach-evidence)")
        }
        MapMode::Missing if world.residuals.is_none() => Some("This world file has no missing-sites table (run make residuals)"),
        MapMode::Ancestry if !world.has_ancestry() => {
            Some("This world file has no ancestry table (python -m isostyle export, then neolith-convert --attach-evidence and --attach-samples)")
        }
        _ => None,
    }
}

/// One button showing the current map mode; it opens the list of modes
/// under their headings, each with a line on what it shows.
fn map_mode_picker(ui: &mut egui::Ui, s: &mut Session) {
    egui::ComboBox::from_id_salt("map-mode").selected_text(s.mode.label()).width(150.0).height(420.0).show_ui(ui, |ui| {
        for (heading, modes) in MAP_MODE_GROUPS {
            ui.label(RichText::new(heading).strong());
            for (mode, what) in modes {
                let label = format!("  {}", mode.label());
                match map_mode_unavailable(*mode, &s.world) {
                    Some(why) => {
                        ui.add_enabled(false, egui::Button::selectable(false, label)).on_disabled_hover_text(why);
                    }
                    None => {
                        if ui.selectable_label(s.mode == *mode, label).on_hover_text(*what).clicked() {
                            s.mode = *mode;
                        }
                    }
                }
            }
        }
    });
}

fn evidence_picker(ui: &mut egui::Ui, s: &mut Session) {
    let selected = s.evidence().map_or("Pick a layer".to_string(), |l| l.name.clone());
    let mut pick = s.evidence_layer;
    egui::ComboBox::from_id_salt("evidence-layer").selected_text(selected).height(520.0).show_ui(ui, |ui| {
        for (group, sets) in evidence_menu(&s.world.evidence) {
            ui.label(RichText::new(group).strong());
            for (set, members) in sets {
                if !set.is_empty() {
                    ui.weak(format!("  {set}"));
                }
                for i in members {
                    let l = &s.world.evidence[i];
                    let indent = if set.is_empty() { "  " } else { "    " };
                    let r = ui.selectable_value(&mut pick, Some(i), format!("{indent}{}", l.name));
                    if !l.note.is_empty() {
                        r.on_hover_text(&l.note);
                    }
                }
            }
        }
    });
    s.evidence_layer = pick;
}

/// The selected evidence layer: its value ramp, the confidence levels and
/// the warning that most of it is not evidence.
fn evidence_legend(ui: &mut egui::Ui, s: &Session) {
    let Some(l) = s.evidence() else {
        ui.weak("This file has no evidence layers.");
        return;
    };
    let name = ui.label(RichText::new(&l.name).strong());
    if !l.note.is_empty() {
        name.on_hover_text(&l.note);
    }
    // One strip of the value ramp (vmin to vmax) per confidence level, so the
    // fade towards grey is visible at every value, not at one sample colour.
    const W: f32 = 120.0;
    let strip = |ui: &mut egui::Ui, c: u8| {
        let (rect, _) = ui.allocate_exact_size(vec2(W, 14.0), Sense::hover());
        let step = rect.width() / evidence::BINS as f32;
        for b in 0..evidence::BINS {
            let [r, g, bl] = palette::evidence_colour(c, b);
            let x = rect.left() + b as f32 * step;
            ui.painter().rect_filled(Rect::from_min_max(egui::pos2(x, rect.top()), egui::pos2(x + step + 0.5, rect.bottom())), 0.0, Color32::from_rgb(r, g, bl));
        }
    };
    ui.weak(format!("{} (left) to {} (right)", l.format_value(l.vmin), l.format_value(l.vmax)));
    for c in 0..evidence::LEVELS {
        ui.horizontal(|ui| {
            strip(ui, c);
            ui.label(evidence::confidence_label(c));
        });
    }
    ui.horizontal(|ui| {
        swatch_rgb(ui, palette::NO_DATA_COLOUR);
        ui.label("No value");
    });
    ui.label(RichText::new("Speculative where judged or extrapolated: not evidence.").italics());
}

/// Missing-sites bands, most missing first.
fn missing_legend(ui: &mut egui::Ui) {
    ui.weak("Sites missing per hex").on_hover_text(
        "Sites a hex would have if nothing hid them, less the sites known, for the thousand years around each \
         millennium. What a hex should have comes from its area, the epoch, whether it is farmed and how near \
         water it is. A residual against the site list's own pattern, not a population estimate.",
    );
    for b in (0..residuals::BAND_COUNT).rev() {
        ui.horizontal(|ui| {
            swatch_rgb(ui, palette::missing(b));
            ui.label(residuals::band_label(b).unwrap_or_default());
        });
    }
}

/// Expected-population bands, densest first.
fn expected_legend(ui: &mut egui::Ui) {
    ui.weak("People per 100 km²").on_hover_text(
        "What the land would carry, from values on the map and no site data: hunter-gatherers by productivity \
         (Tallavaara et al. 2018), and farmers once farming has arrived and the climate allows it (Pinhasi et al. \
         2005; Davison et al. 2006). Compare with where sites are known.",
    );
    for b in (0..farming::BAND_COUNT).rev() {
        ui.horizontal(|ui| {
            swatch_rgb(ui, palette::expected(b));
            ui.label(farming::band_label(b).unwrap_or_default());
        });
    }
}

/// A density for reading, not arithmetic: "0.47", "3.6", "21".
fn fmt_density(v: f64) -> String {
    match v {
        v if v < 1.0 => format!("{v:.2}"),
        v if v < 10.0 => format!("{v:.1}"),
        v => format!("{v:.0}"),
    }
}

/// Biodiversity bands, richest first.
fn biodiversity_legend(ui: &mut egui::Ui) {
    ui.weak("Species richness, 0–1").on_hover_text(
        "Scaled mammal, bird and plant richness expected at the hex's productivity: a line fitted to present-day maps \
         (Tallavaara et al. 2018). Not an independent reconstruction.",
    );
    for b in (0..forager::BIODIVERSITY_BAND_COUNT).rev() {
        ui.horizontal(|ui| {
            swatch_rgb(ui, palette::biodiversity(b));
            ui.label(forager::biodiversity_band_label(b).unwrap_or_default());
        });
    }
}

/// Productivity bands, most productive first.
fn productivity_legend(ui: &mut egui::Ui) {
    ui.weak(format!("Plant growth, {}", productivity::UNIT)).on_hover_text(
        "Net primary productivity by the Miami model, from the climate model's annual temperature and rainfall \
         (Beyer et al. 2020), at 1000-year steps",
    );
    for b in (0..productivity::BAND_COUNT).rev() {
        ui.horizontal(|ui| {
            swatch_rgb(ui, palette::productivity(b));
            ui.label(productivity::band_label(b).unwrap_or_default());
        });
    }
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

/// The Chronicle tab: the latest events up to the
/// current year, newest first. Clicking one with a place glides there.
fn chronicle(ui: &mut egui::Ui, s: &mut Session, now: f64) {
    const ROWS: usize = 40;
    let year = s.year();
    let mut go = None;
    {
        let recent: Vec<_> = crate::events::recent(&s.events, year, ROWS).collect();
        if recent.is_empty() {
            ui.weak("Nothing yet. Press Play (Space); keys 1–5 set the speed.");
        }
        // An event the clock just passed glows for about two seconds of play.
        let window = (s.clock.years_per_sec * 2.0).max(1.0);
        egui::ScrollArea::vertical().id_salt("chronicle-scroll").auto_shrink([false, false]).show(ui, |ui| {
            for ev in recent {
                let fresh = (1.0 - (year.0 - ev.year.0) as f64 / window).clamp(0.0, 1.0) as f32;
                let fresh = if s.clock.playing { fresh } else { 0.0 };
                ui.horizontal_wrapped(|ui| {
                    ui.weak(RichText::new(format!("{}", -ev.year.0)).monospace().size(11.0));
                    let (r, _) = ui.allocate_exact_size(vec2(8.0, 14.0), Sense::hover());
                    let [cr, cg, cb] = ev.kind.colour();
                    ui.painter().circle_filled(r.center(), 3.5, Color32::from_rgb(cr, cg, cb));
                    let base = ui.visuals().text_color();
                    let glow = Color32::from_rgb(255, 205, 90);
                    let colour = base.lerp_to_gamma(glow, fresh);
                    let text = RichText::new(&ev.text).color(colour);
                    match ev.at {
                        Some(at) => {
                            let r = ui.add(egui::Label::new(text).sense(Sense::click())).on_hover_text("Click to go there");
                            if r.clicked() {
                                go = Some(at);
                            }
                            if r.hovered() {
                                ui.ctx().set_cursor_icon(egui::CursorIcon::PointingHand);
                            }
                        }
                        None => {
                            ui.label(text);
                        }
                    }
                });
            }
        });
    }
    if let Some(at) = go {
        s.glide_to(at, now);
    }
}

/// Right panel: the hovered or selected hex, its current values and each
/// property's keyframe table (editable in place with typed dropdowns).
fn inspector(ui: &mut egui::Ui, s: &mut Session, now: f64) {
    let Some(hex) = s.inspected.or(s.hover) else {
        ui.weak("Hover over the map to see a hex; click a hex or a settlement to select it.");
        return;
    };
    let pinned = s.inspected == Some(hex);
    let (col, row) = s.world.grid.col_row(hex);
    let centre = s.world.grid.centre(hex);
    ui.horizontal(|ui| {
        ui.strong(format!("Hex {}", hex.geojson_id()));
        ui.weak(if pinned { "selected" } else { "hover" });
        if pinned {
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui.small_button("×").on_hover_text("Deselect (Esc)").clicked() {
                    s.inspected = None;
                }
                if ui.small_button("Go to").on_hover_text("Move the map to this hex").clicked() {
                    s.glide_to(centre, now);
                }
            });
        }
    });
    ui.weak(format!("col {col}, row {row} · {:.2}°, {:.2}°", centre.lon, centre.lat));
    ui.add_space(4.0);

    let year = s.year();
    let mut edit: Option<Command> = None;
    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        let water = s.snapshot.terrain[hex.index()] == Terrain::Water as u8;
        if let Some(r) = s.world.residuals.as_ref().filter(|_| s.mode == MapMode::Missing).and_then(|t| t.at(hex, year)) {
            ui.horizontal_wrapped(|ui| {
                swatch_rgb(ui, palette::missing(residuals::band((r.missing * 10.0).round() as i16)));
                let known = match r.sites {
                    1 => "1 site known".to_string(),
                    n => format!("{n} sites known"),
                };
                let text = if r.missing >= 0.05 {
                    format!("Missing sites: {:.1} ({known})", r.missing)
                } else if r.missing <= -0.05 {
                    format!("{:.1} more sites than expected ({known})", -r.missing)
                } else {
                    format!("No sites missing ({known})")
                };
                ui.label(text).on_hover_text(
                    "Sites this hex would have if nothing hid them, less the sites known, for the thousand years \
                     around this millennium. A residual against the site list's own pattern, not a population estimate.",
                );
            });
            ui.label(format!("Reading: {}", r.outcome));
            ui.separator();
        }
        if s.mode == MapMode::Ancestry && !water {
            crate::ancestry_view::inspector(ui, s, hex);
        }
        if let Some(l) = s.evidence().filter(|_| s.mode == MapMode::Evidence) {
            let code = s.evidence_code(hex);
            ui.horizontal_wrapped(|ui| match (l.value(code), evidence::confidence(code)) {
                (Some(v), Some(c)) => {
                    swatch_rgb(ui, palette::evidence(code));
                    let r = ui.label(format!("{}: {} ({})", l.name, l.format_value(v), evidence::confidence_label(c)));
                    if c > 0 {
                        r.on_hover_text("Judged or extrapolated: speculative, not evidence.");
                    }
                }
                _ => {
                    ui.weak(format!("{}: no value", l.name));
                }
            });
        }
        for prop in Prop::ALL {
            // Nobody lives on the water: no population row there.
            if water && prop == Prop::Pop {
                continue;
            }
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
        if let Some(v) = s.world.npp_at(hex, year) {
            let band = s.snapshot.npp[hex.index()];
            ui.horizontal(|ui| {
                if band == NO_DATA {
                    ui.weak("Productivity: none (water)");
                } else {
                    swatch_rgb(ui, palette::productivity(band));
                    ui.label(format!("Productivity: {v} {}", productivity::UNIT)).on_hover_text(
                        "Net primary productivity: plant growth (dry matter) per square metre per year, by the Miami \
                         model from the climate model's annual temperature and rainfall",
                    );
                }
            });
            if band != NO_DATA {
                ui.horizontal(|ui| {
                    swatch_rgb(ui, palette::biodiversity(s.snapshot.biodiversity[hex.index()]));
                    ui.label(format!("Biodiversity: {:.2}", forager::biodiversity(v)))
                        .on_hover_text("Scaled species richness (0–1) expected at this productivity; derived, not measured");
                });
            }
            let shore = s.snapshot.shore_km[hex.index()];
            if let Some(e) = s.world.expected_given(hex, year, shore as f64) {
                let who = if e.farmed { "farmers" } else { "foragers" };
                ui.horizontal(|ui| {
                    swatch_rgb(ui, palette::expected(s.snapshot.expected[hex.index()]));
                    ui.label(format!("Expected: {} {who} per 100 km²", fmt_density(e.density * 100.0))).on_hover_text(
                        "What the land would carry, from values on the map and no site data. Foragers: by productivity \
                         (Tallavaara et al. 2018) and distance to the sea or a lake (this project's fit to Binford's \
                         data), within a factor of about three. \
                         Farmers: growing towards a ceiling for the latitude once farming has arrived and the climate \
                         allows it (Davison et al. 2006).",
                    );
                });
            }
            if band != NO_DATA && shore != u16::MAX {
                ui.label(format!("Sea or lake: {shore} km")).on_hover_text(
                    "From the hex's centre to the edge of the nearest water this year, on the map or beyond its edge. Foragers are denser near it: \
                     about three times on the shore, half at 1000 km.",
                );
            }
            match s.world.farming.get(hex.index()).copied().flatten() {
                Some(y) => {
                    ui.label(format!("Farming arrives: {} BCE", -y.0)).on_hover_text(
                        "A front from Çayönü at 8800 BCE moving 0.9 km a year (Pinhasi et al. 2005). Not fitted to \
                         the sites on this map; often centuries off in either direction.",
                    );
                }
                None if !s.world.farming.is_empty() => {
                    ui.weak("Farming does not arrive by 3000 BCE");
                }
                None => {}
            }
        }
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
        // The keyframe tables and the raw record are for editing the map.
        if !s.editor {
            return;
        }
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
                                        for v in prop.palette() {
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

/// The Map tab: the board's look, in groups, the rarely changed ones folded
/// away under "Advanced".
fn map_tab(ui: &mut egui::Ui, style: &mut BoardStyle, s: &mut Session) {
    egui::ScrollArea::vertical().id_salt("map_tab").auto_shrink([false, false]).show(ui, |ui| {
        let group = |ui: &mut egui::Ui, title: &str, open: bool, body: &mut dyn FnMut(&mut egui::Ui)| {
            egui::CollapsingHeader::new(RichText::new(title).strong()).id_salt(("map_tab", title)).default_open(open).show(ui, |ui| {
                egui::Grid::new(("map_grid", title)).num_columns(2).spacing([10.0, 6.0]).show(ui, |ui| body(ui));
            });
        };
        group(ui, "View", true, &mut |ui| {
            ui.label("Fill the screen");
            ui.checkbox(&mut style.fill_screen, "").on_hover_text(
                "Keep the board covering the whole view at every zoom. Off: see the whole board as a tabletop piece",
            );
            ui.end_row();
            ui.label("Edge room");
            ui.add_enabled(style.fill_screen, egui::Slider::new(&mut style.fill_margin, 0.0..=0.45).custom_formatter(|v, _| format!("{:.0}%", v * 100.0)))
                .on_hover_text("How much of the view, on each side, may show the map's edge when zoomed out");
            ui.end_row();
            ui.label("Curvature");
            let mut curvature = 1.0 - s.morph;
            if ui.add(egui::Slider::new(&mut curvature, 0.0..=1.0).custom_formatter(|v, _| format!("{:.0}%", v * 100.0))).changed() {
                s.morph = 1.0 - curvature;
                s.morph_anim = None;
            }
            ui.end_row();
            ui.label("Depth");
            ui.add(egui::Slider::new(&mut style.depth, 0.0..=1.0))
                .on_hover_text("Haze over the far ground and soft focus at the top and bottom of a tilted view. Off while editing.");
            ui.end_row();
        });
        group(ui, "Terrain", true, &mut |ui| {
            ui.label("Terrain art");
            ui.horizontal(|ui| {
                for art in ArtMode::ALL {
                    ui.selectable_value(&mut style.terrain_art, art, art.label());
                }
            });
            ui.end_row();
            ui.label("Ground detail");
            ui.add_enabled(style.terrain_art != ArtMode::Off, egui::Slider::new(&mut style.art_strength, 0.0..=1.0));
            ui.end_row();
            ui.label("Biome edges");
            ui.add_enabled(style.terrain_art != ArtMode::Off, egui::Checkbox::new(&mut style.art_blend, "Blend, with shores"));
            ui.end_row();
            ui.label("Relief");
            ui.horizontal(|ui| {
                ui.checkbox(&mut style.relief, "");
                ui.add_enabled(style.relief, egui::Slider::new(&mut style.relief_exaggeration, 1.0..=80.0).suffix("×"))
                    .on_hover_text("Vertical exaggeration of the tile heights");
            });
            ui.end_row();
            ui.label("Mountain height");
            ui.add_enabled(style.terrain_art == ArtMode::On, egui::Slider::new(&mut style.mountain_height, 0.3..=1.5).suffix("×"))
                .on_hover_text("Height of the peaks and hills standing on mountain country; lower declutters busy ranges");
            ui.end_row();
            ui.label("Hillshade");
            ui.add(egui::Slider::new(&mut style.hillshade, 0.0..=1.0))
                .on_hover_text("Shade land hexes by their elevation gradient, lit from the north-west");
            ui.end_row();
        });
        group(ui, "Overlays", true, &mut |ui| {
            ui.label("Rivers");
            ui.checkbox(&mut style.rivers, "Rivers and lake shores");
            ui.end_row();
            ui.label("Survey");
            ui.checkbox(&mut style.survey, "Hatch thinly surveyed land");
            ui.end_row();
            ui.label("Region borders");
            ui.add(egui::Slider::new(&mut style.borders, 0.0..=1.0));
            ui.end_row();
        });
        group(ui, "Advanced", false, &mut |ui| {
            ui.label("Edge material");
            ui.horizontal_wrapped(|ui| {
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
        });
        ui.add_space(6.0);
        if ui.button("Reset to defaults").clicked() {
            *style = BoardStyle::default();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::{GridSpec, Koeppen, PopDensity, Terrain};

    #[test]
    fn map_mode_picker_lists_every_menu_mode_once() {
        let listed: Vec<MapMode> = MAP_MODE_GROUPS.iter().flat_map(|(_, modes)| modes.iter().map(|(m, _)| *m)).collect();
        assert_eq!(listed.len(), MapMode::MENU.len());
        assert!(MapMode::MENU.iter().all(|m| listed.iter().filter(|l| *l == m).count() == 1), "{listed:?}");
        assert!(MAP_MODE_GROUPS.iter().all(|(heading, modes)| !heading.is_empty() && modes.iter().all(|(_, what)| !what.is_empty())));
        // Modes that need data the file lacks say why; the rest are always available.
        let grid = GridSpec { cols: 3, rows: 2, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let bare = World::empty(grid);
        assert!(map_mode_unavailable(MapMode::Evidence, &bare).is_some() && map_mode_unavailable(MapMode::Missing, &bare).is_some());
        assert!(map_mode_unavailable(MapMode::Ancestry, &bare).is_some());
        assert!(MapMode::MENU.iter().filter(|m| map_mode_unavailable(**m, &bare).is_none()).count() == MapMode::MENU.len() - 3);
        let with = World { residuals: Some(neolith_core::Residuals::default()), ..bare };
        assert!(map_mode_unavailable(MapMode::Missing, &with).is_none());
    }

    #[test]
    fn evidence_menu_groups_layers_and_keeps_sets_together() {
        let layer = |id: &str, group: &str, set: &str| neolith_core::EvidenceLayer {
            id: id.into(),
            name: id.into(),
            group: group.into(),
            set: set.into(),
            kind: "share".into(),
            units: "share".into(),
            vmin: 0.0,
            vmax: 1.0,
            note: String::new(),
            slices: vec![Year(-5000)],
            codes: vec![],
        };
        let layers = [
            layer("pottery", "Material", ""),
            layer("y_i2", "People", "Y"),
            layer("mt_u5", "People", "mt"),
            layer("adna", "People", ""),
            layer("y_g2a", "People", "Y"),
            layer("cereals", "Subsistence", ""),
        ];
        let menu = evidence_menu(&layers);
        let flat: Vec<(&str, &str, Vec<usize>)> =
            menu.iter().flat_map(|(g, sets)| sets.iter().map(move |(s, m)| (*g, *s, m.clone()))).collect();
        assert_eq!(
            flat,
            vec![
                ("Material", "", vec![0]),
                ("People", "", vec![3]),
                ("People", "Y", vec![1, 4]),
                ("People", "mt", vec![2]),
                ("Subsistence", "", vec![5]),
            ]
        );
    }

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
