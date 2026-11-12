// Terrain art: small illustrations printed on each tile (trees, peaks, dunes,
// waves), drawn from signed-distance shapes so they stay crisp at any zoom
// and need no image assets. Called from fs_board; the `T_*` terrain constants
// are generated from `neolith_core::Terrain` (see renderer::shader_source).
//
// The art is neighbour-aware: biomes creep into each other in patches along
// a noise-warped boundary, water gets foam and shallows along shores, land
// gets a beach, and mountain hexes at the edge of a range get smaller peaks
// and foothills. The same layout drives the optional 3D props (vs_prop), so
// the 2D and 3D layers put the same thing in the same place.
//
// Glyph space: hex-local coordinates (corners on the unit circle, +x east,
// +y north) with x scaled by the hex's on-board aspect, so shapes keep their
// proportions where the curved board squashes hexes east-west.

struct Art {
    albedo: vec3<f32>, // the tile's own colour (linear)
    px: f32,           // glyph-space units per pixel
    k: f32,            // layer opacity
    mono: f32,         // 1 = tonal ink only (non-terrain map modes)
    asp: f32,          // east-west squash of this hex (1 on the flat board)
    size: f32,         // glyph size factor for squashed hexes
    clip: f32,         // glyph opacity near the rim (keeps grout and outlines clear)
    blend: f32,        // 1 = soften biome edges (patchy transitions, shores)
    raised: f32,       // 1 = tall glyphs are drawn as 3D props instead (vs_prop)
    detail: f32,       // 0..1: how far the zoomed-in detail slots have filled in
};

const ART_LUMA: vec3<f32> = vec3<f32>(0.2126, 0.7152, 0.0722);
const ART_WHITE: vec3<f32> = vec3<f32>(1.0, 1.0, 1.0);

fn art_pcg(v: u32) -> u32 {
    let s = v * 747796405u + 2891336453u;
    let w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
    return (w >> 22u) ^ w;
}

fn art_hash(cell: vec2<u32>, i: u32) -> u32 {
    return art_pcg(cell.x + art_pcg(cell.y + art_pcg(i)));
}

// One byte of a hash as 0..1.
fn art_unit(h: u32, shift: u32) -> f32 {
    return f32((h >> shift) & 255u) / 255.0;
}

fn art_rgb(r: f32, g: f32, b: f32) -> vec3<f32> {
    return pow(vec3<f32>(r, g, b), vec3<f32>(2.2));
}

// In tonal mode a colour becomes a lighter or darker shade of the tile.
fn art_tone(c: vec3<f32>, a: Art) -> vec3<f32> {
    let l = dot(c, ART_LUMA);
    return mix(c, a.albedo * (0.5 + 0.95 * l), a.mono);
}

fn art_ink(base: vec3<f32>, colour: vec3<f32>, d: f32, a: Art) -> vec3<f32> {
    let cover = 1.0 - smoothstep(-0.7 * a.px, 0.7 * a.px, d);
    return mix(base, art_tone(colour, a), cover * a.k);
}

fn sd_circle(p: vec2<f32>, r: f32) -> f32 {
    return length(p) - r;
}

fn sd_box(p: vec2<f32>, half: vec2<f32>) -> f32 {
    let d = abs(p) - half;
    return max(d.x, d.y);
}

fn sd_segment(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let pa = p - a;
    let ba = b - a;
    let t = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * t);
}

// Isosceles triangle: base from (-w, 0) to (w, 0), apex at (0, h).
fn sd_tri(p: vec2<f32>, w: f32, h: f32) -> f32 {
    return max(-p.y, (abs(p.x) * h + p.y * w - w * h) * inverseSqrt(h * h + w * w));
}

// Zigzag in -0.5..0.5 with period 1.
fn art_zig(t: f32) -> f32 {
    return abs(fract(t) - 0.5) * 2.0 - 0.5;
}

// ------------------------------------------------------------- glyphs ----
// Each takes the colour so far, the point relative to the glyph's foot and a
// size, and returns the colour with the glyph painted on.

const ART_TRUNK: vec3<f32> = vec3<f32>(0.13, 0.07, 0.035);

fn art_conifer(base: vec3<f32>, p: vec2<f32>, s: f32, fill: vec3<f32>, hi: vec3<f32>, a: Art) -> vec3<f32> {
    let trunk = sd_box(p - vec2<f32>(0.0, 0.04) * s, vec2<f32>(0.018, 0.04) * s);
    var d = sd_tri(p - vec2<f32>(0.0, 0.07) * s, 0.13 * s, 0.17 * s);
    d = min(d, sd_tri(p - vec2<f32>(0.0, 0.15) * s, 0.10 * s, 0.15 * s));
    d = min(d, sd_tri(p - vec2<f32>(0.0, 0.23) * s, 0.07 * s, 0.13 * s));
    var c = art_ink(base, fill * 0.3, min(d, trunk) - 0.018 * s, a);
    c = art_ink(c, ART_TRUNK, trunk, a);
    c = art_ink(c, fill, d, a);
    // Lit west side.
    return art_ink(c, hi, max(d + 0.012 * s, p.x + 0.008 * s), a);
}

fn art_round_tree(base: vec3<f32>, p: vec2<f32>, s: f32, fill: vec3<f32>, hi: vec3<f32>, a: Art) -> vec3<f32> {
    let trunk = sd_box(p - vec2<f32>(0.0, 0.05) * s, vec2<f32>(0.018, 0.05) * s);
    var d = sd_circle(p - vec2<f32>(0.0, 0.19) * s, 0.105 * s);
    d = min(d, sd_circle(p - vec2<f32>(-0.075, 0.135) * s, 0.07 * s));
    d = min(d, sd_circle(p - vec2<f32>(0.075, 0.135) * s, 0.07 * s));
    var c = art_ink(base, fill * 0.3, min(d, trunk) - 0.018 * s, a);
    c = art_ink(c, ART_TRUNK, trunk, a);
    c = art_ink(c, fill, d, a);
    return art_ink(c, hi, sd_circle(p - vec2<f32>(-0.035, 0.215) * s, 0.05 * s), a);
}

fn art_acacia(base: vec3<f32>, p: vec2<f32>, s: f32, fill: vec3<f32>, hi: vec3<f32>, a: Art) -> vec3<f32> {
    var wood = sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(0.01, 0.18) * s) - 0.012 * s;
    wood = min(wood, sd_segment(p, vec2<f32>(0.005, 0.09) * s, vec2<f32>(-0.08, 0.18) * s) - 0.009 * s);
    let e = p - vec2<f32>(0.0, 0.205) * s;
    var d = (length(e / (vec2<f32>(0.18, 0.06) * s)) - 1.0) * 0.06 * s;
    d = max(d, -(e.y + 0.022 * s)); // flat underside
    var c = art_ink(base, fill * 0.3, min(d, wood) - 0.016 * s, a);
    c = art_ink(c, ART_TRUNK, wood, a);
    c = art_ink(c, fill, d, a);
    return art_ink(c, hi, max(d + 0.014 * s, 0.012 * s - e.y), a);
}

fn art_palm(base: vec3<f32>, p: vec2<f32>, s: f32, fill: vec3<f32>, a: Art) -> vec3<f32> {
    let top = vec2<f32>(0.03, 0.25) * s;
    let trunk = sd_segment(p, vec2<f32>(0.0, 0.0), top) - 0.013 * s;
    var d = sd_segment(p, top, vec2<f32>(-0.15, 0.20) * s);
    d = min(d, sd_segment(p, top, vec2<f32>(-0.10, 0.33) * s));
    d = min(d, sd_segment(p, top, vec2<f32>(0.03, 0.37) * s));
    d = min(d, sd_segment(p, top, vec2<f32>(0.15, 0.32) * s));
    d = min(d, sd_segment(p, top, vec2<f32>(0.18, 0.19) * s));
    d -= 0.016 * s;
    var c = art_ink(base, fill * 0.3, min(d, trunk) - 0.016 * s, a);
    c = art_ink(c, ART_TRUNK, trunk, a);
    return art_ink(c, fill, d, a);
}

fn art_shrub(base: vec3<f32>, p: vec2<f32>, s: f32, fill: vec3<f32>, hi: vec3<f32>, a: Art) -> vec3<f32> {
    var d = sd_circle(p - vec2<f32>(0.0, 0.05) * s, 0.05 * s);
    d = min(d, sd_circle(p - vec2<f32>(-0.05, 0.03) * s, 0.035 * s));
    d = min(d, sd_circle(p - vec2<f32>(0.05, 0.03) * s, 0.035 * s));
    d = max(d, -p.y);
    var c = art_ink(base, fill * 0.3, d - 0.014 * s, a);
    c = art_ink(c, fill, d, a);
    return art_ink(c, hi, sd_circle(p - vec2<f32>(-0.015, 0.06) * s, 0.024 * s), a);
}

fn art_tuft(base: vec3<f32>, p: vec2<f32>, s: f32, colour: vec3<f32>, a: Art) -> vec3<f32> {
    var d = sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(0.0, 0.085) * s);
    d = min(d, sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(-0.045, 0.06) * s));
    d = min(d, sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(0.045, 0.06) * s));
    return art_ink(base, colour, d - 0.009 * s, a);
}

fn art_mountain(base: vec3<f32>, p: vec2<f32>, s: f32, a: Art) -> vec3<f32> {
    let w = 0.42 * s;
    let h = 0.62 * s;
    let rock = art_rgb(0.57, 0.52, 0.46);
    let snow = art_rgb(0.98, 0.98, 1.0);
    let d = sd_tri(p, w, h);
    var c = art_ink(base, rock * 0.25, d - 0.02 * s, a);
    c = art_ink(c, rock, d, a);
    // Shaded east flank behind a crooked ridge line.
    let east = 0.05 * s * art_zig(p.y / (0.17 * s)) - p.x;
    c = art_ink(c, rock * 0.62, max(d, east), a);
    // Snow cap with a ragged lower edge.
    let cap = max(d, h * 0.58 + 0.06 * s * art_zig(p.x / (0.12 * s)) - p.y);
    c = art_ink(c, snow, cap, a);
    return art_ink(c, snow * vec3<f32>(0.62, 0.68, 0.80), max(cap, east), a);
}

fn art_dune(base: vec3<f32>, p: vec2<f32>, s: f32, a: Art) -> vec3<f32> {
    let centre = vec2<f32>(0.0, -0.22) * s;
    let r = 0.34 * s;
    let body = max(length(p - centre) - r, -p.y);
    var c = art_ink(base, mix(a.albedo, ART_WHITE, 0.35), body, a);
    // Lee side in shadow, split along a slanted crest.
    c = art_ink(c, a.albedo * 0.62, max(body, 0.03 * s + 0.5 * p.y - p.x), a);
    let crest = max(abs(length(p - centre) - r) - 0.011 * s, -p.y);
    return art_ink(c, a.albedo * 0.4, crest, a);
}

fn art_wave(base: vec3<f32>, p: vec2<f32>, s: f32, a: Art) -> vec3<f32> {
    let freq = 24.0 / s;
    let amp = 0.028 * s;
    let slope = amp * freq * cos(p.x * freq);
    var d = abs(p.y - amp * sin(p.x * freq)) * inverseSqrt(1.0 + slope * slope) - 0.012 * s;
    d = max(d, abs(p.x) - 0.2 * s);
    return art_ink(base, mix(a.albedo, ART_WHITE, 0.5), d, a);
}

fn art_ice(base: vec3<f32>, q: vec2<f32>, a: Art) -> vec3<f32> {
    let x = a.asp;
    let p0 = vec2<f32>(-0.34 * x, 0.30);
    let p1 = vec2<f32>(-0.06 * x, 0.10);
    let p2 = vec2<f32>(0.04 * x, -0.20);
    let p3 = vec2<f32>(0.32 * x, -0.34);
    var d = sd_segment(q, p0, p1);
    d = min(d, sd_segment(q, p1, p2));
    d = min(d, sd_segment(q, p2, p3));
    d = min(d, sd_segment(q, p1, vec2<f32>(0.28 * x, 0.22)));
    d = min(d, sd_segment(q, p2, vec2<f32>(-0.26 * x, -0.32)));
    var c = art_ink(base, a.albedo * vec3<f32>(0.55, 0.66, 0.80), d - 0.011, a);
    // Glints.
    var g = sd_segment(q, vec2<f32>(0.18 * x, -0.02), vec2<f32>(0.30 * x, 0.06));
    g = min(g, sd_segment(q, vec2<f32>(-0.36 * x, -0.06), vec2<f32>(-0.26 * x, 0.0)));
    return art_ink(c, ART_WHITE, g - 0.012, a);
}

fn art_hill(base: vec3<f32>, p: vec2<f32>, s: f32, a: Art) -> vec3<f32> {
    let fill = art_rgb(0.52, 0.53, 0.38);
    let d = max((length(p / (vec2<f32>(0.24, 0.13) * s)) - 1.0) * 0.13 * s, -p.y);
    var c = art_ink(base, fill * 0.3, d - 0.016 * s, a);
    c = art_ink(c, fill, d, a);
    return art_ink(c, fill * 0.7, max(d, 0.04 * s + 0.6 * p.y - p.x), a);
}

// ------------------------------------------------------ neighbourhood ----

// Terrain across each of the 6 edges; off-board neighbours count as `own`.
fn art_neighbours(cell: vec2<u32>, own: u32) -> array<u32, 6> {
    var nb: array<u32, 6>;
    let c = vec2<i32>(cell);
    for (var i = 0u; i < 6u; i++) {
        let nc = c + neighbour_offset(cell.x & 1u, i);
        if (nc.x >= 0 && nc.y >= 0 && nc.x < i32(g.grid.x) && nc.y < i32(g.grid.y)) {
            nb[i] = textureLoad(state_tex, nc, 0).r;
        } else {
            nb[i] = own;
        }
    }
    return nb;
}

// Landform (bits 3-4 of the state flags; see scene::LANDFORM_SHIFT).
const L_HILLS: u32 = 1u;
const L_MOUNTAINS: u32 = 2u;

fn art_landform(cell: vec2<i32>) -> u32 {
    return (textureLoad(state_tex, cell, 0).a >> 3u) & 3u;
}

// Does this hex draw as mountains? The landform says so (the biome shows
// as the tile colour under the peaks), or, in files from before landform
// existed, the old Mountains terrain. Never under water or ice.
fn art_is_mountain(terrain: u32, landform: u32) -> bool {
    return terrain == T_MOUNTAINS || (landform >= L_MOUNTAINS && terrain != T_WATER && terrain != T_ICE);
}

// Bit i set: the neighbour across edge i draws as mountains (off-board
// neighbours count as `own`).
fn art_mountain_neighbours(cell: vec2<u32>, own: bool) -> u32 {
    var m = 0u;
    let c = vec2<i32>(cell);
    for (var i = 0u; i < 6u; i++) {
        let nc = c + neighbour_offset(cell.x & 1u, i);
        var is_m = own;
        if (nc.x >= 0 && nc.y >= 0 && nc.x < i32(g.grid.x) && nc.y < i32(g.grid.y)) {
            let st = textureLoad(state_tex, nc, 0);
            is_m = art_is_mountain(st.r, (st.a >> 3u) & 3u);
        }
        if (is_m) { m |= 1u << i; }
    }
    return m;
}

// Board-wide coordinates in hex-local units, continuous across hex edges
// (rows run south, odd columns sit half a hex lower).
fn art_global(local: vec2<f32>, cell: vec2<u32>) -> vec2<f32> {
    return vec2<f32>(local.x + 1.5 * f32(cell.x), local.y - 1.7320508 * (f32(cell.y) + 0.5 * f32(cell.x & 1u)));
}

fn art_lattice(p: vec2<i32>) -> f32 {
    let h = art_pcg(bitcast<u32>(p.x) + art_pcg(bitcast<u32>(p.y)));
    return f32(h & 0xffffu) / 65535.0;
}

// Smooth value noise, 0..1.
fn art_noise(p: vec2<f32>) -> f32 {
    let cellf = floor(p);
    let f = p - cellf;
    let u = f * f * (3.0 - 2.0 * f);
    let i = vec2<i32>(cellf);
    let a = art_lattice(i);
    let b = art_lattice(i + vec2<i32>(1, 0));
    let c = art_lattice(i + vec2<i32>(0, 1));
    let d = art_lattice(i + vec2<i32>(1, 1));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Signed boundary displacement, roughly -1..1.
fn art_warp(gp: vec2<f32>) -> f32 {
    return (art_noise(gp * 2.1) * 0.75 + art_noise(gp * 4.7 + 17.0) * 0.25) * 2.0 - 1.0;
}

fn art_is_land(t: u32) -> bool {
    return t != T_WATER && t != T_ICE && t < T_COUNT;
}

// Do these two terrains creep into each other? Coasts stay crisp (they get
// foam and a beach instead), except that ice breaks up into floes.
fn art_blends(a: u32, b: u32) -> bool {
    if (a == b || a >= T_COUNT || b >= T_COUNT) {
        return false;
    }
    if (a == T_WATER || b == T_WATER) {
        return a == T_ICE || b == T_ICE;
    }
    return true;
}

// Has a neighbour's ground crept over this point? Returns the edge it came
// across in x and its coverage (0..1) in y. The boundary between two hexes
// is displaced by the same noise on both sides, so patches line up.
fn art_intrusion(p: vec2<f32>, cell: vec2<u32>, terrain: u32, nb_in: array<u32, 6>, soft: f32) -> vec2<f32> {
    var nb = nb_in;
    let w = art_warp(art_global(p, cell)) * 0.8;
    var best = -1e9;
    var edge = 0.0;
    for (var i = 0u; i < 6u; i++) {
        let u = nb[i];
        if (!art_blends(terrain, u)) { continue; }
        let v = select(-w, w, terrain < u) - (SQRT3_2 - dot(p, edge_normal(i)));
        if (v > best) {
            best = v;
            edge = f32(i);
        }
    }
    return vec2<f32>(edge, smoothstep(-soft, soft, best));
}

// Distance (hex-local) to the nearest coast edge of this hex; 9 if none.
fn art_shore(p: vec2<f32>, terrain: u32, nb_in: array<u32, 6>) -> f32 {
    var nb = nb_in;
    var d = 9.0;
    for (var i = 0u; i < 6u; i++) {
        let coast = (terrain == T_WATER && art_is_land(nb[i])) || (terrain != T_WATER && nb[i] == T_WATER);
        if (coast) {
            d = min(d, SQRT3_2 - dot(p, edge_normal(i)));
        }
    }
    return d;
}

// ------------------------------------------------------------- layout ----

// Glyph kinds. The tall ones (up to K_HILL) become props in 3D mode.
const K_NONE: u32 = 0u;
const K_CONIFER: u32 = 1u;
const K_ROUND: u32 = 2u;
const K_ACACIA: u32 = 3u;
const K_PALM: u32 = 4u;
const K_SHRUB: u32 = 5u;
const K_PEAK: u32 = 6u;
const K_HILL: u32 = 7u;
const K_TUFT: u32 = 8u;
const K_WAVE: u32 = 9u;

// What stands in one of the zoomed-in detail slots: mostly more of the
// terrain's main glyph, smaller. `h` is the slot's own hash.
fn art_kind_detail(terrain: u32, h: u32) -> u32 {
    let r = art_unit(h, 24u);
    var k = K_NONE;
    switch terrain {
        case T_BOREAL_FOREST: { k = K_CONIFER; }
        case T_TEMPERATE_FOREST: { k = select(K_ROUND, K_CONIFER, r < 0.15); }
        case T_TROPICAL_FOREST: { k = select(K_ROUND, K_PALM, r < 0.2); }
        case T_WOODLANDS: { k = select(K_TUFT, K_ROUND, r < 0.5); }
        case T_STEPPE_FOREST: { k = select(K_TUFT, K_CONIFER, r < 0.35); }
        case T_SAVANNAH: {
            if (r < 0.15) { k = K_ACACIA; } else if (r < 0.75) { k = K_TUFT; }
        }
        case T_GRASSLAND: { k = K_TUFT; }
        case T_PLAINS: { if (r < 0.5) { k = K_TUFT; } }
        case T_CHAPARRAL: { k = select(K_TUFT, K_SHRUB, r < 0.7); }
        case T_SEMI_DESERT: { if (r < 0.35) { k = K_SHRUB; } }
        case T_WATER: { if (r < 0.55) { k = K_WAVE; } }
        default: {}
    }
    return k;
}

// What stands in slot i of a hex of this terrain. `h` is the slot's hash.
fn art_kind(terrain: u32, i: u32, skip: u32, h: u32) -> u32 {
    if (i >= ART_BASE_SLOTS) {
        return art_kind_detail(terrain, h);
    }
    var k = K_NONE;
    switch terrain {
        case T_BOREAL_FOREST: { k = K_CONIFER; }
        case T_TEMPERATE_FOREST: { if (i != skip) { k = K_ROUND; } }
        case T_TROPICAL_FOREST: { k = select(K_ROUND, K_PALM, i == skip); }
        case T_WOODLANDS: {
            if (i == 1u || i == 3u) { k = K_ROUND; } else if (i != skip) { k = K_TUFT; }
        }
        case T_STEPPE_FOREST: {
            if (i == skip) { k = K_CONIFER; } else if (i != (skip + 2u) % 5u) { k = K_TUFT; }
        }
        case T_SAVANNAH: {
            if (i == 3u + (skip & 1u)) { k = K_ACACIA; } else if (i < 3u && i != skip) { k = K_TUFT; }
        }
        case T_GRASSLAND: { k = K_TUFT; }
        case T_PLAINS: { if (i != skip && i != (skip + 2u) % 5u) { k = K_TUFT; } }
        case T_CHAPARRAL: { if (i != skip) { k = K_SHRUB; } }
        case T_SEMI_DESERT: { if (i >= 2u && i != skip) { k = K_SHRUB; } }
        case T_TUNDRA: { if (i == skip) { k = K_SHRUB; } else if ((i & 1u) == 0u) { k = K_TUFT; } }
        case T_ALPINE: { if ((i & 1u) == 0u && i != skip) { k = K_TUFT; } }
        case T_WATER: { if (i >= 1u && i != 1u + (skip & 1u)) { k = K_WAVE; } }
        default: {}
    }
    return k;
}

// art_kind, with two of the base slots made hills on hilly ground.
fn art_kind_on(terrain: u32, landform: u32, i: u32, skip: u32, h: u32) -> u32 {
    if (landform == L_HILLS && terrain != T_WATER && terrain != T_ICE
        && (i == skip || i == (skip + 3u) % 5u)) {
        return K_HILL;
    }
    return art_kind(terrain, i, skip, h);
}

// Foliage colour per terrain, before gamma (see art_glyph).
fn art_fill(terrain: u32) -> vec3<f32> {
    var c = vec3<f32>(0.20, 0.46, 0.15);
    switch terrain {
        case T_BOREAL_FOREST: { c = vec3<f32>(0.09, 0.30, 0.17); }
        case T_TROPICAL_FOREST: { c = vec3<f32>(0.07, 0.36, 0.17); }
        case T_WOODLANDS: { c = vec3<f32>(0.27, 0.52, 0.16); }
        case T_STEPPE_FOREST: { c = vec3<f32>(0.14, 0.38, 0.22); }
        case T_SAVANNAH: { c = vec3<f32>(0.36, 0.44, 0.13); }
        case T_CHAPARRAL: { c = vec3<f32>(0.33, 0.38, 0.20); }
        case T_SEMI_DESERT: { c = vec3<f32>(0.42, 0.44, 0.24); }
        case T_TUNDRA: { c = vec3<f32>(0.34, 0.38, 0.28); }
        case T_ALPINE: { c = vec3<f32>(0.36, 0.40, 0.30); }
        default: {}
    }
    return c;
}

// Glyph feet inside the hex. Slots 0-4 are the base layout; slots 5-11 sit
// in the gaps and sprout as you zoom in (see art_sprout). Returns the
// jittered foot (hex-local) in xy and a size factor in z.
fn art_slot(i: u32, cell: vec2<u32>, mirror: f32) -> vec3<f32> {
    var slots = array<vec2<f32>, 12>(
        vec2<f32>(0.06, 0.08),
        vec2<f32>(-0.38, 0.0),
        vec2<f32>(0.44, -0.06),
        vec2<f32>(0.26, -0.46),
        vec2<f32>(-0.16, -0.48),
        // Detail.
        vec2<f32>(-0.20, 0.30),
        vec2<f32>(0.30, 0.28),
        vec2<f32>(-0.62, -0.22),
        vec2<f32>(0.60, -0.30),
        vec2<f32>(0.02, -0.22),
        vec2<f32>(-0.46, -0.52),
        vec2<f32>(0.12, -0.66),
    );
    let h = art_hash(cell, i + 1u);
    let jitter = (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * vec2<f32>(0.10, 0.07);
    let p = slots[i] + jitter;
    return vec3<f32>(p.x * mirror, p.y, 0.85 + 0.3 * art_unit(h, 16u));
}

// The slot drawn n-th: back (north) to front, so nearer glyphs overlap
// farther ones.
fn art_order(n: u32) -> u32 {
    var order = array<u32, 12>(5u, 6u, 0u, 1u, 2u, 7u, 9u, 8u, 3u, 4u, 10u, 11u);
    return order[n];
}

// How far slot i has grown in at detail level d (0..1). Base slots are
// always there; detail slots sprout one by one, each at its own zoom.
fn art_sprout(i: u32, cell: vec2<u32>, d: f32) -> f32 {
    if (i < ART_BASE_SLOTS) {
        return 1.0;
    }
    let start = art_unit(art_hash(cell, 80u + i), 0u) * 0.6;
    return smoothstep(start, start + 0.4, d);
}

// As the detail slots fill in, everything gets smaller to make room: trees
// most, tufts and waves a little, mountains not at all.
fn art_shrink(kind: u32, d: f32) -> f32 {
    if (kind <= K_PALM) {
        return mix(1.0, 0.62, d);
    }
    if (kind == K_PEAK || kind == K_HILL) {
        return 1.0;
    }
    return mix(1.0, 0.8, d);
}

// Is the ground under a glyph no longer this hex's own? `p` is where the
// glyph stands (hex-local).
fn art_hidden(p: vec2<f32>, cell: vec2<u32>, terrain: u32, nb: array<u32, 6>, blend: f32) -> bool {
    if (terrain == T_WATER) {
        return art_shore(p, terrain, nb) < 0.34; // open-sea waves keep off the surf
    }
    if (blend < 0.5) {
        return false;
    }
    return art_intrusion(p, cell, terrain, nb, 0.01).y > 0.5;
}

// Mountain hexes: slots 0-1 are peaks, larger deep inside a range; slots
// 2-4 are foothills towards lowland neighbours. Returns the centre
// (hex-local) in xy, a size in z and the kind in w.
fn art_mountain_slot(i: u32, cell: vec2<u32>, h0: u32, mirror: f32, nb_in: array<u32, 6>, mtn: u32) -> vec4<f32> {
    var nb = nb_in;
    if (i >= ART_BASE_SLOTS) {
        // Detail: three small crags around the main peaks.
        if (i > 7u) {
            return vec4<f32>(0.0, 0.0, 0.0, f32(K_NONE));
        }
        var extra = array<vec2<f32>, 3>(vec2<f32>(0.42, 0.30), vec2<f32>(-0.08, 0.36), vec2<f32>(-0.46, -0.16));
        let h = art_hash(cell, 30u + i);
        let p = extra[i - 5u] + (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.08;
        return vec4<f32>(p.x * mirror, p.y, 0.4 + 0.15 * art_unit(h, 16u), f32(K_PEAK));
    }
    if (i < 2u) {
        var range = 0.0;
        for (var e = 0u; e < 6u; e++) {
            if ((mtn & (1u << e)) != 0u) { range += 1.0 / 6.0; }
        }
        let j = (vec2<f32>(art_unit(h0, 8u), art_unit(h0, 16u)) - 0.5) * 0.08;
        if (i == 0u) {
            return vec4<f32>((-0.34 + j.x) * mirror, 0.08, mix(0.65, 1.05, range), f32(K_PEAK));
        }
        return vec4<f32>((0.10 + j.y) * mirror, -0.12, mix(0.95, 1.5, range), f32(K_PEAK));
    }
    let start = (h0 >> 4u) % 6u;
    var found = 2u;
    for (var k = 0u; k < 6u; k++) {
        let e = (k + start) % 6u;
        if (art_is_land(nb[e]) && (mtn & (1u << e)) == 0u) {
            if (found == i) {
                let h = art_hash(cell, 20u + i);
                let jitter = (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.18;
                return vec4<f32>(edge_normal(e) * 0.52 + jitter, 0.85 + 0.3 * art_unit(h, 16u), f32(K_HILL));
            }
            found++;
        }
    }
    return vec4<f32>(0.0, 0.0, 0.0, f32(K_NONE));
}

fn art_glyph(base: vec3<f32>, p: vec2<f32>, s: f32, kind: u32, terrain: u32, a: Art) -> vec3<f32> {
    let f = art_fill(terrain);
    let fill = pow(f, vec3<f32>(2.2));
    let hi = pow(f * 1.45 + 0.07, vec3<f32>(2.2));
    var c = base;
    switch kind {
        case K_CONIFER: { c = art_conifer(c, p, 1.7 * s, fill, hi, a); }
        case K_ROUND: { c = art_round_tree(c, p, 1.75 * s, fill, hi, a); }
        case K_ACACIA: { c = art_acacia(c, p, 1.9 * s, fill, hi, a); }
        case K_PALM: { c = art_palm(c, p, 1.8 * s, art_rgb(0.16, 0.50, 0.16), a); }
        case K_SHRUB: {
            c = art_shrub(c, p - vec2<f32>(0.0, 0.1), select(1.7, 1.2, terrain == T_SEMI_DESERT) * s, fill, hi, a);
        }
        case K_TUFT: { c = art_tuft(c, p - vec2<f32>(0.0, 0.14), 1.6 * s, a.albedo * 0.5, a); }
        case K_WAVE: { c = art_wave(c, p - vec2<f32>(0.0, 0.2), 1.25 * s, a); }
        case K_HILL: { c = art_hill(c, p + vec2<f32>(0.0, 0.06), s, a); }
        default: {}
    }
    return c;
}

fn terrain_art(local: vec2<f32>, cell: vec2<u32>, terrain: u32, a: Art) -> vec3<f32> {
    if (terrain >= T_COUNT) {
        return a.albedo;
    }
    let nb = art_neighbours(cell, terrain);
    let gp = art_global(local, cell);
    let blend = a.blend * (1.0 - a.mono);
    var c = a.albedo;

    // ---- ground: biomes creeping across edges, then the coast.
    if (blend > 0.5) {
        let hit = art_intrusion(local, cell, terrain, nb, a.px);
        if (hit.y > 0.0) {
            var n = nb;
            let other = textureLoad(palette_tex, vec2<i32>(i32(n[u32(hit.x)]), 0), 0).rgb;
            c = mix(c, saturate_colour(other), hit.y * a.k);
        }
    }
    if (a.blend > 0.5) {
        let coast = art_shore(local, terrain, nb);
        if (coast < 1.0) {
            let wobble = (art_noise(gp * 4.0) - 0.5) * 0.10;
            let d = coast + wobble;
            if (terrain == T_WATER) {
                // Shallows, a surf line on the shore and two broken foam lines.
                let shallow = (1.0 - smoothstep(0.0, 0.5, d)) * 0.55 * (1.0 - a.mono);
                c = mix(c, art_rgb(0.62, 0.90, 0.92), shallow * a.k);
                let gaps = (0.42 - art_noise(gp * 3.1 + 5.0)) * 0.12;
                c = art_ink(c, ART_WHITE, d - 0.035, a);
                var foam = a;
                foam.k = a.k * 0.8;
                c = art_ink(c, ART_WHITE, max(abs(d - 0.15) - 0.018, gaps), foam);
                foam.k = a.k * 0.5;
                c = art_ink(c, ART_WHITE, max(abs(coast + wobble * 1.7 - 0.30) - 0.013, -gaps), foam);
            } else if (terrain != T_ICE && a.mono < 0.5) {
                c = art_ink(c, art_rgb(0.93, 0.87, 0.66), d - 0.075, a); // beach
            }
        }
    }

    // ---- glyphs, kept clear of the rim.
    var ag = a;
    ag.k = a.k * a.clip;
    let h0 = art_hash(cell, 0u);
    // Mirror half the hexes so neighbours do not look stamped.
    let mirror = select(1.0, -1.0, (h0 & 1u) == 1u);
    // Glyph space: x squashed with the hex so shapes keep their proportions.
    let q = vec2<f32>(local.x * a.asp, local.y);
    let skip = (h0 >> 1u) % 5u; // the slot some terrains leave empty
    let flat_only = a.raised > 0.5;

    let landform = art_landform(vec2<i32>(cell));
    if (art_is_mountain(terrain, landform)) {
        if (flat_only) {
            return c;
        }
        let mtn = art_mountain_neighbours(cell, true);
        // Northern foothills, the peaks, then the southern foothills.
        // Crags 5 and 6 stand behind the main peaks, crag 7 in front.
        var order = array<u32, 8>(5u, 6u, 0u, 1u, 7u, 2u, 3u, 4u);
        for (var layer = 0u; layer < 3u; layer++) {
            for (var n = 0u; n < 8u; n++) {
                let i = order[n];
                let grow = art_sprout(i, cell, a.detail);
                if (grow <= 0.0) { continue; }
                let m = art_mountain_slot(i, cell, h0, mirror, nb, mtn);
                let kind = u32(m.w);
                let want = select(select(2u, 0u, m.y > 0.0), 1u, kind == K_PEAK);
                if (kind == K_NONE || want != layer) { continue; }
                let at = q - vec2<f32>(m.x * a.asp, m.y);
                if (kind == K_HILL) {
                    c = art_hill(c, at + vec2<f32>(0.0, 0.06), m.z * a.size, ag);
                } else if (!art_hidden(m.xy, cell, terrain, nb, blend)) {
                    let sz = m.z * grow;
                    c = art_mountain(c, at + vec2<f32>(0.0, 0.3 * sz), sz * a.size, ag);
                }
            }
        }
        return c;
    }
    if (terrain == T_ICE) {
        return art_ice(c, vec2<f32>(q.x * mirror, q.y), ag);
    }
    if (terrain == T_EXTREME_DESERT || terrain == T_SEMI_DESERT) {
        let s0 = art_slot(1u, cell, mirror);
        c = art_dune(c, q - vec2<f32>((s0.x + 0.12) * a.asp, s0.y + 0.12), 1.3 * s0.z * a.size, ag);
        if (terrain == T_EXTREME_DESERT) {
            let s1 = art_slot(3u, cell, mirror);
            c = art_dune(c, q - vec2<f32>((s1.x - 0.08) * a.asp, s1.y + 0.06), 1.5 * s1.z * a.size, ag);
        }
    }
    for (var n = 0u; n < ART_SLOTS; n++) {
        let i = art_order(n);
        let grow = art_sprout(i, cell, a.detail);
        if (grow <= 0.0) { continue; }
        let kind = art_kind_on(terrain, landform, i, skip, art_hash(cell, 100u + i));
        if (kind == K_NONE || (flat_only && kind <= K_HILL)) { continue; }
        let s = art_slot(i, cell, mirror);
        let sz = s.z * a.size * grow * art_shrink(kind, a.detail);
        let at = q - vec2<f32>(s.x * a.asp, s.y);
        // Every glyph fits in this circle; skip the work for pixels outside.
        if (length(at - vec2<f32>(0.0, 0.55 * sz)) > 0.7 * sz + 2.0 * a.px) { continue; }
        if (art_hidden(s.xy + vec2<f32>(0.0, 0.15), cell, terrain, nb, blend)) { continue; }
        c = art_glyph(c, at, sz, kind, terrain, ag);
    }
    return c;
}

// -------------------------------------------------------------- props ----
// The 3D layer: the tall glyphs as low-poly solids standing on the board.
// One template mesh (5 slots x 3 bands of a 5-sided lathe) is instanced per
// hex; this vertex shader decides from the hex's terrain and neighbours
// what each slot is, and collapses the slots and bands that are unused.

struct PropIn {
    @location(0) attrs: vec4<u32>,   // slot, band, end (0 bottom, 1 top), side
    @location(1) centre: vec3<f32>,  // hex centre on the unit sphere
    @location(2) east: vec3<f32>,    // sphere offset to the east corner (local x = 1)
    @location(3) north: vec3<f32>,   // sphere offset to the north edge (local y = sqrt(3)/2)
    @location(4) flat_pos: vec2<f32>,
    @location(5) cell: vec2<u32>,
};

struct PropOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world: vec3<f32>,
    @location(1) colour: vec3<f32>,
};

// One band of a prop's profile: (bottom radius, bottom height, top radius,
// top height) in hex-local units. All zero = unused.
fn art_profile(kind: u32, band: u32) -> vec4<f32> {
    var bands = array<vec4<f32>, 21>(
        // conifer: trunk, skirt, top
        vec4<f32>(0.035, 0.0, 0.035, 0.09), vec4<f32>(0.19, 0.08, 0.07, 0.30), vec4<f32>(0.14, 0.26, 0.0, 0.55),
        // round tree: trunk, lower crown, upper crown
        vec4<f32>(0.035, 0.0, 0.035, 0.16), vec4<f32>(0.09, 0.13, 0.19, 0.29), vec4<f32>(0.19, 0.29, 0.0, 0.50),
        // acacia: trunk, flat crown
        vec4<f32>(0.03, 0.0, 0.03, 0.25), vec4<f32>(0.08, 0.23, 0.27, 0.31), vec4<f32>(0.27, 0.31, 0.0, 0.39),
        // palm: trunk, drooping fronds
        vec4<f32>(0.035, 0.0, 0.025, 0.42), vec4<f32>(0.25, 0.35, 0.0, 0.50), vec4<f32>(0.0),
        // shrub
        vec4<f32>(0.10, 0.0, 0.085, 0.06), vec4<f32>(0.085, 0.06, 0.0, 0.12), vec4<f32>(0.0),
        // peak: rock, snow
        vec4<f32>(0.46, 0.0, 0.20, 0.38), vec4<f32>(0.20, 0.38, 0.0, 0.64), vec4<f32>(0.0),
        // hill
        vec4<f32>(0.30, 0.0, 0.17, 0.10), vec4<f32>(0.17, 0.10, 0.0, 0.15), vec4<f32>(0.0),
    );
    return bands[(kind - 1u) * 3u + band];
}

fn art_prop_colour(kind: u32, band: u32, top: bool, terrain: u32) -> vec3<f32> {
    let f = art_fill(terrain);
    var c = pow(mix(f, f * 1.45 + 0.07, f32(band) * 0.5 - 0.25), vec3<f32>(2.2));
    if (kind == K_PEAK) {
        c = select(art_rgb(0.57, 0.52, 0.46), art_rgb(0.98, 0.98, 1.0), band == 1u);
    } else if (kind == K_HILL) {
        c = art_rgb(0.52, 0.53, 0.38);
    } else if (kind == K_PALM && band == 1u) {
        c = art_rgb(0.16, 0.50, 0.16);
    } else if (band == 0u && kind != K_SHRUB) {
        c = art_rgb(0.42, 0.28, 0.16); // trunk
    }
    return c * select(0.82, 1.08, top);
}

@vertex
fn vs_prop(in: PropIn) -> PropOut {
    var out: PropOut;
    // Outside the clip volume: every vertex of an unused prop lands here.
    out.clip = vec4<f32>(2.0, 2.0, 2.0, 1.0);
    out.world = vec3<f32>(0.0);
    out.colour = vec3<f32>(0.0);

    let t = g.cam_pos.w;
    // World length of one hex-local unit, curved and flat.
    let unit_c = length(in.north) / SQRT3_2;
    let unit_f = g.hex.y / SQRT3_2;
    let centre = mix(in.centre, vec3<f32>(in.flat_pos.x, 1.0, -in.flat_pos.y), t);
    // Props shrink away as the hex gets small on screen.
    let hex_px = mix(unit_c, unit_f, t) * g.art.z / max(distance(g.cam_pos.xyz, centre), 1e-6);
    let lod = smoothstep(5.0, 11.0, hex_px) * g.art.y;
    if (lod <= 0.0) {
        return out;
    }
    let slot = in.attrs.x;
    // Zoomed in, the detail slots sprout (same rule as the 2D layer).
    let detail = smoothstep(ART_DETAIL_LO, ART_DETAIL_HI, hex_px);
    let grow = art_sprout(slot, in.cell, detail);
    if (grow <= 0.0) {
        return out;
    }

    let st = textureLoad(state_tex, vec2<i32>(in.cell), 0);
    let terrain = st.r;
    if (terrain >= T_COUNT || terrain == T_WATER) {
        return out;
    }
    let band = in.attrs.y;
    let top = in.attrs.z == 1u;
    let h0 = art_hash(in.cell, 0u);
    let mirror = select(1.0, -1.0, (h0 & 1u) == 1u);
    let mode = u32(g.grid.z);
    let blend = g.art.w * f32(mode == 0u);
    let nb = art_neighbours(in.cell, terrain);

    var kind = K_NONE;
    var at = vec2<f32>(0.0);
    var size = 1.0;
    let landform = (st.a >> 3u) & 3u;
    if (art_is_mountain(terrain, landform)) {
        let m = art_mountain_slot(slot, in.cell, h0, mirror, nb, art_mountain_neighbours(in.cell, true));
        kind = u32(m.w);
        at = m.xy;
        size = m.z;
    } else {
        kind = art_kind_on(terrain, landform, slot, (h0 >> 1u) % 5u, art_hash(in.cell, 100u + slot));
        let s = art_slot(slot, in.cell, mirror);
        at = s.xy + vec2<f32>(0.0, 0.15);
        size = s.z * 1.45;
    }
    if (kind == K_NONE || kind > K_HILL) {
        return out;
    }
    if (kind != K_HILL && art_hidden(at, in.cell, terrain, nb, blend)) {
        return out;
    }
    let prof = art_profile(kind, band);
    if (prof.x + prof.z <= 0.0) {
        return out;
    }

    // Squashed hexes get smaller props, as in the 2D layer.
    let asp = mix(min(length(in.east) / unit_c, 1.0), 1.0, t);
    size *= sqrt(asp) * lod * grow * art_shrink(kind, detail);
    let hs = art_hash(in.cell, 40u + slot);
    var r = select(prof.x, prof.z, top) * size;
    let h = select(prof.y, prof.w, top) * size;
    if (kind == K_PEAK || kind == K_HILL) {
        // Craggy: each side of the lathe has its own radius.
        r *= 0.78 + 0.44 * art_unit(art_hash(in.cell, 60u + slot * 8u + in.attrs.w), 0u);
    }
    let ang = (f32(in.attrs.w) + art_unit(hs, 0u)) * 1.2566371;
    let ring = vec2<f32>(cos(ang), sin(ang)) * r;

    // Standing on the hex's tile, raised by the relief.
    let lift = hex_lift(vec2<i32>(in.cell));
    let curved = in.centre * (1.0 + lift) + in.east * at.x + in.north * (at.y / SQRT3_2)
        + (normalize(in.east) * ring.x + normalize(in.north) * ring.y + normalize(in.centre) * h) * unit_c;
    let flat_p = vec3<f32>(
        in.flat_pos.x + g.hex.x * at.x + ring.x * unit_f,
        1.0 + lift + h * unit_f,
        -(in.flat_pos.y + g.hex.y * at.y / SQRT3_2 + ring.y * unit_f),
    );
    let world = mix(curved, flat_p, t);

    var colour = art_prop_colour(kind, band, top, terrain);
    if (mode != 0u) {
        // Other map modes: a shade of the hex's own colour.
        let albedo = saturate_colour(textureLoad(palette_tex, vec2<i32>(i32(layer_value(st, vec2<i32>(in.cell), mode)), i32(mode)), 0).rgb);
        colour = albedo * (0.5 + 0.95 * dot(colour, ART_LUMA));
    }
    out.clip = g.view_proj * vec4<f32>(world, 1.0);
    out.world = world;
    out.colour = colour;
    return out;
}

@fragment
fn fs_prop(in: PropOut) -> @location(0) vec4<f32> {
    // Faceted: the face normal comes from the derivatives.
    var n = normalize(cross(dpdx(in.world), dpdy(in.world)));
    if (dot(n, g.cam_pos.xyz - in.world) < 0.0) {
        n = -n;
    }
    return vec4<f32>(in.colour * lighting(n), 1.0);
}
