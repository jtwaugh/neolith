//! The wgpu side of the board: one pipeline for the board mesh plus small
//! ones for the studio background, the contact shadow and the settlement
//! pieces, all drawn into an offscreen multisampled colour + depth target.
//! A blit pipeline then shows the resolved image inside the egui panel.

use super::mesh::{self, BoardMesh, HexInstance, HexVertex, PropVertex};
use crate::palette;
use bytemuck::{Pod, Zeroable};
use eframe::wgpu;
use eframe::wgpu::util::DeviceExt as _;
use neolith_core::Terrain;

pub const COLOUR_FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8UnormSrgb;
const DEPTH_FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Depth32Float;
/// The baked prop layout and glyph lists (terrain_art.wgsl, fs_slot_bake)
/// and per-hex art data (fs_hex_bake): integer texels
/// are colour-renderable in WebGL2 too, unlike float ones.
const PROP_TEX_FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba32Uint;
/// Prop slots per hex in prop_tex, across and down; must match art_prop_texel.
const PROP_TEX_SLOTS: [u32; 2] = [4, 3];
const _: () = assert!(PROP_TEX_SLOTS[0] * PROP_TEX_SLOTS[1] == mesh::PROP_SLOTS as u32);
const SAMPLES: u32 = 4;

/// Terrain art detail: between these hex radii on screen (pixels) the extra
/// glyph slots sprout and the rest shrink to make room.
pub const ART_DETAIL_PX: [f32; 2] = [24.0, 44.0];

/// Picks the hexes whose 3D props can show with globals `g` into `out`,
/// those that need the detail slots first; returns how many those are.
///
/// `vs_prop` drops a prop's vertices off screen when the hex is water or
/// too small on screen, but only after running them, for every hex × up to
/// 360 template vertices. These are the same tests, once per hex on the CPU:
/// - water and unset hexes have no props;
/// - at or below 5 px per hex unit the props have shrunk to nothing (`lod`
///   is smoothstep(5, 11, hex_px));
/// - hexes outside the view frustum (with room for relief and prop height);
/// - the detail slots sprout above `ART_DETAIL_PX[0]`, so only hexes past
///   that get the whole template.
pub fn select_props(all: &[HexInstance], state_rgba: &[u8], cols: usize, g: &Globals, out: &mut Vec<HexInstance>) -> u32 {
    use glam::{Mat4, Vec3, Vec4};
    let water = Terrain::ALL.iter().position(|t| *t == Terrain::Water).unwrap_or(usize::MAX);
    let view_proj = Mat4::from_cols_array(&g.view_proj);
    let rows = [view_proj.row(0), view_proj.row(1), view_proj.row(2), view_proj.row(3)];
    // Left, right, bottom, top and near (wgpu's 0..1 depth) planes, normalised.
    let planes = [rows[3] + rows[0], rows[3] - rows[0], rows[3] + rows[1], rows[3] - rows[1], rows[2]]
        .map(|p| p / p.truncate().length().max(1e-12));
    let eye = Vec3::new(g.cam_pos[0], g.cam_pos[1], g.cam_pos[2]);
    let t = g.cam_pos[3];
    let sqrt3_2 = 3f32.sqrt() / 2.0;
    let unit_f = g.hex[1] / sqrt3_2;
    // The highest tile (Everest-ish) in board units, for the frustum margin.
    let max_lift = g.hex[2] * 9000.0;
    out.clear();
    let mut base = Vec::new();
    for inst in all {
        let [c, r] = inst.cell.map(usize::from);
        let terrain = state_rgba.get((r * cols + c) * 4).copied().map_or(usize::MAX, usize::from);
        if terrain >= Terrain::ALL.len() || terrain == water {
            continue;
        }
        let centre = Vec3::from_array(inst.centre).lerp(Vec3::new(inst.flat[0], 1.0, -inst.flat[1]), t);
        let unit_c = Vec3::from_array(inst.north).length() / sqrt3_2;
        let unit = unit_c + (unit_f - unit_c) * t;
        let hex_px = unit * g.art[2] / eye.distance(centre).max(1e-6);
        if hex_px <= 5.0 {
            continue;
        }
        let radius = unit * 4.0 + max_lift;
        let p = Vec4::from((centre, 1.0));
        if planes.iter().any(|pl| pl.dot(p) < -radius) {
            continue;
        }
        if hex_px > ART_DETAIL_PX[0] {
            out.push(*inst);
        } else {
            base.push(*inst);
        }
    }
    let detail = out.len() as u32;
    out.extend_from_slice(&base);
    detail
}

/// The whole shader module: the `T_*` terrain constants (generated from the
/// enum, so the shader cannot drift from it), the terrain art, then the board.
pub fn shader_source() -> String {
    let mut src = String::new();
    for (i, t) in Terrain::ALL.iter().enumerate() {
        let mut name = String::new();
        for ch in format!("{t:?}").chars() {
            if ch.is_uppercase() && !name.is_empty() {
                name.push('_');
            }
            name.push(ch.to_ascii_uppercase());
        }
        src.push_str(&format!("const T_{name}: u32 = {i}u;\n"));
    }
    src.push_str(&format!("const T_COUNT: u32 = {}u;\n", Terrain::ALL.len()));
    src.push_str(&format!(
        "const ART_SLOTS: u32 = {}u;\nconst ART_BASE_SLOTS: u32 = {}u;\nconst ART_DETAIL_LO: f32 = {:?};\nconst ART_DETAIL_HI: f32 = {:?};\n",
        mesh::PROP_SLOTS,
        mesh::PROP_BASE_SLOTS,
        ART_DETAIL_PX[0],
        ART_DETAIL_PX[1],
    ));
    src.push_str(&format!(
        "const RIVER_REACH: f32 = {:?};\nconst RIVER_HALF_MAX: f32 = {:?};\nconst RIVER_BED: f32 = {:?};\n",
        super::lines::FIELD_REACH,
        super::lines::FIELD_HALF_MAX,
        super::lines::BED_SHARE,
    ));
    src.push_str(include_str!("terrain_art.wgsl"));
    src.push_str(include_str!("board.wgsl"));
    src
}

/// The uniform block; must match `Globals` in board.wgsl.
#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
pub struct Globals {
    pub view_proj: [f32; 16],
    pub cam_pos: [f32; 4],
    pub grid: [f32; 4],
    pub key_light: [f32; 4],
    pub fill_light: [f32; 4],
    pub tile: [f32; 4],
    pub lines: [f32; 4],
    pub wall_colour: [f32; 4],
    pub frame_colour: [f32; 4],
    pub bg_top: [f32; 4],
    pub bg_bottom: [f32; 4],
    pub shadow: [f32; 4],
    pub art: [f32; 4],
    pub hex: [f32; 4],
}

/// A vertex of a settlement piece, already in world space.
#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
pub struct PieceVertex {
    pub pos: [f32; 3],
    pub normal: [f32; 3],
    pub colour: [f32; 4],
}

/// A vertex of a line overlay (river, channel belt, lake shore), in world
/// space. The fragment shader shapes the ribbon from `uv`.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Pod, Zeroable)]
pub struct LineVertex {
    pub pos: [f32; 3],
    /// x: across the ribbon (-1 left edge .. 1 right edge); y: 0 along the
    /// body, 0..1 out through a round cap.
    pub uv: [f32; 2],
    /// Distance along the line, in dash periods.
    pub along: f32,
    /// sRGB colour and opacity.
    pub colour: [u8; 4],
    /// x: dash "on" fraction (0 = solid), z: edge feather (fraction of
    /// the half width); y and w unused.
    pub params: [u8; 4],
}

/// Indexed triangles of the line overlays, in draw order.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct LineMesh {
    pub vertices: Vec<LineVertex>,
    pub indices: Vec<u32>,
}

struct Targets {
    size: [u32; 2],
    msaa_view: wgpu::TextureView,
    depth_view: wgpu::TextureView,
    resolve: wgpu::Texture,
    resolve_view: wgpu::TextureView,
    blit_bind_group: wgpu::BindGroup,
}

pub struct BoardRenderer {
    board_pipeline: wgpu::RenderPipeline,
    background_pipeline: wgpu::RenderPipeline,
    shadow_pipeline: wgpu::RenderPipeline,
    piece_pipeline: wgpu::RenderPipeline,
    line_pipeline: wgpu::RenderPipeline,
    prop_pipeline: wgpu::RenderPipeline,
    prop_vertices: wgpu::Buffer,
    prop_indices: wgpu::Buffer,
    /// The props drawn this frame (see [`Self::cull_props`]): the hexes
    /// that need the detail slots first, then the base-only ones.
    prop_instances: wgpu::Buffer,
    prop_instance_count: u32,
    prop_detail_count: u32,
    /// Every hex's instance, the source `cull_props` picks from.
    prop_all: Vec<HexInstance>,
    prop_tex_view: wgpu::TextureView,
    art_tex_view: wgpu::TextureView,
    hex_tex_view: wgpu::TextureView,
    slot_bake_pipeline: wgpu::RenderPipeline,
    hex_bake_pipeline: wgpu::RenderPipeline,
    bake_bind_group: wgpu::BindGroup,
    /// The edge-blend value the art textures were baked with; `None` when the hex
    /// state changed since (see [`Self::bake_props`]).
    art_baked_blend: Option<f32>,
    prop_scratch: Vec<HexInstance>,
    blit_pipeline: wgpu::RenderPipeline,
    blit_layout: wgpu::BindGroupLayout,
    blit_params: wgpu::Buffer,
    sampler: wgpu::Sampler,
    globals: wgpu::Buffer,
    bind_group: wgpu::BindGroup,
    vertices: wgpu::Buffer,
    indices: wgpu::Buffer,
    index_count: u32,
    state_tex: wgpu::Texture,
    elevation_tex: wgpu::Texture,
    height_tex: wgpu::Texture,
    /// R8: the selected evidence layer's codes (see [`Self::upload_evidence`]).
    evidence_tex: wgpu::Texture,
    /// RGBA8: where the river channels are (see [`Self::upload_river_field`]).
    river_tex: wgpu::Texture,
    /// The field last uploaded, so an unchanged one isn't re-sent.
    river_field: Option<super::lines::RiverField>,
    state_size: [u32; 2],
    /// CPU copy of `state_tex` (RGBA8), for single-texel flag updates.
    state_rgba: Vec<u8>,
    pieces: wgpu::Buffer,
    piece_capacity: usize,
    piece_count: u32,
    /// The piece vertices last uploaded, so an unchanged set isn't re-sent.
    piece_data: Vec<PieceVertex>,
    line_vertices: wgpu::Buffer,
    line_indices: wgpu::Buffer,
    line_capacity: [usize; 2],
    line_count: u32,
    /// The line mesh last uploaded, so an unchanged one isn't re-sent.
    line_data: LineMesh,
    targets: Option<Targets>,
    /// The globals the offscreen target was last rendered with, or `None`
    /// when an upload (state, pieces) has made it stale. `render` skips the
    /// pass while this still matches, and egui just blits the old image:
    /// most repaints are for the panels and leave the board unchanged.
    rendered: Option<Globals>,
}

impl BoardRenderer {
    /// `target_format` is the format the blit draws into (egui's surface).
    pub fn new(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        target_format: wgpu::TextureFormat,
        mesh: &BoardMesh,
        cols: u32,
        rows: u32,
    ) -> Self {
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("board shader"),
            source: wgpu::ShaderSource::Wgsl(shader_source().into()),
        });

        let globals = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("board globals"),
            size: std::mem::size_of::<Globals>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let tex_desc = |label, width, height, format| wgpu::TextureDescriptor {
            label: Some(label),
            size: wgpu::Extent3d { width, height, depth_or_array_layers: 1 },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        };
        let state_tex = device.create_texture(&tex_desc("hex state", cols, rows, wgpu::TextureFormat::Rgba8Uint));
        let elevation_tex = device.create_texture(&tex_desc("hex relief", cols, rows, wgpu::TextureFormat::Rgba8Uint));
        let height_tex = device.create_texture(&tex_desc("hex height", cols, rows, wgpu::TextureFormat::R16Sint));
        let evidence_tex = device.create_texture(&tex_desc("hex evidence", cols, rows, wgpu::TextureFormat::R8Uint));
        // No layer until one is uploaded.
        queue.write_texture(
            evidence_tex.as_image_copy(),
            &vec![neolith_core::evidence::NO_VALUE; (cols * rows) as usize],
            wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(cols), rows_per_image: Some(rows) },
            wgpu::Extent3d { width: cols, height: rows, depth_or_array_layers: 1 },
        );
        let [river_w, river_h] = super::lines::field_size(cols, rows).0;
        let river_tex = device.create_texture(&tex_desc("river field", river_w, river_h, wgpu::TextureFormat::Rgba8Unorm));
        let river_view = river_tex.create_view(&Default::default());
        // The baked prop layout and glyph lists (fs_slot_bake): 4 × 3 slots
        // per hex; the per-hex art data (fs_hex_bake).
        let prop_tex = device.create_texture(&wgpu::TextureDescriptor {
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::RENDER_ATTACHMENT,
            ..tex_desc("prop layout", cols * PROP_TEX_SLOTS[0], rows * PROP_TEX_SLOTS[1], PROP_TEX_FORMAT)
        });
        let prop_tex_view = prop_tex.create_view(&Default::default());
        let art_tex = device.create_texture(&wgpu::TextureDescriptor {
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::RENDER_ATTACHMENT,
            ..tex_desc("glyph lists", cols * PROP_TEX_SLOTS[0], rows * PROP_TEX_SLOTS[1], PROP_TEX_FORMAT)
        });
        let art_tex_view = art_tex.create_view(&Default::default());
        let hex_tex = device.create_texture(&wgpu::TextureDescriptor {
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::RENDER_ATTACHMENT,
            ..tex_desc("hex art data", cols, rows, PROP_TEX_FORMAT)
        });
        let hex_tex_view = hex_tex.create_view(&Default::default());
        let palette_tex = device.create_texture_with_data(
            queue,
            &tex_desc(
                "palette",
                palette::PALETTE_WIDTH as u32,
                palette::PALETTE_ROWS as u32,
                wgpu::TextureFormat::Rgba8UnormSrgb,
            ),
            wgpu::util::TextureDataOrder::LayerMajor,
            &palette::palette_texture(),
        );

        let tex_entry = |binding, sample_type| wgpu::BindGroupLayoutEntry {
            binding,
            // The prop vertex shader reads the hex state and palette too.
            visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
            ty: wgpu::BindingType::Texture {
                sample_type,
                view_dimension: wgpu::TextureViewDimension::D2,
                multisampled: false,
            },
            count: None,
        };
        let uniform_entry = |binding, visibility| wgpu::BindGroupLayoutEntry {
            binding,
            visibility,
            ty: wgpu::BindingType::Buffer {
                ty: wgpu::BufferBindingType::Uniform,
                has_dynamic_offset: false,
                min_binding_size: None,
            },
            count: None,
        };
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("board layout"),
            entries: &[
                uniform_entry(0, wgpu::ShaderStages::VERTEX_FRAGMENT),
                tex_entry(1, wgpu::TextureSampleType::Uint),
                tex_entry(2, wgpu::TextureSampleType::Float { filterable: true }),
                tex_entry(3, wgpu::TextureSampleType::Uint),
                tex_entry(4, wgpu::TextureSampleType::Sint),
                tex_entry(5, wgpu::TextureSampleType::Uint),
                tex_entry(6, wgpu::TextureSampleType::Uint),
                tex_entry(7, wgpu::TextureSampleType::Uint),
                tex_entry(8, wgpu::TextureSampleType::Uint),
                tex_entry(9, wgpu::TextureSampleType::Float { filterable: true }),
            ],
        });
        let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("board bind group"),
            layout: &layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: globals.as_entire_binding() },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(&state_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::TextureView(&palette_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry {
                    binding: 3,
                    resource: wgpu::BindingResource::TextureView(&elevation_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry {
                    binding: 4,
                    resource: wgpu::BindingResource::TextureView(&height_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry { binding: 5, resource: wgpu::BindingResource::TextureView(&prop_tex_view) },
                wgpu::BindGroupEntry { binding: 6, resource: wgpu::BindingResource::TextureView(&art_tex_view) },
                wgpu::BindGroupEntry { binding: 7, resource: wgpu::BindingResource::TextureView(&hex_tex_view) },
                wgpu::BindGroupEntry {
                    binding: 8,
                    resource: wgpu::BindingResource::TextureView(&evidence_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry { binding: 9, resource: wgpu::BindingResource::TextureView(&river_view) },
            ],
        });
        // The bakes render into the art textures, so can't have them bound: their own
        // layout with just what they read (globals, hex state, river field).
        let bake_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("prop bake layout"),
            entries: &[
                uniform_entry(0, wgpu::ShaderStages::VERTEX_FRAGMENT),
                tex_entry(1, wgpu::TextureSampleType::Uint),
                tex_entry(9, wgpu::TextureSampleType::Float { filterable: true }),
            ],
        });
        let bake_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("prop bake bind group"),
            layout: &bake_layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: globals.as_entire_binding() },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(&state_tex.create_view(&Default::default())),
                },
                wgpu::BindGroupEntry { binding: 9, resource: wgpu::BindingResource::TextureView(&river_view) },
            ],
        });
        let bake_pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("prop bake pipeline layout"),
            bind_group_layouts: &[Some(&bake_layout)],
            immediate_size: 0,
        });
        let bake_pipeline = |label: &str, fs: &str, outputs: usize| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some(label),
                layout: Some(&bake_pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &shader,
                    entry_point: Some("vs_fullscreen"),
                    compilation_options: Default::default(),
                    buffers: &[],
                },
                primitive: Default::default(),
                depth_stencil: None,
                multisample: Default::default(),
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: Some(fs),
                    compilation_options: Default::default(),
                    targets: &vec![
                        Some(wgpu::ColorTargetState { format: PROP_TEX_FORMAT, blend: None, write_mask: wgpu::ColorWrites::ALL });
                        outputs
                    ],
                }),
                multiview_mask: None,
                cache: None,
            })
        };
        let slot_bake_pipeline = bake_pipeline("slot bake", "fs_slot_bake", 2);
        let hex_bake_pipeline = bake_pipeline("hex art bake", "fs_hex_bake", 1);
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("board pipeline layout"),
            bind_group_layouts: &[Some(&layout)],
            immediate_size: 0,
        });

        let depth = |write: bool, compare| {
            Some(wgpu::DepthStencilState {
                format: DEPTH_FORMAT,
                depth_write_enabled: Some(write),
                depth_compare: Some(compare),
                stencil: Default::default(),
                bias: Default::default(),
            })
        };
        let multisample = wgpu::MultisampleState { count: SAMPLES, ..Default::default() };
        let pipeline = |label: &str,
                        vs: &str,
                        fs: &str,
                        buffers: &[Option<wgpu::VertexBufferLayout<'_>>],
                        cull: Option<wgpu::Face>,
                        depth_stencil: Option<wgpu::DepthStencilState>,
                        blend: Option<wgpu::BlendState>,
                        alpha_to_coverage: bool| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some(label),
                layout: Some(&pipeline_layout),
                vertex: wgpu::VertexState {
                    module: &shader,
                    entry_point: Some(vs),
                    compilation_options: Default::default(),
                    buffers,
                },
                primitive: wgpu::PrimitiveState { cull_mode: cull, ..Default::default() },
                depth_stencil,
                multisample: wgpu::MultisampleState { alpha_to_coverage_enabled: alpha_to_coverage, ..multisample },
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: Some(fs),
                    compilation_options: Default::default(),
                    targets: &[Some(wgpu::ColorTargetState {
                        format: COLOUR_FORMAT,
                        blend,
                        // Coverage alpha is not colour: the target stays opaque.
                        write_mask: if alpha_to_coverage { wgpu::ColorWrites::COLOR } else { wgpu::ColorWrites::ALL },
                    })],
                }),
                multiview_mask: None,
                cache: None,
            })
        };

        let board_attrs = wgpu::vertex_attr_array![0 => Float32x3, 1 => Float32x2, 2 => Uint16x2, 3 => Uint8x4];
        let board_buffers = [Some(wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<HexVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &board_attrs,
        })];
        let piece_attrs = wgpu::vertex_attr_array![0 => Float32x3, 1 => Float32x3, 2 => Float32x4];
        let piece_buffers = [Some(wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<PieceVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &piece_attrs,
        })];
        use wgpu::CompareFunction::{Always, Less};
        let board_pipeline =
            pipeline("board", "vs_board", "fs_board", &board_buffers, Some(wgpu::Face::Back), depth(true, Less), None, false);
        let background_pipeline =
            pipeline("background", "vs_fullscreen", "fs_background", &[], None, depth(false, Always), None, false);
        let shadow_pipeline = pipeline(
            "contact shadow",
            "vs_shadow",
            "fs_shadow",
            &[],
            None,
            depth(false, Less),
            Some(wgpu::BlendState::ALPHA_BLENDING),
            false,
        );
        let template_attrs = wgpu::vertex_attr_array![0 => Uint8x4];
        let instance_attrs =
            wgpu::vertex_attr_array![1 => Float32x3, 2 => Float32x3, 3 => Float32x3, 4 => Float32x2, 5 => Uint16x2];
        let prop_buffers = [
            Some(wgpu::VertexBufferLayout {
                array_stride: std::mem::size_of::<PropVertex>() as u64,
                step_mode: wgpu::VertexStepMode::Vertex,
                attributes: &template_attrs,
            }),
            Some(wgpu::VertexBufferLayout {
                array_stride: std::mem::size_of::<HexInstance>() as u64,
                step_mode: wgpu::VertexStepMode::Instance,
                attributes: &instance_attrs,
            }),
        ];
        let prop_pipeline = pipeline("terrain props", "vs_prop", "fs_prop", &prop_buffers, None, depth(true, Less), None, false);
        // Pieces turn opacity into MSAA coverage, so campfire smoke is
        // see-through without sorting and still depth-tested like the rest.
        let piece_pipeline = pipeline("pieces", "vs_piece", "fs_piece", &piece_buffers, None, depth(true, Less), None, true);
        // Lines are translucent (soft edges, fades), so they test against
        // the board's depth without writing their own.
        let line_attrs =
            wgpu::vertex_attr_array![0 => Float32x3, 1 => Float32x2, 2 => Float32, 3 => Unorm8x4, 4 => Unorm8x4];
        let line_buffers = [Some(wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<LineVertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &line_attrs,
        })];
        let line_pipeline = pipeline(
            "lines",
            "vs_line",
            "fs_line",
            &line_buffers,
            None,
            depth(false, Less),
            Some(wgpu::BlendState::ALPHA_BLENDING),
            false,
        );

        // Blit into egui's render pass.
        let blit_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("blit layout"),
            entries: &[
                tex_entry(0, wgpu::TextureSampleType::Float { filterable: true }),
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
                uniform_entry(2, wgpu::ShaderStages::FRAGMENT),
            ],
        });
        let blit_pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("blit pipeline layout"),
            bind_group_layouts: &[Some(&blit_layout)],
            immediate_size: 0,
        });
        let blit_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("blit"),
            layout: Some(&blit_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_fullscreen"),
                compilation_options: Default::default(),
                buffers: &[],
            },
            primitive: Default::default(),
            depth_stencil: None,
            multisample: Default::default(),
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_blit"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: None,
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            multiview_mask: None,
            cache: None,
        });
        let encode = if target_format.is_srgb() { 0.0f32 } else { 1.0 };
        let blit_params = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("blit params"),
            contents: bytemuck::cast_slice(&[encode, 0.0, 0.0, 0.0]),
            usage: wgpu::BufferUsages::UNIFORM,
        });
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("blit sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });

        let vertices = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("board vertices"),
            contents: bytemuck::cast_slice(&mesh.vertices),
            usage: wgpu::BufferUsages::VERTEX,
        });
        let indices = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("board indices"),
            contents: bytemuck::cast_slice(&mesh.indices),
            usage: wgpu::BufferUsages::INDEX,
        });
        let (template, template_indices) = mesh::prop_template();
        let prop_vertices = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("prop template"),
            contents: bytemuck::cast_slice(&template),
            usage: wgpu::BufferUsages::VERTEX,
        });
        let prop_indices = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("prop template indices"),
            contents: bytemuck::cast_slice(&template_indices),
            usage: wgpu::BufferUsages::INDEX,
        });
        let prop_instances = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("prop instances"),
            contents: bytemuck::cast_slice(&mesh.props),
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
        });
        let piece_capacity = 4096;
        let pieces = Self::piece_buffer(device, piece_capacity);
        let line_capacity = [4096, 8192];
        let (line_vertices, line_indices) = Self::line_buffers(device, line_capacity);

        Self {
            board_pipeline,
            background_pipeline,
            shadow_pipeline,
            piece_pipeline,
            line_pipeline,
            prop_pipeline,
            prop_vertices,
            prop_indices,
            prop_instances,
            prop_instance_count: mesh.props.len() as u32,
            prop_detail_count: mesh.props.len() as u32,
            prop_all: mesh.props.clone(),
            prop_tex_view,
            art_tex_view,
            hex_tex_view,
            slot_bake_pipeline,
            hex_bake_pipeline,
            bake_bind_group,
            art_baked_blend: None,
            prop_scratch: Vec::with_capacity(mesh.props.len()),
            blit_pipeline,
            blit_layout,
            blit_params,
            sampler,
            globals,
            bind_group,
            vertices,
            indices,
            index_count: mesh.indices.len() as u32,
            state_tex,
            elevation_tex,
            height_tex,
            evidence_tex,
            river_tex,
            river_field: None,
            state_size: [cols, rows],
            state_rgba: Vec::new(),
            pieces,
            piece_capacity,
            piece_count: 0,
            piece_data: Vec::new(),
            line_vertices,
            line_indices,
            line_capacity,
            line_count: 0,
            line_data: LineMesh::default(),
            targets: None,
            rendered: None,
        }
    }

    fn piece_buffer(device: &wgpu::Device, capacity: usize) -> wgpu::Buffer {
        device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("settlement pieces"),
            size: (capacity * std::mem::size_of::<PieceVertex>()) as u64,
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        })
    }

    fn line_buffers(device: &wgpu::Device, capacity: [usize; 2]) -> (wgpu::Buffer, wgpu::Buffer) {
        let buffer = |label, size: usize, usage| {
            device.create_buffer(&wgpu::BufferDescriptor {
                label: Some(label),
                size: size as u64,
                usage: usage | wgpu::BufferUsages::COPY_DST,
                mapped_at_creation: false,
            })
        };
        (
            buffer("line vertices", capacity[0] * std::mem::size_of::<LineVertex>(), wgpu::BufferUsages::VERTEX),
            buffer("line indices", capacity[1] * 4, wgpu::BufferUsages::INDEX),
        )
    }

    /// Replaces the line overlays (rivers, channel belts, lake shores).
    pub fn upload_lines(&mut self, device: &wgpu::Device, queue: &wgpu::Queue, mesh: &LineMesh) {
        if *mesh == self.line_data {
            return;
        }
        self.line_data.clone_from(mesh);
        self.rendered = None;
        if mesh.vertices.len() > self.line_capacity[0] || mesh.indices.len() > self.line_capacity[1] {
            self.line_capacity = [
                mesh.vertices.len().next_power_of_two().max(self.line_capacity[0]),
                mesh.indices.len().next_power_of_two().max(self.line_capacity[1]),
            ];
            (self.line_vertices, self.line_indices) = Self::line_buffers(device, self.line_capacity);
        }
        if !mesh.indices.is_empty() {
            queue.write_buffer(&self.line_vertices, 0, bytemuck::cast_slice(&mesh.vertices));
            queue.write_buffer(&self.line_indices, 0, bytemuck::cast_slice(&mesh.indices));
        }
        self.line_count = mesh.indices.len() as u32;
    }

    /// Uploads the whole per-hex state ([`super::scene::StateTexels`]):
    /// `cols × rows` RGBA8 texels in row order (terrain, koeppen,
    /// population, flags), RGBA8 relief (elevation band, hillshade,
    /// productivity band, biodiversity and expected-population bands) and R16
    /// surface height. About 200 KB.
    pub fn upload_state(&mut self, queue: &wgpu::Queue, state: &super::scene::StateTexels) {
        let [w, h] = self.state_size;
        assert_eq!(state.rgba.len(), (w * h * 4) as usize);
        assert_eq!(state.relief.len(), (w * h * 4) as usize);
        assert_eq!(state.height.len(), (w * h) as usize);
        let height: &[u8] = bytemuck::cast_slice(&state.height);
        for (texture, bytes, texel) in [
            (&self.state_tex, state.rgba.as_slice(), 4),
            (&self.elevation_tex, state.relief.as_slice(), 4),
            (&self.height_tex, height, 2),
        ] {
            queue.write_texture(
                wgpu::TexelCopyTextureInfo { texture, mip_level: 0, origin: wgpu::Origin3d::ZERO, aspect: wgpu::TextureAspect::All },
                bytes,
                wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * texel), rows_per_image: Some(h) },
                wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
            );
        }
        // The prop layout reads terrain (r) and landform (a, bits 3-4), not
        // the selection, hover and lasso flags (a, bits 0-2), so selecting
        // keeps the bake.
        let layout_changed = self.state_rgba.len() != state.rgba.len()
            || self.state_rgba.chunks_exact(4).zip(state.rgba.chunks_exact(4)).any(|(a, b)| a[0] != b[0] || a[3] >> 3 != b[3] >> 3);
        if layout_changed {
            self.art_baked_blend = None;
        }
        self.state_rgba.clone_from(&state.rgba);
        self.rendered = None;
    }

    /// Uploads the selected evidence layer's codes at the current year,
    /// `cols × rows` bytes in row order ([`super::scene::evidence_texels`]).
    pub fn upload_evidence(&mut self, queue: &wgpu::Queue, texels: &[u8]) {
        let [w, h] = self.state_size;
        assert_eq!(texels.len(), (w * h) as usize);
        queue.write_texture(
            self.evidence_tex.as_image_copy(),
            texels,
            wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w), rows_per_image: Some(h) },
            wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
        );
        self.rendered = None;
    }

    /// Replaces the river field ([`super::lines::river_field`]): where the
    /// channels are, for the terrain art. The prop layout depends on it, so
    /// a new one re-bakes the art.
    pub fn upload_river_field(&mut self, queue: &wgpu::Queue, field: &super::lines::RiverField) {
        if self.river_field.as_ref() == Some(field) {
            return;
        }
        let [w, h] = field.size;
        assert_eq!([w, h], [self.river_tex.width(), self.river_tex.height()]);
        queue.write_texture(
            self.river_tex.as_image_copy(),
            &field.rgba,
            wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * 4), rows_per_image: Some(h) },
            wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
        );
        self.river_field = Some(field.clone());
        self.art_baked_blend = None;
        self.rendered = None;
    }

    /// Sets or clears `flag` (e.g. [`super::scene::FLAG_HOVER`]) on the hex
    /// at state-texture position `(col, row)`, re-sending only that texel.
    /// Much cheaper than [`Self::upload_state`] for hover, which changes
    /// whenever the cursor crosses a hex edge. Does nothing before the first
    /// full upload.
    pub fn set_flag(&mut self, queue: &wgpu::Queue, col: u32, row: u32, flag: u8, on: bool) {
        let [w, h] = self.state_size;
        let t = (row * w + col) as usize * 4;
        if col >= w || row >= h || t + 4 > self.state_rgba.len() {
            return;
        }
        let texel = &mut self.state_rgba[t..t + 4];
        let flags = if on { texel[3] | flag } else { texel[3] & !flag };
        if flags == texel[3] {
            return;
        }
        texel[3] = flags;
        queue.write_texture(
            wgpu::TexelCopyTextureInfo {
                texture: &self.state_tex,
                mip_level: 0,
                origin: wgpu::Origin3d { x: col, y: row, z: 0 },
                aspect: wgpu::TextureAspect::All,
            },
            &self.state_rgba[t..t + 4],
            wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(4), rows_per_image: Some(1) },
            wgpu::Extent3d { width: 1, height: 1, depth_or_array_layers: 1 },
        );
        self.rendered = None;
    }

    /// Replaces the settlement piece triangles (world space).
    pub fn upload_pieces(&mut self, device: &wgpu::Device, queue: &wgpu::Queue, vertices: &[PieceVertex]) {
        let bytes: &[u8] = bytemuck::cast_slice(vertices);
        if bytes == bytemuck::cast_slice::<_, u8>(&self.piece_data) {
            return;
        }
        self.piece_data.clear();
        self.piece_data.extend_from_slice(vertices);
        self.rendered = None;
        if vertices.len() > self.piece_capacity {
            self.piece_capacity = vertices.len().next_power_of_two();
            self.pieces = Self::piece_buffer(device, self.piece_capacity);
        }
        if !vertices.is_empty() {
            queue.write_buffer(&self.pieces, 0, bytemuck::cast_slice(vertices));
        }
        self.piece_count = vertices.len() as u32;
    }

    fn ensure_targets(&mut self, device: &wgpu::Device, size: [u32; 2]) {
        let size = [size[0].clamp(1, 8192), size[1].clamp(1, 8192)];
        if self.targets.as_ref().is_some_and(|t| t.size == size) {
            return;
        }
        self.rendered = None;
        let texture = |label, format, sample_count, usage| {
            device.create_texture(&wgpu::TextureDescriptor {
                label: Some(label),
                size: wgpu::Extent3d { width: size[0], height: size[1], depth_or_array_layers: 1 },
                mip_level_count: 1,
                sample_count,
                dimension: wgpu::TextureDimension::D2,
                format,
                usage,
                view_formats: &[],
            })
        };
        use wgpu::TextureUsages as U;
        let msaa = texture("board msaa", COLOUR_FORMAT, SAMPLES, U::RENDER_ATTACHMENT);
        let depth = texture("board depth", DEPTH_FORMAT, SAMPLES, U::RENDER_ATTACHMENT);
        let resolve =
            texture("board colour", COLOUR_FORMAT, 1, U::RENDER_ATTACHMENT | U::TEXTURE_BINDING | U::COPY_SRC);
        let resolve_view = resolve.create_view(&Default::default());
        let blit_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("blit bind group"),
            layout: &self.blit_layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: wgpu::BindingResource::TextureView(&resolve_view) },
                wgpu::BindGroupEntry { binding: 1, resource: wgpu::BindingResource::Sampler(&self.sampler) },
                wgpu::BindGroupEntry { binding: 2, resource: self.blit_params.as_entire_binding() },
            ],
        });
        self.targets = Some(Targets {
            size,
            msaa_view: msaa.create_view(&Default::default()),
            depth_view: depth.create_view(&Default::default()),
            resolve,
            resolve_view,
            blit_bind_group,
        });
    }

    /// Draws the scene into the offscreen target unless it already holds
    /// this exact frame (same globals, nothing uploaded since).
    ///
    /// It records into its own encoder and submits it straight away rather
    /// than using egui's: eframe drops a frame's encoder when it can't get a
    /// surface texture (a window not shown yet, a hidden tab), and a frame
    /// believed drawn but never executed would leave the board blank.
    pub fn render_if_changed(&mut self, device: &wgpu::Device, queue: &wgpu::Queue, size: [u32; 2], globals: &Globals) {
        self.ensure_targets(device, size);
        if self.rendered.as_ref().is_some_and(|g| bytemuck::bytes_of(g) == bytemuck::bytes_of(globals)) {
            return;
        }
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("board") });
        self.render(device, queue, &mut encoder, size, globals);
        queue.submit([encoder.finish()]);
        self.rendered = Some(*globals);
    }

    /// Draws the scene into the offscreen target (resized to `size` pixels).
    pub fn render(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        encoder: &mut wgpu::CommandEncoder,
        size: [u32; 2],
        globals: &Globals,
    ) {
        self.ensure_targets(device, size);
        queue.write_buffer(&self.globals, 0, bytemuck::bytes_of(globals));
        if globals.art[0] > 0.0 || globals.art[1] > 0.0 {
            self.bake_art(encoder, globals);
        }
        if globals.art[1] > 0.0 {
            self.cull_props(queue, globals);
        }
        let targets = self.targets.as_ref().unwrap();
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("board"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: &targets.msaa_view,
                depth_slice: None,
                resolve_target: Some(&targets.resolve_view),
                ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::BLACK), store: wgpu::StoreOp::Discard },
            })],
            depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                view: &targets.depth_view,
                depth_ops: Some(wgpu::Operations { load: wgpu::LoadOp::Clear(1.0), store: wgpu::StoreOp::Discard }),
                stencil_ops: None,
            }),
            timestamp_writes: None,
            occlusion_query_set: None,
            multiview_mask: None,
        });
        pass.set_bind_group(0, &self.bind_group, &[]);
        pass.set_pipeline(&self.background_pipeline);
        pass.draw(0..3, 0..1);
        pass.set_pipeline(&self.shadow_pipeline);
        pass.draw(0..6, 0..1);
        pass.set_pipeline(&self.board_pipeline);
        pass.set_vertex_buffer(0, self.vertices.slice(..));
        pass.set_index_buffer(self.indices.slice(..), wgpu::IndexFormat::Uint32);
        pass.draw_indexed(0..self.index_count, 0, 0..1);
        if globals.art[1] > 0.0 {
            // 3D terrain art: one template, instanced per hex.
            pass.set_pipeline(&self.prop_pipeline);
            pass.set_vertex_buffer(0, self.prop_vertices.slice(..));
            pass.set_vertex_buffer(1, self.prop_instances.slice(..));
            pass.set_index_buffer(self.prop_indices.slice(..), wgpu::IndexFormat::Uint16);
            // Detail hexes first with the whole template, then the rest with the base slots only.
            let (n, d) = (self.prop_instance_count, self.prop_detail_count);
            if d > 0 {
                pass.draw_indexed(0..mesh::prop_index_count(mesh::PROP_SLOTS), 0, 0..d);
            }
            if n > d {
                pass.draw_indexed(0..mesh::prop_index_count(mesh::PROP_BASE_SLOTS), 0, d..n);
            }
        }
        if self.line_count > 0 {
            // Over the tiles and their art, under the settlement pieces.
            pass.set_pipeline(&self.line_pipeline);
            pass.set_vertex_buffer(0, self.line_vertices.slice(..));
            pass.set_index_buffer(self.line_indices.slice(..), wgpu::IndexFormat::Uint32);
            pass.draw_indexed(0..self.line_count, 0, 0..1);
        }
        if self.piece_count > 0 {
            pass.set_pipeline(&self.piece_pipeline);
            pass.set_vertex_buffer(0, self.pieces.slice(..));
            pass.draw(0..self.piece_count, 0..1);
        }
    }

    /// Re-bakes the terrain art textures (per-hex data, then the prop layout
    /// and glyph lists) if the hex state or the edge blending (on only in
    /// the terrain map mode) changed since the last bake. [`Self::set_flag`]
    /// doesn't touch them: the art ignores those flags.
    fn bake_art(&mut self, encoder: &mut wgpu::CommandEncoder, g: &Globals) {
        let blend = if g.grid[2] == 0.0 { g.art[3] } else { 0.0 };
        if self.art_baked_blend == Some(blend) {
            return;
        }
        for (label, pipeline, views) in [
            ("hex art bake", &self.hex_bake_pipeline, vec![&self.hex_tex_view]),
            ("slot bake", &self.slot_bake_pipeline, vec![&self.prop_tex_view, &self.art_tex_view]),
        ] {
            let attachments: Vec<_> = views
                .into_iter()
                .map(|view| {
                    Some(wgpu::RenderPassColorAttachment {
                        view,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT), store: wgpu::StoreOp::Store },
                    })
                })
                .collect();
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some(label),
                color_attachments: &attachments,
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });
            pass.set_pipeline(pipeline);
            pass.set_bind_group(0, &self.bake_bind_group, &[]);
            pass.draw(0..3, 0..1);
        }
        self.art_baked_blend = Some(blend);
    }

    /// Uploads the props that can show this frame ([`select_props`]).
    fn cull_props(&mut self, queue: &wgpu::Queue, g: &Globals) {
        let mut out = std::mem::take(&mut self.prop_scratch);
        let cols = self.state_size[0] as usize;
        self.prop_detail_count = select_props(&self.prop_all, &self.state_rgba, cols, g, &mut out);
        self.prop_instance_count = out.len() as u32;
        if !out.is_empty() {
            queue.write_buffer(&self.prop_instances, 0, bytemuck::cast_slice(&out));
        }
        self.prop_scratch = out;
    }

    /// Draws the last rendered image over the current viewport of `pass`.
    pub fn blit(&self, pass: &mut wgpu::RenderPass<'_>) {
        if let Some(t) = &self.targets {
            pass.set_pipeline(&self.blit_pipeline);
            pass.set_bind_group(0, &t.blit_bind_group, &[]);
            pass.draw(0..3, 0..1);
        }
    }

    /// The resolved colour target of the last render (for screenshots).
    #[cfg_attr(target_arch = "wasm32", allow(dead_code))]
    pub fn colour_texture(&self) -> Option<(&wgpu::Texture, [u32; 2])> {
        self.targets.as_ref().map(|t| (&t.resolve, t.size))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The whole module parses and validates, so a shader mistake fails the
    /// tests rather than the app at startup.
    #[test]
    fn shader_validates() {
        use wgpu::naga;
        let module = naga::front::wgsl::parse_str(&shader_source()).unwrap_or_else(|e| panic!("{}", e.emit_to_string(&shader_source())));
        naga::valid::Validator::new(naga::valid::ValidationFlags::all(), naga::valid::Capabilities::default())
            .validate(&module)
            .unwrap_or_else(|e| panic!("{}", e.emit_to_string(&shader_source())));
    }

    #[test]
    fn shader_terrain_constants_follow_the_enum() {
        let src = shader_source();
        assert!(src.contains("const T_WATER: u32 = 0u;"));
        assert!(src.contains(&format!("const T_BOREAL_FOREST: u32 = {}u;", Terrain::BorealForest as u8)));
        assert_eq!(src.matches("\nconst T_").count(), Terrain::ALL.len());
        // Every terrain the art switches on has a constant.
        let art = include_str!("terrain_art.wgsl");
        for case in art.lines().filter_map(|l| l.trim().strip_prefix("case ")) {
            let name = case.split(':').next().unwrap().trim();
            assert!(src.contains(&format!("const {name}: u32")), "{name} has no constant");
        }
    }
}
