//! `world.bin`: a small versioned header followed by zstd-compressed
//! postcard. Decoding is pure Rust (works in WASM); native builds compress
//! with libzstd, WASM builds with the pure-Rust encoder. Both write standard
//! zstd frames, so files are interchangeable.

use crate::grid::GridSpec;
use crate::timeline::Timeline;
use crate::values::{Koeppen, PopDensity, Terrain};
use crate::lake::Lake;
use crate::river::River;
use crate::world::{Settlement, World};
use serde::Deserialize;
use std::fmt;
use std::io::Read;

pub const MAGIC: [u8; 4] = *b"NEOL";
/// Version 2 added rivers, version 3 lakes, version 4 elevation, version 5
/// landform. Older files still load.
pub const VERSION: u16 = 5;
const HEADER_LEN: usize = 6;

#[derive(Debug)]
pub enum IoError {
    NotAWorldFile,
    UnsupportedVersion(u16),
    Corrupt(String),
    Invalid(String),
}

impl fmt::Display for IoError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IoError::NotAWorldFile => write!(f, "not a Neolith world file (bad magic)"),
            IoError::UnsupportedVersion(v) => {
                write!(f, "world file version {v} is not supported (this build reads version {VERSION})")
            }
            IoError::Corrupt(e) => write!(f, "world file is corrupt: {e}"),
            IoError::Invalid(e) => write!(f, "world file is invalid: {e}"),
        }
    }
}

impl std::error::Error for IoError {}

/// Serialises a world to `world.bin` bytes.
pub fn encode(world: &World) -> Vec<u8> {
    let raw = postcard::to_stdvec(world).expect("World serialisation cannot fail");
    let mut out = Vec::with_capacity(raw.len() / 8 + HEADER_LEN);
    out.extend_from_slice(&MAGIC);
    out.extend_from_slice(&VERSION.to_le_bytes());
    out.extend_from_slice(&compress(&raw));
    out
}

/// Parses `world.bin` bytes and validates the result.
pub fn decode(bytes: &[u8]) -> Result<World, IoError> {
    if bytes.len() < HEADER_LEN || bytes[..4] != MAGIC {
        return Err(IoError::NotAWorldFile);
    }
    let version = u16::from_le_bytes([bytes[4], bytes[5]]);
    if !(1..=VERSION).contains(&version) {
        return Err(IoError::UnsupportedVersion(version));
    }
    let raw = decompress(&bytes[HEADER_LEN..]).map_err(IoError::Corrupt)?;
    let corrupt = |e: postcard::Error| IoError::Corrupt(e.to_string());
    let world: World = if version == 1 {
        postcard::from_bytes::<WorldV1>(&raw).map_err(corrupt)?.into()
    } else if version == 2 {
        postcard::from_bytes::<WorldV2>(&raw).map_err(corrupt)?.into()
    } else if version == 3 {
        postcard::from_bytes::<WorldV3>(&raw).map_err(corrupt)?.into()
    } else if version == 4 {
        postcard::from_bytes::<WorldV4>(&raw).map_err(corrupt)?.into()
    } else {
        postcard::from_bytes(&raw).map_err(|e| IoError::Corrupt(e.to_string()))?
    };
    world.validate().map_err(IoError::Invalid)?;
    Ok(world)
}

/// The version 1 layout: no rivers.
#[derive(Deserialize)]
struct WorldV1 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
}

impl From<WorldV1> for World {
    fn from(v: WorldV1) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w
    }
}

/// The version 2 layout: rivers, no lakes.
#[derive(Deserialize)]
struct WorldV2 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
}

impl From<WorldV2> for World {
    fn from(v: WorldV2) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w
    }
}

/// The version 3 layout: lakes, no elevation.
#[derive(Deserialize)]
struct WorldV3 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
}

impl From<WorldV3> for World {
    fn from(v: WorldV3) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w
    }
}

/// The version 4 layout: elevation, no landform.
#[derive(Deserialize)]
struct WorldV4 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
}

impl From<WorldV4> for World {
    fn from(v: WorldV4) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn compress(raw: &[u8]) -> Vec<u8> {
    zstd::bulk::compress(raw, 19).expect("in-memory zstd compression cannot fail")
}

#[cfg(target_arch = "wasm32")]
fn compress(raw: &[u8]) -> Vec<u8> {
    compress_pure(raw)
}

/// The pure-Rust encoder used on WASM. Compiled everywhere so it is tested.
#[cfg_attr(not(any(target_arch = "wasm32", test)), allow(dead_code))]
fn compress_pure(raw: &[u8]) -> Vec<u8> {
    ruzstd::encoding::compress_to_vec(raw, ruzstd::encoding::CompressionLevel::Fastest)
}

fn decompress(data: &[u8]) -> Result<Vec<u8>, String> {
    let mut decoder = ruzstd::decoding::StreamingDecoder::new(data).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(|e| e.to_string())?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::world::test_world;

    #[test]
    fn round_trip() {
        let w = test_world(20, 15);
        let bytes = encode(&w);
        assert_eq!(&bytes[..4], b"NEOL");
        assert_eq!(decode(&bytes).unwrap(), w);
    }

    /// M5: an edit survives save → reload, inserted keyframes included.
    #[test]
    fn edits_survive_save_and_reload() {
        use crate::{fill, pencil, History, KeyMode, Terrain, Value, Year};
        let mut w = test_world(20, 15);
        let mut h = History::default();
        let cmd = pencil(&w, [crate::HexId(7)], Value::Terrain(Terrain::Ice), Year(-7500), KeyMode::InsertAtYear);
        h.apply(&mut w, cmd);
        let cmd = fill(&w, crate::HexId(40), Value::Terrain(Terrain::Savannah), Year(-9000), KeyMode::InEffect);
        h.apply(&mut w, cmd);
        let reloaded = decode(&encode(&w)).unwrap();
        assert_eq!(reloaded, w);
        assert_eq!(reloaded.value_at(crate::HexId(7), crate::Prop::Terrain, Year(-7500)), Some(Value::Terrain(Terrain::Ice)));
        assert!(reloaded.keyframe_years().contains(&Year(-7500)));
    }

    #[test]
    fn reads_version_1_files() {
        #[derive(serde::Serialize)]
        struct V1<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V1 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&1u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert!(old.rivers.is_empty());
        assert_eq!(old.terrain, w.terrain);
        assert_eq!(old.settlements, w.settlements);
    }

    #[test]
    fn reads_version_2_files() {
        #[derive(serde::Serialize)]
        struct V2<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V2 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&2u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.rivers, w.rivers);
        assert!(old.lakes.is_empty());
    }

    #[test]
    fn reads_version_3_files() {
        #[derive(serde::Serialize)]
        struct V3<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V3 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&3u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.lakes, w.lakes);
        assert!(old.elevation.iter().all(|z| *z == crate::NO_ELEVATION));
    }

    #[test]
    fn reads_version_4_files() {
        #[derive(serde::Serialize)]
        struct V4<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V4 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&4u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.elevation, w.elevation);
        assert!(old.landform.iter().all(|l| l.is_none()));
    }

    #[test]
    fn pure_rust_encoder_round_trips() {
        let w = test_world(20, 15);
        let raw = postcard::to_stdvec(&w).unwrap();
        assert_eq!(decompress(&compress_pure(&raw)).unwrap(), raw);
    }

    #[test]
    fn rejects_bad_input() {
        assert!(matches!(decode(b"nope"), Err(IoError::NotAWorldFile)));
        assert!(matches!(decode(b"GEOJSON{}"), Err(IoError::NotAWorldFile)));
        let mut bytes = encode(&test_world(4, 4));
        bytes[4] = 99;
        assert!(matches!(decode(&bytes), Err(IoError::UnsupportedVersion(99))));
        bytes[4] = VERSION as u8;
        bytes.truncate(bytes.len() / 2);
        assert!(matches!(decode(&bytes), Err(IoError::Corrupt(_))));
    }
}
