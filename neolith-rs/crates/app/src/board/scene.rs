//! Turns app state into what the renderer consumes: the uniform block, the
//! per-hex state texels and the settlement piece triangles. (Rivers and
//! lake shores are in [`super::lines`].)

use super::camera::View;
use super::mesh::BoardMesh;
use super::projection::Projection;
use super::relief::{self, Relief};
use super::renderer::{Globals, PieceVertex};
use crate::palette::Rgb;
use glam::{DVec3, Vec3};
use std::f64::consts::{FRAC_PI_2, TAU};
use neolith_core::{GridSpec, Landform, LonLat, MapMode, Selection, Snapshot, Year};

pub const FLAG_SELECTED: u8 = 1;
pub const FLAG_HOVER: u8 = 2;
pub const FLAG_LASSO: u8 = 4;
/// Bits 3-4 of the flags byte: the hex's [`Landform`] (0 = flat or unknown).
pub const LANDFORM_SHIFT: u8 = 3;
/// Survey intensity 1 (thinly surveyed) and 0 (hardly surveyed): few dated
/// records of any period, so an absence of sites there says little.
pub const FLAG_SURVEY_THIN: u8 = 1 << 5;
pub const FLAG_SURVEY_NONE: u8 = 1 << 6;

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
    /// Hatch land where few dated records of any period exist, so an
    /// absence of sites there is not read as an absence of people.
    pub survey: bool,
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
            survey: true,
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

/// Radius of a hex on screen, in points, at the camera's target (the same
/// measure board.wgsl fades the grout and borders by).
pub fn hex_px(view: &View, grid: &GridSpec, cam_dist: f64) -> f64 {
    let unit = (grid.h / 2.0).to_radians() / (3f64.sqrt() / 2.0);
    unit * view.focal * view.size.y / 2.0 / cam_dist.max(1e-6)
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
        hex: [
            (grid.w / 2.0).to_radians() as f32,
            (grid.h / 2.0).to_radians() as f32,
            relief::scale(style) as f32,
            if style.survey { 1.0 } else { 0.0 },
        ],
    }
}

/// Per-hex state for the GPU, both row-major `cols × rows`.
pub struct StateTexels {
    /// RGBA8: terrain, koeppen, population, flags.
    pub rgba: Vec<u8>,
    /// RGBA8: elevation band, hillshade ([`neolith_core::elevation::hillshade`]),
    /// productivity band, and in four bits each (15 = no data) the
    /// biodiversity band (low) and expected-population band (high).
    pub relief: Vec<u8>,
    /// R16: tile surface height in metres (`Snapshot::height`).
    pub height: Vec<i16>,
}

/// Two bands in one byte, four bits each; anything over 14 (so
/// [`neolith_core::NO_DATA`]) becomes 15, which the shader reads as no data.
fn pack_bands(low: u8, high: u8) -> u8 {
    low.min(15) | high.min(15) << 4
}

#[allow(clippy::too_many_arguments)]
pub fn state_texels(
    grid: &GridSpec,
    snapshot: &Snapshot,
    hillshade: &[u8],
    landform: &[Option<Landform>],
    survey: &[u8],
    selection: Option<&Selection>,
    lasso: Option<&Selection>,
    hover: Option<neolith_core::HexId>,
) -> StateTexels {
    let (cols, rows) = (grid.cols as usize, grid.rows as usize);
    let mut px = vec![0u8; cols * rows * 4];
    let mut relief = vec![0u8; cols * rows * 4];
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
        match survey.get(i) {
            Some(0) => flags |= FLAG_SURVEY_NONE,
            Some(1) => flags |= FLAG_SURVEY_THIN,
            _ => {}
        }
        let t = r as usize * cols + c as usize;
        px[t * 4..t * 4 + 4].copy_from_slice(&[snapshot.terrain[i], snapshot.koeppen[i], snapshot.pop[i], flags]);
        relief[t * 4..t * 4 + 4].copy_from_slice(&[snapshot.elevation[i], hillshade[i], snapshot.npp[i], pack_bands(snapshot.biodiversity[i], snapshot.expected[i])]);
        height[t] = snapshot.height[i];
    }
    StateTexels { rgba: px, relief, height }
}

/// The evidence texture: per-hex `codes` (file order, e.g.
/// [`neolith_core::EvidenceLayer::codes_at`]) laid out row-major
/// `cols × rows`. Missing codes (no layer) are [`neolith_core::evidence::NO_VALUE`].
pub fn evidence_texels(grid: &GridSpec, codes: &[u8]) -> Vec<u8> {
    let cols = grid.cols as usize;
    let mut out = vec![neolith_core::evidence::NO_VALUE; cols * grid.rows as usize];
    for id in grid.ids() {
        let (c, r) = grid.col_row(id);
        if let Some(code) = codes.get(id.index()) {
            out[r as usize * cols + c as usize] = *code;
        }
    }
    out
}

/// A settlement to draw as a game piece.
#[derive(Clone, Debug, PartialEq)]
pub struct Piece {
    pub pos: LonLat,
    /// Recorded population this year, 0 when there is no figure.
    pub population: u32,
    /// The site's inferred importance (0-3); sizes the piece when there is
    /// no population figure.
    pub importance: u8,
    /// How firmly the site is attested (0-2); 0 draws a paler piece.
    pub evidence: u8,
    pub highlighted: bool,
}

impl Piece {
    pub fn new(s: &neolith_core::Settlement, year: Year) -> Self {
        Piece {
            pos: s.pos,
            population: s.population_at(year).unwrap_or(0),
            importance: s.importance,
            evidence: s.evidence,
            highlighted: false,
        }
    }

    /// Label priority 0-3: from the population figure when there is one,
    /// else from the inferred importance.
    pub fn rank(&self) -> u8 {
        match self.population {
            0 => self.importance.min(3),
            _ => self.size_tier(),
        }
    }

    /// Size tier 0-3, from the recorded population alone: importance is
    /// inferred, so it never makes a piece bigger (it earns a star instead).
    pub fn size_tier(&self) -> u8 {
        match self.population {
            0..=199 => 0,
            200..=999 => 1,
            1000..=2999 => 2,
            _ => 3,
        }
    }

    /// Drawn as a standing stone: only a recorded population of a town's
    /// size earns one. Everything else is a campfire on trampled ground.
    pub fn monolith(&self) -> bool {
        self.population >= 1000
    }

    /// An important site (inferred importance 3) carries a star above its
    /// piece, whichever piece that is.
    pub fn starred(&self) -> bool {
        self.importance >= 3
    }
}

/// World-space geometry of a piece, for drawing, labels and click tests.
#[derive(Clone, Copy, Debug)]
pub struct PieceFrame {
    pub base: DVec3,
    pub up: DVec3,
    /// Base radius of the piece.
    pub radius: f64,
    /// Height of the piece itself (stone or fire and smoke).
    pub body: f64,
    /// Full height, including the star of an important site.
    pub height: f64,
}

/// Larger settlements get taller, heavier pieces.
pub fn tier_scale(tier: u8) -> f64 {
    match tier {
        0 => 0.85,
        1 => 1.0,
        2 => 1.2,
        _ => 1.4,
    }
}

/// Heights in piece radii: the standing stone, the campfire with its smoke,
/// and the room a star takes above either.
const MONOLITH_H: f64 = 2.9;
const CAMPFIRE_H: f64 = 1.7;
const STAR_H: f64 = 1.45;

pub fn piece_frame(piece: &Piece, proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> PieceFrame {
    // About a third of a hex wide close up. Further out the world size grows only
    // slightly with distance, so pieces shrink on screen roughly with the map
    // (ZOOM_EXP = 0: fixed world size; 1: fixed pixel size).
    // Closer than DIST_REF they shrink in the world (NEAR_EXP), so a camp
    // doesn't grow to fill its hex and bury its neighbours: on screen a
    // piece still grows as you close in, but slower than the map does.
    const PIECE_R0: f64 = 0.0024;
    const DIST_REF: f64 = 0.48;
    const ZOOM_EXP: f64 = 0.2;
    const NEAR_EXP: f64 = 0.25;
    let rel = cam_dist / DIST_REF;
    let zoom = if rel >= 1.0 { rel.powf(ZOOM_EXP) } else { rel.max(1e-3).powf(NEAR_EXP) };
    let radius = PIECE_R0 * zoom * tier_scale(piece.size_tier());
    let body = radius * if piece.monolith() { MONOLITH_H } else { CAMPFIRE_H };
    PieceFrame {
        base: proj.surface_at(piece.pos, t, relief.at(piece.pos)),
        up: proj.normal(piece.pos, t),
        radius,
        body,
        height: body + if piece.starred() { radius * STAR_H } else { 0.0 },
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

/// Builds the triangles for all pieces: a rough standing stone where a
/// population of 1000 or more is recorded, a smouldering campfire on
/// trampled dirt everywhere else, and a star over either when the site is
/// important (inferred importance 3).
pub fn piece_vertices(pieces: &[Piece], proj: &Projection, relief: &Relief, t: f64, cam_dist: f64) -> Vec<PieceVertex> {
    let mut out = Vec::new();
    for piece in pieces {
        let f = piece_frame(piece, proj, relief, t, cam_dist);
        let up = f.up;
        let x = up.cross(DVec3::Z).normalize();
        let z = x.cross(up);
        let dir = |a: f64| x * a.cos() + z * a.sin();
        let at = |a: f64, r: f64, h: f64| f.base + dir(a) * r + up * h;
        // Stable per-site variation, so no two stones or fires match.
        let rnd = |k: f64| ((piece.pos.lon * 12.9898 + piece.pos.lat * 78.233 + k * 37.719).sin() * 43758.5453).rem_euclid(1.0);
        let glow = if piece.highlighted { 1.35 } else { 1.0 };
        // A site known from a single date is drawn paler: tentative.
        let pale = if piece.evidence == 0 { 0.45 } else { 0.0 };
        // `emit` 0 shades the face by its own normal; above 0 the face is lit
        // as if facing up and brightened by that factor (embers, the star).
        // `alpha` is the opacity at each corner (smoke thins as it rises).
        let mut tri = |a: DVec3, b: DVec3, c: DVec3, colour: Rgb, emit: f64, alpha: [f32; 3]| {
            let mut n = (b - a).cross(c - a).normalize_or_zero();
            // Face away from the piece's axis.
            let centroid = (a + b + c) / 3.0 - f.base;
            if n.dot(centroid - up * centroid.dot(up)) < 0.0 && n.dot(up).abs() < 0.999 {
                n = -n;
            }
            if n.dot(up) < -0.5 {
                n = -n;
            }
            let gain = if emit > 0.0 {
                n = up;
                glow * emit
            } else {
                glow
            } as f32;
            let [r, g, bl] = srgb_to_linear(colour).map(|c| c + (1.0 - c) * pale);
            for (p, alpha) in [a, b, c].into_iter().zip(alpha) {
                out.push(PieceVertex {
                    pos: p.as_vec3().to_array(),
                    normal: n.as_vec3().to_array(),
                    colour: [r * gain, g * gain, bl * gain, alpha],
                });
            }
        };
        const SOLID: [f32; 3] = [1.0; 3];
        let r = f.radius;
        let h = f.body;
        let turn = rnd(0.0) * TAU;
        if piece.monolith() {
            // Standing stone: an unhewn five-sided boulder, leaning a little,
            // lumpy at the shoulder and broken off unevenly at the top.
            let (stone, crown) = ([0x8d, 0x89, 0x7f], [0xa9, 0xa5, 0x98]);
            let lean = dir(rnd(1.0) * TAU) * r * 0.22;
            const N: usize = 5;
            let ring = |k: usize, rad: f64, height: f64, lean_part: f64, salt: f64| {
                let a = turn + (k % N) as f64 * TAU / N as f64 + (rnd(salt + (k % N) as f64) - 0.5) * 0.5;
                let j = 0.8 + 0.4 * rnd(salt + 10.0 + (k % N) as f64);
                at(a, rad * j, height) + lean * lean_part
            };
            let foot = |k| ring(k, r * 0.62, 0.0, 0.0, 2.0);
            let shoulder = |k| ring(k, r * 0.66, h * 0.5, 0.45, 20.0);
            // A blunt, slanting top: one side of the rim stands well above the other.
            let top = |k: usize| ring(k, r * 0.46, h * (0.74 + 0.22 * rnd(40.0 + (k % N) as f64)), 0.9, 40.0);
            let tip = f.base + up * h * 0.97 + lean * 1.3;
            for k in 0..N {
                tri(foot(k), foot(k + 1), shoulder(k + 1), stone, 0.0, SOLID);
                tri(foot(k), shoulder(k + 1), shoulder(k), stone, 0.0, SOLID);
                tri(shoulder(k), shoulder(k + 1), top(k + 1), stone, 0.0, SOLID);
                tri(shoulder(k), top(k + 1), top(k), stone, 0.0, SOLID);
                tri(top(k), top(k + 1), tip, crown, 0.0, SOLID);
            }
        } else {
            // Trampled dirt: a low, ragged patch of bare earth.
            let (dirt, ash, log, ember, smoke) =
                ([0x5c, 0x47, 0x33], [0x2b, 0x27, 0x24], [0x3d, 0x2c, 0x20], [0xff, 0x74, 0x18], [0xc9, 0xc5, 0xbd]);
            const N: usize = 10;
            let rim = |k: usize| {
                let k = k % N;
                at(turn + k as f64 * TAU / N as f64, r * (0.85 + 0.3 * rnd(2.0 + k as f64)), r * 0.03)
            };
            let hub = f.base + up * r * 0.1;
            for k in 0..N {
                tri(rim(k), rim(k + 1), hub, dirt, 0.0, SOLID);
            }
            // The hearth: a bed of ash with embers still glowing in it.
            for k in 0..6 {
                let (a0, a1) = (turn + k as f64 * TAU / 6.0, turn + (k + 1) as f64 * TAU / 6.0);
                tri(at(a0, r * 0.42, r * 0.11), at(a1, r * 0.42, r * 0.11), f.base + up * r * 0.16, ash, 0.0, SOLID);
                tri(at(a0, r * 0.2, r * 0.15), at(a1, r * 0.2, r * 0.15), f.base + up * r * 0.4, ember, 1.5, SOLID);
            }
            // Charred logs leaning in over the embers.
            for k in 0..4 {
                let a = turn + 0.4 + k as f64 * FRAC_PI_2;
                tri(at(a - 0.22, r * 0.46, r * 0.12), at(a + 0.22, r * 0.46, r * 0.12), at(a, r * 0.04, r * 0.36), log, 0.0, SOLID);
            }
            // A thin wisp of smoke, drifting as it rises and thinning to
            // nothing (the piece pipeline turns opacity into MSAA coverage).
            let drift = dir(rnd(1.0) * TAU);
            let sway = drift.cross(up);
            const SEGS: usize = 5;
            let puff = |j: usize, k: usize| {
                let u = j as f64 / SEGS as f64;
                let centre = up * (r * 0.4 + (h - r * 0.4) * u) + drift * r * 0.35 * u * u + sway * r * 0.1 * (u * 5.0).sin();
                let rad = r * (0.04 + 0.08 * (u * std::f64::consts::PI).sin());
                f.base + centre + dir(turn + k as f64 * TAU / 3.0) * rad
            };
            let thin = |j: usize| (0.85 * (1.0 - j as f64 / SEGS as f64).powf(0.8)) as f32;
            for j in 0..SEGS {
                let (a0, a1) = (thin(j), thin(j + 1));
                for k in 0..3 {
                    tri(puff(j, k), puff(j, k + 1), puff(j + 1, k + 1), smoke, 0.0, [a0, a0, a1]);
                    tri(puff(j, k), puff(j + 1, k + 1), puff(j + 1, k), smoke, 0.0, [a0, a1, a1]);
                }
            }
        }
        if piece.starred() {
            // A five-pointed star floating over the piece, as two crossed
            // upright cut-outs so it reads from any side.
            let gold = [0xff, 0xd0, 0x3a];
            let centre = f.base + up * (h + r * 0.8);
            for plane in [dir(turn), dir(turn + FRAC_PI_2)] {
                let point = |i: usize| {
                    let a = i as f64 * std::f64::consts::PI / 5.0;
                    let rad = r * if i % 2 == 0 { 0.62 } else { 0.26 };
                    centre + (plane * a.sin() + up * a.cos()) * rad
                };
                for i in 0..10 {
                    tri(centre, point(i), point(i + 1), gold, 1.5, SOLID);
                }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evidence_texels_are_row_major() {
        let grid = GridSpec { cols: 3, rows: 2, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let codes: Vec<u8> = (0..grid.len() as u8).collect();
        let tex = evidence_texels(&grid, &codes);
        assert_eq!(tex.len(), 6);
        for id in grid.ids() {
            let (c, r) = grid.col_row(id);
            assert_eq!(tex[r as usize * 3 + c as usize], codes[id.index()]);
        }
        assert!(evidence_texels(&grid, &[]).iter().all(|c| *c == neolith_core::evidence::NO_VALUE));
    }

    #[test]
    fn spline_passes_through_its_points() {
        let pts = [LonLat::new(30.0, 30.0), LonLat::new(31.0, 31.0), LonLat::new(33.0, 31.0)];
        let s = river_spline(&pts, 0.1);
        assert!(s.len() > 20);
        for p in pts {
            assert!(s.iter().any(|q| (q.lon - p.lon).abs() < 1e-9 && (q.lat - p.lat).abs() < 1e-9));
        }
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
            npp: vec![6; n],
            biodiversity: vec![3; n],
            expected: vec![neolith_core::NO_DATA; n],
            shore_km: vec![0; n],
            height: (0..n as i16).map(|i| i * 10).collect(),
        };
        let mut sel = Selection::new(n);
        sel.insert(HexId(5));
        let shade: Vec<u8> = (0..n as u8).map(|i| 200 - i).collect();
        let mut lf = vec![None; n];
        lf[0] = Some(Landform::HighMountains);
        let mut survey = vec![2u8; n];
        survey[0] = 0;
        survey[5] = 1;
        let st = state_texels(&grid, &snap, &shade, &lf, &survey, Some(&sel), None, Some(HexId(5)));
        let px = &st.rgba;
        // Hex 5 is (col 1, row 2) -> texel index 2 * 4 + 1.
        let o = (2 * 4 + 1) * 4;
        assert_eq!(&px[o..o + 4], &[5, 7, 2, FLAG_SELECTED | FLAG_HOVER | FLAG_SURVEY_THIN]);
        assert_eq!(&px[0..4], &[0, 7, 2, (Landform::HighMountains as u8) << LANDFORM_SHIFT | FLAG_SURVEY_NONE]);
        // Without a survey layer no hex is flagged.
        let st = state_texels(&grid, &snap, &shade, &lf, &[], None, None, None);
        assert!(st.rgba.chunks(4).all(|t| t[3] & (FLAG_SURVEY_NONE | FLAG_SURVEY_THIN) == 0));
        assert_eq!(st.relief[(2 * 4 + 1) * 4..(2 * 4 + 1) * 4 + 4], [105, 195, 6, 0xf3]);
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
    fn props_culled_to_visible_land_and_detail_only_close_up() {
        use crate::board::{camera::Camera, mesh, renderer::select_props};
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let proj = Projection::new(grid.centre_of_bounds());
        let board = mesh::build(&grid, &proj);
        let style = BoardStyle { terrain_art: ArtMode::Raised, ..Default::default() };
        use neolith_core::Terrain;
        let state = |t: Terrain| [Terrain::ALL.iter().position(|x| *x == t).unwrap() as u8, 0, 0, 0].repeat(grid.len());
        // (props drawn, of which with the detail slots)
        let at = |dist: f64, rgba: &[u8]| {
            let mut cam = Camera::initial(&grid);
            cam.dist = dist;
            let view = cam.view(&proj, 0.0, glam::DVec2::new(1280.0, 800.0));
            let g = globals(&view, &style, MapMode::Terrain, &grid, &board, 800.0);
            let mut out = Vec::new();
            let detail = select_props(&board.props, rgba, grid.cols as usize, &g, &mut out);
            (out.len(), detail as usize)
        };
        let land = state(Terrain::Grassland);
        let (far, far_detail) = at(2.15, &land);
        assert_eq!(far_detail, 0, "no detail slots from far away");
        assert!(far <= grid.len());
        let (near, near_detail) = at(0.07, &land);
        assert!(near > 0 && near_detail > 0, "close up, the hexes in view get the detail slots");
        assert_eq!(at(0.07, &state(Terrain::Water)), (0, 0), "water has no props");
    }

    #[test]
    fn population_picks_the_piece_and_importance_only_adds_a_star() {
        let p = |population, importance| Piece { pos: LonLat::new(0.0, 0.0), population, importance, evidence: 2, highlighted: false };
        // Only a recorded population of 1000 or more raises a stone.
        assert!(p(5000, 0).monolith() && p(1000, 0).monolith());
        assert!(!p(150, 3).monolith() && !p(0, 3).monolith() && !p(999, 3).monolith());
        // Importance never changes the piece or its size, only the star.
        assert!(p(0, 3).starred() && p(5000, 3).starred() && !p(0, 2).starred() && !p(5000, 2).starred());
        assert_eq!(p(0, 3).size_tier(), p(0, 0).size_tier());
        assert_eq!((p(150, 3).size_tier(), p(5000, 0).size_tier()), (0, 3));
        // Label priority: a figure wins, importance stands in without one.
        assert_eq!((p(150, 3).rank(), p(5000, 0).rank(), p(0, 2).rank()), (0, 3, 2));
    }

    #[test]
    fn pieces_stand_on_the_board() {
        let proj = Projection::new(LonLat::new(25.0, 41.0));
        let grid = GridSpec { cols: 4, rows: 4, origin_lon: 29.0, origin_lat: 36.0, w: 0.5773502691896262, h: 0.5 };
        // A raised board: the piece stands on its hex's top.
        let height = vec![2000i16; grid.len()];
        let relief = Relief::new(&grid, &height, 1e-6);
        // Campfire 56 triangles, standing stone 25, the star 20 more.
        for (pop, importance, tris) in [(100, 1, 56), (5000, 1, 25), (0, 3, 76), (5000, 3, 45)] {
            let p = Piece { pos: LonLat::new(30.0, 35.0), population: pop, importance, evidence: 2, highlighted: false };
            let verts = piece_vertices(std::slice::from_ref(&p), &proj, &relief, 0.0, 1.0);
            assert_eq!(verts.len(), tris * 3);
            // Only a campfire's smoke is see-through.
            assert_eq!(verts.iter().any(|v| v.colour[3] < 1.0), pop < 1000);
            let f = piece_frame(&p, &proj, &relief, 0.0, 1.0);
            assert!((f.base.length() - (1.0 + 2000e-6)).abs() < 1e-9);
            for v in &verts {
                let h = (Vec3::from(v.pos).as_dvec3() - f.base).dot(f.up);
                assert!(h > -1e-6 && h <= f.height + 1e-6);
            }
        }
    }

    #[test]
    fn pieces_shrink_in_the_world_close_up() {
        let proj = Projection::new(LonLat::new(25.0, 41.0));
        let grid = GridSpec { cols: 4, rows: 4, origin_lon: 29.0, origin_lat: 36.0, w: 0.5773502691896262, h: 0.5 };
        let relief = Relief::flat(&grid);
        let p = Piece { pos: LonLat::new(30.0, 35.0), population: 0, importance: 1, evidence: 2, highlighted: false };
        let r = |dist: f64| piece_frame(&p, &proj, &relief, 0.0, dist).radius;
        // Smaller in the world, but still larger on screen (radius / distance).
        assert!(r(0.06) < r(0.12) && r(0.12) < r(0.48));
        assert!(r(0.06) / 0.06 > r(0.12) / 0.12 && r(0.12) / 0.12 > r(0.48) / 0.48);
        assert!(r(1.5) > r(0.48));
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
        let piece = |lon, lat| Piece { pos: LonLat::new(lon, lat), population: 0, importance: 1, evidence: 2, highlighted: false };
        let near = piece_frame(&piece(35.4, 31.8), &proj, &relief, 0.0, cam.dist);
        let far = piece_frame(&piece(30.75, 22.75), &proj, &relief, 0.0, cam.dist);
        let on = piece_on_screen(&view, &near).expect("the piece at the target is on screen");
        assert!(on.radius_px <= 200.0);
        assert!(piece_on_screen(&view, &far).is_none());
    }
}
