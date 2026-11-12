//! Small geometry helpers shared by the tools and the app.

/// Even-odd point-in-polygon test. The polygon is implicitly closed.
pub fn point_in_polygon(poly: &[[f64; 2]], p: [f64; 2]) -> bool {
    let n = poly.len();
    if n < 3 {
        return false;
    }
    let mut inside = false;
    let mut j = n - 1;
    for i in 0..n {
        let (xi, yi) = (poly[i][0], poly[i][1]);
        let (xj, yj) = (poly[j][0], poly[j][1]);
        if (yi > p[1]) != (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi {
            inside = !inside;
        }
        j = i;
    }
    inside
}

/// Great-circle distance in km between two (lon, lat) points in degrees.
pub fn great_circle_km(a: [f64; 2], b: [f64; 2]) -> f64 {
    let (lon1, lat1, lon2, lat2) = (a[0].to_radians(), a[1].to_radians(), b[0].to_radians(), b[1].to_radians());
    let h = ((lat2 - lat1) / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * ((lon2 - lon1) / 2.0).sin().powi(2);
    2.0 * 6371.0 * h.sqrt().min(1.0).asin()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn great_circle() {
        assert!((great_circle_km([0.0, 0.0], [0.0, 90.0]) - std::f64::consts::FRAC_PI_2 * 6371.0).abs() < 1e-6);
        assert!((great_circle_km([0.0, 60.0], [1.0, 60.0]) - 55.6).abs() < 0.1);
        assert_eq!(great_circle_km([12.0, 34.0], [12.0, 34.0]), 0.0);
    }

    #[test]
    fn square_and_concave() {
        let sq = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]];
        assert!(point_in_polygon(&sq, [1.0, 1.0]));
        assert!(!point_in_polygon(&sq, [3.0, 1.0]));
        assert!(!point_in_polygon(&sq[..2], [1.0, 0.0]));
        // A "U" shape: the notch is outside.
        let u = [[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [2.0, 3.0], [2.0, 1.0], [1.0, 1.0], [1.0, 3.0], [0.0, 3.0]];
        assert!(point_in_polygon(&u, [0.5, 2.0]));
        assert!(!point_in_polygon(&u, [1.5, 2.0]));
        assert!(point_in_polygon(&u, [1.5, 0.5]));
    }
}
