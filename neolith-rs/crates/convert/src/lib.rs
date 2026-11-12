//! GeoJSON ⇄ `world.bin` conversion and dataset statistics.

use neolith_core::{
    GridSpec, HexId, Koeppen, Lake, LakeShape, Landform, LonLat, PopDensity, Prop, River, RiverClass, RiverState, Settlement, Terrain, Timeline,
    Value, World, Year, NO_ELEVATION,
};
use serde::Deserialize;
use serde_json::{json, Map, Value as Json};
use std::collections::BTreeMap;
use std::fmt::Write as _;

/// The result of an import: the world plus everything worth telling the user.
pub struct Import {
    pub world: World,
    pub warnings: Vec<String>,
}

#[derive(Deserialize)]
struct FeatureCollection {
    features: Vec<Feature>,
}

#[derive(Deserialize)]
struct Feature {
    properties: HexProps,
}

#[derive(Deserialize)]
struct HexProps {
    id: u32,
    left: f64,
    top: f64,
    right: f64,
    bottom: f64,
    terrain: BTreeMap<String, String>,
    #[serde(default)]
    climate: BTreeMap<String, String>,
    koeppen: BTreeMap<String, f64>,
    population_density: BTreeMap<String, f64>,
    /// River class per year (0 none, 1 minor, 2 major); absent in older files.
    #[serde(default)]
    river: BTreeMap<String, u8>,
    /// Median elevation in metres (static, not year-keyed); absent in older files.
    #[serde(default)]
    elevation: Option<f64>,
    /// Landform class (0 flat, 1 hills, 2 mountains, 3 high mountains; static);
    /// absent in older files.
    #[serde(default)]
    landform: Option<u8>,
}

fn parse_year(key: &str, what: &str) -> Result<Year, String> {
    key.trim().parse::<i32>().map(Year).map_err(|_| format!("{what}: year key {key:?} is not an integer"))
}

/// Counts occurrences of problems so each is reported once with its count.
#[derive(Default)]
struct Tally(BTreeMap<String, usize>);

impl Tally {
    fn add(&mut self, what: String) {
        *self.0.entry(what).or_default() += 1;
    }

    fn drain_into(self, prefix: &str, out: &mut Vec<String>) {
        for (what, n) in self.0 {
            out.push(format!("{prefix}{what} ({n} hex-epochs)"));
        }
    }
}

/// Parses `combined_map.geojson` text into a world (without settlements).
pub fn import_map(geojson: &str) -> Result<Import, String> {
    let fc: FeatureCollection =
        serde_json::from_str(geojson).map_err(|e| format!("cannot parse the map GeoJSON: {e}"))?;
    let feats = &fc.features;
    if feats.is_empty() {
        return Err("the map GeoJSON has no features".into());
    }

    // 1. Derive the grid and check every hex lands exactly on it.
    let p0 = &feats[0].properties;
    let (w, h) = (p0.right - p0.left, p0.top - p0.bottom);
    if !(w > 0.0 && h > 0.0) {
        return Err(format!("hex {} has a degenerate bbox (w={w}, h={h})", p0.id));
    }
    let origin_lon = feats.iter().map(|f| f.properties.left).fold(f64::INFINITY, f64::min);
    let origin_lat = feats.iter().map(|f| f.properties.top).fold(f64::NEG_INFINITY, f64::max);
    let col_of = |p: &HexProps| (p.left - origin_lon) / (0.75 * w);
    let max_col = feats.iter().map(|f| col_of(&f.properties)).fold(0.0, f64::max).round() as usize;
    let cols = max_col + 1;
    if !feats.len().is_multiple_of(cols) {
        return Err(format!("{} hexes do not form a rectangle with {cols} columns", feats.len()));
    }
    let rows = feats.len() / cols;
    if cols > u16::MAX as usize || rows > u16::MAX as usize {
        return Err(format!("grid of {cols} × {rows} is too large"));
    }
    let grid = GridSpec { cols: cols as u16, rows: rows as u16, origin_lon, origin_lat, w, h };

    const TOL: f64 = 1e-6;
    let mut seen = vec![false; feats.len()];
    for f in feats {
        let p = &f.properties;
        let fc = col_of(p);
        let col = fc.round();
        let shift = if (col as i64).rem_euclid(2) == 1 { h / 2.0 } else { 0.0 };
        let fr = (origin_lat - shift - p.top) / h;
        let row = fr.round();
        if (fc - col).abs() > TOL || (fr - row).abs() > TOL {
            return Err(format!("hex {} is off the grid: fractional (col, row) = ({fc}, {fr})", p.id));
        }
        if ((p.right - p.left) - w).abs() > TOL || ((p.top - p.bottom) - h).abs() > TOL {
            return Err(format!("hex {} has a different size from hex {}", p.id, p0.id));
        }
        if col < 0.0 || row < 0.0 || col as usize >= cols || row as usize >= rows {
            return Err(format!("hex {} at (col {col}, row {row}) is outside the {cols} × {rows} grid", p.id));
        }
        let expect = grid.id_at(col as u16, row as u16);
        if p.id != expect.geojson_id() {
            return Err(format!(
                "hex id {} at (col {col}, row {row}) breaks the column-major id layout (expected id {})",
                p.id,
                expect.geojson_id()
            ));
        }
        if std::mem::replace(&mut seen[expect.index()], true) {
            return Err(format!("hex id {} appears twice", p.id));
        }
    }

    // 2–3. Parse property values into enums; cross-check climate against koeppen.
    let mut world = World::empty(grid);
    let mut warnings = Vec::new();
    let mut unknown_terrain = Tally::default();
    let mut bad = Tally::default();
    let mut climate_mismatch = Tally::default();
    let mut no_elevation = 0usize;
    let mut no_landform = 0usize;
    for f in feats {
        let p = &f.properties;
        let hex = HexId::from_geojson_id(p.id).unwrap();
        let what = format!("hex {}", p.id);
        match p.elevation {
            Some(z) if z.is_finite() => {
                world.elevation[hex.index()] = z.round().clamp(NO_ELEVATION as f64 + 1.0, i16::MAX as f64) as i16;
            }
            _ => no_elevation += 1,
        }
        match p.landform.map(Landform::from_u8) {
            Some(Some(l)) => world.landform[hex.index()] = Some(l),
            Some(None) => bad.add(format!("landform {}", p.landform.unwrap())),
            None => no_landform += 1,
        }
        for (k, name) in &p.terrain {
            let t = Terrain::from_name(name).unwrap_or_else(|| {
                unknown_terrain.add(format!("{name:?}"));
                Terrain::Unknown
            });
            world.set_key(hex, parse_year(k, &what)?, Value::Terrain(t));
        }
        for (k, v) in &p.koeppen {
            let year = parse_year(k, &what)?;
            let idx = v.round();
            match ((v - idx).abs() < 1e-9 && (0.0..256.0).contains(&idx)).then(|| Koeppen::new(idx as u8)).flatten() {
                Some(kp) => {
                    world.set_key(hex, year, Value::Koeppen(kp));
                    match p.climate.get(k) {
                        Some(c) if c == kp.code() => {}
                        Some(c) => climate_mismatch.add(format!("koeppen {} ({}) but climate {c:?}", kp.index(), kp.code())),
                        None => climate_mismatch.add(format!("koeppen {} but no climate value", kp.index())),
                    }
                }
                None => bad.add(format!("koeppen index {v}")),
            }
        }
        for (k, v) in &p.population_density {
            match PopDensity::from_value(*v) {
                Some(pd) => {
                    world.set_key(hex, parse_year(k, &what)?, Value::Pop(pd));
                }
                None => bad.add(format!("population density {v}")),
            }
        }
    }
    for f in feats {
        let p = &f.properties;
        let hex = HexId::from_geojson_id(p.id).unwrap();
        for (k, v) in &p.river {
            match RiverClass::from_u8(*v) {
                Some(_) => {
                    world.river[hex.index()].set_key(parse_year(k, &format!("hex {}", p.id))?, *v);
                }
                None => bad.add(format!("river class {v}")),
            }
        }
    }
    if !bad.0.is_empty() {
        let mut msgs = Vec::new();
        bad.drain_into("", &mut msgs);
        return Err(format!("values outside the known vocabulary: {}", msgs.join("; ")));
    }
    // None at all is an older file; only a partial layer is suspicious.
    if no_elevation > 0 && no_elevation < feats.len() {
        warnings.push(format!("{no_elevation} hexes have no elevation"));
    }
    if no_landform > 0 && no_landform < feats.len() {
        warnings.push(format!("{no_landform} hexes have no landform"));
    }
    unknown_terrain.drain_into("unknown terrain name mapped to Unknown: ", &mut warnings);
    climate_mismatch.drain_into("climate does not match koeppen: ", &mut warnings);
    Ok(Import { world, warnings })
}

/// Parses settlements. Accepts the current bare-array file, a proper
/// FeatureCollection, and the older shape with `population` at the top level.
pub fn import_settlements(text: &str) -> Result<(Vec<Settlement>, Vec<String>), String> {
    let root: Json = serde_json::from_str(text).map_err(|e| format!("cannot parse settlements: {e}"))?;
    let items = match &root {
        Json::Array(a) => a,
        Json::Object(o) => o
            .get("features")
            .and_then(Json::as_array)
            .ok_or("settlements: expected an array or a FeatureCollection")?,
        _ => return Err("settlements: expected an array or a FeatureCollection".into()),
    };
    let mut out: Vec<Settlement> = Vec::new();
    let mut warnings = Vec::new();
    for (i, item) in items.iter().enumerate() {
        let what = format!("settlement #{i}");
        let props = item.get("properties").ok_or(format!("{what}: no properties"))?;
        let id = item.get("id").or_else(|| props.get("id")).and_then(Json::as_u64).unwrap_or(i as u64 + 1) as u32;
        let name = props.get("name").and_then(Json::as_str).ok_or(format!("{what}: no name"))?.to_string();
        let founded = props
            .get("founding")
            .and_then(Json::as_i64)
            .ok_or(format!("{what} ({name}): no founding year"))?;
        let coords = item
            .pointer("/geometry/coordinates")
            .and_then(Json::as_array)
            .filter(|c| c.len() >= 2)
            .ok_or(format!("{what} ({name}): no point geometry"))?;
        let (lon, lat) = (coords[0].as_f64(), coords[1].as_f64());
        let (Some(lon), Some(lat)) = (lon, lat) else {
            return Err(format!("{what} ({name}): coordinates are not numbers"));
        };
        let mut population = Timeline::new();
        if let Some(pop) = props.get("population").or_else(|| item.get("population")).and_then(Json::as_object) {
            for (k, v) in pop {
                let n = v.as_f64().ok_or(format!("{what} ({name}): population {v} is not a number"))?;
                population.set_key(parse_year(k, &what)?, n.max(0.0).round() as u32);
            }
        }
        let s = Settlement { id, name, pos: LonLat::new(lon, lat), founded: Year(founded as i32), population };
        if let Some(dup) = out.iter().find(|o| o.name == s.name && o.pos == s.pos && o.founded == s.founded) {
            warnings.push(format!(
                "settlement id {} ({}) duplicates id {} at the same point; dropped",
                s.id, s.name, dup.id
            ));
            continue;
        }
        if out.iter().any(|o| o.id == s.id) {
            return Err(format!("settlement id {} is used twice for different settlements", s.id));
        }
        out.push(s);
    }
    Ok((out, warnings))
}

/// Parses `rivers.geojson` (LineString features from `python -m pipeline build`).
pub fn import_rivers(text: &str) -> Result<Vec<River>, String> {
    let root: Json = serde_json::from_str(text).map_err(|e| format!("cannot parse rivers: {e}"))?;
    let feats = root.get("features").and_then(Json::as_array).ok_or("rivers: expected a FeatureCollection")?;
    let mut out = Vec::new();
    for (i, f) in feats.iter().enumerate() {
        let p = f.get("properties").ok_or(format!("river #{i}: no properties"))?;
        let name = p.get("name").and_then(Json::as_str).ok_or(format!("river #{i}: no name"))?.to_string();
        let what = format!("river #{i} ({name})");
        let key = p.get("river").and_then(Json::as_str).unwrap_or(&name).to_string();
        let id = p.get("id").and_then(Json::as_u64).unwrap_or(i as u64 + 1) as u32;
        let size = p.get("size").and_then(Json::as_u64).ok_or(format!("{what}: no size"))?;
        if !(1..=3).contains(&size) {
            return Err(format!("{what}: size {size} is not 1-3"));
        }
        let coords = f
            .pointer("/geometry/coordinates")
            .and_then(Json::as_array)
            .ok_or(format!("{what}: no LineString geometry"))?;
        let points = coords
            .iter()
            .map(|c| match (c.get(0).and_then(Json::as_f64), c.get(1).and_then(Json::as_f64)) {
                (Some(lon), Some(lat)) => Ok(LonLat::new(lon, lat)),
                _ => Err(format!("{what}: coordinates are not numbers")),
            })
            .collect::<Result<Vec<_>, _>>()?;
        if points.len() < 2 {
            return Err(format!("{what}: fewer than 2 points"));
        }
        let mut state = Timeline::new();
        for (k, v) in p.get("state").and_then(Json::as_object).ok_or(format!("{what}: no state"))? {
            let s = v.as_str().and_then(RiverState::from_name).ok_or(format!("{what}: unknown state {v}"))?;
            state.set_key(parse_year(k, &what)?, s);
        }
        out.push(River { id, key, name, size: size as u8, points, state });
    }
    Ok(out)
}

/// Parses `lakes.geojson`: one MultiLineString feature per lake shoreline,
/// with `lake`, `name`, `level` and the years it holds (`from`, `to`; `to`
/// null for "until the end").
pub fn import_lakes(text: &str) -> Result<Vec<Lake>, String> {
    let root: Json = serde_json::from_str(text).map_err(|e| format!("cannot parse lakes: {e}"))?;
    let feats = root.get("features").and_then(Json::as_array).ok_or("lakes: expected a FeatureCollection")?;
    let mut lakes: Vec<Lake> = Vec::new();
    for (i, f) in feats.iter().enumerate() {
        let p = f.get("properties").ok_or(format!("lake shape #{i}: no properties"))?;
        let key = p.get("lake").and_then(Json::as_str).ok_or(format!("lake shape #{i}: no lake key"))?;
        let what = format!("lake shape #{i} ({key})");
        let name = p.get("name").and_then(Json::as_str).unwrap_or(key);
        let level = p.get("level").and_then(Json::as_f64).ok_or(format!("{what}: no level"))? as f32;
        let from = p.get("from").and_then(Json::as_i64).ok_or(format!("{what}: no from year"))? as i32;
        let to = p.get("to").and_then(Json::as_i64).map(|y| y as i32);
        let lines = f
            .pointer("/geometry/coordinates")
            .and_then(Json::as_array)
            .ok_or(format!("{what}: no MultiLineString geometry"))?;
        let mut rings = Vec::new();
        for line in lines {
            let pts = line
                .as_array()
                .ok_or(format!("{what}: bad ring"))?
                .iter()
                .map(|c| match (c.get(0).and_then(Json::as_f64), c.get(1).and_then(Json::as_f64)) {
                    (Some(lon), Some(lat)) => Ok(LonLat::new(lon, lat)),
                    _ => Err(format!("{what}: coordinates are not numbers")),
                })
                .collect::<Result<Vec<_>, _>>()?;
            if pts.len() >= 3 {
                rings.push(pts);
            }
        }
        let lake = match lakes.iter_mut().find(|l| l.key == key) {
            Some(l) => l,
            None => {
                lakes.push(Lake { key: key.into(), name: name.into(), shapes: Vec::new(), shape: Timeline::new() });
                lakes.last_mut().unwrap()
            }
        };
        let idx = lake.shapes.len() as u16;
        lake.shapes.push(LakeShape { level, rings });
        lake.shape.set_key(Year(from), idx);
        if let Some(to) = to {
            // A later shape's own key at the same year overrides this.
            if lake.shape.get_key(Year(to)).is_none() {
                lake.shape.set_key(Year(to), neolith_core::NO_SHAPE);
            }
        }
    }
    Ok(lakes)
}

/// The lakes as a `lakes.geojson` FeatureCollection.
pub fn export_lakes(world: &World) -> Json {
    let mut feats = Vec::new();
    for l in &world.lakes {
        let keys = l.shape.keys();
        for (k, (from, idx)) in keys.iter().enumerate() {
            let Some(shape) = l.shapes.get(*idx as usize) else { continue };
            let to = keys.get(k + 1).map(|(y, _)| y.0);
            let rings: Vec<Json> =
                shape.rings.iter().map(|r| json!(r.iter().map(|p| json!([p.lon, p.lat])).collect::<Vec<_>>())).collect();
            feats.push(json!({
                "type": "Feature",
                "geometry": { "type": "MultiLineString", "coordinates": rings },
                "properties": { "lake": l.key, "name": l.name, "level": shape.level, "from": from.0, "to": to },
            }));
        }
    }
    json!({ "type": "FeatureCollection", "features": feats })
}

/// The rivers as a `rivers.geojson` FeatureCollection.
pub fn export_rivers(world: &World) -> Json {
    let feats: Vec<Json> = world
        .rivers
        .iter()
        .map(|r| {
            let state: Map<String, Json> = r.state.keys().iter().map(|(y, s)| (y.0.to_string(), json!(s.name()))).collect();
            json!({
                "type": "Feature",
                "geometry": { "type": "LineString", "coordinates": r.points.iter().map(|p| json!([p.lon, p.lat])).collect::<Vec<_>>() },
                "properties": { "id": r.id, "river": r.key, "name": r.name, "size": r.size, "state": state },
            })
        })
        .collect();
    json!({ "type": "FeatureCollection", "features": feats })
}

fn year_map(keys: &[(Year, Value)], f: impl Fn(Value) -> Json) -> Json {
    Json::Object(keys.iter().map(|(y, v)| (y.0.to_string(), f(*v))).collect::<Map<_, _>>())
}

/// One hex as a GeoJSON feature in the `combined_map.geojson` format.
pub fn hex_feature(world: &World, hex: HexId) -> Json {
    let g = &world.grid;
    let poly = g.polygon(hex);
    let mut ring: Vec<Json> = poly.iter().map(|p| json!([p.lon, p.lat])).collect();
    ring.push(ring[0].clone());
    let c = g.centre(hex);
    let koeppen = world.keys(hex, Prop::Koeppen);
    let river: Map<String, Json> =
        world.river[hex.index()].keys().iter().map(|(y, c)| (y.0.to_string(), json!(c))).collect();
    let code = |v: Value| match v {
        Value::Koeppen(k) => k,
        _ => unreachable!(),
    };
    let mut feature = json!({
        "type": "Feature",
        "geometry": { "type": "Polygon", "coordinates": [ring] },
        "properties": {
            "id": hex.geojson_id(),
            "left": c.lon - g.w / 2.0,
            "top": c.lat + g.h / 2.0,
            "bottom": c.lat - g.h / 2.0,
            "right": c.lon + g.w / 2.0,
            "terrain": year_map(&world.keys(hex, Prop::Terrain), |v| match v {
                Value::Terrain(t) => json!(t.name()),
                _ => unreachable!(),
            }),
            "climate": year_map(&koeppen, |v| json!(code(v).code())),
            "koeppen": year_map(&koeppen, |v| json!(code(v).index() as f64)),
            "population_density": year_map(&world.keys(hex, Prop::Pop), |v| match v {
                Value::Pop(p) => json!(p.value()),
                _ => unreachable!(),
            }),
        }
    });
    if !river.is_empty() {
        feature["properties"]["river"] = Json::Object(river);
    }
    let z = world.elevation[hex.index()];
    if z != NO_ELEVATION {
        feature["properties"]["elevation"] = json!(z);
    }
    if let Some(l) = world.landform[hex.index()] {
        feature["properties"]["landform"] = json!(l as u8);
    }
    feature
}

/// Writes the world's hexes as a `combined_map.geojson` FeatureCollection.
pub fn export_map(world: &World, mut out: impl std::io::Write) -> std::io::Result<()> {
    out.write_all(b"{\"type\": \"FeatureCollection\", \"features\": [")?;
    for (i, hex) in world.grid.ids().enumerate() {
        if i > 0 {
            out.write_all(b", ")?;
        }
        serde_json::to_writer(&mut out, &hex_feature(world, hex))?;
    }
    out.write_all(b"]}\n")
}

/// The settlements in the bare-array shape of `settlements.geojson`.
pub fn export_settlements(world: &World) -> Json {
    Json::Array(
        world
            .settlements
            .iter()
            .map(|s| {
                let pop: Map<String, Json> =
                    s.population.keys().iter().map(|(y, n)| (y.0.to_string(), json!(n))).collect();
                json!({
                    "id": s.id,
                    "properties": { "name": s.name, "founding": s.founded.0, "type": "settlement", "population": pop },
                    "geometry": { "type": "Point", "coordinates": [s.pos.lon, s.pos.lat] },
                })
            })
            .collect(),
    )
}

/// An epoch-by-epoch summary of the dataset.
pub fn stats(world: &World) -> String {
    let g = &world.grid;
    let (west, south, east, north) = g.bounds();
    let mut s = String::new();
    let _ = writeln!(s, "grid: {} cols × {} rows = {} hexes, {:.5}° × {:.5}°", g.cols, g.rows, g.len(), g.w, g.h);
    let _ = writeln!(s, "extent: lon {west:.3} … {east:.3}, lat {south:.3} … {north:.3}");
    let years = world.keyframe_years();
    let _ = writeln!(s, "keyframes: {}", years.iter().map(|y| y.0.to_string()).collect::<Vec<_>>().join(", "));
    let placeholder = [Terrain::Water, Terrain::Plains, Terrain::Mountains, Terrain::Ice];
    let mut prev: Option<neolith_core::Snapshot> = None;
    for y in &years {
        let snap = world.snapshot(*y);
        let mut counts = [0usize; 256];
        snap.terrain.iter().for_each(|t| counts[*t as usize] += 1);
        let mut present: Vec<(Terrain, usize)> =
            Terrain::ALL.iter().map(|t| (*t, counts[*t as usize])).filter(|(_, n)| *n > 0).collect();
        present.sort_by_key(|(_, n)| std::cmp::Reverse(*n));
        let distinct = |v: &[u8]| {
            let mut seen = [false; 256];
            v.iter().for_each(|b| seen[*b as usize] = true);
            seen.iter().filter(|b| **b).count()
        };
        let mut flags = Vec::new();
        if present.iter().all(|(t, _)| placeholder.contains(t)) {
            flags.push("PLACEHOLDER terrain (only Water/Plains/Mountains/Ice)".to_string());
        }
        let mut changed = String::new();
        if let Some(p) = &prev {
            let diff = |a: &[u8], b: &[u8]| a.iter().zip(b).filter(|(x, y)| x != y).count();
            let (dt, dk, dp) = (diff(&p.terrain, &snap.terrain), diff(&p.koeppen, &snap.koeppen), diff(&p.pop, &snap.pop));
            changed = format!("  changed since previous: terrain {dt}, koeppen {dk}, population {dp}\n");
            if dt + dk + dp == 0 {
                flags.push("IDENTICAL to the previous keyframe".to_string());
            }
        }
        let _ = writeln!(s, "\n{} ({y})", y.0);
        let _ = writeln!(
            s,
            "  distinct values: terrain {}, koeppen {}, population {}",
            present.len(),
            distinct(&snap.koeppen),
            distinct(&snap.pop)
        );
        let _ = writeln!(
            s,
            "  terrain: {}",
            present.iter().map(|(t, n)| format!("{} {n}", t.name())).collect::<Vec<_>>().join(", ")
        );
        s.push_str(&changed);
        for f in flags {
            let _ = writeln!(s, "  ⚠ {f}");
        }
        prev = Some(snap);
    }
    let mut keys: Vec<&str> = world.rivers.iter().map(|r| r.key.as_str()).collect();
    keys.dedup();
    let z: Vec<i16> = world.elevation.iter().copied().filter(|z| *z != NO_ELEVATION).collect();
    match (z.iter().min(), z.iter().max()) {
        (Some(lo), Some(hi)) => {
            let _ = writeln!(s, "\nelevation: {} hexes, {lo}…{hi} m", z.len());
        }
        _ => {
            let _ = writeln!(s, "\nelevation: none");
        }
    }
    if world.landform.iter().any(Option::is_some) {
        let n = |l: Landform| world.landform.iter().filter(|x| **x == Some(l)).count();
        let _ = writeln!(
            s,
            "landform: {}",
            Landform::ALL.iter().map(|l| format!("{} {}", l.label(), n(*l))).collect::<Vec<_>>().join(", ")
        );
    }
    let _ = writeln!(s, "\nrivers: {} ({} stretches)", keys.len(), world.rivers.len());
    for l in &world.lakes {
        let levels: Vec<f32> = l.shapes.iter().map(|x| x.level).collect();
        let lo = levels.iter().cloned().fold(f32::INFINITY, f32::min);
        let hi = levels.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        let _ = writeln!(s, "lake {}: {} shorelines, {lo:.0}–{hi:.0} m", l.name, l.shapes.len());
    }
    let _ = writeln!(s, "\nsettlements: {}", world.settlements.len());
    for st in &world.settlements {
        let _ = writeln!(
            s,
            "  #{} {} — founded {}, ({:.3}, {:.3}), {} population keys",
            st.id,
            st.name,
            st.founded,
            st.pos.lon,
            st.pos.lat,
            st.population.len()
        );
    }
    s
}

#[cfg(test)]
mod lake_tests {
    use super::*;

    #[test]
    fn lakes_round_trip_through_geojson() {
        let text = r#"{"type":"FeatureCollection","features":[
          {"type":"Feature","geometry":{"type":"MultiLineString","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]},
           "properties":{"lake":"m","name":"M","level":329,"from":-9500,"to":-8300}},
          {"type":"Feature","geometry":{"type":"MultiLineString","coordinates":[[[0,0],[2,0],[2,2],[0,0]]]},
           "properties":{"lake":"m","name":"M","level":320,"from":-8300,"to":null}}]}"#;
        let lakes = import_lakes(text).unwrap();
        assert_eq!(lakes.len(), 1);
        let l = &lakes[0];
        assert!(l.shape_at(Year(-9600)).is_none());
        assert_eq!(l.shape_at(Year(-9000)).unwrap().level, 329.0);
        assert_eq!(l.shape_at(Year(-5000)).unwrap().level, 320.0);
        let mut w = World::empty(GridSpec { cols: 2, rows: 2, origin_lon: 0.0, origin_lat: 1.0, w: 0.5773502691896262, h: 0.5 });
        w.lakes = lakes;
        let again = import_lakes(&export_lakes(&w).to_string()).unwrap();
        assert_eq!(again, w.lakes);
    }
}
