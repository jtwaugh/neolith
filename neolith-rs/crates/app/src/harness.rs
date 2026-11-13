//! Agent harness (native only): `neolith --harness [port]`.
//!
//! A localhost TCP server that lets an agent drive the running app the way a
//! game-playing agent reads a console's RAM: every request is one JSON line,
//! every reply is one JSON line. The agent can
//!
//! - read the game state straight out of the app's memory (`state`, `hex`,
//!   `pick`): year, clock, map mode, camera, the inspected hex, settlements
//!   and labels as drawn last frame, a summary of what is on screen;
//! - take a screenshot of the whole window (`screenshot`);
//! - act through the same paths a player does: synthetic mouse and keyboard
//!   input (`click`, `move`, `drag`, `scroll`, `key`), or direct commands for
//!   the top-bar and timeline controls (`set`, `camera`, `start`).
//!
//! Screen coordinates are screenshot pixels unless a request says
//! `"space": "pt"` (egui points; pixels = points × `pixels_per_point`).
//! See `neolith-rs/harness/README.md` for the protocol and the Python client.

use crate::app::{NeolithApp, Screen, Tool};
use crate::board::scene::ArtMode;
use egui::{Event, Modifiers, PointerButton, Pos2};
use glam::DVec2;
use neolith_core::{HexId, LonLat, MapMode, Prop, Year, NO_ELEVATION};
use serde_json::{json, Map, Value};
use std::collections::VecDeque;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::{Arc, Mutex};

type Reply = Sender<Value>;

pub struct Harness {
    rx: Receiver<(Value, Reply)>,
    /// Synthetic input, one batch of events per frame.
    input: VecDeque<Vec<Event>>,
    /// Replies sent once the input queue has drained and `frames` more have passed.
    after_input: Vec<(u32, Reply, Value)>,
    /// `wait`: replies due at a given app time.
    timers: Vec<(f64, Reply)>,
    /// A screenshot is in flight (one at a time).
    shooting: Arc<AtomicBool>,
    /// The widget tree of the last painted frame (from egui's AccessKit output).
    widgets: Arc<Mutex<Vec<Value>>>,
    /// Real mouse and keyboard input reaches the app (off by default, so a
    /// human's cursor over the window can't disturb the agent's session).
    user_input: bool,
    /// Frames a due reply has waited for the camera to come to rest.
    settle_wait: u32,
    pub port: u16,
}

/// Captures egui's AccessKit tree after every pass, so `ui` can list the
/// widgets on screen with their labels, state and rectangles.
struct UiCapture {
    widgets: Arc<Mutex<Vec<Value>>>,
}

impl egui::Plugin for UiCapture {
    fn debug_name(&self) -> &'static str {
        "neolith-harness-ui-capture"
    }

    fn output_hook(&mut self, ctx: &egui::Context, output: &mut egui::FullOutput) {
        let Some(update) = &output.platform_output.accesskit_update else { return };
        let ppp = ctx.pixels_per_point() as f64;
        let mut out = Vec::new();
        for (_, node) in &update.nodes {
            let label = node.label().map(str::to_owned).or_else(|| node.value().map(str::to_owned)).unwrap_or_default();
            let Some(b) = node.bounds() else { continue };
            if label.trim().is_empty() || b.x1 - b.x0 < 1.0 || b.y1 - b.y0 < 1.0 {
                continue;
            }
            let rect = [b.x0 * ppp, b.y0 * ppp, b.x1 * ppp, b.y1 * ppp].map(f64::round);
            let mut v = json!({
                "role": format!("{:?}", node.role()),
                "label": label,
                "rect_px": rect,
                "centre_px": [((b.x0 + b.x1) / 2.0 * ppp).round(), ((b.y0 + b.y1) / 2.0 * ppp).round()],
            });
            if let Some(t) = node.toggled() {
                v["toggled"] = json!(format!("{t:?}") == "True");
            }
            if let Some(sel) = node.is_selected() {
                v["selected"] = json!(sel);
            }
            if node.is_disabled() {
                v["disabled"] = json!(true);
            }
            if let (Some(val), Some(_)) = (node.value(), node.label()) {
                v["value"] = json!(val);
            }
            if let Some(n) = node.numeric_value() {
                v["numeric_value"] = json!(n);
            }
            out.push(v);
        }
        // Reading order: top to bottom, then left to right.
        out.sort_by(|a, b| {
            let k = |v: &Value| (v["rect_px"][1].as_f64().unwrap_or(0.0), v["rect_px"][0].as_f64().unwrap_or(0.0));
            k(a).partial_cmp(&k(b)).unwrap_or(std::cmp::Ordering::Equal)
        });
        *self.widgets.lock().unwrap() = out;
    }
}

impl Harness {
    /// Binds `127.0.0.1:port` and starts accepting connections.
    pub fn start(ctx: &egui::Context, port: u16) -> std::io::Result<Self> {
        let listener = TcpListener::bind(("127.0.0.1", port))?;
        let port = listener.local_addr()?.port();
        let (tx, rx) = channel();
        let server_ctx = ctx.clone();
        std::thread::spawn(move || {
            let ctx = server_ctx;
            for stream in listener.incoming().flatten() {
                let (tx, ctx) = (tx.clone(), ctx.clone());
                std::thread::spawn(move || serve(stream, tx, ctx));
            }
        });
        let widgets = Arc::new(Mutex::new(Vec::new()));
        ctx.enable_accesskit();
        ctx.add_plugin(UiCapture { widgets: widgets.clone() });
        eprintln!("neolith harness listening on 127.0.0.1:{port}");
        Ok(Self {
            rx,
            input: VecDeque::new(),
            after_input: Vec::new(),
            timers: Vec::new(),
            shooting: Arc::default(),
            widgets,
            user_input: false,
            settle_wait: 0,
            port,
        })
    }
}

fn serve(stream: TcpStream, tx: Sender<(Value, Reply)>, ctx: egui::Context) {
    let Ok(mut out) = stream.try_clone() else { return };
    for line in BufReader::new(stream).lines() {
        let Ok(line) = line else { return };
        if line.trim().is_empty() {
            continue;
        }
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(req) => {
                let (rtx, rrx) = channel();
                if tx.send((req, rtx)).is_err() {
                    return;
                }
                // The window is usually behind the agent's terminal; without this the
                // app only runs its logic, never the ui pass that input and screenshots need.
                ctx.send_viewport_cmd(egui::ViewportCommand::RequestPaintWhileHidden);
                ctx.request_repaint();
                rrx.recv().unwrap_or_else(|_| json!({"ok": false, "error": "the app closed"}))
            }
            Err(e) => json!({"ok": false, "error": format!("bad JSON: {e}")}),
        };
        if writeln!(out, "{reply}").is_err() {
            return;
        }
    }
}

/// egui key names, plus common aliases (`space`, `Num1`, `Digit1`, `KeyA`, `esc`).
fn key_from_name(name: &str) -> Option<egui::Key> {
    let trimmed = name.trim();
    let stripped = ["Num", "Digit", "Key", "num", "digit", "key"]
        .iter()
        .find_map(|p| trimmed.strip_prefix(p).filter(|r| !r.is_empty()))
        .unwrap_or(trimmed);
    let alias = match stripped.to_lowercase().as_str() {
        "esc" => "Escape".to_owned(),
        "return" => "Enter".to_owned(),
        "up" | "down" | "left" | "right" => {
            let mut c = stripped.chars();
            format!("Arrow{}{}", c.next().unwrap().to_ascii_uppercase(), c.as_str().to_lowercase())
        }
        _ => stripped.to_owned(),
    };
    let capitalised = |s: &str| {
        let mut c = s.chars();
        c.next().map(|f| f.to_uppercase().collect::<String>() + c.as_str()).unwrap_or_default()
    };
    [trimmed.to_owned(), alias.clone(), capitalised(&alias), alias.to_uppercase()]
        .iter()
        .find_map(|n| egui::Key::from_name(n))
}

/// Shrinks a `state` readout to what an agent needs most turns.
fn brief_state(v: &mut Value) {
    let Value::Object(m) = v else { return };
    if let Some(Value::Array(k)) = m.get("keyframes") {
        let summary = json!({"count": k.len(), "first": k.first(), "last": k.last()});
        m.insert("keyframes".into(), summary);
    }
    if let Some(Value::Object(s)) = m.get_mut("settlements") {
        if let Some(Value::Array(p)) = s.get_mut("pieces") {
            p.truncate(10);
        }
        if let Some(Value::Array(l)) = s.get("labels_drawn") {
            let n = l.len();
            s.insert("labels_drawn".into(), json!(n));
        }
    }
    if let Some(Value::Array(l)) = m.get("map_labels") {
        let names: Vec<Value> = l.iter().map(|x| x["name"].clone()).collect();
        m.insert("map_labels".into(), json!(names));
    }
    for k in ["hover", "inspected"] {
        if let Some(Value::Object(h)) = m.get_mut(k) {
            h.retain(|k, _| ["id", "lon", "lat", "values", "elevation_m", "npp", "shore_km", "expected_density_per_km2", "farmed", "farming_arrives", "missing_sites", "evidence"].contains(&k.as_str()));
        }
    }
}

/// A view-summary label for an evidence code: the value bin and confidence.
fn evidence_label(layer: Option<&neolith_core::EvidenceLayer>, code: Option<u8>) -> String {
    use neolith_core::evidence;
    match (layer, code) {
        (Some(l), Some(c)) => match (l.value(c), evidence::confidence(c)) {
            (Some(v), Some(k)) => format!("{} ({})", l.format_value(v), evidence::confidence_label(k)),
            _ => "no value".into(),
        },
        _ => "no data".into(),
    }
}

fn err(msg: impl Into<String>) -> Value {
    json!({"ok": false, "error": msg.into()})
}

fn ok(mut v: Value) -> Value {
    if let Value::Object(m) = &mut v {
        m.insert("ok".into(), Value::Bool(true));
    }
    v
}

fn f(req: &Value, k: &str) -> Option<f64> {
    req.get(k).and_then(Value::as_f64)
}

fn modifiers(req: &Value) -> Modifiers {
    let mut m = Modifiers::NONE;
    for name in req.get("modifiers").and_then(Value::as_array).into_iter().flatten().filter_map(Value::as_str) {
        match name {
            "shift" => m.shift = true,
            "ctrl" => m.ctrl = true,
            "alt" => m.alt = true,
            "cmd" | "command" => {
                m.command = true;
                m.mac_cmd = cfg!(target_os = "macos");
                m.ctrl |= !cfg!(target_os = "macos");
            }
            _ => {}
        }
    }
    m
}

fn button(req: &Value) -> PointerButton {
    match req.get("button").and_then(Value::as_str) {
        Some("right" | "secondary") => PointerButton::Secondary,
        Some("middle") => PointerButton::Middle,
        _ => PointerButton::Primary,
    }
}

fn hex_json(app: &NeolithApp, hex: HexId) -> Value {
    let Some(s) = &app.session else { return Value::Null };
    let w = &s.world;
    let year = s.year();
    let (col, row) = w.grid.col_row(hex);
    let c = w.grid.centre(hex);
    let mut props = Map::new();
    for p in Prop::ALL {
        props.insert(p.label().to_lowercase(), w.value_at(hex, p, year).map_or(Value::Null, |v| Value::String(v.label())));
    }
    let lakes: Vec<_> = w
        .lakes
        .iter()
        .filter_map(|l| l.shape_at(year).filter(|sh| sh.contains(c)).map(|sh| json!({"name": l.name, "level_m": sh.level})))
        .collect();
    let rivers: Vec<_> =
        crate::panels::rivers_in_hex(w, hex, year).into_iter().map(|(n, st)| json!({"name": n, "state": format!("{st:?}")})).collect();
    let shore = w.shore_km(year)[hex.index()];
    let residual = w.residuals.as_ref().and_then(|t| t.at(hex, year));
    let expected = w.expected_given(hex, year, shore as f64);
    let evidence = s.evidence().map_or(Value::Null, |l| {
        let code = s.evidence_code(hex);
        json!({"layer": l.id, "code": code, "value": l.value(code), "units": l.units,
               "confidence": neolith_core::evidence::confidence(code).map(neolith_core::evidence::confidence_label)})
    });
    json!({
        "id": hex.geojson_id(), "col": col, "row": row, "lon": c.lon, "lat": c.lat,
        "values": props,
        "elevation_m": match w.elevation[hex.index()] { NO_ELEVATION => Value::Null, z => json!(z) },
        "npp": w.npp_at(hex, year).map_or(Value::Null, |v| json!(v)),
        "shore_km": if shore.is_finite() { json!(shore) } else { Value::Null },
        "expected_density_per_km2": expected.map_or(Value::Null, |e| json!(e.density)),
        "farmed": expected.is_some_and(|e| e.farmed),
        "farming_arrives": w.farming.get(hex.index()).copied().flatten().map_or(Value::Null, |y| json!(y.0)),
        "missing_sites": residual.map_or(Value::Null, |r| json!({"missing": r.missing, "sites_known": r.sites, "reading": r.outcome})),
        "landform": w.landform[hex.index()].map_or(Value::Null, |l| json!(l.label())),
        "evidence": evidence,
        "lakes": lakes, "rivers": rivers,
        "selected": s.selection.contains(hex),
    })
}

/// Board-local point (egui points) from a request's x, y.
fn board_local(app: &NeolithApp, ctx: &egui::Context, req: &Value) -> Option<(DVec2, DVec2)> {
    let s = app.session.as_ref()?;
    let rect = s.input.drawn.rect?;
    let p = screen_pos(ctx, req)?;
    Some((DVec2::new((p.x - rect.left()) as f64, (p.y - rect.top()) as f64), DVec2::new(rect.width() as f64, rect.height() as f64)))
}

fn screen_pos(ctx: &egui::Context, req: &Value) -> Option<Pos2> {
    let (x, y) = (f(req, "x")? as f32, f(req, "y")? as f32);
    let scale = if req.get("space").and_then(Value::as_str) == Some("pt") { 1.0 } else { ctx.pixels_per_point() };
    Some(Pos2::new(x / scale, y / scale))
}

fn rect_px(r: egui::Rect, ppp: f32) -> Value {
    json!([r.left() * ppp, r.top() * ppp, r.right() * ppp, r.bottom() * ppp].map(|v| v.round()))
}

fn pos_px(p: Pos2, ppp: f32) -> Value {
    json!([(p.x * ppp).round(), (p.y * ppp).round()])
}

impl NeolithApp {
    /// Feeds one frame's worth of synthetic input to egui.
    pub fn harness_input(&mut self, raw: &mut egui::RawInput) {
        let Some(h) = &mut self.harness else { return };
        if !h.user_input {
            raw.events.retain(|e| {
                !matches!(
                    e,
                    Event::PointerMoved(_)
                        | Event::MouseMoved(_)
                        | Event::PointerButton { .. }
                        | Event::PointerGone
                        | Event::MouseWheel { .. }
                        | Event::Zoom(_)
                        | Event::Rotate(_)
                        | Event::Touch { .. }
                        | Event::Key { .. }
                        | Event::Text(_)
                        | Event::Ime(_)
                        | Event::ModifiersChanged(_)
                )
            });
        }
        if let Some(batch) = h.input.pop_front() {
            raw.focused = true;
            raw.events.extend(batch);
        }

    }

    /// Handles the requests that arrived since the last frame and sends the
    /// replies that are due.
    pub fn harness_frame(&mut self, ctx: &egui::Context) {
        let Some(mut h) = self.harness.take() else { return };
        let now = ctx.input(|i| i.time);
        while let Ok((req, reply)) = h.rx.try_recv() {
            match self.harness_request(ctx, &mut h, &req, &reply, now) {
                Some(v) => {
                    let _ = reply.send(v);
                }
                None => {} // replied later
            }
        }
        let drained = h.input.is_empty();
        let mut keep = Vec::new();
        let pending = std::mem::take(&mut h.after_input);
        // Replies wait for the camera to stop gliding or coasting (up to
        // about two seconds), so `after` shows where it came to rest.
        let moving = self.session.as_ref().is_some_and(|s| s.input.camera_moving());
        for (frames, reply, mut v) in pending {
            if drained && frames == 0 && (!moving || h.settle_wait >= 120) {
                v["after"] = self.harness_brief(ctx);
                let _ = reply.send(ok(v));
            } else {
                keep.push((if drained { frames.saturating_sub(1) } else { frames }, reply, v));
            }
        }
        h.settle_wait = if drained && moving && keep.iter().any(|(f, _, _)| *f == 0) { h.settle_wait + 1 } else { 0 };
        h.after_input.extend(keep);
        h.timers.retain(|(t, reply)| {
            if now >= *t {
                let _ = reply.send(ok(json!({"time": now})));
                false
            } else {
                true
            }
        });
        if !h.input.is_empty() || !h.after_input.is_empty() || !h.timers.is_empty() || h.shooting.load(Ordering::SeqCst) {
            ctx.send_viewport_cmd(egui::ViewportCommand::RequestPaintWhileHidden);
            ctx.request_repaint();
        }
        self.harness = Some(h);
    }

    fn harness_request(&mut self, ctx: &egui::Context, h: &mut Harness, req: &Value, reply: &Reply, now: f64) -> Option<Value> {
        let cmd = req.get("cmd").and_then(Value::as_str).unwrap_or("");
        let ppp = ctx.pixels_per_point();
        // Input commands reply once their events have been processed, plus a
        // couple of frames for the app to react (glides, smooth scroll).
        let queue = |h: &mut Harness, batches: Vec<Vec<Event>>, settle: u32| {
            h.input.extend(batches);
            h.after_input.push((settle, reply.clone(), json!({})));
            None
        };
        match cmd {
            "ping" => Some(ok(json!({"pong": true}))),
            "state" => {
                let mut v = self.harness_state(ctx);
                v["harness_port"] = json!(h.port);
                v["user_input"] = json!(h.user_input);
                if req.get("brief").and_then(Value::as_bool) == Some(true) {
                    brief_state(&mut v);
                }
                if let Some(fields) = req.get("fields").and_then(Value::as_array) {
                    let keep: Vec<&str> = fields.iter().filter_map(Value::as_str).collect();
                    if let Value::Object(m) = &mut v {
                        m.retain(|k, _| keep.contains(&k.as_str()));
                    }
                }
                Some(ok(v))
            }
            "ui" => {
                let filter = req.get("filter").and_then(Value::as_str).map(str::to_lowercase);
                let widgets: Vec<Value> = h
                    .widgets
                    .lock()
                    .unwrap()
                    .iter()
                    .filter(|w| {
                        filter.as_ref().is_none_or(|f| w["label"].as_str().unwrap_or("").to_lowercase().contains(f.as_str()))
                    })
                    .cloned()
                    .collect();
                Some(ok(json!({"count": widgets.len(), "widgets": widgets})))
            }
            "screenshot" => {
                let Some(path) = req.get("path").and_then(Value::as_str).map(str::to_owned) else {
                    return Some(err("screenshot needs a path"));
                };
                if h.shooting.swap(true, Ordering::SeqCst) {
                    return Some(err("a screenshot is already in progress"));
                }
                let (reply, shooting) = (reply.clone(), h.shooting.clone());
                // The callback runs after this frame is rendered.
                ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(egui::ScreenshotCallback::new(
                    move |image: std::sync::Arc<egui::ColorImage>| {
                        let [w, hgt] = image.size;
                        let r = image::save_buffer(&path, image.as_raw(), w as u32, hgt as u32, image::ColorType::Rgba8);
                        let _ = reply.send(match r {
                            Ok(()) => ok(json!({"path": path, "width": w, "height": hgt})),
                            Err(e) => err(format!("cannot write {path}: {e}")),
                        });
                        shooting.store(false, Ordering::SeqCst);
                    },
                )));
                None
            }
            "start" => {
                let Some(s) = &mut self.session else { return Some(err("no world loaded yet")) };
                if let Some(y) = f(req, "year") {
                    self.start_year = y as i32;
                }
                if matches!(self.screen, Screen::Start) {
                    s.clock.set_year(Year(self.start_year));
                    self.screen = Screen::Main;
                }
                Some(ok(json!({"screen": "main"})))
            }
            "set" => {
                if let Some(u) = req.get("user_input").and_then(Value::as_bool) {
                    h.user_input = u;
                }
                let mut v = self.harness_set(req, now);
                if v["ok"] == json!(true) {
                    // Settle a couple of frames so the reply shows the result.
                    v.as_object_mut().unwrap().remove("ok");
                    h.after_input.push((2, reply.clone(), v));
                    return None;
                }
                Some(v)
            }
            "camera" => {
                let Some(s) = &mut self.session else { return Some(err("no world loaded yet")) };
                let c = &mut s.camera;
                if let Some(v) = f(req, "lon") {
                    c.target.lon = v;
                }
                if let Some(v) = f(req, "lat") {
                    c.target.lat = v;
                }
                if let Some(v) = f(req, "yaw") {
                    c.yaw = v.to_radians();
                }
                if let Some(v) = f(req, "pitch") {
                    c.pitch = v.to_radians();
                    c.pitch_pref = c.pitch;
                }
                if let Some(v) = f(req, "dist") {
                    c.dist = v;
                }
                let grid = s.world.grid.clone();
                s.camera.clamp(&grid);
                // A camera set directly is not then carried off by an earlier pan's coast.
                s.input.stop_camera();
                s.state_dirty = true;
                queue(h, vec![vec![]], 2)
            }
            "hex" => {
                let Some(s) = &self.session else { return Some(err("no world loaded yet")) };
                let hex = match (f(req, "id"), f(req, "lon"), f(req, "lat")) {
                    (Some(id), _, _) => HexId::from_geojson_id(id as u32),
                    (None, Some(lon), Some(lat)) => s.world.grid.hex_at(LonLat::new(lon, lat)),
                    _ => return Some(err("hex needs id, or lon and lat")),
                };
                Some(match hex {
                    Some(hex) if hex.index() < s.world.grid.len() => ok(json!({"hex": hex_json(self, hex)})),
                    _ => err("no such hex"),
                })
            }
            "pick" => {
                let Some((local, size)) = board_local(self, ctx, req) else { return Some(err("pick needs x, y over the board")) };
                let s = self.session.as_ref().unwrap();
                let view = s.camera.view(&s.proj, s.morph, size);
                let hex = view.pick_relief(local, &s.relief).and_then(|ll| s.world.grid.hex_at(ll));
                Some(ok(json!({"hex": hex.map_or(Value::Null, |h| hex_json(self, h))})))
            }
            "project" => {
                let Some(s) = &self.session else { return Some(err("no world loaded yet")) };
                let (Some(lon), Some(lat), Some(rect)) = (f(req, "lon"), f(req, "lat"), s.input.drawn.rect) else {
                    return Some(err("project needs lon, lat and a drawn board"));
                };
                let view = s.camera.view(&s.proj, s.morph, DVec2::new(rect.width() as f64, rect.height() as f64));
                Some(ok(json!({"screen": view
                    .project_relief(LonLat::new(lon, lat), &s.relief)
                    .map(|p| Pos2::new(rect.left() + p.x as f32, rect.top() + p.y as f32))
                    .filter(|p| rect.contains(*p))
                    .map_or(Value::Null, |p| pos_px(p, ppp))})))
            }
            "move" => {
                let Some(p) = screen_pos(ctx, req) else { return Some(err("move needs x, y")) };
                queue(h, vec![vec![Event::PointerMoved(p)]], 1)
            }
            "click" | "double_click" => {
                let Some(p) = screen_pos(ctx, req) else { return Some(err("click needs x, y")) };
                let (button, modifiers) = (button(req), modifiers(req));
                let press = |pressed| Event::PointerButton { pos: p, button, pressed, modifiers };
                let mut b = vec![vec![Event::ModifiersChanged(modifiers), Event::PointerMoved(p)], vec![press(true)], vec![press(false)]];
                if cmd == "double_click" {
                    b.extend([vec![press(true)], vec![press(false)]]);
                }
                b.push(vec![Event::ModifiersChanged(Modifiers::NONE)]);
                queue(h, b, 3)
            }
            "drag" => {
                let (Some(a), Some(b)) = (
                    screen_pos(ctx, &json!({"x": req.get("x"), "y": req.get("y"), "space": req.get("space")})),
                    screen_pos(ctx, &json!({"x": req.get("to_x"), "y": req.get("to_y"), "space": req.get("space")})),
                ) else {
                    return Some(err("drag needs x, y, to_x, to_y"));
                };
                let (button, modifiers) = (button(req), modifiers(req));
                let steps = f(req, "steps").unwrap_or(12.0).clamp(2.0, 200.0) as usize;
                let mut batches = vec![
                    vec![Event::ModifiersChanged(modifiers), Event::PointerMoved(a)],
                    vec![Event::PointerButton { pos: a, button, pressed: true, modifiers }],
                ];
                for k in 1..=steps {
                    batches.push(vec![Event::PointerMoved(a.lerp(b, k as f32 / steps as f32))]);
                }
                // Hold still before releasing so the pan does not coast.
                batches.push(vec![Event::PointerMoved(b)]);
                batches.push(vec![Event::PointerButton { pos: b, button, pressed: false, modifiers }]);
                batches.push(vec![Event::ModifiersChanged(Modifiers::NONE)]);
                queue(h, batches, 3)
            }
            "scroll" => {
                let Some(p) = screen_pos(ctx, req) else { return Some(err("scroll needs x, y")) };
                let dy = f(req, "dy").unwrap_or(240.0) as f32; // positive zooms the board in
                let wheel = Event::MouseWheel {
                    unit: egui::MouseWheelUnit::Point,
                    delta: egui::vec2(f(req, "dx").unwrap_or(0.0) as f32, dy),
                    phase: egui::TouchPhase::Move,
                    source: egui::MouseWheelSource::Unknown,
                    modifiers: modifiers(req),
                };
                // egui smooths scrolling over several frames.
                queue(h, vec![vec![Event::PointerMoved(p)], vec![wheel]], 20)
            }
            "key" => {
                let name = req.get("key").and_then(Value::as_str).unwrap_or("");
                let Some(key) = key_from_name(name) else {
                    return Some(err(format!(
                        "unknown key {name:?}; use egui names: A–Z, 0–9, Space, Enter, Escape, Tab, Backspace, Delete, \
                         ArrowUp/Down/Left/Right, PageUp, PageDown, Home, End, F1–F12, Plus, Minus"
                    )));
                };
                let modifiers = modifiers(req);
                let ev = |pressed| Event::Key { key, physical_key: None, pressed, repeat: false, modifiers };
                queue(h, vec![vec![Event::ModifiersChanged(modifiers), ev(true)], vec![ev(false), Event::ModifiersChanged(Modifiers::NONE)]], 2)
            }
            "text" => {
                let t = req.get("text").and_then(Value::as_str).unwrap_or("").to_owned();
                queue(h, vec![vec![Event::Text(t)]], 2)
            }
            "wait" => {
                if let Some(frames) = f(req, "frames") {
                    return queue(h, vec![], frames.max(0.0) as u32);
                }
                h.timers.push((now + f(req, "seconds").unwrap_or(1.0).clamp(0.0, 600.0), reply.clone()));
                None
            }
            "quit" => {
                ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                Some(ok(json!({})))
            }
            other => Some(err(format!(
                "unknown cmd {other:?}; try ping, state, ui, screenshot, start, set, camera, hex, pick, project, move, \
                 click, double_click, drag, scroll, key, text, wait, quit"
            ))),
        }
    }

    /// The few fields an action usually changes, attached to its reply.
    fn harness_brief(&self, ctx: &egui::Context) -> Value {
        let screen = match &self.screen {
            Screen::Loading => "loading",
            Screen::Failed(_) => "failed",
            Screen::Start => "start",
            Screen::Main => "main",
        };
        let Some(s) = &self.session else { return json!({"screen": screen}) };
        let c = &s.camera;
        let _ = ctx;
        json!({
            "screen": screen,
            "year": s.year().0,
            "playing": s.clock.playing,
            "years_per_sec": s.clock.years_per_sec,
            "map_mode": s.mode.label(),
            "evidence_layer": s.evidence().map(|l| l.id.clone()),
            "editor": s.editor,
            "flat": s.morph_target() > 0.5,
            "camera": {"lon": c.target.lon, "lat": c.target.lat, "yaw_deg": c.yaw.to_degrees(),
                       "pitch_deg": c.pitch.to_degrees(), "dist": c.dist},
            "hover": s.hover.map(|h| h.geojson_id()),
            "inspected": s.inspected.map(|h| h.geojson_id()),
            "settlement_popup": s.settlement.map(|i| s.world.settlements[i].name.clone()),
            "hovered_settlement": s.input.drawn.piece_hover.map(|i| s.world.settlements[i].name.clone()),
            "speed_step": s.clock.speed_step() + 1,
            "events": crate::events::recent(&s.events, s.year(), 12)
                .map(|e| json!({"year": e.year.0, "kind": e.kind.name(), "text": e.text}))
                .collect::<Vec<_>>(),
        })
    }

    fn harness_set(&mut self, req: &Value, now: f64) -> Value {
        if let Some(v) = req.get("relief").and_then(Value::as_bool) {
            self.style.relief = v;
        }
        if let Some(v) = req.get("art").and_then(Value::as_str) {
            self.style.terrain_art = match v {
                "off" => ArtMode::Off,
                "on" | "3d" => ArtMode::On,
                _ => return err(format!("art: off or on, not {v:?} (the 2D art is gone)")),
            };
        }
        if let Some(v) = req.get("rivers").and_then(Value::as_bool) {
            self.style.rivers = v;
        }
        if let Some(v) = req.get("survey").and_then(Value::as_bool) {
            self.style.survey = v;
        }
        // Board-style layers, to look at one at a time.
        let st = &mut self.style;
        for (k, slot, lo, hi) in [
            ("hillshade", &mut st.hillshade, 0.0, 1.0),
            ("borders", &mut st.borders, 0.0, 1.0),
            ("grout", &mut st.grout, 0.0, 1.0),
            ("bevel", &mut st.bevel, 0.0, 1.0),
            ("art_strength", &mut st.art_strength, 0.0, 1.0),
            ("saturation", &mut st.saturation, 0.0, 1.3),
            ("relief_exaggeration", &mut st.relief_exaggeration, 1.0, 40.0),
            ("mountain_height", &mut st.mountain_height, 0.3, 1.5),
            ("fill_margin", &mut st.fill_margin, 0.0, 0.45),
            ("depth", &mut st.depth, 0.0, 1.0),
        ] {
            if let Some(v) = f(req, k) {
                *slot = (v as f32).clamp(lo, hi);
            }
        }
        for (k, slot) in [("art_blend", &mut st.art_blend), ("flat_lighting", &mut st.flat_lighting), ("fill", &mut st.fill_screen)] {
            if let Some(v) = req.get(k).and_then(Value::as_bool) {
                *slot = v;
            }
        }
        let Some(s) = &mut self.session else { return err("no world loaded yet") };
        // The board style lives in the sidebar's Map tab.
        if let Some(v) = req.get("style_window").and_then(Value::as_bool) {
            s.side_tab = if v { crate::panels::SideTab::Map } else { crate::panels::SideTab::Selected };
        }
        if let Some(v) = req.get("tab").and_then(Value::as_str) {
            match crate::panels::SideTab::ALL.iter().find(|t| t.label().eq_ignore_ascii_case(v)) {
                Some(t) => s.side_tab = *t,
                None => return err(format!("unknown tab {v:?}; use Selected, Chronicle or Map")),
            }
        }
        if let Some(y) = f(req, "year") {
            s.clock.set_year(Year(y as i32));
        }
        if let Some(v) = req.get("playing").and_then(Value::as_bool) {
            s.clock.playing = v && !s.editor;
        }
        if let Some(v) = f(req, "speed") {
            s.clock.years_per_sec = v.clamp(crate::clock::SPEED_MIN, crate::clock::SPEED_MAX);
        }
        if let Some(id) = req.get("evidence").and_then(Value::as_str) {
            if !s.select_evidence(id) {
                let ids: Vec<&str> = s.world.evidence.iter().map(|l| l.id.as_str()).collect();
                return err(format!("evidence: no layer {id:?}; this world has {}", if ids.is_empty() { "none".into() } else { ids.join(", ") }));
            }
        }
        if let Some(m) = req.get("mode").and_then(Value::as_str) {
            match MapMode::from_arg(m) {
                Some(MapMode::Evidence) if s.world.evidence.is_empty() => return err("mode: this world has no evidence layers"),
                Some(MapMode::Missing) if s.world.residuals.is_none() => return err("mode: this world has no missing-sites table"),
                Some(m) => s.mode = m,
                None => {
                    return err(format!(
                        "mode: terrain, koeppen, pop, elevation, npp, biodiversity, expected, evidence or missing, not {m:?}"
                    ))
                }
            }
        }
        if let Some(v) = req.get("editor").and_then(Value::as_bool) {
            s.set_editor(v);
        }
        if let Some(t) = req.get("tool").and_then(Value::as_str) {
            s.tool = match t {
                "select" => Tool::Select,
                "pencil" => Tool::Pencil,
                "fill" => Tool::Fill,
                "lasso" => Tool::Lasso,
                _ => return err(format!("tool: select, pencil, fill or lasso, not {t:?}")),
            };
        }
        if let Some(v) = req.get("flat").and_then(Value::as_bool) {
            if (s.morph_target() > 0.5) != v {
                s.toggle_flat(now);
            }
        }
        if req.get("inspect").is_some_and(Value::is_null) {
            s.inspected = None;
        } else if let Some(id) = f(req, "inspect") {
            s.inspected = HexId::from_geojson_id(id as u32).filter(|h| h.index() < s.world.grid.len());
        }
        if req.get("settlement").is_some_and(Value::is_null) {
            s.settlement = None;
        } else if let Some(name) = req.get("settlement").and_then(Value::as_str) {
            match s.world.settlements.iter().position(|st| st.name.eq_ignore_ascii_case(name)) {
                Some(i) => s.settlement = Some(i),
                None => return err(format!("no settlement named {name:?}")),
            }
        }
        s.state_dirty = true;
        ok(json!({}))
    }

    fn harness_state(&self, ctx: &egui::Context) -> Value {
        let ppp = ctx.pixels_per_point();
        let screen_rect = ctx.content_rect();
        let screen = match &self.screen {
            Screen::Loading => json!("loading"),
            Screen::Failed(e) => json!({"failed": e}),
            Screen::Start => json!("start"),
            Screen::Main => json!("main"),
        };
        let mut out = json!({
            "screen": screen,
            "window_px": [(screen_rect.width() * ppp).round(), (screen_rect.height() * ppp).round()],
            "pixels_per_point": ppp,
            "status": self.status.as_ref().map(|(m, _)| m.clone()),
            "style": {
                "relief": self.style.relief,
                "terrain_art": self.style.terrain_art.label(),
                "rivers": self.style.rivers,
                "survey": self.style.survey,
                "hillshade": self.style.hillshade,
                "borders": self.style.borders,
                "grout": self.style.grout,
                "bevel": self.style.bevel,
                "art_strength": self.style.art_strength,
                "art_blend": self.style.art_blend,
                "saturation": self.style.saturation,
                "flat_lighting": self.style.flat_lighting,
                "relief_exaggeration": self.style.relief_exaggeration,
                "mountain_height": self.style.mountain_height,
                "fill": self.style.fill_screen,
                "fill_margin": self.style.fill_margin,
                "depth": self.style.depth,
                "style_window_open": self.session.as_ref().is_some_and(|s| s.side_tab == crate::panels::SideTab::Map),
            },
            "start_year": self.start_year,
        });
        let Some(s) = &self.session else { return out };
        let year = s.year();
        let (min, max) = s.clock.range();
        let d = &s.input.drawn;
        let settlement_json = |i: usize| {
            let st = &s.world.settlements[i];
            let mut v = json!({"index": i, "name": st.name, "lon": st.pos.lon, "lat": st.pos.lat, "founded": st.founded.0,
                   "population": st.population_at(year)});
            if let Some(info) = s.world.site_info(i) {
                let att = |stage| crate::site_record::attribution(&s.world, info, year, st.phase_at(year), stage).map(|a| json!({"name": a.name, "wikipedia": a.wikipedia, "inferred": a.inferred}));
                v["record"] = json!({
                    "kind": info.kind, "last_date": info.abandoned.map(|y| y.0), "n_dates": info.dates.len(),
                    "abandoned_by": st.abandoned_by().map(|y| y.0),
                    "occupation": st.occupation.iter().map(|(a, b)| [a.0, b.0]).collect::<Vec<_>>(),
                    "dates_by_now": info.dates.iter().filter(|d| d.cal <= year).count(),
                    "culture": att(false), "stage": att(true), "features": info.features,
                    "wikipedia": info.wikipedia, "wikidata": info.wikidata,
                });
            }
            v
        };
        // What the board shows: hexes whose centre is on screen, by value.
        let mut summary = Value::Null;
        if let Some(rect) = d.rect {
            let view = s.camera.view(&s.proj, s.morph, DVec2::new(rect.width() as f64, rect.height() as f64));
            let prop = s.mode.prop();
            let mut counts: std::collections::BTreeMap<String, usize> = Default::default();
            let mut n = 0;
            for hex in s.world.grid.ids() {
                let centre = s.world.grid.centre(hex);
                let Some(p) = view.project_relief(centre, &s.relief) else { continue };
                if p.x < 0.0 || p.y < 0.0 || p.x > rect.width() as f64 || p.y > rect.height() as f64 {
                    continue;
                }
                // Skip hexes hidden behind the curve of the board.
                if view.pick(p).and_then(|ll| s.world.grid.hex_at(ll)) != Some(hex) {
                    continue;
                }
                n += 1;
                let label = match prop {
                    Some(prop) => s.world.value_at(hex, prop, year).map_or("no data".into(), |v| v.label()),
                    None if s.mode == MapMode::Npp => neolith_core::productivity::band_label(s.snapshot.npp[hex.index()])
                        .map_or("no data".into(), |l| format!("{l} {}", neolith_core::productivity::UNIT)),
                    None if s.mode == MapMode::Expected => neolith_core::farming::band_label(s.snapshot.expected[hex.index()])
                        .map_or("no data".into(), |l| format!("{l} per 100 km²")),
                    None if s.mode == MapMode::Missing => s
                        .world
                        .residuals
                        .as_ref()
                        .and_then(|t| t.at(hex, year))
                        .and_then(|r| neolith_core::residuals::band_label(neolith_core::residuals::band((r.missing * 10.0).round() as i16)))
                        .map_or("no data".into(), |l| format!("{l} sites missing")),
                    None if s.mode == MapMode::Evidence => evidence_label(s.evidence(), s.evidence_codes().get(hex.index()).copied()),
                    None if s.mode == MapMode::Biodiversity => {
                        neolith_core::forager::biodiversity_band_label(s.snapshot.biodiversity[hex.index()])
                            .unwrap_or("no data".into())
                    }
                    None => match s.world.elevation[hex.index()] {
                        NO_ELEVATION => "no data".into(),
                        z => format!("{}–{} m", z.div_euclid(500) * 500, z.div_euclid(500) * 500 + 500),
                    },
                };
                *counts.entry(label).or_default() += 1;
            }
            let mut top: Vec<_> = counts.into_iter().collect();
            top.sort_by(|a, b| b.1.cmp(&a.1));
            let by_value: Map<String, Value> = top.into_iter().take(12).map(|(k, v)| (k, json!(v))).collect();
            summary = json!({"hexes_on_screen": n, "by_value": by_value});
        }
        let c = &s.camera;
        let mut pieces: Vec<_> = d.pieces.iter().collect();
        pieces.sort_by_key(|(i, _, _)| std::cmp::Reverse(s.world.settlements[*i].population_at(year).unwrap_or(0)));
        let pieces: Vec<Value> = pieces
            .into_iter()
            .take(60)
            .map(|(i, base, top)| {
                let mut v = settlement_json(*i);
                v["screen_px"] = pos_px(base.lerp(*top, 0.5), ppp);
                v
            })
            .collect();
        let labels: Vec<Value> =
            d.labels.iter().map(|(i, r)| json!({"name": s.world.settlements[*i].name, "rect_px": rect_px(*r, ppp)})).collect();
        let extra = json!({
            "file": s.file_name, "unsaved": s.unsaved,
            "year": year.0, "year_label": year.to_string(),
            "clock": {"playing": s.clock.playing, "years_per_sec": s.clock.years_per_sec, "speed_step": s.clock.speed_step() + 1,
                      "min": min.0, "max": max.0},
            "chronicle": crate::events::recent(&s.events, s.year(), 12)
                .map(|e| json!({"year": e.year.0, "kind": e.kind.name(), "text": e.text}))
                .collect::<Vec<_>>(),
            "keyframes": s.keyframes.iter().map(|k| k.0).collect::<Vec<_>>(),
            "map_mode": s.mode.label(),
            "evidence_layer": s.evidence().map(|l| l.id.clone()),
            "evidence_layers": s.world.evidence.iter().map(|l| l.id.clone()).collect::<Vec<_>>(),
            "editor": s.editor, "tool": format!("{:?}", s.tool),
            "history": {"can_undo": s.history.can_undo(), "can_redo": s.history.can_redo()},
            "selection_count": s.selection.count(),
            "camera": {"lon": c.target.lon, "lat": c.target.lat, "yaw_deg": c.yaw.to_degrees(),
                       "pitch_deg": c.pitch.to_degrees(), "dist": c.dist},
            "flat": s.morph_target() > 0.5,
            "board_rect_px": d.rect.map_or(Value::Null, |r| rect_px(r, ppp)),
            "hover": s.hover.map_or(Value::Null, |h| hex_json(self, h)),
            "inspected": s.inspected.map_or(Value::Null, |h| hex_json(self, h)),
            "settlement_popup": s.settlement.map_or(Value::Null, settlement_json),
            "settlements": {
                "total": s.world.settlements.len(),
                "founded_by_now": s.world.settlements.iter().filter(|st| st.founded <= year).count(),
                "occupied_now": s.world.settlements.iter().filter(|st| st.exists_at(year)).count(),
                "on_screen": d.pieces.len(),
                "hovered": d.piece_hover.map_or(Value::Null, settlement_json),
                // The first 60 on screen, biggest first, with where to click them.
                "pieces": pieces,
                "labels_drawn": labels,
            },
            "view_summary": summary,
            "map_labels": d.geo.iter().map(|l| json!({"name": l.name, "kind": l.kind, "size": l.size.round(),
                                                      "rect_px": rect_px(l.bounds, ppp)})).collect::<Vec<_>>(),
            "world": {"hexes": s.world.grid.len(), "rivers": s.world.rivers.len(), "lakes": s.world.lakes.len()},
        });
        if let (Value::Object(o), Value::Object(e)) = (&mut out, extra) {
            o.extend(e);
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modifiers_parse() {
        let m = modifiers(&json!({"modifiers": ["shift", "alt"]}));
        assert!(m.shift && m.alt && !m.ctrl);
        assert_eq!(button(&json!({"button": "right"})), PointerButton::Secondary);
        assert_eq!(button(&json!({})), PointerButton::Primary);
    }

    #[test]
    fn key_aliases() {
        assert_eq!(key_from_name("space"), Some(egui::Key::Space));
        assert_eq!(key_from_name("Num1"), Some(egui::Key::Num1));
        assert_eq!(key_from_name("1"), Some(egui::Key::Num1));
        assert_eq!(key_from_name("z"), Some(egui::Key::Z));
        assert_eq!(key_from_name("esc"), Some(egui::Key::Escape));
        assert_eq!(key_from_name("left"), Some(egui::Key::ArrowLeft));
        assert_eq!(key_from_name("nonsense"), None);
    }

    #[test]
    fn brief_state_trims() {
        let mut v = json!({"keyframes": [-3, -2, -1], "settlements": {"pieces": (0..20).collect::<Vec<_>>(), "labels_drawn": [1, 2]}});
        brief_state(&mut v);
        assert_eq!(v["keyframes"]["count"], json!(3));
        assert_eq!(v["settlements"]["pieces"].as_array().unwrap().len(), 10);
        assert_eq!(v["settlements"]["labels_drawn"], json!(2));
    }

    #[test]
    fn ok_marks_objects() {
        assert_eq!(ok(json!({"a": 1})), json!({"a": 1, "ok": true}));
        assert_eq!(err("x")["ok"], json!(false));
    }
}
