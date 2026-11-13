//! The relief texture: the world's heightmap ([`neolith_core::Heightmap`])
//! resampled into board-wide hex-local coordinates (terrain_art.wgsl
//! `art_global`), so fs_board can look a height up from where it is on the
//! board without knowing longitude or latitude. One R16Float texel per
//! 1 / [`TEXELS_PER_UNIT`] of a hex-local unit (corners are 1 from a hex's
//! centre); the GPU filters between them.

use neolith_core::{GridSpec, Heightmap, LonLat};

/// Texels per hex-local unit: a hex's corner radius is 0.29° of longitude,
/// so 4 is a little finer than the 0.1° heightmap.
pub const TEXELS_PER_UNIT: f32 = 4.0;

/// The texture and where it sits: texel (i, j) is centred on art_global
/// `(x0 + (i + 0.5) / k, y0 - (j + 0.5) / k)`.
#[derive(Clone, Debug, PartialEq)]
pub struct Heightfield {
    pub width: u32,
    pub height: u32,
    pub x0: f32,
    pub y0: f32,
    /// Metres as IEEE half floats, row-major from the top (north).
    pub texels: Vec<u16>,
}

impl Heightfield {
    /// The relief uniform for board.wgsl: x0, y0, texels per unit, 1 (on).
    pub fn uniform(&self) -> [f32; 4] {
        [self.x0, self.y0, TEXELS_PER_UNIT, 1.0]
    }
}

/// Longitude and latitude of art_global `(x, y)` on `grid`: hex (0, 0)'s
/// centre plus x half-widths east and y (in units of √3/2 half-heights)
/// north, as `art_global` lays them out.
fn lon_lat(grid: &GridSpec, x: f64, y: f64) -> LonLat {
    let c = grid.centre(grid.id_at(0, 0));
    LonLat::new(c.lon + x * grid.w / 2.0, c.lat + y * (grid.h / 2.0) / (3f64.sqrt() / 2.0))
}

/// The texture's size for a grid of `cols` x `rows` hexes: art_global
/// spans x from -1 (west of column 0) to 1.5 (cols - 1) + 1, and y from +1
/// (north of row 0) down to -√3 (rows - 0.5) - 1.
pub fn size(cols: u32, rows: u32) -> [u32; 2] {
    let k = TEXELS_PER_UNIT as f64;
    let x1 = 1.5 * (cols as f64 - 1.0) + 1.0;
    let y1 = -(3f64.sqrt() * (rows as f64 - 0.5)) - 1.0;
    [((x1 + 1.0) * k).ceil() as u32, ((1.0 - y1) * k).ceil() as u32]
}

pub fn build(grid: &GridSpec, map: &Heightmap) -> Heightfield {
    let k = TEXELS_PER_UNIT as f64;
    let (x0, y0) = (-1.0, 1.0);
    let [width, height] = size(grid.cols as u32, grid.rows as u32);
    let mut texels = Vec::with_capacity((width * height) as usize);
    for j in 0..height {
        for i in 0..width {
            let p = lon_lat(grid, x0 + (i as f64 + 0.5) / k, y0 - (j as f64 + 0.5) / k);
            texels.push(f16_bits(map.at(p).unwrap_or(0.0) as f32));
        }
    }
    Heightfield { width, height, x0: x0 as f32, y0: y0 as f32, texels }
}

/// IEEE 754 half-float bits of `v` (round to nearest; heights are far from
/// the range limits).
pub fn f16_bits(v: f32) -> u16 {
    let b = v.to_bits();
    let sign = ((b >> 16) & 0x8000) as u16;
    let exp = ((b >> 23) & 0xff) as i32 - 127 + 15;
    let mant = b & 0x7f_ffff;
    if v == 0.0 || exp <= 0 {
        return sign;
    }
    if exp >= 31 {
        return sign | 0x7c00;
    }
    let half = sign | ((exp as u16) << 10) | (mant >> 13) as u16;
    // Round to nearest on the dropped bits.
    half + ((mant >> 12) & 1) as u16
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn half_floats() {
        assert_eq!(f16_bits(0.0), 0);
        assert_eq!(f16_bits(1.0), 0x3c00);
        assert_eq!(f16_bits(-2.0), 0xc000);
        assert_eq!(f16_bits(2048.0), 0x6800);
        // Mont Blanc's height comes back within half a step (2 m up there).
        assert!((half_to_f32(f16_bits(4810.0)) - 4810.0).abs() <= 2.0);
    }

    #[test]
    fn texels_follow_the_heightmap_under_each_hex() {
        let grid = GridSpec { cols: 4, rows: 3, origin_lon: 10.0, origin_lat: 50.0, w: 0.5773502691896262, h: 0.5 };
        // Heights rising 100 m per degree east.
        let (w, s, e, n) = grid.bounds();
        let (cols, rows) = ((((e - w) / 0.1).ceil() + 2.0) as u32, (((n - s) / 0.1).ceil() + 2.0) as u32);
        let west = w - 0.1;
        let z = (0..rows).flat_map(|_| (0..cols).map(move |c| ((west + (c as f64 + 0.5) * 0.1 - 10.0) * 100.0) as i16)).collect();
        let map = Heightmap { west, north: n + 0.1, cell: 0.1, cols, rows, z };
        let f = build(&grid, &map);
        assert_eq!(f.texels.len(), (f.width * f.height) as usize);
        // The texel nearest a hex centre carries about the height there.
        let id = grid.id_at(2, 1);
        let c = grid.centre(id);
        let x = 1.5 * 2.0;
        let y = -(3f64.sqrt() * (1.0 + 0.5 * 0.0));
        let (i, j) = (((x - f.x0 as f64) * 4.0) as u32, ((f.y0 as f64 - y) * 4.0) as u32);
        let got = f.texels[(j * f.width + i) as usize];
        let want = map.at(c).unwrap();
        let back = half_to_f32(got);
        assert!((back as f64 - want).abs() < 15.0, "{back} vs {want}");
    }

    fn half_to_f32(h: u16) -> f32 {
        let exp = ((h >> 10) & 0x1f) as i32;
        let mant = (h & 0x3ff) as f32;
        if exp == 0 {
            return 0.0;
        }
        let v = (1.0 + mant / 1024.0) * 2f32.powi(exp - 15);
        if h & 0x8000 != 0 { -v } else { v }
    }
}
