use crate::grid::{GridSpec, HexId, LonLat};
use crate::lake::Lake;
use crate::massif::Massif;
#[cfg(test)]
use crate::massif::{MassifKind, Summit};
use crate::river::{River, RiverClass};
use crate::time::Year;
use crate::timeline::Timeline;
use crate::elevation::{self, NO_ELEVATION};
use crate::evidence::EvidenceLayer;
use crate::residuals::Residuals;
use crate::farming;
use crate::forager;
use crate::productivity;
use crate::values::{Koeppen, Landform, MapMode, PopDensity, Prop, Terrain, Value};
use serde::{Deserialize, Serialize};

/// Snapshot byte for "no keyframe in effect yet" (year before the first key).
pub const NO_DATA: u8 = 255;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Settlement {
    pub id: u32,
    pub name: String,
    pub pos: LonLat,
    pub founded: Year,
    pub population: Timeline<u32>,
    /// Occupation phases `(start, abandoned_by)`, sorted, from the site's
    /// dates: each ends a fixed span after its last date, the point by which
    /// the site is assumed abandoned. Empty means occupied from `founded` on
    /// (hand entries, Wikidata-only sites, files before version 6).
    pub occupation: Vec<(Year, Year)>,
    /// Inferred importance, 0-3, from the site type, how long it was lived
    /// in and how it compares with its neighbours (the pipeline's
    /// `score_sites`). Sizes the piece when there is no population figure.
    pub importance: u8,
    /// How firmly the site is attested, 0-2: one date (or none), 2-4, 5+.
    pub evidence: u8,
}

impl Settlement {
    /// Importance and evidence for files and hand entries that give none:
    /// an ordinary, well-attested site.
    pub const DEFAULT_IMPORTANCE: u8 = 1;
    pub const DEFAULT_EVIDENCE: u8 = 2;

    /// Whether the site is occupied in `year`: on or after `founded`, before
    /// the last phase's end, and not in a gap between phases. Years between
    /// `founded` and the first phase count as occupied, since a hand-entered
    /// founding may be earlier than the first date.
    pub fn exists_at(&self, year: Year) -> bool {
        if self.founded > year {
            return false;
        }
        match self.occupation.last() {
            None => true,
            Some(&(_, end)) if year >= end => false,
            Some(_) => !self.occupation.windows(2).any(|w| w[0].1 <= year && year < w[1].0),
        }
    }

    /// The year the site is assumed abandoned by, if it is.
    pub fn abandoned_by(&self) -> Option<Year> {
        self.occupation.last().map(|(_, end)| *end)
    }

    /// The stretch of occupation containing `year`, as `(start, end)`
    /// (end exclusive), or `None` if the site is not occupied then. The first
    /// stretch starts at `founded` if that is earlier than the first phase;
    /// a site without phases runs from `founded` with no end.
    pub fn phase_at(&self, year: Year) -> Option<(Year, Year)> {
        if !self.exists_at(year) {
            return None;
        }
        let i = self.occupation.iter().rposition(|(a, _)| *a <= year).unwrap_or(0);
        Some(match self.occupation.get(i) {
            None => (self.founded, Year(i32::MAX)),
            Some(&(a, b)) if i == 0 => (a.min(self.founded), b),
            Some(&(a, b)) => (a, b),
        })
    }

    /// Years the site has been lived in up to `year`, not counting gaps
    /// between phases (the first phase starting at `founded` if that is
    /// earlier, as in [`Self::phase_at`]). Drives how big a tell has grown
    /// and how long its ruin lasts.
    pub fn occupied_years_by(&self, year: Year) -> i32 {
        if self.founded > year {
            return 0;
        }
        if self.occupation.is_empty() {
            return year.0 - self.founded.0;
        }
        self.occupation
            .iter()
            .enumerate()
            .map(|(k, &(a, b))| {
                let a = if k == 0 { a.min(self.founded) } else { a };
                (b.0.min(year.0) - a.0).max(0)
            })
            .sum()
    }

    /// Population at `year`: the latest population key at or before it,
    /// within the current phase of occupation. `None` while the site is
    /// unoccupied, and a figure never carries across a gap.
    pub fn population_at(&self, year: Year) -> Option<u32> {
        let (start, _) = self.phase_at(year)?;
        self.population.keys().iter().rev().find(|(y, _)| *y <= year && *y >= start).map(|(_, n)| *n)
    }
}

/// One radiocarbon date at a site, as filed (lab number, conventional age
/// and 1-sigma error in 14C years BP) plus its calibrated median year.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct C14Date {
    pub lab: String,
    pub bp: u32,
    pub err: u32,
    pub cal: Year,
    /// The database the date came from (e.g. `xronos`, `p3k14c`).
    pub dataset: String,
}

/// What the record says about a settlement, beyond what the board needs.
/// Every field may be empty; worlds written before version 6 have none.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SiteInfo {
    /// Site type as filed: "settlement", "cave", "rock shelter", ...
    pub kind: String,
    /// Latest calibrated date at the site.
    pub abandoned: Option<Year>,
    pub aliases: Vec<String>,
    /// Period labels on the site's dates, as filed.
    pub periods: Vec<String>,
    /// (from year, culture or stage id in [`World::cultures`]), from the
    /// site's own labelled dates.
    pub culture: Vec<(Year, String)>,
    pub stage: Vec<(Year, String)>,
    /// The same, inferred from neighbouring sites where the site's own
    /// labels say nothing.
    pub culture_inferred: Vec<(Year, String)>,
    pub stage_inferred: Vec<(Year, String)>,
    /// Notable features recorded by hand (rock art, megaliths, ...).
    pub features: Vec<String>,
    /// English Wikipedia article title, and Wikidata id, when matched.
    pub wikipedia: Option<String>,
    pub wikidata: Option<String>,
    /// Culture labels Wikidata gives the site.
    pub wikidata_culture: Vec<String>,
    /// Datasets the site comes from, and publications they cite.
    pub sources: Vec<String>,
    pub references: Vec<String>,
    /// Radiocarbon dates, oldest first.
    pub dates: Vec<C14Date>,
}

impl SiteInfo {
    /// The `sources` tag of inferred settlements: guesses placed by the
    /// pipeline (`pipeline/inferred.py`) where the record is thin for a known
    /// reason, never a recorded site.
    pub const INFERRED: &'static str = "inferred";

    /// Whether this is an inferred settlement, not a recorded one.
    pub fn is_inferred(&self) -> bool {
        self.sources.iter().any(|s| s == Self::INFERRED)
    }
}

/// An archaeological culture or stage that [`SiteInfo`] refers to by id.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CultureInfo {
    pub id: String,
    /// "culture" or "stage".
    pub kind: String,
    pub name: String,
    /// English Wikipedia article title it is cited to.
    pub wikipedia: Option<String>,
}

/// The whole time-varying world, struct-of-arrays indexed by [`HexId`].
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct World {
    pub grid: GridSpec,
    pub terrain: Vec<Timeline<Terrain>>,
    pub koeppen: Vec<Timeline<Koeppen>>,
    pub pop: Vec<Timeline<PopDensity>>,
    pub settlements: Vec<Settlement>,
    /// Per hex: the [`RiverClass`] (as u8) of the rivers crossing it.
    pub river: Vec<Timeline<u8>>,
    pub rivers: Vec<River>,
    pub lakes: Vec<Lake>,
    /// Per hex: median elevation in metres (ETOPO1, present-day datum), or
    /// [`NO_ELEVATION`]. Static: sea level changes show through `terrain`.
    pub elevation: Vec<i16>,
    /// Per hex: static [`Landform`], or `None` (files before version 5).
    pub landform: Vec<Option<Landform>>,
    /// Per settlement, same order as `settlements`; empty for files before
    /// version 6. Use [`World::site_info`].
    pub site_info: Vec<SiteInfo>,
    /// The cultures and stages `site_info` refers to.
    pub cultures: Vec<CultureInfo>,
    /// Per hex: survey intensity, 0-2 (0: few dated records of any period,
    /// so an absence of sites says little; 2: well surveyed). A detection
    /// layer, never an input to population. Empty for files before
    /// version 7. Use [`World::survey_at`].
    pub survey: Vec<u8>,
    /// Per hex: net primary productivity over time, in g dry matter/m²/yr (see
    /// [`productivity`]). Empty for files before version 8. Use
    /// [`World::npp_at`].
    pub npp: Vec<Timeline<u16>>,
    /// Per hex: the year farming reaches it (a front from one origin at one
    /// speed; see the pipeline's `farming.py`), or `None` if it has not by
    /// the end of the period. Says nothing about whether the hex can be
    /// farmed. Empty for files before version 9.
    pub farming: Vec<Option<Year>>,
    /// Speculative evidence layers ([`crate::evidence`]), in picker order.
    /// Empty for files before version 10.
    pub evidence: Vec<EvidenceLayer>,
    /// Sites the list is missing per hex and epoch ([`crate::residuals`]),
    /// from the pipeline. `None` for files before version 11 and worlds
    /// built without it.
    pub residuals: Option<Residuals>,
    /// Per hex: km from its centre to the nearest open sea beyond the map's
    /// edge over time, from the pipeline's wider elevation window
    /// (`edge_sea.py`); [`NO_EDGE_SEA`] where there is none within reach.
    /// The map's own Water cannot show a coast that lies off the map (the
    /// Gulf of Guinea, the Atlantic off Senegal). Empty for files before
    /// version 12. Use [`World::edge_sea_km`].
    pub edge_sea: Vec<Timeline<u16>>,
    /// Per hex: a sketch of its high ground ([`crate::massif`]) where it is
    /// hilly or mountainous, from the pipeline's elevation raster. Empty
    /// for files before version 13; the board then lays peaks out by hash.
    pub massif: Vec<Option<Massif>>,
    /// Today's topography at a few samples per hex ([`crate::heightmap`]),
    /// for drawing relief only. `None` for files before version 14.
    pub heightmap: Option<crate::heightmap::Heightmap>,
    /// Ancestry of individual ancient genomes ([`crate::ancestry`]), for the
    /// Ancestry map mode. `None` for files before version 15 and worlds
    /// built without it.
    pub ancestry: Option<crate::ancestry::Ancestry>,
}

/// An [`World::edge_sea`] value meaning no sea beyond the edge within reach.
pub const NO_EDGE_SEA: u16 = u16::MAX;

/// What [`World::expected_at`] returns.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Expected {
    /// People per km².
    pub density: f64,
    /// Farming has arrived and the hex can be farmed this year.
    pub farmed: bool,
}

/// The flattened state at one year: one byte per hex per property
/// ([`Value::as_u8`], or [`NO_DATA`]). This is what the renderer uploads.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Snapshot {
    pub year: Year,
    pub terrain: Vec<u8>,
    pub koeppen: Vec<u8>,
    pub pop: Vec<u8>,
    /// [`RiverClass`] per hex (0 where no data).
    pub river: Vec<u8>,
    /// [`elevation::band`] per hex, given whether it is Water this year.
    pub elevation: Vec<u8>,
    /// [`productivity::band`] per hex; [`NO_DATA`] on Water and where the
    /// file has no productivity.
    pub npp: Vec<u8>,
    /// [`forager::biodiversity_band`] of the biodiversity the productivity
    /// implies; [`NO_DATA`] wherever `npp` is.
    pub biodiversity: Vec<u8>,
    /// [`farming::band`] of [`World::expected_at`]; [`NO_DATA`] on Water
    /// and where the file has no productivity.
    pub expected: Vec<u8>,
    /// [`World::shore_km`] per hex, `u16::MAX` where it is infinite. Pass it
    /// to [`World::expected_given`] to ask about one hex without working
    /// the distances out again.
    pub shore_km: Vec<u16>,
    /// The surface height the board raises each hex to, in metres
    /// ([`World::surface_heights`]).
    pub height: Vec<i16>,
}

impl Snapshot {
    pub fn get(&self, prop: Prop) -> &[u8] {
        match prop {
            Prop::Terrain => &self.terrain,
            Prop::Koeppen => &self.koeppen,
            Prop::Pop => &self.pop,
        }
    }

    /// What the board shows in `mode`, one byte per hex. Empty for
    /// [`MapMode::Evidence`]: a snapshot doesn't know which layer is picked
    /// (see [`crate::EvidenceLayer::codes_at`]).
    pub fn layer(&self, mode: MapMode) -> &[u8] {
        match mode {
            MapMode::Evidence | MapMode::Missing | MapMode::Ancestry => &[],
            MapMode::Elevation => &self.elevation,
            MapMode::Npp => &self.npp,
            MapMode::Biodiversity => &self.biodiversity,
            MapMode::Expected => &self.expected,
            MapMode::Terrain | MapMode::Ground => &self.terrain,
            MapMode::Koeppen => &self.koeppen,
            MapMode::Pop => &self.pop,
        }
    }

    pub fn value(&self, prop: Prop, hex: HexId) -> Option<Value> {
        Value::from_u8(prop, self.get(prop)[hex.index()])
    }

    pub fn river(&self, hex: HexId) -> RiverClass {
        RiverClass::from_u8(self.river[hex.index()]).unwrap_or(RiverClass::None)
    }
}

impl World {
    /// An empty world (no keyframes) on the given grid.
    pub fn empty(grid: GridSpec) -> Self {
        let n = grid.len();
        Self {
            grid,
            terrain: vec![Timeline::new(); n],
            koeppen: vec![Timeline::new(); n],
            pop: vec![Timeline::new(); n],
            settlements: Vec::new(),
            river: vec![Timeline::new(); n],
            rivers: Vec::new(),
            lakes: Vec::new(),
            elevation: vec![NO_ELEVATION; n],
            landform: vec![None; n],
            site_info: Vec::new(),
            cultures: Vec::new(),
            survey: Vec::new(),
            npp: Vec::new(),
            farming: Vec::new(),
            evidence: Vec::new(),
            residuals: None,
            edge_sea: Vec::new(),
            massif: Vec::new(),
            heightmap: None,
            ancestry: None,
        }
    }

    /// Whether the world can show the Ancestry map mode: the sample table
    /// and one `anc_<key>` evidence layer per component.
    pub fn has_ancestry(&self) -> bool {
        self.ancestry.as_ref().is_some_and(|a| {
            a.components.len() == crate::ancestry::COMPONENTS
                && a.components.iter().all(|c| self.evidence_layer(&format!("anc_{}", c.key)).is_some())
        })
    }

    /// One hex's ancestry shares at `year` from the `anc_*` layers, in
    /// component order and normalised to sum to 1; `None` where no genome is
    /// in reach (the layers are recorded only and never filled).
    pub fn ancestry_shares(&self, hex: HexId, year: Year) -> Option<[f32; crate::ancestry::COMPONENTS]> {
        let a = self.ancestry.as_ref()?;
        let mut shares = [0.0f32; crate::ancestry::COMPONENTS];
        for (k, c) in a.components.iter().take(shares.len()).enumerate() {
            let l = self.evidence_layer(&format!("anc_{}", c.key))?;
            shares[k] = l.value(l.code_at(hex, year))?;
        }
        let total: f32 = shares.iter().sum();
        (total > 1e-6).then(|| shares.map(|v| v / total))
    }

    /// The Ancestry map code of every hex at `year` ([`crate::ancestry::code`];
    /// [`crate::ancestry::NO_CODE`] where no genome is in reach). A hex is
    /// "thin" when fewer than [`World::ANCESTRY_FIRM`] date-weighted fitted
    /// genomes lie within [`World::ANCESTRY_REACH_KM`] of it.
    pub fn ancestry_codes(&self, year: Year) -> Vec<u8> {
        use crate::ancestry::{code, Status, COMPONENTS, NO_CODE};
        let n = self.grid.len();
        let Some(a) = self.ancestry.as_ref().filter(|_| self.has_ancestry()) else {
            return vec![NO_CODE; n];
        };
        let layers: Vec<Vec<u8>> = a
            .components
            .iter()
            .map(|c| self.evidence_layer(&format!("anc_{}", c.key)).map_or(Vec::new(), |l| l.codes_at(year)))
            .collect();
        // Fitted genomes dated near this year, with their weight.
        let near: Vec<(crate::grid::LonLat, f32)> = a
            .samples
            .iter()
            .filter(|s| s.status == Status::Fit)
            .map(|s| (s.pos, s.overlap(year, Self::ANCESTRY_HALF_YEARS)))
            .filter(|(_, w)| *w > 0.01)
            .collect();
        let dlat = Self::ANCESTRY_REACH_KM / 111.0;
        self.grid
            .ids()
            .map(|hex| {
                let mut shares = [0.0f32; COMPONENTS];
                for (k, codes) in layers.iter().enumerate() {
                    match crate::evidence::bin(codes.get(hex.index()).copied().unwrap_or(crate::evidence::NO_VALUE)) {
                        Some(b) => shares[k] = (b as f32 + 0.5) / crate::evidence::BINS as f32,
                        None => return NO_CODE,
                    }
                }
                let p = self.grid.centre(hex);
                let dlon = dlat / p.lat.to_radians().cos().max(0.2);
                let weight: f32 = near
                    .iter()
                    .filter(|(q, _)| (q.lat - p.lat).abs() <= dlat && (q.lon - p.lon).abs() <= dlon)
                    .filter(|(q, _)| crate::geom::great_circle_km([q.lon, q.lat], [p.lon, p.lat]) <= Self::ANCESTRY_REACH_KM)
                    .map(|(_, w)| *w)
                    .sum();
                code(&shares, weight < Self::ANCESTRY_FIRM)
            })
            .collect()
    }

    /// How far a hex looks for the genomes behind its colour, in km.
    pub const ANCESTRY_REACH_KM: f64 = 150.0;
    /// Half the window of years a genome counts for around the current year.
    pub const ANCESTRY_HALF_YEARS: f32 = 500.0;
    /// Date-weighted fitted genomes in reach below which a hex is drawn thin.
    pub const ANCESTRY_FIRM: f32 = 2.0;

    /// The evidence layer with this id.
    pub fn evidence_layer(&self, id: &str) -> Option<&EvidenceLayer> {
        self.evidence.iter().find(|l| l.id == id)
    }

    /// Productivity of a hex at `year` in g/m²/yr, if the file has the
    /// layer and the hex a value by then. Stored for every hex; a hex that
    /// is Water that year produces nothing a population can use.
    pub fn npp_at(&self, hex: HexId, year: Year) -> Option<u16> {
        self.npp.get(hex.index()).and_then(|t| t.at(year))
    }

    /// Expected hunter-gatherer density of a hex at `year` in people per
    /// km² ([`forager::density`]): `None` without productivity, and on
    /// Water or Ice.
    pub fn forager_density_at(&self, hex: HexId, year: Year) -> Option<f64> {
        match self.terrain[hex.index()].at(year) {
            Some(Terrain::Water | Terrain::Ice) => None,
            _ => self.npp_at(hex, year).map(|npp| forager::density(npp, self.shore_km(year)[hex.index()] as f64)),
        }
    }

    /// Km from a hex's centre to the nearest open sea beyond the map's edge
    /// at `year` ([`World::edge_sea`]), if the file has the layer and there
    /// is such a sea within reach.
    pub fn edge_sea_km(&self, hex: HexId, year: Year) -> Option<u16> {
        self.edge_sea.get(hex.index()).and_then(|t| t.at(year)).filter(|km| *km != NO_EDGE_SEA)
    }

    /// Per hex: km from its centre to the nearest water at `year`, 0 on
    /// Water, infinite if there is none. The nearer of the edge of the
    /// nearest Water hex on the map (sea or lake: the distance to that
    /// hex's centre, less half a hex) and the sea beyond the map's edge
    /// ([`World::edge_sea_km`]). In whole km.
    ///
    /// Found by spreading outward from every Water hex at once, nearest
    /// first, so it costs one pass over the grid.
    pub fn shore_km(&self, year: Year) -> Vec<f32> {
        use std::cmp::Reverse;
        let n = self.grid.len();
        let centre = |i: usize| {
            let c = self.grid.centre(HexId(i as u32));
            [c.lon, c.lat]
        };
        let mut out = vec![f32::INFINITY; n];
        let mut heap = std::collections::BinaryHeap::new();
        for (i, t) in self.terrain.iter().enumerate() {
            if t.at(year) == Some(Terrain::Water) {
                heap.push(Reverse((0u32, i as u32, i as u32)));
            }
        }
        // Metres to the Water hex each entry came from; the nearest claim on a hex wins.
        while let Some(Reverse((m, i, source))) = heap.pop() {
            let i = i as usize;
            if out[i].is_finite() {
                continue;
            }
            out[i] = m as f32 / 1000.0;
            for nb in self.grid.neighbours(HexId(i as u32)) {
                if !out[nb.index()].is_finite() {
                    let km = crate::geom::great_circle_km(centre(nb.index()), centre(source as usize));
                    heap.push(Reverse(((km * 1000.0) as u32, nb.0, source)));
                }
            }
        }
        let hex_km = (self.grid.h * 111.2) as f32;
        // Whole km: fine for the model, and a snapshot can hold it in 16 bits.
        out.iter()
            .enumerate()
            .map(|(i, d)| {
                let on_map = (d - d.min(hex_km) / 2.0).round();
                match self.edge_sea_km(HexId(i as u32), year) {
                    Some(km) if *d > 0.0 => on_map.min(km as f32),
                    _ => on_map,
                }
            })
            .collect()
    }

    /// Survey intensity of a hex (0-2), if the file has the layer.
    pub fn survey_at(&self, hex: HexId) -> Option<u8> {
        self.survey.get(hex.index()).copied()
    }

    /// The record for settlement `i`, if the file has one.
    pub fn site_info(&self, i: usize) -> Option<&SiteInfo> {
        self.site_info.get(i)
    }

    /// Whether settlement `i` is inferred, not recorded ([`SiteInfo::is_inferred`]).
    pub fn is_inferred(&self, i: usize) -> bool {
        self.site_info(i).is_some_and(SiteInfo::is_inferred)
    }

    /// The culture or stage with this id.
    pub fn culture(&self, id: &str) -> Option<&CultureInfo> {
        self.cultures.iter().find(|c| c.id == id)
    }

    pub fn snapshot(&self, year: Year) -> Snapshot {
        let terrain: Vec<u8> = self.terrain.iter().map(|t| t.at(year).map_or(NO_DATA, |v| v as u8)).collect();
        let elevation = self
            .elevation
            .iter()
            .zip(&terrain)
            .map(|(z, t)| elevation::band(*z, *t == Terrain::Water as u8))
            .collect();
        let height = self.surface_heights(year, &terrain);
        let land_npp = |i: usize| self.npp.get(i).and_then(|t| t.at(year)).filter(|_| terrain[i] != Terrain::Water as u8);
        let npp = (0..terrain.len()).map(|i| land_npp(i).map_or(NO_DATA, productivity::band)).collect();
        let biodiversity = (0..terrain.len())
            .map(|i| land_npp(i).map_or(NO_DATA, |v| forager::biodiversity_band(forager::biodiversity(v))))
            .collect();
        let shore = self.shore_km(year);
        let expected = self
            .grid
            .ids()
            .map(|h| self.expected_given(h, year, shore[h.index()] as f64).map_or(NO_DATA, |e| farming::band(e.density)))
            .collect();
        let shore_km = shore.iter().map(|d| if d.is_finite() { *d as u16 } else { u16::MAX }).collect();
        Snapshot {
            year,
            npp,
            biodiversity,
            expected,
            shore_km,
            terrain,
            elevation,
            height,
            koeppen: self.koeppen.iter().map(|t| t.at(year).map_or(NO_DATA, |v| v.index())).collect(),
            pop: self.pop.iter().map(|t| t.at(year).map_or(NO_DATA, |v| v as u8)).collect(),
            river: self.river.iter().map(|t| t.at(year).unwrap_or(0)).collect(),
        }
    }

    /// The top of each hex at `year`, in metres above today's sea level, for
    /// drawing relief: land at its elevation (not below 0, so exposed shelf
    /// and the Caspian depression sit level with the sea); Water at the level
    /// of the lake it lies in (the shoreline contains its centre, or failing
    /// that a neighbour's), and otherwise at `max(elevation, 0)`, which is
    /// sea level for the sea. `terrain` is the snapshot's terrain bytes.
    pub fn surface_heights(&self, year: Year, terrain: &[u8]) -> Vec<i16> {
        let water = |i: usize| terrain[i] == Terrain::Water as u8;
        let mut out: Vec<i16> =
            self.elevation.iter().map(|z| if *z == NO_ELEVATION { 0 } else { (*z).max(0) }).collect();
        // Lake levels, for Water hexes whose centre is inside a shoreline.
        let mut lake: Vec<Option<i16>> = vec![None; out.len()];
        for l in &self.lakes {
            let Some(shape) = l.shape_at(year) else { continue };
            let pts = shape.rings.iter().flatten();
            let (mut w, mut s, mut e, mut n) = (f64::INFINITY, f64::INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY);
            for p in pts {
                (w, s, e, n) = (w.min(p.lon), s.min(p.lat), e.max(p.lon), n.max(p.lat));
            }
            let level = shape.level.round() as i16;
            for id in self.grid.ids() {
                let i = id.index();
                if !water(i) || lake[i].is_some() {
                    continue;
                }
                let c = self.grid.centre(id);
                if c.lon >= w && c.lon <= e && c.lat >= s && c.lat <= n && shape.contains(c) {
                    lake[i] = Some(level);
                }
            }
        }
        // Lake hexes whose centre is just outside the shoreline.
        let direct = lake.clone();
        for id in self.grid.ids() {
            let i = id.index();
            if water(i) && direct[i].is_none() {
                lake[i] = self.grid.neighbours(id).find_map(|nb| direct[nb.index()]);
            }
        }
        for (h, l) in out.iter_mut().zip(&lake) {
            if let Some(level) = l {
                *h = *level;
            }
        }
        out
    }

    /// Every year at which any hex property or river has a keyframe, sorted, unique.
    pub fn keyframe_years(&self) -> Vec<Year> {
        let mut years: Vec<Year> = Vec::new();
        let mut last = None;
        let mut add = |y: Year| {
            // Timelines overwhelmingly share keys; skip the common repeats cheaply.
            if last != Some(y) {
                last = Some(y);
                if let Err(i) = years.binary_search(&y) {
                    years.insert(i, y);
                }
            }
        };
        for i in 0..self.grid.len() {
            self.terrain[i].keys().iter().for_each(|(y, _)| add(*y));
            self.koeppen[i].keys().iter().for_each(|(y, _)| add(*y));
            self.pop[i].keys().iter().for_each(|(y, _)| add(*y));
            self.river[i].keys().iter().for_each(|(y, _)| add(*y));
        }
        for r in &self.rivers {
            r.state.keys().iter().for_each(|(y, _)| add(*y));
        }
        for l in &self.lakes {
            l.shape.keys().iter().for_each(|(y, _)| add(*y));
        }
        years
    }

    /// The value of `prop` in effect at `year`.
    pub fn value_at(&self, hex: HexId, prop: Prop, year: Year) -> Option<Value> {
        let i = hex.index();
        match prop {
            Prop::Terrain => self.terrain[i].at(year).map(Value::Terrain),
            Prop::Koeppen => self.koeppen[i].at(year).map(Value::Koeppen),
            Prop::Pop => self.pop[i].at(year).map(Value::Pop),
        }
    }

    /// The year of the keyframe of `prop` in effect at `year`.
    pub fn key_in_effect(&self, hex: HexId, prop: Prop, year: Year) -> Option<Year> {
        let i = hex.index();
        match prop {
            Prop::Terrain => self.terrain[i].key_in_effect(year),
            Prop::Koeppen => self.koeppen[i].key_in_effect(year),
            Prop::Pop => self.pop[i].key_in_effect(year),
        }
    }

    /// The value stored exactly at keyframe `key`.
    pub fn key_value(&self, hex: HexId, prop: Prop, key: Year) -> Option<Value> {
        let i = hex.index();
        match prop {
            Prop::Terrain => self.terrain[i].get_key(key).map(Value::Terrain),
            Prop::Koeppen => self.koeppen[i].get_key(key).map(Value::Koeppen),
            Prop::Pop => self.pop[i].get_key(key).map(Value::Pop),
        }
    }

    /// All keyframes of one property of one hex.
    pub fn keys(&self, hex: HexId, prop: Prop) -> Vec<(Year, Value)> {
        let i = hex.index();
        match prop {
            Prop::Terrain => self.terrain[i].keys().iter().map(|(y, v)| (*y, Value::Terrain(*v))).collect(),
            Prop::Koeppen => self.koeppen[i].keys().iter().map(|(y, v)| (*y, Value::Koeppen(*v))).collect(),
            Prop::Pop => self.pop[i].keys().iter().map(|(y, v)| (*y, Value::Pop(*v))).collect(),
        }
    }

    /// Sets (or inserts) a keyframe. Returns the previous value at that key.
    pub fn set_key(&mut self, hex: HexId, key: Year, value: Value) -> Option<Value> {
        let i = hex.index();
        match value {
            Value::Terrain(v) => self.terrain[i].set_key(key, v).map(Value::Terrain),
            Value::Koeppen(v) => self.koeppen[i].set_key(key, v).map(Value::Koeppen),
            Value::Pop(v) => self.pop[i].set_key(key, v).map(Value::Pop),
        }
    }

    /// Removes a keyframe. Returns its value if it existed.
    pub fn remove_key(&mut self, hex: HexId, prop: Prop, key: Year) -> Option<Value> {
        let i = hex.index();
        match prop {
            Prop::Terrain => self.terrain[i].remove_key(key).map(Value::Terrain),
            Prop::Koeppen => self.koeppen[i].remove_key(key).map(Value::Koeppen),
            Prop::Pop => self.pop[i].remove_key(key).map(Value::Pop),
        }
    }

    /// Expected population of a hex at `year`, from values on the map and
    /// no site data: hunter-gatherers at the density its productivity and
    /// distance to water support ([`forager::density`]); once farming has reached it
    /// ([`World::farming`]) and while its climate and rivers allow
    /// ([`farming::farmable`]), growing towards the farmers' ceiling for its
    /// latitude ([`farming::density`]). Nobody on Ice; `None` on Water and
    /// without productivity.
    pub fn expected_at(&self, hex: HexId, year: Year) -> Option<Expected> {
        self.expected_given(hex, year, self.shore_km(year)[hex.index()] as f64)
    }

    /// [`World::expected_at`] for every hex, working out the distances to
    /// water once.
    pub fn expected_field(&self, year: Year) -> Vec<Option<Expected>> {
        let shore = self.shore_km(year);
        self.grid.ids().map(|h| self.expected_given(h, year, shore[h.index()] as f64)).collect()
    }

    /// [`World::expected_at`] with the hex's distance to water supplied
    /// ([`World::shore_km`], or a snapshot's copy of it).
    pub fn expected_given(&self, hex: HexId, year: Year, shore_km: f64) -> Option<Expected> {
        let i = hex.index();
        match self.terrain[i].at(year) {
            Some(Terrain::Water) => return None,
            Some(Terrain::Ice) => return self.npp_at(hex, year).map(|_| Expected { density: 0.0, farmed: false }),
            _ => {}
        }
        let npp = self.npp_at(hex, year)?;
        let foragers = forager::density(npp, shore_km);
        let since = self.farming.get(i).copied().flatten().map(|a| year.0 - a.0).filter(|y| *y >= 0);
        let farmable = || {
            let river = RiverClass::from_u8(self.river[i].at(year).unwrap_or(0)).unwrap_or(RiverClass::None);
            self.koeppen[i].at(year).is_some_and(|k| farming::farmable(k, npp, river))
        };
        Some(match since {
            Some(years) if farmable() => {
                let ceiling = farming::CEILING * farming::latitude_factor(self.grid.centre(hex).lat);
                Expected { density: farming::density(foragers, ceiling, years as f64), farmed: true }
            }
            _ => Expected { density: foragers, farmed: false },
        })
    }

    /// Structural invariants; checked after loading a file.
    pub fn validate(&self) -> Result<(), String> {
        let n = self.grid.len();
        if n == 0 {
            return Err("grid is empty".into());
        }
        if !(self.grid.w > 0.0 && self.grid.h > 0.0) {
            return Err("grid cell size must be positive".into());
        }
        if self.terrain.len() != n
            || self.koeppen.len() != n
            || self.pop.len() != n
            || self.river.len() != n
            || self.elevation.len() != n
            || self.landform.len() != n
        {
            return Err(format!(
                "property arrays ({}, {}, {}, {}, {}, {}) do not match the grid ({n} hexes)",
                self.terrain.len(),
                self.koeppen.len(),
                self.pop.len(),
                self.river.len(),
                self.elevation.len(),
                self.landform.len()
            ));
        }
        for i in 0..n {
            if !(self.terrain[i].is_sorted() && self.koeppen[i].is_sorted() && self.pop[i].is_sorted()) {
                return Err(format!("hex {i}: keyframes are not sorted"));
            }
            if self.koeppen[i].keys().iter().any(|(_, k)| k.index() >= Koeppen::COUNT) {
                return Err(format!("hex {i}: Köppen index out of range"));
            }
            if !self.river[i].is_sorted() || self.river[i].keys().iter().any(|(_, c)| RiverClass::from_u8(*c).is_none()) {
                return Err(format!("hex {i}: river classes are unsorted or out of range"));
            }
        }
        for s in &self.settlements {
            if !s.population.is_sorted() {
                return Err(format!("settlement {}: population keys are not sorted", s.id));
            }
            if s.occupation.iter().any(|(a, b)| a >= b) || s.occupation.windows(2).any(|w| w[0].1 > w[1].0) {
                return Err(format!("settlement {}: occupation phases are empty, unsorted or overlap", s.id));
            }
        }
        if !self.farming.is_empty() && self.farming.len() != n {
            return Err(format!("farming layer has {} values for {n} hexes", self.farming.len()));
        }
        if !self.edge_sea.is_empty() && (self.edge_sea.len() != n || self.edge_sea.iter().any(|t| !t.is_sorted())) {
            return Err(format!("edge-sea layer has {} timelines for {n} hexes, or unsorted keys", self.edge_sea.len()));
        }
        if !self.massif.is_empty() && self.massif.len() != n {
            return Err(format!("massif layer has {} values for {n} hexes", self.massif.len()));
        }
        for (i, m) in self.massif.iter().enumerate() {
            if let Some(m) = m {
                m.validate().map_err(|e| format!("hex {i}: {e}"))?;
            }
        }
        if let Some(h) = &self.heightmap {
            h.validate()?;
        }
        if !self.npp.is_empty() && (self.npp.len() != n || self.npp.iter().any(|t| !t.is_sorted())) {
            return Err(format!("productivity layer has {} timelines for {n} hexes, or unsorted keys", self.npp.len()));
        }
        if !self.survey.is_empty() && (self.survey.len() != n || self.survey.iter().any(|v| *v > 2)) {
            return Err(format!("survey layer has {} values (0-2) for {n} hexes", self.survey.len()));
        }
        if self.settlements.iter().any(|s| s.importance > 3 || s.evidence > 2) {
            return Err("settlement importance must be 0-3 and evidence 0-2".into());
        }
        if !self.site_info.is_empty() && self.site_info.len() != self.settlements.len() {
            return Err(format!(
                "{} site records for {} settlements",
                self.site_info.len(),
                self.settlements.len()
            ));
        }
        if let Some(r) = &self.residuals {
            r.validate(n)?;
        }
        if let Some(a) = &self.ancestry {
            a.validate()?;
        }
        for (i, l) in self.evidence.iter().enumerate() {
            l.validate(n)?;
            if self.evidence[..i].iter().any(|o| o.id == l.id) {
                return Err(format!("evidence layer {} appears twice", l.id));
            }
        }
        for r in &self.rivers {
            if r.points.len() < 2 || !(1..=3).contains(&r.size) || !r.state.is_sorted() {
                return Err(format!("river {} ({}): needs 2+ points, size 1-3 and sorted keys", r.id, r.name));
            }
        }
        for l in &self.lakes {
            let bad_index = l.shape.keys().iter().any(|(_, i)| *i != crate::lake::NO_SHAPE && *i as usize >= l.shapes.len());
            if !l.shape.is_sorted() || bad_index {
                return Err(format!("lake {}: shape keys unsorted or out of range", l.key));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod ancestry_tests {
    use super::*;
    use crate::ancestry::{decode, Component, Sample, Status, COMPONENTS, NO_CODE};

    #[test]
    fn hex_codes_come_from_the_layers_and_thin_out_without_genomes() {
        let mut w = test_world(6, 5);
        let n = w.grid.len();
        assert!(!w.has_ancestry());
        assert!(w.ancestry_codes(Year(-6000)).iter().all(|c| *c == NO_CODE));
        let keys = ["whg", "ehg", "ana", "irn", "lev", "naf"];
        let here = w.grid.centre(HexId(0));
        let sample = |id: &str, year: i32| Sample {
            id: id.into(), group: "G".into(), locality: String::new(), pos: here, year: Year(year), sd: 50, snps: 500_000,
            status: Status::Fit, model: "whg+ana".into(), p_milli: Some(300), weights: vec![250, 0, 750, 0, 0, 0], publication: String::new(),
        };
        w.ancestry = Some(crate::ancestry::Ancestry {
            components: keys.iter().map(|k| Component { key: k.to_string(), name: k.to_string() }).collect(),
            samples: vec![sample("c", -6010), sample("a", -6000), sample("b", -6000)],
        });
        assert!(!w.has_ancestry(), "the layers are needed too");
        // One slice; hex 0: 25% whg, 75% ana (bins 12 and 37 of 50); hex 1: the same; the rest unknown.
        for (k, key) in keys.iter().enumerate() {
            let mut l = crate::evidence::test_layer(&format!("anc_{key}"), n);
            l.slices = vec![Year(-6000)];
            l.codes = vec![crate::evidence::NO_VALUE; n];
            for hex in [0, n - 1] {
                l.codes[hex] = match k { 0 => 12, 2 => 37, _ => 0 };
            }
            w.evidence.push(l);
        }
        assert_eq!(w.validate(), Ok(()));
        assert!(w.has_ancestry());
        let codes = w.ancestry_codes(Year(-6000));
        let (shares, thin) = decode(codes[0]).unwrap();
        assert_eq!(shares, [0.25, 0.0, 0.75, 0.0, 0.0, 0.0]);
        assert!(!thin, "three genomes of that date beside the hex");
        let (far, thin_far) = decode(codes[n - 1]).unwrap();
        assert_eq!(far, shares);
        assert!(thin_far, "no genome within reach of the far corner");
        assert!(codes[1..n - 1].iter().all(|c| *c == NO_CODE), "unsampled land stays unknown");
        let s = w.ancestry_shares(HexId(0), Year(-6000)).unwrap();
        assert!((s.iter().sum::<f32>() - 1.0).abs() < 1e-5 && s[2] > 0.7);
        assert_eq!(w.ancestry_shares(HexId(1), Year(-6000)), None);
        assert_eq!(COMPONENTS, keys.len());
    }
}

#[cfg(test)]
pub(crate) fn test_world(cols: u16, rows: u16) -> World {
    // A small deterministic world with two keyframes on every hex.
    let grid = GridSpec { cols, rows, origin_lon: 0.0, origin_lat: 50.0, w: 0.5773502691896262, h: 0.5 };
    let mut w = World::empty(grid);
    for id in w.grid.ids().collect::<Vec<_>>() {
        let (c, r) = w.grid.col_row(id);
        let land = (c / 3 + r / 3) % 2 == 0;
        let t0 = if land { Terrain::Plains } else { Terrain::Water };
        w.set_key(id, Year(-10000), Value::Terrain(t0));
        w.set_key(id, Year(-8000), Value::Terrain(if c < 2 { Terrain::Water } else { t0 }));
        w.set_key(id, Year(-10000), Value::Koeppen(Koeppen::new(if land { 15 } else { 0 }).unwrap()));
        w.set_key(id, Year(-10000), Value::Pop(PopDensity::P0_0));
        w.elevation[id.index()] = if land { 120 } else { -30 };
        w.landform[id.index()] = Some(if land && c % 4 == 0 { Landform::Mountains } else { Landform::Flat });
    }
    w.survey = (0..w.grid.len()).map(|i| (i % 3) as u8).collect();
    w.npp = (0..w.grid.len()).map(|i| Timeline::from_keys([(Year(-10000), 100), (Year(-8000), 100 + 60 * (i as u16 % 5))])).collect();
    w.farming = (0..w.grid.len()).map(|i| (i % 2 == 0).then_some(Year(-9000 + 100 * (i as i32 % 7)))).collect();
    w.rivers.push(River {
        id: 1,
        key: "test".into(),
        name: "Test River".into(),
        size: 2,
        points: vec![LonLat::new(0.5, 49.5), LonLat::new(1.5, 48.5), LonLat::new(2.0, 48.0)],
        state: Timeline::from_keys([(Year(-10000), crate::RiverState::Perennial), (Year(-8000), crate::RiverState::Absent)]),
    });
    w.river[0].set_key(Year(-10000), RiverClass::Major as u8);
    w.river[0].set_key(Year(-8000), RiverClass::None as u8);
    w.lakes.push(crate::lake::Lake {
        key: "test".into(),
        name: "Test Lake".into(),
        shapes: vec![crate::lake::LakeShape {
            level: 10.0,
            rings: vec![vec![LonLat::new(2.0, 48.0), LonLat::new(3.0, 48.0), LonLat::new(3.0, 49.0)]],
        }],
        shape: Timeline::from_keys([(Year(-10000), 0), (Year(-8000), crate::lake::NO_SHAPE)]),
    });
    w.settlements.push(Settlement {
        id: 1,
        name: "Testville".into(),
        pos: LonLat::new(1.0, 49.0),
        founded: Year(-9000),
        population: Timeline::from_keys([(Year(-9000), 100), (Year(-8900), 150)]),
        occupation: Vec::new(),
        importance: 2,
        evidence: 1,
    });
    w.site_info.push(SiteInfo {
        kind: "settlement".into(),
        abandoned: Some(Year(-8500)),
        culture: vec![(Year(-9000), "test_culture".into())],
        features: vec!["rock art".into()],
        wikipedia: Some("Testville".into()),
        dates: vec![C14Date { lab: "T-1".into(), bp: 9950, err: 40, cal: Year(-9000), dataset: "test".into() }],
        ..SiteInfo::default()
    });
    w.cultures.push(CultureInfo {
        id: "test_culture".into(),
        kind: "culture".into(),
        name: "Test culture".into(),
        wikipedia: Some("Test culture".into()),
    });
    let n = w.grid.len();
    w.evidence.push(crate::evidence::test_layer("test_layer", n));
    w.residuals = Some(crate::residuals::test_table(n));
    w
}

/// Gives `w`'s mountain hexes a massif sketch (a two-summit ridge).
#[cfg(test)]
pub(crate) fn add_test_massif(w: &mut World) {
    w.massif = (0..w.grid.len())
        .map(|i| {
            (w.landform[i] == Some(Landform::Mountains)).then(|| {
                Massif::new(MassifKind::Ridge, 30.0 * (i % 6) as f64, 0.5, 900.0, vec![Summit::new(0.2, -0.1, 1400.0), Summit::new(-0.4, 0.3, 600.0)])
            })
        })
        .collect();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snapshot_follows_keyframes_both_ways() {
        let w = test_world(8, 6);
        let hex = w.grid.id_at(0, 0);
        let early = w.snapshot(Year(-9000));
        let late = w.snapshot(Year(-7999));
        assert_eq!(early.value(Prop::Terrain, hex), Some(Value::Terrain(Terrain::Plains)));
        assert_eq!(late.value(Prop::Terrain, hex), Some(Value::Terrain(Terrain::Water)));
        // Scrubbing backwards is just another snapshot.
        assert_eq!(w.snapshot(Year(-9000)), early);
        // Before the first key there is no data.
        assert!(w.snapshot(Year(-10001)).terrain.iter().all(|v| *v == NO_DATA));
    }

    #[test]
    fn keyframe_years_are_sorted_unique() {
        let mut w = test_world(8, 6);
        assert_eq!(w.keyframe_years(), vec![Year(-10000), Year(-8000)]);
        w.set_key(HexId(5), Year(-8500), Value::Pop(PopDensity::P1_0));
        assert_eq!(w.keyframe_years(), vec![Year(-10000), Year(-8500), Year(-8000)]);
    }

    #[test]
    fn settlement_population() {
        let w = test_world(4, 4);
        let s = &w.settlements[0];
        assert!(!s.exists_at(Year(-9001)));
        assert!(s.exists_at(Year(-9000)));
        assert_eq!(s.population_at(Year(-8950)), Some(100));
        assert_eq!(s.population_at(Year(-5000)), Some(150));
        assert!(s.exists_at(Year(3000)), "no phases: never abandoned");
    }

    #[test]
    fn occupation_phases() {
        let mut s = test_world(4, 4).settlements.remove(0);
        s.founded = Year(-9500);
        s.occupation = vec![(Year(-9000), Year(-7000)), (Year(-5000), Year(-4000))];
        let at = |y| s.exists_at(Year(y));
        assert!(!at(-9600));
        assert!(at(-9500), "a founding before the first date counts");
        assert!(at(-7001) && !at(-7000), "phase end is exclusive");
        assert!(!at(-6000), "hiatus");
        assert!(at(-5000) && at(-4001));
        assert!(!at(-4000) && !at(0));
        assert_eq!(s.abandoned_by(), Some(Year(-4000)));
        assert_eq!(s.phase_at(Year(-9200)), Some((Year(-9500), Year(-7000))));
        assert_eq!(s.phase_at(Year(-4500)), Some((Year(-5000), Year(-4000))));
        assert_eq!(s.phase_at(Year(-6000)), None);
        // Occupied years: from the founding, gaps not counted.
        assert_eq!(s.occupied_years_by(Year(-9600)), 0);
        assert_eq!(s.occupied_years_by(Year(-9000)), 500);
        assert_eq!(s.occupied_years_by(Year(-6000)), 2500, "the hiatus adds nothing");
        assert_eq!(s.occupied_years_by(Year(-4500)), 3000);
        assert_eq!(s.occupied_years_by(Year(0)), 3500);
    }

    #[test]
    fn population_does_not_cross_gaps() {
        let mut s = test_world(4, 4).settlements.remove(0);
        s.occupation = vec![(Year(-9000), Year(-7000)), (Year(-5000), Year(-4000))];
        s.population = Timeline::from_keys([(Year(-9000), 100), (Year(-4500), 300)]);
        assert_eq!(s.population_at(Year(-7500)), Some(100));
        assert_eq!(s.population_at(Year(-6000)), None, "hiatus");
        assert_eq!(s.population_at(Year(-4800)), None, "phase 1's figure stays in phase 1");
        assert_eq!(s.population_at(Year(-4400)), Some(300));
        assert_eq!(s.population_at(Year(-3000)), None, "abandoned");
    }

    #[test]
    fn validate_catches_length_mismatch() {
        let mut w = test_world(4, 4);
        assert!(w.validate().is_ok());
        w.pop.pop();
        assert!(w.validate().is_err());
        let mut w = test_world(4, 4);
        w.rivers[0].points.truncate(1);
        assert!(w.validate().is_err());
    }

    #[test]
    fn elevation_band_follows_the_water() {
        let w = test_world(8, 6);
        // Hex (0, 0): land at 120 m until -8000, then Water (still 120 m: a lake band).
        let hex = w.grid.id_at(0, 0);
        assert_eq!(w.snapshot(Year(-9000)).elevation[hex.index()], elevation::band(120, false));
        assert_eq!(w.snapshot(Year(-7000)).elevation[hex.index()], elevation::band(120, true));
        assert!(elevation::is_water_band(w.snapshot(Year(-7000)).layer(MapMode::Elevation)[hex.index()]));
        let mut w = w;
        w.elevation[0] = NO_ELEVATION;
        assert_eq!(w.snapshot(Year(-9000)).elevation[0], NO_DATA);
    }

    #[test]
    fn shore_distance_is_to_the_edge_of_the_nearest_water() {
        let w = test_world(9, 7);
        let year = Year(-10000);
        let shore = w.shore_km(year);
        let water: Vec<HexId> = w.grid.ids().filter(|h| w.terrain[h.index()].at(year) == Some(Terrain::Water)).collect();
        assert!(!water.is_empty());
        let c = |h: HexId| [w.grid.centre(h).lon, w.grid.centre(h).lat];
        let hex_km = w.grid.h * 111.2;
        for h in w.grid.ids() {
            let nearest = water.iter().map(|x| crate::geom::great_circle_km(c(h), c(*x))).fold(f64::INFINITY, f64::min);
            let want = nearest - nearest.min(hex_km) / 2.0;
            // Spreading through neighbours can miss the true nearest by a fraction of a hex.
            assert!((shore[h.index()] as f64 - want).abs() <= 0.25 * hex_km, "hex {}: {} vs {want}", h.0, shore[h.index()]);
        }
        assert!(water.iter().all(|h| shore[h.index()] == 0.0));
        // Land beside water is about half a hex from its edge.
        let beside = w.grid.ids().find(|h| !water.contains(h) && w.grid.neighbours(*h).any(|n| water.contains(&n))).unwrap();
        assert!((10.0..35.0).contains(&shore[beside.index()]), "{}", shore[beside.index()]);
        // The field and the single-hex query agree; no Water at all means no bonus and no panic.
        let field = w.expected_field(year);
        assert!(w.grid.ids().all(|h| field[h.index()] == w.expected_at(h, year)));
        let snap = w.snapshot(year);
        assert!(w.grid.ids().all(|h| w.expected_given(h, year, snap.shore_km[h.index()] as f64) == field[h.index()]));
        assert!(shore.iter().all(|d| d.fract() == 0.0));
        let mut dry = w.clone();
        for h in water {
            dry.set_key(h, Year(-10000), Value::Terrain(Terrain::Plains));
            dry.set_key(h, Year(-8000), Value::Terrain(Terrain::Plains));
        }
        assert!(dry.shore_km(year).iter().all(|d| d.is_infinite()));
        assert!(dry.snapshot(year).shore_km.iter().all(|d| *d == u16::MAX));
        assert_eq!(dry.expected_given(HexId(0), year, u16::MAX as f64), dry.expected_at(HexId(0), year));
        assert!(dry.expected_at(HexId(0), year).is_some());
    }

    #[test]
    fn sea_beyond_the_map_edge_counts_as_shore() {
        let w = test_world(9, 7);
        let (early, late) = (Year(-10000), Year(-5000));
        let base = w.shore_km(early);
        // The land hex furthest from the map's own water.
        let far = w.grid.ids().filter(|h| base[h.index()] > 0.0).max_by(|a, b| base[a.index()].total_cmp(&base[b.index()])).unwrap();
        let water = w.grid.ids().find(|h| base[h.index()] == 0.0).unwrap();
        let mut e = w.clone();
        e.edge_sea = vec![Timeline::from_keys([(early, NO_EDGE_SEA)]); w.grid.len()];
        assert_eq!(e.shore_km(early), base, "no sea in reach changes nothing");
        assert_eq!(e.edge_sea_km(far, early), None);
        e.edge_sea[far.index()] = Timeline::from_keys([(early, 7), (late, NO_EDGE_SEA)]);
        e.edge_sea[water.index()] = Timeline::from_keys([(early, 7)]);
        let shore = e.shore_km(early);
        assert_eq!(shore[far.index()], 7.0);
        assert_eq!(shore[water.index()], 0.0, "Water stays 0");
        assert!(shore.iter().zip(&base).enumerate().all(|(i, (a, b))| i == far.index() || a == b));
        assert!(e.expected_at(far, early).unwrap().density > w.expected_at(far, early).unwrap().density);
        // It follows the year, and a nearer shore on the map still wins.
        assert_eq!(e.shore_km(late)[far.index()], w.shore_km(late)[far.index()]);
        e.edge_sea[far.index()] = Timeline::from_keys([(early, 60000)]);
        assert_eq!(e.shore_km(early)[far.index()], base[far.index()]);
        // A map with no Water of its own still has a shore.
        let mut dry = e.clone();
        for h in w.grid.ids().filter(|h| base[h.index()] == 0.0) {
            dry.set_key(h, early, Value::Terrain(Terrain::Plains));
        }
        dry.edge_sea[far.index()] = Timeline::from_keys([(early, 300)]);
        assert_eq!(dry.shore_km(early)[far.index()], 300.0);
        // The layer must match the grid.
        e.edge_sea.pop();
        assert!(e.validate().is_err());
    }

    #[test]
    fn expected_population_switches_to_farmers_when_farming_arrives_on_farmable_land() {
        let mut w = test_world(6, 5);
        // A land hex that stays land, with a farmable climate (test worlds use Köppen 15, Cfb).
        let hex = w.grid.ids().find(|h| w.terrain[h.index()].at(Year(-3000)) == Some(Terrain::Plains)).unwrap();
        let i = hex.index();
        assert!(farming::farmable(w.koeppen[i].at(Year(-9000)).unwrap(), 800, RiverClass::None));
        w.npp[i] = Timeline::from_keys([(Year(-10000), 800)]);
        w.farming[i] = Some(Year(-6000));
        let shore = |w: &World, y: i32| w.shore_km(Year(y))[i] as f64;
        let foragers = forager::density(800, shore(&w, -6001));
        assert_eq!(w.expected_at(hex, Year(-6001)), Some(Expected { density: foragers, farmed: false }));
        assert_eq!(w.expected_at(hex, Year(-6000)), Some(Expected { density: foragers, farmed: true }));
        let ceiling = farming::CEILING * farming::latitude_factor(w.grid.centre(hex).lat);
        let later = w.expected_at(hex, Year(-5000)).unwrap();
        assert!(later.farmed && (later.density - ceiling).abs() < 1e-3 * ceiling, "{later:?} vs {ceiling}");
        assert_eq!(w.snapshot(Year(-5000)).layer(MapMode::Expected)[i], farming::band(later.density));
        // Dry land without a river can't be farmed, so foragers stay; a river changes that.
        w.npp[i] = Timeline::from_keys([(Year(-10000), 100)]);
        let foragers = forager::density(100, shore(&w, -5000));
        assert_eq!(w.expected_at(hex, Year(-5000)), Some(Expected { density: foragers, farmed: false }));
        w.river[i].set_key(Year(-10000), RiverClass::Major as u8);
        assert!(w.expected_at(hex, Year(-5000)).unwrap().farmed);
        // Never reached: foragers. Ice: nobody. Water or no productivity: nothing to say.
        w.farming[i] = None;
        assert!(!w.expected_at(hex, Year(-3000)).unwrap().farmed);
        w.set_key(hex, Year(-4000), Value::Terrain(Terrain::Ice));
        assert_eq!(w.expected_at(hex, Year(-3500)), Some(Expected { density: 0.0, farmed: false }));
        w.set_key(hex, Year(-4000), Value::Terrain(Terrain::Water));
        assert_eq!(w.expected_at(hex, Year(-3500)), None);
        assert_eq!(w.snapshot(Year(-3500)).expected[i], NO_DATA);
        w.farming.clear();
        w.npp.clear();
        assert_eq!(w.expected_at(hex, Year(-9000)), None);
    }

    #[test]
    fn productivity_band_follows_the_year_and_the_water() {
        let mut w = test_world(6, 5);
        // Hex (0, 0) is land at first and Water from -8000; index 4 gains productivity then.
        let hex = w.grid.id_at(0, 0);
        assert_eq!(w.npp_at(hex, Year(-9000)), Some(100));
        assert_eq!(w.snapshot(Year(-9000)).npp[hex.index()], productivity::band(100));
        assert_eq!(w.snapshot(Year(-7000)).layer(MapMode::Npp)[hex.index()], NO_DATA);
        let land = w.grid.ids().find(|h| h.index() % 5 == 4 && w.terrain[h.index()].at(Year(-7000)) != Some(Terrain::Water)).unwrap();
        assert_eq!(w.snapshot(Year(-7000)).npp[land.index()], productivity::band(340));
        assert_eq!(
            w.snapshot(Year(-7000)).layer(MapMode::Biodiversity)[land.index()],
            forager::biodiversity_band(forager::biodiversity(340))
        );
        assert_eq!(w.snapshot(Year(-7000)).biodiversity[hex.index()], NO_DATA);
        assert_eq!(w.forager_density_at(land, Year(-7000)), Some(forager::density(340, w.shore_km(Year(-7000))[land.index()] as f64)));
        assert_eq!(w.forager_density_at(hex, Year(-7000)), None);
        w.set_key(land, Year(-7000), Value::Terrain(Terrain::Ice));
        assert_eq!(w.forager_density_at(land, Year(-7000)), None);
        assert_eq!(w.npp_at(land, Year(-10001)), None);
        w.npp.clear();
        assert!(w.snapshot(Year(-9000)).npp.iter().all(|b| *b == NO_DATA));
        assert_eq!(w.npp_at(hex, Year(-9000)), None);
    }

    #[test]
    fn surface_heights_put_lakes_at_their_level() {
        let w = test_world(8, 6);
        // test_world: land 120 m, water -30 m; the test lake (level 10 m)
        // covers the triangle (2,48)-(3,48)-(3,49) from -10000 to -8000.
        let h = w.snapshot(Year(-9000)).height;
        for id in w.grid.ids() {
            let i = id.index();
            let t = w.snapshot(Year(-9000)).terrain[i];
            if t == Terrain::Plains as u8 {
                assert_eq!(h[i], 120);
            } else {
                assert!(h[i] == 0 || h[i] == 10, "{} {}", i, h[i]);
            }
        }
        // After the lake is gone, all water is at sea level.
        assert!(w.snapshot(Year(-7000)).height.iter().all(|z| *z == 0 || *z == 120));
    }

    #[test]
    fn rivers_follow_their_state() {
        let w = test_world(8, 6);
        assert_eq!(w.snapshot(Year(-9000)).river(HexId(0)), RiverClass::Major);
        assert_eq!(w.snapshot(Year(-7000)).river(HexId(0)), RiverClass::None);
        assert_eq!(w.rivers[0].state_at(Year(-9000)), crate::RiverState::Perennial);
        assert_eq!(w.rivers[0].state_at(Year(-7000)), crate::RiverState::Absent);
    }
}
