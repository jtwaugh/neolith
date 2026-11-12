//! Net primary productivity per hex (grams of dry matter per square metre
//! per year, by the Miami model from the pipeline's climate model: the scale
//! [`crate::forager`] was fitted on) and the bands the productivity map mode
//! colours it by. It changes with the climate, at the model's 1000-year steps.

/// Lower bounds (g/m²/yr) of the bands, lowest first. The last band is
/// open-ended above.
const BOUNDS: [u16; 10] = [0, 100, 200, 400, 600, 800, 1000, 1300, 1600, 2000];

pub const BAND_COUNT: u8 = BOUNDS.len() as u8;

pub const UNIT: &str = "g/m²/yr";

/// The band of a hex producing `npp`.
pub fn band(npp: u16) -> u8 {
    BOUNDS.iter().rposition(|lo| *lo <= npp).unwrap_or(0) as u8
}

/// Legend label for a band, e.g. "200–300".
pub fn band_label(b: u8) -> Option<String> {
    let lo = *BOUNDS.get(b as usize)?;
    Some(match BOUNDS.get(b as usize + 1) {
        Some(hi) => format!("{lo}–{hi}"),
        None => format!("{lo} and up"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bands_cover_the_range_in_order() {
        assert_eq!(band(0), 0);
        assert_eq!(band(99), 0);
        assert_eq!(band(100), 1);
        assert_eq!(band(1999), BAND_COUNT - 2);
        assert_eq!(band(u16::MAX), BAND_COUNT - 1);
        assert_eq!(band_label(2).as_deref(), Some("200–400"));
        assert_eq!(band_label(BAND_COUNT - 1).as_deref(), Some("2000 and up"));
        assert_eq!(band_label(BAND_COUNT), None);
        assert_eq!(band_label(crate::NO_DATA), None);
    }
}
