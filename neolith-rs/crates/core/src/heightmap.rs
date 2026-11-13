//! A coarse elevation raster under the hexes, for drawing relief: each hex
//! has one median elevation ([`crate::World::elevation`]), which shows a
//! range as a plateau with no ridges in it. This keeps a regular lon/lat
//! grid of a few samples per hex (today's topography, from the pipeline's
//! ETOPO1 subset) so the board can light ridges and valleys and put snow on
//! peaks. It is drawn, never simulated: every rule reads the hexes.

use crate::grid::LonLat;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Heightmap {
    /// Longitude of the west edge of the first column (degrees).
    pub west: f64,
    /// Latitude of the north edge of the first row (degrees).
    pub north: f64,
    /// Cell size in degrees, both ways.
    pub cell: f64,
    pub cols: u32,
    pub rows: u32,
    /// Metres, row-major from the north-west; rows run south.
    pub z: Vec<i16>,
}

impl Heightmap {
    /// Is it well formed?
    pub fn validate(&self) -> Result<(), String> {
        if !(self.cell > 0.0 && self.cell.is_finite()) {
            return Err(format!("heightmap cell size {} is not positive", self.cell));
        }
        if self.z.len() != self.cols as usize * self.rows as usize {
            return Err(format!("heightmap has {} heights for {} x {} cells", self.z.len(), self.cols, self.rows));
        }
        Ok(())
    }

    /// The height at `p` (metres), interpolated between cell centres, or
    /// `None` outside the raster.
    pub fn at(&self, p: LonLat) -> Option<f64> {
        let x = (p.lon - self.west) / self.cell - 0.5;
        let y = (self.north - p.lat) / self.cell - 0.5;
        if !(x >= -0.5 && y >= -0.5 && x <= self.cols as f64 - 0.5 && y <= self.rows as f64 - 0.5) {
            return None;
        }
        let (x, y) = (x.clamp(0.0, (self.cols - 1) as f64), y.clamp(0.0, (self.rows - 1) as f64));
        let (x0, y0) = (x.floor() as u32, y.floor() as u32);
        let (x1, y1) = ((x0 + 1).min(self.cols - 1), (y0 + 1).min(self.rows - 1));
        let (fx, fy) = (x - x0 as f64, y - y0 as f64);
        let z = |c: u32, r: u32| self.z[(r * self.cols + c) as usize] as f64;
        let top = z(x0, y0) * (1.0 - fx) + z(x1, y0) * fx;
        let bottom = z(x0, y1) * (1.0 - fx) + z(x1, y1) * fx;
        Some(top * (1.0 - fy) + bottom * fy)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interpolates_between_cell_centres() {
        // 2 x 2 cells of 1°, from 10°E, 50°N.
        let h = Heightmap { west: 10.0, north: 50.0, cell: 1.0, cols: 2, rows: 2, z: vec![0, 100, 200, 300] };
        assert!(h.validate().is_ok());
        assert_eq!(h.at(LonLat::new(10.5, 49.5)), Some(0.0));
        assert_eq!(h.at(LonLat::new(11.5, 48.5)), Some(300.0));
        assert_eq!(h.at(LonLat::new(11.0, 49.5)), Some(50.0));
        assert_eq!(h.at(LonLat::new(11.0, 49.0)), Some(150.0));
        assert_eq!(h.at(LonLat::new(9.0, 49.0)), None);
        assert!(Heightmap { z: vec![0; 3], ..h }.validate().is_err());
    }
}
