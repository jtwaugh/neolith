//! Checks against the real dataset in the parent repo (M0 and M1 "done when").
//! Skipped, with a note, if the GeoJSON is not present.

use neolith_convert::{export_map, import_map, import_settlements};
use neolith_core::{io, HexId};
use serde_json::Value as Json;
use std::path::PathBuf;

fn asset(name: &str) -> Option<String> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../game/static/game/assets").join(name);
    match std::fs::read_to_string(&path) {
        Ok(s) => Some(s),
        Err(_) => {
            eprintln!("SKIPPED: {} not found", path.display());
            None
        }
    }
}

#[test]
fn geojson_bin_geojson_round_trip_reproduces_every_property() {
    let Some(text) = asset("combined_map.geojson") else { return };
    let import = import_map(&text).expect("import");
    assert!(import.warnings.is_empty(), "unexpected warnings: {:?}", import.warnings);

    // geojson → bin → world
    let bytes = io::encode(&import.world);
    let world = io::decode(&bytes).expect("decode");
    assert_eq!(world, import.world);
    assert!(bytes.len() < 400 * 1024, "world.bin is {} bytes", bytes.len());

    // → geojson, compared against the original value by value.
    let mut out = Vec::new();
    export_map(&world, &mut out).unwrap();
    let original: Json = serde_json::from_str(&text).unwrap();
    let exported: Json = serde_json::from_slice(&out).unwrap();
    let (a, b) = (original["features"].as_array().unwrap(), exported["features"].as_array().unwrap());
    assert_eq!(a.len(), b.len());
    for (fa, fb) in a.iter().zip(b) {
        let (pa, pb) = (&fa["properties"], &fb["properties"]);
        assert_eq!(pa["id"], pb["id"]);
        for prop in ["terrain", "climate", "koeppen", "population_density", "elevation", "npp", "farming"] {
            assert_eq!(pa[prop], pb[prop], "hex {} {prop}", pa["id"]);
        }
        for side in ["left", "top", "right", "bottom"] {
            let (x, y) = (pa[side].as_f64().unwrap(), pb[side].as_f64().unwrap());
            assert!((x - y).abs() < 1e-9, "hex {} {side}: {x} vs {y}", pa["id"]);
        }
        // M1: polygon(id) matches the GeoJSON vertices to 1e-9 (the exported
        // ring is polygon(id) plus the closing point).
        let (ra, rb) = (&fa["geometry"]["coordinates"][0], &fb["geometry"]["coordinates"][0]);
        assert_eq!(ra.as_array().unwrap().len(), 7);
        assert_eq!(rb.as_array().unwrap().len(), 7);
        for i in 0..7 {
            for k in 0..2 {
                let (x, y) = (ra[i][k].as_f64().unwrap(), rb[i][k].as_f64().unwrap());
                assert!((x - y).abs() < 1e-9, "hex {} vertex {i}: {x} vs {y}", pa["id"]);
            }
        }
    }

    // M1: hex_at(centre(id)) == id, and neighbours share exactly one edge
    // (two polygon vertices) in the source geometry.
    let g = &world.grid;
    let ring = |id: HexId| -> Vec<(f64, f64)> {
        a[id.index()]["geometry"]["coordinates"][0].as_array().unwrap()[..6]
            .iter()
            .map(|p| (p[0].as_f64().unwrap(), p[1].as_f64().unwrap()))
            .collect()
    };
    for id in g.ids() {
        assert_eq!(g.hex_at(g.centre(id)), Some(id));
        if id.0 % 7 == 0 {
            let mine = ring(id);
            for n in g.neighbours(id) {
                let shared = ring(n)
                    .iter()
                    .filter(|q| mine.iter().any(|p| (p.0 - q.0).abs() < 1e-9 && (p.1 - q.1).abs() < 1e-9))
                    .count();
                assert_eq!(shared, 2, "hex {} and {} are not edge-adjacent", id.0 + 1, n.0 + 1);
            }
        }
    }
}

#[test]
fn settlements_import_dedupes() {
    let Some(text) = asset("settlements.geojson") else { return };
    let (settlements, warnings) = import_settlements(&text).expect("import");
    assert_eq!(settlements.len(), 11);
    assert_eq!(warnings.len(), 1, "{warnings:?}");
    assert!(settlements.iter().any(|s| s.name == "Çatalhöyük" && s.founded.0 == -7400));
}
