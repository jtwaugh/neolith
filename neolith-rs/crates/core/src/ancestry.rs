//! Autosomal ancestry of individual ancient genomes (isostyle's
//! `neolith-ancestry-samples-1` export, written up in `data/ancestry/SOURCES.md`
//! in the parent repo), for the Ancestry map mode's sample pins and the
//! inspector's strip of individuals over time.
//!
//! Each sample's weights are a qpAdm model estimate against a fixed set of
//! reference groups ([`Ancestry::components`]): shared ancestry, not a
//! people, language or culture. Nothing here is computed in the app, and
//! nothing fills land without samples.

use crate::geom::great_circle_km;
use crate::grid::LonLat;
use crate::time::Year;
use serde::{Deserialize, Serialize};

/// A reference group the proportions are measured against.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Component {
    /// Short key, e.g. `ana`; the evidence layer for it is `anc_<key>`.
    pub key: String,
    /// Plain name, e.g. "Anatolian farmer".
    pub name: String,
}

/// How a sample's model came out.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Status {
    /// A model was accepted; the sample has weights.
    Fit,
    /// No feasible model of up to four sources.
    NoFit,
    /// Too few SNPs to model.
    LowCoverage,
    /// One of the individuals a reference group is made of: 100% its own
    /// source by construction, so shown but flagged.
    Reference,
}

impl Status {
    pub fn label(self) -> &'static str {
        match self {
            Status::Fit => "model fits",
            Status::NoFit => "no model fits",
            Status::LowCoverage => "too little DNA to model",
            Status::Reference => "reference individual",
        }
    }
}

/// One ancient individual.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Sample {
    /// AADR individual id.
    pub id: String,
    /// AADR group label.
    pub group: String,
    pub locality: String,
    pub pos: LonLat,
    /// Date mean and standard deviation in years.
    pub year: Year,
    pub sd: u16,
    /// SNPs covered on the 1240K set.
    pub snps: u32,
    pub status: Status,
    /// The accepted model's sources, e.g. `whg+ana`.
    pub model: String,
    /// The model's p-value in thousandths, if modelled.
    pub p_milli: Option<u16>,
    /// Share per component in thousandths, in [`Ancestry::components`] order;
    /// empty unless the status is [`Status::Fit`] or [`Status::Reference`].
    pub weights: Vec<u16>,
    /// The paper that first reported the individual, as AADR abbreviates it.
    pub publication: String,
}

impl Sample {
    /// Share per component, 0..1; `None` without a model.
    pub fn shares(&self) -> Option<Vec<f32>> {
        (!self.weights.is_empty()).then(|| self.weights.iter().map(|w| *w as f32 / 1000.0).collect())
    }

    /// How much of the sample's date distribution falls within `half` years
    /// of `year`, 0..1 (a normal distribution with the sample's mean and SD).
    pub fn overlap(&self, year: Year, half: f32) -> f32 {
        let sd = (self.sd as f32).max(1.0);
        let z = |y: f32| (y - self.year.0 as f32) / (sd * std::f32::consts::SQRT_2);
        0.5 * (erf(z(year.0 as f32 + half)) - erf(z(year.0 as f32 - half)))
    }
}

/// Abramowitz & Stegun 7.1.26; error below 1.5e-7.
fn erf(x: f32) -> f32 {
    let t = 1.0 / (1.0 + 0.327_591_1 * x.abs());
    let y = 1.0 - (((((1.061_405_4 * t - 1.453_152_1) * t) + 1.421_413_8) * t - 0.284_496_72) * t + 0.254_829_6) * t * (-x * x).exp();
    y.copysign(x)
}

/// The sample table.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Ancestry {
    pub components: Vec<Component>,
    /// Sorted by date, oldest first.
    pub samples: Vec<Sample>,
}

impl Ancestry {
    /// Samples within `km` of `p`, oldest first, with their distance.
    pub fn near(&self, p: LonLat, km: f64) -> Vec<(&Sample, f64)> {
        // A cheap latitude cut before the great-circle distance.
        let dlat = km / 111.0;
        self.samples
            .iter()
            .filter(|s| (s.pos.lat - p.lat).abs() <= dlat)
            .map(|s| (s, great_circle_km([s.pos.lon, s.pos.lat], [p.lon, p.lat])))
            .filter(|(_, d)| *d <= km)
            .collect()
    }

    /// The date-weighted mean shares of the fitted samples within `km` of
    /// `p` around `year`, and the weight behind them (effective genomes).
    /// `None` when no fitted sample is in reach.
    pub fn mean_near(&self, p: LonLat, km: f64, year: Year, half: f32) -> Option<(Vec<f32>, f32)> {
        let mut sum = vec![0.0f32; self.components.len()];
        let mut total = 0.0f32;
        for (s, _) in self.near(p, km) {
            if s.status != Status::Fit {
                continue;
            }
            let w = s.overlap(year, half);
            for (a, v) in sum.iter_mut().zip(&s.weights) {
                *a += w * *v as f32 / 1000.0;
            }
            total += w;
        }
        (total > 1e-3).then(|| (sum.iter().map(|v| v / total).collect(), total))
    }

    pub fn validate(&self) -> Result<(), String> {
        let n = self.components.len();
        if n == 0 && !self.samples.is_empty() {
            return Err("ancestry: samples without components".into());
        }
        for s in &self.samples {
            let modelled = matches!(s.status, Status::Fit | Status::Reference);
            if modelled != (s.weights.len() == n) || (!modelled && !s.weights.is_empty()) {
                return Err(format!("ancestry sample {}: {} weights for status {:?}", s.id, s.weights.len(), s.status));
            }
            let sum: u32 = s.weights.iter().map(|w| *w as u32).sum();
            if modelled && !(985..=1015).contains(&sum) {
                return Err(format!("ancestry sample {}: weights sum to {sum}/1000", s.id));
            }
            if !(-90.0..=90.0).contains(&s.pos.lat) || !(-180.0..=180.0).contains(&s.pos.lon) {
                return Err(format!("ancestry sample {}: bad position", s.id));
            }
        }
        if self.samples.windows(2).any(|w| w[0].year > w[1].year) {
            return Err("ancestry: samples are not sorted by date".into());
        }
        Ok(())
    }
}

/// The number of components the map mode's codes are built for.
pub const COMPONENTS: usize = 6;
/// A hex's mixture is shown in steps of 1 / `STEPS` of each component.
pub const STEPS: u8 = 4;
/// Mixtures of [`COMPONENTS`] components in [`STEPS`] steps: C(9, 5).
pub const MIXTURES: u8 = 126;
/// The code for "no genome in reach": the hex is drawn as unknown.
pub const NO_CODE: u8 = 255;

/// Every mixture, in code order: the steps of each component, summing to
/// [`STEPS`]. Lexicographic, first component most significant.
pub fn mixtures() -> Vec<[u8; COMPONENTS]> {
    fn fill(k: usize, left: u8, cur: &mut [u8; COMPONENTS], out: &mut Vec<[u8; COMPONENTS]>) {
        if k == COMPONENTS - 1 {
            cur[k] = left;
            out.push(*cur);
            return;
        }
        for v in 0..=left {
            cur[k] = v;
            fill(k + 1, left - v, cur, out);
        }
    }
    let mut out = Vec::with_capacity(MIXTURES as usize);
    fill(0, STEPS, &mut [0; COMPONENTS], &mut out);
    out
}

/// Shares rounded to steps that sum to [`STEPS`] (largest remainders get the
/// spare steps, so a rounded mixture is still a whole).
pub fn quantise(shares: &[f32; COMPONENTS]) -> [u8; COMPONENTS] {
    let total: f32 = shares.iter().sum::<f32>().max(1e-6);
    let exact: [f32; COMPONENTS] = std::array::from_fn(|k| shares[k].max(0.0) / total * STEPS as f32);
    let mut steps: [u8; COMPONENTS] = std::array::from_fn(|k| exact[k].floor() as u8);
    let mut order: [usize; COMPONENTS] = std::array::from_fn(|k| k);
    order.sort_by(|a, b| (exact[*b] - exact[*b].floor()).total_cmp(&(exact[*a] - exact[*a].floor())));
    let spare = STEPS.saturating_sub(steps.iter().sum());
    for k in order.iter().take(spare as usize) {
        steps[*k] += 1;
    }
    steps
}

/// The map code of a mixture: its index in [`mixtures`], plus [`MIXTURES`]
/// when few genomes stand behind it (`thin`).
pub fn code(shares: &[f32; COMPONENTS], thin: bool) -> u8 {
    let steps = quantise(shares);
    let index = mixtures().iter().position(|m| *m == steps).unwrap_or(0) as u8;
    index + if thin { MIXTURES } else { 0 }
}

/// A code's mixture as shares (0..1) and whether it is thin; `None` for
/// [`NO_CODE`] and anything else out of range.
pub fn decode(code: u8) -> Option<([f32; COMPONENTS], bool)> {
    if code >= 2 * MIXTURES {
        return None;
    }
    let m = mixtures()[(code % MIXTURES) as usize];
    Some((std::array::from_fn(|k| m[k] as f32 / STEPS as f32), code >= MIXTURES))
}

#[cfg(test)]
pub(crate) fn test_table() -> Ancestry {
    let sample = |id: &str, lon: f64, year: i32, status: Status, weights: &[u16]| Sample {
        id: id.into(),
        group: "Test_N".into(),
        locality: "Test cave".into(),
        pos: LonLat::new(lon, 49.0),
        year: Year(year),
        sd: 100,
        snps: 500_000,
        status,
        model: if weights.is_empty() { String::new() } else { "a+b".into() },
        p_milli: (!weights.is_empty()).then_some(420),
        weights: weights.to_vec(),
        publication: "TestEtAl2020".into(),
    };
    Ancestry {
        components: vec![Component { key: "a".into(), name: "A".into() }, Component { key: "b".into(), name: "B".into() }],
        samples: vec![
            sample("old", 1.0, -8000, Status::Fit, &[1000, 0]),
            sample("mid", 1.2, -6000, Status::Fit, &[250, 750]),
            sample("thin", 1.1, -6000, Status::LowCoverage, &[]),
            sample("far", 30.0, -6000, Status::Fit, &[0, 1000]),
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn overlap_is_the_normal_mass_in_the_window() {
        let t = test_table();
        let s = &t.samples[1];
        assert!((s.overlap(Year(-6000), 100.0) - 0.6827).abs() < 1e-3);
        assert!((s.overlap(Year(-6000), 5000.0) - 1.0).abs() < 1e-4);
        assert!(s.overlap(Year(-3000), 100.0) < 1e-6);
    }

    #[test]
    fn near_and_mean() {
        let t = test_table();
        let here = LonLat::new(1.0, 49.0);
        let near = t.near(here, 300.0);
        assert_eq!(near.iter().map(|(s, _)| s.id.as_str()).collect::<Vec<_>>(), ["old", "mid", "thin"]);
        let (mix, weight) = t.mean_near(here, 300.0, Year(-6000), 500.0).unwrap();
        assert!((mix[0] - 0.25).abs() < 1e-3 && (mix[1] - 0.75).abs() < 1e-3, "only the fitted sample of that date counts");
        assert!(weight > 0.99 && weight < 1.01);
        assert_eq!(t.mean_near(here, 300.0, Year(-3000), 500.0), None, "no genome, no value");
        assert_eq!(t.mean_near(LonLat::new(15.0, 49.0), 300.0, Year(-6000), 500.0), None);
    }

    #[test]
    fn codes_cover_every_mixture_once() {
        let all = mixtures();
        assert_eq!(all.len(), MIXTURES as usize);
        assert!(all.iter().all(|m| m.iter().sum::<u8>() == STEPS));
        assert!(all.windows(2).all(|w| w[0] < w[1]), "sorted, so distinct");
        assert!(2 * (MIXTURES as u16) < 254, "codes stay clear of the sea index and NO_CODE");
        for (i, m) in all.iter().enumerate() {
            let shares: [f32; COMPONENTS] = std::array::from_fn(|k| m[k] as f32 / STEPS as f32);
            assert_eq!(code(&shares, false), i as u8);
            assert_eq!(decode(code(&shares, true)), Some((shares, true)));
        }
        assert_eq!(decode(NO_CODE), None);
        assert_eq!(decode(252), None);
    }

    #[test]
    fn quantising_keeps_the_whole() {
        // 90% + 10% rounds to all of the first; 60/40 to 2 and 2 of 4... largest remainder decides.
        assert_eq!(quantise(&[0.9, 0.1, 0.0, 0.0, 0.0, 0.0]), [4, 0, 0, 0, 0, 0]);
        assert_eq!(quantise(&[0.7, 0.3, 0.0, 0.0, 0.0, 0.0]), [3, 1, 0, 0, 0, 0]);
        assert_eq!(quantise(&[0.34, 0.33, 0.33, 0.0, 0.0, 0.0]).iter().sum::<u8>(), STEPS);
        // Shares that do not quite sum to 1 (binned layer values) are normalised.
        assert_eq!(quantise(&[0.45, 0.45, 0.0, 0.0, 0.0, 0.0]), [2, 2, 0, 0, 0, 0]);
    }

    #[test]
    fn validation() {
        let mut t = test_table();
        assert_eq!(t.validate(), Ok(()));
        t.samples[1].weights = vec![250, 500];
        assert!(t.validate().is_err(), "weights must sum to 1");
        let mut t = test_table();
        t.samples[2].weights = vec![500, 500];
        assert!(t.validate().is_err(), "an unmodelled sample has no weights");
        let mut t = test_table();
        t.samples.swap(0, 1);
        assert!(t.validate().is_err());
    }
}
