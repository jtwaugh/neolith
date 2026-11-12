use crate::grid::{GridSpec, HexId, LonLat};
use crate::lake::Lake;
use crate::river::{River, RiverClass};
use crate::time::Year;
use crate::timeline::Timeline;
use crate::elevation::{self, NO_ELEVATION};
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
}

impl Settlement {
    pub fn exists_at(&self, year: Year) -> bool {
        self.founded <= year
    }

    /// Population at `year`: the latest population key at or before it.
    pub fn population_at(&self, year: Year) -> Option<u32> {
        self.population.at(year)
    }
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

    /// What the board shows in `mode`, one byte per hex.
    pub fn layer(&self, mode: MapMode) -> &[u8] {
        match mode.prop() {
            Some(p) => self.get(p),
            None => &self.elevation,
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
        }
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
        Snapshot {
            year,
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
    });
    w
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
