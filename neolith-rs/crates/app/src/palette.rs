//! Colours, as `const` tables keyed by the typed enums. A colour can never be
//! assigned implicitly: every value of every property has an entry here, and
//! the tests check the tables are complete.

use neolith_core::elevation::{self, BAND_COUNT};
use neolith_core::evidence;
use neolith_core::farming;
use neolith_core::forager;
use neolith_core::productivity;
use neolith_core::residuals;
use neolith_core::{Koeppen, MapMode, PopDensity, Terrain, Value, NO_DATA};

pub type Rgb = [u8; 3];

const fn hex(c: u32) -> Rgb {
    [(c >> 16) as u8, (c >> 8) as u8, c as u8]
}

/// Shown where no keyframe is in effect yet.
pub const NO_DATA_COLOUR: Rgb = hex(0x3a3a3a);

pub const fn terrain(t: Terrain) -> Rgb {
    match t {
        Terrain::Ice => hex(0xbfd1e5),
        Terrain::Water => hex(0x3a5a6c), // dark slate: quieter than any land, so coasts read (MAP_STYLE.md)
        Terrain::Plains => hex(0xeef0b4),
        Terrain::Mountains => hex(0xbdbdbd),
        Terrain::Chaparral => hex(0xa1887f),
        Terrain::ExtremeDesert => hex(0xe0bd85),
        Terrain::SemiDesert => hex(0xf5deb3),
        Terrain::Free => hex(0xffffff),
        Terrain::Savannah => hex(0xc9a43a),
        Terrain::Woodlands => hex(0x8bc34a),
        Terrain::TropicalForest => hex(0x2e8b3c),
        Terrain::Grassland => hex(0xd7d062),
        Terrain::TemperateForest => hex(0x689f38),
        Terrain::SteppeForest => hex(0xa2d0a5),
        Terrain::BorealForest => hex(0x1f5f4a),
        Terrain::Tundra => hex(0x8f9c8a),
        Terrain::Alpine => hex(0xb2a6d3),
        // Not in the old colour domain (they got recycled colours); explicit now.
        Terrain::Land => hex(0xb39b73),
        Terrain::Unknown => hex(0x8d7f96),
        Terrain::Floodplain => hex(0x4fc26b),
    }
}

/// The standard Köppen–Geiger palette, copied from `settings.COLOR_SCHEMES`.
const KOEPPEN: [Rgb; Koeppen::COUNT as usize] = [
    hex(0x184a85), hex(0x1c00ff), hex(0x3183ff), hex(0x61b2f3), hex(0xf40000), hex(0xf8a09f),
    hex(0xf1af00), hex(0xfce163), hex(0xfeff00), hex(0xcdce00), hex(0xa0a100), hex(0xabff9b),
    hex(0x7bd069), hex(0x4aa12d), hex(0xd2ff44), hex(0x83ff48), hex(0x54ce00), hex(0xf500ff),
    hex(0xc700d2), hex(0x9b37a3), hex(0x9e6fa2), hex(0xb6b8ff), hex(0x6a83e5), hex(0x585ac1),
    hex(0x380095), hex(0x57ffff), hex(0x5cceff), hex(0x2a8889), hex(0x164f6d), hex(0xbbbbbb),
    hex(0x717170),
];

pub fn koeppen(k: Koeppen) -> Rgb {
    KOEPPEN[k.index() as usize]
}

/// A perceptual ramp (viridis), in bucket order: denser is always lighter.
pub const fn pop(p: PopDensity) -> Rgb {
    match p {
        PopDensity::P0_0 => hex(0x440154),
        PopDensity::P0_1 => hex(0x472d7b),
        PopDensity::P0_3 => hex(0x3b528b),
        PopDensity::P0_5 => hex(0x2c728e),
        PopDensity::P0_8 => hex(0x21918c),
        PopDensity::P1_0 => hex(0x28ae80),
        PopDensity::P1_5 => hex(0x5ec962),
        PopDensity::P2_0 => hex(0xaddc30),
        PopDensity::P5_0 => hex(0xfde725),
    }
}

/// Elevation bands ([`elevation::band`] order): water from deep to
/// shallow, then conventional hypsometric tints from below today's sea level
/// up to the high plateaus.
const ELEVATION: [Rgb; BAND_COUNT as usize] = [
    // Water: deeper than 4000 m … 0–50 m.
    hex(0x0b2a55), hex(0x123d73), hex(0x1a5291), hex(0x2b6cb0), hex(0x4a8cc9), hex(0x78ace0), hex(0xa9cdee),
    // Land: below 0 m, 0–50, 50–100, 100–200, 200–300, 300–500.
    hex(0x3f7f5a), hex(0x5f9e5f), hex(0x84b66a), hex(0xadcc7c), hex(0xd2dd8f), hex(0xeadb98),
    // 500–750, 750–1000, 1000–1500, 1500–2000, 2000–2500, 2500 and up.
    hex(0xe2bf7b), hex(0xd3a066), hex(0xbb8256), hex(0x9c674a), hex(0x87675c), hex(0xd8d2cc),
];

pub fn elevation(band: u8) -> Rgb {
    ELEVATION.get(band as usize).copied().unwrap_or(NO_DATA_COLOUR)
}

/// Productivity bands ([`productivity::band`] order): bare ground through
/// dry grass to dense forest, light to dark so the ramp also reads in grey.
const PRODUCTIVITY: [Rgb; productivity::BAND_COUNT as usize] = [
    hex(0xf3ead2), hex(0xe9dcae), hex(0xdccf8a), hex(0xc4c672), hex(0xa3bb62),
    hex(0x7fac57), hex(0x5c9a4e), hex(0x3e8547), hex(0x276c40), hex(0x145237),
];

pub fn productivity(band: u8) -> Rgb {
    PRODUCTIVITY.get(band as usize).copied().unwrap_or(NO_DATA_COLOUR)
}

/// Biodiversity bands ([`forager::biodiversity_band`] order), light to dark.
/// Purple, so it can't be mistaken for the productivity it is derived from.
const BIODIVERSITY: [Rgb; forager::BIODIVERSITY_BAND_COUNT as usize] = [
    hex(0xf4eef5), hex(0xe6d8ea), hex(0xd6c0de), hex(0xc4a7d1), hex(0xb08dc3),
    hex(0x9a74b3), hex(0x835ca1), hex(0x6b468b), hex(0x533272), hex(0x3b2157),
];

pub fn biodiversity(band: u8) -> Rgb {
    BIODIVERSITY.get(band as usize).copied().unwrap_or(NO_DATA_COLOUR)
}

/// Expected-population bands ([`farming::band`] order): the viridis ramp
/// the Population mode uses, dark for empty land to yellow for the densest.
const EXPECTED: [Rgb; farming::BAND_COUNT as usize] = [
    hex(0x440154), hex(0x482878), hex(0x3e4a89), hex(0x31688e), hex(0x26828e),
    hex(0x1f9e89), hex(0x35b779), hex(0x6ece58), hex(0xb5de2b), hex(0xfde725),
];

pub fn expected(band: u8) -> Rgb {
    EXPECTED.get(band as usize).copied().unwrap_or(NO_DATA_COLOUR)
}

/// The evidence ramp: plasma (Kovesi/matplotlib), a perceptual sequential
/// ramp distinct from the viridis of the population modes. Anchors at every
/// tenth; [`evidence_colour`] interpolates the 50 value bins between them.
const PLASMA: [Rgb; 11] = [
    hex(0x0d0887), hex(0x41049d), hex(0x6a00a8), hex(0x8f0da4), hex(0xb12a90), hex(0xcc4778),
    hex(0xe16462), hex(0xf2844b), hex(0xfca636), hex(0xfcce25), hex(0xf0f921),
];

/// The neutral grey that speculative evidence values fade towards.
pub const EVIDENCE_GREY: Rgb = hex(0x9a9893);

/// How much of the ramp colour each confidence level keeps (the rest is
/// [`EVIDENCE_GREY`]): full for observed, fading through judged high,
/// medium and low to extrapolated.
/// Steps are wide enough that adjacent levels read apart at any value.
pub const EVIDENCE_STRENGTH: [f32; evidence::LEVELS as usize] = [1.0, 0.7, 0.48, 0.3, 0.15];

fn mix(a: Rgb, b: Rgb, t: f32) -> Rgb {
    std::array::from_fn(|k| (a[k] as f32 + (b[k] as f32 - a[k] as f32) * t).round() as u8)
}

/// The colour of value bin `bin` (0..[`evidence::BINS`]) at confidence
/// level `confidence` (0..[`evidence::LEVELS`]).
pub fn evidence_colour(confidence: u8, bin: u8) -> Rgb {
    let t = (bin.min(evidence::BINS - 1) as f32 + 0.5) / evidence::BINS as f32 * (PLASMA.len() - 1) as f32;
    let k = (t.floor() as usize).min(PLASMA.len() - 2);
    let ramp = mix(PLASMA[k], PLASMA[k + 1], t - k as f32);
    let strength = EVIDENCE_STRENGTH.get(confidence as usize).copied().unwrap_or(0.0);
    mix(EVIDENCE_GREY, ramp, strength)
}

/// The colour of an evidence code ([`neolith_core::evidence`]);
/// [`NO_DATA_COLOUR`] for [`evidence::NO_VALUE`].
pub fn evidence(code: u8) -> Rgb {
    match (evidence::confidence(code), evidence::bin(code)) {
        (Some(c), Some(b)) => evidence_colour(c, b),
        _ => NO_DATA_COLOUR,
    }
}

/// Missing-sites bands ([`residuals::band`] order): a neutral for "fewer
/// than half a site", then one blue from light to dark.
const MISSING: [Rgb; residuals::BAND_COUNT as usize] =
    [hex(0xd9d8d2), hex(0x86b6ef), hex(0x5598e7), hex(0x2a78d6), hex(0x1c5cab), hex(0x0d366b)];

pub fn missing(band: u8) -> Rgb {
    MISSING.get(band as usize).copied().unwrap_or(NO_DATA_COLOUR)
}

pub fn colour(v: Value) -> Rgb {
    match v {
        Value::Terrain(t) => terrain(t),
        Value::Koeppen(k) => koeppen(k),
        Value::Pop(p) => pop(p),
    }
}

pub const PALETTE_WIDTH: usize = 256;

/// Palette entry the shader uses for Water hexes in the Köppen and
/// Population modes, so the sea is one calm colour there instead of a data
/// value (zero population, the Ocean code). Matches `SEA_INDEX` in board.wgsl.
pub const SEA_INDEX: u8 = 254;
pub const SEA_COLOUR: Rgb = hex(0x5f7d99);

/// The colour of byte `v` of a snapshot layer ([`neolith_core::Snapshot::layer`]).
pub fn layer_colour(mode: MapMode, v: u8) -> Rgb {
    match (mode, mode.prop()) {
        (_, Some(prop)) => Value::from_u8(prop, v).map_or(NO_DATA_COLOUR, colour),
        (MapMode::Npp, None) => productivity(v),
        (MapMode::Biodiversity, None) => biodiversity(v),
        (MapMode::Expected, None) => expected(v),
        (MapMode::Evidence, None) => evidence(v),
        (MapMode::Missing, None) => missing(v),
        (_, None) => elevation(v),
    }
}

/// Palette texture rows: one per [`MapMode`].
pub const PALETTE_ROWS: usize = MapMode::ALL.len();

/// The GPU palette texture: 256 × [`PALETTE_ROWS`] RGBA8 (sRGB), one row per
/// map mode, indexed by the snapshot layer byte. Unused entries (and
/// `NO_DATA`) are dark grey.
pub fn palette_texture() -> Vec<u8> {
    let mut px = Vec::with_capacity(PALETTE_WIDTH * PALETTE_ROWS * 4);
    for mode in MapMode::ALL {
        for i in 0..PALETTE_WIDTH {
            let sea = i == SEA_INDEX as usize && matches!(mode, MapMode::Koeppen | MapMode::Pop | MapMode::Npp | MapMode::Biodiversity | MapMode::Expected | MapMode::Evidence | MapMode::Missing);
            let c = if sea { SEA_COLOUR } else { layer_colour(mode, i as u8) };
            px.extend_from_slice(&[c[0], c[1], c[2], 255]);
        }
    }
    debug_assert!(Value::from_u8(neolith_core::Prop::Terrain, NO_DATA).is_none());
    debug_assert!(elevation::band_label(NO_DATA).is_none());
    px
}

#[cfg(test)]
mod tests {
    use super::*;

    fn luma(c: Rgb) -> f64 {
        0.2126 * c[0] as f64 + 0.7152 * c[1] as f64 + 0.0722 * c[2] as f64
    }

    #[test]
    fn population_ramp_is_monotonic() {
        let l: Vec<f64> = PopDensity::ALL.iter().map(|p| luma(pop(*p))).collect();
        assert!(l.windows(2).all(|w| w[0] < w[1]), "{l:?}");
    }

    /// CIELAB (D65) of an sRGB colour.
    fn lab(c: Rgb) -> [f64; 3] {
        let lin = |v: u8| {
            let v = v as f64 / 255.0;
            if v <= 0.04045 { v / 12.92 } else { ((v + 0.055) / 1.055).powf(2.4) }
        };
        let [r, g, b] = c.map(lin);
        let x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
        let y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        let z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
        let f = |t: f64| if t > 0.008856 { t.cbrt() } else { 7.787 * t + 16.0 / 116.0 };
        [116.0 * f(y) - 16.0, 500.0 * (f(x) - f(y)), 200.0 * (f(y) - f(z))]
    }

    fn delta_e(a: Rgb, b: Rgb) -> f64 {
        let (a, b) = (lab(a), lab(b));
        ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2)).sqrt()
    }

    /// Not just different bytes: every pair of terrains must be told apart
    /// at a glance (CIE76 ΔE; about 2 is a just-noticeable difference).
    #[test]
    fn terrain_colours_are_perceptually_distinct() {
        for (i, a) in Terrain::ALL.iter().enumerate() {
            for b in &Terrain::ALL[i + 1..] {
                let d = delta_e(terrain(*a), terrain(*b));
                assert!(d >= 12.0, "{a:?} and {b:?} look alike (ΔE {d:.1})");
            }
        }
    }

    #[test]
    fn water_gets_lighter_towards_the_shore() {
        let l: Vec<f64> = (0..elevation::LAND_BAND).map(|b| luma(elevation(b))).collect();
        assert!(l.windows(2).all(|w| w[0] < w[1]), "{l:?}");
    }

    #[test]
    fn productivity_ramp_darkens_and_has_its_own_row() {
        let l: Vec<f64> = (0..productivity::BAND_COUNT).map(|b| luma(productivity(b))).collect();
        assert!(l.windows(2).all(|w| w[1] < w[0]), "{l:?}");
        let px = palette_texture();
        assert_eq!(px.len(), PALETTE_WIDTH * PALETTE_ROWS * 4);
        let o = (MapMode::Npp.index() * PALETTE_WIDTH + 3) * 4;
        assert_eq!(px[o..o + 3], productivity(3));
        let sea = (MapMode::Npp.index() * PALETTE_WIDTH + SEA_INDEX as usize) * 4;
        assert_eq!(px[sea..sea + 3], SEA_COLOUR);
        let l: Vec<f64> = (0..forager::BIODIVERSITY_BAND_COUNT).map(|b| luma(biodiversity(b))).collect();
        assert!(l.windows(2).all(|w| w[1] < w[0]), "{l:?}");
        let o = (MapMode::Biodiversity.index() * PALETTE_WIDTH + 7) * 4;
        assert_eq!(px[o..o + 3], biodiversity(7));
        let l: Vec<f64> = (0..farming::BAND_COUNT).map(|b| luma(expected(b))).collect();
        assert!(l.windows(2).all(|w| w[1] > w[0]), "{l:?}");
        let o = (MapMode::Expected.index() * PALETTE_WIDTH + 9) * 4;
        assert_eq!(px[o..o + 3], expected(9));
    }

    #[test]
    fn evidence_row_ramps_and_fades_with_confidence() {
        use neolith_core::evidence::{BINS, LEVELS, NO_VALUE};
        // Every code has a colour, and the codes past the last level are no data.
        let px = palette_texture();
        let row = MapMode::Evidence.index();
        assert_eq!(row, 7);
        assert_eq!(PALETTE_ROWS, MapMode::ALL.len());
        let at = |i: usize| [px[(row * 256 + i) * 4], px[(row * 256 + i) * 4 + 1], px[(row * 256 + i) * 4 + 2]];
        for c in 0..LEVELS {
            for b in 0..BINS {
                let code = c * BINS + b;
                assert_eq!(at(code as usize), evidence_colour(c, b), "code {code}");
                assert_eq!(evidence(code), evidence_colour(c, b));
            }
        }
        assert_eq!(at(NO_VALUE as usize), NO_DATA_COLOUR);
        assert_eq!(at(SEA_INDEX as usize), SEA_COLOUR);
        assert!(((LEVELS * BINS) as usize..SEA_INDEX as usize).all(|i| at(i) == NO_DATA_COLOUR));
        // Observed: the ramp itself, perceptually ordered (lighter with the value).
        assert_eq!(evidence_colour(0, 0), mix(PLASMA[0], PLASMA[1], 0.1));
        let l: Vec<f64> = (0..BINS).map(|b| lab(evidence_colour(0, b))[0]).collect();
        assert!(l.windows(2).all(|w| w[1] > w[0]), "{l:?}");
        // Each level is closer to the grey than the one before, and still a ramp.
        for b in [0, 20, 49] {
            let d: Vec<f64> = (0..LEVELS).map(|c| delta_e(evidence_colour(c, b), EVIDENCE_GREY)).collect();
            assert!(d.windows(2).all(|w| w[1] < w[0]), "bin {b}: {d:?}");
        }
        for c in 0..LEVELS {
            assert!(delta_e(evidence_colour(c, 0), evidence_colour(c, BINS - 1)) > 15.0, "level {c} still shows the value");
        }
        assert!(EVIDENCE_STRENGTH.windows(2).all(|w| w[1] < w[0]));
        assert!(delta_e(EVIDENCE_GREY, NO_DATA_COLOUR) > 20.0, "faded values must not read as no data");
    }

    #[test]
    fn missing_sites_row_darkens_with_the_count() {
        let l: Vec<f64> = (1..residuals::BAND_COUNT).map(|b| luma(missing(b))).collect();
        assert!(l.windows(2).all(|w| w[1] < w[0]), "{l:?}");
        assert!(luma(missing(0)) > luma(missing(1)));
        let px = palette_texture();
        let at = |i: usize| {
            let o = (MapMode::Missing.index() * PALETTE_WIDTH + i) * 4;
            [px[o], px[o + 1], px[o + 2]]
        };
        assert_eq!(at(4), missing(4));
        assert_eq!(at(SEA_INDEX as usize), SEA_COLOUR);
        assert_eq!(at(NO_DATA as usize), NO_DATA_COLOUR);
        assert_eq!(missing(residuals::BAND_COUNT), NO_DATA_COLOUR);
    }

    #[test]
    fn elevation_colours_are_distinct() {
        let mut seen = std::collections::HashSet::new();
        for b in 0..BAND_COUNT {
            assert!(seen.insert(elevation(b)), "band {b} reuses a colour");
        }
    }

    #[test]
    fn palette_texture_layout() {
        let px = palette_texture();
        assert_eq!(px.len(), 256 * PALETTE_ROWS * 4);
        let row3 = |i: usize| [px[(3 * 256 + i) * 4], px[(3 * 256 + i) * 4 + 1], px[(3 * 256 + i) * 4 + 2]];
        assert_eq!(row3(0), elevation(0));
        assert_eq!(row3(255), NO_DATA_COLOUR);
        let row = |r: usize, i: usize| [px[(r * 256 + i) * 4], px[(r * 256 + i) * 4 + 1], px[(r * 256 + i) * 4 + 2]];
        assert_eq!(row(MapMode::Koeppen.index(), SEA_INDEX as usize), SEA_COLOUR);
        assert_eq!(row(MapMode::Pop.index(), SEA_INDEX as usize), SEA_COLOUR);
        assert!(Value::from_u8(neolith_core::Prop::Koeppen, SEA_INDEX).is_none());
        // board.wgsl tests the terrain byte against TERRAIN_WATER = 0.
        assert_eq!(Terrain::Water as u8, 0);
        assert!(Value::from_u8(neolith_core::Prop::Pop, SEA_INDEX).is_none());
        let at = |row: usize, i: usize| [px[(row * 256 + i) * 4], px[(row * 256 + i) * 4 + 1], px[(row * 256 + i) * 4 + 2]];
        assert_eq!(at(0, Terrain::Water as usize), terrain(Terrain::Water));
        assert_eq!(at(1, 0), hex(0x184a85));
        assert_eq!(at(2, 8), pop(PopDensity::P5_0));
        assert_eq!(at(0, 255), NO_DATA_COLOUR);
    }
}
