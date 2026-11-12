//! The hex grid. It is a perfect rectangle of flat-topped hexes in lon/lat
//! degrees, so geometry, adjacency and hit-testing are all arithmetic on
//! `(col, row)`; nothing is stored per hex.
//!
//! Layout (matches the QGIS grid the data came from):
//! - ids run down each column from the north, column by column from the west:
//!   `index = col * rows + row`;
//! - odd columns are shifted half a hex south ("odd-q" offset layout).

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct LonLat {
    pub lon: f64,
    pub lat: f64,
}

impl LonLat {
    pub const fn new(lon: f64, lat: f64) -> Self {
        Self { lon, lat }
    }
}

/// 0-based hex index (= old GeoJSON id − 1).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct HexId(pub u32);

impl HexId {
    pub fn index(self) -> usize {
        self.0 as usize
    }

    /// The 1-based id used in the GeoJSON files.
    pub fn geojson_id(self) -> u32 {
        self.0 + 1
    }

    pub fn from_geojson_id(id: u32) -> Option<Self> {
        id.checked_sub(1).map(HexId)
    }
}

/// Neighbour offsets `(dcol, drow)` per edge, for even and odd columns.
/// Edge `k` lies between corner `k` and corner `k + 1`, where corner `k` is at
/// angle `60°·k` counter-clockwise from east. So the edges face, in order:
/// NE, N, NW, SW, S, SE. Rows increase southwards. The board shader mirrors
/// this table.
pub const NEIGHBOUR_OFFSETS: [[(i32, i32); 6]; 2] = [
    [(1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1), (1, 0)],
    [(1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1), (1, 1)],
];

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GridSpec {
    pub cols: u16,
    pub rows: u16,
    /// West edge of column 0.
    pub origin_lon: f64,
    /// North edge of row 0 in an even column.
    pub origin_lat: f64,
    /// Hex width (corner to corner) in degrees of longitude.
    pub w: f64,
    /// Hex height (edge to edge) in degrees of latitude.
    pub h: f64,
}

impl GridSpec {
    pub fn len(&self) -> usize {
        self.cols as usize * self.rows as usize
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn ids(&self) -> impl Iterator<Item = HexId> {
        (0..self.len() as u32).map(HexId)
    }

    pub fn id_at(&self, col: u16, row: u16) -> HexId {
        debug_assert!(col < self.cols && row < self.rows);
        HexId(col as u32 * self.rows as u32 + row as u32)
    }

    pub fn col_row(&self, id: HexId) -> (u16, u16) {
        ((id.0 / self.rows as u32) as u16, (id.0 % self.rows as u32) as u16)
    }

    fn centre_cr(&self, col: i64, row: i64) -> LonLat {
        let shift = if col.rem_euclid(2) == 1 { self.h / 2.0 } else { 0.0 };
        LonLat {
            lon: self.origin_lon + self.w / 2.0 + col as f64 * 0.75 * self.w,
            lat: self.origin_lat - self.h / 2.0 - row as f64 * self.h - shift,
        }
    }

    pub fn centre(&self, id: HexId) -> LonLat {
        let (c, r) = self.col_row(id);
        self.centre_cr(c as i64, r as i64)
    }

    /// The 6 corners, counter-clockwise starting from the east corner
    /// (corner `k` is at angle `60°·k`).
    pub fn corners(&self, id: HexId) -> [LonLat; 6] {
        let c = self.centre(id);
        let (hw, qw, hh) = (self.w / 2.0, self.w / 4.0, self.h / 2.0);
        [
            LonLat::new(c.lon + hw, c.lat),
            LonLat::new(c.lon + qw, c.lat + hh),
            LonLat::new(c.lon - qw, c.lat + hh),
            LonLat::new(c.lon - hw, c.lat),
            LonLat::new(c.lon - qw, c.lat - hh),
            LonLat::new(c.lon + qw, c.lat - hh),
        ]
    }

    /// The polygon in the vertex order of the source GeoJSON: west corner,
    /// then clockwise (NW, NE, E, SE, SW).
    pub fn polygon(&self, id: HexId) -> [LonLat; 6] {
        let c = self.corners(id);
        [c[3], c[2], c[1], c[0], c[5], c[4]]
    }

    /// The neighbour across edge `edge` (0..6, see [`NEIGHBOUR_OFFSETS`]).
    pub fn neighbour(&self, id: HexId, edge: usize) -> Option<HexId> {
        let (c, r) = self.col_row(id);
        let (dc, dr) = NEIGHBOUR_OFFSETS[(c % 2) as usize][edge];
        let (nc, nr) = (c as i32 + dc, r as i32 + dr);
        (nc >= 0 && nr >= 0 && nc < self.cols as i32 && nr < self.rows as i32)
            .then(|| self.id_at(nc as u16, nr as u16))
    }

    pub fn neighbours(&self, id: HexId) -> impl Iterator<Item = HexId> + '_ {
        (0..6).filter_map(move |e| self.neighbour(id, e))
    }

    /// Every `(hex, edge)` on the outside of the grid (no neighbour across it).
    /// These are where the board's side walls go.
    pub fn outside_edges(&self) -> Vec<(HexId, u8)> {
        let mut out = Vec::new();
        for id in self.ids() {
            for e in 0..6 {
                if self.neighbour(id, e).is_none() {
                    out.push((id, e as u8));
                }
            }
        }
        out
    }

    /// Hit test: the hex containing `p`, or `None` outside the grid.
    pub fn hex_at(&self, p: LonLat) -> Option<HexId> {
        if !(p.lon.is_finite() && p.lat.is_finite()) || self.is_empty() {
            return None;
        }
        // Candidate column from the centre spacing, then the nearest centre
        // among it and its neighbours. In (lon/(w/2), lat/(h/2)·(√3/2)) space
        // the hexes are regular, so the hex containing p is the one with the
        // nearest centre.
        let fc = (p.lon - self.origin_lon - self.w / 2.0) / (0.75 * self.w);
        if !(-2.0..=self.cols as f64 + 1.0).contains(&fc) {
            return None;
        }
        let c0 = fc.round() as i64;
        let sy = (3f64.sqrt() / 2.0) * self.w / self.h;
        let mut best: Option<(f64, i64, i64)> = None;
        for c in (c0 - 1)..=(c0 + 1) {
            let shift = if c.rem_euclid(2) == 1 { self.h / 2.0 } else { 0.0 };
            let fr = (self.origin_lat - self.h / 2.0 - shift - p.lat) / self.h;
            if !(-2.0..=self.rows as f64 + 1.0).contains(&fr) {
                continue;
            }
            let r0 = fr.round() as i64;
            for r in (r0 - 1)..=(r0 + 1) {
                let ctr = self.centre_cr(c, r);
                let (dx, dy) = (p.lon - ctr.lon, (p.lat - ctr.lat) * sy);
                let d = dx * dx + dy * dy;
                if best.is_none_or(|(bd, _, _)| d < bd) {
                    best = Some((d, c, r));
                }
            }
        }
        let (_, c, r) = best?;
        (c >= 0 && r >= 0 && c < self.cols as i64 && r < self.rows as i64)
            .then(|| self.id_at(c as u16, r as u16))
    }

    /// `(west, south, east, north)` bounds of all hex polygons.
    pub fn bounds(&self) -> (f64, f64, f64, f64) {
        let east = self.origin_lon + self.w + (self.cols.max(1) - 1) as f64 * 0.75 * self.w;
        let shift = if self.cols > 1 { self.h / 2.0 } else { 0.0 };
        let south = self.origin_lat - self.rows as f64 * self.h - shift;
        (self.origin_lon, south, east, self.origin_lat)
    }

    /// Centre of the bounds.
    pub fn centre_of_bounds(&self) -> LonLat {
        let (w, s, e, n) = self.bounds();
        LonLat::new((w + e) / 2.0, (s + n) / 2.0)
    }
}

#[cfg(test)]
pub(crate) fn test_grid() -> GridSpec {
    // The real grid's parameters.
    GridSpec {
        cols: 190,
        rows: 139,
        origin_lon: -16.464168425,
        origin_lat: 75.858035103,
        w: 0.5773502691896262,
        h: 0.5,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_layout() {
        let g = test_grid();
        assert_eq!(g.len(), 26_410);
        assert_eq!(g.col_row(HexId(0)), (0, 0));
        assert_eq!(g.col_row(HexId(138)), (0, 138));
        assert_eq!(g.col_row(HexId(139)), (1, 0));
        for id in g.ids() {
            let (c, r) = g.col_row(id);
            assert_eq!(g.id_at(c, r), id);
        }
    }

    #[test]
    fn polygon_matches_source_data() {
        // First two columns' first hexes, copied from combined_map.geojson.
        let g = test_grid();
        let expect0 = [
            (-16.464168425, 75.608035103),
            (-16.319830857702595, 75.858035103),
            (-16.03115572310778, 75.858035103),
            (-15.886818155810374, 75.608035103),
            (-16.03115572310778, 75.358035103),
            (-16.319830857702595, 75.358035103),
        ];
        let expect139 = [
            (-16.03115572310778, 75.358035103),
            (-15.886818155810374, 75.608035103),
            (-15.598143021215561, 75.608035103),
            (-15.453805453918156, 75.358035103),
            (-15.598143021215561, 75.108035103),
            (-15.886818155810374, 75.108035103),
        ];
        for (id, expect) in [(HexId(0), expect0), (HexId(139), expect139)] {
            for (p, e) in g.polygon(id).iter().zip(expect) {
                assert!((p.lon - e.0).abs() < 1e-9 && (p.lat - e.1).abs() < 1e-9, "{p:?} vs {e:?}");
            }
        }
    }

    #[test]
    fn hex_at_centre_is_identity() {
        let g = test_grid();
        for id in g.ids() {
            assert_eq!(g.hex_at(g.centre(id)), Some(id));
        }
    }

    #[test]
    fn hex_at_inside_points_near_corners() {
        let g = test_grid();
        for id in g.ids().step_by(37) {
            let c = g.centre(id);
            for corner in g.corners(id) {
                // 98% of the way to each corner is still inside this hex.
                let p = LonLat::new(c.lon + (corner.lon - c.lon) * 0.98, c.lat + (corner.lat - c.lat) * 0.98);
                assert_eq!(g.hex_at(p), Some(id));
            }
        }
    }

    #[test]
    fn hex_at_outside_is_none() {
        let g = test_grid();
        let (w, s, e, n) = g.bounds();
        for p in [
            LonLat::new(w - 0.01, 40.0),
            LonLat::new(e + 0.01, 40.0),
            LonLat::new(20.0, n + 0.01),
            LonLat::new(20.0, s - 0.01),
            LonLat::new(-170.0, -80.0),
            LonLat::new(f64::NAN, 0.0),
        ] {
            assert_eq!(g.hex_at(p), None, "{p:?}");
        }
        // The notch above an odd column's first hex is outside the grid.
        let c = g.centre(g.id_at(1, 0));
        assert_eq!(g.hex_at(LonLat::new(c.lon, c.lat + g.h * 0.75)), None);
    }

    #[test]
    fn neighbours_are_geometrically_adjacent_and_symmetric() {
        let g = test_grid();
        // In the regularised metric adjacent centres are exactly √3/2·w apart.
        let sy = (3f64.sqrt() / 2.0) * g.w / g.h;
        let step = 3f64.sqrt() / 2.0 * g.w;
        let mut interior = 0;
        for id in g.ids() {
            let c = g.centre(id);
            let ns: Vec<HexId> = g.neighbours(id).collect();
            if ns.len() == 6 {
                interior += 1;
            }
            for n in &ns {
                let nc = g.centre(*n);
                let d = ((nc.lon - c.lon).powi(2) + ((nc.lat - c.lat) * sy).powi(2)).sqrt();
                assert!((d - step).abs() < 1e-9, "{id:?} -> {n:?}: {d}");
                assert!(g.neighbours(*n).any(|b| b == id));
            }
        }
        assert_eq!(interior, 188 * 137);
    }

    #[test]
    fn edge_k_faces_its_neighbour() {
        // The neighbour across edge k lies in the direction of that edge's
        // midpoint (so the shader's border lookup agrees with the geometry).
        let g = test_grid();
        for id in [g.id_at(10, 10), g.id_at(11, 10)] {
            let c = g.centre(id);
            let corners = g.corners(id);
            for e in 0..6 {
                let n = g.centre(g.neighbour(id, e).unwrap());
                let (a, b) = (corners[e], corners[(e + 1) % 6]);
                let mid = LonLat::new((a.lon + b.lon) / 2.0, (a.lat + b.lat) / 2.0);
                assert!((c.lon + 2.0 * (mid.lon - c.lon) - n.lon).abs() < 1e-9);
                assert!((c.lat + 2.0 * (mid.lat - c.lat) - n.lat).abs() < 1e-9);
            }
        }
    }

    #[test]
    fn outside_edges_count() {
        let g = test_grid();
        let edges = g.outside_edges();
        // Every outside edge belongs to a boundary hex.
        for (id, _) in &edges {
            let (c, r) = g.col_row(*id);
            assert!(c == 0 || r == 0 || c == g.cols - 1 || r == g.rows - 1);
        }
        // N and S edges of the top and bottom rows (190 each), the slanted
        // top edges of even columns and bottom edges of odd columns (190 each),
        // and the west/east columns' two slanted edges per hex (278 each),
        // less the two corner edges counted twice.
        assert_eq!(edges.len(), 4 * 190 + 2 * 278 - 2);
    }

    #[test]
    fn bounds_match_data() {
        let g = test_grid();
        let (w, s, e, n) = g.bounds();
        assert!((w - -16.464168425).abs() < 1e-9);
        assert!((n - 75.858035103).abs() < 1e-9);
        assert!((e - 65.95258250181912).abs() < 1e-9);
        assert!((s - 6.108035103).abs() < 1e-9);
    }
}
