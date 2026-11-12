//! Per-hex elevation (static: ETOPO1 median, present-day datum) and the
//! bands the elevation map mode colours it by.
//!
//! The band depends on the year only through whether the hex is Water then:
//! water hexes get a depth band, everything else a height band. So shelf that
//! the lower sea level exposes (Doggerland, the Persian Gulf) shows as land
//! "below 0 m", the present-day datum.

use crate::grid::GridSpec;
use crate::world::NO_DATA;

/// Stored where a hex has no elevation (files written before version 4).
pub const NO_ELEVATION: i16 = i16::MIN;

/// Lower bounds (metres) of the water bands, deepest first. The first band
/// is open-ended below.
const SEA: [i16; 7] = [i16::MIN + 1, -4000, -3000, -2000, -1000, -200, -50];
/// Lower bounds (metres) of the land bands, lowest first. The first band
/// (land below today's sea level) is open-ended below.
const LAND: [i16; 12] = [i16::MIN + 1, 0, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 2500];

/// Number of bands: water bands then land bands.
pub const BAND_COUNT: u8 = (SEA.len() + LAND.len()) as u8;
/// First land band.
pub const LAND_BAND: u8 = SEA.len() as u8;

/// The band of a hex at `elevation` metres, or [`NO_DATA`].
pub fn band(elevation: i16, water: bool) -> u8 {
    if elevation == NO_ELEVATION {
        return NO_DATA;
    }
    let (table, base) = if water { (&SEA[..], 0) } else { (&LAND[..], LAND_BAND) };
    // Last band whose lower bound is at or below the elevation. Water above
    // 0 m (lakes) falls in the shallowest band.
    base + (table.iter().rposition(|lo| *lo <= elevation).unwrap_or(0) as u8)
}

pub fn is_water_band(b: u8) -> bool {
    b < LAND_BAND
}

/// Legend label for a band, e.g. "200–300 m" or "water, below 4000 m".
pub fn band_label(b: u8) -> Option<String> {
    if b >= BAND_COUNT {
        return None;
    }
    let (table, i, water) = if is_water_band(b) {
        (&SEA[..], b as usize, true)
    } else {
        (&LAND[..], (b - LAND_BAND) as usize, false)
    };
    let lo = table[i];
    let hi = if water { table.get(i + 1).copied().unwrap_or(0) } else { table.get(i + 1).copied().unwrap_or(i16::MAX) };
    Some(match (water, i == 0, hi == i16::MAX) {
        (true, true, _) => format!("Water, deeper than {} m", -hi),
        (true, false, _) => format!("Water, {}–{} m deep", -hi, -lo),
        (false, true, _) => "Land below 0 m (today's sea level)".into(),
        (false, false, true) => format!("Land, {lo} m and up"),
        (false, false, false) => format!("Land, {lo}–{hi} m"),
    })
}

/// [`hillshade`] value of level ground: the shade is a multiplier, `v / 128`.
pub const FLAT_SHADE: u8 = 128;

/// Vertical exaggeration for [`hillshade`]. Hexes are 40–55 km across, so a
/// 1000 m step between neighbours is barely a 1° slope; this makes it about 30°.
pub const HILLSHADE_EXAGGERATION: f64 = 30.0;

/// Per-hex hillshade from the elevation gradient: a plane fitted through the
/// hex and its neighbours by least squares, lit from the north-west at 45°
/// (the cartographic convention, and from the far side of the board as the
/// camera faces north, so relief doesn't read inverted).
///
/// Neighbours below sea level are raised to `min(own elevation, 0)` so that
/// coasts aren't shaded by the drop to the sea floor. Hexes without
/// elevation, or without two usable neighbours, are [`FLAT_SHADE`].
pub fn hillshade(grid: &GridSpec, elevation: &[i16], exaggeration: f64) -> Vec<u8> {
    const M_PER_DEG: f64 = 111_320.0;
    let (az, alt) = (315f64.to_radians(), 45f64.to_radians());
    // Towards the light: x east, y north, z up.
    let light = [alt.cos() * az.sin(), alt.cos() * az.cos(), alt.sin()];
    grid.ids()
        .map(|id| {
            let z0 = elevation[id.index()];
            if z0 == NO_ELEVATION {
                return FLAT_SHADE;
            }
            let c0 = grid.centre(id);
            let floor = (z0 as f64).min(0.0);
            // Normal equations for dz = gx·dx + gy·dy.
            let (mut sxx, mut sxy, mut syy, mut sxz, mut syz, mut n) = (0.0, 0.0, 0.0, 0.0, 0.0, 0);
            for nb in grid.neighbours(id) {
                let z = elevation[nb.index()];
                if z == NO_ELEVATION {
                    continue;
                }
                let c = grid.centre(nb);
                let dx = (c.lon - c0.lon) * M_PER_DEG * ((c.lat + c0.lat) / 2.0).to_radians().cos();
                let dy = (c.lat - c0.lat) * M_PER_DEG;
                let dz = (z as f64).max(floor) - z0 as f64;
                sxx += dx * dx;
                sxy += dx * dy;
                syy += dy * dy;
                sxz += dx * dz;
                syz += dy * dz;
                n += 1;
            }
            let det = sxx * syy - sxy * sxy;
            if n < 2 || det.abs() < 1e-6 * sxx * syy {
                return FLAT_SHADE;
            }
            let gx = (syy * sxz - sxy * syz) / det * exaggeration;
            let gy = (sxx * syz - sxy * sxz) / det * exaggeration;
            // Surface normal (-gx, -gy, 1), normalised, dotted with the light.
            let shade = (-gx * light[0] - gy * light[1] + light[2]) / (gx * gx + gy * gy + 1.0).sqrt();
            (FLAT_SHADE as f64 * shade.max(0.0) / light[2]).round().clamp(0.0, 255.0) as u8
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bands() {
        assert_eq!(band(NO_ELEVATION, false), NO_DATA);
        assert_eq!(band(-5000, true), 0);
        assert_eq!(band(-30, true), LAND_BAND - 1);
        // Lakes above sea level: shallowest water band.
        assert_eq!(band(400, true), LAND_BAND - 1);
        // Exposed shelf.
        assert_eq!(band(-40, false), LAND_BAND);
        assert_eq!(band(0, false), LAND_BAND + 1);
        assert_eq!(band(250, false), LAND_BAND + 4);
        assert_eq!(band(i16::MAX, false), BAND_COUNT - 1);
    }

    #[test]
    fn hillshade_lights_north_west_slopes() {
        let grid = GridSpec { cols: 9, rows: 9, origin_lon: 0.0, origin_lat: 50.0, w: 0.5773502691896262, h: 0.5 };
        let centre = grid.id_at(4, 4);
        let ramp = |f: &dyn Fn(f64, f64) -> f64| -> u8 {
            // Coordinates relative to the centre hex, so the ramps fit in i16.
            let c0 = grid.centre(centre);
            let z: Vec<i16> = grid
                .ids()
                .map(|id| {
                    let c = grid.centre(id);
                    f(c.lon - c0.lon, c.lat - c0.lat) as i16
                })
                .collect();
            hillshade(&grid, &z, HILLSHADE_EXAGGERATION)[centre.index()]
        };
        assert_eq!(ramp(&|_, _| 300.0), FLAT_SHADE);
        // A slope facing north-west (falling towards it) is lit; one facing
        // south-east is in shade.
        let nw = ramp(&|lon, lat| 1000.0 + 1000.0 * lon - 1000.0 * lat);
        let se = ramp(&|lon, lat| 1000.0 - 1000.0 * lon + 1000.0 * lat);
        assert!(nw > FLAT_SHADE && se < FLAT_SHADE, "{nw} {se}");
        // A slope across the light (facing south-west) stays nearer flat.
        let ne = ramp(&|lon, lat| 1000.0 + 600.0 * lon + 1000.0 * lat) as i32;
        assert!((ne - FLAT_SHADE as i32).abs() < (nw as i32 - FLAT_SHADE as i32), "{ne}");
        // Coasts: a deep sea floor next door doesn't shade the land.
        let coast = ramp(&|lon, _| if lon < -0.2 { -3000.0 } else { 0.0 });
        assert_eq!(coast, FLAT_SHADE);
    }

    #[test]
    fn bands_are_ordered_and_labelled() {
        assert!(SEA.windows(2).all(|w| w[0] < w[1]) && LAND.windows(2).all(|w| w[0] < w[1]));
        for b in 0..BAND_COUNT {
            assert!(band_label(b).is_some(), "band {b}");
        }
        assert_eq!(band_label(BAND_COUNT), None);
        assert_eq!(band_label(LAND_BAND + 4).unwrap(), "Land, 200–300 m");
        assert_eq!(band_label(LAND_BAND - 1).unwrap(), "Water, 0–50 m deep");
        assert_eq!(band_label(0).unwrap(), "Water, deeper than 4000 m");
    }
}
