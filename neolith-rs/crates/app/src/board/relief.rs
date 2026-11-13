//! Tile heights on the CPU side: the same lift the vertex shader gives each
//! hex (snapshot height × scale), so picking, pieces and line overlays sit on
//! the raised tiles.

use super::scene::BoardStyle;
use neolith_core::{GridSpec, HexId, LonLat};

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
}

impl Relief {
    /// `height`: metres per hex (`Snapshot::height`); `scale`: board units per metre.
    pub fn new(grid: &GridSpec, height: &[i16], scale: f64) -> Self {
        let lift: Vec<f32> = height.iter().map(|h| (*h as f64 * scale) as f32).collect();
        let min = lift.iter().copied().fold(0.0f32, f32::min) as f64;
        let max = lift.iter().copied().fold(0.0f32, f32::max) as f64;
        Self { grid: grid.clone(), lift, min, max, smooth: false }
    }

    /// No relief: every hex at the board surface.
    pub fn flat(grid: &GridSpec) -> Self {
        Self { grid: grid.clone(), lift: Vec::new(), min: 0.0, max: 0.0, smooth: false }
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
        let y = (p.lat - c.lat) / (self.grid.h / 2.0) * (3f64.sqrt() / 2.0);
        let k = (y.atan2(x).to_degrees() / 60.0).floor().rem_euclid(6.0) as usize;
        let (k1, a0, a1) = ((k + 1) % 6, (k as f64 * 60.0).to_radians(), ((k + 1) as f64 * 60.0).to_radians());
        let (c0, c1) = ((a0.cos(), a0.sin()), (a1.cos(), a1.sin()));
        let det = c0.0 * c1.1 - c0.1 * c1.0;
        let a = (x * c1.1 - y * c1.0) / det;
        let b = (c0.0 * y - c0.1 * x) / det;
        (1.0 - a - b) * self.hex(id) + a * self.corner(id, k) + b * self.corner(id, k1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
