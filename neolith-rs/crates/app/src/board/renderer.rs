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
const SAMPLES: u32 = 4;

/// Terrain art detail: between these hex radii on screen (pixels) the extra
/// glyph slots sprout and the rest shrink to make room.
pub const ART_DETAIL_PX: [f32; 2] = [24.0, 44.0];

/// Can any hex be close enough to the camera for the detail slots? A lower
/// bound on the eye's distance to the board gives an upper bound on hex
/// size, so this errs towards drawing them.
pub fn detail_possible(g: &Globals) -> bool {
    let eye = glam::Vec3::new(g.cam_pos[0], g.cam_pos[1], g.cam_pos[2]);
    let height = (eye.length() - 1.0).min(eye.y - 1.0).max(1e-6);
    let unit = g.hex[1] / (3f32.sqrt() / 2.0);
    unit * g.art[2] / height > ART_DETAIL_PX[0]
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
    prop_pipeline: wgpu::RenderPipeline,
    prop_vertices: wgpu::Buffer,
    prop_indices: wgpu::Buffer,
    prop_index_count: u32,
    prop_base_index_count: u32,
    prop_instances: wgpu::Buffer,
    prop_instance_count: u32,
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
    state_size: [u32; 2],
    pieces: wgpu::Buffer,
    piece_capacity: usize,
    piece_count: u32,
    targets: Option<Targets>,
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
        let elevation_tex = device.create_texture(&tex_desc("hex relief", cols, rows, wgpu::TextureFormat::Rg8Uint));
        let height_tex = device.create_texture(&tex_desc("hex height", cols, rows, wgpu::TextureFormat::R16Sint));
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
            ],
        });
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
                        blend: Option<wgpu::BlendState>| {
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
                multisample,
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: Some(fs),
                    compilation_options: Default::default(),
                    targets: &[Some(wgpu::ColorTargetState {
                        format: COLOUR_FORMAT,
                        blend,
                        write_mask: wgpu::ColorWrites::ALL,
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
            pipeline("board", "vs_board", "fs_board", &board_buffers, Some(wgpu::Face::Back), depth(true, Less), None);
        let background_pipeline =
            pipeline("background", "vs_fullscreen", "fs_background", &[], None, depth(false, Always), None);
        let shadow_pipeline = pipeline(
            "contact shadow",
            "vs_shadow",
            "fs_shadow",
            &[],
            None,
            depth(false, Less),
            Some(wgpu::BlendState::ALPHA_BLENDING),
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
        let prop_pipeline = pipeline("terrain props", "vs_prop", "fs_prop", &prop_buffers, None, depth(true, Less), None);
        let piece_pipeline = pipeline("pieces", "vs_piece", "fs_piece", &piece_buffers, None, depth(true, Less), None);

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
            usage: wgpu::BufferUsages::VERTEX,
        });
        let piece_capacity = 4096;
        let pieces = Self::piece_buffer(device, piece_capacity);

        Self {
            board_pipeline,
            background_pipeline,
            shadow_pipeline,
            piece_pipeline,
            prop_pipeline,
            prop_vertices,
            prop_indices,
            prop_index_count: template_indices.len() as u32,
            prop_base_index_count: mesh::prop_index_count(mesh::PROP_BASE_SLOTS),
            prop_instances,
            prop_instance_count: mesh.props.len() as u32,
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
            state_size: [cols, rows],
            pieces,
            piece_capacity,
            piece_count: 0,
            targets: None,
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

    /// Uploads the whole per-hex state ([`super::scene::StateTexels`]):
    /// `cols × rows` RGBA8 texels in row order (terrain, koeppen,
    /// population, flags), RG8 relief (elevation band, hillshade) and R16
    /// surface height. About 200 KB.
    pub fn upload_state(&self, queue: &wgpu::Queue, state: &super::scene::StateTexels) {
        let [w, h] = self.state_size;
        assert_eq!(state.rgba.len(), (w * h * 4) as usize);
        assert_eq!(state.relief.len(), (w * h * 2) as usize);
        assert_eq!(state.height.len(), (w * h) as usize);
        let height: &[u8] = bytemuck::cast_slice(&state.height);
        for (texture, bytes, texel) in [
            (&self.state_tex, state.rgba.as_slice(), 4),
            (&self.elevation_tex, state.relief.as_slice(), 2),
            (&self.height_tex, height, 2),
        ] {
            queue.write_texture(
                wgpu::TexelCopyTextureInfo { texture, mip_level: 0, origin: wgpu::Origin3d::ZERO, aspect: wgpu::TextureAspect::All },
                bytes,
                wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * texel), rows_per_image: Some(h) },
                wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
            );
        }
    }

    /// Replaces the settlement piece triangles (world space).
    pub fn upload_pieces(&mut self, device: &wgpu::Device, queue: &wgpu::Queue, vertices: &[PieceVertex]) {
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
            // The detail slots only matter close up; skip their vertex work otherwise.
            let count = if detail_possible(globals) { self.prop_index_count } else { self.prop_base_index_count };
            pass.draw_indexed(0..count, 0, 0..self.prop_instance_count);
        }
        if self.piece_count > 0 {
            pass.set_pipeline(&self.piece_pipeline);
            pass.set_vertex_buffer(0, self.pieces.slice(..));
            pass.draw(0..self.piece_count, 0..1);
        }
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
