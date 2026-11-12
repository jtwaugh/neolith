//! The editing model: typed edits grouped into commands, exact undo/redo,
//! and the tools (pencil, fill, lasso) as pure functions that *return* a
//! [`Command`] instead of touching the world.

use crate::geom::point_in_polygon;
use crate::grid::{GridSpec, HexId, LonLat};
use crate::time::Year;
use crate::values::{Prop, Value};
use crate::world::World;

/// Which keyframe an edit at the current year changes.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum KeyMode {
    /// Change the keyframe in effect at the current year (at −7500 that is
    /// the −8000 key). If no keyframe is in effect yet, one is created at the
    /// current year.
    #[default]
    InEffect,
    /// Insert (or overwrite) a keyframe exactly at the current year.
    InsertAtYear,
}

/// One keyframe change on one hex. `before` is the value previously stored
/// *at that key* (`None`: the key did not exist and reverting removes it).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Edit {
    pub hex: HexId,
    pub key: Year,
    pub before: Option<Value>,
    pub after: Value,
}

impl Edit {
    pub fn prop(&self) -> Prop {
        self.after.prop()
    }
}

/// One user action (a stroke, a fill, ...): the unit of undo.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Command {
    pub label: &'static str,
    pub edits: Vec<Edit>,
}

impl Command {
    pub fn new(label: &'static str) -> Self {
        Self { label, edits: Vec::new() }
    }

    pub fn is_empty(&self) -> bool {
        self.edits.is_empty()
    }

    pub fn apply(&self, world: &mut World) {
        for e in &self.edits {
            world.set_key(e.hex, e.key, e.after);
        }
    }

    /// Exact inverse of [`Command::apply`].
    pub fn revert(&self, world: &mut World) {
        for e in self.edits.iter().rev() {
            match e.before {
                Some(v) => {
                    world.set_key(e.hex, e.key, v);
                }
                None => {
                    world.remove_key(e.hex, e.prop(), e.key);
                }
            }
        }
    }

    /// True if any edit adds a keyframe year that did not exist on that hex
    /// (the set of keyframe years may have changed).
    pub fn inserts_keys(&self) -> bool {
        self.edits.iter().any(|e| e.before.is_none())
    }
}

#[derive(Default, Debug)]
pub struct History {
    undo: Vec<Command>,
    redo: Vec<Command>,
}

impl History {
    /// Applies `cmd` and records it. Empty commands are ignored.
    pub fn apply(&mut self, world: &mut World, cmd: Command) {
        if cmd.is_empty() {
            return;
        }
        cmd.apply(world);
        self.push_applied(cmd);
    }

    /// Records a command whose edits are *already applied* to the world (a
    /// drag stroke applied hex by hex for live feedback).
    pub fn push_applied(&mut self, cmd: Command) {
        if cmd.is_empty() {
            return;
        }
        self.undo.push(cmd);
        self.redo.clear();
    }

    /// Undoes the last command. Returns it (for dirty tracking) if there was one.
    pub fn undo(&mut self, world: &mut World) -> Option<&Command> {
        let cmd = self.undo.pop()?;
        cmd.revert(world);
        self.redo.push(cmd);
        self.redo.last()
    }

    pub fn redo(&mut self, world: &mut World) -> Option<&Command> {
        let cmd = self.redo.pop()?;
        cmd.apply(world);
        self.undo.push(cmd);
        self.undo.last()
    }

    pub fn can_undo(&self) -> bool {
        !self.undo.is_empty()
    }

    pub fn can_redo(&self) -> bool {
        !self.redo.is_empty()
    }

    pub fn undo_label(&self) -> Option<&'static str> {
        self.undo.last().map(|c| c.label)
    }

    pub fn redo_label(&self) -> Option<&'static str> {
        self.redo.last().map(|c| c.label)
    }

    pub fn clear(&mut self) {
        self.undo.clear();
        self.redo.clear();
    }
}

/// A set of hexes (bitset).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Selection {
    bits: Vec<u64>,
    len: usize,
}

impl Selection {
    pub fn new(len: usize) -> Self {
        Self { bits: vec![0; len.div_ceil(64)], len }
    }

    pub fn all(len: usize) -> Self {
        let mut s = Self::new(len);
        s.select_all();
        s
    }

    pub fn capacity(&self) -> usize {
        self.len
    }

    pub fn contains(&self, id: HexId) -> bool {
        let i = id.index();
        i < self.len && self.bits[i / 64] & (1 << (i % 64)) != 0
    }

    /// Returns true if the hex was newly inserted.
    pub fn insert(&mut self, id: HexId) -> bool {
        let i = id.index();
        if i >= self.len || self.contains(id) {
            return false;
        }
        self.bits[i / 64] |= 1 << (i % 64);
        true
    }

    pub fn remove(&mut self, id: HexId) {
        let i = id.index();
        if i < self.len {
            self.bits[i / 64] &= !(1 << (i % 64));
        }
    }

    pub fn clear(&mut self) {
        self.bits.iter_mut().for_each(|b| *b = 0);
    }

    pub fn select_all(&mut self) {
        self.bits.iter_mut().for_each(|b| *b = u64::MAX);
        let tail = self.len % 64;
        if tail != 0 {
            *self.bits.last_mut().unwrap() = (1u64 << tail) - 1;
        }
    }

    pub fn union_with(&mut self, other: &Selection) {
        for (a, b) in self.bits.iter_mut().zip(&other.bits) {
            *a |= *b;
        }
    }

    pub fn subtract(&mut self, other: &Selection) {
        for (a, b) in self.bits.iter_mut().zip(&other.bits) {
            *a &= !*b;
        }
    }

    pub fn count(&self) -> usize {
        self.bits.iter().map(|b| b.count_ones() as usize).sum()
    }

    pub fn is_empty(&self) -> bool {
        self.bits.iter().all(|b| *b == 0)
    }

    pub fn iter(&self) -> impl Iterator<Item = HexId> + '_ {
        self.bits.iter().enumerate().flat_map(|(w, bits)| {
            let mut b = *bits;
            std::iter::from_fn(move || {
                if b == 0 {
                    return None;
                }
                let i = b.trailing_zeros();
                b &= b - 1;
                Some(HexId((w * 64) as u32 + i))
            })
        })
    }
}

fn edit_for(world: &World, hex: HexId, value: Value, year: Year, mode: KeyMode) -> Option<Edit> {
    let prop = value.prop();
    if world.value_at(hex, prop, year) == Some(value) {
        return None; // already that value: nothing to do
    }
    let key = match mode {
        KeyMode::InEffect => world.key_in_effect(hex, prop, year).unwrap_or(year),
        KeyMode::InsertAtYear => year,
    };
    Some(Edit { hex, key, before: world.key_value(hex, prop, key), after: value })
}

/// Paints `value` (which implies the property) onto every hex in `hexes` at
/// `year`. Hexes that already have the value produce no edit; duplicates in
/// `hexes` are edited once.
pub fn pencil(
    world: &World,
    hexes: impl IntoIterator<Item = HexId>,
    value: Value,
    year: Year,
    mode: KeyMode,
) -> Command {
    let mut seen = Selection::new(world.grid.len());
    let mut cmd = Command::new("Pencil");
    for hex in hexes {
        if hex.index() < world.grid.len() && seen.insert(hex) {
            cmd.edits.extend(edit_for(world, hex, value, year, mode));
        }
    }
    cmd
}

/// Flood fill: paints `value` onto the connected region of hexes sharing the
/// start hex's value (of `value`'s property, at `year`). Returns an empty
/// command when the start hex already has `value`.
pub fn fill(world: &World, start: HexId, value: Value, year: Year, mode: KeyMode) -> Command {
    let mut cmd = Command::new("Fill");
    let prop = value.prop();
    if start.index() >= world.grid.len() {
        return cmd;
    }
    let target = world.value_at(start, prop, year);
    if target == Some(value) {
        return cmd;
    }
    let mut visited = Selection::new(world.grid.len());
    let mut queue = std::collections::VecDeque::from([start]);
    visited.insert(start);
    while let Some(hex) = queue.pop_front() {
        cmd.edits.extend(edit_for(world, hex, value, year, mode));
        for n in world.grid.neighbours(hex) {
            if world.value_at(n, prop, year) == target && visited.insert(n) {
                queue.push_back(n);
            }
        }
    }
    cmd
}

/// Selects every hex whose centre lies inside the lon/lat polygon.
pub fn lasso(grid: &GridSpec, polygon: &[LonLat]) -> Selection {
    let poly: Vec<[f64; 2]> = polygon.iter().map(|p| [p.lon, p.lat]).collect();
    let mut sel = Selection::new(grid.len());
    for id in grid.ids() {
        let c = grid.centre(id);
        if point_in_polygon(&poly, [c.lon, c.lat]) {
            sel.insert(id);
        }
    }
    sel
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::values::{Koeppen, PopDensity, Terrain};
    use crate::world::test_world;
    use proptest::prelude::*;

    const Y: Year = Year(-7500);

    #[test]
    fn pencil_edits_key_in_effect() {
        let mut w = test_world(8, 6);
        let hex = w.grid.id_at(4, 4);
        let v = Value::Terrain(Terrain::Ice);
        let cmd = pencil(&w, [hex, hex], v, Y, KeyMode::InEffect);
        assert_eq!(cmd.edits.len(), 1);
        assert_eq!(cmd.edits[0].key, Year(-8000));
        assert!(cmd.edits[0].before.is_some());
        cmd.apply(&mut w);
        assert_eq!(w.value_at(hex, Prop::Terrain, Y), Some(v));
        assert_eq!(w.value_at(hex, Prop::Terrain, Year(-8001)), Some(Value::Terrain(Terrain::Plains)));
        // Painting the same value again is a no-op.
        assert!(pencil(&w, [hex], v, Y, KeyMode::InEffect).is_empty());
    }

    #[test]
    fn pencil_insert_mode_creates_key_and_undo_removes_it() {
        let mut w = test_world(8, 6);
        let before = w.clone();
        let hex = w.grid.id_at(4, 4);
        let v = Value::Terrain(Terrain::Ice);
        let mut h = History::default();
        let cmd = pencil(&w, [hex], v, Y, KeyMode::InsertAtYear);
        assert_eq!(cmd.edits[0], Edit { hex, key: Y, before: None, after: v });
        assert!(cmd.inserts_keys());
        h.apply(&mut w, cmd);
        assert_eq!(w.keys(hex, Prop::Terrain).len(), 3);
        assert_eq!(w.value_at(hex, Prop::Terrain, Year(-7501)), Some(Value::Terrain(Terrain::Plains)));
        h.undo(&mut w);
        assert_eq!(w, before);
    }

    #[test]
    fn edit_before_first_key_creates_key_at_year() {
        let w = test_world(4, 4);
        let cmd = pencil(&w, [HexId(0)], Value::Pop(PopDensity::P2_0), Year(-12000), KeyMode::InEffect);
        assert_eq!(cmd.edits[0].key, Year(-12000));
        assert_eq!(cmd.edits[0].before, None);
    }

    #[test]
    fn fill_same_value_is_noop() {
        let w = test_world(12, 9);
        let hex = w.grid.id_at(4, 4);
        let current = w.value_at(hex, Prop::Terrain, Y).unwrap();
        assert!(fill(&w, hex, current, Y, KeyMode::InEffect).is_empty());
    }

    #[test]
    fn fill_covers_exactly_the_connected_region() {
        let mut w = test_world(12, 9);
        let start = w.grid.id_at(4, 4);
        let target = w.value_at(start, Prop::Terrain, Y);
        // Reference flood fill.
        let mut region = vec![start];
        let mut i = 0;
        while i < region.len() {
            for n in w.grid.neighbours(region[i]).collect::<Vec<_>>() {
                if w.value_at(n, Prop::Terrain, Y) == target && !region.contains(&n) {
                    region.push(n);
                }
            }
            i += 1;
        }
        let v = Value::Terrain(Terrain::Mountains);
        let cmd = fill(&w, start, v, Y, KeyMode::InEffect);
        let mut edited: Vec<HexId> = cmd.edits.iter().map(|e| e.hex).collect();
        edited.sort();
        region.sort();
        assert_eq!(edited, region);
        assert!(region.len() > 1 && region.len() < w.grid.len());
        cmd.apply(&mut w);
        assert!(region.iter().all(|h| w.value_at(*h, Prop::Terrain, Y) == Some(v)));
    }

    #[test]
    fn fill_whole_uniform_world_terminates() {
        let w = test_world(30, 30);
        // Pop is uniformly P0_0.
        let cmd = fill(&w, HexId(0), Value::Pop(PopDensity::P5_0), Y, KeyMode::InEffect);
        assert_eq!(cmd.edits.len(), 900);
    }

    #[test]
    fn selection_ops() {
        let mut s = Selection::new(130);
        assert!(s.is_empty());
        assert!(s.insert(HexId(0)));
        assert!(s.insert(HexId(129)));
        assert!(!s.insert(HexId(129)));
        assert!(!s.insert(HexId(130)));
        assert_eq!(s.iter().collect::<Vec<_>>(), vec![HexId(0), HexId(129)]);
        s.select_all();
        assert_eq!(s.count(), 130);
        s.remove(HexId(64));
        assert_eq!(s.count(), 129);
        assert!(!s.contains(HexId(64)));
        s.clear();
        assert_eq!(s.count(), 0);
        assert_eq!(Selection::all(64).count(), 64);
    }

    #[test]
    fn lasso_selects_centres_inside() {
        let w = test_world(12, 9);
        let g = &w.grid;
        let (west, south, east, north) = g.bounds();
        let all = lasso(g, &[
            LonLat::new(west - 1.0, south - 1.0),
            LonLat::new(east + 1.0, south - 1.0),
            LonLat::new(east + 1.0, north + 1.0),
            LonLat::new(west - 1.0, north + 1.0),
        ]);
        assert_eq!(all.count(), g.len());
        let c = g.centre(g.id_at(5, 5));
        let one = lasso(g, &[
            LonLat::new(c.lon - 0.1, c.lat - 0.1),
            LonLat::new(c.lon + 0.1, c.lat - 0.1),
            LonLat::new(c.lon, c.lat + 0.1),
        ]);
        assert_eq!(one.iter().collect::<Vec<_>>(), vec![g.id_at(5, 5)]);
    }

    fn arb_value() -> impl Strategy<Value = Value> {
        prop_oneof![
            (0u8..17).prop_map(|v| Value::Terrain(Terrain::from_u8(v).unwrap())),
            (0u8..31).prop_map(|v| Value::Koeppen(Koeppen::new(v).unwrap())),
            (0u8..9).prop_map(|v| Value::Pop(PopDensity::from_u8(v).unwrap())),
        ]
    }

    #[derive(Clone, Debug)]
    enum Op {
        Pencil(Vec<u32>, Value, i32, bool),
        Fill(u32, Value, i32, bool),
        Undo,
        Redo,
    }

    fn arb_op() -> impl Strategy<Value = Op> {
        let year = -11000i32..-6000;
        prop_oneof![
            3 => (prop::collection::vec(0u32..48, 1..8), arb_value(), year.clone(), any::<bool>())
                .prop_map(|(h, v, y, m)| Op::Pencil(h, v, y, m)),
            2 => (0u32..48, arb_value(), year, any::<bool>()).prop_map(|(h, v, y, m)| Op::Fill(h, v, y, m)),
            2 => Just(Op::Undo),
            1 => Just(Op::Redo),
        ]
    }

    proptest! {
        /// Undo/redo round-trips exactly: after any sequence of tool commands
        /// and undo/redo, undoing everything restores the original world, and
        /// redoing everything restores the final one.
        #[test]
        fn undo_redo_round_trips(ops in prop::collection::vec(arb_op(), 1..40)) {
            let original = test_world(8, 6);
            let mut w = original.clone();
            let mut h = History::default();
            for op in ops {
                let mode = |m| if m { KeyMode::InsertAtYear } else { KeyMode::InEffect };
                match op {
                    Op::Pencil(hexes, v, y, m) => {
                        let cmd = pencil(&w, hexes.into_iter().map(HexId), v, Year(y), mode(m));
                        h.apply(&mut w, cmd);
                    }
                    Op::Fill(hex, v, y, m) => {
                        let cmd = fill(&w, HexId(hex), v, Year(y), mode(m));
                        h.apply(&mut w, cmd);
                    }
                    Op::Undo => { h.undo(&mut w); }
                    Op::Redo => { h.redo(&mut w); }
                }
                prop_assert!(w.validate().is_ok());
            }
            let fin = w.clone();
            let mut undone = 0;
            while h.undo(&mut w).is_some() { undone += 1; }
            prop_assert_eq!(&w, &original);
            for _ in 0..undone { h.redo(&mut w); }
            prop_assert_eq!(&w, &fin);
        }
    }
}
