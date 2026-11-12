//! Lakes whose extent changes over time. The pipeline turns the hexes a lake
//! covers into Water in the terrain timelines; this holds the real shoreline
//! at each level, which is drawn over the hexes.

use crate::geom::point_in_polygon;
use crate::grid::LonLat;
use crate::time::Year;
use crate::timeline::Timeline;
use serde::{Deserialize, Serialize};

/// `Lake::shape` value for "no lake drawn".
pub const NO_SHAPE: u16 = u16::MAX;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct LakeShape {
    /// Water level, metres above sea level.
    pub level: f32,
    /// Closed shoreline rings (islands are rings too).
    pub rings: Vec<Vec<LonLat>>,
}

impl LakeShape {
    /// Even-odd test across all rings, so islands are dry.
    pub fn contains(&self, p: LonLat) -> bool {
        let mut inside = false;
        for r in &self.rings {
            let poly: Vec<[f64; 2]> = r.iter().map(|q| [q.lon, q.lat]).collect();
            inside ^= point_in_polygon(&poly, [p.lon, p.lat]);
        }
        inside
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Lake {
    /// Catalogue key (`megachad`).
    pub key: String,
    pub name: String,
    pub shapes: Vec<LakeShape>,
    /// Index into `shapes` in effect from each key ([`NO_SHAPE`]: none).
    pub shape: Timeline<u16>,
}

impl Lake {
    pub fn shape_at(&self, year: Year) -> Option<&LakeShape> {
        self.shape.at(year).and_then(|i| self.shapes.get(i as usize))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn square(x0: f64, y0: f64, s: f64) -> Vec<LonLat> {
        vec![LonLat::new(x0, y0), LonLat::new(x0 + s, y0), LonLat::new(x0 + s, y0 + s), LonLat::new(x0, y0 + s)]
    }

    #[test]
    fn islands_are_dry_and_shapes_follow_time() {
        let high = LakeShape { level: 329.0, rings: vec![square(0.0, 0.0, 4.0), square(1.0, 1.0, 1.0)] };
        assert!(high.contains(LonLat::new(0.5, 0.5)));
        assert!(!high.contains(LonLat::new(1.5, 1.5)));
        assert!(!high.contains(LonLat::new(5.0, 5.0)));
        let lake = Lake {
            key: "l".into(),
            name: "L".into(),
            shapes: vec![high],
            shape: Timeline::from_keys([(Year(-9500), 0), (Year(-3000), NO_SHAPE)]),
        };
        assert!(lake.shape_at(Year(-9600)).is_none());
        assert_eq!(lake.shape_at(Year(-5000)).unwrap().level, 329.0);
        assert!(lake.shape_at(Year(-2000)).is_none());
    }
}
