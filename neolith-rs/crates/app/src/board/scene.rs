//! Turns app state into what the renderer consumes: the uniform block, the
//! per-hex state texels and the settlement piece triangles.

use super::camera::View;
use super::mesh::BoardMesh;
use super::projection::Projection;
use super::relief::{self, Relief};
use super::renderer::{Globals, PieceVertex};
use crate::palette::Rgb;
use glam::{DVec3, Vec3};
use std::f64::consts::{FRAC_PI_2, FRAC_PI_4};
use neolith_core::{GridSpec, Lake, Landform, LonLat, MapMode, River, RiverState, Selection, Snapshot, Year};

pub const FLAG_SELECTED: u8 = 1;
pub const FLAG_HOVER: u8 = 2;
pub const FLAG_LASSO: u8 = 4;
/// Bits 3-4 of the flags byte: the hex's [`Landform`] (0 = flat or unknown).
pub const LANDFORM_SHIFT: u8 = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Material {
    Wood,
    Slate,
    Cardboard,
}

impl Material {
    pub const ALL: [Material; 3] = [Material::Wood, Material::Slate, Material::Cardboard];

    pub fn label(self) -> &'static str {
        match self {
            Material::Wood => "Wood",
            Material::Slate => "Slate",
            Material::Cardboard => "Cardboard",
        }
    }

    fn colours(self) -> (Rgb, Rgb) {
        // (edge walls, frame lip)
        match self {
            Material::Wood => ([0x8a, 0x5a, 0x36], [0xb0, 0x7a, 0x4a]),
            Material::Slate => ([0x4a, 0x55, 0x60], [0x6c, 0x78, 0x84]),
            Material::Cardboard => ([0xb9, 0xa2, 0x7c], [0xd9, 0xc7, 0xa3]),
        }
    }
}

/// The terrain art layer: illustrations inside the hexes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ArtMode {
    Off,
    /// Printed on the tiles.
    Flat,
    /// Trees, peaks and hills stand on the board as 3D props; the rest
    /// (waves, tufts, dunes, shores) stays printed.
    Raised,
}

impl ArtMode {
    pub const ALL: [ArtMode; 3] = [ArtMode::Off, ArtMode::Flat, ArtMode::Raised];

    pub fn label(self) -> &'static str {
        match self {
            ArtMode::Off => "Off",
            ArtMode::Flat => "2D",
            ArtMode::Raised => "3D",
        }
    }
}

/// The tunable look of the board (the "board style" panel).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BoardStyle {
    pub grout: f32,
    pub bevel: f32,
    /// Lighting quantisation levels; 0 = off.
    pub quantise: f32,
    pub saturation: f32,
    pub borders: f32,
    pub thickness: f32,
    pub frame_lip: bool,
    pub flat_lighting: bool,
    pub material: Material,
    pub terrain_art: ArtMode,
    /// Opacity of the printed art.
    pub art_strength: f32,
    /// Neighbour-aware edges: biomes creep into each other in patches,
    /// shores get foam and a beach.
    pub art_blend: bool,
    /// Draw river lines and lake shorelines.
    pub rivers: bool,
    /// Hillshade from the elevation gradient on land hexes, in every map
    /// mode; 0 = off.
    pub hillshade: f32,
    /// The relief layer: tiles raised to their surface height.
    pub relief: bool,
    /// Vertical exaggeration of the relief.
    pub relief_exaggeration: f32,
    /// Keep the board covering the whole view (no table or sky), clamping
    /// the camera like a Paradox map. Off shows the board as a tabletop piece.
    pub fill_screen: bool,
    /// With `fill_screen`: the fraction of the view on each side that may
    /// show the map's edge (0 = always covered).
    pub fill_margin: f32,
}

impl Default for BoardStyle {
    fn default() -> Self {
        Self {
            grout: 0.6,
            bevel: 0.5,
            quantise: 0.0,
            saturation: 0.92,
            borders: 0.7,
            thickness: 0.015,
            frame_lip: false,
            flat_lighting: false,
            material: Material::Wood,
            terrain_art: ArtMode::Flat,
            art_strength: 1.0,
            art_blend: true,
            rivers: true,
            hillshade: 0.6,
            relief: true,
            relief_exaggeration: 10.0,
            fill_screen: true,
            fill_margin: 0.25,
        }
    }
}

pub fn srgb_to_linear(c: Rgb) -> [f32; 3] {
    c.map(|v| {
        let x = v as f32 / 255.0;
        if x <= 0.04045 {
            x / 12.92
        } else {
            ((x + 0.055) / 1.055).powf(2.4)
        }
    })
}

fn rgb4(c: Rgb, a: f32) -> [f32; 4] {
    let [r, g, b] = srgb_to_linear(c);
    [r, g, b, a]
}

/// `px_height` is the height of the render target in pixels.
pub fn globals(
    view: &View,
    style: &BoardStyle,
    mode: MapMode,
    grid: &GridSpec,
    mesh: &BoardMesh,
    px_height: f32,
) -> Globals {
    let t = view.t as f32;
    let lerp = |a: f32, b: f32| a + (b - a) * t;
    let dir = |v: Vec3, intensity: f32| {
        let v = v.normalize();
        [v.x, v.y, v.z, intensity]
    };
    let (wall, frame) = style.material.colours();
    // The table sits just under the lowest point of the board.
    let table = lerp(mesh.sphere_min_y * (1.0 - style.thickness), 1.0 - style.thickness) - 0.004;
    Globals {
        view_proj: view.view_proj.as_mat4().to_cols_array(),
        cam_pos: [view.eye.x as f32, view.eye.y as f32, view.eye.z as f32, t],
        grid: [grid.cols as f32, grid.rows as f32, mode.index() as f32, style.thickness],
        // Key from above-front-left, dim fill from the right-back.
        key_light: dir(Vec3::new(-0.45, 0.85, 0.40), 0.78),
        fill_light: dir(Vec3::new(0.60, 0.35, -0.50), 0.22),
        tile: [style.grout, style.bevel, style.quantise, style.saturation],
        lines: [style.borders, style.hillshade, 0.34, if style.flat_lighting { 1.0 } else { 0.0 }],
        wall_colour: rgb4(wall, 1.0),
        frame_colour: rgb4(frame, if style.frame_lip { 1.0 } else { 0.0 }),
        // A dark walnut tabletop (see fs_background).
        bg_top: rgb4([0x5a, 0x3e, 0x2a], 1.0),
        // Alpha carries the viewport aspect, so the grain isn't stretched.
        bg_bottom: rgb4([0x2a, 0x1c, 0x13], (view.size.x / view.size.y.max(1.0)) as f32),
        shadow: [
            table,
            lerp(mesh.sphere_half_extent[0], mesh.flat_half_extent[0]),
            lerp(mesh.sphere_half_extent[1], mesh.flat_half_extent[1]),
            0.55,
        ],
        art: [
            if style.terrain_art == ArtMode::Off { 0.0 } else { style.art_strength },
            if style.terrain_art == ArtMode::Raised { 1.0 } else { 0.0 },
            view.focal as f32 * px_height / 2.0,
            if style.art_blend { 1.0 } else { 0.0 },
        ],
        hex: [(grid.w / 2.0).to_radians() as f32, (grid.h / 2.0).to_radians() as f32, relief::scale(style) as f32, 0.0],
    }
}

/// Per-hex state for the GPU, both row-major `cols × rows`.
pub struct StateTexels {
    /// RGBA8: terrain, koeppen, population, flags.
    pub rgba: Vec<u8>,
    /// RG8: elevation band, hillshade ([`neolith_core::elevation::hillshade`]).
    pub relief: Vec<u8>,
    /// R16: tile surface height in metres (`Snapshot::height`).
    pub height: Vec<i16>,
}

pub fn state_texels(
    grid: &GridSpec,
    snapshot: &Snapshot,
    hillshade: &[u8],
    landform: &[Option<Landform>],
    selection: Option<&Selection>,
    lasso: Option<&Selection>,
    hover: Option<neolith_core::HexId>,
) -> StateTexels {
    let (cols, rows) = (grid.cols as usize, grid.rows as usize);
    let mut px = vec![0u8; cols * rows * 4];
    let mut relief = vec![0u8; cols * rows * 2];
    let mut height = vec![0i16; cols * rows];
    for id in grid.ids() {
        let (c, r) = grid.col_row(id);
        let i = id.index();
        let mut flags = landform.get(i).copied().flatten().map_or(0, |l| (l as u8) << LANDFORM_SHIFT);
        if selection.is_some_and(|s| s.contains(id)) {
            flags |= FLAG_SELECTED;
        }
        if lasso.is_some_and(|s| s.contains(id)) {
            flags |= FLAG_LASSO;
        }
        if hover == Some(id) {
            flags |= FLAG_HOVER;
        }
        let t = r as usize * cols + c as usize;
        px[t * 4..t * 4 + 4].copy_from_slice(&[snapshot.terrain[i], snapshot.koeppen[i], snapshot.pop[i], flags]);
        relief[t * 2..t * 2 + 2].copy_from_slice(&[snapshot.elevation[i], hillshade[i]]);
        height[t] = snapshot.height[i];
    }
    StateTexels { rgba: px, relief, height }
}

/// A settlement to draw as a game piece.
#[derive(Clone, Debug)]
pub struct Piece {
    pub pos: LonLat,
    pub population: u32,
    pub highlighted: bool,
}

/// World-space geometry of a piece, for drawing, labels and click tests.
#[derive(Clone, Copy, Debug)]
pub struct PieceFrame {
    pub base: DVec3,
    pub up: DVec3,
    /// Base radius of the piece.
    pub radius: f64,
    pub height: f64,
}

/// Larger settlements get taller, heavier pieces.
pub fn tier_scale(population: u32) -> f64 {
    match population {
        0..=199 => 0.85,
        200..=999 => 1.0,
        1000..=2999 => 1.2,
        _ => 1.4,
    }
}

pub fn piece_frame(piece: &Piece, proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> PieceFrame {
    // About a third of a hex wide close up. Further out the world size grows only
    // slightly with distance, so pieces shrink on screen roughly with the map
    // (ZOOM_EXP = 0: fixed world size; 1: fixed pixel size).
    const PIECE_R0: f64 = 0.0024;
    const DIST_REF: f64 = 0.48;
    const ZOOM_EXP: f64 = 0.2;
    let zoom = (cam_dist / DIST_REF).max(1.0).powf(ZOOM_EXP);
    let radius = PIECE_R0 * zoom * tier_scale(piece.population);
    let tall = piece.population >= 1000;
    PieceFrame {
        base: proj.surface_at(piece.pos, t, relief.at(piece.pos)),
        up: proj.normal(piece.pos, t),
        radius,
        height: radius * if tall { 3.4 } else { 2.0 },
    }
}

/// A piece projected to the screen (points): its base, its top and its base
/// radius in pixels.
#[derive(Clone, Copy, Debug)]
pub struct ScreenPiece {
    pub base: glam::DVec2,
    pub top: glam::DVec2,
    pub radius_px: f64,
}

/// Projects a piece to the screen; `None` when it is behind the curve of the
/// board, behind the camera, or off the viewport. (A piece far outside the
/// view can project to huge coordinates and a huge radius, which used to
/// make it win every hover test on the screen.)
pub fn piece_on_screen(view: &View, f: &PieceFrame) -> Option<ScreenPiece> {
    if f.up.dot(view.eye - f.base) <= 0.0 {
        return None;
    }
    let base = view.project_world(f.base)?;
    let margin = 64.0;
    if !(base.x >= -margin && base.y >= -margin && base.x <= view.size.x + margin && base.y <= view.size.y + margin) {
        return None;
    }
    let top = view.project_world(f.base + f.up * f.height)?;
    let side = f.up.cross(DVec3::Z).normalize_or(DVec3::X);
    let edge = view.project_world(f.base + side * f.radius)?;
    // A piece is never bigger than a fraction of the view, whatever the projection says.
    let cap = view.size.min_element() * 0.25;
    Some(ScreenPiece { base, top, radius_px: (edge - base).length().min(cap) })
}

/// Builds the triangles for all pieces: round huts for small settlements,
/// obelisks for towns (≥ 1000 people).
pub fn piece_vertices(pieces: &[Piece], proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> Vec<PieceVertex> {
    let mut out = Vec::new();
    for piece in pieces {
        let f = piece_frame(piece, proj, relief, t, cam_dist);
        let up = f.up;
        let x = up.cross(DVec3::Z).normalize();
        let z = x.cross(up);
        let at = |a: f64, r: f64, h: f64| f.base + (x * a.cos() + z * a.sin()) * r + up * h;
        let glow = if piece.highlighted { 1.35 } else { 1.0 };
        let mut tri = |a: DVec3, b: DVec3, c: DVec3, colour: Rgb| {
            let mut n = (b - a).cross(c - a).normalize_or_zero();
            // Face away from the piece's axis.
            let centroid = (a + b + c) / 3.0 - f.base;
            if n.dot(centroid - up * centroid.dot(up)) < 0.0 && n.dot(up).abs() < 0.999 {
                n = -n;
            }
            if n.dot(up) < -0.5 {
                n = -n;
            }
            let [r, g, bl] = srgb_to_linear(colour);
            for p in [a, b, c] {
                out.push(PieceVertex {
                    pos: p.as_vec3().to_array(),
                    normal: n.as_vec3().to_array(),
                    colour: [r * glow, g * glow, bl * glow, 1.0],
                });
            }
        };
        let r = f.radius;
        if piece.population >= 1000 {
            // Obelisk: tapered square pillar with a pyramid cap.
            let (stone, cap) = ([0xe8, 0xe0, 0xcc], [0xd0, 0xa0, 0x28]);
            let (h1, h2) = (f.height * 0.82, f.height);
            for k in 0..4 {
                let (a0, a1) = ((k as f64 + 0.5) * FRAC_PI_2, (k as f64 + 1.5) * FRAC_PI_2);
                let (b0, b1) = (at(a0, r * 0.62, 0.0), at(a1, r * 0.62, 0.0));
                let (t0, t1) = (at(a0, r * 0.36, h1), at(a1, r * 0.36, h1));
                tri(b0, b1, t1, stone);
                tri(b0, t1, t0, stone);
                tri(t0, t1, f.base + up * h2, cap);
            }
        } else {
            // Round hut: an octagonal wall under a conical roof.
            let (wall, roof) = ([0xdc, 0xcb, 0xa6], [0x9a, 0x4f, 0x2c]);
            let (h1, h2) = (f.height * 0.42, f.height);
            for k in 0..8 {
                let (a0, a1) = (k as f64 * FRAC_PI_4, (k + 1) as f64 * FRAC_PI_4);
                let (b0, b1) = (at(a0, r * 0.8, 0.0), at(a1, r * 0.8, 0.0));
                let (t0, t1) = (at(a0, r * 0.8, h1), at(a1, r * 0.8, h1));
                tri(b0, b1, t1, wall);
                tri(b0, t1, t0, wall);
                tri(at(a0, r, h1), at(a1, r, h1), f.base + up * h2, roof);
            }
        }
    }
    out
}

/// Points along a centripetal Catmull-Rom spline through `pts`, about
/// `step` degrees apart (the polyline from the pipeline is simplified, so
/// the spline puts the bends back).
pub fn river_spline(pts: &[LonLat], step: f64) -> Vec<LonLat> {
    let p: Vec<glam::DVec2> = pts.iter().map(|q| glam::DVec2::new(q.lon, q.lat)).collect();
    let n = p.len();
    if n < 2 {
        return pts.to_vec();
    }
    let mut out = Vec::new();
    for i in 0..n - 1 {
        let p1 = p[i];
        let p2 = p[i + 1];
        let p0 = if i > 0 { p[i - 1] } else { p1 * 2.0 - p2 };
        let p3 = if i + 2 < n { p[i + 2] } else { p2 * 2.0 - p1 };
        let knot = |a: glam::DVec2, b: glam::DVec2| a.distance(b).sqrt().max(1e-9);
        let t0 = 0.0;
        let t1 = t0 + knot(p0, p1);
        let t2 = t1 + knot(p1, p2);
        let t3 = t2 + knot(p2, p3);
        let k = ((p1.distance(p2) / step).ceil() as usize).max(1);
        for j in 0..k {
            let t = t1 + (t2 - t1) * j as f64 / k as f64;
            let a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0));
            let a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1));
            let a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2));
            let b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0));
            let b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1));
            let c = b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1));
            out.push(LonLat::new(c.x, c.y));
        }
    }
    out.push(pts[n - 1]);
    out
}

/// How far a line is drawn from the map: the world width grows a little with
/// camera distance (like pieces) so lines stay visible zoomed out.
fn line_zoom(cam_dist: f64) -> f64 {
    const DIST_REF: f64 = 0.48;
    const ZOOM_EXP: f64 = 0.6;
    (cam_dist / DIST_REF).max(1.0).powf(ZOOM_EXP)
}

/// Appends a flat ribbon along `pts` (already splined), `half` wide on each
/// side, `lift` above the tiles under it. With `dash` (on, off; degrees of
/// arc) only the "on" stretches are drawn.
#[allow(clippy::too_many_arguments)]
fn ribbon(
    out: &mut Vec<PieceVertex>,
    pts: &[LonLat],
    proj: &Projection,
    relief: &Relief,
    t: f64,
    half: f64,
    lift: f64,
    colour: Rgb,
    dash: Option<(f64, f64)>,
) {
    let m = pts.len();
    if m < 2 {
        return;
    }
    let [cr, cg, cb] = srgb_to_linear(colour);
    // Each point at the highest tile among it and its neighbours, so a line
    // crossing a step stays on top of the higher tile up to its edge.
    let tops: Vec<f64> = pts.iter().map(|p| relief.at(*p)).collect();
    let world: Vec<DVec3> = (0..m)
        .map(|i| {
            let top = tops[i.saturating_sub(1)].max(tops[i]).max(tops[(i + 1).min(m - 1)]);
            proj.surface_at(pts[i], t, top)
        })
        .collect();
    let ups: Vec<DVec3> = pts.iter().map(|p| proj.normal(*p, t)).collect();
    let mut edges = Vec::with_capacity(m);
    let mut along = Vec::with_capacity(m);
    let mut dist = 0.0;
    for i in 0..m {
        let tangent = world[(i + 1).min(m - 1)] - world[i.saturating_sub(1)];
        let side = tangent.cross(ups[i]).normalize_or_zero() * half;
        let c = world[i] + ups[i] * lift;
        edges.push((c - side, c + side));
        if i > 0 {
            dist += (pts[i].lon - pts[i - 1].lon).hypot(pts[i].lat - pts[i - 1].lat);
        }
        along.push(dist);
    }
    for i in 0..m - 1 {
        if let Some((on, off)) = dash {
            if along[i] % (on + off) > on {
                continue;
            }
        }
        let n = ups[i].as_vec3().to_array();
        let (l0, r0) = edges[i];
        let (l1, r1) = edges[i + 1];
        for p in [l0, r0, r1, l0, r1, l1] {
            out.push(PieceVertex { pos: p.as_vec3().to_array(), normal: n, colour: [cr, cg, cb, 1.0] });
        }
    }
}

/// Flat ribbons for the rivers flowing at `year`, lying just above the board
/// top. Perennial rivers are solid; seasonal ones are paler and dashed.
pub fn river_vertices(rivers: &[River], year: Year, proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> Vec<PieceVertex> {
    // Half widths (radians) per size, close up.
    const HALF_WIDTH: [f64; 3] = [0.00030, 0.00045, 0.00065];
    let zoom = line_zoom(cam_dist);
    let mut out = Vec::new();
    for r in rivers {
        let state = r.state_at(year);
        if state == RiverState::Absent {
            continue;
        }
        let seasonal = state == RiverState::Seasonal;
        let colour = if seasonal { [0x6c, 0xa6, 0xd2] } else { [0x2a, 0x62, 0xb0] };
        let half = HALF_WIDTH[(r.size.clamp(1, 3) - 1) as usize] * zoom;
        let dash = seasonal.then_some((0.22, 0.14));
        ribbon(&mut out, &river_spline(&r.points, 0.04), proj, relief, t, half, 0.0004, colour, dash);
    }
    out
}

/// Shoreline rings of the lakes at `year`: a thin dark line showing the
/// lake's real shape over the Water hexes.
pub fn lake_vertices(lakes: &[Lake], year: Year, proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> Vec<PieceVertex> {
    let half = 0.00022 * line_zoom(cam_dist);
    let mut out = Vec::new();
    for l in lakes {
        let Some(shape) = l.shape_at(year) else { continue };
        for ring in &shape.rings {
            let mut closed = ring.clone();
            if closed.first().map(|p| (p.lon, p.lat)) != closed.last().map(|p| (p.lon, p.lat)) {
                closed.push(ring[0]);
            }
            ribbon(&mut out, &river_spline(&closed, 0.04), proj, relief, t, half, 0.00035, [0x1d, 0x48, 0x7a], None);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spline_passes_through_its_points_and_ribbons_lie_on_the_board() {
        let pts = [LonLat::new(30.0, 30.0), LonLat::new(31.0, 31.0), LonLat::new(33.0, 31.0)];
        let s = river_spline(&pts, 0.1);
        assert!(s.len() > 20);
        for p in pts {
            assert!(s.iter().any(|q| (q.lon - p.lon).abs() < 1e-9 && (q.lat - p.lat).abs() < 1e-9));
        }
        let proj = Projection::new(LonLat::new(30.0, 35.0));
        let grid = GridSpec { cols: 12, rows: 12, origin_lon: 28.0, origin_lat: 34.0, w: 0.5773502691896262, h: 0.5 };
        let flat = Relief::flat(&grid);
        let river = |state| River {
            id: 1,
            key: "r".into(),
            name: "R".into(),
            size: 2,
            points: pts.to_vec(),
            state: neolith_core::Timeline::from_keys([(Year(-10000), state)]),
        };
        let verts = river_vertices(&[river(RiverState::Perennial)], Year(-9000), &proj, &flat, 0.0, 1.0);
        assert!(!verts.is_empty() && verts.len().is_multiple_of(3));
        for v in &verts {
            let r = Vec3::from(v.pos).length();
            assert!(r > 1.0 && r < 1.002, "{r}");
        }
        let dashed = river_vertices(&[river(RiverState::Seasonal)], Year(-9000), &proj, &flat, 0.0, 1.0);
        assert!(!dashed.is_empty() && dashed.len() < verts.len());
        assert!(river_vertices(&[river(RiverState::Perennial)], Year(-10001), &proj, &flat, 0.0, 1.0).is_empty());
    }
    use neolith_core::{HexId, Year};

    #[test]
    fn state_texels_are_row_major_with_flags() {
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let n = grid.len();
        let snap = Snapshot {
            year: Year(0),
            terrain: (0..n as u8).collect(),
            koeppen: vec![7; n],
            pop: vec![2; n],
            river: vec![0; n],
            elevation: (100..100 + n as u8).collect(),
            height: (0..n as i16).map(|i| i * 10).collect(),
        };
        let mut sel = Selection::new(n);
        sel.insert(HexId(5));
        let shade: Vec<u8> = (0..n as u8).map(|i| 200 - i).collect();
        let mut lf = vec![None; n];
        lf[0] = Some(Landform::HighMountains);
        let st = state_texels(&grid, &snap, &shade, &lf, Some(&sel), None, Some(HexId(5)));
        let px = &st.rgba;
        // Hex 5 is (col 1, row 2) -> texel index 2 * 4 + 1.
        let o = (2 * 4 + 1) * 4;
        assert_eq!(&px[o..o + 4], &[5, 7, 2, FLAG_SELECTED | FLAG_HOVER]);
        assert_eq!(&px[0..4], &[0, 7, 2, (Landform::HighMountains as u8) << LANDFORM_SHIFT]);
        assert_eq!(st.relief[(2 * 4 + 1) * 2..(2 * 4 + 1) * 2 + 2], [105, 195]);
        assert_eq!(st.height[2 * 4 + 1], 50);
    }

    #[test]
    fn terrain_art_toggle_reaches_the_shader() {
        use crate::board::{camera::Camera, mesh};
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let proj = Projection::new(grid.centre_of_bounds());
        let board = mesh::build(&grid, &proj);
        let view = Camera::initial(&grid).view(&proj, 0.0, glam::DVec2::new(800.0, 600.0));
        let art = |style: &BoardStyle| globals(&view, style, MapMode::Terrain, &grid, &board, 600.0).art;
        let flat = BoardStyle { art_strength: 0.6, ..Default::default() };
        assert_eq!(art(&flat)[..2], [0.6, 0.0]);
        assert_eq!(art(&BoardStyle { terrain_art: ArtMode::Raised, ..flat })[..2], [0.6, 1.0]);
        assert_eq!(art(&BoardStyle { terrain_art: ArtMode::Off, ..flat })[..2], [0.0, 0.0]);
        assert_eq!(art(&BoardStyle { art_blend: false, ..flat })[3], 0.0);
        // A hex one unit away and one unit tall covers focal * height / 2 pixels.
        assert!((art(&flat)[2] - view.focal as f32 * 300.0).abs() < 1e-3);
    }

    #[test]
    fn detail_slots_only_drawn_close_up() {
        use crate::board::{camera::Camera, mesh, renderer::detail_possible};
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let proj = Projection::new(grid.centre_of_bounds());
        let board = mesh::build(&grid, &proj);
        let style = BoardStyle { terrain_art: ArtMode::Raised, ..Default::default() };
        let at = |dist: f64| {
            let mut cam = Camera::initial(&grid);
            cam.dist = dist;
            let view = cam.view(&proj, 0.0, glam::DVec2::new(1280.0, 800.0));
            detail_possible(&globals(&view, &style, MapMode::Terrain, &grid, &board, 800.0))
        };
        assert!(!at(2.15));
        assert!(at(0.07));
    }

    #[test]
    fn pieces_stand_on_the_board() {
        let proj = Projection::new(LonLat::new(25.0, 41.0));
        let grid = GridSpec { cols: 4, rows: 4, origin_lon: 29.0, origin_lat: 36.0, w: 0.5773502691896262, h: 0.5 };
        // A raised board: the piece stands on its hex's top.
        let height = vec![2000i16; grid.len()];
        let relief = Relief::new(&grid, &height, 1e-6);
        for (pop, tris) in [(100, 24), (5000, 12)] {
            let p = Piece { pos: LonLat::new(30.0, 35.0), population: pop, highlighted: false };
            let verts = piece_vertices(std::slice::from_ref(&p), &proj, &relief, 0.0, 1.0);
            assert_eq!(verts.len(), tris * 3);
            let f = piece_frame(&p, &proj, &relief, 0.0, 1.0);
            assert!((f.base.length() - (1.0 + 2000e-6)).abs() < 1e-9);
            for v in &verts {
                let h = (Vec3::from(v.pos).as_dvec3() - f.base).dot(f.up);
                assert!(h > -1e-6 && h <= f.height + 1e-6);
            }
        }
    }

    /// Zoomed in over the Levant, a settlement 1000 km away in Egypt (El
    /// Kortein in the critic's report) must not count as on screen: it used
    /// to project far off the viewport with a huge radius and win every hover.
    #[test]
    fn far_off_screen_pieces_are_culled() {
        use crate::board::camera::Camera;
        let grid = GridSpec { cols: 190, rows: 139, origin_lon: -16.5, origin_lat: 6.1, w: 0.5773502691896262, h: 0.5 };
        let proj = Projection::new(grid.centre_of_bounds());
        let relief = Relief::flat(&grid);
        let mut cam = Camera::initial(&grid);
        cam.target = LonLat::new(35.4, 31.8);
        cam.dist = 0.107;
        let view = cam.view(&proj, 0.0, glam::DVec2::new(1200.0, 800.0));
        let piece = |lon, lat| Piece { pos: LonLat::new(lon, lat), population: 0, highlighted: false };
        let near = piece_frame(&piece(35.4, 31.8), &proj, &relief, 0.0, cam.dist);
        let far = piece_frame(&piece(30.75, 22.75), &proj, &relief, 0.0, cam.dist);
        let on = piece_on_screen(&view, &near).expect("the piece at the target is on screen");
        assert!(on.radius_px <= 200.0);
        assert!(piece_on_screen(&view, &far).is_none());
    }
}
