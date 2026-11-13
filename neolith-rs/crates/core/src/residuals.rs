//! Sites the list is missing, per hex and epoch: the pipeline's residual
//! step (`pipeline/residuals.py`, written up in `data/population/SOURCES.md`
//! in the parent repo), carried in the world file for the Missing sites map
//! mode. Nothing here is computed in the app.
//!
//! "Missing" is the sites a hex would have if nothing hid them, less the
//! sites known. It is a residual against the site list's own pattern (area,
//! epoch, farmed or not, distance to water), not a population estimate.
//!
//! A slice holds from its year until the next; years before the first slice
//! read the first.

use crate::grid::HexId;
use crate::time::Year;
use serde::{Deserialize, Serialize};

/// Stored where a hex has no figure in a slice (Water, Ice).
pub const NO_FIGURE: i16 = i16::MIN;
/// The outcome code for "no figure".
pub const NO_OUTCOME: u8 = 255;

/// The residual table: `slices.len() × hexes` values per column, slice-major.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Residuals {
    /// Sorted, strictly increasing.
    pub slices: Vec<Year>,
    /// What the outcome codes mean, as the pipeline names them, e.g.
    /// "little dated archaeology nearby".
    pub outcomes: Vec<String>,
    /// Sites known in the hex within the slice's window.
    pub sites: Vec<u16>,
    /// Missing sites in tenths (negative: more known than expected), or
    /// [`NO_FIGURE`].
    pub missing: Vec<i16>,
    /// Index into `outcomes`, or [`NO_OUTCOME`].
    pub outcome: Vec<u8>,
}

/// One hex's row at one year.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Residual<'a> {
    pub sites: u16,
    /// Sites missing (negative: more known than expected).
    pub missing: f32,
    pub outcome: &'a str,
}

/// Lower bounds (missing sites) of the bands the map mode uses, lowest
/// first; the first band is everything below 0.5, the last open-ended.
const BOUNDS: [f32; 6] = [f32::NEG_INFINITY, 0.5, 1.0, 2.0, 5.0, 10.0];

pub const BAND_COUNT: u8 = BOUNDS.len() as u8;

/// The band of a missing-sites figure in tenths; [`crate::NO_DATA`] for
/// [`NO_FIGURE`].
pub fn band(tenths: i16) -> u8 {
    if tenths == NO_FIGURE {
        return crate::NO_DATA;
    }
    let v = tenths as f32 / 10.0;
    BOUNDS.iter().rposition(|lo| *lo <= v).unwrap_or(0) as u8
}

/// Legend label for a band: "fewer than 0.5", "1–2", "10 or more".
pub fn band_label(b: u8) -> Option<String> {
    let lo = *BOUNDS.get(b as usize)?;
    Some(match BOUNDS.get(b as usize + 1) {
        Some(hi) if b == 0 => format!("fewer than {hi}"),
        Some(hi) => format!("{lo}–{hi}"),
        None => format!("{lo} or more"),
    })
}

impl Residuals {
    /// Hexes per slice.
    pub fn hexes(&self) -> usize {
        self.missing.len().checked_div(self.slices.len()).unwrap_or(0)
    }

    /// The index of the slice in effect at `year`: the latest at or before
    /// it, or the first for earlier years. `None` without slices.
    pub fn slice_at(&self, year: Year) -> Option<usize> {
        if self.slices.is_empty() {
            return None;
        }
        Some(self.slices.partition_point(|s| *s <= year).saturating_sub(1))
    }

    /// Every hex's band at `year` (empty without slices), for the board.
    pub fn bands_at(&self, year: Year) -> Vec<u8> {
        let n = self.hexes();
        self.slice_at(year).map_or(Vec::new(), |k| self.missing[k * n..(k + 1) * n].iter().map(|m| band(*m)).collect())
    }

    /// One hex's row at `year`, if it has a figure.
    pub fn at(&self, hex: HexId, year: Year) -> Option<Residual<'_>> {
        let i = self.slice_at(year)? * self.hexes() + hex.index();
        let missing = *self.missing.get(i).filter(|m| **m != NO_FIGURE && hex.index() < self.hexes())?;
        Some(Residual {
            sites: self.sites[i],
            missing: missing as f32 / 10.0,
            outcome: self.outcomes.get(self.outcome[i] as usize).map_or("", String::as_str),
        })
    }

    /// Structural invariants for a world of `hexes` hexes.
    pub fn validate(&self, hexes: usize) -> Result<(), String> {
        let n = self.slices.len() * hexes;
        if self.slices.is_empty() || self.slices.windows(2).any(|w| w[0] >= w[1]) {
            return Err("residuals: slices are empty or not increasing".into());
        }
        if self.sites.len() != n || self.missing.len() != n || self.outcome.len() != n {
            return Err(format!(
                "residuals: {} sites, {} missing and {} outcome values for {} slices of {hexes} hexes",
                self.sites.len(),
                self.missing.len(),
                self.outcome.len(),
                self.slices.len()
            ));
        }
        if self.outcome.iter().any(|o| *o != NO_OUTCOME && *o as usize >= self.outcomes.len()) {
            return Err("residuals: an outcome code has no name".into());
        }
        if self.missing.iter().zip(&self.outcome).any(|(m, o)| (*m == NO_FIGURE) != (*o == NO_OUTCOME)) {
            return Err("residuals: a hex has a figure without an outcome, or the reverse".into());
        }
        Ok(())
    }
}

/// A small table for tests: two slices; hex `i` is missing `i` tenths in the
/// first and `10 × i` in the second; every fourth hex has no figure.
#[cfg(test)]
pub(crate) fn test_table(hexes: usize) -> Residuals {
    let row = |scale: i16| -> (Vec<u16>, Vec<i16>, Vec<u8>) {
        let none = |i: usize| i % 4 == 3;
        (
            (0..hexes).map(|i| (i % 3) as u16).collect(),
            (0..hexes).map(|i| if none(i) { NO_FIGURE } else { i as i16 * scale }).collect(),
            (0..hexes).map(|i| if none(i) { NO_OUTCOME } else { (i % 2) as u8 }).collect(),
        )
    };
    let (a, b) = (row(1), row(10));
    Residuals {
        slices: vec![Year(-6000), Year(-5000)],
        outcomes: vec!["as expected".into(), "little dated archaeology nearby".into()],
        sites: [a.0, b.0].concat(),
        missing: [a.1, b.1].concat(),
        outcome: [a.2, b.2].concat(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bands_and_labels() {
        assert_eq!(band(-30), 0);
        assert_eq!(band(4), 0);
        assert_eq!(band(5), 1);
        assert_eq!(band(19), 2);
        assert_eq!(band(20), 3);
        assert_eq!(band(99), 4);
        assert_eq!(band(100), BAND_COUNT - 1);
        assert_eq!(band(NO_FIGURE), crate::NO_DATA);
        assert_eq!(band_label(0).as_deref(), Some("fewer than 0.5"));
        assert_eq!(band_label(2).as_deref(), Some("1–2"));
        assert_eq!(band_label(BAND_COUNT - 1).as_deref(), Some("10 or more"));
        assert_eq!(band_label(BAND_COUNT), None);
        assert_eq!(band_label(crate::NO_DATA), None);
    }

    #[test]
    fn slices_hold_until_the_next_and_before_the_first() {
        let t = test_table(8);
        assert_eq!(t.validate(8), Ok(()));
        assert_eq!(t.hexes(), 8);
        assert_eq!(t.slice_at(Year(-9000)), Some(0));
        assert_eq!(t.slice_at(Year(-5001)), Some(0));
        assert_eq!(t.slice_at(Year(-5000)), Some(1));
        assert_eq!(t.slice_at(Year(-3000)), Some(1));
        let r = t.at(HexId(6), Year(-5500)).unwrap();
        assert_eq!((r.sites, r.missing, r.outcome), (0, 0.6, "as expected"));
        let r = t.at(HexId(5), Year(-4000)).unwrap();
        assert_eq!((r.sites, r.missing, r.outcome), (2, 5.0, "little dated archaeology nearby"));
        assert_eq!(t.at(HexId(3), Year(-5500)), None);
        assert_eq!(t.at(HexId(8), Year(-5500)), None);
        assert_eq!(t.bands_at(Year(-4000)), vec![0, 2, 3, crate::NO_DATA, 3, 4, 4, crate::NO_DATA]);
        assert!(Residuals::default().bands_at(Year(0)).is_empty() && Residuals::default().at(HexId(0), Year(0)).is_none());
    }

    #[test]
    fn validate_catches_bad_tables() {
        let ok = test_table(8);
        assert!(ok.validate(9).is_err());
        let mut t = ok.clone();
        t.slices.reverse();
        assert!(t.validate(8).is_err());
        let mut t = ok.clone();
        t.outcome[0] = 7;
        assert!(t.validate(8).is_err());
        let mut t = ok.clone();
        t.outcome[0] = NO_OUTCOME;
        assert!(t.validate(8).is_err());
        assert!(Residuals::default().validate(8).is_err());
    }
}
