//! `world.bin`: a small versioned header followed by zstd-compressed
//! postcard. Decoding is pure Rust (works in WASM); native builds compress
//! with libzstd, WASM builds with the pure-Rust encoder. Both write standard
//! zstd frames, so files are interchangeable.

use crate::grid::GridSpec;
use crate::timeline::Timeline;
use crate::values::{Koeppen, Landform, PopDensity, Terrain};
use crate::lake::Lake;
use crate::river::River;
use crate::world::{CultureInfo, Settlement, SiteInfo, World};
use serde::Deserialize;
use std::fmt;
use std::io::Read;

pub const MAGIC: [u8; 4] = *b"NEOL";
/// Version 2 added rivers, version 3 lakes, version 4 elevation, version 5
/// landform, version 6 site records, cultures and occupation phases, version 7
/// settlement importance and evidence and the survey layer, version 8
/// productivity, version 9 the farming front, version 10 the speculative
/// evidence layers, version 11 the missing-sites residuals, version 12 the sea beyond the
/// map's edge. Older files still load.
pub const VERSION: u16 = 12;
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
    } else if version == 5 {
        postcard::from_bytes::<WorldV5>(&raw).map_err(corrupt)?.into()
    } else if version == 6 {
        postcard::from_bytes::<WorldV6>(&raw).map_err(corrupt)?.into()
    } else if version == 7 {
        postcard::from_bytes::<WorldV7>(&raw).map_err(corrupt)?.into()
    } else if version == 8 {
        postcard::from_bytes::<WorldV8>(&raw).map_err(corrupt)?.into()
    } else if version == 9 {
        postcard::from_bytes::<WorldV9>(&raw).map_err(corrupt)?.into()
    } else if version == 10 {
        postcard::from_bytes::<WorldV10>(&raw).map_err(corrupt)?.into()
    } else if version == 11 {
        postcard::from_bytes::<WorldV11>(&raw).map_err(corrupt)?.into()
    } else {
        postcard::from_bytes(&raw).map_err(|e| IoError::Corrupt(e.to_string()))?
    };
    world.validate().map_err(IoError::Invalid)?;
    Ok(world)
}

/// A settlement before version 6: no occupation phases.
#[derive(Deserialize)]
#[cfg_attr(test, derive(serde::Serialize))]
struct SettlementV5 {
    id: u32,
    name: String,
    pos: crate::grid::LonLat,
    founded: crate::time::Year,
    population: Timeline<u32>,
}

impl From<SettlementV5> for Settlement {
    fn from(s: SettlementV5) -> Self {
        SettlementV6 { id: s.id, name: s.name, pos: s.pos, founded: s.founded, population: s.population, occupation: Vec::new() }
            .into()
    }
}

/// A settlement before version 7: no importance or evidence.
#[derive(Deserialize)]
#[cfg_attr(test, derive(serde::Serialize))]
struct SettlementV6 {
    id: u32,
    name: String,
    pos: crate::grid::LonLat,
    founded: crate::time::Year,
    population: Timeline<u32>,
    occupation: Vec<(crate::time::Year, crate::time::Year)>,
}

impl From<SettlementV6> for Settlement {
    fn from(s: SettlementV6) -> Self {
        Settlement {
            id: s.id,
            name: s.name,
            pos: s.pos,
            founded: s.founded,
            population: s.population,
            occupation: s.occupation,
            importance: Settlement::DEFAULT_IMPORTANCE,
            evidence: Settlement::DEFAULT_EVIDENCE,
        }
    }
}

#[cfg(test)]
impl From<&Settlement> for SettlementV6 {
    fn from(s: &Settlement) -> Self {
        SettlementV6 {
            id: s.id,
            name: s.name.clone(),
            pos: s.pos,
            founded: s.founded,
            population: s.population.clone(),
            occupation: s.occupation.clone(),
        }
    }
}

#[cfg(test)]
impl From<&Settlement> for SettlementV5 {
    fn from(s: &Settlement) -> Self {
        SettlementV5 { id: s.id, name: s.name.clone(), pos: s.pos, founded: s.founded, population: s.population.clone() }
    }
}

/// The version 1 layout: no rivers.
#[derive(Deserialize)]
struct WorldV1 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<SettlementV5>,
}

impl From<WorldV1> for World {
    fn from(v: WorldV1) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
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
    settlements: Vec<SettlementV5>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
}

impl From<WorldV2> for World {
    fn from(v: WorldV2) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
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
    settlements: Vec<SettlementV5>,
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
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
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
    settlements: Vec<SettlementV5>,
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
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w
    }
}

/// The version 5 layout: landform, no site records.
#[derive(Deserialize)]
struct WorldV5 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<SettlementV5>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
}

impl From<WorldV5> for World {
    fn from(v: WorldV5) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w
    }
}

/// The version 6 layout: site records, no importance, evidence or survey.
#[derive(Deserialize)]
struct WorldV6 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<SettlementV6>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
}

impl From<WorldV6> for World {
    fn from(v: WorldV6) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements.into_iter().map(Into::into).collect();
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w
    }
}

/// The version 7 layout: survey, no productivity.
#[derive(Deserialize)]
struct WorldV7 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
    survey: Vec<u8>,
}

impl From<WorldV7> for World {
    fn from(v: WorldV7) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w.survey = v.survey;
        w
    }
}

/// The version 8 layout: productivity, no farming front.
#[derive(Deserialize)]
struct WorldV8 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
    survey: Vec<u8>,
    npp: Vec<Timeline<u16>>,
}

impl From<WorldV8> for World {
    fn from(v: WorldV8) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w.survey = v.survey;
        w.npp = v.npp;
        w
    }
}

/// The version 9 layout: the farming front, no evidence layers.
#[derive(Deserialize)]
struct WorldV9 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
    survey: Vec<u8>,
    npp: Vec<Timeline<u16>>,
    farming: Vec<Option<crate::time::Year>>,
}

impl From<WorldV9> for World {
    fn from(v: WorldV9) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w.survey = v.survey;
        w.npp = v.npp;
        w.farming = v.farming;
        w
    }
}

/// The version 10 layout: evidence layers, no residuals.
#[derive(Deserialize)]
struct WorldV10 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
    survey: Vec<u8>,
    npp: Vec<Timeline<u16>>,
    farming: Vec<Option<crate::time::Year>>,
    evidence: Vec<crate::evidence::EvidenceLayer>,
}

impl From<WorldV10> for World {
    fn from(v: WorldV10) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w.survey = v.survey;
        w.npp = v.npp;
        w.farming = v.farming;
        w.evidence = v.evidence;
        w
    }
}

/// The version 11 layout: residuals, no sea beyond the edge.
#[derive(Deserialize)]
struct WorldV11 {
    grid: GridSpec,
    terrain: Vec<Timeline<Terrain>>,
    koeppen: Vec<Timeline<Koeppen>>,
    pop: Vec<Timeline<PopDensity>>,
    settlements: Vec<Settlement>,
    river: Vec<Timeline<u8>>,
    rivers: Vec<River>,
    lakes: Vec<Lake>,
    elevation: Vec<i16>,
    landform: Vec<Option<Landform>>,
    site_info: Vec<SiteInfo>,
    cultures: Vec<CultureInfo>,
    survey: Vec<u8>,
    npp: Vec<Timeline<u16>>,
    farming: Vec<Option<crate::time::Year>>,
    evidence: Vec<crate::evidence::EvidenceLayer>,
    residuals: Option<crate::residuals::Residuals>,
}

impl From<WorldV11> for World {
    fn from(v: WorldV11) -> Self {
        let mut w = World::empty(v.grid);
        w.terrain = v.terrain;
        w.koeppen = v.koeppen;
        w.pop = v.pop;
        w.settlements = v.settlements;
        w.river = v.river;
        w.rivers = v.rivers;
        w.lakes = v.lakes;
        w.elevation = v.elevation;
        w.landform = v.landform;
        w.site_info = v.site_info;
        w.cultures = v.cultures;
        w.survey = v.survey;
        w.npp = v.npp;
        w.farming = v.farming;
        w.evidence = v.evidence;
        w.residuals = v.residuals;
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
            settlements: &'a Vec<SettlementV5>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V1 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements.iter().map(SettlementV5::from).collect(),
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&1u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert!(old.rivers.is_empty());
        assert_eq!(old.terrain, w.terrain);
        assert_eq!(old.settlements[0].name, w.settlements[0].name);
        assert_eq!(old.settlements[0].importance, Settlement::DEFAULT_IMPORTANCE);
    }

    #[test]
    fn reads_version_2_files() {
        #[derive(serde::Serialize)]
        struct V2<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<SettlementV5>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V2 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements.iter().map(SettlementV5::from).collect(),
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
            settlements: &'a Vec<SettlementV5>,
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
            settlements: &w.settlements.iter().map(SettlementV5::from).collect(),
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
            settlements: &'a Vec<SettlementV5>,
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
            settlements: &w.settlements.iter().map(SettlementV5::from).collect(),
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
    fn reads_version_5_files() {
        #[derive(serde::Serialize)]
        struct V5<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<SettlementV5>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V5 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements.iter().map(SettlementV5::from).collect(),
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&5u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.landform, w.landform);
        assert_eq!(old.settlements[0].population, w.settlements[0].population);
        assert!(old.site_info.is_empty() && old.cultures.is_empty());
        assert!(old.site_info(0).is_none());
    }

    #[test]
    fn reads_version_6_files() {
        #[derive(serde::Serialize)]
        struct V6<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<SettlementV6>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
            site_info: &'a Vec<SiteInfo>,
            cultures: &'a Vec<CultureInfo>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V6 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements.iter().map(SettlementV6::from).collect(),
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&6u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.site_info, w.site_info);
        assert_eq!(old.settlements[0].occupation, w.settlements[0].occupation);
        assert_eq!(old.settlements[0].importance, Settlement::DEFAULT_IMPORTANCE);
        assert_eq!(old.settlements[0].evidence, Settlement::DEFAULT_EVIDENCE);
        assert!(old.survey.is_empty() && old.survey_at(crate::HexId(0)).is_none());
    }

    #[test]
    fn reads_version_7_files() {
        #[derive(serde::Serialize)]
        struct V7<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
            site_info: &'a Vec<SiteInfo>,
            cultures: &'a Vec<CultureInfo>,
            survey: &'a Vec<u8>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V7 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
            survey: &w.survey,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&7u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.survey, w.survey);
        assert_eq!(old.settlements, w.settlements);
        assert!(old.npp.is_empty() && old.npp_at(crate::HexId(0), crate::Year(-9000)).is_none());
    }

    #[test]
    fn reads_version_8_files() {
        #[derive(serde::Serialize)]
        struct V8<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
            site_info: &'a Vec<SiteInfo>,
            cultures: &'a Vec<CultureInfo>,
            survey: &'a Vec<u8>,
            npp: &'a Vec<Timeline<u16>>,
        }
        let w = test_world(6, 5);
        let raw = postcard::to_stdvec(&V8 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
            survey: &w.survey,
            npp: &w.npp,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&8u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.npp, w.npp);
        assert!(old.farming.is_empty());
        assert!(!old.expected_at(crate::HexId(0), crate::Year(-3000)).is_some_and(|e| e.farmed));
    }

    #[test]
    fn reads_version_9_files() {
        #[derive(serde::Serialize)]
        struct V9<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
            site_info: &'a Vec<SiteInfo>,
            cultures: &'a Vec<CultureInfo>,
            survey: &'a Vec<u8>,
            npp: &'a Vec<Timeline<u16>>,
            farming: &'a Vec<Option<crate::Year>>,
        }
        let w = test_world(6, 5);
        assert!(!w.evidence.is_empty());
        let raw = postcard::to_stdvec(&V9 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
            survey: &w.survey,
            npp: &w.npp,
            farming: &w.farming,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&9u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.farming, w.farming);
        assert_eq!(old.npp, w.npp);
        assert!(old.evidence.is_empty());
        assert!(old.residuals.is_none());
        assert_eq!(World { evidence: w.evidence.clone(), residuals: w.residuals.clone(), ..old }, w);
    }

    #[test]
    fn reads_version_10_files() {
        #[derive(serde::Serialize)]
        struct V10<'a> {
            grid: &'a GridSpec,
            terrain: &'a Vec<Timeline<Terrain>>,
            koeppen: &'a Vec<Timeline<Koeppen>>,
            pop: &'a Vec<Timeline<PopDensity>>,
            settlements: &'a Vec<Settlement>,
            river: &'a Vec<Timeline<u8>>,
            rivers: &'a Vec<River>,
            lakes: &'a Vec<Lake>,
            elevation: &'a Vec<i16>,
            landform: &'a Vec<Option<Landform>>,
            site_info: &'a Vec<SiteInfo>,
            cultures: &'a Vec<CultureInfo>,
            survey: &'a Vec<u8>,
            npp: &'a Vec<Timeline<u16>>,
            farming: &'a Vec<Option<crate::Year>>,
            evidence: &'a Vec<crate::EvidenceLayer>,
        }
        let w = test_world(6, 5);
        assert!(w.residuals.is_some());
        let raw = postcard::to_stdvec(&V10 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
            survey: &w.survey,
            npp: &w.npp,
            farming: &w.farming,
            evidence: &w.evidence,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&10u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.evidence, w.evidence);
        assert!(old.residuals.is_none());
        assert_eq!(World { residuals: w.residuals.clone(), ..old }, w);
    }

    #[test]
    fn reads_version_11_files() {
        #[derive(serde::Serialize)]
        struct V11<'a> {
        grid: &'a GridSpec,
        terrain: &'a Vec<Timeline<Terrain>>,
        koeppen: &'a Vec<Timeline<Koeppen>>,
        pop: &'a Vec<Timeline<PopDensity>>,
        settlements: &'a Vec<Settlement>,
        river: &'a Vec<Timeline<u8>>,
        rivers: &'a Vec<River>,
        lakes: &'a Vec<Lake>,
        elevation: &'a Vec<i16>,
        landform: &'a Vec<Option<Landform>>,
        site_info: &'a Vec<SiteInfo>,
        cultures: &'a Vec<CultureInfo>,
        survey: &'a Vec<u8>,
        npp: &'a Vec<Timeline<u16>>,
        farming: &'a Vec<Option<crate::Year>>,
        evidence: &'a Vec<crate::EvidenceLayer>,
        residuals: &'a Option<crate::Residuals>,
        }
        let mut w = test_world(6, 5);
        w.edge_sea = vec![Timeline::from_keys([(crate::Year(-10000), 40)]); w.grid.len()];
        let raw = postcard::to_stdvec(&V11 {
            grid: &w.grid,
            terrain: &w.terrain,
            koeppen: &w.koeppen,
            pop: &w.pop,
            settlements: &w.settlements,
            river: &w.river,
            rivers: &w.rivers,
            lakes: &w.lakes,
            elevation: &w.elevation,
            landform: &w.landform,
            site_info: &w.site_info,
            cultures: &w.cultures,
            survey: &w.survey,
            npp: &w.npp,
            farming: &w.farming,
            evidence: &w.evidence,
            residuals: &w.residuals,
        })
        .unwrap();
        let mut bytes = MAGIC.to_vec();
        bytes.extend_from_slice(&11u16.to_le_bytes());
        bytes.extend_from_slice(&compress_pure(&raw));
        let old = decode(&bytes).unwrap();
        assert_eq!(old.residuals, w.residuals);
        assert!(old.edge_sea.is_empty());
        assert_eq!(World { edge_sea: w.edge_sea.clone(), ..old }, w);
    }

    #[test]
    fn version_12_round_trips_the_edge_sea_and_rejects_a_bad_one() {
        let mut w = test_world(7, 5);
        w.edge_sea = vec![Timeline::from_keys([(crate::Year(-10000), 40), (crate::Year(-6000), crate::NO_EDGE_SEA)]); w.grid.len()];
        assert_eq!(decode(&encode(&w)).unwrap(), w);
        w.edge_sea.pop();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn version_11_round_trips_residuals_and_rejects_bad_ones() {
        let w = test_world(7, 5);
        assert_eq!(decode(&encode(&w)).unwrap().residuals, w.residuals);
        let mut bad = w.clone();
        bad.residuals.as_mut().unwrap().missing.pop();
        assert!(matches!(decode(&encode(&bad)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn version_10_round_trips_evidence() {
        let mut w = test_world(7, 5);
        w.evidence.push(crate::evidence::test_layer("second", w.grid.len()));
        w.evidence[1].codes[3] = crate::evidence::NO_VALUE;
        let bytes = encode(&w);
        assert_eq!(u16::from_le_bytes([bytes[4], bytes[5]]), VERSION);
        let back = decode(&bytes).unwrap();
        assert_eq!(back.evidence, w.evidence);
        assert_eq!(back.evidence_layer("second").unwrap().codes[3], crate::evidence::NO_VALUE);
        assert_eq!(back, w);
    }

    #[test]
    fn evidence_must_match_grid() {
        let mut w = test_world(6, 5);
        w.evidence[0].codes.pop();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
        let mut w = test_world(6, 5);
        w.evidence[0].slices.reverse();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
        let mut w = test_world(6, 5);
        let dup = w.evidence[0].clone();
        w.evidence.push(dup);
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn farming_must_match_grid() {
        let mut w = test_world(6, 5);
        w.farming.pop();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn productivity_must_match_grid() {
        let mut w = test_world(6, 5);
        w.npp.pop();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn survey_must_match_grid() {
        let mut w = test_world(6, 5);
        w.survey.pop();
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
        let mut w = test_world(6, 5);
        w.survey[0] = 3;
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
    }

    #[test]
    fn site_records_must_match_settlements() {
        let mut w = test_world(6, 5);
        w.site_info.push(crate::SiteInfo::default());
        assert!(matches!(decode(&encode(&w)), Err(IoError::Invalid(_))));
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
