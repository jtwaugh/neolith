//! Orbit camera around a look-at point on the board, plus analytic picking.

use super::projection::Projection;
use super::relief::Relief;
use glam::{DMat3, DMat4, DVec2, DVec3};
use neolith_core::{GridSpec, LonLat};

pub const PITCH_MIN: f64 = 15.0 * std::f64::consts::PI / 180.0;
pub const PITCH_MAX: f64 = std::f64::consts::FRAC_PI_2;
pub const DIST_MIN: f64 = 0.06;
pub const DIST_MAX: f64 = 3.6;
/// Lowest tilt in "Fill screen" mode.
pub const FILL_PITCH_MIN: f64 = 35.0 * std::f64::consts::PI / 180.0;

#[derive(Clone, Copy, Debug)]
pub struct Camera {
    /// Look-at point on the board surface. Kept inside the grid bounds.
    pub target: LonLat,
    /// Heading in radians; 0 looks north (camera to the south).
    pub yaw: f64,
    /// Elevation above the board surface, radians; π/2 is straight down.
    pub pitch: f64,
    /// The tilt the player chose (orbit). "Fill screen" may tilt the camera
    /// further towards top-down when zoomed out, and returns to this one as
    /// it zooms back in.
    pub pitch_pref: f64,
    pub dist: f64,
    pub fov_y: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Ray {
    pub origin: DVec3,
    pub dir: DVec3,
}

/// A camera resolved for one frame: matrices for a given viewport and morph.
#[derive(Clone, Copy, Debug)]
pub struct View {
    pub view_proj: DMat4,
    inv_view_proj: DMat4,
    pub eye: DVec3,
    /// Viewport size in points.
    pub size: DVec2,
    /// Morph: 0 = curved, 1 = flat.
    pub t: f64,
    pub proj: Projection,
    /// Projection scale: 1 / tan(fov_y / 2).
    pub focal: f64,
}

impl Camera {
    /// Three-quarter view from the south with the whole board in frame.
    pub fn initial(grid: &GridSpec) -> Self {
        Self {
            target: grid.centre_of_bounds(),
            yaw: 0.0,
            pitch: 50f64.to_radians(),
            pitch_pref: 50f64.to_radians(),
            dist: 2.15,
            fov_y: 35f64.to_radians(),
        }
    }

    pub fn clamp(&mut self, grid: &GridSpec) {
        let (w, s, e, n) = grid.bounds();
        self.target.lon = self.target.lon.clamp(w, e);
        self.target.lat = self.target.lat.clamp(s, n);
        self.pitch = self.pitch.clamp(PITCH_MIN, PITCH_MAX);
        self.pitch_pref = self.pitch_pref.clamp(PITCH_MIN, PITCH_MAX);
        self.dist = self.dist.clamp(DIST_MIN, DIST_MAX);
        self.yaw = self.yaw.rem_euclid(std::f64::consts::TAU);
    }

    /// Whether the board covers the viewport, less `margin` (a fraction of
    /// the width and height on each side that may show the table): the
    /// corners and edge midpoints of that inner rectangle all land on a hex.
    pub fn covers(&self, proj: &Projection, grid: &GridSpec, t: f64, size: DVec2, margin: f64) -> bool {
        let view = self.view(proj, t, size);
        let m = margin.clamp(0.0, 0.49);
        let (ix, iy) = ((size.x * m).max(2.0), (size.y * m).max(2.0));
        let (x0, x1, y0, y1) = (ix, size.x - ix, iy, size.y - iy);
        let (xm, ym) = (size.x / 2.0, size.y / 2.0);
        [(x0, y0), (xm, y0), (x1, y0), (x0, ym), (x1, ym), (x0, y1), (xm, y1), (x1, y1)]
            .iter()
            .all(|&(x, y)| view.pick(DVec2::new(x, y)).and_then(|ll| grid.hex_at(ll)).is_some())
    }

    /// Keeps the board filling the viewport (the "Fill screen" style), as in
    /// a Paradox map, except for `margin` (a fraction of the view on each
    /// side) where the map's edge and the table may show.
    ///
    /// Starting from the player's tilt (at least [`FILL_PITCH_MIN`]; lower,
    /// the top of the view looks past the curved board), in order:
    /// 1. if the view shows something off the board but would not from the
    ///    board's centre, the look-at point slides towards the centre just
    ///    far enough (panning into an edge stops at the edge);
    /// 2. otherwise the camera tilts towards top-down just far enough, as
    ///    Paradox cameras do when zoomed out;
    /// 3. if even straight down from the centre shows the table, it zooms in
    ///    until it doesn't.
    pub fn clamp_to_fill(&mut self, proj: &Projection, grid: &GridSpec, t: f64, size: DVec2, margin: f64) {
        self.pitch = self.pitch_pref.max(FILL_PITCH_MIN);
        if size.x < 8.0 || size.y < 8.0 || self.covers(proj, grid, t, size, margin) {
            return;
        }
        let from = self.target;
        let centre = grid.centre_of_bounds();
        let at = |f: f64| LonLat::new(from.lon + (centre.lon - from.lon) * f, from.lat + (centre.lat - from.lat) * f);
        let covers_at = |cam: &Camera, f: f64| Camera { target: at(f), ..*cam }.covers(proj, grid, t, size, margin);
        if !covers_at(self, 1.0) {
            // Tilt: the least pitch at which the centre is covered.
            let centred = Camera { target: centre, ..*self };
            if (Camera { pitch: PITCH_MAX, ..centred }).covers(proj, grid, t, size, margin) {
                let (mut lo, mut hi) = (self.pitch, PITCH_MAX);
                for _ in 0..20 {
                    let mid = (lo + hi) / 2.0;
                    if (Camera { pitch: mid, ..centred }).covers(proj, grid, t, size, margin) {
                        hi = mid;
                    } else {
                        lo = mid;
                    }
                }
                self.pitch = hi;
            } else {
                self.pitch = PITCH_MAX;
            }
        }
        if !covers_at(self, 1.0) {
            // Zoomed out too far for any position: the largest distance that
            // covers from the centre.
            let (mut lo, mut hi) = (DIST_MIN, self.dist);
            let centred = Camera { target: centre, ..*self };
            if !(Camera { dist: lo, ..centred }).covers(proj, grid, t, size, margin) {
                return; // cannot cover at all (a tiny window); leave the camera be
            }
            for _ in 0..24 {
                let mid = (lo + hi) / 2.0;
                if (Camera { dist: mid, ..centred }).covers(proj, grid, t, size, margin) {
                    lo = mid;
                } else {
                    hi = mid;
                }
            }
            self.dist = lo;
        }
        // The smallest slide towards the centre that covers.
        let (mut lo, mut hi) = (0.0, 1.0);
        for _ in 0..24 {
            let mid = (lo + hi) / 2.0;
            if covers_at(self, mid) {
                hi = mid;
            } else {
                lo = mid;
            }
        }
        self.target = at(hi);
    }

    pub fn view(&self, proj: &Projection, t: f64, size: DVec2) -> View {
        let p = proj.surface(self.target, t);
        let n = proj.normal(self.target, t);
        // Local north: step along the meridian, made tangent to the surface.
        let ahead = proj.surface(LonLat::new(self.target.lon, self.target.lat + 1e-3), t);
        let behind = proj.surface(LonLat::new(self.target.lon, self.target.lat - 1e-3), t);
        let north = ahead - behind;
        let north = (north - n * north.dot(n)).normalize();
        let east = north.cross(n);
        let heading = north * self.yaw.cos() + east * self.yaw.sin();
        let eye = p + (n * self.pitch.sin() - heading * self.pitch.cos()) * self.dist;
        let up = n * self.pitch.cos() + heading * self.pitch.sin();
        let view = DMat4::look_at_rh(eye, p, up);
        let aspect = (size.x / size.y.max(1.0)).max(1e-3);
        let projm = DMat4::perspective_rh(self.fov_y, aspect, self.dist * 0.02, self.dist + 8.0);
        let view_proj = projm * view;
        View { view_proj, inv_view_proj: view_proj.inverse(), eye, size, t, proj: *proj, focal: 1.0 / (self.fov_y / 2.0).tan() }
    }
}

impl View {
    /// The ray through a viewport position (points, origin top-left).
    pub fn ray(&self, pos: DVec2) -> Ray {
        let x = 2.0 * pos.x / self.size.x - 1.0;
        let y = 1.0 - 2.0 * pos.y / self.size.y;
        let near = self.inv_view_proj.project_point3(DVec3::new(x, y, 0.0));
        let far = self.inv_view_proj.project_point3(DVec3::new(x, y, 1.0));
        Ray { origin: near, dir: (far - near).normalize() }
    }

    /// Projects a world position to viewport points. `None` behind the camera.
    pub fn project_world(&self, world: DVec3) -> Option<DVec2> {
        let clip = self.view_proj * world.extend(1.0);
        if clip.w <= 1e-9 {
            return None;
        }
        let ndc = clip.truncate() / clip.w;
        Some(DVec2::new((ndc.x + 1.0) * 0.5 * self.size.x, (1.0 - ndc.y) * 0.5 * self.size.y))
    }

    /// Projects a board position to viewport points (at the board surface,
    /// ignoring relief).
    #[cfg(test)]
    pub fn project(&self, p: LonLat) -> Option<DVec2> {
        self.project_world(self.proj.surface(p, self.t))
    }

    /// Projects a board position on the raised tiles to viewport points.
    pub fn project_relief(&self, p: LonLat, relief: &Relief) -> Option<DVec2> {
        self.project_world(self.proj.surface_at(p, self.t, relief.at(p)))
    }

    /// Analytic picking: the lon/lat on the board's top surface under a
    /// viewport position, or `None` if the ray misses the surface entirely.
    /// (The caller turns this into a hex with `GridSpec::hex_at`.)
    pub fn pick(&self, pos: DVec2) -> Option<LonLat> {
        self.pick_at(pos, 0.0)
    }

    /// Like [`View::pick`], on the board raised by `relief`: the first hex
    /// whose tile (top or cliff) the ray reaches. Steps down through the
    /// height range and stops at the first point that is under its hex's top.
    pub fn pick_relief(&self, pos: DVec2, relief: &Relief) -> Option<LonLat> {
        if relief.is_flat() {
            return self.pick(pos);
        }
        const STEPS: usize = 32;
        let mut last = None;
        for k in 0..=STEPS {
            let h = relief.max + (relief.min - relief.max) * k as f64 / STEPS as f64;
            let Some(p) = self.pick_at(pos, h) else { continue };
            let top = relief.at(p);
            if top >= h - 1e-12 {
                // Snap onto that hex's top when the ray reaches it there;
                // otherwise the ray hit its cliff face.
                let hex = relief.grid().hex_at(p);
                return Some(self.pick_at(pos, top).filter(|q| relief.grid().hex_at(*q) == hex).unwrap_or(p));
            }
            last = Some(p);
        }
        last
    }

    /// Picking against the surface raised uniformly by `lift` board units.
    fn pick_at(&self, pos: DVec2, lift: f64) -> Option<LonLat> {
        let ray = self.ray(pos);
        if self.t <= 0.0 {
            return ray_sphere(&ray, 1.0 + lift).map(|hit| self.proj.sphere_inv(hit));
        }
        if self.t >= 1.0 {
            return ray_plane(&ray, 1.0 + lift).map(|hit| self.proj.plane_inv(hit - DVec3::Y * lift));
        }
        self.pick_morphed(&ray, lift)
    }

    /// Mid-morph the surface is `mix(sphere, plane, t)`, which has no closed
    /// form; solve `surface(λ, φ) = origin + s·dir` by Newton iteration.
    fn pick_morphed(&self, ray: &Ray, lift: f64) -> Option<LonLat> {
        let start = match (ray_sphere(ray, 1.0 + lift), ray_plane(ray, 1.0 + lift)) {
            (Some(s), Some(p)) => {
                let (a, b) = (self.proj.sphere_inv(s), self.proj.plane_inv(p - DVec3::Y * lift));
                LonLat::new(a.lon + (b.lon - a.lon) * self.t, a.lat + (b.lat - a.lat) * self.t)
            }
            (Some(s), None) => self.proj.sphere_inv(s),
            (None, Some(p)) => self.proj.plane_inv(p - DVec3::Y * lift),
            (None, None) => return None,
        };
        let (mut lon, mut lat) = (start.lon, start.lat);
        let surface = |p: LonLat| self.proj.surface_at(p, self.t, lift);
        let mut s = (surface(start) - ray.origin).dot(ray.dir);
        const H: f64 = 1e-4; // degrees
        for _ in 0..25 {
            if !(lon.abs() < 720.0 && lat.abs() < 89.9) {
                return None;
            }
            let here = surface(LonLat::new(lon, lat));
            let f = here - (ray.origin + ray.dir * s);
            if f.length_squared() < 1e-22 {
                return (s > 0.0).then_some(LonLat::new(lon, lat));
            }
            let d_lon = (surface(LonLat::new(lon + H, lat)) - here) / H;
            let d_lat = (surface(LonLat::new(lon, lat + H)) - here) / H;
            let j = DMat3::from_cols(d_lon, d_lat, -ray.dir);
            if j.determinant().abs() < 1e-14 {
                return None;
            }
            let step = j.inverse() * f;
            lon -= step.x;
            lat -= step.y;
            s -= step.z;
        }
        None
    }
}

/// Nearer intersection of a ray with the sphere of radius `r`.
fn ray_sphere(ray: &Ray, r: f64) -> Option<DVec3> {
    let b = ray.origin.dot(ray.dir);
    let c = ray.origin.length_squared() - r * r;
    let disc = b * b - c;
    if disc < 0.0 {
        return None;
    }
    let s = -b - disc.sqrt();
    (s > 0.0).then(|| ray.origin + ray.dir * s)
}

/// Intersection of a ray with the plane y = `y` (the flat board is y = 1), from above.
fn ray_plane(ray: &Ray, y: f64) -> Option<DVec3> {
    if ray.dir.y.abs() < 1e-12 {
        return None;
    }
    let s = (y - ray.origin.y) / ray.dir.y;
    (s > 0.0).then(|| ray.origin + ray.dir * s)
}

/// Moves the camera target so that board point `grabbed` ends up under the
/// viewport position `cursor` ("grabbing the board").
#[allow(clippy::too_many_arguments)]
pub fn grab(
    cam: &mut Camera,
    proj: &Projection,
    t: f64,
    size: DVec2,
    grid: &GridSpec,
    relief: &Relief,
    grabbed: LonLat,
    cursor: DVec2,
) {
    for _ in 0..4 {
        let Some(under) = cam.view(proj, t, size).pick_relief(cursor, relief) else { return };
        let (dlon, dlat) = (grabbed.lon - under.lon, grabbed.lat - under.lat);
        if dlon.abs() + dlat.abs() < 1e-9 {
            break;
        }
        cam.target.lon += dlon;
        cam.target.lat += dlat;
        cam.clamp(grid);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::HexId;

    fn grid() -> GridSpec {
        GridSpec { cols: 190, rows: 139, origin_lon: -16.464168425, origin_lat: 75.858035103, w: 0.5773502691896262, h: 0.5 }
    }

    #[test]
    fn fill_clamp_always_covers_the_view() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1600.0, 950.0);
        let mut rng = Lcg(7);
        for t in [0.0, 1.0] {
            for _ in 0..40 {
                let (w, s, e, n) = g.bounds();
                let mut cam = Camera::initial(&g);
                cam.target = LonLat::new(w + (e - w) * rng.next(), s + (n - s) * rng.next());
                cam.dist = DIST_MIN + (DIST_MAX - DIST_MIN) * rng.next();
                cam.yaw = rng.next() * std::f64::consts::TAU;
                cam.pitch_pref = PITCH_MIN + (PITCH_MAX - PITCH_MIN) * rng.next();
                cam.clamp(&g);
                cam.clamp_to_fill(&proj, &g, t, size, 0.0);
                assert!(cam.covers(&proj, &g, t, size, 0.0), "t {t}: {cam:?}");
                assert!(cam.pitch >= FILL_PITCH_MIN && cam.pitch >= cam.pitch_pref.min(PITCH_MAX) - 1e-9);
            }
        }
    }

    #[test]
    fn fill_clamp_tilts_out_and_back() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1600.0, 950.0);
        let mut cam = Camera::initial(&g);
        cam.clamp_to_fill(&proj, &g, 0.0, size, 0.0);
        // The default view is zoomed well out, so it tilts towards top-down…
        assert!(cam.pitch > cam.pitch_pref + 0.05, "{cam:?}");
        assert!(cam.dist > 0.5, "zoomed out stays zoomed out: {cam:?}");
        // …and returns to the player's tilt close in.
        cam.dist = 0.15;
        cam.clamp_to_fill(&proj, &g, 0.0, size, 0.0);
        assert!((cam.pitch - cam.pitch_pref).abs() < 1e-9, "{cam:?}");
    }

    #[test]
    fn edge_margin_lets_the_camera_zoom_further_out() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1600.0, 950.0);
        let far = |margin| {
            let mut cam = Camera::initial(&g);
            cam.dist = DIST_MAX;
            cam.clamp_to_fill(&proj, &g, 0.0, size, margin);
            assert!(cam.covers(&proj, &g, 0.0, size, margin));
            cam.dist
        };
        let (strict, roomy) = (far(0.0), far(0.25));
        assert!(roomy > strict * 1.4, "strict {strict}, with margin {roomy}");
        // A margin near one half leaves the camera almost free.
        assert!(far(0.45) > roomy);
    }

    /// Small deterministic generator (no rand dependency).
    struct Lcg(u64);
    impl Lcg {
        fn next(&mut self) -> f64 {
            self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            ((self.0 >> 11) as f64) / ((1u64 << 53) as f64)
        }
    }

    /// M2a/M2b: "clicking" 100 random hex centres picks that hex — curved,
    /// flat and mid-morph, from several camera positions.
    #[test]
    fn clicking_hex_centres_picks_that_hex() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1280.0, 800.0);
        let mut rng = Lcg(7);
        for t in [0.0, 1.0, 0.35, 0.8] {
            let mut checked = 0;
            while checked < 100 {
                let id = HexId((rng.next() * g.len() as f64) as u32);
                let mut cam = Camera::initial(&g);
                cam.yaw = rng.next() * std::f64::consts::TAU;
                cam.pitch = PITCH_MIN + rng.next() * (PITCH_MAX - PITCH_MIN);
                cam.dist = 0.2 + rng.next() * 3.0;
                let c = g.centre(id);
                cam.target = LonLat::new(c.lon + (rng.next() - 0.5) * 20.0, c.lat + (rng.next() - 0.5) * 20.0);
                cam.clamp(&g);
                let view = cam.view(&proj, t, size);
                let Some(px) = view.project(c) else { continue };
                if px.x < 0.0 || px.y < 0.0 || px.x > size.x || px.y > size.y {
                    continue;
                }
                // Skip centres hidden behind the curve of the board.
                let facing = proj.normal(c, t).dot(view.eye - proj.surface(c, t)) > 0.05;
                if !facing {
                    continue;
                }
                let hit = view.pick(px).unwrap_or_else(|| panic!("t={t}: no hit for {id:?}"));
                match g.hex_at(hit) {
                    Some(h) if h == id => checked += 1,
                    // Mid-morph the surface can occlude itself near the horizon; only
                    // then may the nearest hit be a different, nearer hex.
                    Some(_) if t > 0.0 && t < 1.0 => {
                        let d_hit = (proj.surface(hit, t) - view.eye).length();
                        let d_c = (proj.surface(c, t) - view.eye).length();
                        assert!(d_hit < d_c, "t={t}: picked a farther hex than {id:?}");
                    }
                    other => panic!("t={t}: expected {id:?}, picked {other:?}"),
                }
            }
        }
    }

    /// With relief, a raised hex is picked at its top, and a hex hidden
    /// behind a tall neighbour's cliff gives way to that neighbour.
    #[test]
    fn pick_relief_hits_raised_tiles() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1200.0, 800.0);
        let mut cam = Camera::initial(&g);
        cam.dist = 0.25;
        cam.pitch = 0.5;
        let (col, row) = g.col_row(g.hex_at(cam.target).unwrap());
        let tall = g.id_at(col, row);
        let mut height = vec![0i16; g.len()];
        height[tall.index()] = 3000;
        let relief = Relief::new(&g, &height, 20.0 / 6_371_000.0);
        for t in [0.0, 1.0, 0.5] {
            let view = cam.view(&proj, t, size);
            // The top centre of the tall hex picks the tall hex, at its centre.
            let c = g.centre(tall);
            let px = view.project_relief(c, &relief).unwrap();
            let hit = view.pick_relief(px, &relief).unwrap();
            assert_eq!(g.hex_at(hit), Some(tall), "t={t}");
            assert!((hit.lon - c.lon).abs() < 1e-6 && (hit.lat - c.lat).abs() < 1e-6, "t={t}: {hit:?}");
            // The hex just beyond it (north, away from the camera) at ground
            // level is behind its cliff: the ray meets the tall hex first.
            let behind = g.neighbour(tall, 1).unwrap();
            let px = view.project_relief(g.centre(behind), &relief).unwrap();
            assert_eq!(view.pick_relief(px, &relief).and_then(|ll| g.hex_at(ll)), Some(tall), "t={t}");
        }
    }

    #[test]
    fn pick_misses_off_the_board() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1000.0, 700.0);
        let cam = Camera::initial(&g);
        for t in [0.0, 0.5, 1.0] {
            let view = cam.view(&proj, t, size);
            // Top-left corner of the initial view is studio background.
            let hit = view.pick(DVec2::new(2.0, 2.0));
            assert!(hit.and_then(|ll| g.hex_at(ll)).is_none(), "t={t}: {hit:?}");
            // The middle of the view is the target.
            let mid = view.pick(size / 2.0).unwrap();
            assert!((mid.lon - cam.target.lon).abs() < 1e-6 && (mid.lat - cam.target.lat).abs() < 1e-6);
        }
    }

    #[test]
    fn grab_keeps_point_under_cursor() {
        let g = grid();
        let proj = Projection::new(g.centre_of_bounds());
        let size = DVec2::new(1000.0, 700.0);
        for t in [0.0, 1.0, 0.5] {
            let mut cam = Camera::initial(&g);
            cam.dist = 1.0;
            cam.yaw = 0.7;
            let start = DVec2::new(400.0, 300.0);
            let grabbed = cam.view(&proj, t, size).pick(start).unwrap();
            let cursor = DVec2::new(520.0, 380.0);
            grab(&mut cam, &proj, t, size, &g, &Relief::flat(&g), grabbed, cursor);
            let now = cam.view(&proj, t, size).pick(cursor).unwrap();
            assert!((now.lon - grabbed.lon).abs() < 1e-4 && (now.lat - grabbed.lat).abs() < 1e-4, "t={t}");
        }
    }

    #[test]
    fn clamp_limits() {
        let g = grid();
        let mut cam = Camera::initial(&g);
        cam.pitch = 0.0;
        cam.dist = 100.0;
        cam.target = LonLat::new(500.0, -500.0);
        cam.clamp(&g);
        assert_eq!(cam.pitch, PITCH_MIN);
        assert_eq!(cam.dist, DIST_MAX);
        let (_, s, e, _) = g.bounds();
        assert_eq!((cam.target.lon, cam.target.lat), (e, s));
    }
}
