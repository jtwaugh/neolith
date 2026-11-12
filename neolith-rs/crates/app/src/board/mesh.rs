//! The board's static geometry, built once at load: top tiles, the stepped
//! edge walls and the underside. GPU-free so it can be tested.

use super::projection::Projection;
use bytemuck::{Pod, Zeroable};
use neolith_core::{GridSpec, HexId, LonLat};

pub const KIND_TOP: u8 = 0;
pub const KIND_WALL: u8 = 1;
pub const KIND_UNDERSIDE: u8 = 2;
/// A cliff between two tiles of different height: from this hex's top
/// (`depth` 0) to the neighbour's across edge `corner` (`depth` 255). One
/// per inside edge, double-sided; see [`STEP_EDGES`].
pub const KIND_STEP: u8 = 3;

/// The edges (NE, N, NW) each hex builds steps on. The other three are its
/// neighbours' NE/N/NW edges, so every inside edge gets exactly one step.
pub const STEP_EDGES: [usize; 3] = [0, 1, 2];

/// One board vertex (28 bytes).
///
/// Differences from the sketch in DESIGN.md §7.2.1, both to keep 7 shared
/// vertices per hex without relying on flat-interpolation provoking-vertex
/// rules (which differ between WebGPU and WebGL2): instead of a per-triangle
/// `edge`, each vertex carries its `corner` index, from which the vertex
/// shader derives hex-local coordinates; the fragment shader finds the
/// nearest edge and the distance to it from those. `kind`/`depth` let the
/// walls and underside share the buffer and morph with the top.
#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
pub struct HexVertex {
    /// Unit-sphere position, board-rotated.
    pub sphere: [f32; 3],
    /// Equirectangular (λ, φ) relative to the board centre, radians.
    pub flat: [f32; 2],
    /// (col, row): the texel in the state texture.
    pub cell: [u16; 2],
    /// Corner index 0..6 (angle 60°·k); unused at the centre.
    pub corner: u8,
    /// 0 at the hex centre, 255 on the rim.
    pub rim: u8,
    /// [`KIND_TOP`], [`KIND_WALL`], [`KIND_UNDERSIDE`] or [`KIND_STEP`].
    pub kind: u8,
    /// 0 on the top surface, 255 at the bottom of the board.
    pub depth: u8,
}

/// One vertex of the prop template: which slot of the hex, which band of
/// the lathe, which end of the band (0 bottom, 1 top) and which side. The
/// vertex shader turns these into a tree or a peak (see terrain_art.wgsl).
#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
pub struct PropVertex {
    pub attrs: [u8; 4],
}

/// Glyph slots per hex: the base layout, then the detail slots that sprout
/// when zoomed in. The template lists the base slots first, so drawing only
/// its first [`prop_index_count`]`(PROP_BASE_SLOTS)` indices skips the detail.
pub const PROP_SLOTS: u8 = 12;
pub const PROP_BASE_SLOTS: u8 = 5;
pub const PROP_BANDS: u8 = 3;
pub const PROP_SIDES: u8 = 5;

/// Indices in the template for the first `slots` slots.
pub const fn prop_index_count(slots: u8) -> u32 {
    slots as u32 * PROP_BANDS as u32 * PROP_SIDES as u32 * 6
}

/// The template mesh instanced once per hex for the 3D terrain art.
pub fn prop_template() -> (Vec<PropVertex>, Vec<u16>) {
    let (mut vertices, mut indices) = (Vec::new(), Vec::new());
    for slot in 0..PROP_SLOTS {
        for band in 0..PROP_BANDS {
            let base = vertices.len() as u16;
            for end in 0..2 {
                for side in 0..PROP_SIDES {
                    vertices.push(PropVertex { attrs: [slot, band, end, side] });
                }
            }
            let n = PROP_SIDES as u16;
            for side in 0..n {
                let (a, b) = (base + side, base + (side + 1) % n);
                indices.extend_from_slice(&[a, b, b + n, a, b + n, a + n]);
            }
        }
    }
    (vertices, indices)
}

/// Per-hex instance data for the props (48 bytes): the hex's frame on the
/// curved board and its place on the flat one.
#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
pub struct HexInstance {
    /// Hex centre on the unit sphere, board-rotated.
    pub centre: [f32; 3],
    /// Sphere offset from the centre to the east corner.
    pub east: [f32; 3],
    /// Sphere offset from the centre to the middle of the north edge.
    pub north: [f32; 3],
    /// Equirectangular (λ, φ) of the centre, as in [`HexVertex::flat`].
    pub flat: [f32; 2],
    pub cell: [u16; 2],
}

pub fn hex_instances(grid: &GridSpec, proj: &Projection) -> Vec<HexInstance> {
    grid.ids()
        .map(|id| {
            let c = grid.centre(id);
            let centre = proj.sphere(c);
            let east = proj.sphere(LonLat::new(c.lon + grid.w / 2.0, c.lat)) - centre;
            let north = proj.sphere(LonLat::new(c.lon, c.lat + grid.h / 2.0)) - centre;
            let (col, row) = grid.col_row(id);
            HexInstance {
                centre: centre.as_vec3().to_array(),
                east: east.as_vec3().to_array(),
                north: north.as_vec3().to_array(),
                flat: proj.flat(c).as_vec2().to_array(),
                cell: [col, row],
            }
        })
        .collect()
}

pub struct BoardMesh {
    pub vertices: Vec<HexVertex>,
    pub indices: Vec<u32>,
    /// One per hex, for the 3D terrain art.
    pub props: Vec<HexInstance>,
    /// Lowest top-surface height (y) on the curved board.
    pub sphere_min_y: f32,
    /// Half extents (x, z) of the footprint: curved, then flat.
    pub sphere_half_extent: [f32; 2],
    pub flat_half_extent: [f32; 2],
}

pub fn build(grid: &GridSpec, proj: &Projection) -> BoardMesh {
    let n = grid.len();
    let outside = grid.outside_edges();
    // Tops and undersides, outside walls, then up to 3 steps per hex.
    let mut vertices = Vec::with_capacity(n * 14 + outside.len() * 4 + n * 12);
    let mut indices = Vec::with_capacity(n * 36 + outside.len() * 6 + n * 36);
    let mut mesh_min_y = f32::INFINITY;
    let (mut s_ext, mut f_ext) = ([0f32; 2], [0f32; 2]);

    let vertex = |p: LonLat, cell: (u16, u16), corner: u8, rim: u8, kind: u8, depth: u8| {
        let s = proj.sphere(p).as_vec3();
        let f = proj.flat(p).as_vec2();
        HexVertex { sphere: s.to_array(), flat: f.to_array(), cell: [cell.0, cell.1], corner, rim, kind, depth }
    };

    for (kind, depth) in [(KIND_TOP, 0u8), (KIND_UNDERSIDE, 255u8)] {
        for i in 0..n {
            let id = HexId(i as u32);
            let cell = grid.col_row(id);
            let base = vertices.len() as u32;
            vertices.push(vertex(grid.centre(id), cell, 0, 0, kind, depth));
            for (k, c) in grid.corners(id).into_iter().enumerate() {
                let v = vertex(c, cell, k as u8, 255, kind, depth);
                if kind == KIND_TOP {
                    mesh_min_y = mesh_min_y.min(v.sphere[1]);
                    s_ext = [s_ext[0].max(v.sphere[0].abs()), s_ext[1].max(v.sphere[2].abs())];
                    f_ext = [f_ext[0].max(v.flat[0].abs()), f_ext[1].max(v.flat[1].abs())];
                }
                vertices.push(v);
            }
            for k in 0..6u32 {
                let (a, b) = (base + 1 + k, base + 1 + (k + 1) % 6);
                // Counter-clockwise seen from outside the board.
                if kind == KIND_TOP {
                    indices.extend_from_slice(&[base, a, b]);
                } else {
                    indices.extend_from_slice(&[base, b, a]);
                }
            }
        }
    }

    // Side walls: one quad per outside edge, from the top surface down to the
    // board's thickness, so the sides are stepped like a hex-tile board.
    for (id, edge) in outside {
        let cell = grid.col_row(id);
        let corners = grid.corners(id);
        let (a, b) = (corners[edge as usize], corners[(edge as usize + 1) % 6]);
        let base = vertices.len() as u32;
        vertices.push(vertex(a, cell, edge, 255, KIND_WALL, 255)); // a bottom
        vertices.push(vertex(b, cell, edge, 255, KIND_WALL, 255)); // b bottom
        vertices.push(vertex(b, cell, edge, 255, KIND_WALL, 0)); // b top
        vertices.push(vertex(a, cell, edge, 255, KIND_WALL, 0)); // a top
        indices.extend_from_slice(&[base, base + 1, base + 2, base, base + 2, base + 3]);
    }

    // Steps: one quad per inside edge, from this hex's top to the
    // neighbour's (the vertex shader places both). It has triangles in both
    // windings: whichever side is lower sees the cliff face, the other side
    // is culled. The vertex shader colours it by the higher hex.
    for i in 0..n {
        let id = HexId(i as u32);
        let cell = grid.col_row(id);
        let corners = grid.corners(id);
        for edge in STEP_EDGES {
            if grid.neighbour(id, edge).is_none() {
                continue;
            }
            let (a, b) = (corners[edge], corners[(edge + 1) % 6]);
            let base = vertices.len() as u32;
            let e = edge as u8;
            vertices.push(vertex(a, cell, e, 255, KIND_STEP, 255)); // a, neighbour height
            vertices.push(vertex(b, cell, e, 255, KIND_STEP, 255)); // b, neighbour height
            vertices.push(vertex(b, cell, e, 255, KIND_STEP, 0)); // b, own height
            vertices.push(vertex(a, cell, e, 255, KIND_STEP, 0)); // a, own height
            // Front (faces the neighbour), then back (faces this hex).
            indices.extend_from_slice(&[base, base + 1, base + 2, base, base + 2, base + 3]);
            indices.extend_from_slice(&[base, base + 2, base + 1, base, base + 3, base + 2]);
        }
    }

    let props = hex_instances(grid, proj);
    BoardMesh { vertices, indices, props, sphere_min_y: mesh_min_y, sphere_half_extent: s_ext, flat_half_extent: f_ext }
}

#[cfg(test)]
mod tests {
    use super::*;
    use glam::Vec3;

    fn small() -> (GridSpec, Projection) {
        let g = GridSpec { cols: 12, rows: 9, origin_lon: 10.0, origin_lat: 50.0, w: 0.5773502691896262, h: 0.5 };
        let p = Projection::new(g.centre_of_bounds());
        (g, p)
    }

    #[test]
    fn counts() {
        let (g, p) = small();
        let m = build(&g, &p);
        let walls = g.outside_edges().len();
        // Every inside edge once; each step is double-sided.
        let steps = (g.len() * 6 - walls) / 2;
        assert_eq!(m.vertices.len(), g.len() * 14 + (walls + steps) * 4);
        assert_eq!(m.indices.len(), g.len() * 36 + walls * 6 + steps * 12);
        // And each inside edge is covered: the step's edge and its far side.
        let mut seen = std::collections::HashSet::new();
        for v in m.vertices.iter().filter(|v| v.kind == KIND_STEP) {
            let id = g.id_at(v.cell[0], v.cell[1]);
            let nb = g.neighbour(id, v.corner as usize).unwrap();
            seen.insert((id.0.min(nb.0), id.0.max(nb.0)));
        }
        assert_eq!(seen.len(), steps);
        assert!(m.indices.iter().all(|i| (*i as usize) < m.vertices.len()));
        assert_eq!(std::mem::size_of::<HexVertex>(), 28);
    }

    #[test]
    fn props() {
        let (g, p) = small();
        let m = build(&g, &p);
        assert_eq!(m.props.len(), g.len());
        assert_eq!(std::mem::size_of::<HexInstance>(), 48);
        // East and north are (chords, so only nearly) tangent to the sphere
        // and at right angles.
        for i in &m.props {
            let (c, e, n) = (Vec3::from(i.centre), Vec3::from(i.east), Vec3::from(i.north));
            assert!(e.normalize().dot(c).abs() < 0.02 && n.normalize().dot(c).abs() < 0.02);
            assert!(e.normalize().dot(n.normalize()).abs() < 0.02);
        }
        let (v, idx) = prop_template();
        assert_eq!(v.len(), 12 * 3 * 2 * 5);
        assert_eq!(idx.len() as u32, prop_index_count(PROP_SLOTS));
        // The base slots come first.
        let base = prop_index_count(PROP_BASE_SLOTS) as usize;
        assert!(idx[..base].iter().all(|i| v[*i as usize].attrs[0] < PROP_BASE_SLOTS));
        assert!(idx[base..].iter().all(|i| v[*i as usize].attrs[0] >= PROP_BASE_SLOTS));
        assert!(idx.iter().all(|i| (*i as usize) < v.len()));
    }

    /// Every triangle must face outwards (the renderer culls back faces):
    /// top up, underside down, walls away from their hex.
    #[test]
    fn winding_faces_outwards() {
        let (g, p) = small();
        let m = build(&g, &p);
        let thick = 0.015f32;
        let pos = |v: &HexVertex| Vec3::from(v.sphere) * (1.0 - thick * v.depth as f32 / 255.0);
        for tri in m.indices.chunks(3) {
            let v: Vec<&HexVertex> = tri.iter().map(|i| &m.vertices[*i as usize]).collect();
            let (a, b, c) = (pos(v[0]), pos(v[1]), pos(v[2]));
            let normal = (b - a).cross(c - a);
            let centroid = (a + b + c) / 3.0;
            match v[0].kind {
                KIND_TOP => assert!(normal.dot(centroid) > 0.0),
                KIND_UNDERSIDE => assert!(normal.dot(centroid) < 0.0),
                KIND_STEP => {}
                _ => {
                    let id = g.id_at(v[0].cell[0], v[0].cell[1]);
                    let hex_centre = p.sphere(g.centre(id)).as_vec3();
                    assert!(normal.dot(centroid - hex_centre) > 0.0);
                }
            }
        }
    }

    /// Steps come as front/back pairs: the same triangles, opposite windings.
    #[test]
    fn steps_are_double_sided() {
        let (g, p) = small();
        let m = build(&g, &p);
        let first = m.indices.iter().position(|i| m.vertices[*i as usize].kind == KIND_STEP).unwrap();
        let step = &m.indices[first..];
        assert!(step.iter().all(|i| m.vertices[*i as usize].kind == KIND_STEP));
        for quad in step.chunks(12) {
            let (front, back) = quad.split_at(6);
            for (f, b) in front.chunks(3).zip(back.chunks(3)) {
                assert_eq!((f[0], f[1], f[2]), (b[0], b[2], b[1]));
            }
        }
    }
}
