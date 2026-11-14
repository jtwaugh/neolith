//! The application: screens, the session tied to one loaded world, and the
//! per-frame logic (clock, snapshot refresh, edits).

use crate::board::camera::Camera;
use crate::board::mesh::{self, BoardMesh};
use crate::board::projection::Projection;
use crate::board::relief::{self, Relief};
use crate::board::renderer::BoardRenderer;
use crate::board::scene::BoardStyle;
use crate::clock::{epoch_index, Clock};
use crate::files::{FileEvent, Files};
use crate::view::BoardInput;
use eframe::wgpu;
use neolith_core::{
    elevation, io, Command, HexId, History, KeyMode, Koeppen, MapMode, PopDensity, Selection, Snapshot, Terrain, Value, World, Year,
};
use std::sync::{Arc, Mutex};

pub const DEFAULT_START_YEAR: i32 = -7500;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tool {
    Select,
    Pencil,
    Fill,
    Lasso,
}

pub enum Screen {
    Loading,
    Failed(String),
    Start,
    Main,
}

pub struct Gpu {
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
    pub target_format: wgpu::TextureFormat,
}

/// Everything tied to one loaded world.
pub struct Session {
    pub world: World,
    pub file_name: String,
    pub unsaved: bool,
    pub keyframes: Vec<Year>,
    pub clock: Clock,
    pub snapshot: Snapshot,
    snapshot_epoch: Option<usize>,
    /// Counts snapshot rebuilds, so caches can tell a new snapshot (a new
    /// epoch or an edit) from the old.
    pub snapshot_gen: u64,
    /// The world changed under the snapshot (an edit, undo or redo).
    world_changed: bool,

    pub mode: MapMode,
    /// Index into `world.evidence` of the layer the Evidence mode shows.
    pub evidence_layer: Option<usize>,
    /// The (layer, slice) whose codes are on the GPU; see [`Session::tick`].
    evidence_shown: Option<(usize, i32)>,
    /// The GPU evidence texture needs re-uploading.
    pub evidence_dirty: bool,
    pub editor: bool,
    pub tool: Tool,
    /// The palette choice per map mode. Typed, never a string.
    pub paint: [Value; 3],
    pub key_mode: KeyMode,
    pub history: History,
    pub selection: Selection,
    pub hover: Option<HexId>,
    pub inspected: Option<HexId>,
    /// Index into `world.settlements` of the selected settlement (shown in
    /// the sidebar's Selected tab).
    pub settlement: Option<usize>,
    pub side_tab: crate::panels::SideTab,
    /// On a narrow (phone) screen the sidebar is a sheet over the bottom
    /// of the board, and this says whether it is open.
    pub sheet: bool,

    pub proj: Projection,
    pub mesh: BoardMesh,
    pub camera: Camera,
    /// Morph between the curved (0) and flat (1) board.
    pub morph: f64,
    pub morph_anim: Option<(f64, f64, f64)>,
    pub renderer: Arc<Mutex<BoardRenderer>>,
    /// The GPU state texture needs re-uploading.
    pub state_dirty: bool,
    /// Per-hex hillshade, from the (static) elevation.
    pub hillshade: Vec<u8>,
    /// Tile heights for picking and overlays; see [`Session::update_relief`].
    pub relief: Arc<Relief>,
    /// The scale `relief` was built with, or `None` when the snapshot changed since.
    relief_scale: Option<(f64, bool)>,
    /// The real topography the mountains are shaped from, if the world has it.
    dem_map: Option<Arc<neolith_core::heightmap::Heightmap>>,
    pub input: BoardInput,
    /// The chronicle ([`crate::events`]), in year order.
    pub events: Vec<crate::events::Event>,
    /// The world was edited since `events` was built.
    events_stale: bool,
    /// The famous-site entry of each settlement ([`crate::renown::index`]),
    /// rebuilt with `events`.
    pub renown: Vec<Option<crate::renown::Renowned>>,
}

impl Session {
    fn new(world: World, file_name: String, gpu: &Gpu, start_year: i32) -> Self {
        let grid = &world.grid;
        let proj = Projection::new(grid.centre_of_bounds());
        let mut board = mesh::build(grid, &proj, &mesh::fine_hexes(&world));
        let mut renderer =
            BoardRenderer::new(&gpu.device, &gpu.queue, gpu.target_format, &board, grid.cols as u32, grid.rows as u32);
        renderer.upload_massif(&gpu.queue, &crate::board::scene::massif_texels(grid, &world.massif));
        if let Some(map) = &world.heightmap {
            renderer.upload_heightfield(&gpu.queue, &crate::board::heightfield::build(grid, map));
        }
        // The vertex data now lives on the GPU; keep only the extents.
        board.vertices = Vec::new();
        board.indices = Vec::new();

        let keyframes = world.keyframe_years();
        let first = keyframes.first().copied().unwrap_or(Year(DEFAULT_START_YEAR));
        let last = keyframes.last().copied().unwrap_or(first);
        // The clock ends at the last keyframe: nothing changes after it.
        let mut clock = Clock::new(first, last);
        clock.set_year(Year(start_year));
        let snapshot = world.snapshot(clock.year());
        let snapshot_epoch = epoch_index(&keyframes, clock.year());
        Self {
            camera: Camera::initial(grid),
            selection: Selection::new(grid.len()),
            keyframes,
            clock,
            snapshot,
            snapshot_epoch,
            snapshot_gen: 0,
            world_changed: false,
            mode: MapMode::Ground,
            evidence_layer: (!world.evidence.is_empty()).then_some(0),
            evidence_shown: None,
            evidence_dirty: true,
            editor: false,
            tool: Tool::Select,
            paint: [
                Value::Terrain(Terrain::Water),
                Value::Koeppen(Koeppen::OCEAN),
                Value::Pop(PopDensity::P0_0),
            ],
            key_mode: KeyMode::InEffect,
            history: History::default(),
            hover: None,
            inspected: None,
            settlement: None,
            side_tab: crate::panels::SideTab::Selected,
            sheet: false,
            proj,
            mesh: board,
            morph: 0.0,
            morph_anim: None,
            renderer: Arc::new(Mutex::new(renderer)),
            state_dirty: true,
            hillshade: elevation::hillshade(&world.grid, &world.elevation, elevation::HILLSHADE_EXAGGERATION),
            relief: Arc::new(Relief::flat(&world.grid)),
            relief_scale: None,
            dem_map: world.heightmap.clone().map(Arc::new),
            input: BoardInput::default(),
            events: crate::events::build(&world),
            events_stale: false,
            renown: crate::renown::index(&world),
            world,
            file_name,
            unsaved: false,
        }
    }

    pub fn year(&self) -> Year {
        self.clock.year()
    }

    /// Rebuilds the CPU copy of the tile heights when the snapshot or the
    /// relief style changed. The GPU computes the same from the height
    /// texture and the scale uniform.
    pub fn update_relief(&mut self, style: &BoardStyle) {
        let scale = relief::scale(style);
        let key = (scale, style.art_blend);
        if self.relief_scale != Some(key) {
            self.relief = Arc::new(
                Relief::new(&self.world.grid, &self.snapshot.height, scale).smoothed(style.art_blend).with_dem(self.dem()),
            );
            self.relief_scale = Some(key);
        }
    }

    /// The mountains' real topography for this snapshot (board::relief::Dem).
    pub fn dem(&self) -> Option<crate::board::relief::Dem> {
        let map = self.dem_map.clone()?;
        Some(crate::board::relief::Dem::new(map, &self.snapshot.terrain, &self.world.landform))
    }

    /// The evidence layer the Evidence mode shows, if the world has any.
    pub fn evidence(&self) -> Option<&neolith_core::EvidenceLayer> {
        self.evidence_layer.and_then(|i| self.world.evidence.get(i))
    }

    /// The selected evidence layer's code per hex at the current year (file
    /// order), or nothing without a layer. Hexes under ice this year have no
    /// value (the board hides the sea itself).
    pub fn evidence_codes(&self) -> Vec<u8> {
        let mut codes = self.evidence().map_or(Vec::new(), |l| l.codes_at(self.year()));
        for (code, terrain) in codes.iter_mut().zip(&self.snapshot.terrain) {
            if *terrain == neolith_core::Terrain::Ice as u8 {
                *code = neolith_core::evidence::NO_VALUE;
            }
        }
        codes
    }

    /// One hex's evidence code this year, as the board shows it.
    /// What the overlay texture should hold: the Missing sites bands while
    /// that mode is shown, else the picked evidence layer's codes. Both use
    /// 255 for "nothing here".
    pub fn overlay_codes(&self) -> Vec<u8> {
        if self.mode == MapMode::Missing {
            self.world.residuals.as_ref().map_or(Vec::new(), |r| r.bands_at(self.year()))
        } else if self.mode == MapMode::Ancestry {
            // Ice hides the ground this year (the board hides the sea itself).
            let mut codes = self.world.ancestry_codes(self.year());
            for (code, terrain) in codes.iter_mut().zip(&self.snapshot.terrain) {
                if *terrain == neolith_core::Terrain::Ice as u8 {
                    *code = neolith_core::ancestry::NO_CODE;
                }
            }
            codes
        } else {
            self.evidence_codes()
        }
    }

    pub fn evidence_code(&self, hex: neolith_core::HexId) -> u8 {
        let hidden = self.snapshot.terrain.get(hex.index()).is_some_and(|t| *t == neolith_core::Terrain::Ice as u8 || *t == neolith_core::Terrain::Water as u8);
        match self.evidence() {
            Some(l) if !hidden => l.code_at(hex, self.year()),
            _ => neolith_core::evidence::NO_VALUE,
        }
    }

    /// Picks the evidence layer with this id; false if there is none.
    pub fn select_evidence(&mut self, id: &str) -> bool {
        match self.world.evidence.iter().position(|l| l.id == id) {
            Some(i) => {
                self.evidence_layer = Some(i);
                true
            }
            None => false,
        }
    }

    /// The value the pencil and fill tools paint in the current map mode
    /// (none in a read-only mode).
    pub fn paint_value(&self) -> Option<Value> {
        self.mode.prop().map(|p| self.paint[p.index()])
    }

    /// The keyframe an edit made now would change, per the current key mode:
    /// the global keyframe in effect, or the current year when inserting.
    pub fn edit_key(&self) -> Year {
        match (self.key_mode, epoch_index(&self.keyframes, self.year())) {
            (KeyMode::InEffect, Some(i)) => self.keyframes[i],
            _ => self.year(),
        }
    }

    fn after_edit(&mut self, inserted_keys: bool) {
        self.world_changed = true;
        self.events_stale = true;
        self.unsaved = true;
        if inserted_keys {
            self.keyframes = self.world.keyframe_years();
        }
    }

    /// Applies a tool's command through the history.
    pub fn apply(&mut self, cmd: Command) {
        if cmd.is_empty() {
            return;
        }
        let inserted = cmd.inserts_keys();
        self.history.apply(&mut self.world, cmd);
        self.after_edit(inserted);
    }

    /// Applies part of a stroke immediately (live feedback while dragging);
    /// the caller records the whole stroke with [`Session::finish_stroke`].
    pub fn apply_live(&mut self, cmd: &Command) {
        if cmd.is_empty() {
            return;
        }
        cmd.apply(&mut self.world);
        self.after_edit(cmd.inserts_keys());
    }

    pub fn finish_stroke(&mut self, cmd: Command) {
        self.history.push_applied(cmd);
    }

    pub fn undo(&mut self) {
        if self.history.undo(&mut self.world).is_some() {
            self.after_edit(true);
        }
    }

    pub fn redo(&mut self) {
        if self.history.redo(&mut self.world).is_some() {
            self.after_edit(true);
        }
    }

    pub fn set_editor(&mut self, on: bool) {
        self.editor = on;
        if on {
            // Entering the editor pauses the clock.
            self.clock.playing = false;
        } else {
            self.tool = Tool::Select;
        }
    }

    /// Starts the ~400 ms curved ↔ flat animation.
    pub fn toggle_flat(&mut self, now: f64) {
        let target = if self.morph_target() > 0.5 { 0.0 } else { 1.0 };
        self.morph_anim = Some((self.morph, target, now));
    }

    pub fn morph_target(&self) -> f64 {
        self.morph_anim.map_or(self.morph, |(_, to, _)| to)
    }

    /// One code path for play, pause, speed and scrub: advance the clock, and
    /// rebuild the snapshot only when the year crossed a keyframe (in either
    /// direction) or the world was edited.
    pub fn tick(&mut self, dt: f64, now: f64) -> bool {
        let mut animating = self.clock.tick(dt);
        if let Some((from, to, start)) = self.morph_anim {
            let p = ((now - start) / 0.4).clamp(0.0, 1.0);
            let eased = p * p * (3.0 - 2.0 * p);
            self.morph = from + (to - from) * eased;
            if p >= 1.0 {
                self.morph_anim = None;
            }
            animating = true;
        }
        let epoch = epoch_index(&self.keyframes, self.year());
        if epoch != self.snapshot_epoch || self.world_changed {
            self.snapshot = self.world.snapshot(self.year());
            self.snapshot_epoch = epoch;
            self.snapshot_gen += 1;
            self.world_changed = false;
            self.state_dirty = true;
            self.relief_scale = None;
            // Ice hides evidence, and the ice just moved.
            self.evidence_shown = None;
        }
        // The evidence texture follows the picked layer and the year: values
        // are interpolated between slices.
        let shown = if self.mode == MapMode::Missing {
            // The Missing sites mode borrows the texture: keyed by its slice.
            self.world.residuals.as_ref().and_then(|r| r.slice_at(self.year())).map(|k| (usize::MAX, k as i32))
        } else if self.mode == MapMode::Ancestry {
            // Borrows the texture too: mixtures move with every year.
            self.world.has_ancestry().then(|| (usize::MAX - 1, self.year().0))
        } else if self.mode == MapMode::Evidence {
            self.evidence_layer.filter(|i| *i < self.world.evidence.len()).map(|i| (i, self.year().0))
        } else {
            // No other mode reads the texture: don't re-send it (and so
            // redraw the board) every year the clock plays.
            None
        };
        if shown != self.evidence_shown {
            self.evidence_shown = shown;
            self.evidence_dirty = true;
        }
        // Rebuilt once a stroke is finished, not per painted hex.
        if self.events_stale && self.input.is_idle() {
            self.events = crate::events::build(&self.world);
            self.renown = crate::renown::index(&self.world);
            self.events_stale = false;
        }
        animating || self.clock.playing
    }

    /// Glides the camera to `to` (the double-click animation).
    pub fn glide_to(&mut self, to: neolith_core::LonLat, now: f64) {
        self.input.glide_to(self.camera.target, to, now);
    }
}

pub struct NeolithApp {
    pub files: Files,
    pub gpu: Option<Gpu>,
    pub screen: Screen,
    pub start_year: i32,
    pub session: Option<Session>,
    pub style: BoardStyle,
    /// A transient message for the status line, with the time it was set.
    pub status: Option<(String, f64)>,
    /// `--ui-screenshot`: capture the window after a few frames and exit.
    #[cfg(not(target_arch = "wasm32"))]
    pub auto_shot: Option<AutoShot>,
    /// `--harness`: the agent control server.
    #[cfg(not(target_arch = "wasm32"))]
    pub harness: Option<crate::harness::Harness>,
}

/// Scripted launch used by `--ui-screenshot` to check the real UI.
#[cfg(not(target_arch = "wasm32"))]
pub struct AutoShot {
    pub path: String,
    pub editor: bool,
    pub flat: bool,
    pub mode: MapMode,
    pub year: Option<i32>,
    pub frames: u32,
}

impl NeolithApp {
    pub fn new(cc: &eframe::CreationContext<'_>, world_path: Option<String>) -> Self {
        let gpu = cc.wgpu_render_state.as_ref().map(|rs| Gpu {
            device: rs.device.clone(),
            queue: rs.queue.clone(),
            target_format: rs.target_format,
        });
        crate::labels::install_fonts(&cc.egui_ctx);
        let files = Files::default();
        let screen = if gpu.is_some() {
            files.load_default(&cc.egui_ctx, world_path);
            Screen::Loading
        } else {
            Screen::Failed("Neolith needs the wgpu renderer (WebGPU or WebGL2), which is not available here.".into())
        };
        Self {
            files,
            gpu,
            screen,
            start_year: DEFAULT_START_YEAR,
            session: None,
            style: BoardStyle::default(),
            status: None,
            #[cfg(not(target_arch = "wasm32"))]
            auto_shot: None,
            #[cfg(not(target_arch = "wasm32"))]
            harness: None,
        }
    }

    /// Drives the app into the main screen, asks egui for a screenshot of
    /// the whole window, saves it and closes.
    #[cfg(not(target_arch = "wasm32"))]
    fn run_auto_shot(&mut self, ctx: &egui::Context) {
        let Some(shot) = &mut self.auto_shot else { return };
        ctx.request_repaint();
        if let Screen::Failed(e) = &self.screen {
            eprintln!("error: {e}");
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            return;
        }
        let Some(s) = &mut self.session else { return };
        if matches!(self.screen, Screen::Start) {
            self.screen = Screen::Main;
            s.clock.set_year(Year(shot.year.unwrap_or(self.start_year)));
            s.mode = shot.mode;
            s.set_editor(shot.editor);
            if shot.editor {
                s.tool = Tool::Pencil;
                s.inspected = s.world.grid.hex_at(s.camera.target);
            }
            if shot.flat {
                s.morph = 1.0;
            }
        }
        shot.frames += 1;
        if shot.frames == 12 {
            let (path, ctx2) = (shot.path.clone(), ctx.clone());
            let save = move |image: std::sync::Arc<egui::ColorImage>| {
                let [w, h] = image.size;
                match image::save_buffer(&path, image.as_raw(), w as u32, h as u32, image::ColorType::Rgba8) {
                    Ok(()) => println!("wrote {path}"),
                    Err(e) => eprintln!("error: cannot write {path}: {e}"),
                }
                ctx2.send_viewport_cmd(egui::ViewportCommand::Close);
            };
            ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(egui::ScreenshotCallback::new(save)));
        }
    }

    fn handle_file_events(&mut self, now: f64) {
        while let Some(ev) = self.files.poll() {
            match ev {
                FileEvent::Loaded { name, bytes } => match {
                    let _span = crate::perf::span("load: decode");
                    io::decode(&bytes)
                } {
                    Ok(world) => {
                        let _span = crate::perf::span("load: session");
                        let gpu = self.gpu.as_ref().expect("a world is only loaded with a GPU");
                        let was_running = matches!(self.screen, Screen::Main);
                        let year = self.session.as_ref().map_or(self.start_year, |s| s.year().0);
                        self.session = Some(Session::new(world, name.clone(), gpu, year));
                        self.screen = if was_running { Screen::Main } else { Screen::Start };
                        self.status = Some((format!("Loaded {name}"), now));
                    }
                    Err(e) => self.fail(format!("{name}: {e}"), now),
                },
                FileEvent::Saved(name) => {
                    if let Some(s) = &mut self.session {
                        s.unsaved = false;
                        s.file_name = name.clone();
                    }
                    self.status = Some((format!("Saved {name}"), now));
                }
                FileEvent::Error(e) => self.fail(e, now),
            }
        }
    }

    fn fail(&mut self, message: String, now: f64) {
        log::error!("{message}");
        if self.session.is_some() {
            // Keep the current world; just report.
            self.status = Some((format!("Error: {message}"), now));
        } else {
            self.screen = Screen::Failed(message);
        }
    }

    pub fn save(&mut self, ctx: &egui::Context) {
        if let Some(s) = &self.session {
            self.files.save_dialog(ctx, io::encode(&s.world));
        }
    }
}

impl eframe::App for NeolithApp {
    /// Runs every pass, painted or not, so the harness answers even while
    /// the window is hidden.
    #[cfg(not(target_arch = "wasm32"))]
    fn logic(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.harness_frame(ctx);
    }

    #[cfg(not(target_arch = "wasm32"))]
    fn raw_input_hook(&mut self, _ctx: &egui::Context, raw_input: &mut egui::RawInput) {
        self.harness_input(raw_input);
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        crate::perf::frame();
        let _frame_span = crate::perf::span("ui total");
        let ctx = ui.ctx().clone();
        let (now, dt) = ctx.input(|i| (i.time, i.stable_dt as f64));
        // The clock follows wall time; `stable_dt` (a smoothed estimate, good for
        // animation) drifts by several percent when frames are irregular.
        let clock_dt = ctx.input(|i| i.unstable_dt as f64);
        self.handle_file_events(now);
        #[cfg(not(target_arch = "wasm32"))]
        self.run_auto_shot(&ctx);
        match &self.screen {
            Screen::Loading => {
                egui::CentralPanel::default().show(ui, |ui| {
                    ui.centered_and_justified(|ui| ui.heading("Loading the world…"));
                });
            }
            Screen::Failed(message) => {
                let message = message.clone();
                egui::CentralPanel::default().show(ui, |ui| {
                    ui.add_space(40.0);
                    ui.vertical_centered(|ui| {
                        ui.heading("Neolith could not start");
                        ui.add_space(8.0);
                        ui.label(message);
                        ui.add_space(12.0);
                        if self.gpu.is_some() && ui.button("Open a world file…").clicked() {
                            self.files.open_dialog(&ctx);
                        }
                    });
                });
            }
            Screen::Start => self.start_screen(ui),
            Screen::Main => {
                #[cfg(target_arch = "wasm32")]
                crate::web_gpu::frame_drawn();
                if let Some(s) = &mut self.session {
                    if s.tick(clock_dt, now) {
                        ctx.request_repaint();
                    }
                }
                self.main_screen(ui, now, dt);
            }
        }
    }
}
