//! Choosing WebGPU or WebGL 2 on the web, with a fallback.
//!
//! wgpu on the web uses WebGPU whenever `navigator.gpu` exists and never
//! falls back to WebGL by itself. Chrome on Android and Firefox (141+ on
//! Windows, 145+ on macOS) expose `navigator.gpu` on devices where the
//! adapter is missing, the device's limits are too small, or the driver
//! fails later, so a WebGPU-only start leaves those users with nothing.
//!
//! The policy, in order:
//! 1. `?gl` (or `?renderer=gl`) in the URL forces WebGL; `?webgpu` forces WebGPU.
//! 2. If an earlier WebGPU start on this tab never reached a working board
//!    (it panicked, or the device was lost), the next load uses WebGL. A
//!    `sessionStorage` flag is set before WebGPU starts and cleared once
//!    frames are being drawn ([`frame_drawn`]); index.html reloads the
//!    page once when the wasm traps while the flag is set.
//! 3. Otherwise WebGPU is tried first; if eframe fails to start with it,
//!    the canvas is replaced and the start retried with WebGL.

use eframe::wgpu;
use std::sync::Arc;

const PENDING_KEY: &str = "neolith.webgpu-pending";

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Backend {
    WebGpu,
    WebGl,
}

fn session() -> Option<web_sys::Storage> {
    web_sys::window()?.session_storage().ok()?
}

/// Which backend to try first on this load.
pub fn first_choice() -> Backend {
    use crate::perf::query_param;
    let renderer = query_param("renderer");
    if query_param("gl").is_some() || renderer.as_deref() == Some("gl") {
        return Backend::WebGl;
    }
    if query_param("webgpu").is_some() || renderer.as_deref() == Some("webgpu") {
        return Backend::WebGpu;
    }
    let crashed = session().and_then(|s| s.get_item(PENDING_KEY).ok().flatten()).is_some();
    if crashed {
        log::warn!("the last WebGPU start on this tab did not reach a working board; using WebGL");
        return Backend::WebGl;
    }
    Backend::WebGpu
}

/// Note that a WebGPU start is under way, so a crash before
/// [`frame_drawn`] makes the next load use WebGL.
pub fn mark_pending(backend: Backend) {
    if let Some(s) = session() {
        let _ = match backend {
            Backend::WebGpu => s.set_item(PENDING_KEY, "1"),
            Backend::WebGl => s.remove_item(PENDING_KEY),
        };
    }
}

/// The board was drawn. Asynchronous WebGPU validation errors and device
/// loss show up within a frame or two, so if nothing has trapped a few
/// seconds later the backend counts as working. A timer rather than a
/// frame count: egui draws only on change, so an idle board makes no frames.
pub fn frame_drawn() {
    use std::sync::atomic::{AtomicBool, Ordering};
    use wasm_bindgen::JsCast as _;
    static ARMED: AtomicBool = AtomicBool::new(false);
    if ARMED.swap(true, Ordering::Relaxed) {
        return;
    }
    let cb = wasm_bindgen::closure::Closure::once_into_js(mark_running);
    if let Some(w) = web_sys::window() {
        let _ = w.set_timeout_with_callback_and_timeout_and_arguments_0(cb.unchecked_ref(), 3000);
    }
}

fn mark_running() {
    if let Some(s) = session() {
        let _ = s.remove_item(PENDING_KEY);
    }
}

/// eframe's web options for `backend`.
///
/// Limits: the board needs no more than WebGL 2 gives (16 sampled
/// textures per stage, small uniforms), so it asks for WebGL 2's limits on
/// both backends, which every WebGPU adapter meets. egui's own default asks
/// for 8192² textures, which many Android GPUs (4096²) refuse, so the
/// texture size is the adapter's, capped at 8192.
pub fn web_options(backend: Backend) -> eframe::WebOptions {
    let mut options = eframe::WebOptions::default();
    if let egui_wgpu::WgpuSetup::CreateNew(create) = &mut options.wgpu_options.wgpu_setup {
        create.instance_descriptor.backends = match backend {
            Backend::WebGpu => wgpu::Backends::BROWSER_WEBGPU,
            Backend::WebGl => wgpu::Backends::GL,
        };
        create.device_descriptor = Arc::new(|adapter| {
            let have = adapter.limits();
            let info = adapter.get_info();
            log::info!("GPU: {} ({:?}), max texture {}", info.name, info.backend, have.max_texture_dimension_2d);
            wgpu::DeviceDescriptor {
                label: Some("neolith device"),
                required_limits: wgpu::Limits {
                    max_texture_dimension_2d: have.max_texture_dimension_2d.min(8192),
                    ..wgpu::Limits::downlevel_webgl2_defaults()
                },
                ..Default::default()
            }
        });
    }
    options
}

/// Swap `canvas` for a fresh copy: a canvas that has handed out a
/// `webgpu` context cannot give a `webgl2` one.
pub fn fresh_canvas(canvas: &web_sys::HtmlCanvasElement) -> Option<web_sys::HtmlCanvasElement> {
    use wasm_bindgen::JsCast as _;
    let fresh = canvas.clone_node().ok()?.dyn_into::<web_sys::HtmlCanvasElement>().ok()?;
    canvas.replace_with_with_node_1(&fresh).ok()?;
    Some(fresh)
}
