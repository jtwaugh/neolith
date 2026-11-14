//! Where the settlement pieces stand, for display: a site whose recorded
//! point falls in a drawn river or lake is moved onto the bank, a site
//! beside water turns to face it (its huts lined up along the bank, a canoe
//! drawn up), stilt villages go out over the water, and neighbours are
//! nudged apart so they don't overlap close up. Never the record: a
//! [`Piece`] keeps `pos` and is drawn at `at` ([`Piece::at`]).
//!
//! Distances are worked out at the pieces' closest-in size
//! ([`scene::near_radius`]) and the rivers' close-up width, where the
//! arrangement shows; further out pieces are bigger than the offsets.

use super::lines;
use super::scene::{self, Piece, Shape};
use glam::DVec2;
use neolith_core::{GridSpec, Lake, LonLat, River, Terrain, Year};
use std::collections::HashMap;

/// Side of a cell of the segment index, degrees.
const CELL: f64 = 0.25;
/// How far past its bank a piece still counts as beside the water, in
/// piece radii.
const REACH: f64 = 4.0;
/// Pieces are kept this many (summed) radii apart.
const SPACING: f64 = 1.15;
const RELAX_ROUNDS: usize = 3;

/// One straight stretch of shoreline or river centreline, in degrees.
#[derive(Clone, Copy, Debug)]
struct Segment {
    a: LonLat,
    b: LonLat,
    /// For a river: its close-up half width (degrees) out to the edge of
    /// its bed; 0 for a lake shore.
    half: f64,
    /// Index into [`Waters::lakes`] for a lake shore.
    lake: Option<usize>,
}

/// The water at one year: river centrelines as drawn, and lake shores,
/// indexed by cell.
#[derive(Default)]
pub struct Waters {
    segments: Vec<Segment>,
    cells: HashMap<(i32, i32), Vec<u32>>,
    lakes: Vec<neolith_core::LakeShape>,
}

fn cell_of(p: LonLat) -> (i32, i32) {
    ((p.lon / CELL).floor() as i32, (p.lat / CELL).floor() as i32)
}

impl Waters {
    /// The rivers that are `flowing` ([`lines::flowing`]) and the lakes at
    /// `year`.
    pub fn new(rivers: &[River], flowing: &[Option<bool>], lakes: &[Lake], year: Year) -> Self {
        let mut w = Waters::default();
        for (r, _) in rivers.iter().zip(flowing).filter(|(_, f)| f.is_some()) {
            let half_deg = lines::half_width(r.size).to_degrees();
            let (pts, _) = lines::centreline(&r.points, half_deg, half_deg * 0.9);
            let half = half_deg * lines::BED_SHARE;
            for s in pts.windows(2) {
                w.push(Segment {
                    a: s[0],
                    b: s[1],
                    half,
                    lake: None,
                });
            }
        }
        for lake in lakes {
            let Some(shape) = lake.shape_at(year) else {
                continue;
            };
            let li = w.lakes.len();
            w.lakes.push(shape.clone());
            for ring in &shape.rings {
                for k in 0..ring.len() {
                    w.push(Segment {
                        a: ring[k],
                        b: ring[(k + 1) % ring.len()],
                        half: 0.0,
                        lake: Some(li),
                    });
                }
            }
        }
        w
    }

    fn push(&mut self, s: Segment) {
        let id = self.segments.len() as u32;
        let (c0, c1) = (
            cell_of(LonLat::new(s.a.lon.min(s.b.lon), s.a.lat.min(s.b.lat))),
            cell_of(LonLat::new(s.a.lon.max(s.b.lon), s.a.lat.max(s.b.lat))),
        );
        // A long lake edge may span many cells; that's fine, they are few.
        for i in c0.0..=c1.0 {
            for j in c0.1..=c1.1 {
                self.cells.entry((i, j)).or_default().push(id);
            }
        }
        self.segments.push(s);
    }

    /// The nearest stretch of water to `p` within `reach` degrees past
    /// its edge: (segment, offset from `p` to the nearest point on it, in
    /// ground degrees (east scaled by cos lat, north), and the distance to
    /// the water's edge (negative inside it)).
    fn nearest(&self, p: LonLat, reach: f64) -> Option<(Segment, DVec2, f64)> {
        let k = p.lat.to_radians().cos().max(0.05);
        let ground = |q: LonLat| DVec2::new((q.lon - p.lon) * k, q.lat - p.lat);
        let span = (reach / CELL).ceil() as i32 + 1;
        let (ci, cj) = cell_of(p);
        let mut best: Option<(Segment, DVec2, f64)> = None;
        for i in ci - span..=ci + span {
            for j in cj - span..=cj + span {
                for &id in self.cells.get(&(i, j)).map_or(&[][..], |v| &v[..]) {
                    let s = self.segments[id as usize];
                    let (a, b) = (ground(s.a), ground(s.b));
                    let ab = b - a;
                    let t = if ab.length_squared() > 0.0 {
                        (-a).dot(ab) / ab.length_squared()
                    } else {
                        0.0
                    };
                    let off = a + ab * t.clamp(0.0, 1.0);
                    let edge = off.length() - s.half;
                    if edge < reach && best.as_ref().is_none_or(|b| edge < b.2) {
                        best = Some((s, off, edge));
                    }
                }
            }
        }
        best
    }

    fn in_lake(&self, li: usize, p: LonLat) -> bool {
        self.lakes[li].contains(p)
    }
}

/// Moves a point by `d` ground degrees (east scaled by cos lat, north).
fn shift(p: LonLat, d: DVec2) -> LonLat {
    LonLat::new(
        p.lon + d.x / p.lat.to_radians().cos().max(0.05),
        p.lat + d.y,
    )
}

/// A stable pseudo-random sign for a site, for the side of a river it goes
/// to when it stands exactly on the centreline.
fn side_of(p: LonLat) -> f64 {
    if ((p.lon * 91.7 + p.lat * 37.3).sin() * 1e4).fract() >= 0.0 {
        1.0
    } else {
        -1.0
    }
}

/// Sets each piece's `at` and `water`: onto the bank (or for stilts, just
/// out over the water), facing the water, then apart from its neighbours;
/// beside the sea (a Water hex next door) it faces the sea.
pub fn place(pieces: &mut [Piece], waters: &Waters, grid: &GridSpec, terrain: &[u8]) {
    for p in pieces.iter_mut() {
        p.at = p.pos;
        p.water = None;
        settle(p, waters, grid, terrain);
    }
    relax(pieces);
    // The nudge apart may have pushed a piece back into the water.
    for p in pieces.iter_mut() {
        settle(p, waters, grid, terrain);
    }
}

fn settle(p: &mut Piece, waters: &Waters, grid: &GridSpec, terrain: &[u8]) {
    let r = scene::near_radius(p.size_tier()).to_degrees();
    let seeks = p.shape.seeks_water();
    let stilts = p.shape == Shape::Stilts;
    if let Some((seg, off, edge)) = waters.nearest(p.at, r * REACH) {
        let len = off.length();
        let to_water = if len > 1e-12 {
            off / len
        } else {
            DVec2::new(0.0, side_of(p.pos))
        };
        let inside = match seg.lake {
            Some(li) => waters.in_lake(li, p.at),
            None => edge < 0.0,
        };
        // In a lake the nearest shore point lies away from the water.
        let toward = if seg.lake.is_some() && inside {
            -to_water
        } else {
            to_water
        };
        // Where the piece's centre should stand, measured from the water's
        // edge (positive on land).
        let want = if stilts { -r * 0.8 } else { r * 1.4 };
        let now = if inside { -edge.abs() } else { edge.abs() };
        if now < want || (stilts && now > want) || (seeks && now > want) {
            // Move along the line to the water by (now - want): onto the bank, out
            // over it (stilts), or up to it (sites that seek water and are in reach).
            p.at = shift(p.at, toward * (now - want));
        }
        if seeks || now < r * REACH {
            p.water = Some([toward.x, toward.y]);
        }
        return;
    }
    // The sea: a Water hex beside the site's own.
    if !seeks {
        return;
    }
    let Some(home) = grid.hex_at(p.at) else {
        return;
    };
    let water = |id: neolith_core::HexId| terrain.get(id.index()) == Some(&(Terrain::Water as u8));
    let k = p.at.lat.to_radians().cos().max(0.05);
    let sum: DVec2 = grid
        .neighbours(home)
        .filter(|&n| water(n))
        .map(|n| {
            let c = grid.centre(n);
            DVec2::new((c.lon - p.at.lon) * k, c.lat - p.at.lat).normalize_or_zero()
        })
        .sum();
    if sum.length() > 1e-6 {
        let d = sum.normalize();
        p.water = Some([d.x, d.y]);
    }
}

/// Pushes overlapping pieces apart (a few rounds of pairwise repulsion on
/// a grid), at their close-up sizes.
fn relax(pieces: &mut [Piece]) {
    let radius: Vec<f64> = pieces
        .iter()
        .map(|p| scene::near_radius(p.size_tier()).to_degrees())
        .collect();
    let cell = radius.iter().cloned().fold(1e-6, f64::max) * SPACING * 2.0;
    for _ in 0..RELAX_ROUNDS {
        let ground = |p: LonLat| DVec2::new(p.lon * p.lat.to_radians().cos().max(0.05), p.lat);
        let mut grid: HashMap<(i64, i64), Vec<usize>> = HashMap::new();
        for (i, p) in pieces.iter().enumerate() {
            let g = ground(p.at);
            grid.entry(((g.x / cell).floor() as i64, (g.y / cell).floor() as i64))
                .or_default()
                .push(i);
        }
        let mut push = vec![DVec2::ZERO; pieces.len()];
        for (i, p) in pieces.iter().enumerate() {
            let g = ground(p.at);
            let (ci, cj) = ((g.x / cell).floor() as i64, (g.y / cell).floor() as i64);
            for di in -1..=1 {
                for dj in -1..=1 {
                    for &j in grid.get(&(ci + di, cj + dj)).map_or(&[][..], |v| &v[..]) {
                        if j <= i {
                            continue;
                        }
                        let d = ground(pieces[j].at) - g;
                        let min = (radius[i] + radius[j]) * SPACING;
                        let len = d.length();
                        if len >= min {
                            continue;
                        }
                        // Coincident: split along a stable direction.
                        let dir = if len > 1e-12 {
                            d / len
                        } else {
                            DVec2::from_angle(i as f64 * 2.399)
                        };
                        let gap = (min - len) * 0.5;
                        push[i] -= dir * gap;
                        push[j] += dir * gap;
                    }
                }
            }
        }
        for (p, d) in pieces.iter_mut().zip(push) {
            if d != DVec2::ZERO {
                p.at = shift(p.at, d);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::{RiverState, Timeline};

    fn river() -> River {
        River {
            id: 0,
            key: "r".into(),
            name: "R".into(),
            size: 2,
            points: (0..=20)
                .map(|i| LonLat::new(10.0 + i as f64 * 0.1, 45.0))
                .collect(),
            state: Timeline::from_keys([(Year(-10000), RiverState::Perennial)]),
        }
    }

    fn grid() -> GridSpec {
        GridSpec {
            cols: 40,
            rows: 40,
            origin_lon: 5.0,
            origin_lat: 50.0,
            w: 0.5773502691896262,
            h: 0.5,
        }
    }

    fn piece(lon: f64, lat: f64, shape: Shape) -> Piece {
        let s = neolith_core::Settlement {
            id: 0,
            name: "s".into(),
            pos: LonLat::new(lon, lat),
            founded: Year(-6000),
            population: Timeline::default(),
            occupation: Vec::new(),
            importance: 1,
            evidence: 2,
        };
        Piece {
            shape,
            ..Piece::new(&s, Year(-5000))
        }
    }

    fn waters() -> Waters {
        let r = [river()];
        Waters::new(&r, &lines::flowing(&r, Year(-5000)), &[], Year(-5000))
    }

    #[test]
    fn a_site_in_the_river_is_moved_onto_the_bank_facing_the_water() {
        let w = waters();
        let mut ps = vec![
            piece(11.0, 45.0, Shape::Hamlet),
            piece(11.5, 45.003, Shape::Camp),
        ];
        place(&mut ps, &w, &grid(), &[]);
        for p in &ps {
            let (_, off, edge) = w.nearest(p.at, 1.0).unwrap();
            let r = scene::near_radius(0).to_degrees();
            assert!(
                edge > r * 0.9,
                "piece still in the river: edge {edge}, radius {r}"
            );
            let [e, n] = p.water.expect("faces the water");
            assert!(DVec2::new(e, n).dot(off.normalize()) > 0.9);
        }
        // The one north of the centreline went north.
        assert!(ps[1].at.lat > 45.0);
    }

    #[test]
    fn stilts_stand_out_over_the_water() {
        let w = waters();
        let mut ps = vec![piece(11.0, 45.2, Shape::Stilts)];
        place(&mut ps, &w, &grid(), &[]);
        // Too far to reach: stays put.
        assert_eq!(ps[0].at, ps[0].pos);
        let mut ps = vec![piece(11.0, 45.06, Shape::Stilts)];
        place(&mut ps, &w, &grid(), &[]);
        assert!(
            w.nearest(ps[0].at, 1.0).unwrap().2 < 0.0,
            "stilts are over the water"
        );
    }

    #[test]
    fn inland_sites_stay_put_and_coincident_ones_part() {
        let w = Waters::default();
        let mut ps = vec![
            piece(20.0, 40.0, Shape::Hamlet),
            piece(20.0, 40.0, Shape::Hamlet),
            piece(25.0, 40.0, Shape::Monument),
        ];
        place(&mut ps, &w, &grid(), &[]);
        assert_eq!(ps[2].at, ps[2].pos);
        assert!(ps[2].water.is_none());
        let k = 40f64.to_radians().cos();
        let d = DVec2::new(
            (ps[0].at.lon - ps[1].at.lon) * k,
            ps[0].at.lat - ps[1].at.lat,
        )
        .length();
        assert!(d > scene::near_radius(0).to_degrees() * 1.5, "apart by {d}");
    }
}
