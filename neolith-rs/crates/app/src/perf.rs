//! A frame profiler, for checking performance on phones where no desktop
//! profiler reaches. It keeps the CPU time of named sections of a frame,
//! the interval between frames and the GPU time of the board pass.
//!
//! Off by default. On the web, `?perf` in the page's URL turns it on and
//! draws a small readout in the board's top-right corner, so it works on a
//! phone. Natively it is on under `NEOLITH_PERF=1` or the harness's `perf`
//! command, which also reads it.
//!
//! GPU time is the time from submitting the board pass until the GPU
//! reports it done (`on_submitted_work_done`). That includes any queueing,
//! so it is an upper bound. Natively, `NEOLITH_PERF=gpu` blocks on the
//! pass instead, which is exact but stalls the frame.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use web_time::Instant;

static ENABLED: AtomicBool = AtomicBool::new(false);
static STATE: Mutex<State> = Mutex::new(State::new());

/// Frames kept for the interval percentiles (about two seconds at 60 Hz).
const WINDOW: usize = 120;

#[derive(Clone, Copy, Debug, Default, serde::Serialize)]
pub struct Stat {
    /// The last sample, ms.
    pub last: f32,
    /// A moving average (about the last 30 samples), ms.
    pub avg: f32,
    /// The largest sample in the window, ms.
    pub max: f32,
    /// Samples in the window.
    pub count: u32,
    #[serde(skip)]
    recent: [f32; 32],
    #[serde(skip)]
    next: usize,
}

impl Stat {
    fn add(&mut self, ms: f32) {
        self.last = ms;
        self.avg = if self.count == 0 { ms } else { self.avg + (ms - self.avg) / 30.0 };
        self.recent[self.next] = ms;
        self.next = (self.next + 1) % self.recent.len();
        self.count = self.count.saturating_add(1);
        self.max = self.recent.iter().copied().fold(0.0, f32::max);
    }
}

struct State {
    sections: Vec<(&'static str, Stat)>,
    intervals: VecDeque<f32>,
    last_frame: Option<Instant>,
    /// Board passes drawn, and frames, since the last report.
    board_renders: u32,
    frames: u32,
    board_px: [u32; 2],
}

impl State {
    const fn new() -> Self {
        Self { sections: Vec::new(), intervals: VecDeque::new(), last_frame: None, board_renders: 0, frames: 0, board_px: [0; 2] }
    }
}

pub fn enabled() -> bool {
    ENABLED.load(Ordering::Relaxed)
}

pub fn set_enabled(on: bool) {
    ENABLED.store(on, Ordering::Relaxed);
}

/// `NEOLITH_PERF=gpu` (native): wait for each board pass to finish.
pub fn gpu_sync() -> bool {
    #[cfg(not(target_arch = "wasm32"))]
    {
        static SYNC: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        *SYNC.get_or_init(|| std::env::var("NEOLITH_PERF").is_ok_and(|v| v == "gpu"))
    }
    #[cfg(target_arch = "wasm32")]
    false
}

/// Turns the profiler on from the environment (native) or the URL (web).
pub fn init() {
    #[cfg(not(target_arch = "wasm32"))]
    let on = std::env::var("NEOLITH_PERF").is_ok_and(|v| !v.is_empty() && v != "0");
    #[cfg(target_arch = "wasm32")]
    let on = query_param("perf").is_some();
    set_enabled(on);
}

/// The value of `name` in the page URL's query (`?name=value`), if any.
#[cfg(target_arch = "wasm32")]
pub fn query_param(name: &str) -> Option<String> {
    let q = web_sys::window()?.location().search().ok()?;
    q.trim_start_matches('?').split('&').find_map(|kv| {
        let (k, v) = kv.split_once('=').unwrap_or((kv, ""));
        (k == name).then(|| v.to_string())
    })
}

pub fn record(name: &'static str, ms: f32) {
    if !enabled() {
        return;
    }
    let mut st = STATE.lock().unwrap();
    match st.sections.iter_mut().find(|(n, _)| *n == name) {
        Some((_, s)) => s.add(ms),
        None => {
            let mut s = Stat::default();
            s.add(ms);
            st.sections.push((name, s));
        }
    }
}

/// Times the rest of the enclosing scope as section `name`.
#[must_use]
pub struct Span(Option<(&'static str, Instant)>);

pub fn span(name: &'static str) -> Span {
    Span(enabled().then(|| (name, Instant::now())))
}

impl Drop for Span {
    fn drop(&mut self) {
        if let Some((name, t)) = self.0 {
            record(name, t.elapsed().as_secs_f32() * 1000.0);
        }
    }
}

/// Call once at the start of every frame.
pub fn frame() {
    if !enabled() {
        return;
    }
    let now = Instant::now();
    let mut st = STATE.lock().unwrap();
    if let Some(t) = st.last_frame {
        let ms = (now - t).as_secs_f32() * 1000.0;
        if st.intervals.len() == WINDOW {
            st.intervals.pop_front();
        }
        st.intervals.push_back(ms);
    }
    st.last_frame = Some(now);
    st.frames += 1;
}

/// The board pass ran this frame, at `px` pixels.
pub fn board_rendered(px: [u32; 2]) {
    if !enabled() {
        return;
    }
    let mut st = STATE.lock().unwrap();
    st.board_renders += 1;
    st.board_px = px;
}

/// Times the board pass on the GPU: from now until the queue reports the
/// work submitted so far done.
pub fn time_gpu(device: &eframe::wgpu::Device, queue: &eframe::wgpu::Queue, cpu_start: Instant) {
    if !enabled() {
        return;
    }
    if gpu_sync() {
        let _ = device.poll(eframe::wgpu::PollType::wait_indefinitely());
        record("gpu board", cpu_start.elapsed().as_secs_f32() * 1000.0);
        return;
    }
    let _ = device;
    queue.on_submitted_work_done(move || record("gpu board", cpu_start.elapsed().as_secs_f32() * 1000.0));
}

#[derive(Debug, serde::Serialize)]
pub struct Report {
    pub sections: Vec<(String, Stat)>,
    pub interval_p50: f32,
    pub interval_p95: f32,
    pub interval_max: f32,
    pub fps: f32,
    pub frames: u32,
    pub board_renders: u32,
    pub board_px: [u32; 2],
}

/// The numbers so far; `reset` starts the counters and sections again.
pub fn report(reset: bool) -> Report {
    let mut st = STATE.lock().unwrap();
    let mut iv: Vec<f32> = st.intervals.iter().copied().collect();
    iv.sort_by(f32::total_cmp);
    let pct = |p: f32| if iv.is_empty() { 0.0 } else { iv[((iv.len() - 1) as f32 * p).round() as usize] };
    let mean = if iv.is_empty() { 0.0 } else { iv.iter().sum::<f32>() / iv.len() as f32 };
    let r = Report {
        sections: st.sections.iter().map(|(n, s)| (n.to_string(), *s)).collect(),
        interval_p50: pct(0.5),
        interval_p95: pct(0.95),
        interval_max: iv.last().copied().unwrap_or(0.0),
        fps: if mean > 0.0 { 1000.0 / mean } else { 0.0 },
        frames: st.frames,
        board_renders: st.board_renders,
        board_px: st.board_px,
    };
    if reset {
        st.sections.clear();
        st.intervals.clear();
        st.board_renders = 0;
        st.frames = 0;
    }
    r
}

/// Draws the readout at the top right of `rect`.
pub fn overlay(painter: &egui::Painter, rect: egui::Rect) {
    if !enabled() {
        return;
    }
    let r = report(false);
    let mut text = format!(
        "{:.0} fps  frame p50 {:.1} p95 {:.1} max {:.0} ms\nboard {}×{} px, {} passes / {} frames\n",
        r.fps, r.interval_p50, r.interval_p95, r.interval_max, r.board_px[0], r.board_px[1], r.board_renders, r.frames
    );
    for (name, s) in &r.sections {
        text.push_str(&format!("{name:<12} {:>5.2} avg {:>5.1} max\n", s.avg, s.max));
    }
    let font = egui::FontId::monospace(10.0);
    let galley = painter.layout_no_wrap(text, font, egui::Color32::from_rgb(230, 230, 200));
    let pos = egui::pos2(rect.right() - galley.size().x - 8.0, rect.top() + 46.0);
    painter.rect_filled(egui::Rect::from_min_size(pos, galley.size()).expand(4.0), 3.0, egui::Color32::from_black_alpha(170));
    painter.galley(pos, galley, egui::Color32::WHITE);
}
