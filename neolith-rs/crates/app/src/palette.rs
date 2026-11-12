//! Colours, as `const` tables keyed by the typed enums. A colour can never be
//! assigned implicitly: every value of every property has an entry here, and
//! the tests check the tables are complete.

use neolith_core::elevation::{self, BAND_COUNT};
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
        Terrain::Water => hex(0x64b5f6),
        Terrain::Plains => hex(0xffe0b2),
        Terrain::Mountains => hex(0xbdbdbd),
        Terrain::Chaparral => hex(0xa1887f),
        Terrain::ExtremeDesert => hex(0xd2b48c),
        Terrain::SemiDesert => hex(0xf5deb3),
        Terrain::Free => hex(0xffffff),
        Terrain::Savannah => hex(0xc1b23d),
        Terrain::Woodlands => hex(0x8bc34a),
        Terrain::TropicalForest => hex(0x388e3c),
        Terrain::Grassland => hex(0xd7c55c),
        Terrain::TemperateForest => hex(0x689f38),
        Terrain::SteppeForest => hex(0xa2d0a5),
        Terrain::BorealForest => hex(0x2e7d32),
        Terrain::Tundra => hex(0x9fa89a),
        Terrain::Alpine => hex(0xbcb3c6),
        // Not in the old colour domain (they got recycled colours); explicit now.
        Terrain::Land => hex(0xcfc29b),
        Terrain::Unknown => hex(0x8d7f96),
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
    match mode.prop() {
        Some(prop) => Value::from_u8(prop, v).map_or(NO_DATA_COLOUR, colour),
        None => elevation(v),
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
            let sea = i == SEA_INDEX as usize && matches!(mode, MapMode::Koeppen | MapMode::Pop);
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

    #[test]
    fn terrain_colours_are_distinct() {
        let mut seen = std::collections::HashSet::new();
        for t in Terrain::ALL {
            assert!(seen.insert(terrain(*t)), "{t:?} reuses a colour");
        }
    }

    #[test]
    fn water_gets_lighter_towards_the_shore() {
        let l: Vec<f64> = (0..elevation::LAND_BAND).map(|b| luma(elevation(b))).collect();
        assert!(l.windows(2).all(|w| w[0] < w[1]), "{l:?}");
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
        assert_eq!(px.len(), 256 * 4 * 4);
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
