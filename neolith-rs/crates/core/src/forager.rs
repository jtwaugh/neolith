//! Expected hunter-gatherer population density from a hex's productivity:
//! the regression of Tallavaara, Eronen & Luoto (2018, PNAS 115: 1232–1237)
//! on 300 ethnographic groups, refitted from their published data (see
//! `data/population/SOURCES.md` in the parent repo for the working).
//!
//! The model has three inputs. Only productivity is stored per hex
//! ([`crate::World::npp`]); the other two are derived here:
//!
//! - **Biodiversity** follows productivity ([`biodiversity`]): there is no
//!   reconstruction of species richness for the early Holocene.
//! - **Pathogen stress** also follows productivity ([`pathogen_stress`]),
//!   by the relation the authors fitted to their forager groups: level until
//!   about 1,350 g/m²/yr and rising above it. Their mapped surface is not
//!   used: it is interpolated from disease recorded in historical, mostly
//!   farming societies, and over this map lies above the fitted range.
//!
//! The published model has no aquatic resources. A correction for distance
//! to the sea or a lake is added here ([`shore_factor`]); it is this
//! project's own fit, not part of the published model. Rivers are still
//! left out. Nothing here uses site or date counts.

/// Pathogen stress (mean z-score of the prevalence of 10 pathogens)
/// expected at a productivity: the authors' own piecewise fit to their 300
/// forager groups (their script, "between npp and pathogenic stress"):
/// −0.808 + 0.0000712 per g/m²/yr, and a further 0.0005244 per g/m²/yr
/// above the break at 1,349.
///
/// This is what holds the wet tropics back: density peaks near 1,700
/// g/m²/yr and falls beyond it.
pub fn pathogen_stress(npp: u16) -> f64 {
    let n = npp as f64;
    -0.8080 + 7.120e-5 * n + 5.244e-4 * (n - 1349.258).max(0.0)
}

/// Biodiversity (0–1: scaled mammal, bird and plant richness) expected at a
/// productivity. A straight line fitted to the authors' present-day rasters
/// over this map's extent, weighted by cell area (R² 0.82).
pub fn biodiversity(npp: u16) -> f64 {
    (0.064_383_16 + 0.000_180_32 * npp as f64).clamp(0.0, 1.0)
}

/// The fitted groups' densities span 0.2 to 270.75 people per 100 km²;
/// predictions are held inside that range.
const LN_DENSITY_RANGE: (f64, f64) = (-1.609_437_912_434_1, 5.601_195_885_881_1);

/// Natural log of people per 100 km² at productivity `npp` (Miami model,
/// g dry matter/m²/yr), biodiversity `b` and pathogen stress `s`.
pub fn ln_density_per_100km2(npp: f64, b: f64, s: f64) -> f64 {
    -0.429_785_625 + 0.001_087_454_06 * npp + 8.981_427_6 * b + 1.096_655_43 * s
        - 0.002_217_536_83 * npp * s
        - 0.003_002_944_97 * npp * b
}

/// Distances to water beyond this are treated as this far (km): about the
/// 99th percentile of the groups the correction was fitted on.
pub const MAX_SHORE_KM: f64 = 2000.0;

/// How many times denser foragers are `shore_km` from the sea or a large
/// lake than the published equation says: `exp(2.1279 − 0.4024 ln(km + 10))`.
///
/// Fitted to what the equation misses for the 338 groups of Binford's data
/// (D-PLACE) that have all three of its layers: R² 0.175 on the misses, and
/// it still helps when each of the 27 regions is held out in turn. About
/// ×3.3 on the shore, ×1.6 at 50 km, ×1 at 190 km, ×0.5 at 1000 km.
pub fn shore_factor(shore_km: f64) -> f64 {
    (2.1279 - 0.4024 * (shore_km.clamp(0.0, MAX_SHORE_KM) + 10.0).ln()).exp()
}

/// Distance at which [`shore_factor`] is 1, where the published equation
/// stands unchanged.
pub const NEUTRAL_SHORE_KM: f64 = 187.9;

/// Expected hunter-gatherer density in people per km² on land producing
/// `npp`, `shore_km` from the sea or a lake, with biodiversity and pathogen
/// stress as described in the module docs. A single hex is good to within a
/// factor of about three either way.
pub fn density(npp: u16, shore_km: f64) -> f64 {
    let ln = ln_density_per_100km2(npp as f64, biodiversity(npp), pathogen_stress(npp)) + shore_factor(shore_km).ln();
    ln.clamp(LN_DENSITY_RANGE.0, LN_DENSITY_RANGE.1).exp() / 100.0
}

/// Lower bounds of the biodiversity bands, lowest first; the last is
/// open-ended above.
const BIODIVERSITY_BOUNDS: [f64; 10] = [0.0, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.36, 0.43];

pub const BIODIVERSITY_BAND_COUNT: u8 = BIODIVERSITY_BOUNDS.len() as u8;

/// The band of a biodiversity value.
pub fn biodiversity_band(b: f64) -> u8 {
    BIODIVERSITY_BOUNDS.iter().rposition(|lo| *lo <= b).unwrap_or(0) as u8
}

/// Legend label for a biodiversity band, e.g. "0.10–0.13".
pub fn biodiversity_band_label(band: u8) -> Option<String> {
    let lo = *BIODIVERSITY_BOUNDS.get(band as usize)?;
    Some(match BIODIVERSITY_BOUNDS.get(band as usize + 1) {
        Some(hi) => format!("{lo:.2}–{hi:.2}"),
        None => format!("{lo:.2} and up"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn equation_matches_the_refit() {
        // The sample means (npp 889.4855, biodiversity 0.2026282, pathogen
        // stress -0.6955953) give the intercept of the centred model the
        // authors print: 2.425.
        let at_means = ln_density_per_100km2(889.485_506, 0.202_628_2, -0.695_595_3);
        assert!((at_means - 2.425).abs() < 0.001, "{at_means}");
        // Coefficients, one at a time.
        assert!((ln_density_per_100km2(0.0, 0.0, 0.0) + 0.429_785_625).abs() < 1e-12);
        assert!((ln_density_per_100km2(1000.0, 0.0, 0.0) - (-0.429_785_625 + 1.087_454_06)).abs() < 1e-9);
        assert!((ln_density_per_100km2(1000.0, 0.2, -0.5) - 2.413_805_661).abs() < 1e-8);
    }

    #[test]
    fn pathogens_follow_productivity_as_in_the_authors_fit() {
        assert!((pathogen_stress(0) + 0.808).abs() < 1e-12);
        assert!((pathogen_stress(1000) + 0.7368).abs() < 1e-4);
        // Level below the break, rising above it.
        assert!(pathogen_stress(1349) - pathogen_stress(0) < 0.1);
        assert!((pathogen_stress(2349) - pathogen_stress(1349) - (0.0712 + 0.5244)).abs() < 1e-3);
    }

    #[test]
    fn density_peaks_in_productive_forest_and_falls_in_the_wet_tropics() {
        let density = |npp: u16| super::density(npp, NEUTRAL_SHORE_KM);
        let d: Vec<f64> = (0..=3000).step_by(50).map(density).collect();
        assert!(d.iter().all(|v| (0.002 - 1e-9..=2.7075 + 1e-9).contains(v)), "{d:?}");
        let peak = d.iter().cloned().fold(0.0, f64::max);
        let at = d.iter().position(|v| *v == peak).unwrap() * 50;
        assert!((1600..=1800).contains(&at), "peak at {at}");
        assert!((0.6..0.7).contains(&peak), "{peak}");
        // Rising up to the peak, falling after it.
        assert!(d[..=at / 50].windows(2).all(|w| w[1] > w[0]) && d[at / 50..].windows(2).all(|w| w[1] < w[0]), "{d:?}");
        // Desert, steppe, temperate forest and rainforest, people per km².
        assert!(density(50) < 0.01, "{}", density(50));
        assert!((0.02..0.08).contains(&density(500)), "{}", density(500));
        assert!((0.1..0.4).contains(&density(1000)), "{}", density(1000));
        assert!((0.02..0.06).contains(&density(3000)), "{}", density(3000));
    }

    #[test]
    fn foragers_are_denser_near_water() {
        assert!((shore_factor(NEUTRAL_SHORE_KM) - 1.0).abs() < 1e-3);
        assert!((shore_factor(0.0) - 3.32).abs() < 0.01);
        assert!((shore_factor(50.0) - 1.62).abs() < 0.01);
        assert!((shore_factor(1000.0) - 0.52).abs() < 0.01);
        // Beyond the fitted range, and for land with no water anywhere, it stops falling.
        assert_eq!(shore_factor(f64::INFINITY), shore_factor(MAX_SHORE_KM));
        assert_eq!(shore_factor(-5.0), shore_factor(0.0));
        let d: Vec<f64> = [0.0, 25.0, 100.0, 400.0, 1500.0].iter().map(|km| density(700, *km)).collect();
        assert!(d.windows(2).all(|w| w[1] < w[0]), "{d:?}");
        assert!((density(700, 0.0) / density(700, NEUTRAL_SHORE_KM) - 3.32).abs() < 0.02);
        // Still held inside the fitted groups' range: the bottom binds far inland on bare ground,
        // the top no longer does (the richest shore reaches about 2.2 per km²).
        assert!((density(0, f64::INFINITY) - 0.002).abs() < 1e-9);
        assert!((2.0..2.7075).contains(&density(1700, 0.0)), "{}", density(1700, 0.0));
    }

    #[test]
    fn biodiversity_follows_productivity_in_bands() {
        assert!((biodiversity(0) - 0.0644).abs() < 1e-4);
        assert!((biodiversity(1000) - 0.2447).abs() < 1e-4);
        assert_eq!(biodiversity_band(biodiversity(0)), 0);
        assert_eq!(biodiversity_band(0.2447), 5);
        assert_eq!(biodiversity_band(0.9), BIODIVERSITY_BAND_COUNT - 1);
        assert_eq!(biodiversity_band_label(1).as_deref(), Some("0.08–0.10"));
        assert_eq!(biodiversity_band_label(BIODIVERSITY_BAND_COUNT - 1).as_deref(), Some("0.43 and up"));
        assert_eq!(biodiversity_band_label(crate::NO_DATA), None);
    }
}
