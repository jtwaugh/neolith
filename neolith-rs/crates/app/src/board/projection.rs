//! Where the board sits in the scene. The board's top surface lies on the
//! unit sphere, rotated so the board's centre is at +Y ("resting on the
//! table") with east along +X and north along −Z. The flat board is the
//! equirectangular layout on the plane tangent at the centre (y = 1).
//!
//! All of this is `f64` and GPU-free so camera and picking can be tested.

use glam::{DVec2, DVec3};
use neolith_core::LonLat;

#[derive(Clone, Copy, Debug)]
pub struct Projection {
    lon0: f64,
    lat0: f64,
    east: DVec3,
    north: DVec3,
    up: DVec3,
}

fn raw(lon: f64, lat: f64) -> DVec3 {
    DVec3::new(lat.cos() * lon.cos(), lat.sin(), -lat.cos() * lon.sin())
}

impl Projection {
    pub fn new(centre: LonLat) -> Self {
        let (lon0, lat0) = (centre.lon.to_radians(), centre.lat.to_radians());
        Self {
            lon0,
            lat0,
            up: raw(lon0, lat0),
            east: DVec3::new(-lon0.sin(), 0.0, -lon0.cos()),
            north: DVec3::new(-lat0.sin() * lon0.cos(), lat0.cos(), lat0.sin() * lon0.sin()),
        }
    }

    /// Position on the (board-rotated) unit sphere.
    pub fn sphere(&self, p: LonLat) -> DVec3 {
        let v = raw(p.lon.to_radians(), p.lat.to_radians());
        DVec3::new(v.dot(self.east), v.dot(self.up), -v.dot(self.north))
    }

    /// Equirectangular coordinates relative to the centre, in radians.
    pub fn flat(&self, p: LonLat) -> DVec2 {
        DVec2::new(p.lon.to_radians() - self.lon0, p.lat.to_radians() - self.lat0)
    }

    /// The flat board position for equirectangular coordinates.
    pub fn plane(flat: DVec2) -> DVec3 {
        DVec3::new(flat.x, 1.0, -flat.y)
    }

    /// The top surface at morph `t` (0 = curved, 1 = flat). Must match the
    /// vertex shader.
    pub fn surface(&self, p: LonLat, t: f64) -> DVec3 {
        self.sphere(p).lerp(Self::plane(self.flat(p)), t)
    }

    /// The top surface raised by `lift` board units (a hex's relief), as
    /// the vertex shader does it: `mix(sphere·(1 + lift), plane + lift·ŷ, t)`.
    pub fn surface_at(&self, p: LonLat, t: f64, lift: f64) -> DVec3 {
        self.surface(p, t) + self.sphere(p).lerp(DVec3::Y, t) * lift
    }

    /// Outward surface normal at morph `t`.
    pub fn normal(&self, p: LonLat, t: f64) -> DVec3 {
        self.sphere(p).lerp(DVec3::Y, t).normalize()
    }

    /// Inverse of [`Projection::sphere`].
    pub fn sphere_inv(&self, v: DVec3) -> LonLat {
        let p = (self.east * v.x + self.up * v.y - self.north * v.z).normalize();
        LonLat::new((-p.z).atan2(p.x).to_degrees(), p.y.clamp(-1.0, 1.0).asin().to_degrees())
    }

    /// Inverse of [`Projection::plane`] ∘ [`Projection::flat`].
    pub fn plane_inv(&self, v: DVec3) -> LonLat {
        LonLat::new((self.lon0 + v.x).to_degrees(), (self.lat0 - v.z).to_degrees())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn centre_is_on_top_and_axes_are_east_north() {
        let c = LonLat::new(24.7, 41.0);
        let p = Projection::new(c);
        assert!((p.sphere(c) - DVec3::Y).length() < 1e-12);
        let e = p.sphere(LonLat::new(c.lon + 0.01, c.lat)) - DVec3::Y;
        let n = p.sphere(LonLat::new(c.lon, c.lat + 0.01)) - DVec3::Y;
        assert!(e.x > 0.0 && e.z.abs() < 1e-6, "{e:?}");
        assert!(n.z < 0.0 && n.x.abs() < 1e-6, "{n:?}");
        // Same orientation on the flat board.
        let fe = Projection::plane(p.flat(LonLat::new(c.lon + 0.01, c.lat)));
        let fn_ = Projection::plane(p.flat(LonLat::new(c.lon, c.lat + 0.01)));
        assert!(fe.x > 0.0 && fn_.z < 0.0);
    }

    #[test]
    fn inverses() {
        let p = Projection::new(LonLat::new(24.7, 41.0));
        for ll in [LonLat::new(-16.0, 75.0), LonLat::new(65.0, 7.0), LonLat::new(24.7, 41.0)] {
            let a = p.sphere_inv(p.sphere(ll));
            let b = p.plane_inv(Projection::plane(p.flat(ll)));
            for r in [a, b] {
                assert!((r.lon - ll.lon).abs() < 1e-9 && (r.lat - ll.lat).abs() < 1e-9, "{r:?} vs {ll:?}");
            }
        }
    }
}
