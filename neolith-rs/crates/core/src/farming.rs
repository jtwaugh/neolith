//! Expected population once farming has reached a hex: whether the land
//! can be farmed, how many farmers it carries, and how fast they get there.
//!
//! When farming arrives is computed by the pipeline ([`crate::World::farming`]);
//! everything here is derived per year from values on the map, and uses no
//! site or date counts. Sources and the reasoning are in
//! `data/population/SOURCES.md` in the parent repo.

use crate::river::RiverClass;
use crate::values::Koeppen;

/// Farmers per km² that farmed land carries: 50 times the 7 per 100 km² of
/// hunter-gatherers in temperate forest (Davison et al. 2006, after Ammerman
/// & Cavalli-Sforza and Dolukhanov).
pub const CEILING: f64 = 3.5;

/// Intrinsic growth rate per year (Davison et al. 2006): doubling in about
/// 35 years while far below the ceiling.
pub const GROWTH: f64 = 0.02;

/// How the ceiling thins towards the north: Davison et al. cut it "by a
/// factor of approximately 2 across the distance from Greece to Denmark",
/// linearly in latitude. Read here as 1 at 38°N and south of it, 0.5 at
/// 56°N, and on down the same line (0 at 74°N).
pub fn latitude_factor(lat: f64) -> f64 {
    (1.0 - 0.5 * (lat - 38.0) / 18.0).clamp(0.0, 1.0)
}

/// Productivity (g/m²/yr) below which land is too dry to farm without a
/// river: the Miami model's value for 250 mm of rain a year, the usual
/// lower limit given for rain-fed cereals. Where cold limits growth instead,
/// the same value is a mean annual temperature of about −3 °C.
pub const DRY_LIMIT: u16 = 460;

/// Whether the Near Eastern crops can be grown on a hex:
///
/// - not in polar climates (Köppen E) or where fewer than four months
///   reach 10 °C (third letter c or d);
/// - not in the tropics (A): wheat and barley are winter-rain crops;
/// - and only where productivity reaches [`DRY_LIMIT`], unless a river
///   crosses the hex (the Nile, Mesopotamia).
///
/// Dryness is judged from productivity, not from the arid Köppen classes:
/// the map's climate layer has steppe across the whole Sahara. These rules
/// are this project's own, not a published model.
pub fn farmable(climate: Koeppen, npp: u16, river: RiverClass) -> bool {
    let code = climate.code().as_bytes();
    let warm_enough = match code[0] {
        b'B' => true,
        b'C' | b'D' => !matches!(code.get(2), Some(b'c' | b'd')),
        _ => false,
    };
    warm_enough && (npp >= DRY_LIMIT || river != RiverClass::None)
}

/// People per km² `years` after farming arrives on land that carried
/// `foragers` per km² and can carry `ceiling`: logistic growth at
/// [`GROWTH`] from the one to the other. Farming never lowers the figure:
/// where the ceiling is below the forager density, that density stands.
pub fn density(foragers: f64, ceiling: f64, years: f64) -> f64 {
    if ceiling <= foragers || foragers <= 0.0 || years <= 0.0 {
        return foragers;
    }
    ceiling / (1.0 + (ceiling / foragers - 1.0) * (-GROWTH * years).exp())
}

/// Lower bounds (people per km²) of the bands the expected-population map
/// mode uses, lowest first; the last is open-ended above. Fewer than 15, so
/// a band fits in four bits.
const BOUNDS: [f64; 10] = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 3.0];

pub const BAND_COUNT: u8 = BOUNDS.len() as u8;

pub fn band(density: f64) -> u8 {
    BOUNDS.iter().rposition(|lo| *lo <= density).unwrap_or(0) as u8
}

/// Legend label for a band in people per 100 km², e.g. "5–10".
pub fn band_label(band: u8) -> Option<String> {
    let lo = *BOUNDS.get(band as usize)? * 100.0;
    Some(match BOUNDS.get(band as usize + 1) {
        Some(hi) => format!("{lo:.0}–{:.0}", hi * 100.0),
        None => format!("{lo:.0} and up"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn k(code: &str) -> Koeppen {
        Koeppen::from_code(code).unwrap()
    }

    #[test]
    fn farmable_climates() {
        for code in ["Csa", "Csb", "Cfa", "Cfb", "Dfa", "Dfb", "Dsa", "Dwb", "BSh", "BSk", "BWh", "Cwa"] {
            assert!(farmable(k(code), 900, RiverClass::None), "{code}");
        }
        for code in ["Af", "Am", "Aw/As", "Cfc", "Csc", "Dfc", "Dfd", "Dsc", "Dwd", "ET", "EF", "Ocean"] {
            assert!(!farmable(k(code), 900, RiverClass::None), "{code}");
        }
        // Too dry without a river, whatever the class says: the Sahara is "steppe" on the map.
        assert!(!farmable(k("BSh"), DRY_LIMIT - 10, RiverClass::None));
        assert!(farmable(k("BSh"), DRY_LIMIT, RiverClass::None));
        assert!(!farmable(k("Csa"), 200, RiverClass::None));
        // A river makes dry land farmable (the Nile, Mesopotamia), not cold or tropical land.
        assert!(farmable(k("BWh"), 40, RiverClass::Minor) && farmable(k("BSh"), 40, RiverClass::Major));
        assert!(!farmable(k("Dfc"), 40, RiverClass::Major) && !farmable(k("Af"), 2000, RiverClass::Major));
        // The limit is the Miami value of 250 mm of rain.
        let miami = 3000.0 * (1.0 - (-0.000664f64 * 250.0).exp());
        assert!((miami - DRY_LIMIT as f64).abs() < 5.0, "{miami}");
        assert_eq!(Koeppen::all().filter(|c| farmable(*c, 900, RiverClass::None)).count(), 16);
    }

    #[test]
    fn ceiling_thins_northward() {
        assert_eq!(latitude_factor(30.0), 1.0);
        assert_eq!(latitude_factor(38.0), 1.0);
        assert!((latitude_factor(56.0) - 0.5).abs() < 1e-12);
        assert!((latitude_factor(47.0) - 0.75).abs() < 1e-12);
        assert_eq!(latitude_factor(80.0), 0.0);
    }

    #[test]
    fn growth_is_logistic_from_foragers_to_the_ceiling() {
        assert_eq!(density(0.05, 3.5, 0.0), 0.05);
        // Early on it doubles in ln 2 / 0.02 = 34.7 years, nearly.
        let d = density(0.05, 3.5, 34.657);
        assert!((d / 0.05 - 2.0).abs() < 0.04, "{d}");
        // Half the ceiling after ln(K/N0 - 1) / growth years.
        let half = (3.5f64 / 0.05 - 1.0).ln() / GROWTH;
        assert!((density(0.05, 3.5, half) - 1.75).abs() < 1e-9);
        assert!((density(0.05, 3.5, 1000.0) - 3.5).abs() < 1e-5);
        let steps: Vec<f64> = (0..40).map(|i| density(0.05, 3.5, i as f64 * 25.0)).collect();
        assert!(steps.windows(2).all(|w| w[1] > w[0]));
        // Never lowers what foragers already reach; no farmers from nothing.
        assert_eq!(density(2.0, 1.75, 500.0), 2.0);
        assert_eq!(density(0.0, 3.5, 500.0), 0.0);
        assert_eq!(density(0.05, 3.5, -10.0), 0.05);
    }

    #[test]
    fn bands() {
        assert_eq!(band(0.0), 0);
        assert_eq!(band(0.0099), 0);
        assert_eq!(band(0.058), 3);
        assert_eq!(band(3.5), BAND_COUNT - 1);
        assert!(BAND_COUNT < 15);
        assert_eq!(band_label(3).as_deref(), Some("5–10"));
        assert_eq!(band_label(BAND_COUNT - 1).as_deref(), Some("300 and up"));
        assert_eq!(band_label(crate::NO_DATA), None);
    }
}
