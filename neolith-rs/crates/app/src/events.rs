//! The chronicle: a feed of events derived from the world file, the
//! biome changes at each keyframe and the founding, abandonment and
//! resettlement of settlements.

use crate::labels::{geo_labels, settlement_label, Kind};
use neolith_core::{GridSpec, HexId, LonLat, Terrain, World, Year};
use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EventKind {
    Founded,
    Abandoned,
    Biome,
    Sea,
}

impl EventKind {
    /// The dot drawn beside the event in the feed.
    pub fn colour(self) -> [u8; 3] {
        match self {
            EventKind::Founded => [214, 120, 64],
            EventKind::Abandoned => [150, 138, 124],
            EventKind::Biome => [120, 190, 90],
            EventKind::Sea => [90, 160, 230],
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            EventKind::Founded => "founded",
            EventKind::Abandoned => "abandoned",
            EventKind::Biome => "biome",
            EventKind::Sea => "sea",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Event {
    pub year: Year,
    pub kind: EventKind,
    pub text: String,
    /// Where to take the camera when the event is clicked.
    pub at: Option<LonLat>,
}

/// A change group must cover at least this many hexes to be reported.
const MIN_HEXES: usize = 15;
/// At most this many biome or sea events per keyframe.
const PER_KEYFRAME: usize = 4;

/// Every event in the world, in chronological order (stable within a year).
pub fn build(world: &World) -> Vec<Event> {
    let mut out = biome_events(world);
    out.extend(settlement_events(world));
    out.sort_by_key(|e| e.year);
    out
}

/// Terrain changes, read straight off each hex's keys: grouped by year and
/// (from, to), split into connected patches, and kept when big enough.
fn biome_events(world: &World) -> Vec<Event> {
    let grid = &world.grid;
    let mut changes: HashMap<(Year, Terrain, Terrain), Vec<HexId>> = HashMap::new();
    for id in grid.ids() {
        let keys = world.terrain[id.index()].keys();
        for w in keys.windows(2) {
            let ((_, from), (year, to)) = (w[0], w[1]);
            if from != to {
                changes.entry((year, from, to)).or_default().push(id);
            }
        }
    }
    let mut per_year: HashMap<Year, Vec<(usize, Event)>> = HashMap::new();
    for ((year, from, to), hexes) in changes {
        for patch in patches(grid, &hexes) {
            if patch.len() < MIN_HEXES {
                continue;
            }
            let at = patch_centre(grid, &patch);
            let place = place_name(at).map(|n| format!(" in {n}")).unwrap_or_default();
            let n = patch.len();
            let (kind, text) = match (from, to) {
                (_, Terrain::Water) => (EventKind::Sea, format!("The sea rose over {n} hexes of {}{place}", from.name())),
                (Terrain::Water, _) => (EventKind::Sea, format!("The sea fell back: {n} hexes of new {}{place}", to.name())),
                _ => (EventKind::Biome, format!("{} spread over {n} hexes of {}{place}", to.name(), from.name())),
            };
            per_year.entry(year).or_default().push((n, Event { year, kind, text, at: Some(at) }));
        }
    }
    let mut out = Vec::new();
    for (_, mut evs) in per_year {
        evs.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.text.cmp(&b.1.text)));
        out.extend(evs.into_iter().take(PER_KEYFRAME).map(|(_, e)| e));
    }
    out
}

/// One settlement change: (peak population, year, label, position).
type Change = (u32, Year, Option<String>, LonLat);

/// Foundings, resettlements after a gap and abandonments (each phase's
/// assumed end), each summarised per century.
fn settlement_events(world: &World) -> Vec<Event> {
    let first = world.keyframe_years().first().copied();
    let (mut founded, mut resettled, mut abandoned) = (Vec::new(), Vec::new(), Vec::new());
    for (i, st) in world.settlements.iter().enumerate() {
        // An inferred settlement is a guess, not an event in the record.
        if world.is_inferred(i) {
            continue;
        }
        let peak = st.population.keys().iter().map(|(_, n)| *n).max().unwrap_or(0);
        let change = |y: Year| (peak, y, settlement_label(&st.name), st.pos);
        // Places already there at the start are the setting, not news.
        if !first.is_some_and(|f| st.founded <= f) {
            founded.push(change(st.founded));
        }
        for (i, &(start, end)) in st.occupation.iter().enumerate() {
            if i > 0 {
                resettled.push(change(start));
            }
            abandoned.push(change(end));
        }
    }
    let mut out = per_century(founded, EventKind::Founded, "founded");
    out.extend(per_century(resettled, EventKind::Founded, "resettled"));
    out.extend(per_century(abandoned, EventKind::Abandoned, "abandoned"));
    out
}

/// Changes in each century: the biggest few by name, the rest as one
/// rolled-up line, so the feed isn't a catalogue dump.
fn per_century(changes: Vec<Change>, kind: EventKind, verb: &str) -> Vec<Event> {
    let mut by_century: HashMap<i32, Vec<Change>> = HashMap::new();
    for c in changes {
        by_century.entry(c.1 .0.div_euclid(100)).or_default().push(c);
    }
    let mut out = Vec::new();
    for (_, mut sts) in by_century {
        sts.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.2.cmp(&b.2)));
        let (mut named, mut rest) = (0, 0);
        let mut last = Year(i32::MIN);
        for (_, year, name, pos) in sts {
            last = last.max(year);
            match name {
                Some(name) if named < NAMED_PER_CENTURY => {
                    named += 1;
                    out.push(Event { year, kind, text: format!("{name} {verb}"), at: Some(pos) });
                }
                _ => rest += 1,
            }
        }
        if rest > 0 {
            let text = if rest == 1 { format!("1 more settlement {verb}") } else { format!("{rest} more settlements {verb}") };
            out.push(Event { year: last, kind, text, at: None });
        }
    }
    out
}

/// Settlements named in the feed per century, per kind of change.
const NAMED_PER_CENTURY: usize = 2;

/// Connected components of `hexes` on the grid.
fn patches(grid: &GridSpec, hexes: &[HexId]) -> Vec<Vec<HexId>> {
    let mut left: std::collections::HashSet<HexId> = hexes.iter().copied().collect();
    let mut out = Vec::new();
    for &start in hexes {
        if !left.remove(&start) {
            continue;
        }
        let mut patch = vec![start];
        let mut i = 0;
        while i < patch.len() {
            for n in grid.neighbours(patch[i]) {
                if left.remove(&n) {
                    patch.push(n);
                }
            }
            i += 1;
        }
        out.push(patch);
    }
    out
}

/// The member hex nearest the patch's mean position (so it lies in the patch).
fn patch_centre(grid: &GridSpec, patch: &[HexId]) -> LonLat {
    let n = patch.len() as f64;
    let (lon, lat) = patch.iter().fold((0.0, 0.0), |(a, b), h| {
        let c = grid.centre(*h);
        (a + c.lon, b + c.lat)
    });
    let (lon, lat) = (lon / n, lat / n);
    let d = |h: &HexId| {
        let c = grid.centre(*h);
        (c.lon - lon).powi(2) + (c.lat - lat).powi(2)
    };
    grid.centre(*patch.iter().min_by(|a, b| d(a).total_cmp(&d(b))).unwrap())
}

/// The nearest land region or range name within a few degrees.
fn place_name(at: LonLat) -> Option<&'static str> {
    geo_labels()
        .iter()
        .filter(|l| matches!(l.kind, Kind::Region | Kind::Mountains))
        .map(|l| {
            let m = l.path[1];
            (l, (m[0] - at.lon).powi(2) + (m[1] - at.lat).powi(2))
        })
        .filter(|(_, d)| *d < 8.0 * 8.0)
        .min_by(|a, b| a.1.total_cmp(&b.1))
        .map(|(l, _)| l.name.as_str())
}

/// Events in effect at `year`, newest first.
pub fn recent(events: &[Event], year: Year, n: usize) -> impl Iterator<Item = &Event> {
    let end = events.partition_point(|e| e.year <= year);
    events[..end].iter().rev().take(n)
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::{Settlement, Timeline, Value};

    fn world() -> World {
        let grid = GridSpec { cols: 10, rows: 10, origin_lon: 30.0, origin_lat: 40.0, w: 0.5773502691896262, h: 0.5 };
        let mut w = World::empty(grid);
        for id in w.grid.ids().collect::<Vec<_>>() {
            w.set_key(id, Year(-9000), Value::Terrain(Terrain::Grassland));
            // The western half turns to forest; one stray hex elsewhere too.
            let (c, _) = w.grid.col_row(id);
            if c < 5 || id.0 == 99 {
                w.set_key(id, Year(-8000), Value::Terrain(Terrain::TemperateForest));
            }
        }
        w
    }

    #[test]
    fn big_patches_become_events_and_strays_do_not() {
        let w = world();
        let ev = build(&w);
        let biome: Vec<_> = ev.iter().filter(|e| e.kind == EventKind::Biome).collect();
        assert_eq!(biome.len(), 1, "{ev:?}");
        assert_eq!(biome[0].year, Year(-8000));
        assert!(biome[0].text.starts_with("Temperate Forest spread over 50 hexes of Grassland"), "{}", biome[0].text);
    }

    #[test]
    fn foundings_and_recent_order() {
        let mut w = world();
        let s = |id, name: &str, y| Settlement {
            id,
            name: name.into(),
            pos: LonLat::new(31.0, 38.0),
            founded: Year(y),
            population: Timeline::new(),
            occupation: Vec::new(),
            importance: 1,
            evidence: 2,
        };
        w.settlements = vec![
            s(1, "Jericho", -8550),
            s(2, "WHS 1065", -8540),
            s(3, "Ain Ghazal", -8530),
            s(4, "Beidha", -8520),
            s(5, "Old", -9500),
        ];
        w.settlements[3].population = Timeline::from_keys([(Year(-8000), 400)]);
        w.settlements[0].population = Timeline::from_keys([(Year(-8000), 2000)]);
        let ev = build(&w);
        assert!(ev.windows(2).all(|p| p[0].year <= p[1].year));
        let texts: Vec<&str> = recent(&ev, Year(-8200), 10).map(|e| e.text.as_str()).collect();
        // The two biggest are named; the unnamed and the smaller are rolled up.
        assert!(texts.contains(&"Jericho founded"), "{texts:?}");
        assert!(texts.contains(&"Beidha founded"), "{texts:?}");
        assert!(texts.contains(&"2 more settlements founded"), "{texts:?}");
        assert!(!texts.iter().any(|t| t.contains("Old")));
        assert!(!texts.iter().any(|t| t.contains("Forest")));
    }

    #[test]
    fn abandonments_and_resettlements() {
        let mut w = world();
        w.settlements = vec![Settlement {
            id: 1,
            name: "Jericho".into(),
            pos: LonLat::new(31.0, 38.0),
            founded: Year(-8550),
            population: Timeline::new(),
            occupation: vec![(Year(-8550), Year(-7000)), (Year(-6000), Year(-5000))],
            importance: 1,
            evidence: 2,
        }];
        let ev = build(&w);
        let at = |y| ev.iter().filter(|e| e.year == Year(y)).map(|e| (e.kind, e.text.as_str())).collect::<Vec<_>>();
        assert_eq!(at(-8550), [(EventKind::Founded, "Jericho founded")]);
        assert_eq!(at(-7000), [(EventKind::Abandoned, "Jericho abandoned")]);
        assert_eq!(at(-6000), [(EventKind::Founded, "Jericho resettled")]);
        assert_eq!(at(-5000), [(EventKind::Abandoned, "Jericho abandoned")]);
    }
}
