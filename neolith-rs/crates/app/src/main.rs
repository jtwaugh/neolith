//! Neolith: the map, clock and editor. One codebase for native and web.

mod app;
mod board;
mod clock;
mod credits;
mod events;
mod files;
mod labels;
#[cfg(not(target_arch = "wasm32"))]
mod harness;
mod palette;
mod panels;
mod perf;
mod renown;
#[cfg(not(target_arch = "wasm32"))]
mod screenshot;
mod site_record;
mod view;

#[cfg(not(target_arch = "wasm32"))]
const USAGE: &str = "\
neolith [world.bin]
neolith --screenshot <out.png> [--world <world.bin>] [--year <y>] [--mode terrain|koeppen|pop|elevation|evidence]
        [--evidence <layer id>]
        [--flat <0..1>] [--yaw <deg>] [--pitch <deg>] [--dist <d>] [--lon <deg>] [--lat <deg>]
        [--size <W>x<H>] [--lip] [--art on|off] [--no-blend] [--material wood|slate|cardboard]
        [--hillshade <0..1>] [--relief <exaggeration, 0 = off>]
neolith --ui-screenshot <out.png> [--editor] [--flat 1] [--mode …] [--year <y>]   (opens the window briefly)
neolith --harness [<port>] [--world <world.bin>] [--size <W>x<H>]
        agent control server on 127.0.0.1 (default port 7878, 0 = any); see harness/README.md
";

#[cfg(not(target_arch = "wasm32"))]
fn main() -> std::process::ExitCode {
    use std::process::ExitCode;
    perf::init();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("warn")).init();
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        print!("{USAGE}");
        return ExitCode::SUCCESS;
    }
    if args.iter().any(|a| a == "--screenshot") {
        return match screenshot_cli(&args) {
            Ok(()) => ExitCode::SUCCESS,
            Err(e) => {
                eprintln!("error: {e}");
                ExitCode::FAILURE
            }
        };
    }
    let value_of = |k: &str| args.iter().position(|a| a == k).and_then(|i| args.get(i + 1)).cloned();
    let auto_shot = value_of("--ui-screenshot").map(|path| app::AutoShot {
        path,
        editor: args.iter().any(|a| a == "--editor"),
        flat: value_of("--flat").is_some_and(|v| v != "0"),
        mode: match value_of("--mode").as_deref() {
            Some(m) => neolith_core::MapMode::from_arg(m).unwrap_or(neolith_core::MapMode::Terrain),
            None => neolith_core::MapMode::Terrain,
        },
        year: value_of("--year").and_then(|v| v.parse().ok()),
        frames: 0,
    });
    let harness_port = args.iter().position(|a| a == "--harness").map(|i| {
        args.get(i + 1).and_then(|p| p.parse::<u16>().ok()).unwrap_or(7878)
    });
    let world_path = if auto_shot.is_some() || harness_port.is_some() {
        value_of("--world")
    } else {
        args.iter().find(|a| !a.starts_with('-')).cloned()
    };
    let size = value_of("--size")
        .and_then(|s| s.split_once('x').and_then(|(w, h)| Some([w.parse::<f32>().ok()?, h.parse::<f32>().ok()?])))
        .unwrap_or([1360.0, 860.0]);
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Neolith")
            .with_inner_size(size)
            .with_min_inner_size([360.0, 480.0]),
        renderer: eframe::Renderer::Wgpu,
        // Under the harness the window is usually behind the agent's terminal;
        // waiting on vsync for an occluded window stalls every frame on macOS.
        wgpu_options: egui_wgpu::WgpuConfiguration {
            surface: egui_wgpu::SurfaceConfig {
                present_mode: if harness_port.is_some() {
                    eframe::wgpu::PresentMode::AutoNoVsync
                } else {
                    eframe::wgpu::PresentMode::AutoVsync
                },
                ..egui_wgpu::WgpuConfiguration::default().surface
            },
            ..Default::default()
        },
        ..Default::default()
    };
    let result = eframe::run_native(
        "Neolith",
        options,
        Box::new(move |cc| {
            let mut app = app::NeolithApp::new(cc, world_path);
            app.auto_shot = auto_shot;
            if let Some(port) = harness_port {
                app.harness = Some(harness::Harness::start(&cc.egui_ctx, port)?);
            }
            Ok(Box::new(app))
        }),
    );
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn screenshot_cli(args: &[String]) -> Result<(), String> {
    use board::scene::{ArtMode, Material};
    use neolith_core::{MapMode, Year};
    let get = |k: &str| args.iter().position(|a| a == k).and_then(|i| args.get(i + 1)).cloned();
    let num = |k: &str| -> Result<Option<f64>, String> {
        get(k).map(|v| v.parse::<f64>().map_err(|_| format!("{k}: {v:?} is not a number"))).transpose()
    };
    let path = get("--world").unwrap_or_else(|| "assets/world.bin".to_string());
    let bytes = std::fs::read(&path).map_err(|e| format!("cannot read {path}: {e}"))?;
    let world = neolith_core::io::decode(&bytes).map_err(|e| format!("{path}: {e}"))?;
    let size = match get("--size") {
        Some(s) => {
            let (w, h) = s.split_once('x').ok_or("--size wants <W>x<H>")?;
            [w.parse().map_err(|_| "--size wants <W>x<H>")?, h.parse().map_err(|_| "--size wants <W>x<H>")?]
        }
        None => [1280, 800],
    };
    let opt = screenshot::Options {
        out: get("--screenshot").ok_or("--screenshot needs an output path")?,
        year: Year(num("--year")?.unwrap_or(app::DEFAULT_START_YEAR as f64) as i32),
        mode: match get("--mode").as_deref() {
            None => MapMode::Terrain,
            Some(m) => MapMode::from_arg(m).ok_or(format!("unknown --mode {m}"))?,
        },
        flat: num("--flat")?.unwrap_or(0.0).clamp(0.0, 1.0),
        size,
        yaw: num("--yaw")?,
        pitch: num("--pitch")?,
        dist: num("--dist")?,
        lon: num("--lon")?,
        lat: num("--lat")?,
        lip: args.iter().any(|a| a == "--lip"),
        material: match get("--material").as_deref() {
            None | Some("wood") => Material::Wood,
            Some("slate") => Material::Slate,
            Some("cardboard") => Material::Cardboard,
            Some(other) => return Err(format!("unknown --material {other}")),
        },
        art: match get("--art").as_deref() {
            None | Some("on") | Some("3d") => ArtMode::On,
            Some("off") => ArtMode::Off,
            Some(other) => return Err(format!("unknown --art {other}")),
        },
        blend: !args.iter().any(|a| a == "--no-blend"),
        hillshade: num("--hillshade")?,
        relief: num("--relief")?,
        evidence: get("--evidence"),
    };
    screenshot::run(&world, &opt)?;
    println!("wrote {}", opt.out);
    Ok(())
}

#[cfg(target_arch = "wasm32")]
fn main() {
    use wasm_bindgen::JsCast as _;
    eframe::WebLogger::init(log::LevelFilter::Info).ok();
    perf::init();
    wasm_bindgen_futures::spawn_local(async {
        let canvas = web_sys::window()
            .and_then(|w| w.document())
            .and_then(|d| d.get_element_by_id("neolith_canvas"))
            .and_then(|e| e.dyn_into::<web_sys::HtmlCanvasElement>().ok())
            .expect("index.html must contain <canvas id=\"neolith_canvas\">");
        let result = eframe::WebRunner::new()
            .start(canvas, eframe::WebOptions::default(), Box::new(|cc| Ok(Box::new(app::NeolithApp::new(cc, None)))))
            .await;
        // Clear the page's "Loading…" placeholder, or turn it into the error.
        let loading = web_sys::window().and_then(|w| w.document()).and_then(|d| d.get_element_by_id("loading"));
        match result {
            Ok(()) => {
                if let Some(el) = loading {
                    el.remove();
                }
            }
            Err(e) => {
                log::error!("failed to start: {e:?}");
                if let Some(el) = loading {
                    el.set_class_name("error");
                    el.set_text_content(Some(
                        "Neolith could not start. It needs a browser with WebGPU or WebGL 2; see the console for details.",
                    ));
                }
            }
        }
    });
}
