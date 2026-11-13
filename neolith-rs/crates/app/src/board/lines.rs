//! Line overlays on the board: rivers, the channel belts of their alluvial
//! floodplain reaches, as ribbons for the renderer's line pipeline.
//!
//! A river is drawn in three steps. Its course is splined, resampled evenly
//! and smoothed until no bend is tighter than the line is wide (a ribbon
//! folds over itself on a tighter one). The ribbon is then laid out in
//! lon/lat, so it follows the board in both projections, with round caps and
//! per-point width and opacity, and painted twice: wide and dark for the
//! banks, narrower for the water. The fragment shader does the soft edges and dashes.
//!
//! Courses are fixed over a run: what changes with the year is a river's
//! state. A change cross-fades over [`FADE_YEARS`] instead of popping, and
//! on Floodplain hexes a wide pale belt under the channel shows the strip
//! the river moved within, without claiming where it ran in a given year.

use super::projection::Projection;
use super::relief::Relief;
use super::renderer::{LineMesh, LineVertex};
use super::scene::river_spline;
use glam::{DVec2, DVec3};
use neolith_core::{GridSpec, Lake, LonLat, River, RiverState, Snapshot, Terrain, Year};

/// Years a river takes to fade in, out or between states after a state key.
pub const FADE_YEARS: f64 = 120.0;

/// Half widths (radians) per river size, close up.
const HALF_WIDTH: [f64; 3] = [0.00032, 0.00048, 0.00068];
/// Half width (radians) of a channel belt, close up.
const BELT_HALF: f64 = 0.0038;
/// A headwater starts at this fraction of the river's width and reaches full
/// width over this many degrees.
const TAPER_FROM: f64 = 0.4;
const TAPER_DEG: f64 = 1.2;
/// Dash period (degrees) and "on" fraction of a seasonal river.
const DASH_PERIOD: f64 = 0.36;
const DASH_ON: f64 = 0.6;
/// How far (degrees) a river fades over before Water hexes, and a belt
/// before the end of the floodplain.
const WATER_FADE_DEG: f64 = 0.10;
const BELT_FADE_DEG: f64 = 0.30;
/// The shortest floodplain reach (degrees) that gets a belt.
const BELT_MIN_DEG: f64 = 1.2;

/// Fill and bank colours. The banks are a wider, darker line under the
/// fill, drawn for every river before any fill, so where rivers meet the
/// water runs together and only the outer banks show.
const PERENNIAL: [[u8; 3]; 2] = [[0x4c, 0x9a, 0xe8], [0x1e, 0x4f, 0x94]];
const SEASONAL: [[u8; 3]; 2] = [[0x9a, 0xcb, 0xee], [0x4d, 0x7d, 0xb3]];
/// The fill's share of the line's width, close up and from far out. Close
/// up the dark line is only a waterline: the bed (below) does the banks.
const FILL: [f64; 2] = [0.78, 0.37];
/// The bed a channel lies in, close up: wet mud and sand past the water's
/// edge, feathered into the ground. Perennial, then seasonal (a dry wash,
/// drawn whole under the dashed water). [`BED_SHARE`] is its share of the
/// line's width; the terrain art keeps trees off it (see [`river_field`]).
const BED: [[u8; 3]; 2] = [[0x9a, 0x86, 0x58], [0xc6, 0xb4, 0x86]];
pub const BED_SHARE: f64 = 1.8;
/// A pale streak down the middle of the water, close up.
const GLINT: [u8; 3] = [0xc4, 0xe4, 0xfb];
const BELT: [u8; 3] = [0xd6, 0xea, 0xc0];

/// How far a line is drawn from the map: the world width grows a little with
/// camera distance (like pieces) so lines stay visible zoomed out.
fn line_zoom(cam_dist: f64) -> f64 {
    const DIST_REF: f64 = 0.48;
    const ZOOM_EXP: f64 = 0.6;
    (cam_dist / DIST_REF).max(1.0).powf(ZOOM_EXP)
}

/// What the builders need to place a line on the board.
pub struct Board<'a> {
    pub proj: &'a Projection,
    pub relief: &'a Relief,
    /// Morph: 0 curved, 1 flat.
    pub t: f64,
    pub cam_dist: f64,
}

/// What of a river to draw at `year`: up to two (state, opacity) phases, the
/// outgoing state fading out as the incoming one fades in. The state in
/// effect at `run_start` is there from the beginning, so it doesn't fade in.
pub fn phases(river: &River, year: Year, run_start: Year) -> Vec<(RiverState, f64)> {
    let keys = river.state.keys();
    let idx = keys.partition_point(|(k, _)| *k <= year);
    if idx == 0 {
        return Vec::new();
    }
    let (key, cur) = keys[idx - 1];
    let prev = if idx >= 2 { keys[idx - 2].1 } else { RiverState::Absent };
    let x = ((year.0 - key.0) as f64 / FADE_YEARS).clamp(0.0, 1.0);
    let f = if key <= run_start { 1.0 } else { x * x * (3.0 - 2.0 * x) };
    if prev == cur || f >= 1.0 {
        return if cur == RiverState::Absent { Vec::new() } else { vec![(cur, 1.0)] };
    }
    [(prev, 1.0 - f), (cur, f)].into_iter().filter(|(s, a)| *s != RiverState::Absent && *a > 0.0).collect()
}

/// Points every `step` degrees along `pts` (ends kept).
fn resample(pts: &[LonLat], step: f64) -> Vec<LonLat> {
    let mut out = vec![pts[0]];
    let mut need = step;
    for w in pts.windows(2) {
        let (a, b) = (DVec2::new(w[0].lon, w[0].lat), DVec2::new(w[1].lon, w[1].lat));
        let len = a.distance(b);
        let mut at = 0.0;
        while len - at >= need {
            at += need;
            let p = a.lerp(b, at / len);
            out.push(LonLat::new(p.x, p.y));
            need = step;
        }
        need -= len - at;
    }
    let last = pts[pts.len() - 1];
    // The end replaces a sample that landed almost on it.
    if need > step * 0.5 && out.len() > 1 {
        out.pop();
    }
    out.push(last);
    out
}

/// Gaussian-like smoothing of an evenly sampled line (`step` degrees apart)
/// to about `sigma` degrees, ends fixed: bends tighter than that go.
fn smooth(pts: &mut [LonLat], sigma: f64, step: f64) {
    let n = pts.len();
    if n < 3 {
        return;
    }
    // Each [1 2 1]/4 pass adds step²/2 of variance.
    let passes = (2.0 * (sigma / step).powi(2)).ceil().clamp(0.0, 60.0) as usize;
    let mut next = pts.to_vec();
    for _ in 0..passes {
        for i in 1..n - 1 {
            next[i] = LonLat::new(
                (pts[i - 1].lon + 2.0 * pts[i].lon + pts[i + 1].lon) * 0.25,
                (pts[i - 1].lat + 2.0 * pts[i].lat + pts[i + 1].lat) * 0.25,
            );
        }
        pts.copy_from_slice(&next);
    }
}

/// A river course ready to stroke at `half_deg` half width: splined, evenly
/// sampled, with no wiggle the line is too wide to show. Returns the points
/// and their spacing.
fn centreline(points: &[LonLat], half_deg: f64, sigma: f64) -> (Vec<LonLat>, f64) {
    let step = (half_deg * 0.7).clamp(0.02, 0.08);
    let mut pts = resample(&river_spline(points, 0.04), step);
    smooth(&mut pts, sigma, step);
    (pts, step)
}

/// Box blur with the ends held (so a value at the end of the line stays).
fn blur(v: &[f64], radius: usize) -> Vec<f64> {
    if radius == 0 || v.is_empty() {
        return v.to_vec();
    }
    let n = v.len() as isize;
    let r = radius as isize;
    let at = |i: isize| v[i.clamp(0, n - 1) as usize];
    let mut sum: f64 = (-r..=r).map(at).sum();
    let mut out = Vec::with_capacity(v.len());
    for i in 0..n {
        out.push(sum / (2 * r + 1) as f64);
        sum += at(i + r + 1) - at(i - r);
    }
    out
}

/// How a ribbon is painted.
struct Paint {
    /// Share of the spine's width.
    share: f64,
    colour: [u8; 3],
    /// Dash "on" fraction; `None` = solid.
    dash: Option<f64>,
    /// Edge feather, as a fraction of the half width.
    feather: f64,
    profile: Profile,
}

/// How the fragment shader shapes a ribbon across its width (`fs_line`).
#[derive(Clone, Copy, PartialEq)]
enum Profile {
    /// One flat colour.
    Plain = 0,
    /// A river bed: banks sloping to the water and lit as slopes, wet and
    /// dark at the water's edge, drier and ragged at the outer edge.
    Bed = 1,
    /// A river's water: paler shallows by the banks, streaks along the flow.
    Water = 2,
}

fn unit(v: f64) -> u8 {
    (v.clamp(0.0, 1.0) * 255.0).round() as u8
}

/// A line placed on the board: per point, the centre and the vector to its
/// right edge in world space. Built once, painted any number of times (a
/// river's banks and its water share one).
struct Spine {
    centre: Vec<DVec3>,
    side: Vec<DVec3>,
    /// Distance along the line, in dash periods.
    along: Vec<f32>,
    /// World vectors out past the first and last point, a half width long;
    /// `None` for a closed line.
    caps: Option<[DVec3; 2]>,
}

impl Spine {
    /// `half`: half width in radians of arc, scaled per point by `width`;
    /// `lift`: height above the tiles, board units.
    fn new(pts: &[LonLat], width: &[f64], half: f64, lift: f64, closed: bool, board: &Board) -> Self {
        let n = pts.len();
        let half_deg = half.to_degrees();
        // Local metric: a degree of longitude is cos(lat) of a degree of latitude.
        let metric = |p: LonLat, d: DVec2| DVec2::new(d.x * p.lat.to_radians().cos(), d.y);
        let unmetric = |p: LonLat, d: DVec2| DVec2::new(d.x / p.lat.to_radians().cos().max(0.05), d.y);
        let diff = |a: LonLat, b: LonLat| DVec2::new(b.lon - a.lon, b.lat - a.lat);
        let shift = |p: LonLat, d: DVec2| LonLat::new(p.lon + d.x, p.lat + d.y);
        let nb = |i: usize, d: isize| -> usize {
            if closed {
                // The last point of a closed line repeats the first.
                ((i as isize + d).rem_euclid(n as isize - 1)) as usize
            } else {
                (i as isize + d).clamp(0, n as isize - 1) as usize
            }
        };

        let mut dirs = Vec::with_capacity(n);
        let mut left = Vec::with_capacity(n);
        let mut right = Vec::with_capacity(n);
        let mut along = Vec::with_capacity(n);
        let mut dist = 0.0;
        for i in 0..n {
            let dir = metric(pts[i], diff(pts[nb(i, -1)], pts[nb(i, 1)])).normalize_or_zero();
            let side = unmetric(pts[i], dir.perp()) * (half_deg * width[i]);
            dirs.push(dir);
            left.push(shift(pts[i], side));
            right.push(shift(pts[i], -side));
            if i > 0 {
                dist += metric(pts[i], diff(pts[i - 1], pts[i])).length();
            }
            along.push((dist / DASH_PERIOD) as f32);
        }
        // Inside a bend tighter than the line is wide the edge would run
        // backwards; hold it at the pivot instead.
        for i in 1..n {
            let fwd = diff(pts[i - 1], pts[i]);
            for edge in [&mut left, &mut right] {
                if diff(edge[i - 1], edge[i]).dot(fwd) < 0.0 {
                    edge[i] = edge[i - 1];
                }
            }
        }
        // Each cross-section sits on the highest tile under it or its
        // neighbours, so a line crossing a step stays on top of the higher tile.
        let tops: Vec<f64> = if board.relief.is_flat() {
            vec![0.0; n]
        } else {
            let own: Vec<f64> = (0..n)
                .map(|i| board.relief.at(pts[i]).max(board.relief.at(left[i])).max(board.relief.at(right[i])))
                .collect();
            (0..n).map(|i| own[nb(i, -1)].max(own[i]).max(own[nb(i, 1)])).collect()
        };
        let place = |p: LonLat, i: usize| board.proj.surface_at(p, board.t, tops[i] + lift);
        let mut centre = Vec::with_capacity(n);
        let mut side = Vec::with_capacity(n);
        for i in 0..n {
            let (l, r) = (place(left[i], i), place(right[i], i));
            centre.push((l + r) * 0.5);
            side.push((r - l) * 0.5);
        }
        let caps = (!closed).then(|| {
            [(0usize, -1.0), (n - 1, 1.0)].map(|(i, sign)| {
                let out = unmetric(pts[i], dirs[i]) * (half_deg * width[i] * sign);
                place(shift(pts[i], out), i) - place(pts[i], i)
            })
        });
        Self { centre, side, along, caps }
    }

    /// Appends the ribbon to `mesh`. `alpha` is the opacity per point;
    /// stretches with none are left out.
    fn paint(&self, mesh: &mut LineMesh, alpha: &[f64], p: &Paint) {
        let n = self.centre.len();
        if n < 2 || alpha.iter().all(|a| *a < 0.004) {
            return;
        }
        // The shader reads the profile back as `params.y * 3`.
        let params = [unit(p.dash.unwrap_or(0.0)), p.profile as u8 * 85, unit(p.feather), 0];
        let vertex = |pos: DVec3, i: usize, uv: [f32; 2]| LineVertex {
            pos: pos.as_vec3().to_array(),
            uv,
            along: self.along[i],
            colour: [p.colour[0], p.colour[1], p.colour[2], unit(alpha[i])],
            params,
        };
        let base = mesh.vertices.len() as u32;
        for i in 0..n {
            let side = self.side[i] * p.share;
            mesh.vertices.push(vertex(self.centre[i] - side, i, [-1.0, 0.0]));
            mesh.vertices.push(vertex(self.centre[i] + side, i, [1.0, 0.0]));
        }
        for i in 0..n - 1 {
            if alpha[i] < 0.004 && alpha[i + 1] < 0.004 {
                continue;
            }
            let k = base + 2 * i as u32;
            mesh.indices.extend_from_slice(&[k, k + 1, k + 3, k, k + 3, k + 2]);
        }
        // Round caps: a square past each end, cut to a semicircle by the shader.
        let Some(caps) = &self.caps else { return };
        for (i, out) in [(0usize, caps[0]), (n - 1, caps[1])] {
            if alpha[i] < 0.004 {
                continue;
            }
            let (side, out) = (self.side[i] * p.share, out * p.share);
            let k = mesh.vertices.len() as u32;
            mesh.vertices.push(vertex(self.centre[i] - side + out, i, [-1.0, 1.0]));
            mesh.vertices.push(vertex(self.centre[i] + side + out, i, [1.0, 1.0]));
            let e = base + 2 * i as u32;
            mesh.indices.extend_from_slice(&[e, e + 1, k + 1, e, k + 1, k]);
        }
    }
}

/// Whether `river` starts on another river (a branch leaving its parent, or
/// the next stretch of the same river), so its start is not a headwater.
fn starts_on_another(river: &River, rivers: &[River]) -> bool {
    const NEAR: f64 = 0.08;
    let p = DVec2::new(river.points[0].lon, river.points[0].lat);
    rivers.iter().filter(|o| o.id != river.id).any(|o| {
        o.points.windows(2).any(|w| {
            let (a, b) = (DVec2::new(w[0].lon, w[0].lat), DVec2::new(w[1].lon, w[1].lat));
            let ab = b - a;
            let t = ((p - a).dot(ab) / ab.length_squared().max(1e-18)).clamp(0.0, 1.0);
            (a + ab * t).distance_squared(p) < NEAR * NEAR
        })
    })
}

/// Whether `river` starts at a lake at `year` (its outlet): its first point
/// is on a Water hex, or inside or right at a lake's shoreline.
fn starts_at_lake(river: &River, lakes: &[Lake], year: Year, on_water: bool) -> bool {
    const NEAR: f64 = 0.08;
    let p0 = river.points[0];
    let p = DVec2::new(p0.lon, p0.lat);
    on_water
        || lakes.iter().filter_map(|l| l.shape_at(year)).any(|shape| {
            shape.contains(p0)
                || shape.rings.iter().any(|ring| {
                    (0..ring.len()).any(|i| {
                        let (a, b) = (ring[i], ring[(i + 1) % ring.len()]);
                        let (a, b) = (DVec2::new(a.lon, a.lat), DVec2::new(b.lon, b.lat));
                        let ab = b - a;
                        let t = ((p - a).dot(ab) / ab.length_squared().max(1e-18)).clamp(0.0, 1.0);
                        (a + ab * t).distance_squared(p) < NEAR * NEAR
                    })
                })
        })
}

/// The rivers flowing at the snapshot's year: channel belts on their
/// floodplain reaches, then the channels (small rivers under great ones).
/// Perennial rivers are solid; seasonal ones paler and dashed.
pub fn rivers(mesh: &mut LineMesh, rivers: &[River], lakes: &[Lake], snapshot: &Snapshot, board: &Board) {
    let year = snapshot.year;
    let zoom = line_zoom(board.cam_dist);
    let grid = board.relief.grid();
    let terrain_at = |p: LonLat| grid.hex_at(p).and_then(|id| snapshot.terrain.get(id.index()).copied());
    let run_start = rivers.iter().filter_map(|r| r.state.keys().first().map(|(y, _)| *y)).min().unwrap_or(year);

    let mut order: Vec<(&River, Vec<(RiverState, f64)>)> = rivers
        .iter()
        .filter(|r| r.points.len() >= 2)
        .map(|r| (r, phases(r, year, run_start)))
        .filter(|(_, ph)| !ph.is_empty())
        .collect();
    order.sort_by_key(|(r, _)| r.size);

    // Belts: the strip an alluvial river moves within, under every channel.
    // Its line is smoothed harder than the channel's, which wanders inside.
    // From far out the lines are a pixel or two wide: the belts step back
    // and the darker banks take more of each river, so courses still read.
    let far = {
        let x = ((board.cam_dist - 0.5) / 1.1).clamp(0.0, 1.0);
        x * x * (3.0 - 2.0 * x)
    };
    let belt_half = BELT_HALF * zoom.sqrt();
    for (r, ph) in order.iter().filter(|(r, _)| r.size >= 2) {
        let shown = ph.iter().map(|(_, a)| *a).sum::<f64>().min(1.0);
        let half_deg = belt_half.to_degrees();
        let (pts, step) = centreline(&r.points, half_deg, half_deg * 0.6);
        let on: Vec<f64> = pts.iter().map(|p| (terrain_at(*p) == Some(Terrain::Floodplain as u8)) as u8 as f64).collect();
        // A hex or two of bottomland is too short a reach to show a belt.
        let mut on = on;
        let min_run = (BELT_MIN_DEG / step).ceil() as usize;
        let mut i = 0;
        while i < on.len() {
            let j = (i..on.len()).find(|k| on[*k] != on[i]).unwrap_or(on.len());
            if on[i] > 0.0 && j - i < min_run {
                on[i..j].fill(0.0);
            }
            i = j;
        }
        if on.iter().all(|v| *v == 0.0) {
            continue;
        }
        let alpha: Vec<f64> = blur(&on, (BELT_FADE_DEG / step).round() as usize).iter().map(|g| g * 0.5 * (1.0 - 0.7 * far) * shown).collect();
        let spine = Spine::new(&pts, &vec![1.0; pts.len()], belt_half, 0.00030, false, board);
        spine.paint(mesh, &alpha, &Paint { share: 1.0, colour: BELT, dash: None, feather: 0.3, profile: Profile::Plain });
    }

    // Channels: every river's banks, then every river's fill.
    struct Channel {
        spine: Spine,
        /// (seasonal, opacity per point) for each phase drawn.
        phases: Vec<(bool, Vec<f64>)>,
    }
    let channels: Vec<Channel> = order
        .iter()
        .map(|(r, ph)| {
            let half = HALF_WIDTH[(r.size.clamp(1, 3) - 1) as usize] * zoom;
            let half_deg = half.to_degrees();
            let (pts, step) = centreline(&r.points, half_deg, half_deg * 0.9);
            // Thin at the source, unless it leaves another river or a lake.
            let on_water = terrain_at(r.points[0]) == Some(Terrain::Water as u8);
            let taper = !starts_on_another(r, rivers) && !starts_at_lake(r, lakes, year, on_water);
            let mut along = 0.0;
            let width: Vec<f64> = (0..pts.len())
                .map(|i| {
                    if i > 0 {
                        along += (pts[i].lon - pts[i - 1].lon).hypot(pts[i].lat - pts[i - 1].lat);
                    }
                    let x = (along / TAPER_DEG).min(1.0);
                    if taper { TAPER_FROM + (1.0 - TAPER_FROM) * x * x * (3.0 - 2.0 * x) } else { 1.0 }
                })
                .collect();
            // A river isn't drawn across a lake it flows through.
            let wet: Vec<f64> = pts.iter().map(|p| (terrain_at(*p) == Some(Terrain::Water as u8)) as u8 as f64).collect();
            let dry: Vec<f64> = blur(&wet, (WATER_FADE_DEG / step).round() as usize).iter().map(|w| 1.0 - w).collect();
            let phases = ph.iter().map(|(state, a)| (*state == RiverState::Seasonal, dry.iter().map(|d| d * a).collect())).collect();
            Channel { spine: Spine::new(&pts, &width, half, 0.0004, false, board), phases }
        })
        .collect();
    // Beds first, under every channel, fading out with distance.
    let near = 1.0 - far;
    if near > 0.01 {
        for c in &channels {
            for (seasonal, alpha) in &c.phases {
                let alpha: Vec<f64> = alpha.iter().map(|a| a * 0.9 * near).collect();
                let paint = Paint { share: BED_SHARE, colour: BED[*seasonal as usize], dash: None, feather: 0.45, profile: Profile::Bed };
                c.spine.paint(mesh, &alpha, &paint);
            }
        }
    }
    for (layer, share) in [(1, 1.0), (0, FILL[0] + (FILL[1] - FILL[0]) * far)] {
        for c in &channels {
            for (seasonal, alpha) in &c.phases {
                let paint = Paint {
                    share,
                    colour: if *seasonal { SEASONAL[layer] } else { PERENNIAL[layer] },
                    dash: seasonal.then_some(DASH_ON),
                    feather: 0.0,
                    // The fill, not the dark waterline under it.
                    profile: if layer == 0 { Profile::Water } else { Profile::Plain },
                };
                c.spine.paint(mesh, alpha, &paint);
            }
        }
    }
    if near > 0.01 {
        for c in &channels {
            for (seasonal, alpha) in &c.phases {
                let alpha: Vec<f64> = alpha.iter().map(|a| a * 0.5 * near).collect();
                let paint = Paint { share: 0.26, colour: GLINT, dash: seasonal.then_some(DASH_ON), feather: 0.7, profile: Profile::Plain };
                c.spine.paint(mesh, &alpha, &paint);
            }
        }
    }
}

/// Where the channels are, for the terrain art: a raster over the whole
/// grid that gives, near a river, the nearest point of its centreline. The
/// layout bake uses it to keep props out of the water and put riverside
/// growth on the banks, and the tile shader to green the ground along it
/// (`art_river` in terrain_art.wgsl).
///
/// It is in the art's board-wide hex-local coordinates (`art_global`: x
/// east, y north, a hex's corners one unit from its centre), `size[0]`
/// texels spanning the grid's width. RGBA8 per texel: r, g: offset from the
/// texel's centre to the nearest centreline point, over [`FIELD_REACH`]
/// (-1..1 as 0..255); b: the channel's half width over [`FIELD_HALF_MAX`];
/// a: 0 no river within reach, 128 seasonal, 255 perennial.
#[derive(Clone, Debug, PartialEq)]
pub struct RiverField {
    pub size: [u32; 2],
    pub rgba: Vec<u8>,
}

/// How far (hex-local units) from a centreline the field reaches.
pub const FIELD_REACH: f64 = 0.75;
/// The half width (hex-local units) that encodes as 255.
pub const FIELD_HALF_MAX: f64 = 0.25;
/// Field texels per column of hexes, unless that would pass `FIELD_MAX_SIZE`.
const FIELD_PER_COLUMN: f64 = 8.0;
/// WebGL2 guarantees textures only up to 2048 texels a side.
const FIELD_MAX_SIZE: f64 = 2040.0;

/// The field's size in texels and its texel size (hex-local units) for a
/// grid of `cols × rows` hexes. In art_global coordinates the grid runs
/// from x = -1 east and from y = √3/2 south.
pub fn field_size(cols: u32, rows: u32) -> ([u32; 2], f64) {
    let span = DVec2::new(1.5 * (cols as f64 - 1.0) + 2.0, 3f64.sqrt() * (rows as f64 + 0.5));
    let texel = (1.5 / FIELD_PER_COLUMN).max(span.x / FIELD_MAX_SIZE).max(span.y / FIELD_MAX_SIZE);
    let w = (span.x / texel).ceil().max(1.0);
    // The shader works the texel size out from the width.
    let texel = span.x / w;
    ([w as u32, (span.y / texel).ceil().max(1.0) as u32], texel)
}

impl RiverField {
    /// No rivers on a grid of `cols × rows` hexes.
    pub fn empty(cols: u32, rows: u32) -> Self {
        let size = field_size(cols, rows).0;
        Self { size, rgba: vec![0; (size[0] * size[1] * 4) as usize] }
    }
}

/// What each river mostly is at `year`, in order: `None` when it isn't
/// flowing, else whether it is seasonal. A river mid-fade counts as the
/// state it is nearer to. The field only changes when this does.
pub fn flowing(rivers: &[River], year: Year) -> Vec<Option<bool>> {
    let run_start = rivers.iter().filter_map(|r| r.state.keys().first().map(|(y, _)| *y)).min().unwrap_or(year);
    rivers
        .iter()
        .map(|r| {
            if r.points.len() < 2 {
                return None;
            }
            let ph = phases(r, year, run_start);
            let shown: f64 = ph.iter().map(|(_, a)| *a).sum();
            let top = ph.into_iter().max_by(|a, b| a.1.total_cmp(&b.1))?;
            (shown >= 0.5).then_some(top.0 == RiverState::Seasonal)
        })
        .collect()
}

/// The field for the rivers that are `flowing` (see [`flowing`]), at their
/// close-up width: props only show close up.
pub fn river_field(rivers: &[River], flowing: &[Option<bool>], grid: &GridSpec) -> RiverField {
    let mut field = RiverField::empty(grid.cols as u32, grid.rows as u32);
    let ([w, h], texel) = field_size(grid.cols as u32, grid.rows as u32);
    let (w, h) = (w as usize, h as usize);
    let sqrt3_2 = 3f64.sqrt() / 2.0;
    let (lon0, lat0) = (grid.origin_lon + grid.w / 2.0, grid.origin_lat - grid.h / 2.0);
    let local = |p: LonLat| DVec2::new((p.lon - lon0) / (grid.w / 2.0), (p.lat - lat0) / (grid.h / 2.0) * sqrt3_2);
    let centre = |i: usize, j: usize| DVec2::new((i as f64 + 0.5) * texel - 1.0, sqrt3_2 - (j as f64 + 0.5) * texel);

    let rgba = &mut field.rgba;
    let mut best = vec![f32::INFINITY; w * h];
    let byte = |v: f64| (v.clamp(0.0, 1.0) * 255.0).round() as u8;
    for (r, seasonal) in rivers.iter().zip(flowing).filter_map(|(r, f)| f.map(|s| (r, s))) {
        let half = HALF_WIDTH[(r.size.clamp(1, 3) - 1) as usize];
        let half_deg = half.to_degrees();
        let (pts, _) = centreline(&r.points, half_deg, half_deg * 0.9);
        let half_local = half_deg / (grid.h / 2.0) * sqrt3_2;
        let meta = [byte(half_local / FIELD_HALF_MAX), if seasonal { 128 } else { 255 }];
        let pts: Vec<DVec2> = pts.iter().map(|p| local(*p)).collect();
        for seg in pts.windows(2) {
            let (a, b) = (seg[0], seg[1]);
            let ab = b - a;
            let (lo, hi) = (a.min(b) - FIELD_REACH, a.max(b) + FIELD_REACH);
            // Texel ranges: columns run east, rows south.
            let range = |lo: f64, hi: f64, n: usize| (lo.floor().max(0.0) as usize)..(hi.ceil().max(0.0) as usize).min(n);
            let cols = range((lo.x + 1.0) / texel, (hi.x + 1.0) / texel, w);
            for j in range((sqrt3_2 - hi.y) / texel, (sqrt3_2 - lo.y) / texel, h) {
                for i in cols.clone() {
                    let c = centre(i, j);
                    let t = ((c - a).dot(ab) / ab.length_squared().max(1e-18)).clamp(0.0, 1.0);
                    let off = a + ab * t - c;
                    let d = off.length();
                    let k = j * w + i;
                    if d < FIELD_REACH && (d as f32) < best[k] {
                        best[k] = d as f32;
                        let o = off / FIELD_REACH * 0.5 + 0.5;
                        rgba[k * 4..k * 4 + 4].copy_from_slice(&[byte(o.x), byte(o.y), meta[0], meta[1]]);
                    }
                }
            }
        }
    }
    field
}

#[cfg(test)]
mod tests {
    use super::*;
    use glam::Vec3;
    use neolith_core::{GridSpec, Timeline};

    fn grid() -> GridSpec {
        GridSpec { cols: 12, rows: 12, origin_lon: 28.0, origin_lat: 34.0, w: 0.5773502691896262, h: 0.5 }
    }

    fn river(keys: &[(i32, RiverState)]) -> River {
        River {
            id: 1,
            key: "r".into(),
            name: "R".into(),
            size: 2,
            points: vec![LonLat::new(30.0, 30.0), LonLat::new(31.0, 31.0), LonLat::new(33.0, 31.0)],
            state: Timeline::from_keys(keys.iter().map(|(y, s)| (Year(*y), *s))),
        }
    }

    fn snapshot(grid: &GridSpec, year: i32, terrain: Terrain) -> Snapshot {
        let n = grid.len();
        Snapshot {
            year: Year(year),
            terrain: vec![terrain as u8; n],
            koeppen: vec![0; n],
            pop: vec![0; n],
            river: vec![0; n],
            elevation: vec![0; n],
            npp: vec![0; n],
            biodiversity: vec![0; n],
            expected: vec![0; n],
            shore_km: vec![0; n],
            height: vec![0; n],
        }
    }

    fn build(r: &River, year: i32, terrain: Terrain) -> LineMesh {
        let grid = grid();
        let proj = Projection::new(LonLat::new(30.0, 35.0));
        let relief = Relief::flat(&grid);
        let board = Board { proj: &proj, relief: &relief, t: 0.0, cam_dist: 1.0 };
        let mut mesh = LineMesh::default();
        rivers(&mut mesh, std::slice::from_ref(r), &[], &snapshot(&grid, year, terrain), &board);
        mesh
    }

    #[test]
    fn a_lake_outlet_is_not_a_headwater() {
        use neolith_core::LakeShape;
        let sq = |x0: f64, y0: f64, s: f64| {
            vec![LonLat::new(x0, y0), LonLat::new(x0 + s, y0), LonLat::new(x0 + s, y0 + s), LonLat::new(x0, y0 + s)]
        };
        let lake = |x0, y0| Lake {
            key: "l".into(),
            name: "L".into(),
            shapes: vec![LakeShape { level: 5.0, rings: vec![sq(x0, y0, 1.0)] }],
            shape: Timeline::from_keys([(Year(-9000), 0), (Year(-5000), neolith_core::NO_SHAPE)]),
        };
        let r = river(&[(-10000, RiverState::Perennial)]); // starts at (30, 30)
        // Inside the shoreline, or just outside it; not far from it, not
        // before or after the lake exists.
        assert!(starts_at_lake(&r, &[lake(29.5, 29.5)], Year(-8000), false));
        assert!(starts_at_lake(&r, &[lake(30.05, 29.5)], Year(-8000), false));
        assert!(!starts_at_lake(&r, &[lake(30.5, 29.5)], Year(-8000), false));
        assert!(!starts_at_lake(&r, &[lake(29.5, 29.5)], Year(-9500), false));
        assert!(!starts_at_lake(&r, &[lake(29.5, 29.5)], Year(-4000), false));
        // A Water hex under the source counts without a shoreline.
        assert!(starts_at_lake(&r, &[], Year(-8000), true));
    }

    #[test]
    fn ribbons_lie_on_the_board_and_index_their_own_vertices() {
        let r = river(&[(-10000, RiverState::Perennial)]);
        let mesh = build(&r, -9000, Terrain::Plains);
        assert!(!mesh.indices.is_empty() && mesh.indices.len().is_multiple_of(3));
        assert!(mesh.indices.iter().all(|i| (*i as usize) < mesh.vertices.len()));
        for v in &mesh.vertices {
            let len = Vec3::from(v.pos).length();
            assert!(len > 1.0 && len < 1.002, "{len}");
            // The water is opaque; its bed and glint are not.
            if PERENNIAL.iter().any(|c| v.colour[..3] == *c) {
                assert_eq!(v.colour[3], 255);
            }
        }
        assert!(build(&r, -10001, Terrain::Plains).indices.is_empty());
    }

    #[test]
    fn a_channel_lies_in_a_bed_that_only_shows_close_up() {
        let r = river(&[(-10000, RiverState::Perennial)]);
        let bed = |cam_dist: f64| {
            let grid = grid();
            let proj = Projection::new(LonLat::new(30.0, 35.0));
            let relief = Relief::flat(&grid);
            let board = Board { proj: &proj, relief: &relief, t: 0.0, cam_dist };
            let mut mesh = LineMesh::default();
            rivers(&mut mesh, std::slice::from_ref(&r), &[], &snapshot(&grid, -9000, Terrain::Plains), &board);
            // Drawn first, under the water.
            (mesh.vertices[0].colour[..3] == BED[0], mesh.vertices.iter().any(|v| v.colour[..3] == BED[0]))
        };
        assert_eq!(bed(0.3), (true, true));
        assert_eq!(bed(2.0), (false, false));
    }

    #[test]
    fn the_river_field_knows_the_nearest_centreline_point() {
        let grid = grid();
        let r = river(&[(-10000, RiverState::Perennial), (-8000, RiverState::Seasonal), (-6000, RiverState::Absent)]);
        let rs = std::slice::from_ref(&r);
        assert_eq!(flowing(rs, Year(-9000)), vec![Some(false)]);
        assert_eq!(flowing(rs, Year(-7000)), vec![Some(true)]);
        assert_eq!(flowing(rs, Year(-5000)), vec![None]);
        assert_eq!(river_field(rs, &flowing(rs, Year(-5000)), &grid), RiverField::empty(12, 12));

        // A straight river east along 31°N (the test river's spline swings
        // wide after its bend).
        let r = River { points: vec![LonLat::new(30.0, 31.0), LonLat::new(31.5, 31.0), LonLat::new(33.0, 31.0)], ..r };
        let rs = std::slice::from_ref(&r);
        let field = river_field(rs, &flowing(rs, Year(-9000)), &grid);
        let ([w, h], texel) = field_size(12, 12);
        assert_eq!(field.size, [w, h]);
        // A point 0.1°
        // north of it, mid-reach, in art_global coordinates:
        let sqrt3_2 = 3f64.sqrt() / 2.0;
        let (lon0, lat0) = (grid.origin_lon + grid.w / 2.0, grid.origin_lat - grid.h / 2.0);
        let local = |lon: f64, lat: f64| DVec2::new((lon - lon0) / (grid.w / 2.0), (lat - lat0) / (grid.h / 2.0) * sqrt3_2);
        let p = local(32.0, 31.1);
        let (i, j) = (((p.x + 1.0) / texel) as usize, ((sqrt3_2 - p.y) / texel) as usize);
        let e = &field.rgba[(j * w as usize + i) * 4..][..4];
        assert_eq!(e[3], 255);
        let centre = DVec2::new((i as f64 + 0.5) * texel - 1.0, sqrt3_2 - (j as f64 + 0.5) * texel);
        let q = centre + (DVec2::new(e[0] as f64, e[1] as f64) / 255.0 * 2.0 - 1.0) * FIELD_REACH;
        assert!((q.y - local(32.0, 31.0).y).abs() < 0.02, "{q}");
        assert!((q.x - centre.x).abs() < 0.02, "{q}");
        // Far from the river there is nothing.
        let far = local(29.0, 33.0);
        let (i, j) = (((far.x + 1.0) / texel) as usize, ((sqrt3_2 - far.y) / texel) as usize);
        assert_eq!(field.rgba[(j * w as usize + i) * 4 + 3], 0);
    }

    #[test]
    fn the_cleaned_course_keeps_its_ends_and_loses_tight_wiggles() {
        // A zigzag 0.02° wide, far finer than a 0.1° half width.
        let zig: Vec<LonLat> = (0..200).map(|i| LonLat::new(30.0 + i as f64 * 0.01, 31.0 + (i % 2) as f64 * 0.02)).collect();
        let (pts, step) = centreline(&zig, 0.1, 0.09);
        assert_eq!((pts[0].lon, pts[0].lat), (zig[0].lon, zig[0].lat));
        assert_eq!((pts[pts.len() - 1].lon, pts[pts.len() - 1].lat), (zig[199].lon, zig[199].lat));
        for w in pts.windows(2) {
            assert!(w[1].lon > w[0].lon, "the line doubles back");
            assert!((w[1].lon - w[0].lon).hypot(w[1].lat - w[0].lat) < step * 1.6);
        }
        let mid = &pts[pts.len() / 2];
        assert!((mid.lat - 31.01).abs() < 0.004, "{}", mid.lat);
    }

    #[test]
    fn state_changes_cross_fade() {
        let r = river(&[(-10000, RiverState::Perennial), (-8000, RiverState::Seasonal), (-6000, RiverState::Absent)]);
        let start = Year(-10000);
        // There from the start of the run: no fade in.
        assert_eq!(phases(&r, Year(-10000), start), vec![(RiverState::Perennial, 1.0)]);
        assert_eq!(phases(&r, Year(-8000), start), vec![(RiverState::Perennial, 1.0)]);
        let mid = phases(&r, Year(-8000 + FADE_YEARS as i32 / 2), start);
        assert_eq!(mid, vec![(RiverState::Perennial, 0.5), (RiverState::Seasonal, 0.5)]);
        assert_eq!(phases(&r, Year(-7000), start), vec![(RiverState::Seasonal, 1.0)]);
        // Fades out after the key that ends it, then is gone.
        let out = phases(&r, Year(-6000 + FADE_YEARS as i32 / 4), start);
        assert!(out.len() == 1 && out[0].0 == RiverState::Seasonal && out[0].1 > 0.5 && out[0].1 < 1.0);
        assert!(phases(&r, Year(-5000), start).is_empty());
        // A river that appears later fades in.
        let late = river(&[(-9000, RiverState::Perennial)]);
        let p = phases(&late, Year(-9000 + FADE_YEARS as i32 / 2), start);
        assert_eq!(p, vec![(RiverState::Perennial, 0.5)]);
        // Drawn half transparent, beside a river that was there from the start.
        let (grid, proj) = (grid(), Projection::new(LonLat::new(30.0, 35.0)));
        let relief = Relief::flat(&grid);
        let board = Board { proj: &proj, relief: &relief, t: 0.0, cam_dist: 1.0 };
        let old = River { id: 2, points: vec![LonLat::new(29.0, 36.0), LonLat::new(29.0, 38.0)], ..river(&[(-10000, RiverState::Perennial)]) };
        let mut mesh = LineMesh::default();
        rivers(&mut mesh, &[old, late], &[], &snapshot(&grid, -9000 + FADE_YEARS as i32 / 2, Terrain::Plains), &board);
        // (Of the water: the beds and glints have their own opacity.)
        let water: Vec<_> = mesh.vertices.iter().filter(|v| PERENNIAL.iter().any(|c| v.colour[..3] == *c)).collect();
        assert!(water.iter().any(|v| v.colour[3] == 255));
        assert!(water.iter().any(|v| v.colour[3] > 100 && v.colour[3] < 150));
        assert!(water.iter().all(|v| v.colour[3] == 255 || (v.colour[3] > 100 && v.colour[3] < 150)));
    }

    #[test]
    fn belts_follow_the_floodplain_and_rivers_stop_at_water() {
        let r = river(&[(-10000, RiverState::Perennial)]);
        let plain = build(&r, -9000, Terrain::Plains);
        let flood = build(&r, -9000, Terrain::Floodplain);
        assert!(flood.indices.len() > plain.indices.len());
        assert!(flood.vertices.iter().any(|v| v.colour[..3] == BELT));
        assert!(!plain.vertices.iter().any(|v| v.colour[..3] == BELT));
        assert!(build(&r, -9000, Terrain::Water).indices.is_empty());
    }
}
