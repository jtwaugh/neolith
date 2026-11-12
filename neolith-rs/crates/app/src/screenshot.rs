//! Headless rendering of the board to a PNG (native only):
//! `neolith --screenshot out.png [--year -7000] [--mode koeppen|elevation] [--flat 1] …`.
//! Used to check and compare the board look without opening a window.

use crate::board::camera::Camera;
use crate::board::projection::Projection;
use crate::board::lines;
use crate::board::renderer::{BoardRenderer, LineMesh, COLOUR_FORMAT};
use crate::board::scene::{self, ArtMode, BoardStyle, Material, Piece};
use crate::board::mesh;
use eframe::wgpu;
use glam::DVec2;
use neolith_core::{MapMode, World, Year};

pub struct Options {
    pub out: String,
    pub year: Year,
    pub mode: MapMode,
    pub flat: f64,
    pub size: [u32; 2],
    pub yaw: Option<f64>,
    pub pitch: Option<f64>,
    pub dist: Option<f64>,
    pub lon: Option<f64>,
    pub lat: Option<f64>,
    pub lip: bool,
    pub material: Material,
    pub art: ArtMode,
    /// Blend biome edges and draw shores.
    pub blend: bool,
    pub hillshade: Option<f64>,
    /// Relief exaggeration; 0 turns the relief off.
    pub relief: Option<f64>,
    /// The evidence layer (id) for `--mode evidence`; the first if `None`.
    pub evidence: Option<String>,
}

pub fn run(world: &World, opt: &Options) -> Result<(), String> {
    let instance = wgpu::Instance::default();
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default()))
        .map_err(|e| format!("no GPU adapter: {e}"))?;
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default()))
        .map_err(|e| format!("cannot open the GPU device: {e}"))?;

    let grid = &world.grid;
    let proj = Projection::new(grid.centre_of_bounds());
    let board = mesh::build(grid, &proj);
    let mut renderer = BoardRenderer::new(&device, &queue, COLOUR_FORMAT, &board, grid.cols as u32, grid.rows as u32);

    let snapshot = world.snapshot(opt.year);
    let shade = neolith_core::elevation::hillshade(grid, &world.elevation, neolith_core::elevation::HILLSHADE_EXAGGERATION);
    renderer.upload_state(&queue, &scene::state_texels(grid, &snapshot, &shade, &world.landform, &world.survey, None, None, None));
    if opt.mode == MapMode::Evidence {
        let layer = match &opt.evidence {
            Some(id) => world.evidence_layer(id).ok_or(format!("no evidence layer {id:?}"))?,
            None => world.evidence.first().ok_or("this world has no evidence layers")?,
        };
        renderer.upload_evidence(&queue, &scene::evidence_texels(grid, layer.codes_at(opt.year)));
    }

    let mut cam = Camera::initial(grid);
    if let Some(v) = opt.yaw {
        cam.yaw = v.to_radians();
    }
    if let Some(v) = opt.pitch {
        cam.pitch = v.to_radians();
        cam.pitch_pref = cam.pitch;
    }
    if let Some(v) = opt.dist {
        cam.dist = v;
    }
    if let Some(v) = opt.lon {
        cam.target.lon = v;
    }
    if let Some(v) = opt.lat {
        cam.target.lat = v;
    }
    cam.clamp(grid);
    let view = cam.view(&proj, opt.flat, DVec2::new(opt.size[0] as f64, opt.size[1] as f64));

    let style = BoardStyle { frame_lip: opt.lip, material: opt.material, terrain_art: opt.art, art_blend: opt.blend, ..Default::default() };
    let style = BoardStyle { hillshade: opt.hillshade.map_or(style.hillshade, |h| h as f32), ..style };
    let style = match opt.relief {
        Some(x) => BoardStyle { relief: x > 0.0, relief_exaggeration: x as f32, ..style },
        None => style,
    };

    let pieces: Vec<Piece> = world
        .settlements
        .iter()
        .filter(|s| s.exists_at(opt.year))
        .map(|s| Piece::new(s, opt.year))
        .collect();
    let relief = crate::board::relief::Relief::new(grid, &snapshot.height, crate::board::relief::scale(&style));
    let verts = scene::piece_vertices(&pieces, &proj, &relief, opt.flat, cam.dist);
    renderer.upload_pieces(&device, &queue, &verts);
    let mut line_mesh = LineMesh::default();
    let line_board = lines::Board { proj: &proj, relief: &relief, t: opt.flat, cam_dist: cam.dist };
    lines::rivers(&mut line_mesh, &world.rivers, &world.lakes, &snapshot, &line_board);
    lines::lakes(&mut line_mesh, &world.lakes, opt.year, &line_board);
    renderer.upload_lines(&device, &queue, &line_mesh);
    renderer.upload_river_field(&queue, &lines::river_field(&world.rivers, &lines::flowing(&world.rivers, opt.year), grid));

    let globals = scene::globals(&view, &style, opt.mode, grid, &board, opt.size[1] as f32);

    // NEOLITH_BENCH=<frames>: time the board pass (GPU throughput, after a
    // warm-up frame) and print it before writing the screenshot.
    if let Some(frames) = std::env::var("NEOLITH_BENCH").ok().and_then(|v| v.parse::<u32>().ok()).filter(|n| *n > 0) {
        let wait = || device.poll(wgpu::PollType::Wait { submission_index: None, timeout: None }).map(|_| ());
        let frame = |renderer: &mut BoardRenderer| {
            let mut encoder = device.create_command_encoder(&Default::default());
            renderer.render(&device, &queue, &mut encoder, opt.size, &globals);
            queue.submit([encoder.finish()]);
        };
        frame(&mut renderer);
        wait().map_err(|e| format!("GPU poll failed: {e}"))?;
        let start = std::time::Instant::now();
        for _ in 0..frames {
            frame(&mut renderer);
        }
        wait().map_err(|e| format!("GPU poll failed: {e}"))?;
        let ms = start.elapsed().as_secs_f64() * 1000.0 / frames as f64;
        println!("bench: {ms:.2} ms/frame over {frames} frames at {}x{}", opt.size[0], opt.size[1]);
    }

    let mut encoder = device.create_command_encoder(&Default::default());
    renderer.render(&device, &queue, &mut encoder, opt.size, &globals);

    // Read the resolved colour target back.
    let (texture, [w, h]) = renderer.colour_texture().unwrap();
    let row = (w * 4).next_multiple_of(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT);
    let buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("screenshot"),
        size: (row * h) as u64,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    encoder.copy_texture_to_buffer(
        texture.as_image_copy(),
        wgpu::TexelCopyBufferInfo {
            buffer: &buffer,
            layout: wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(row), rows_per_image: Some(h) },
        },
        wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
    );
    queue.submit([encoder.finish()]);
    buffer.map_async(wgpu::MapMode::Read, .., |r| r.expect("map screenshot buffer"));
    device
        .poll(wgpu::PollType::Wait { submission_index: None, timeout: None })
        .map_err(|e| format!("GPU poll failed: {e}"))?;
    let data = buffer.get_mapped_range(..).map_err(|e| format!("cannot read back: {e}"))?;
    let mut pixels = Vec::with_capacity((w * h * 4) as usize);
    for y in 0..h {
        let start = (y * row) as usize;
        pixels.extend_from_slice(&data[start..start + (w * 4) as usize]);
    }
    image::save_buffer(&opt.out, &pixels, w, h, image::ColorType::Rgba8)
        .map_err(|e| format!("cannot write {}: {e}", opt.out))?;
    Ok(())
}
