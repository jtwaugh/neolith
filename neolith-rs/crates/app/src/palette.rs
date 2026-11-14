//! Colours, as `const` tables keyed by the typed enums. A colour can never be
//! assigned implicitly: every value of every property has an entry here, and
//! the tests check the tables are complete.

use neolith_core::elevation::{self, BAND_COUNT};
use neolith_core::evidence;
use neolith_core::farming;
use neolith_core::forager;
use neolith_core::productivity;
use neolith_core::residuals;
use neolith_core::{Cover, Koeppen, MapMode, PopDensity, Terrain, Value, NO_DATA};

pub type Rgb = [u8; 3];

const fn hex(c: u32) -> Rgb {
    [(c >> 16) as u8, (c >> 8) as u8, c as u8]
}

/// Shown where no keyframe is in effect yet.
pub const NO_DATA_COLOUR: Rgb = hex(0x3a3a3a);

/// The mean colour of each ground cover (Ground map mode): what the
/// procedural texture averages to from far out, and its legend swatch.
/// Muted, earthy tones, as photographed ground is.
pub const fn cover(c: Cover) -> Rgb {
    match c {
        Cover::Grass => hex(0x6f8a3c),
        Cover::Moss => hex(0x5f6e48),
        Cover::Sand => hex(0xd4b27c),
        Cover::Rock => hex(0x8c8681),
        Cover::Snow => hex(0xe6edf3),
        Cover::Litter => hex(0x5c4a32),
    }
}

/// A terrain's mean ground colour in the Ground map mode: its cover
/// ([`cover`]) as that biome wears it, so the biome mosaic still reads from
/// far out (steppe straw, floodplain green). Tones follow the terrain map's
/// natural ground on the heightmap ranges (board.wgsl `natural_ground`).
pub const fn ground_terrain(t: Terrain) -> Rgb {
    match t {
        Terrain::Water => terrain(Terrain::Water),
        Terrain::Ice => cover(Cover::Snow),
        Terrain::Alpine | Terrain::Mountains => cover(Cover::Rock),
        Terrain::ExtremeDesert => hex(0xd2b483),
        Terrain::SemiDesert => hex(0xb8a479),
        Terrain::Savannah => hex(0xa89a64),
        Terrain::Chaparral => hex(0x948a64),
        Terrain::Grassland | Terrain::Plains => hex(0x9b9c64),
        Terrain::SteppeForest => hex(0x80915a),
        Terrain::Floodplain => hex(0x6c9351),
        Terrain::Land | Terrain::Free | Terrain::Unknown => hex(0x8f9060),
        Terrain::Tundra => hex(0x858a71),
        Terrain::BorealForest => hex(0x4a5a3a),
        Terrain::Woodlands => hex(0x6f7a48),
        Terrain::TemperateForest => hex(0x5f6a3c),
        Terrain::TropicalForest => hex(0x4a5f32),
    }
}

/// A terrain byte's colour in the Ground map mode.
pub fn ground(v: u8) -> Rgb {
    Terrain::from_u8(v).map_or(NO_DATA_COLOUR, ground_terrain)
}

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

/// The six ancestry components, in the table's order (whg, ehg, ana, irn,
/// lev, naf). Checked with the dataviz palette validator against every pair
/// (2026-11-13): the main contrast, western hunter-gatherer blue against
/// Anatolian-farmer orange, is the pair furthest apart under every kind of
/// colour blindness; the weakest pair (irn green, naf pink) never meets on the map.
pub const ANCESTRY: [Rgb; neolith_core::ancestry::COMPONENTS] =
    [hex(0x2a78d6), hex(0x4a3aa7), hex(0xd95926), hex(0x1baf7a), hex(0xeda100), hex(0xe87ba4)];

/// How much of the mixture colour a thin hex keeps (few genomes in reach);
/// the rest is [`EVIDENCE_GREY`].
pub const ANCESTRY_THIN: f32 = 0.5;

fn srgb_to_linear(v: u8) -> f32 {
    let c = v as f32 / 255.0;
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}

fn linear_to_srgb(c: f32) -> u8 {
    let c = c.clamp(0.0, 1.0);
    let v = if c <= 0.003_130_8 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 };
    (v * 255.0).round() as u8
}

/// OKLab (Ottosson 2020) of an sRGB colour.
pub fn oklab(c: Rgb) -> [f32; 3] {
    let (r, g, b) = (srgb_to_linear(c[0]), srgb_to_linear(c[1]), srgb_to_linear(c[2]));
    let l = (0.412_221_46 * r + 0.536_332_55 * g + 0.051_445_995 * b).cbrt();
    let m = (0.211_903_5 * r + 0.680_699_5 * g + 0.107_396_96 * b).cbrt();
    let s = (0.088_302_46 * r + 0.281_718_85 * g + 0.629_978_7 * b).cbrt();
    [
        0.210_454_26 * l + 0.793_617_8 * m - 0.004_072_047 * s,
        1.977_998_5 * l - 2.428_592_2 * m + 0.450_593_7 * s,
        0.025_904_037 * l + 0.782_771_77 * m - 0.808_675_77 * s,
    ]
}

pub fn from_oklab(c: [f32; 3]) -> Rgb {
    let l = (c[0] + 0.396_337_78 * c[1] + 0.215_803_76 * c[2]).powi(3);
    let m = (c[0] - 0.105_561_346 * c[1] - 0.063_854_17 * c[2]).powi(3);
    let s = (c[0] - 0.089_484_18 * c[1] - 1.291_485_5 * c[2]).powi(3);
    [
        linear_to_srgb(4.076_741_7 * l - 3.307_711_6 * m + 0.230_969_94 * s),
        linear_to_srgb(-1.268_438 * l + 2.609_757_4 * m - 0.341_319_38 * s),
        linear_to_srgb(-0.004_196_086_3 * l - 0.703_418_6 * m + 1.707_614_7 * s),
    ]
}

/// The colour of a mixture of the six components: their colours averaged in
/// OKLab by share, so a half-and-half hex reads as an honest in-between and
/// not as a third thing.
pub fn ancestry_mix(shares: &[f32]) -> Rgb {
    let total: f32 = shares.iter().take(ANCESTRY.len()).sum::<f32>().max(1e-6);
    let mut lab = [0.0f32; 3];
    for (share, colour) in shares.iter().zip(ANCESTRY) {
        let c = oklab(colour);
        for k in 0..3 {
            lab[k] += share / total * c[k];
        }
    }
    from_oklab(lab)
}

/// The colour of an Ancestry map code ([`neolith_core::ancestry::code`]);
/// [`NO_DATA_COLOUR`] for a hex with no genome in reach.
pub fn ancestry(code: u8) -> Rgb {
    match neolith_core::ancestry::decode(code) {
        Some((shares, thin)) => {
            let c = ancestry_mix(&shares);
            if thin { mix(EVIDENCE_GREY, c, ANCESTRY_THIN) } else { c }
        }
        None => NO_DATA_COLOUR,
    }
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
        (MapMode::Ground, None) => ground(v),
        (MapMode::Npp, None) => productivity(v),
        (MapMode::Biodiversity, None) => biodiversity(v),
        (MapMode::Expected, None) => expected(v),
        (MapMode::Evidence, None) => evidence(v),
        (MapMode::Missing, None) => missing(v),
        (MapMode::Ancestry, None) => ancestry(v),
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
            let sea = i == SEA_INDEX as usize && matches!(mode, MapMode::Koeppen | MapMode::Pop | MapMode::Npp | MapMode::Biodiversity | MapMode::Expected | MapMode::Evidence | MapMode::Missing | MapMode::Ancestry);
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

    /// sRGB to CIELAB (D65).
    fn lab_of(c: [f64; 3]) -> [f64; 3] {
        let [r, g, b] = c;
        let x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047;
        let y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b;
        let z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883;
        let f = |t: f64| if t > 0.008856 { t.cbrt() } else { 7.787 * t + 16.0 / 116.0 };
        [116.0 * f(y) - 16.0, 500.0 * (f(x) - f(y)), 200.0 * (f(y) - f(z))]
    }

    fn to_linear(c: Rgb) -> [f64; 3] {
        c.map(|v| {
            let v = v as f64 / 255.0;
            if v <= 0.04045 { v / 12.92 } else { ((v + 0.055) / 1.055).powf(2.4) }
        })
    }

    /// Colour difference (CIE76) between two colours as seen through `sim`,
    /// a 3x3 matrix on linear RGB (the identity for full colour vision).
    fn seen_delta_e(a: Rgb, b: Rgb, sim: &[[f64; 3]; 3]) -> f64 {
        let see = |c: Rgb| {
            let l = to_linear(c);
            lab_of(sim.map(|row| (row[0] * l[0] + row[1] * l[1] + row[2] * l[2]).clamp(0.0, 1.0)))
        };
        let (p, q) = (see(a), see(b));
        ((p[0] - q[0]).powi(2) + (p[1] - q[1]).powi(2) + (p[2] - q[2]).powi(2)).sqrt()
    }

    /// The map-mode ramps as seen with red-green colour blindness: every pair
    /// of neighbouring steps should still be told apart. Prints a line that
    /// `python -m pipeline state` reads (`cargo test -p neolith-app
    /// ramp_contrast_audit -- --nocapture`); only reports, the target is in
    /// data/state/targets.toml.
    #[test]
    fn ramp_contrast_audit() {
        // Machado, Oliveira & Fernandes 2009, severity 1.0.
        const PROTAN: [[f64; 3]; 3] =
            [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]];
        const DEUTAN: [[f64; 3]; 3] =
            [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]];
        // Below this two flat fills side by side are hard to tell apart.
        const MIN_STEP: f64 = 5.0;
        let ramps: Vec<(&str, Vec<Rgb>)> = vec![
            ("population", PopDensity::ALL.iter().map(|p| pop(*p)).collect()),
            ("elevation, water", ELEVATION[..7].to_vec()),
            ("elevation, land", ELEVATION[7..].to_vec()),
            ("productivity", PRODUCTIVITY.to_vec()),
            ("biodiversity", BIODIVERSITY.to_vec()),
            ("expected population", EXPECTED.to_vec()),
            ("evidence", PLASMA.to_vec()),
        ];
        let mut weak = Vec::new();
        let mut least = (f64::INFINITY, String::new());
        for (name, ramp) in &ramps {
            for (k, w) in ramp.windows(2).enumerate() {
                for (who, sim) in [("protan", &PROTAN), ("deutan", &DEUTAN)] {
                    let d = seen_delta_e(w[0], w[1], sim);
                    if d < least.0 {
                        least = (d, format!("{name} steps {k}-{} ({who})", k + 1));
                    }
                    if d < MIN_STEP {
                        weak.push(format!("{name} {k}-{} {who} {d:.1}", k + 1));
                    }
                }
            }
        }
        println!(
            "RAMP_AUDIT {}",
            serde_json::json!({"weak_steps": weak.len(), "weak": weak, "least": (least.0 * 10.0).round() / 10.0, "least_at": least.1, "min_step": MIN_STEP, "ramps": ramps.len()})
        );
        // Sanity: the simulation is the identity on greys.
        assert!(seen_delta_e([120, 120, 120], [120, 120, 120], &DEUTAN) < 1e-9);
        assert!((seen_delta_e([0, 0, 0], [255, 255, 255], &DEUTAN) - 100.0).abs() < 1.5);
    }

    #[test]
    fn ancestry_mixtures_are_in_between() {
        use neolith_core::ancestry::{code, COMPONENTS, MIXTURES, NO_CODE};
        // OKLab round-trips, and a pure component is its own colour.
        for c in ANCESTRY {
            assert_eq!(from_oklab(oklab(c)), c);
        }
        let pure = |k: usize| -> [f32; COMPONENTS] { std::array::from_fn(|i| (i == k) as u8 as f32) };
        assert_eq!(ancestry(code(&pure(2), false)), ANCESTRY[2]);
        // Half hunter-gatherer, half farmer sits between the two in lightness.
        let mut half = [0.0; COMPONENTS];
        (half[0], half[2]) = (0.5, 0.5);
        let (a, b, m) = (oklab(ANCESTRY[0])[0], oklab(ANCESTRY[2])[0], oklab(ancestry(code(&half, false)))[0]);
        assert!(m > a.min(b) - 1e-3 && m < a.max(b) + 1e-3);
        // Thin hexes are the same hue, greyer; every code differs from no data.
        let thin = ancestry(code(&pure(2), true));
        assert!(thin != ANCESTRY[2] && thin != NO_DATA_COLOUR);
        assert_eq!(ancestry(NO_CODE), NO_DATA_COLOUR);
        let row = MapMode::Ancestry.index();
        let tex = palette_texture();
        let at = |i: usize| -> Rgb { let o = (row * PALETTE_WIDTH + i) * 4; [tex[o], tex[o + 1], tex[o + 2]] };
        assert!((0..2 * MIXTURES as usize).all(|i| at(i) != NO_DATA_COLOUR));
        assert_eq!(at(SEA_INDEX as usize), SEA_COLOUR);
        // The main contrast: western hunter-gatherer against Anatolian farmer.
        assert!(delta_e(ANCESTRY[0], ANCESTRY[2]) > 40.0);
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
