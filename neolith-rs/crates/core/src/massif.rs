//! A sketch of a hilly or mountain hex's high ground, from the elevation
//! raster (the pipeline's `elevation.massif`): where its summits stand, which
//! way its ridge runs and what kind of high ground it is. Static, like
//! [`crate::Landform`], which it refines: the landform says how rough a hex
//! is, the massif says what the roughness looks like, so the board can draw
//! the Taurus as ridges that chain from hex to hex, Erciyes as one cone and
//! the central Anatolian plateau as high, open ground.

use serde::{Deserialize, Serialize};

/// What kind of high ground a hex holds.
#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MassifKind {
    /// Rough ground with no strong grain: a knot of peaks.
    Massif,
    /// A linear range: the gradient over the high ground lines up
    /// (structure-tensor coherence) along one strike.
    Ridge,
    /// One summit standing far above the rest, with no grain: a volcano
    /// such as Erciyes or Süphan.
    Cone,
    /// High ground with little relief: a tableland such as the central
    /// Anatolian plateau.
    Plateau,
}

impl MassifKind {
    pub const ALL: [MassifKind; 4] = [MassifKind::Massif, MassifKind::Ridge, MassifKind::Cone, MassifKind::Plateau];

    /// The pipeline's names ("massif", "ridge", "cone", "plateau").
    pub fn from_name(name: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|k| k.name() == name)
    }

    pub fn name(self) -> &'static str {
        match self {
            MassifKind::Massif => "massif",
            MassifKind::Ridge => "ridge",
            MassifKind::Cone => "cone",
            MassifKind::Plateau => "plateau",
        }
    }
}

/// Summits kept per hex.
pub const SUMMITS: usize = 3;
/// A summit's height is stored in steps of this many metres.
pub const HEIGHT_STEP: f64 = 20.0;
/// Summit positions are stored in hundredths of a hex-local unit.
const POS_SCALE: f64 = 100.0;

/// One summit: its position in hex-local coordinates (corners on the unit
/// circle, +x east, +y north) and how far it stands above the hex's floor.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Summit {
    x: i8,
    y: i8,
    height: u8,
}

impl Summit {
    /// `x`, `y` hex-local, `height_m` metres above the floor (both clamped
    /// to what the encoding holds: ±1.27 units, 5100 m).
    pub fn new(x: f64, y: f64, height_m: f64) -> Self {
        let pos = |v: f64| (v * POS_SCALE).round().clamp(-127.0, 127.0) as i8;
        Summit { x: pos(x), y: pos(y), height: (height_m / HEIGHT_STEP).round().clamp(0.0, 255.0) as u8 }
    }

    pub fn pos(self) -> (f64, f64) {
        (self.x as f64 / POS_SCALE, self.y as f64 / POS_SCALE)
    }

    pub fn height_m(self) -> f64 {
        self.height as f64 * HEIGHT_STEP
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Massif {
    pub kind: MassifKind,
    /// Strike of the high ground, 0..180° anticlockwise from +x, in 1/256ths
    /// of a half turn. In hex-local coordinates (both axes in degrees of
    /// arc, like the summits), not on the ground: the board squashes x by
    /// the cosine of the latitude, and the props stretch along the strike
    /// as it appears there. Only meaningful with some `coherence`.
    strike: u8,
    /// How cleanly the high ground lines up along the strike, 0..255.
    coherence: u8,
    /// The hex's floor (10th-percentile elevation), metres, present-day datum.
    pub floor: i16,
    /// Highest first; at most [`SUMMITS`].
    pub summits: Vec<Summit>,
}

impl Massif {
    /// `strike_deg` is folded into 0..180; `coherence` clamped to 0..1.
    pub fn new(kind: MassifKind, strike_deg: f64, coherence: f64, floor: f64, summits: Vec<Summit>) -> Self {
        let strike = (strike_deg.rem_euclid(180.0) / 180.0 * 256.0).round() as u32 % 256;
        Massif {
            kind,
            strike: strike as u8,
            coherence: (coherence.clamp(0.0, 1.0) * 255.0).round() as u8,
            floor: floor.round().clamp(i16::MIN as f64, i16::MAX as f64) as i16,
            summits,
        }
    }

    pub fn strike_deg(&self) -> f64 {
        self.strike as f64 / 256.0 * 180.0
    }

    pub fn coherence(&self) -> f64 {
        self.coherence as f64 / 255.0
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.summits.len() > SUMMITS {
            return Err(format!("massif has {} summits (at most {SUMMITS})", self.summits.len()));
        }
        if self.summits.windows(2).any(|w| w[0].height < w[1].height) {
            return Err("massif summits are not highest first".into());
        }
        Ok(())
    }

    /// The four RGBA8 texels the board reads (see `terrain_art.wgsl`,
    /// `art_massif`). Texel 0: kind + 1, strike, coherence, floor in
    /// [`HEIGHT_STEP`]s above -1000 m. Texels 1-3: a summit's x and y
    /// (hundredths of a unit, offset by 128), height in steps, and 255 if
    /// the summit exists.
    pub fn texels(&self) -> [u8; 16] {
        let mut out = [0u8; 16];
        let floor = ((self.floor as f64 + 1000.0) / HEIGHT_STEP).round().clamp(0.0, 255.0) as u8;
        out[..4].copy_from_slice(&[self.kind as u8 + 1, self.strike, self.coherence, floor]);
        for (k, s) in self.summits.iter().take(SUMMITS).enumerate() {
            let at = 4 + k * 4;
            out[at..at + 4].copy_from_slice(&[(s.x as i16 + 128) as u8, (s.y as i16 + 128) as u8, s.height, 255]);
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn summits_and_strike_round_trip_through_the_encoding() {
        let s = Summit::new(0.28, -0.61, 2244.0);
        assert_eq!(s.pos(), (0.28, -0.61));
        assert_eq!(s.height_m(), 2240.0);
        assert_eq!(Summit::new(2.0, -2.0, 9000.0).pos(), (1.27, -1.27));
        let m = Massif::new(MassifKind::Ridge, 190.0, 0.41, -355.0, vec![s]);
        assert!((m.strike_deg() - 10.0).abs() < 0.5);
        assert!((m.coherence() - 0.41).abs() < 0.01);
        assert_eq!(Massif::new(MassifKind::Ridge, 179.9, 0.0, 0.0, vec![]).strike_deg(), 0.0);
    }

    #[test]
    fn texels_pack_kind_summits_and_floor() {
        let m = Massif::new(MassifKind::Cone, 0.0, 0.07, 1072.0, vec![Summit::new(0.28, 0.61, 2244.0), Summit::new(-1.0, 0.0, 700.0)]);
        let t = m.texels();
        assert_eq!(t[0], MassifKind::Cone as u8 + 1);
        assert_eq!(t[3], 104); // (1072 + 1000) / 20
        assert_eq!(&t[4..8], &[156, 189, 112, 255]);
        assert_eq!(&t[8..12], &[28, 128, 35, 255]);
        assert_eq!(&t[12..16], &[0, 0, 0, 0]);
    }

    #[test]
    fn validate_rejects_too_many_or_unordered_summits() {
        let s = |h| Summit::new(0.0, 0.0, h);
        assert!(Massif::new(MassifKind::Massif, 0.0, 0.0, 0.0, vec![s(900.0), s(300.0)]).validate().is_ok());
        assert!(Massif::new(MassifKind::Massif, 0.0, 0.0, 0.0, vec![s(300.0), s(900.0)]).validate().is_err());
        assert!(Massif::new(MassifKind::Massif, 0.0, 0.0, 0.0, vec![s(1.0); 4]).validate().is_err());
        assert_eq!(MassifKind::from_name("plateau"), Some(MassifKind::Plateau));
        assert_eq!(MassifKind::from_name("mesa"), None);
    }
}
