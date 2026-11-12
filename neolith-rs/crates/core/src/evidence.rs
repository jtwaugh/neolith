//! Speculative evidence layers (isostyle's `neolith-evidence-1` export,
//! `isostyle/export.py`): per layer, one byte per (slice, hex), slice-major.
//!
//! A byte is `confidence * BINS + bin`: `bin` (0..BINS) spans `vmin..vmax`,
//! and confidence is 0 observed, 1–3 judged (high, medium, low), 4
//! extrapolated. [`NO_VALUE`] means nothing to show (sea, ice, or nothing to
//! fill from). Anything above confidence 0 is speculation, not evidence.
//!
//! A slice holds from its year until the next slice; years before the first
//! slice read the first (the same step-function rule as the map's keys).

use crate::grid::HexId;
use crate::time::Year;
use serde::{Deserialize, Serialize};

/// Value bins per confidence level.
pub const BINS: u8 = 50;
/// Confidence levels: observed, judged high, medium, low, extrapolated.
pub const LEVELS: u8 = 5;
/// The code for "no value".
pub const NO_VALUE: u8 = 255;

const CONFIDENCE_LABELS: [&str; LEVELS as usize] = [
    "observed",
    "judged, high confidence",
    "judged, medium confidence",
    "judged, low confidence",
    "extrapolated",
];

/// One speculative layer: what it is, and its codes for every slice.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct EvidenceLayer {
    /// Stable identifier, e.g. `domestic_livestock`.
    pub id: String,
    pub name: String,
    /// Picker heading, e.g. "Subsistence".
    pub group: String,
    /// Layers in the same set (e.g. "Y haplogroup") are shares of one whole;
    /// empty for a stand-alone layer.
    pub set: String,
    /// `presence_absence`, `presence_only`, `share` or `grid`, as exported.
    pub kind: String,
    pub units: String,
    pub vmin: f32,
    pub vmax: f32,
    pub note: String,
    /// Sorted, strictly increasing.
    pub slices: Vec<Year>,
    /// `slices.len() × hexes` codes, slice-major.
    pub codes: Vec<u8>,
}

/// The confidence level (0..LEVELS) of a code, or `None` for [`NO_VALUE`]
/// (and any other code out of range).
pub fn confidence(code: u8) -> Option<u8> {
    (code < LEVELS * BINS).then_some(code / BINS)
}

/// The value bin (0..BINS) of a code.
pub fn bin(code: u8) -> Option<u8> {
    (code < LEVELS * BINS).then_some(code % BINS)
}

/// "observed", "judged, high confidence", … "extrapolated".
pub fn confidence_label(level: u8) -> &'static str {
    CONFIDENCE_LABELS.get(level as usize).copied().unwrap_or("no value")
}

/// Whether a code is a judged or extrapolated value: speculation, not evidence.
pub fn is_speculative(code: u8) -> bool {
    confidence(code).is_some_and(|c| c > 0)
}

impl EvidenceLayer {
    /// Hexes per slice.
    pub fn hexes(&self) -> usize {
        self.codes.len().checked_div(self.slices.len()).unwrap_or(0)
    }

    /// The index of the slice in effect at `year`: the latest at or before
    /// it, or the first for earlier years. `None` without slices.
    pub fn slice_at(&self, year: Year) -> Option<usize> {
        if self.slices.is_empty() {
            return None;
        }
        Some(self.slices.partition_point(|s| *s <= year).saturating_sub(1))
    }

    /// Every hex's code at `year` (empty without slices).
    pub fn codes_at(&self, year: Year) -> &[u8] {
        let n = self.hexes();
        self.slice_at(year).map_or(&[], |k| &self.codes[k * n..(k + 1) * n])
    }

    /// The code of one hex at `year`; [`NO_VALUE`] for a hex outside the layer.
    pub fn code_at(&self, hex: HexId, year: Year) -> u8 {
        self.codes_at(year).get(hex.index()).copied().unwrap_or(NO_VALUE)
    }

    /// The value a code stands for: the centre of its bin in `vmin..vmax`.
    pub fn value(&self, code: u8) -> Option<f32> {
        bin(code).map(|b| self.vmin + (b as f32 + 0.5) / BINS as f32 * (self.vmax - self.vmin))
    }

    /// A value for reading, with the units: "0.43 share", "61 % open land".
    pub fn format_value(&self, v: f32) -> String {
        let span = (self.vmax - self.vmin).abs();
        let v = if span >= 20.0 { format!("{v:.0}") } else { format!("{v:.2}") };
        if self.units.is_empty() {
            v
        } else {
            format!("{v} {}", self.units)
        }
    }

    /// Structural invariants for a world of `hexes` hexes.
    pub fn validate(&self, hexes: usize) -> Result<(), String> {
        let bad = |why: String| Err(format!("evidence layer {}: {why}", self.id));
        if self.slices.is_empty() {
            return bad("no slices".into());
        }
        if self.slices.windows(2).any(|w| w[0] >= w[1]) {
            return bad("slices are not sorted".into());
        }
        if self.codes.len() != self.slices.len() * hexes {
            return bad(format!("{} codes for {} slices × {hexes} hexes", self.codes.len(), self.slices.len()));
        }
        if !(self.vmin.is_finite() && self.vmax.is_finite() && self.vmax > self.vmin) {
            return bad(format!("value range {}..{} is empty", self.vmin, self.vmax));
        }
        if let Some(c) = self.codes.iter().find(|c| **c != NO_VALUE && confidence(**c).is_none()) {
            return bad(format!("code {c} is out of range"));
        }
        Ok(())
    }
}

#[cfg(test)]
pub(crate) fn test_layer(id: &str, hexes: usize) -> EvidenceLayer {
    // Slice k: hex i has code (k * 7 + i) % 250, so every hex differs by slice.
    let slices = vec![Year(-9000), Year(-7000), Year(-5000)];
    let codes = (0..slices.len()).flat_map(|k| (0..hexes).map(move |i| ((k * 7 + i) % 250) as u8)).collect();
    EvidenceLayer {
        id: id.into(),
        name: format!("Test {id}"),
        group: "Test".into(),
        set: String::new(),
        kind: "share".into(),
        units: "share".into(),
        vmin: 0.0,
        vmax: 1.0,
        note: String::new(),
        slices,
        codes,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn code_at_steps_at_slice_boundaries() {
        let mut l = test_layer("a", 10);
        l.codes[2 * 10 + 3] = NO_VALUE;
        let at = |y: i32| l.code_at(HexId(3), Year(y));
        // Before the first slice: the first.
        assert_eq!(at(-12000), 3);
        assert_eq!(at(-9000), 3);
        assert_eq!(at(-7001), 3, "a slice holds until the next");
        assert_eq!(at(-7000), 10);
        assert_eq!(at(-5001), 10);
        assert_eq!(at(-5000), NO_VALUE);
        assert_eq!(at(2000), NO_VALUE, "the last slice holds on");
        assert_eq!(l.slice_at(Year(-6000)), Some(1));
        assert_eq!(l.codes_at(Year(-6000)).len(), 10);
        assert_eq!(l.code_at(HexId(99), Year(-6000)), NO_VALUE);
        let empty = EvidenceLayer { slices: vec![], codes: vec![], ..test_layer("e", 0) };
        assert_eq!(empty.slice_at(Year(0)), None);
        assert_eq!(empty.code_at(HexId(0), Year(0)), NO_VALUE);
    }

    #[test]
    fn codes_decode_to_value_and_confidence() {
        let mut l = test_layer("a", 1);
        assert_eq!(confidence(0), Some(0));
        assert_eq!(confidence(49), Some(0));
        assert_eq!(confidence(50), Some(1));
        assert_eq!(confidence(249), Some(4));
        assert_eq!(confidence(250), None);
        assert_eq!(confidence(NO_VALUE), None);
        assert_eq!(bin(3 * 50 + 7), Some(7));
        assert!(!is_speculative(10) && is_speculative(60) && !is_speculative(NO_VALUE));
        assert_eq!(confidence_label(0), "observed");
        assert_eq!(confidence_label(4), "extrapolated");
        assert!((l.value(0).unwrap() - 0.01).abs() < 1e-6, "bin centre");
        assert!((l.value(49).unwrap() - 0.99).abs() < 1e-6);
        assert_eq!(l.value(50), l.value(0), "confidence does not change the value");
        assert_eq!(l.value(NO_VALUE), None);
        l.vmax = 100.0;
        assert!((l.value(25).unwrap() - 51.0).abs() < 1e-4);
        assert_eq!(l.format_value(51.0), "51 share");
    }

    #[test]
    fn validation() {
        assert!(test_layer("a", 4).validate(4).is_ok());
        assert!(test_layer("a", 4).validate(5).is_err());
        let mut l = test_layer("a", 4);
        l.slices.swap(0, 1);
        assert!(l.validate(4).is_err());
        let mut l = test_layer("a", 4);
        l.codes[0] = 250;
        assert!(l.validate(4).is_err());
        let mut l = test_layer("a", 4);
        l.vmax = l.vmin;
        assert!(l.validate(4).is_err());
    }
}
