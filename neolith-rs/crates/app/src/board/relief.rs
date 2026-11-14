//! Tile heights on the CPU side: the same lift the vertex shader gives each
//! hex (snapshot height × scale), so picking, pieces and line overlays sit on
//! the raised tiles.

use super::scene::BoardStyle;
use neolith_core::heightmap::Heightmap;
use neolith_core::{GridSpec, HexId, Landform, LonLat, Terrain};
use std::sync::Arc;

/// The board is a unit sphere: one unit is Earth's radius.
pub const EARTH_RADIUS_M: f64 = 6_371_000.0;

/// Board units per metre of height for `style` (0 with relief off).
pub fn scale(style: &BoardStyle) -> f64 {
    if style.relief {
        style.relief_exaggeration as f64 / EARTH_RADIUS_M
    } else {
        0.0
    }
}

#[derive(Clone, Debug)]
pub struct Relief {
    grid: GridSpec,
    /// Board units per hex.
    lift: Vec<f32>,
    pub min: f64,
    pub max: f64,
    /// One continuous surface (each tile corner at the mean of the three
    /// hexes meeting there, as board.wgsl draws it with edge blending on)
    /// instead of flat tiles with cliffs between them.
    smooth: bool,
    /// Board units per metre (`new`'s scale), for the relief.
    scale: f64,
    /// The real topography the mountains take their shape from on the
    /// smooth board ([`Self::with_dem`]).
    dem: Option<Dem>,
}

/// The real topography (`World::heightmap`) and which hexes are mountains
/// (board.wgsl `dem_mountain`, terrain_art.wgsl `art_is_mountain`).
#[derive(Clone, Debug)]
pub struct Dem {
    pub map: Arc<Heightmap>,
    pub mountain: Vec<bool>,
}

impl Dem {
    /// `terrain`: per hex (`Snapshot::terrain`); `landform`: `World::landform`.
    pub fn new(map: Arc<Heightmap>, terrain: &[u8], landform: &[Option<Landform>]) -> Self {
        let mountain = terrain
            .iter()
            .zip(landform)
            .map(|(&t, l)| {
                t == Terrain::Mountains as u8
                    || (l.is_some_and(|l| l >= Landform::Mountains) && t != Terrain::Water as u8 && t != Terrain::Ice as u8)
            })
            .collect();
        Self { map, mountain }
    }
}

/// Mountain hexes lean towards the real topography from this distance
/// (hex-local units) from any other hex's centre, fully from DEM_REACH_HI.
/// Must match board.wgsl.
const DEM_REACH_LO: f64 = 1.0;
const DEM_REACH_HI: f64 = 1.9;

impl Relief {
    /// `height`: metres per hex (`Snapshot::height`); `scale`: board units per metre.
    pub fn new(grid: &GridSpec, height: &[i16], scale: f64) -> Self {
        let lift: Vec<f32> = height.iter().map(|h| (*h as f64 * scale) as f32).collect();
        let min = lift.iter().copied().fold(0.0f32, f32::min) as f64;
        let max = lift.iter().copied().fold(0.0f32, f32::max) as f64;
        Self { grid: grid.clone(), lift, min, max, smooth: false, scale, dem: None }
    }

    /// No relief: every hex at the board surface.
    pub fn flat(grid: &GridSpec) -> Self {
        Self { grid: grid.clone(), lift: Vec::new(), min: 0.0, max: 0.0, smooth: false, scale: 0.0, dem: None }
    }

    /// Whether it is drawn as one continuous surface ([`Self::smoothed`]).
    pub fn is_smooth(&self) -> bool {
        self.smooth && !self.lift.is_empty()
    }

    pub fn is_flat(&self) -> bool {
        self.min == 0.0 && self.max == 0.0
    }

    pub fn grid(&self) -> &GridSpec {
        &self.grid
    }

    pub fn hex(&self, id: HexId) -> f64 {
        self.lift.get(id.index()).copied().unwrap_or(0.0) as f64
    }

    /// The same heights drawn as one continuous surface (see `smooth`).
    pub fn smoothed(mut self, smooth: bool) -> Self {
        self.smooth = smooth;
        self
    }

    /// Shapes the mountains from `dem` on the smooth surface, as board.wgsl
    /// `surface_lift` does when a heightfield is uploaded. After `smoothed`.
    pub fn with_dem(mut self, dem: Option<Dem>) -> Self {
        self.dem = dem;
        if let (Some(d), true) = (&self.dem, self.smooth) {
            // The summits can stand above every hex's own height.
            let top = d.map.z.iter().copied().max().unwrap_or(0) as f64 * self.scale;
            self.max = self.max.max(top);
        }
        self
    }

    /// Corner `k` of `id` (angle 60°·k): the mean of the three hexes that
    /// meet there (this one and those across edges k − 1 and k); a missing
    /// neighbour counts as this hex. Matches board.wgsl `corner_lift`.
    fn corner(&self, id: HexId, k: usize) -> f64 {
        let own = self.hex(id);
        let nb = |e: usize| self.grid.neighbour(id, e).map_or(own, |n| self.hex(n));
        (own + nb((k + 5) % 6) + nb(k)) / 3.0
    }

    /// The height of the board surface at `p` (0 off the board): the hex's
    /// lift, or with `smooth` the surface interpolated over the fan of
    /// triangles (centre, corner k, corner k + 1) the tile top is made of.
    pub fn at(&self, p: LonLat) -> f64 {
        let Some(id) = self.grid.hex_at(p) else { return 0.0 };
        if !self.smooth || self.lift.is_empty() {
            return self.hex(id);
        }
        // Hex-local coordinates: corners on the unit circle (GridSpec::corners).
        let c = self.grid.centre(id);
        let x = (p.lon - c.lon) / (self.grid.w / 2.0);
        let y = (p.lat - c.lat) / (self.grid.h / 2.0) * (SQRT3 / 2.0);
        let k = sector(x, y);
        let k1 = (k + 1) % 6;
        // Barycentric in the triangle (centre, corner k, corner k + 1).
        // (Every river vertex asks, so no trigonometry: it was most of the
        // time a river rebuild took.)
        let (c0, c1) = (CORNERS[k], CORNERS[k1]);
        let det = SQRT3 / 2.0;
        let a = (x * c1.1 - y * c1.0) / det;
        let b = (c0.0 * y - c0.1 * x) / det;
        let s = (1.0 - a - b) * self.hex(id) + a * self.corner(id, k) + b * self.corner(id, k1);
        match &self.dem {
            Some(dem) => {
                let w = self.dem_weight(dem, id, x, y);
                if w > 0.0 { s + (dem.map.at(p).unwrap_or(0.0) * self.scale - s) * w } else { s }
            }
            None => s,
        }
    }

    /// board.wgsl `dem_weight` at hex-local (x, y) of `id`: by the distance
    /// to the nearest centre of a hex that is not a mountain (this one or a
    /// neighbour; off the board counts as not).
    fn dem_weight(&self, dem: &Dem, id: HexId, x: f64, y: f64) -> f64 {
        let mut d = f64::INFINITY;
        if !dem.mountain.get(id.index()).copied().unwrap_or(false) {
            d = (x * x + y * y).sqrt();
        }
        for e in 0..6 {
            let mountain = self.grid.neighbour(id, e).is_some_and(|n| dem.mountain.get(n.index()).copied().unwrap_or(false));
            if !mountain {
                let a = (e as f64 + 0.5) * std::f64::consts::FRAC_PI_3;
                let (cx, cy) = (SQRT3 * a.cos(), SQRT3 * a.sin());
                d = d.min(((x - cx).powi(2) + (y - cy).powi(2)).sqrt());
            }
        }
        smoothstep(DEM_REACH_LO, DEM_REACH_HI, d)
    }
}

const SQRT3: f64 = 1.732_050_807_568_877_2;

fn smoothstep(lo: f64, hi: f64, x: f64) -> f64 {
    let t = ((x - lo) / (hi - lo)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// The corners of a hex in hex-local coordinates: corner k at 60°·k.
const CORNERS: [(f64, f64); 6] =
    [(1.0, 0.0), (0.5, SQRT3 / 2.0), (-0.5, SQRT3 / 2.0), (-1.0, 0.0), (-0.5, -SQRT3 / 2.0), (0.5, -SQRT3 / 2.0)];

/// Which 60° wedge of a hex (x, y) is in: k for angles 60°·k up to
/// 60°·(k + 1), anticlockwise from +x. On a boundary either wedge gives the
/// same height.
fn sector(x: f64, y: f64) -> usize {
    let t = SQRT3 * x;
    if y >= 0.0 {
        if y < t { 0 } else if y <= -t { 2 } else { 1 }
    } else if y > -t {
        5
    } else if y >= t {
        3
    } else {
        4
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The mountains' blend towards the real topography leaves other hexes
    /// alone, reaches the topography inside a range, and has no seams.
    #[test]
    fn dem_blend_is_seamless_and_local() {
        let grid = GridSpec { cols: 8, rows: 6, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let h: Vec<i16> = (0..grid.len()).map(|i| (i as i16 % 5) * 150).collect();
        let (cols, rows) = (120u32, 100u32);
        let z = (0..rows)
            .flat_map(|r| (0..cols).map(move |c| (1500.0 + 900.0 * (c as f64 * 0.31).sin() * (r as f64 * 0.23).cos()) as i16))
            .collect();
        let map = Arc::new(Heightmap { west: -1.0, north: 11.0, cell: 0.05, cols, rows, z });
        // A block of mountains in the middle.
        let terrain: Vec<u8> = grid
            .ids()
            .map(|id| {
                let (c, r) = grid.col_row(id);
                if (2..6).contains(&c) && (1..5).contains(&r) { Terrain::Mountains as u8 } else { Terrain::Grassland as u8 }
            })
            .collect();
        let dem = Dem::new(map.clone(), &terrain, &vec![None; grid.len()]);
        let plain = Relief::new(&grid, &h, 1e-6).smoothed(true);
        let shaped = Relief::new(&grid, &h, 1e-6).smoothed(true).with_dem(Some(dem.clone()));
        for id in grid.ids() {
            let c = grid.centre(id);
            if dem.mountain[id.index()] {
                continue;
            }
            // Anywhere in a non-mountain hex: untouched.
            for k in 0..6 {
                let q = grid.corners(id)[k];
                let p = LonLat::new(c.lon + 0.97 * (q.lon - c.lon), c.lat + 0.97 * (q.lat - c.lat));
                assert!((shaped.at(p) - plain.at(p)).abs() < 1e-12);
            }
        }
        // Inside the range (every neighbour a mountain): the topography.
        let inner = grid.id_at(3, 2);
        let p = grid.centre(inner);
        assert!((shaped.at(p) - map.at(p).unwrap() * 1e-6).abs() < 1e-9);
        // No seams: a fine walk across the board never jumps.
        let mut last: Option<f64> = None;
        for i in 0..4000 {
            let t = i as f64 / 4000.0;
            let p = LonLat::new(0.1 + t * 3.6, 9.2 - t * 1.4);
            if grid.hex_at(p).is_none() {
                last = None;
                continue;
            }
            let v = shaped.at(p);
            if let Some(l) = last {
                assert!((v - l).abs() < 2e-5, "jump of {} at {p:?}", v - l);
            }
            last = Some(v);
        }
    }

    #[test]
    fn lift_follows_hexes() {
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let h: Vec<i16> = (0..grid.len() as i16).map(|i| i * 100 - 200).collect();
        let r = Relief::new(&grid, &h, 1e-6);
        let id = HexId(5);
        assert!((r.at(grid.centre(id)) - 300e-6).abs() < 1e-9);
        assert!((r.min + 200e-6).abs() < 1e-9 && (r.max - 900e-6).abs() < 1e-9);
        assert!(Relief::flat(&grid).is_flat() && Relief::flat(&grid).at(grid.centre(id)) == 0.0);
    }

    /// The wedge test and corner table give the heights the trigonometry did.
    #[test]
    fn smooth_heights_match_the_trigonometric_form() {
        let grid = GridSpec { cols: 6, rows: 5, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let h: Vec<i16> = (0..grid.len() as i16).map(|i| (i * 37 % 11) * 100 - 300).collect();
        let r = Relief::new(&grid, &h, 1e-6).smoothed(true);
        let reference = |p: LonLat| {
            let id = grid.hex_at(p).unwrap();
            let c = grid.centre(id);
            let x = (p.lon - c.lon) / (grid.w / 2.0);
            let y = (p.lat - c.lat) / (grid.h / 2.0) * (3f64.sqrt() / 2.0);
            let k = (y.atan2(x).to_degrees() / 60.0).floor().rem_euclid(6.0) as usize;
            let (k1, a0, a1) = ((k + 1) % 6, (k as f64 * 60.0).to_radians(), ((k + 1) as f64 * 60.0).to_radians());
            let (c0, c1) = ((a0.cos(), a0.sin()), (a1.cos(), a1.sin()));
            let det = c0.0 * c1.1 - c0.1 * c1.0;
            let a = (x * c1.1 - y * c1.0) / det;
            let b = (c0.0 * y - c0.1 * x) / det;
            (1.0 - a - b) * r.hex(id) + a * r.corner(id, k) + b * r.corner(id, k1)
        };
        let mut n = 0;
        for i in 0..400 {
            for j in 0..300 {
                let p = LonLat::new(0.3 + i as f64 * 0.0071, 7.8 + j as f64 * 0.0069);
                if grid.hex_at(p).is_none() {
                    continue;
                }
                let (got, want) = (r.at(p), reference(p));
                assert!((got - want).abs() < 1e-12, "{p:?}: {got} vs {want}");
                n += 1;
            }
        }
        assert!(n > 50_000);
        // Exactly on the wedges' boundaries and at the centre.
        for id in [grid.id_at(2, 2), grid.id_at(3, 1)] {
            let c = grid.centre(id);
            for k in 0..6 {
                let a = (k as f64 * 60.0).to_radians();
                let p = LonLat::new(c.lon + a.cos() * grid.w / 4.0, c.lat + a.sin() * grid.h / 4.0 / (3f64.sqrt() / 2.0));
                assert!((r.at(p) - reference(p)).abs() < 1e-12);
            }
            assert!((r.at(c) - r.hex(id)).abs() < 1e-12);
        }
    }

    #[test]
    fn smooth_surface_is_continuous() {
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 0.0, origin_lat: 10.0, w: 0.5773502691896262, h: 0.5 };
        let h: Vec<i16> = (0..grid.len() as i16).map(|i| (i * 37 % 11) * 100).collect();
        let r = Relief::new(&grid, &h, 1e-6).smoothed(true);
        let id = grid.id_at(1, 1);
        // The centre keeps the hex's own height.
        assert!((r.at(grid.centre(id)) - r.hex(id)).abs() < 1e-12);
        for e in 0..6 {
            let Some(n) = grid.neighbour(id, e) else { continue };
            let cs = grid.corners(id);
            let (a, b) = (cs[e], cs[(e + 1) % 6]);
            let mid = LonLat::new((a.lon + b.lon) / 2.0, (a.lat + b.lat) / 2.0);
            // Just inside each hex either side of the shared edge: the same height.
            let towards = |c: LonLat, t: f64| LonLat::new(mid.lon + (c.lon - mid.lon) * t, mid.lat + (c.lat - mid.lat) * t);
            let (here, there) = (r.at(towards(grid.centre(id), 1e-6)), r.at(towards(grid.centre(n), 1e-6)));
            assert!((here - there).abs() < 1e-9, "edge {e}: {here} vs {there}");
            // And halfway between the two corner means.
            let want = (r.corner(id, e) + r.corner(id, (e + 1) % 6)) / 2.0;
            assert!((here - want).abs() < 1e-9, "edge {e}: {here} vs {want}");
        }
    }
}
