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
}

impl Relief {
    /// `height`: metres per hex (`Snapshot::height`); `scale`: board units per metre.
    pub fn new(grid: &GridSpec, height: &[i16], scale: f64) -> Self {
        let lift: Vec<f32> = height.iter().map(|h| (*h as f64 * scale) as f32).collect();
        let min = lift.iter().copied().fold(0.0f32, f32::min) as f64;
        let max = lift.iter().copied().fold(0.0f32, f32::max) as f64;
        Self { grid: grid.clone(), lift, min, max }
    }

    /// No relief: every hex at the board surface.
    pub fn flat(grid: &GridSpec) -> Self {
        Self { grid: grid.clone(), lift: Vec::new(), min: 0.0, max: 0.0 }
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

    /// The lift of the hex under `p` (0 off the board).
    pub fn at(&self, p: LonLat) -> f64 {
        self.grid.hex_at(p).map_or(0.0, |id| self.hex(id))
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
}
