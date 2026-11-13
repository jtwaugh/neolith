//! GeoJSON ⇄ `world.bin` conversion and dataset statistics.

use neolith_core::{
    C14Date, CultureInfo, EvidenceLayer, GridSpec, HexId, Koeppen, Lake, LakeShape, Landform, LonLat, Massif, MassifKind, PopDensity, Prop, River, RiverClass, RiverState,
    Settlement, SiteInfo, Summit, Terrain, Timeline, Value, World, Year, NO_ELEVATION,
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
    /// Survey intensity 0-2 (static); absent in older files.
    #[serde(default)]
    survey: Option<f64>,
    /// Net primary productivity per year (g dry matter/m²/yr); absent in older files.
    #[serde(default)]
    npp: BTreeMap<String, f64>,
    /// Km to the nearest open sea beyond the map's edge per year; 65535 for
    /// none within reach. Absent in older files.
    #[serde(default)]
    edge_sea_km: BTreeMap<String, f64>,
    /// Year farming reaches the hex (static); absent where it never does,
    /// and in older files.
    #[serde(default)]
    farming: Option<f64>,
    /// Sketch of the hex's high ground (static; see `neolith_core::massif`):
    /// absent on flat hexes and in older files.
    #[serde(default)]
    massif: Option<MassifProp>,
}

/// The pipeline's `massif` property (`elevation.massif`).
#[derive(Deserialize)]
struct MassifProp {
    kind: String,
    /// Degrees anticlockwise from east.
    strike: f64,
    coherence: f64,
    /// Metres, present-day datum.
    floor: f64,
    /// [x, y, metres above the floor], highest first; hex-local position.
    summits: Vec<[f64; 3]>,
}

impl MassifProp {
    fn to_massif(&self) -> Result<Massif, String> {
        let kind = MassifKind::from_name(&self.kind).ok_or_else(|| format!("massif kind {:?}", self.kind))?;
        let summits = self.summits.iter().map(|[x, y, h]| Summit::new(*x, *y, *h)).collect();
        let m = Massif::new(kind, self.strike, self.coherence, self.floor, summits);
        m.validate()?;
        Ok(m)
    }
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
    let mut survey = vec![None; feats.len()];
    let mut npp = vec![Timeline::new(); feats.len()];
    let mut with_npp = 0usize;
    let mut edge_sea = vec![Timeline::new(); feats.len()];
    let mut with_edge_sea = 0usize;
    let mut farming = vec![None; feats.len()];
    let mut massif = vec![None; feats.len()];
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
        if let Some(m) = &p.massif {
            match m.to_massif() {
                Ok(m) => massif[hex.index()] = Some(m),
                Err(e) => bad.add(e),
            }
        }
        match p.survey {
            Some(v) if (0.0..=2.0).contains(&v) && v.fract() == 0.0 => survey[hex.index()] = Some(v as u8),
            Some(v) => bad.add(format!("survey level {v}")),
            None => {}
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
        match p.farming {
            Some(y) if y.is_finite() && y.fract() == 0.0 && y.abs() < 1e6 => farming[hex.index()] = Some(Year(y as i32)),
            Some(y) => bad.add(format!("farming year {y}")),
            None => {}
        }
        with_npp += !p.npp.is_empty() as usize;
        for (k, v) in &p.npp {
            if v.is_finite() && (0.0..=u16::MAX as f64).contains(v) {
                npp[hex.index()].set_key(parse_year(k, &what)?, v.round() as u16);
            } else {
                bad.add(format!("productivity {v}"));
            }
        }
        with_edge_sea += !p.edge_sea_km.is_empty() as usize;
        for (k, v) in &p.edge_sea_km {
            if v.is_finite() && (0.0..=u16::MAX as f64).contains(v) {
                edge_sea[hex.index()].set_key(parse_year(k, &what)?, v.round() as u16);
            } else {
                bad.add(format!("edge-sea distance {v}"));
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
    if with_npp > 0 {
        if with_npp < feats.len() {
            warnings.push(format!("{} hexes have no productivity", feats.len() - with_npp));
        }
        world.npp = npp;
    }
    if with_edge_sea > 0 {
        if with_edge_sea < feats.len() {
            warnings.push(format!("{} hexes have no edge-sea distance", feats.len() - with_edge_sea));
        }
        world.edge_sea = edge_sea;
    }
    if farming.iter().any(Option::is_some) {
        world.farming = farming;
    }
    if massif.iter().any(Option::is_some) {
        world.massif = massif;
    }
    let surveyed = survey.iter().filter(|v| v.is_some()).count();
    if surveyed > 0 {
        if surveyed < feats.len() {
            warnings.push(format!("{} hexes have no survey level; taken as 0", feats.len() - surveyed));
        }
        world.survey = survey.into_iter().map(|v| v.unwrap_or(0)).collect();
    }
    unknown_terrain.drain_into("unknown terrain name mapped to Unknown: ", &mut warnings);
    climate_mismatch.drain_into("climate does not match koeppen: ", &mut warnings);
    Ok(Import { world, warnings })
}

/// Parses settlements. Accepts the current bare-array file, a proper
/// FeatureCollection, and the older shape with `population` at the top level.
pub fn import_settlements(text: &str) -> Result<(Vec<Settlement>, Vec<String>), String> {
    import_settlement_records(text).map(|(s, _, w)| (s, w))
}

/// Most references kept per site; the full lists stay in the GeoJSON.
pub const MAX_REFERENCES: usize = 12;

/// Like [`import_settlements`], plus each settlement's [`SiteInfo`] (in the
/// same order, without radiocarbon dates; see [`attach_dates`]).
pub fn import_settlement_records(text: &str) -> Result<(Vec<Settlement>, Vec<SiteInfo>, Vec<String>), String> {
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
    let mut info: Vec<SiteInfo> = Vec::new();
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
        let mut occupation = Vec::new();
        for ph in props.get("occupation").and_then(Json::as_array).into_iter().flatten() {
            match ph.as_array().map(|p| p.iter().filter_map(Json::as_i64).collect::<Vec<_>>()).as_deref() {
                Some(&[a, b]) if a < b => occupation.push((Year(a as i32), Year(b as i32))),
                _ => return Err(format!("{what} ({name}): occupation phase {ph} is not [start, end]")),
            }
        }
        occupation.sort();
        let level = |k: &str, max: u64, default: u8| match props.get(k) {
            None | Some(Json::Null) => Ok(default),
            Some(v) => v.as_u64().filter(|n| *n <= max).map(|n| n as u8).ok_or(format!("{what} ({name}): {k} {v} is not 0-{max}")),
        };
        let importance = level("importance", 3, Settlement::DEFAULT_IMPORTANCE)?;
        let evidence = level("evidence", 2, Settlement::DEFAULT_EVIDENCE)?;
        let s = Settlement {
            id,
            name,
            pos: LonLat::new(lon, lat),
            founded: Year(founded as i32),
            population,
            occupation,
            importance,
            evidence,
        };
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
        info.push(site_info(props, &what)?);
    }
    Ok((out, info, warnings))
}

/// Appends the inferred settlements in `text` (the pipeline's
/// `inferred.geojson`) to the world's settlements, each tagged
/// [`SiteInfo::INFERRED`] in its sources whatever the file says, so the app
/// never takes one for a recorded site. Ids must not clash with recorded
/// ones. Returns how many were added.
pub fn append_inferred(world: &mut World, text: &str) -> Result<usize, String> {
    let (settlements, info, warnings) = import_settlement_records(text)?;
    if let Some(w) = warnings.first() {
        return Err(format!("inferred settlements: {w}"));
    }
    if world.site_info.len() != world.settlements.len() {
        world.site_info.resize(world.settlements.len(), SiteInfo::default());
    }
    for (s, mut i) in settlements.into_iter().zip(info) {
        if world.settlements.iter().any(|o| o.id == s.id) {
            return Err(format!("inferred settlement {} ({}): id already used by a recorded settlement", s.id, s.name));
        }
        if !i.is_inferred() {
            i.sources.push(SiteInfo::INFERRED.to_string());
        }
        world.settlements.push(s);
        world.site_info.push(i);
    }
    Ok(world.settlements.iter().enumerate().filter(|(k, _)| world.is_inferred(*k)).count())
}

fn strings(v: Option<&Json>) -> Vec<String> {
    v.and_then(Json::as_array)
        .map(|a| a.iter().filter_map(Json::as_str).map(str::to_string).collect())
        .unwrap_or_default()
}

/// `{"<year>": "<id>", ...}` -> sorted (year, id) pairs.
fn year_ids(v: Option<&Json>, what: &str) -> Result<Vec<(Year, String)>, String> {
    let mut out = Vec::new();
    for (k, id) in v.and_then(Json::as_object).into_iter().flatten() {
        if let Some(id) = id.as_str() {
            out.push((parse_year(k, what)?, id.to_string()));
        }
    }
    out.sort();
    Ok(out)
}

/// The record fields of one `settlements.geojson` feature.
fn site_info(props: &Json, what: &str) -> Result<SiteInfo, String> {
    let text = |k: &str| props.get(k).and_then(Json::as_str).filter(|s| !s.is_empty()).map(str::to_string);
    let mut references = Vec::new();
    for r in strings(props.get("references")) {
        if references.len() < MAX_REFERENCES && !references.contains(&r) {
            references.push(r);
        }
    }
    Ok(SiteInfo {
        kind: text("type").unwrap_or_default(),
        abandoned: props.get("abandoned").and_then(Json::as_i64).map(|y| Year(y as i32)),
        aliases: strings(props.get("aliases")),
        periods: strings(props.get("periods")),
        culture: year_ids(props.get("culture"), what)?,
        stage: year_ids(props.get("stage"), what)?,
        culture_inferred: year_ids(props.get("culture_inferred"), what)?,
        stage_inferred: year_ids(props.get("stage_inferred"), what)?,
        features: strings(props.get("features")),
        wikipedia: text("wikipedia"),
        wikidata: text("wikidata"),
        wikidata_culture: strings(props.get("wikidata_culture")),
        sources: strings(props.get("sources")),
        references,
        dates: Vec::new(),
    })
}

/// Splits CSV text (RFC 4180: quoted fields, doubled quotes) into rows.
fn csv_rows(text: &str) -> Vec<Vec<String>> {
    let (mut rows, mut row, mut field) = (Vec::new(), Vec::new(), String::new());
    let mut quoted = false;
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        match (quoted, c) {
            (true, '"') if chars.peek() == Some(&'"') => {
                chars.next();
                field.push('"');
            }
            (true, '"') => quoted = false,
            (true, c) => field.push(c),
            (false, '"') => quoted = true,
            (false, ',') => row.push(std::mem::take(&mut field)),
            (false, '\r') => {}
            (false, '\n') => {
                row.push(std::mem::take(&mut field));
                rows.push(std::mem::take(&mut row));
            }
            (false, c) => field.push(c),
        }
    }
    if !field.is_empty() || !row.is_empty() {
        row.push(field);
        rows.push(row);
    }
    rows
}

/// Adds the radiocarbon dates in `dates.csv` text (from `make settlements`)
/// to the records, matched by `site_id`. Returns how many were attached and
/// how many named a settlement that isn't there.
pub fn attach_dates(settlements: &[Settlement], info: &mut [SiteInfo], text: &str) -> Result<(usize, usize), String> {
    let mut rows = csv_rows(text).into_iter();
    let header = rows.next().ok_or("dates: empty file")?;
    let col = |name: &str| header.iter().position(|h| h == name).ok_or(format!("dates: no {name} column"));
    let (site, lab, bp, err, cal, dataset) =
        (col("site_id")?, col("lab_number")?, col("c14_age")?, col("c14_error")?, col("cal_year")?, col("dataset")?);
    let index: std::collections::HashMap<u32, usize> = settlements.iter().enumerate().map(|(i, s)| (s.id, i)).collect();
    let (mut attached, mut orphans) = (0, 0);
    for (n, r) in rows.enumerate() {
        if r.len() < header.len() {
            continue;
        }
        let num = |c: usize| -> Result<i64, String> {
            r[c].trim().parse::<f64>().map(|v| v.round() as i64).map_err(|_| format!("dates row {}: {:?} is not a number", n + 2, r[c]))
        };
        let Some(&i) = r[site].parse::<u32>().ok().and_then(|id| index.get(&id)) else {
            orphans += 1;
            continue;
        };
        info[i].dates.push(C14Date {
            lab: r[lab].clone(),
            bp: num(bp)?.max(0) as u32,
            err: num(err)?.max(0) as u32,
            cal: Year(num(cal)? as i32),
            dataset: r[dataset].clone(),
        });
        attached += 1;
    }
    for s in info.iter_mut() {
        s.dates.sort_by(|a, b| (a.cal, &a.lab).cmp(&(b.cal, &b.lab)));
    }
    Ok((attached, orphans))
}

/// Cell size (degrees) of the heightmap built by [`import_heightmap`]: a few
/// samples per hex, enough to light ridges and valleys.
pub const HEIGHTMAP_CELL: f64 = 0.1;

/// An ESRI ASCII grid of elevations (the pipeline's ETOPO1 subset,
/// `build/etopo.asc`) averaged into [`HEIGHTMAP_CELL`] cells over `grid`'s
/// bounds. Source cells with no data, and target cells no source cell
/// reaches, count as sea level.
pub fn import_heightmap(text: &str, grid: &GridSpec) -> Result<neolith_core::Heightmap, String> {
    let mut lines = text.lines();
    let mut header = BTreeMap::new();
    for _ in 0..6 {
        let line = lines.next().ok_or("heightmap: the header is cut short")?;
        let mut kv = line.split_whitespace();
        let (k, v) = (kv.next().unwrap_or("").to_lowercase(), kv.next().unwrap_or(""));
        header.insert(k, v.parse::<f64>().map_err(|_| format!("heightmap: bad header line {line:?}"))?);
    }
    let get = |k: &str| header.get(k).copied().ok_or(format!("heightmap: no {k} in the header"));
    let (ncols, nrows, cell) = (get("ncols")? as usize, get("nrows")? as usize, get("cellsize")?);
    let nodata = header.get("nodata_value").copied();
    // Lower-left corner of the lower-left cell (centre or corner given).
    let x0 = match header.get("xllcorner") { Some(v) => *v, None => get("xllcenter")? - cell / 2.0 };
    let y0 = match header.get("yllcorner") { Some(v) => *v, None => get("yllcenter")? - cell / 2.0 };
    let (west, south, east, north) = grid.bounds();
    let snap = |v: f64, up: bool| if up { (v / HEIGHTMAP_CELL).ceil() } else { (v / HEIGHTMAP_CELL).floor() } * HEIGHTMAP_CELL;
    let (hw, hn) = (snap(west, false), snap(north, true));
    let cols = ((snap(east, true) - hw) / HEIGHTMAP_CELL).round() as usize;
    let rows = ((hn - snap(south, false)) / HEIGHTMAP_CELL).round() as usize;
    let mut sum = vec![0f64; cols * rows];
    let mut count = vec![0u32; cols * rows];
    let mut values = lines.flat_map(str::split_whitespace);
    // Source rows run from the north.
    for r in 0..nrows {
        let lat = y0 + (nrows - 1 - r) as f64 * cell + cell / 2.0;
        let tr = ((hn - lat) / HEIGHTMAP_CELL).floor();
        for c in 0..ncols {
            let v: f64 = values
                .next()
                .ok_or("heightmap: fewer values than ncols x nrows")?
                .parse()
                .map_err(|_| "heightmap: a value is not a number")?;
            let lon = x0 + c as f64 * cell + cell / 2.0;
            let tc = ((lon - hw) / HEIGHTMAP_CELL).floor();
            if tr < 0.0 || tc < 0.0 || tr >= rows as f64 || tc >= cols as f64 || nodata == Some(v) {
                continue;
            }
            let i = tr as usize * cols + tc as usize;
            sum[i] += v;
            count[i] += 1;
        }
    }
    let z = sum
        .iter()
        .zip(&count)
        .map(|(s, n)| if *n == 0 { 0 } else { (s / *n as f64).round().clamp(i16::MIN as f64, i16::MAX as f64) as i16 })
        .collect();
    let h = neolith_core::Heightmap { west: hw, north: hn, cell: HEIGHTMAP_CELL, cols: cols as u32, rows: rows as u32, z };
    h.validate()?;
    Ok(h)
}

/// Parses `data/cultures/cultures.json` into the culture table.
pub fn import_cultures(text: &str) -> Result<Vec<CultureInfo>, String> {
    let root: Json = serde_json::from_str(text).map_err(|e| format!("cannot parse cultures: {e}"))?;
    let items = root.as_array().ok_or("cultures: expected an array")?;
    items
        .iter()
        .map(|c| {
            let get = |k: &str| c.get(k).and_then(Json::as_str).map(str::to_string);
            let id = get("id").ok_or("cultures: an entry has no id")?;
            Ok(CultureInfo {
                kind: get("kind").unwrap_or_default(),
                name: get("name").unwrap_or_else(|| id.clone()),
                wikipedia: c.pointer("/wikipedia/title").and_then(Json::as_str).map(str::to_string),
                id,
            })
        })
        .collect()
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
    if let Some(v) = world.survey_at(hex) {
        feature["properties"]["survey"] = json!(v);
    }
    if let Some(y) = world.farming.get(hex.index()).copied().flatten() {
        feature["properties"]["farming"] = json!(y.0);
    }
    if let Some(t) = world.npp.get(hex.index()).filter(|t| !t.keys().is_empty()) {
        let keys: Map<String, Json> = t.keys().iter().map(|(y, v)| (y.0.to_string(), json!(v))).collect();
        feature["properties"]["npp"] = Json::Object(keys);
    }
    if let Some(t) = world.edge_sea.get(hex.index()).filter(|t| !t.keys().is_empty()) {
        let keys: Map<String, Json> = t.keys().iter().map(|(y, v)| (y.0.to_string(), json!(v))).collect();
        feature["properties"]["edge_sea_km"] = Json::Object(keys);
    }
    if let Some(m) = world.massif.get(hex.index()).and_then(Option::as_ref) {
        let summits: Vec<Json> = m.summits.iter().map(|s| { let (x, y) = s.pos(); json!([x, y, s.height_m()]) }).collect();
        feature["properties"]["massif"] = json!({
            "kind": m.kind.name(), "strike": m.strike_deg(), "coherence": m.coherence(), "floor": m.floor, "summits": summits,
        });
    }
    feature
}

/// Expected population per hex per year as CSV (`hex,year,density_per_km2,farmed,shore_km`),
/// for the pipeline's residual maps: the app's own figures
/// ([`World::expected_at`]), so the equations exist once. Hexes with nothing
/// to say (Water, no productivity) are left out.
pub fn expected_csv(world: &World, years: &[Year]) -> String {
    let mut s = String::from("hex,year,density_per_km2,farmed,shore_km\n");
    let shores: Vec<_> = years.iter().map(|y| world.shore_km(*y)).collect();
    for hex in world.grid.ids() {
        for (y, shore) in years.iter().zip(&shores) {
            let km = shore[hex.index()];
            if let Some(e) = world.expected_given(hex, *y, km as f64) {
                let km = if km.is_finite() { format!("{km:.0}") } else { String::new() };
                let _ = writeln!(s, "{},{},{:.6},{},{km}", hex.geojson_id(), y.0, e.density, e.farmed as u8);
            }
        }
    }
    s
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
                    "properties": {
                        "name": s.name, "founding": s.founded.0, "type": "settlement", "population": pop,
                        "occupation": s.occupation.iter().map(|(a, b)| json!([a.0, b.0])).collect::<Vec<_>>(),
                        "importance": s.importance, "evidence": s.evidence,
                    },
                    "geometry": { "type": "Point", "coordinates": [s.pos.lon, s.pos.lat] },
                })
            })
            .collect(),
    )
}

/// Decodes standard base64 (with or without padding).
fn base64_decode(text: &str) -> Result<Vec<u8>, String> {
    let digit = |c: u8| -> Result<u32, String> {
        Ok(match c {
            b'A'..=b'Z' => c - b'A',
            b'a'..=b'z' => c - b'a' + 26,
            b'0'..=b'9' => c - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return Err(format!("{:?} is not a base64 digit", c as char)),
        } as u32)
    };
    let bytes: Vec<u8> = text.bytes().filter(|c| !c.is_ascii_whitespace()).collect();
    let bytes = bytes.strip_suffix(b"==").or_else(|| bytes.strip_suffix(b"=")).unwrap_or(&bytes);
    if bytes.len() % 4 == 1 {
        return Err("base64 has a stray digit".into());
    }
    let mut out = Vec::with_capacity(bytes.len() * 3 / 4);
    for chunk in bytes.chunks(4) {
        let mut n = 0u32;
        for (k, c) in chunk.iter().enumerate() {
            n |= digit(*c)? << (18 - 6 * k);
        }
        out.extend_from_slice(&n.to_be_bytes()[1..chunk.len()]);
    }
    Ok(out)
}

/// Reads the pipeline's residual table (`data/population/residuals.csv.gz`,
/// unpacked: columns `hex`, `year`, `sites`, `missing` and `outcome` among
/// others) for a world of `hexes` hexes. Hex-years it has no row for (Water,
/// Ice) get no figure.
pub fn import_residuals(text: &str, hexes: usize) -> Result<neolith_core::Residuals, String> {
    use neolith_core::residuals::{Residuals, NO_FIGURE, NO_OUTCOME};
    let rows = csv_rows(text);
    let header = rows.first().ok_or("residuals: empty file")?;
    let col = |name: &str| header.iter().position(|h| h == name).ok_or(format!("residuals: no {name:?} column"));
    let (hex, year, sites, missing, outcome) = (col("hex")?, col("year")?, col("sites")?, col("missing")?, col("outcome")?);
    let body: Vec<&Vec<String>> = rows[1..].iter().filter(|r| r.len() > 1).collect();
    let num = |r: &[String], c: usize, what: &str| -> Result<f64, String> {
        r.get(c).and_then(|v| v.trim().parse::<f64>().ok()).ok_or(format!("residuals: bad {what} in row {r:?}"))
    };
    let mut slices: Vec<Year> = body.iter().map(|r| num(r, year, "year").map(|y| Year(y as i32))).collect::<Result<_, _>>()?;
    slices.sort();
    slices.dedup();
    let n = slices.len() * hexes;
    let mut out = Residuals { slices, outcomes: Vec::new(), sites: vec![0; n], missing: vec![NO_FIGURE; n], outcome: vec![NO_OUTCOME; n] };
    for r in body {
        let id = num(r, hex, "hex")? as u32;
        let h = HexId::from_geojson_id(id).filter(|h| h.index() < hexes).ok_or(format!("residuals: hex {id} is not on the map"))?;
        let k = out.slices.binary_search(&Year(num(r, year, "year")? as i32)).unwrap();
        let i = k * hexes + h.index();
        let name = r.get(outcome).map(|s| s.trim()).filter(|s| !s.is_empty()).ok_or(format!("residuals: no outcome in row {r:?}"))?;
        let code = match out.outcomes.iter().position(|o| o == name) {
            Some(c) => c,
            None => {
                out.outcomes.push(name.to_string());
                out.outcomes.len() - 1
            }
        };
        if code >= NO_OUTCOME as usize {
            return Err("residuals: too many different outcomes".into());
        }
        out.sites[i] = num(r, sites, "sites")?.clamp(0.0, u16::MAX as f64) as u16;
        out.missing[i] = (num(r, missing, "missing")? * 10.0).round().clamp(NO_FIGURE as f64 + 1.0, i16::MAX as f64) as i16;
        out.outcome[i] = code as u8;
    }
    out.validate(hexes)?;
    Ok(out)
}

/// Reads isostyle's speculative layers (`neolith-evidence-1`, written by
/// `isostyle/export.py`) for a world of `hexes` hexes in file order.
pub fn import_evidence(text: &str, hexes: usize) -> Result<Vec<EvidenceLayer>, String> {
    use neolith_core::evidence::{BINS, LEVELS};
    let root: Json = serde_json::from_str(text).map_err(|e| format!("cannot parse the evidence layers: {e}"))?;
    let format = root["format"].as_str().unwrap_or("");
    if format != "neolith-evidence-1" {
        return Err(format!("evidence: format {format:?}, expected \"neolith-evidence-1\""));
    }
    if root["hexes"].as_u64() != Some(hexes as u64) {
        return Err(format!("evidence: made for {} hexes, the map has {hexes}", root["hexes"]));
    }
    if root["bins"].as_u64() != Some(BINS as u64) {
        return Err(format!("evidence: {} bins, this build reads {BINS}", root["bins"]));
    }
    if root["confidence"].as_array().is_some_and(|c| c.len() != LEVELS as usize) {
        return Err(format!("evidence: {} confidence levels, this build reads {LEVELS}", root["confidence"]));
    }
    let slices: Vec<Year> = root["slices"]
        .as_array()
        .ok_or("evidence: no slices")?
        .iter()
        .map(|y| y.as_i64().map(|y| Year(y as i32)).ok_or(format!("evidence: slice {y} is not a year")))
        .collect::<Result<_, _>>()?;
    let text_of = |l: &Json, k: &str| l[k].as_str().unwrap_or("").to_string();
    let mut out = Vec::new();
    for l in root["layers"].as_array().ok_or("evidence: no layers")? {
        let id = text_of(l, "id");
        let codes = base64_decode(l["codes"].as_str().ok_or(format!("evidence layer {id}: no codes"))?)
            .map_err(|e| format!("evidence layer {id}: {e}"))?;
        // Layers may carry their own slices; the export puts them at the top.
        let slices = match l["slices"].as_array() {
            Some(a) => a.iter().filter_map(|y| y.as_i64()).map(|y| Year(y as i32)).collect(),
            None => slices.clone(),
        };
        let layer = EvidenceLayer {
            name: text_of(l, "name"),
            group: text_of(l, "group"),
            set: text_of(l, "set"),
            kind: text_of(l, "kind"),
            units: text_of(l, "units"),
            vmin: l["vmin"].as_f64().ok_or(format!("evidence layer {id}: no vmin"))? as f32,
            vmax: l["vmax"].as_f64().ok_or(format!("evidence layer {id}: no vmax"))? as f32,
            note: text_of(l, "note"),
            slices,
            codes,
            id,
        };
        layer.validate(hexes)?;
        out.push(layer);
    }
    Ok(out)
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
    if !world.farming.is_empty() {
        let _ = writeln!(s, "farming front: reaches {} hexes", world.farming.iter().flatten().count());
    }
    if !world.edge_sea.is_empty() {
        let near = world.edge_sea.iter().filter(|t| t.keys().iter().any(|(_, v)| *v != neolith_core::NO_EDGE_SEA)).count();
        let _ = writeln!(s, "sea beyond the map edge: within reach of {near} hexes");
    }
    if !world.npp.is_empty() {
        let last = world.npp.iter().filter_map(|t| t.keys().last().map(|(_, v)| *v));
        let _ = writeln!(s, "productivity: {} hexes, up to {} g/m²/yr at the last key", world.npp.len(), last.max().unwrap_or(0));
    }
    if world.landform.iter().any(Option::is_some) {
        let n = |l: Landform| world.landform.iter().filter(|x| **x == Some(l)).count();
        let _ = writeln!(
            s,
            "landform: {}",
            Landform::ALL.iter().map(|l| format!("{} {}", l.label(), n(*l))).collect::<Vec<_>>().join(", ")
        );
    }
    if !world.evidence.is_empty() {
        use neolith_core::evidence::{confidence, LEVELS};
        let years = &world.evidence[0].slices;
        let span = format!("{}…{}", years[0].0, years[years.len() - 1].0);
        let _ = writeln!(s, "\nevidence layers: {} ({} slices, {span}; share of coded hex-slices by confidence 0-{})", world.evidence.len(), years.len(), LEVELS - 1);
        for l in &world.evidence {
            let mut n = [0usize; LEVELS as usize];
            l.codes.iter().filter_map(|c| confidence(*c)).for_each(|c| n[c as usize] += 1);
            let coded: usize = n.iter().sum();
            let shares: Vec<String> = n.iter().map(|k| format!("{:.0}%", 100.0 * *k as f64 / coded.max(1) as f64)).collect();
            let set = if l.set.is_empty() { String::new() } else { format!(" / {}", l.set) };
            let _ = writeln!(
                s,
                "  {:<22} {} [{}{set}], {} {}…{}, {:.0}% coded, by confidence {}",
                l.id,
                l.name,
                l.group,
                l.units,
                l.vmin,
                l.vmax,
                100.0 * coded as f64 / l.codes.len().max(1) as f64,
                shares.join("/")
            );
        }
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
    fn massif_round_trips_through_geojson_and_bad_kinds_are_rejected() {
        let feature = |massif: &str| format!(
            r#"{{"type":"FeatureCollection","features":[{{"type":"Feature","geometry":{{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}},
              "properties":{{"id":1,"left":0.0,"top":0.5,"right":0.5773502691896262,"bottom":0.0,"terrain":{{"-10000":"Steppe"}},
              "koeppen":{{}},"population_density":{{}},"landform":2,"massif":{massif}}}}}]}}"#);
        let good = r#"{"kind":"cone","strike":170,"coherence":0.07,"floor":1072,"summits":[[0.28,0.61,2244],[0.62,-0.43,747]]}"#;
        let w = import_map(&feature(good)).unwrap().world;
        let m = w.massif[0].as_ref().unwrap();
        assert_eq!((m.kind, m.floor, m.summits.len()), (MassifKind::Cone, 1072, 2));
        assert_eq!(m.summits[0].pos(), (0.28, 0.61));
        let back = hex_feature(&w, HexId::from_geojson_id(1).unwrap());
        let again = import_map(&feature(&back["properties"]["massif"].to_string())).unwrap().world;
        assert_eq!(again.massif, w.massif);
        let bad = import_map(&feature(&good.replace("cone", "mesa"))).err().unwrap();
        assert!(bad.contains("massif kind"), "{bad}");
    }

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

    #[test]
    fn inferred_settlements_are_appended_and_tagged() {
        let mut w = World::empty(GridSpec { cols: 2, rows: 2, origin_lon: 0.0, origin_lat: 1.0, w: 0.5773502691896262, h: 0.5 });
        let (s, info, _) = import_settlement_records(
            r#"[{"id": 1, "geometry": {"type": "Point", "coordinates": [0.2, 0.5]},
                "properties": {"name": "Recorded", "founding": -5000, "sources": ["xronos"]}}]"#,
        )
        .unwrap();
        (w.settlements, w.site_info) = (s, info);
        // No `sources` in the file: the tag is added all the same.
        let inferred = r#"[{"id": 2, "geometry": {"type": "Point", "coordinates": [0.3, 0.5]},
            "properties": {"name": "Inferred village 1", "founding": -4000, "occupation": [[-4000, -2000]],
              "importance": 0, "evidence": 0}}]"#;
        assert_eq!(append_inferred(&mut w, inferred).unwrap(), 1);
        assert_eq!(w.settlements.len(), 2);
        assert!(!w.is_inferred(0) && w.is_inferred(1));
        assert!(append_inferred(&mut w, &inferred.replace("\"id\": 2", "\"id\": 1")).is_err());
    }

    #[test]
    fn settlement_records_carry_the_metadata() {
        let text = r#"[{"id": 7, "geometry": {"type": "Point", "coordinates": [1, 2]},
            "properties": {"name": "A", "founding": -6000, "abandoned": -5000, "type": "cave",
              "occupation": [[-4000, -3000], [-6000, -5000]],
              "periods": ["LBK"], "aliases": ["B"], "culture": {"-5800": "lbk", "-6000": "x"},
              "stage_inferred": {"-6000": "neolithic"}, "features": ["rock art"],
              "wikipedia": "A (site)", "wikidata": "Q1", "sources": ["xronos"],
              "references": ["r1", "r1", "r2"], "importance": 3, "evidence": 0}},
            {"id": 8, "geometry": {"type": "Point", "coordinates": [3, 4]},
            "properties": {"name": "C", "founding": -7000}}]"#;
        let (s, info, _) = import_settlement_records(text).unwrap();
        assert_eq!((s.len(), info.len()), (2, 2));
        assert_eq!(s[0].occupation, vec![(Year(-6000), Year(-5000)), (Year(-4000), Year(-3000))]);
        assert!(s[1].occupation.is_empty());
        assert_eq!((s[0].importance, s[0].evidence), (3, 0));
        assert_eq!((s[1].importance, s[1].evidence), (Settlement::DEFAULT_IMPORTANCE, Settlement::DEFAULT_EVIDENCE));
        assert!(import_settlement_records(&text.replace("\"importance\": 3", "\"importance\": 4")).is_err());
        let bad = text.replace("[-4000, -3000]", "[-3000, -4000]");
        assert!(import_settlement_records(&bad).is_err());
        let a = &info[0];
        assert_eq!((a.kind.as_str(), a.abandoned), ("cave", Some(Year(-5000))));
        assert_eq!(a.culture, vec![(Year(-6000), "x".to_string()), (Year(-5800), "lbk".to_string())]);
        assert_eq!(a.stage_inferred, vec![(Year(-6000), "neolithic".to_string())]);
        assert_eq!((a.wikipedia.as_deref(), a.wikidata.as_deref()), (Some("A (site)"), Some("Q1")));
        assert_eq!(a.references, vec!["r1", "r2"]);
        assert_eq!(a.features, vec!["rock art"]);
        assert_eq!(info[1], SiteInfo::default());

        let csv = "site_id,site,lab_number,c14_age,c14_error,cal_year,dataset,site_as_filed,references\n\
                   7,A,X-2,6000,30,-4900,xronos,\"A, \"\"the\"\" site\",r1\n\
                   7,A,X-1,7100,45,-5990,p3k14c,A,\n\
                   99,Z,Z-1,100,10,1800,xronos,Z,\n";
        let mut info = info;
        assert_eq!(attach_dates(&s, &mut info, csv).unwrap(), (2, 1));
        let labs: Vec<_> = info[0].dates.iter().map(|d| d.lab.as_str()).collect();
        assert_eq!(labs, ["X-1", "X-2"]);
        assert_eq!(info[0].dates[0], C14Date { lab: "X-1".into(), bp: 7100, err: 45, cal: Year(-5990), dataset: "p3k14c".into() });
    }

    #[test]
    fn evidence_import() {
        assert_eq!(base64_decode("AAEC/w==").unwrap(), vec![0, 1, 2, 255]);
        assert_eq!(base64_decode("TWFu").unwrap(), b"Man");
        assert_eq!(base64_decode("TWE").unwrap(), b"Ma");
        assert!(base64_decode("TW!u").is_err());
        // 2 slices × 2 hexes: [0, 60, 249, 255].
        let doc = |hexes: usize, codes: &str| {
            format!(
                r#"{{"format":"neolith-evidence-1","hexes":{hexes},"slices":[-6000,-5000],"bins":50,
                    "confidence":["a","b","c","d","e"],
                    "layers":[{{"id":"x","name":"X","group":"G","set":"","kind":"share","units":"share",
                                "vmin":0.0,"vmax":1.0,"note":"n","codes":"{codes}"}}]}}"#
            )
        };
        let layers = import_evidence(&doc(2, "ADz5/w=="), 2).unwrap();
        assert_eq!(layers.len(), 1);
        let l = &layers[0];
        assert_eq!((l.id.as_str(), l.group.as_str(), l.note.as_str()), ("x", "G", "n"));
        assert_eq!(l.slices, vec![Year(-6000), Year(-5000)]);
        assert_eq!(l.codes, vec![0, 60, 249, 255]);
        assert_eq!(l.code_at(HexId(1), Year(-5500)), 60);
        assert_eq!(l.code_at(HexId(1), Year(-4000)), 255);
        assert!(import_evidence(&doc(2, "ADz5/w=="), 3).is_err(), "hex count must match the map");
        assert!(import_evidence(&doc(2, "ADz5"), 2).is_err(), "codes must cover every slice");
        assert!(import_evidence(&doc(2, "ADz6/w=="), 2).is_err(), "code 250 is out of range");
        let mut w = World::empty(GridSpec { cols: 2, rows: 1, origin_lon: 0.0, origin_lat: 1.0, w: 0.5773502691896262, h: 0.5 });
        w.evidence = layers;
        assert!(stats(&w).contains("evidence layers: 1"));
    }

    #[test]
    fn residuals_table() {
        let csv = "hex,year,expected_per_km2,sites,missing,outcome\n\
                   1,-6000,0.1,0,0.26,as expected\n\
                   3,-6000,0.1,2,-1.5,more sites than expected\n\
                   1,-5000,0.1,1,2.04,little dated archaeology nearby\n";
        let r = import_residuals(csv, 4).unwrap();
        assert_eq!(r.slices, vec![Year(-6000), Year(-5000)]);
        assert_eq!(r.outcomes, vec!["as expected", "more sites than expected", "little dated archaeology nearby"]);
        let at = |hex: u32, y: i32| r.at(HexId(hex), Year(y)).map(|x| (x.sites, x.missing, x.outcome.to_string()));
        assert_eq!(at(0, -6000), Some((0, 0.3, "as expected".into())));
        assert_eq!(at(2, -6000), Some((2, -1.5, "more sites than expected".into())));
        assert_eq!(at(0, -5000), Some((1, 2.0, "little dated archaeology nearby".into())));
        // No row: no figure. Hexes off the map and missing columns are errors.
        assert_eq!(at(1, -6000), None);
        assert_eq!(at(2, -5000), None);
        assert!(import_residuals(csv, 2).is_err());
        assert!(import_residuals("hex,year,sites\n1,-6000,0\n", 4).is_err());
        assert!(import_residuals("", 4).is_err());
    }

    #[test]
    fn csv_handles_quotes() {
        assert_eq!(csv_rows("a,\"b,c\",\"d\"\"e\"\r\n1,2,3"), vec![vec!["a", "b,c", "d\"e"], vec!["1", "2", "3"]]);
    }

    #[test]
    fn cultures_table() {
        let t = r#"[{"id": "lbk", "kind": "culture", "name": "Linear Pottery", "wikipedia": {"title": "Linear Pottery culture"}},
                    {"id": "x", "kind": "stage", "name": "X"}]"#;
        let c = import_cultures(t).unwrap();
        assert_eq!(c[0], CultureInfo { id: "lbk".into(), kind: "culture".into(), name: "Linear Pottery".into(), wikipedia: Some("Linear Pottery culture".into()) });
        assert_eq!(c[1].wikipedia, None);
    }
}

#[cfg(test)]
mod heightmap_tests {
    use super::*;

    #[test]
    fn averages_into_tenth_degree_cells_over_the_grid() {
        let grid = GridSpec { cols: 2, rows: 2, origin_lon: 10.0, origin_lat: 50.0, w: 0.2, h: 0.2 };
        // 0.05° source cells: each 0.1° target cell averages four.
        let (w, s, e, n) = grid.bounds();
        let (nc, nr) = (((e - w) / 0.05).ceil() as usize + 4, ((n - s) / 0.05).ceil() as usize + 4);
        let mut text = format!("ncols {nc}\nnrows {nr}\nxllcorner {}\nyllcorner {}\ncellsize 0.05\nNODATA_value -9999\n", w - 0.1, s - 0.1);
        for r in 0..nr {
            let row: Vec<String> = (0..nc).map(|c| if r == 0 && c == 0 { "-9999".into() } else { ((c % 2) * 100).to_string() }).collect();
            text.push_str(&row.join(" "));
            text.push('\n');
        }
        let h = import_heightmap(&text, &grid).unwrap();
        assert_eq!(h.cell, HEIGHTMAP_CELL);
        assert!(h.west <= w && h.north >= n);
        assert_eq!(h.z.len(), (h.cols * h.rows) as usize);
        // Alternating 0 / 100 columns average to 50 across a target cell.
        assert!(h.z.iter().all(|z| *z == 50), "{:?}", h.z);
        assert!(import_heightmap("ncols 2\n", &grid).is_err());
    }
}
