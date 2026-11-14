// Terrain art. Trees, shrubs, peaks and hills stand on the board as
// low-poly 3D props (vs_prop); the low details are printed on the tiles
// (tufts, waves, dunes, ice, shores, the ground itself and the props'
// shadows), drawn from signed-distance shapes so they stay crisp at any
// zoom and need no image assets. The printing is called from fs_board; the `T_*` terrain constants
// are generated from `neolith_core::Terrain` (see renderer::shader_source).
//
// The art is neighbour-aware: biomes creep into each other in patches along
// a noise-warped boundary, water gets foam and shallows along shores, land
// gets a beach, and mountain hexes at the edge of a range get smaller peaks
// and foothills. One baked layout drives both the props and the printed
// details, so a prop's shadow falls where it stands.
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
    detail: f32,       // 0..1: how far the zoomed-in detail slots have filled in
    sun: vec2<f32>,    // where a shadow falls, in glyph space, per unit of height
    lod: f32,          // the props' size factor at this zoom (as in vs_prop)
    field: f32,        // 1 = fs_board's ground field drew the colour and the coast
    shore: f32,        // with the field: distance (hex-local) to the drawn coast; 9 if none near
    own: f32,          // with the field: 1 if this point draws the hex's own terrain
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

fn art_tuft(base: vec3<f32>, p: vec2<f32>, s: f32, colour: vec3<f32>, a: Art) -> vec3<f32> {
    var d = sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(0.0, 0.085) * s);
    d = min(d, sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(-0.045, 0.06) * s));
    d = min(d, sd_segment(p, vec2<f32>(0.0, 0.0), vec2<f32>(0.045, 0.06) * s));
    return art_ink(base, colour, d - 0.009 * s, a);
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

// `h` varies the wave: its length, pitch, height, phase and strength, so a
// sea of them does not look stamped.
fn art_wave(base: vec3<f32>, p: vec2<f32>, s: f32, h: u32, a: Art) -> vec3<f32> {
    let freq = mix(17.0, 30.0, art_unit(h, 0u)) / s;
    let amp = mix(0.016, 0.030, art_unit(h, 8u)) * s;
    let reach_x = mix(0.10, 0.25, art_unit(h, 16u)) * s;
    let x = p.x * freq + art_unit(h, 24u) * 6.2831853;
    let slope = amp * freq * cos(x);
    // Thick in the middle, tapering to points.
    let u = clamp(abs(p.x) / reach_x, 0.0, 1.0);
    var d = abs(p.y - amp * sin(x)) * inverseSqrt(1.0 + slope * slope) - 0.013 * s * (1.0 - u * u);
    d = max(d, abs(p.x) - reach_x);
    var w = a;
    w.k = a.k * mix(0.45, 1.0, art_unit(h, 4u));
    return art_ink(base, mix(a.albedo, ART_WHITE, 0.5), d, w);
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

// -------------------------------------------------------------- rivers ----
// Where the channels are (lines::river_field): a raster over the grid in
// art_global coordinates. rg: offset from the texel's centre to the nearest
// centreline point over RIVER_REACH (-1..1 as 0..1), b: the channel's half
// width over RIVER_HALF_MAX, a: 0 no river in reach, 0.5 seasonal, 1 perennial.
@group(0) @binding(9) var river_tex: texture_2d<f32>;

// A slot this close (hex-local) to a river bed's edge stands in it: nothing
// grows there. Out to RIVER_BANK it is on the bank (see art_riparian).
const RIVER_CLEAR: f32 = 0.04;
const RIVER_BANK: f32 = 0.42;

// The nearest channel to `gp` (art_global): x: distance to its centreline
// (9 when none is in reach), y: its half width, z: 0 none, 0.5 seasonal,
// 1 perennial. Each of the four texels around `gp` knows a point of a
// centreline; the distance is to the line through the nearest two, which
// is exact along a straight reach, also for points on the channel.
fn art_river(gp: vec2<f32>) -> vec3<f32> {
    let dims = vec2<i32>(textureDimensions(river_tex));
    let texel = (1.5 * (g.grid.x - 1.0) + 2.0) / f32(dims.x);
    let uv = vec2<f32>(gp.x + 1.0, SQRT3_2 - gp.y) / texel - 0.5;
    let base = vec2<i32>(floor(uv));
    var d0 = 9.0;
    var d1 = 9.0;
    var q0 = vec2<f32>(0.0);
    var q1 = vec2<f32>(0.0);
    var info = vec2<f32>(0.0);
    for (var k = 0; k < 4; k++) {
        let ij = clamp(base + vec2<i32>(k & 1, k >> 1), vec2<i32>(0), dims - 1);
        let e = textureLoad(river_tex, ij, 0);
        if (e.a < 0.25) { continue; }
        let centre = vec2<f32>((f32(ij.x) + 0.5) * texel - 1.0, SQRT3_2 - (f32(ij.y) + 0.5) * texel);
        let q = centre + (e.xy * 2.0 - 1.0) * RIVER_REACH;
        let d = distance(gp, q);
        if (d < d0) {
            d1 = d0;
            q1 = q0;
            d0 = d;
            q0 = q;
            info = e.ba;
        } else if (d < d1) {
            d1 = d;
            q1 = q;
        }
    }
    if (d0 > 8.0) {
        return vec3<f32>(9.0, 0.0, 0.0);
    }
    var d = d0;
    let along = q1 - q0;
    let chord = length(along);
    // Two points of the same reach (not of two rivers side by side).
    if (d1 < 8.0 && chord > 0.03 && chord < 2.5 * texel) {
        let to = gp - q0;
        d = abs(to.x * along.y - to.y * along.x) / chord;
    }
    return vec3<f32>(d, info.x * RIVER_HALF_MAX, info.y);
}

// How the ground at `gp` stands to the nearest river: x: distance past the
// edge of its bed (negative on the bed), y: as art_river's z.
fn art_bank(gp: vec2<f32>) -> vec2<f32> {
    let r = art_river(gp);
    return vec2<f32>(r.x - r.y * RIVER_BED, r.z);
}

// ------------------------------------------------------------- gorges ----
// The water level at each river field texel's centreline point, metres
// (lines::RiverField::level): a river only runs downhill, so where the
// ground rises across its course the board is cut down to it.
@group(0) @binding(15) var level_tex: texture_2d<i32>;

// The gorge's floor reaches this far (hex-local) from the centreline, at
// least, and out past the bed's edge by GORGE_MARGIN; its walls rise to the
// full ground by GORGE_OUT (inside the field's reach, RIVER_REACH).
const GORGE_FLOOR: f32 = 0.26;
const GORGE_MARGIN: f32 = 0.09;
const GORGE_OUT: f32 = 0.72;

// How the ground at `gp` (art_global) is cut towards the nearest river's
// water level: x the level (board units), y the share of the ground's height
// above it that is kept (0 on the gorge floor, 1 beyond the walls). Only on
// the smooth board (edge blending); the river ribbons run at the same level
// (lines::water_levels).
fn art_carve(gp: vec2<f32>) -> vec2<f32> {
    let dims = vec2<i32>(textureDimensions(river_tex));
    let texel = (1.5 * (g.grid.x - 1.0) + 2.0) / f32(dims.x);
    let uv = vec2<f32>(gp.x + 1.0, SQRT3_2 - gp.y) / texel - 0.5;
    let base = vec2<i32>(floor(uv));
    var d0 = 9.0;
    var half = 0.0;
    var at = vec2<i32>(0);
    for (var k = 0; k < 4; k++) {
        let ij = clamp(base + vec2<i32>(k & 1, k >> 1), vec2<i32>(0), dims - 1);
        let e = textureLoad(river_tex, ij, 0);
        if (e.a < 0.25) { continue; }
        let centre = vec2<f32>((f32(ij.x) + 0.5) * texel - 1.0, SQRT3_2 - (f32(ij.y) + 0.5) * texel);
        let d = distance(gp, centre + (e.xy * 2.0 - 1.0) * RIVER_REACH);
        if (d < d0) {
            d0 = d;
            half = e.b * RIVER_HALF_MAX;
            at = ij;
        }
    }
    if (d0 > 8.0) {
        return vec2<f32>(0.0, 1.0);
    }
    let level = f32(textureLoad(level_tex, at, 0).r) * g.hex.z;
    let floor_r = min(max(GORGE_FLOOR, half * RIVER_BED + GORGE_MARGIN), GORGE_OUT - 0.2);
    return vec2<f32>(level, smoothstep(floor_r, GORGE_OUT, d0));
}

// What grows in a slot on a river bank instead of `kind`. Trees stay. Open
// ground gets a gallery of trees (palms in the desert) and reeds; a seasonal
// wash or cold ground only scrub. `h` is the slot's hash, `wet` art_bank's y.
fn art_riparian(kind: u32, terrain: u32, h: u32, wet: f32) -> u32 {
    if (terrain == T_ICE || (kind >= K_CONIFER && kind <= K_PALM) || kind == K_HILL) {
        return kind;
    }
    let r = art_unit(h, 8u);
    if (wet < 0.75 || terrain == T_TUNDRA || terrain == T_ALPINE) {
        return select(K_TUFT, K_SHRUB, r < 0.45);
    }
    if (r < 0.55) {
        let arid = terrain == T_EXTREME_DESERT || terrain == T_SEMI_DESERT;
        return select(K_ROUND, K_PALM, arid || (terrain == T_SAVANNAH && r < 0.2));
    }
    return K_TUFT; // reeds
}

// --------------------------------------------------------------- camps ----
// The settlements in and around each hex (scene::camp_texels), 2 x 2 texels
// per hex filled from the first. rg: the camp in this hex's local
// coordinates over CAMP_SPAN (-1..1 as 0..1), b: its clearing's radius over
// CAMP_RADIUS_MAX in the low 7 bits, plus 128 for a farming site with
// fields round it, a: 0 for no camp, else the hex's east-west squash (a
// clearing is round on the board, so wider in hex-local x where hexes are
// squashed).
@group(0) @binding(10) var camp_tex: texture_2d<f32>;

// A camp entry's clearing radius (hex-local) and whether it has fields.
fn art_camp_radius(z: f32) -> vec2<f32> {
    let b = u32(round(z * 255.0));
    return vec2<f32>(f32(b & 127u) / 127.0 * CAMP_RADIUS_MAX, f32(b >> 7u));
}

// How far `p` (hex-local, in `cell`) is from the nearest camp, in clearing
// radii: under 1 is in a clearing. 9 when the hex has no camp.
fn art_camp(p: vec2<f32>, cell: vec2<u32>) -> f32 {
    var best = 9.0;
    for (var k = 0u; k < 4u; k++) {
        let e = textureLoad(camp_tex, vec2<i32>(cell * 2u + vec2<u32>(k & 1u, k >> 1u)), 0);
        if (e.a <= 0.0) { break; }
        let to = (p - (e.xy * 2.0 - 1.0) * CAMP_SPAN) * vec2<f32>(e.a, 1.0);
        best = min(best, length(to) / max(art_camp_radius(e.z).x, 1e-3));
    }
    return best;
}

// How far out a farming site's fields reach, in clearing radii.
const FIELD_RING: f32 = 2.6;
// The share of that ring under plots; the rest stays as it was (woods
// in a forest), so the fields are a few patches, not a cleared belt.
const FIELD_SHARE: f32 = 0.55;

// How much of the ground at `p` (hex-local, in `cell`) is under a field
// plot (0..1, soft-edged): a few small plots in the ring just outside a
// farming site's clearing. Trees and undergrowth keep off the plots.
fn art_field(p: vec2<f32>, cell: vec2<u32>) -> f32 {
    var near = 9.0;
    for (var k = 0u; k < 4u; k++) {
        let e = textureLoad(camp_tex, vec2<i32>(cell * 2u + vec2<u32>(k & 1u, k >> 1u)), 0);
        if (e.a <= 0.0) { break; }
        let r = art_camp_radius(e.z);
        if (r.y < 0.5) { continue; }
        let to = (p - (e.xy * 2.0 - 1.0) * CAMP_SPAN) * vec2<f32>(e.a, 1.0);
        near = min(near, length(to) / max(r.x, 1e-3));
    }
    if (near >= FIELD_RING) {
        return 0.0;
    }
    let gp = art_global(p, cell);
    // Thicker close in, thinning out to the ring's ragged edge.
    let cover = FIELD_SHARE * (1.0 - smoothstep(FIELD_RING * 0.55, FIELD_RING, near + (art_noise(gp * 3.1 + 17.0) - 0.5) * 0.6));
    let plot = art_noise(gp * 4.6 + 101.0) * 0.7 + art_noise(gp * 9.3 + 131.0) * 0.3;
    return smoothstep(1.0 - cover - 0.06, 1.0 - cover + 0.06, plot);
}

// ------------------------------------------------------------- history ----
// What people have done to each hex (scene::history_texels). Bound but no
// longer drawn from: people don't thin the woods, they clear round their
// sites (art_camp) and farm a few plots there (art_field).
@group(0) @binding(11) var history_tex: texture_2d<f32>;

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

// ----------------------------------------------------------- groves ----
// In wooded biomes a base slot's tree is drawn as a grove: a tight clump of
// three crowns with no trunks (one per band of the lathe, art_grove_profile
// and art_grove_crown), wide enough that the clumps of a hex and its
// neighbours run together into tree cover. The
// detail slots that sprout close up stay single trees, poking out of it.
// Flagged in prop_tex x (K_GROVE_BIT) and in art_tex x (ART_GROVE_BIT, as
// bits 8-15 there hold the slot).
const K_GROVE_BIT: u32 = 0x100u;
const ART_GROVE_BIT: u32 = 0x10000u;

// How big this biome's groves are (0: none, single trees).
fn art_grove_terrain(terrain: u32) -> f32 {
    var s = 0.0;
    switch terrain {
        case T_BOREAL_FOREST, T_TEMPERATE_FOREST, T_TROPICAL_FOREST: { s = 1.0; }
        // Copses, forest-steppe islands, gallery woods.
        case T_WOODLANDS, T_STEPPE_FOREST, T_FLOODPLAIN: { s = 0.78; }
        default: {}
    }
    return s;
}

fn art_is_grove(terrain: u32, slot: u32, kind: u32) -> bool {
    return slot < ART_BASE_SLOTS && (kind == K_CONIFER || kind == K_ROUND || kind == K_PALM)
        && art_grove_terrain(terrain) > 0.0;
}

// Crown `band` of a grove, as art_profile (a cone from a ring just off the
// ground to its top): the big middle crown, then two smaller ones beside
// it. Conifer stands are clumps of spires; broadleaf ones low and round.
fn art_grove_profile(kind: u32, band: u32) -> vec4<f32> {
    var bands = array<vec4<f32>, 9>(
        // conifer
        vec4<f32>(0.18, 0.03, 0.0, 0.52), vec4<f32>(0.16, 0.03, 0.0, 0.42), vec4<f32>(0.15, 0.03, 0.0, 0.37),
        // broadleaf
        vec4<f32>(0.26, 0.04, 0.0, 0.32), vec4<f32>(0.23, 0.04, 0.0, 0.27), vec4<f32>(0.22, 0.04, 0.0, 0.24),
        // tropical (palm slot): taller, fuller
        vec4<f32>(0.27, 0.05, 0.0, 0.40), vec4<f32>(0.24, 0.05, 0.0, 0.34), vec4<f32>(0.23, 0.05, 0.0, 0.31),
    );
    let k = select(select(2u, 1u, kind == K_ROUND), 0u, kind == K_CONIFER);
    return bands[k * 3u + band];
}

// Where crown `band` of a grove stands from the slot's foot, in profile
// units (times the prop's size): the big one a little off centre, the other
// two around it, the clump turned by `turn` (0..1).
fn art_grove_crown(kind: u32, band: u32, turn: f32) -> vec2<f32> {
    let reach = select(0.21, 0.16, kind == K_CONIFER);
    let d = select(reach, 0.05, band == 0u);
    let a = (turn + f32(band) / 3.0 + select(0.0, 0.08, band == 2u)) * 6.2831853;
    return vec2<f32>(cos(a), sin(a)) * d;
}

fn art_dims(kind: u32, grove: bool) -> vec2<f32> {
    if (grove) {
        let p = art_grove_profile(kind, 1u);
        let reach = select(0.21, 0.16, kind == K_CONIFER);
        return vec2<f32>(reach + p.x, art_grove_profile(kind, 0u).w);
    }
    return art_prop_dims(kind);
}

// A grove's size factor at `foot` (hex-local) for a prop of size `size`:
// the biome's grove size, cut back where its rim would reach over a river
// bed or into a camp's clearing.
fn art_grove_size(terrain: u32, kind: u32, foot: vec2<f32>, size: f32, cell: vec2<u32>) -> f32 {
    let s = art_grove_terrain(terrain);
    let rim = art_dims(kind, true).x * size * s;
    let room = art_obstacle(foot, cell, rim + 0.05).x;
    return s * clamp(room / max(rim, 1e-4), 0.45, 1.0);
}

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
        case T_FLOODPLAIN: { k = select(K_TUFT, K_ROUND, r < 0.2); }
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
        case T_TEMPERATE_FOREST: { k = K_ROUND; }
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
        case T_FLOODPLAIN: { if (i == skip) { k = K_ROUND; } else { k = K_TUFT; } }
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
        case T_FLOODPLAIN: { c = vec3<f32>(0.22, 0.50, 0.14); }
        default: {}
    }
    return c;
}

// Glyph feet inside the hex. Slots 0-4 are the base layout; slots 5-11 sit
// in the gaps and sprout as you zoom in (see art_sprout). Returns the
// jittered foot (hex-local) in xy and a size factor in z.
fn art_slot_base(i: u32, cell: vec2<u32>, mirror: f32) -> vec3<f32> {
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

// The layout is pushed out by this much, so trees stand right up to a
// hex's edges and a forest runs on across them. Nothing
// stands closer to an edge than ART_SLOT_MARGIN.
const ART_SPREAD: f32 = 1.32;
const ART_SLOT_MARGIN: f32 = 0.085;

// art_slot_base varied so that the board is not one layout repeated: each
// hex turns it by a multiple of 60 degrees, shakes every slot and spreads
// out to its edges, and sizes drift across the board (noise on board-wide
// coordinates, so stands of big and small trees ignore the hex edges).
fn art_slot(i: u32, cell: vec2<u32>, mirror: f32) -> vec3<f32> {
    let s = art_slot_base(i, cell, mirror);
    let turn = f32(art_hash(cell, 200u) % 6u) * SIXTY;
    let h = art_hash(cell, 210u + i);
    let shake = (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.14;
    let cs = vec2<f32>(cos(turn), sin(turn));
    var p = (vec2<f32>(s.x * cs.x - s.y * cs.y, s.x * cs.y + s.y * cs.x) + shake) * ART_SPREAD;
    for (var e = 0u; e < 6u; e++) {
        let n = edge_normal(e);
        p -= n * max(dot(p, n) - (SQRT3_2 - ART_SLOT_MARGIN), 0.0);
    }
    let big = art_noise(art_global(p, cell) * 0.5 + 80.0);
    return vec3<f32>(p, s.z * (0.8 + 0.4 * big));
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
    return art_shrink_g(kind, false, d);
}

// art_shrink; groves give up less room, so the cover stays closed.
fn art_shrink_g(kind: u32, grove: bool, d: f32) -> f32 {
    if (grove) {
        return mix(1.0, 0.86, d);
    }
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

// How grand a mountain hex's peaks are, 0 to 1: low, worn ranges (the
// Balkan ranges, the Anatolian plateau rims, Lebanon) towards 0, the Alps
// towards 1. From the hex's height and how far it rises above its lowest
// neighbour (the sea counts as 0 m), so a high plateau scores lower than a
// range of the same height standing over lowland. High mountains (landform
// 3) never score below 0.85.
fn art_peak_scale(cell: vec2<u32>, landform: u32) -> f32 {
    let c = vec2<i32>(cell);
    let own = f32(textureLoad(height_tex, c, 0).r);
    var lo = own;
    for (var e = 0u; e < 6u; e++) {
        let nc = c + neighbour_offset(cell.x & 1u, e);
        if (nc.x >= 0 && nc.y >= 0 && nc.x < i32(g.grid.x) && nc.y < i32(g.grid.y)) {
            lo = min(lo, f32(textureLoad(height_tex, nc, 0).r));
        }
    }
    let score = 0.6 * own + 0.8 * max(own - max(lo, 0.0), 0.0);
    var s = smoothstep(700.0, 2300.0, score);
    if (landform == 3u) {
        s = max(s, 0.85);
    }
    return s;
}

// Mountain hexes: slots 0-1 are peaks, larger deep inside a range and on
// grander ranges (`ps`, art_peak_scale); slots 2-4 are foothills towards
// lowland neighbours. Low ranges trade some peaks for rounded hills and
// keep fewer crags, so they read as rough country, not a field of cones.
// Returns the centre (hex-local) in xy, a size in z and the kind in w.
fn art_mountain_slot(i: u32, cell: vec2<u32>, h0: u32, mirror: f32, nb_in: array<u32, 6>, mtn: u32, ps: f32) -> vec4<f32> {
    var nb = nb_in;
    // Footprint: low ranges narrower (their height drops more, in vs_prop),
    // so a 400 m desert range is not a field of broad mounds.
    let foot = mix(0.65, 1.0, ps);
    if (i >= ART_BASE_SLOTS) {
        // Detail: three small crags around the main peaks; on low ranges
        // only some hexes keep each one.
        if (i > 7u) {
            return vec4<f32>(0.0, 0.0, 0.0, f32(K_NONE));
        }
        if (art_unit(art_hash(cell, 40u + i), 0u) > 0.55 + ps) {
            return vec4<f32>(0.0, 0.0, 0.0, f32(K_NONE));
        }
        var extra = array<vec2<f32>, 3>(vec2<f32>(0.42, 0.30), vec2<f32>(-0.08, 0.36), vec2<f32>(-0.46, -0.16));
        let h = art_hash(cell, 30u + i);
        let p = extra[i - 5u] + (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.08;
        return vec4<f32>(p.x * mirror, p.y, (0.4 + 0.15 * art_unit(h, 16u)) * foot, f32(K_PEAK));
    }
    if (i < 2u) {
        var range = 0.0;
        for (var e = 0u; e < 6u; e++) {
            if ((mtn & (1u << e)) != 0u) { range += 1.0 / 6.0; }
        }
        // About half the hexes carry one big peak, the rest a pair; the
        // pair is turned by a multiple of 60 degrees and both are shaken,
        // so a range is not one stamp repeated in rows.
        let hv = art_hash(cell, 220u);
        let j = (vec2<f32>(art_unit(hv, 0u), art_unit(hv, 8u)) - 0.5) * 0.24;
        if (art_unit(hv, 16u) < 0.5) {
            if (i == 1u) {
                return vec4<f32>(0.0, 0.0, 0.0, f32(K_NONE));
            }
            return vec4<f32>(j.x * mirror, -0.04 + 0.6 * j.y, mix(1.05, 1.55, range) * foot, f32(K_PEAK));
        }
        let turn = f32(hv % 6u) * SIXTY;
        let cs = vec2<f32>(cos(turn), sin(turn));
        var p = select(vec2<f32>(0.18, -0.12), vec2<f32>(-0.26, 0.08), i == 0u);
        p = vec2<f32>(p.x * cs.x - p.y * cs.y, p.x * cs.y + p.y * cs.x) + j * 0.6;
        let size = select(mix(0.95, 1.45, range), mix(0.65, 1.05, range), i == 0u) * foot;
        // On low ranges the pair's second is often a rounded hill.
        if (i == 0u && art_unit(hv, 24u) < 0.6 * (1.0 - ps)) {
            return vec4<f32>(p.x * mirror, p.y, size * 1.15, f32(K_HILL));
        }
        return vec4<f32>(p.x * mirror, p.y, size, f32(K_PEAK));
    }
    return art_foothill(i, 2u, cell, h0, nb, mtn);
}

// Slot i as a foothill towards a lowland neighbour: the slots from `first`
// take the hex's lowland edges in turn (from a per-hex start), none once
// they run out.
fn art_foothill(i: u32, first: u32, cell: vec2<u32>, h0: u32, nb: array<u32, 6>, mtn: u32) -> vec4<f32> {
    let start = (h0 >> 4u) % 6u;
    var found = first;
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

// ------------------------------------------------------------ massifs ----
// A sketch of each hilly or mountain hex's high ground from the elevation
// raster (scene::massif_texels; neolith_core::massif), 2 x 2 texels per
// hex. Texel 0 r: kind + 1 (0: no sketch, and the peaks are laid out by
// hash), g: the strike in 256ths of a half turn anticlockwise from +x
// (hex-local), b: coherence 0..255, a: the floor in 20 m steps above
// -1000 m. Texels 1-3: a summit each, highest first; rg: x, y in
// hundredths of a hex-local unit + 128, b: its height above the floor in
// 20 m steps, a: 255 if there is one.
@group(0) @binding(12) var massif_tex: texture_2d<u32>;

const MK_NONE: u32 = 0u;
const MK_MASSIF: u32 = 1u;
const MK_RIDGE: u32 = 2u;
const MK_CONE: u32 = 3u;
const MK_PLATEAU: u32 = 4u;

// Below this height above its floor a summit is a rounded hill.
const ART_HILL_BELOW: f32 = 450.0;

struct MassifSketch {
    kind: u32,
    dir: vec2<f32>,  // along the strike, hex-local, unit
    coherence: f32,
    floor: f32,      // metres
    count: u32,      // summits
};

fn art_massif(cell: vec2<u32>) -> MassifSketch {
    var m: MassifSketch;
    let t = textureLoad(massif_tex, vec2<i32>(cell * 2u), 0);
    m.kind = t.r;
    let a = f32(t.g) / 256.0 * 3.14159265;
    m.dir = vec2<f32>(cos(a), sin(a));
    m.coherence = f32(t.b) / 255.0;
    m.floor = f32(t.a) * 20.0 - 1000.0;
    m.count = 0u;
    for (var k = 1u; k < 4u; k++) {
        if (textureLoad(massif_tex, vec2<i32>(cell * 2u + vec2<u32>(k & 1u, k >> 1u)), 0).a != 0u) {
            m.count = k;
        }
    }
    return m;
}

// Summit k (0..2): hex-local position in xy, metres above the floor in z.
fn art_summit(cell: vec2<u32>, k: u32) -> vec3<f32> {
    let j = k + 1u;
    let t = textureLoad(massif_tex, vec2<i32>(cell * 2u + vec2<u32>(j & 1u, j >> 1u)), 0);
    return vec3<f32>((f32(t.r) - 128.0) / 100.0, (f32(t.g) - 128.0) / 100.0, f32(t.b) * 20.0);
}

// A summit's prop size from its height above the floor: a 150 m knoll up
// to the 2600 m and more of the high ranges.
fn art_summit_size(h: f32) -> f32 {
    return mix(0.55, 1.6, smoothstep(150.0, 2600.0, h));
}

// How much a ridge's peaks stretch along the strike (x) and narrow across
// it (y); 1 for anything else.
fn art_ridge_stretch(m: MassifSketch) -> vec2<f32> {
    let k = select(0.0, smoothstep(0.3, 0.65, m.coherence), m.kind == MK_RIDGE);
    return vec2<f32>(mix(1.0, 1.8, k), mix(1.0, 0.65, k));
}

// `p` pulled back inside the hex, `margin` from its edges.
fn art_inside(p: vec2<f32>, margin: f32) -> vec2<f32> {
    var q = p;
    for (var e = 0u; e < 6u; e++) {
        let n = edge_normal(e);
        q -= n * max(dot(q, n) - (SQRT3_2 - margin), 0.0);
    }
    return q;
}

// The edge a hex-local direction points through.
fn art_edge_towards(d: vec2<f32>) -> u32 {
    let t = fract(atan2(d.y, d.x) / 6.2831853 + 1.0) * 6.0;
    return min(u32(t), 5u);
}

// Does a ridge carry on across edge e? 2: the neighbour is a ridge on
// nearly the same strike (or off the board), 1: it is high ground of some
// other kind, 0: it is not.
fn art_ridge_continues(cell: vec2<u32>, e: u32, m: MassifSketch, mtn: u32) -> u32 {
    let nc = vec2<i32>(cell) + neighbour_offset(cell.x & 1u, e);
    if (nc.x < 0 || nc.y < 0 || nc.x >= i32(g.grid.x) || nc.y >= i32(g.grid.y)) {
        return 2u;
    }
    let t = textureLoad(massif_tex, nc * 2, 0);
    if (t.r == MK_RIDGE) {
        let a = f32(t.g) / 256.0 * 3.14159265;
        if (abs(dot(vec2<f32>(cos(a), sin(a)), m.dir)) > 0.866) {
            return 2u;
        }
    }
    if ((mtn & (1u << e)) != 0u || t.r != 0u) {
        return 1u;
    }
    return 0u;
}

struct MassifSlot {
    foot: vec2<f32>,
    size: f32,
    kind: u32,
    elev: f32,  // the summit's elevation in metres, or -9999 if not known
};

fn art_no_slot() -> MassifSlot {
    return MassifSlot(vec2<f32>(0.0), 0.0, K_NONE, -9999.0);
}

// A summit as a peak, or a hill if it is low.
fn art_summit_slot(s: vec3<f32>, m: MassifSketch, scale: f32) -> MassifSlot {
    if (s.z < ART_HILL_BELOW) {
        return MassifSlot(art_inside(s.xy, 0.12), art_summit_size(s.z) * 1.15 * scale, K_HILL, m.floor + s.z);
    }
    return MassifSlot(art_inside(s.xy, 0.12), art_summit_size(s.z) * scale, K_PEAK, m.floor + s.z);
}

// art_mountain_slot for a hex with a massif sketch: the props stand where
// the raster's summits are and are as big as those stand high. Ridges run
// along their strike and reach for the neighbours they continue into, so
// a range chains across hexes; a cone is one big peak; a plateau is open
// ground with mesas on the rims that drop to lower neighbours; a knot of
// peaks has one prop per summit. Slots 3-4 (4 on ridges) are foothills.
fn art_massif_slot(i: u32, cell: vec2<u32>, h0: u32, nb: array<u32, 6>, mtn: u32, m: MassifSketch) -> MassifSlot {
    let top = select(vec3<f32>(0.0), art_summit(cell, 0u), m.count > 0u);
    let ps = smoothstep(300.0, 2300.0, top.z);
    if (i >= ART_BASE_SLOTS) {
        // Detail: crags around the main peaks of knots and along ridges.
        if (i > 7u || m.kind == MK_CONE || m.kind == MK_PLATEAU || top.z < ART_HILL_BELOW) {
            return art_no_slot();
        }
        let h = art_hash(cell, 30u + i);
        if (art_unit(art_hash(cell, 40u + i), 0u) > 0.55 + ps) {
            return art_no_slot();
        }
        var extra = array<vec2<f32>, 3>(vec2<f32>(0.42, 0.30), vec2<f32>(-0.08, 0.36), vec2<f32>(-0.46, -0.16));
        var p = top.xy * 0.5 + extra[i - 5u] + (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.08;
        if (m.kind == MK_RIDGE) {
            let across = vec2<f32>(-m.dir.y, m.dir.x);
            p = top.xy + m.dir * ((f32(i) - 6.0) * 0.38 + (art_unit(h, 24u) - 0.5) * 0.1) + across * (art_unit(h, 0u) - 0.5) * 0.3;
        }
        return MassifSlot(art_inside(p, 0.12), (0.4 + 0.15 * art_unit(h, 16u)) * mix(0.65, 1.0, ps), K_PEAK, m.floor + top.z * 0.35);
    }
    if (m.kind == MK_PLATEAU) {
        if (i == 0u && top.z >= 250.0) {
            return MassifSlot(art_inside(top.xy, 0.12), 0.75, K_HILL, m.floor + top.z);
        }
        if (i < 2u) {
            return art_no_slot();
        }
        // Mesas on the rims.
        let own = textureLoad(height_tex, vec2<i32>(cell), 0).r;
        let start = (h0 >> 4u) % 6u;
        var found = 2u;
        for (var k = 0u; k < 6u; k++) {
            let e = (k + start) % 6u;
            let nc = vec2<i32>(cell) + neighbour_offset(cell.x & 1u, e);
            if (nc.x < 0 || nc.y < 0 || nc.x >= i32(g.grid.x) || nc.y >= i32(g.grid.y) || !art_is_land(nb[e])) {
                continue;
            }
            if (f32(own - textureLoad(height_tex, nc, 0).r) > 200.0) {
                if (found == i) {
                    let h = art_hash(cell, 20u + i);
                    let jitter = (vec2<f32>(art_unit(h, 0u), art_unit(h, 8u)) - 0.5) * 0.18;
                    return MassifSlot(edge_normal(e) * 0.55 + jitter, 0.7 + 0.2 * art_unit(h, 16u), K_HILL, m.floor);
                }
                found++;
            }
        }
        return art_no_slot();
    }
    if (m.kind == MK_CONE) {
        if (i == 0u) {
            return art_summit_slot(top, m, 1.15);
        }
        if (i < 3u) {
            return art_no_slot();
        }
    } else if (m.kind == MK_RIDGE) {
        if (i == 0u) {
            return art_summit_slot(top, m, 1.0);
        }
        // The ridge line through the highest summit, from the point on it
        // nearest the hex's centre, out towards the edges it crosses.
        let anchor = top.xy - m.dir * dot(top.xy, m.dir);
        if (i == 2u || i == 3u) {
            let d = select(-m.dir, m.dir, i == 2u);
            let c = art_ridge_continues(cell, art_edge_towards(d), m, mtn);
            let reach = select(0.38, select(0.55, 0.66, c == 2u), c > 0u);
            let scale = select(0.55, select(0.7, 0.85, c == 2u), c > 0u);
            let p = art_inside(anchor + d * reach, 0.1);
            if (distance(p, top.xy) < 0.3) {
                return art_no_slot();
            }
            let s = art_summit_slot(top, m, scale);
            return MassifSlot(p, s.size, s.kind, m.floor + top.z * select(0.5, 0.75, c == 2u));
        }
        if (i == 1u) {
            if (m.count < 2u) {
                return art_no_slot();
            }
            let s1 = art_summit(cell, 1u);
            // Not on top of a shoulder.
            for (var j = 0u; j < 2u; j++) {
                let d = select(-m.dir, m.dir, j == 0u);
                if (distance(s1.xy, anchor + d * 0.55) < 0.3) {
                    return art_no_slot();
                }
            }
            return art_summit_slot(s1, m, 1.0);
        }
        let f = art_foothill(i, 4u, cell, h0, nb, mtn);
        return MassifSlot(f.xy, f.z, u32(f.w), -9999.0);
    } else if (i < 3u) {
        // A knot of peaks: one per summit.
        if (i >= m.count) {
            return art_no_slot();
        }
        return art_summit_slot(art_summit(cell, i), m, 1.0);
    }
    let f = art_foothill(i, 3u, cell, h0, nb, mtn);
    return MassifSlot(f.xy, f.z, u32(f.w), -9999.0);
}

// What stands in mountain slot i: from the massif sketch where the hex has
// one with summits (or is a plateau), else laid out by hash.
fn art_mountain_any(i: u32, cell: vec2<u32>, h0: u32, mirror: f32, nb: array<u32, 6>, mtn: u32, ps: f32, m: MassifSketch) -> MassifSlot {
    if (m.kind != MK_NONE && (m.count > 0u || m.kind == MK_PLATEAU)) {
        return art_massif_slot(i, cell, h0, nb, mtn, m);
    }
    let v = art_mountain_slot(i, cell, h0, mirror, nb, mtn, ps);
    return MassifSlot(v.xy, v.z, u32(v.w), -9999.0);
}

// ------------------------------------------------- dressing the ranges ----
// The layout above puts a few big props in a mountain hex and leaves the
// rest of its slots empty, so a range read as lone cones on bare tiles. The
// empty slots are filled: base slots 1-2 with lower shoulder peaks on the
// flanks of the main one, base slots 3-4 and detail slots 8-11 with what
// grows on the hex's biome (conifers on a taiga range, oaks on a temperate
// one, scrub on a dry one), kept off the big props' footprints so they
// stand on the lower slopes and in the saddles between them.

// The big props of a mountain hex (slots 0-7), worked out once.
alias MountainBase = array<MassifSlot, 8>;

fn art_mountain_base(cell: vec2<u32>, h0: u32, mirror: f32, nb: array<u32, 6>, mtn: u32, ps: f32, m: MassifSketch) -> MountainBase {
    var b: MountainBase;
    for (var i = 0u; i < 8u; i++) {
        b[i] = art_mountain_any(i, cell, h0, mirror, nb, mtn, ps, m);
    }
    return b;
}

// What grows on a mountain hex's slopes in this biome, for a slot with hash
// `h`; K_NONE for bare ground. `high` (0..1) thins the trees towards the
// treeline.
fn art_mountain_growth(terrain: u32, h: u32, high: f32) -> u32 {
    let r = art_unit(h, 24u);
    let keep = art_unit(h, 16u);
    var k = K_NONE;
    var p = 0.0;
    switch terrain {
        case T_BOREAL_FOREST: { k = K_CONIFER; p = 0.95; }
        case T_TEMPERATE_FOREST: { k = select(K_ROUND, K_CONIFER, r < 0.55); p = 0.9; }
        case T_TROPICAL_FOREST: { k = select(K_ROUND, K_PALM, r < 0.12); p = 0.9; }
        case T_WOODLANDS: { k = select(K_ROUND, K_CONIFER, r < 0.35); p = 0.65; }
        case T_STEPPE_FOREST: { k = select(K_SHRUB, K_CONIFER, r < 0.7); p = 0.6; }
        case T_FLOODPLAIN: { k = K_ROUND; p = 0.55; }
        case T_SAVANNAH: { k = select(K_SHRUB, K_ACACIA, r < 0.5); p = 0.35; }
        case T_CHAPARRAL: { k = select(K_SHRUB, K_ROUND, r < 0.15); p = 0.65; }
        case T_SEMI_DESERT: { k = K_SHRUB; p = 0.3; }
        case T_GRASSLAND: { k = K_SHRUB; p = 0.2; }
        case T_TUNDRA: { k = K_SHRUB; p = 0.25; }
        case T_ALPINE: { k = K_SHRUB; p = 0.15; }
        default: {}
    }
    // Trees give out towards the treeline; scrub holds on longer.
    if (k <= K_PALM) {
        p *= 1.0 - 0.85 * high;
    }
    return select(K_NONE, k, keep < p);
}

// A lower peak on the flank of the hex's main one (base slot 0), for empty
// slot 1 or 2 (and 3-4 where nothing grows). None beside a cone or on a
// plateau, which keep their clean shapes, or where slot 0 is a hill.
fn art_shoulder(i: u32, cell: vec2<u32>, b: MountainBase, m: MassifSketch) -> MassifSlot {
    let main = b[0];
    if (main.kind != K_PEAK || m.kind == MK_CONE || m.kind == MK_PLATEAU) {
        return art_no_slot();
    }
    let h = art_hash(cell, 240u + i);
    if (i >= 3u && art_unit(h, 24u) > 0.5) {
        return art_no_slot();
    }
    // Round the main peak, a different side per slot, on its skirt.
    let a = (f32(i) * 2.4 + art_unit(h, 0u) * 1.6) + f32(art_hash(cell, 241u) % 6u) * SIXTY;
    var d = vec2<f32>(cos(a), sin(a));
    if (m.kind == MK_RIDGE) {
        // Along the crest, not off its sides.
        d = normalize(m.dir * sign(dot(d, m.dir) + 1e-3) * 0.85 + d * 0.15);
    }
    let r = art_prop_dims(K_PEAK).x * main.size;
    let p = art_inside(main.foot + d * r * (0.7 + 0.25 * art_unit(h, 8u)), 0.12);
    let size = main.size * (0.38 + 0.2 * art_unit(h, 16u));
    let elev = select(-9999.0, main.elev - (main.elev - m.floor) * 0.35, main.elev > -9000.0);
    return MassifSlot(p, size, K_PEAK, elev);
}

// How far `p` is inside the footprint of the big props (and shoulders) in
// `b`, as a fraction of each one's radius: under 1 is on a skirt.
fn art_under_props(p: vec2<f32>, b: MountainBase, sh: array<MassifSlot, 2>, m: MassifSketch) -> f32 {
    var best = 9.0;
    for (var j = 0u; j < 10u; j++) {
        var s = art_no_slot();
        if (j < 8u) { s = b[j]; } else { s = sh[j - 8u]; }
        if (s.kind != K_PEAK && s.kind != K_HILL) { continue; }
        let r = art_prop_dims(s.kind).x * s.size;
        var q = p - s.foot;
        if (s.kind == K_PEAK && m.kind == MK_RIDGE) {
            let k = art_ridge_stretch(m);
            q = vec2<f32>(dot(q, m.dir) / k.x, dot(q, vec2<f32>(-m.dir.y, m.dir.x)) / k.y);
        }
        best = min(best, length(q) / max(r, 1e-4));
    }
    return best;
}

// What stands in mountain slot i: the big prop the layout puts there, or,
// where it leaves the slot empty, a shoulder peak or the biome's growth.
fn art_mountain_dressed(i: u32, cell: vec2<u32>, terrain: u32, b: MountainBase, m: MassifSketch) -> MassifSlot {
    if (i < 8u && b[i].kind != K_NONE) {
        return b[i];
    }
    if (i == 0u || (i >= ART_BASE_SLOTS && i < 8u)) {
        return art_no_slot();
    }
    var sh = array<MassifSlot, 2>(art_no_slot(), art_no_slot());
    for (var j = 1u; j < 3u; j++) {
        if (b[j].kind == K_NONE) { sh[j - 1u] = art_shoulder(j, cell, b, m); }
    }
    if (i < 3u) {
        return sh[i - 1u];
    }
    // Slots 3-4 and 8-11: growth, where the slot's foot is clear of the
    // big props' skirts (a tree a little way up a slope is fine).
    let s = art_slot(i, cell, select(1.0, -1.0, (art_hash(cell, 0u) & 1u) == 1u));
    let foot = s.xy + vec2<f32>(0.0, 0.15);
    let h = art_hash(cell, 100u + i);
    let high = smoothstep(1700.0, 2900.0, f32(textureLoad(height_tex, vec2<i32>(cell), 0).r));
    var kind = art_mountain_growth(terrain, h, high);
    if (kind != K_NONE && art_under_props(foot, b, sh, m) < 0.78) {
        kind = K_NONE;
    }
    if (kind != K_NONE) {
        // Not on a camp or its fields, as on open ground.
        if (art_field(foot, cell) > 0.5 || art_camp(foot, cell) < 1.0 || art_in_river(foot, cell)) {
            kind = K_NONE;
        }
    }
    if (kind == K_NONE) {
        if (i < ART_BASE_SLOTS) {
            return art_shoulder(i, cell, b, m);
        }
        return art_no_slot();
    }
    // A touch smaller than on the flat: the props around are big.
    return MassifSlot(foot, s.z * 1.45 * 0.85, kind, -9999.0);
}

// ----------------------------------------------- room for rivers and camps ----
// A peak or hill is broad (a peak's skirt is most of a hex), so testing its
// foot alone left skirts across river beds and settlement clearings. The
// bake fits each one in: it slides up to ART_CLEAR_SLIDE away from the
// nearest bed or clearing, then shrinks down to ART_CLEAR_MIN of its size,
// and failing that is left out.
const ART_CLEAR_SLIDE: f32 = 0.28;
const ART_CLEAR_MIN: f32 = 0.5;
const ART_CLEAR_MARGIN: f32 = 0.03;

// How many camps stand in or reach into the hex.
fn art_camp_count(cell: vec2<u32>) -> u32 {
    var n = 0u;
    for (var k = 0u; k < 4u; k++) {
        if (textureLoad(camp_tex, vec2<i32>(cell * 2u + vec2<u32>(k & 1u, k >> 1u)), 0).a <= 0.0) { break; }
        n++;
    }
    return n;
}

// The nearest thing a peak or hill keeps off at `p` (hex-local): x: the
// distance to the edge of a river bed or a camp's clearing (negative
// inside; 9 with nothing within `near`), yz: the unit direction away from it.
fn art_obstacle(p: vec2<f32>, cell: vec2<u32>, near: f32) -> vec3<f32> {
    var best = vec3<f32>(9.0, 0.0, 1.0);
    let gp = art_global(p, cell);
    let b = art_bank(gp);
    if (b.y > 0.0 && b.x < near) {
        let e = 0.02;
        let gr = vec2<f32>(art_bank(gp + vec2<f32>(e, 0.0)).x - art_bank(gp - vec2<f32>(e, 0.0)).x,
                           art_bank(gp + vec2<f32>(0.0, e)).x - art_bank(gp - vec2<f32>(0.0, e)).x);
        let l = length(gr);
        best = vec3<f32>(b.x, select(vec2<f32>(0.0, 1.0), gr / l, l > 1e-6));
    }
    for (var k = 0u; k < 4u; k++) {
        let c = textureLoad(camp_tex, vec2<i32>(cell * 2u + vec2<u32>(k & 1u, k >> 1u)), 0);
        if (c.a <= 0.0) { break; }
        let to = p - (c.xy * 2.0 - 1.0) * CAMP_SPAN;
        let d = length(to * vec2<f32>(c.a, 1.0)) - c.z * CAMP_RADIUS_MAX;
        if (d < best.x) {
            let l = length(to);
            best = vec3<f32>(d, select(vec2<f32>(0.0, 1.0), to / l, l > 1e-6));
        }
    }
    return best;
}

// How far a footprint of radius `r`, stretched by `stretch` along `dir`
// and across it, reaches in direction `n`.
fn art_reach(r: f32, stretch: vec2<f32>, dir: vec2<f32>, n: vec2<f32>) -> f32 {
    let a = dot(n, dir) * stretch.x;
    let c = dot(n, vec2<f32>(-dir.y, dir.x)) * stretch.y;
    return r * sqrt(a * a + c * c);
}

// A footprint at `p` fitted around the beds and clearings: xy: the foot,
// z: the size factor (0: leave it out).
fn art_clear(p: vec2<f32>, r: f32, stretch: vec2<f32>, dir: vec2<f32>, cell: vec2<u32>) -> vec3<f32> {
    var q = p;
    var moved = 0.0;
    let near = r * max(stretch.x, stretch.y) + ART_CLEAR_MARGIN + ART_CLEAR_SLIDE;
    for (var it = 0u; it < 4u; it++) {
        let o = art_obstacle(q, cell, near);
        let need = art_reach(r, stretch, dir, o.yz) + ART_CLEAR_MARGIN - o.x;
        if (need <= 0.0) {
            return vec3<f32>(q, 1.0);
        }
        let step = min(need, ART_CLEAR_SLIDE - moved);
        if (step <= 1e-3) { break; }
        q = art_inside(q + o.yz * step, 0.1);
        moved += step;
    }
    let o = art_obstacle(q, cell, near);
    let s = (o.x - ART_CLEAR_MARGIN) / max(art_reach(r, stretch, dir, o.yz), 1e-4);
    return vec3<f32>(q, select(0.0, min(s, 1.0), s >= ART_CLEAR_MIN));
}

// A peak or hill settled into its hex. Where camps crowd a hex the peaks
// become hills and the hills stay small, so the settlements show; then the
// footprint is fitted around beds and clearings (art_clear). xy: the foot,
// z: the size (0: nothing stands there), w: the kind.
fn art_settle(kind: u32, at: vec2<f32>, size: f32, cell: vec2<u32>, m: MassifSketch) -> vec4<f32> {
    var k = kind;
    var s = size;
    let camps = art_camp_count(cell);
    if (camps >= 2u && k == K_PEAK) {
        k = K_HILL;
        s *= 1.1;
    }
    if (camps >= 1u && k == K_HILL) {
        s = min(s, select(1.1, 0.9, camps >= 2u));
    }
    let stretch = select(vec2<f32>(1.0), art_ridge_stretch(m), k == K_PEAK);
    // As vs_prop builds it: crags make sides up to a fifth wider, and the
    // "Mountain height" style widens by its square root.
    let r = art_prop_dims(k).x * s * 1.1 * sqrt(max(g.wall_colour.w, 0.0));
    let c = art_clear(at, r, stretch, m.dir, cell);
    return vec4<f32>(c.xy, s * c.z, f32(k));
}

// The summit elevation a prop_tex entry carries in its top 16 bits: 20 m
// steps above -1000 m, 0 for none.
fn art_elev_code(elev: f32) -> u32 {
    if (elev <= -9000.0) {
        return 0u;
    }
    return u32(clamp((elev + 1000.0) / 20.0, 1.0, 65535.0));
}

fn art_glyph(base: vec3<f32>, p: vec2<f32>, s: f32, kind: u32, terrain: u32, h: u32, a: Art) -> vec3<f32> {
    // The printed kinds only: the rest are props.
    var c = base;
    switch kind {
        case K_TUFT: { c = art_tuft(c, p - vec2<f32>(0.0, 0.14), 1.6 * s, a.albedo * 0.5, a); }
        case K_WAVE: { c = art_wave(c, p - vec2<f32>(0.0, 0.2), 1.25 * s, h, a); }
        default: {}
    }
    return c;
}

// A prop's footprint radius and height in profile units (see art_profile).
fn art_prop_dims(kind: u32) -> vec2<f32> {
    var dims = array<vec2<f32>, 7>(
        vec2<f32>(0.19, 0.55), vec2<f32>(0.19, 0.50), vec2<f32>(0.27, 0.39), vec2<f32>(0.25, 0.50),
        vec2<f32>(0.10, 0.12), vec2<f32>(0.46, 0.64), vec2<f32>(0.30, 0.15),
    );
    return dims[kind - 1u];
}

// The soft shadow a prop of size `s` standing at the origin casts on the
// ground at `p` (glyph space), 0..1. A blob, not a projection: a capsule
// from under the prop out along the light. A tree's starts under its crown.
fn art_prop_shadow(p: vec2<f32>, kind: u32, grove: bool, s: f32, a: Art) -> f32 {
    let dim = art_dims(kind, grove) * s;
    let reach = a.sun * dim.y;
    let start = reach * select(0.0, 0.3, kind <= K_PALM && !grove);
    let d = sd_segment(p, start, reach * 0.8 + vec2<f32>(1e-5, 0.0)) - dim.x * 0.8;
    let soft = dim.x * 0.35 + a.px;
    return 1.0 - smoothstep(-soft, soft * 0.5, d);
}

// The shadows the props of `cell` cast at `q`: glyph space relative to that
// cell's centre, which may be a neighbour's (trees stand right up to the
// edges, and their shadows fall across them).
fn art_shadows_from(cell: vec2<u32>, q: vec2<f32>, a: Art) -> f32 {
    let mountain = (textureLoad(hex_tex, vec2<i32>(cell), 0).z & 1u) != 0u;
    var shadow = 0.0;
    for (var n = 0u; n < ART_SLOTS; n++) {
        let e = textureLoad(art_tex, art_prop_texel(cell, n), 0);
        let kind = e.x & 0xffu;
        if (kind == K_NONE) { break; }
        if (kind > K_HILL) { continue; }
        let grow = art_sprout((e.x >> 8u) & 0xffu, cell, a.detail);
        if (grow <= 0.0) { continue; }
        // Same foot and size as art_prop_layout gives the prop.
        let foot = vec2<f32>(bitcast<f32>(e.y), bitcast<f32>(e.z)) + vec2<f32>(0.0, select(0.15, 0.0, mountain));
        let grove = (e.x & ART_GROVE_BIT) != 0u;
        let ps = bitcast<f32>(e.w) * select(1.45, 1.0, mountain) * a.size * a.lod * grow * art_shrink_g(kind, grove, a.detail);
        shadow = max(shadow, art_prop_shadow(q - vec2<f32>(foot.x * a.asp, foot.y), kind, grove, ps, a));
    }
    return shadow;
}

fn art_is_forest(t: u32) -> bool {
    return t == T_BOREAL_FOREST || t == T_TEMPERATE_FOREST || t == T_TROPICAL_FOREST;
}

// How much of a biome's ground is grass sward (0 bare .. 1 all grass), for
// the close-up grass material (fs_board's lighting).
fn art_grassiness(t: u32) -> f32 {
    var k = 0.0;
    switch t {
        case T_GRASSLAND, T_PLAINS, T_FLOODPLAIN, T_LAND, T_FREE: { k = 1.0; }
        case T_SAVANNAH, T_STEPPE_FOREST: { k = 0.9; }
        case T_WOODLANDS, T_ALPINE: { k = 0.75; }
        case T_TUNDRA, T_TEMPERATE_FOREST: { k = 0.55; }
        case T_CHAPARRAL, T_BOREAL_FOREST, T_TROPICAL_FOREST, T_MOUNTAINS: { k = 0.4; }
        case T_SEMI_DESERT: { k = 0.25; }
        default: {}
    }
    return k;
}

fn terrain_art(local: vec2<f32>, cell: vec2<u32>, terrain: u32, a: Art) -> vec3<f32> {
    if (terrain >= T_COUNT) {
        return a.albedo;
    }
    // Neighbours and the glyph list, baked per hex (see fs_hex_bake, fs_art_bake).
    let hx = textureLoad(hex_tex, vec2<i32>(cell), 0);
    let nb = art_unpack_neighbours(hx);
    let gp = art_global(local, cell);
    let blend = a.blend * (1.0 - a.mono);
    var c = a.albedo;

    // ---- ground: a forest floor, biomes creeping across edges, mottling,
    // then the coast. (Terrain mode only: elsewhere the colour is data.)
    let ground_k = a.k * (1.0 - a.mono);
    if (ground_k > 0.0 && art_is_forest(terrain)) {
        // Leaf litter and shade under the canopy, in drifts.
        let litter = smoothstep(0.3, 0.7, art_noise(gp * 1.9 + 9.0));
        c = mix(c, pow(art_fill(terrain), vec3<f32>(2.2)) * 1.15, (0.32 + 0.28 * litter) * ground_k);
    }
    if (blend > 0.5 && a.field < 0.5) {
        let hit = art_intrusion(local, cell, terrain, nb, a.px);
        if (hit.y > 0.0) {
            var n = nb;
            let other = textureLoad(palette_tex, vec2<i32>(i32(n[u32(hit.x)]), 0), 0).rgb;
            c = mix(c, saturate_colour(other), hit.y * a.k);
        }
    }
    if (ground_k > 0.0 && art_is_land(terrain)) {
        // Greener along a river, most of all through dry country.
        let bank = art_bank(gp);
        if (bank.y > 0.0) {
            let arid = terrain == T_EXTREME_DESERT || terrain == T_SEMI_DESERT || terrain == T_SAVANNAH
                || terrain == T_CHAPARRAL;
            let ragged = (art_noise(gp * 3.3 + 7.0) - 0.5) * 0.3;
            let k = (1.0 - smoothstep(0.0, 0.6, bank.x + ragged)) * bank.y;
            c = mix(c, art_rgb(0.33, 0.56, 0.22), k * select(0.25, 0.6, arid) * ground_k);
        }
    }
    if (ground_k > 0.0 && art_is_land(terrain)) {
        // Trodden bare around a camp, with a ragged edge.
        let camp = art_camp(local, cell) + (art_noise(gp * 5.3 + 13.0) - 0.5) * 0.3;
        c = mix(c, art_rgb(0.47, 0.38, 0.27), (1.0 - smoothstep(0.55, 1.0, camp)) * 0.7 * ground_k);
    }
    if (ground_k > 0.0 && art_is_land(terrain)) {
        // A farming site's fields (art_field), in strips, each plot
        // ploughed its own way. The strips fade out from far off, leaving
        // the fields' colour.
        let field = art_field(local, cell);
        if (field > 0.0) {
            let turn = art_noise(floor(gp * 2.3) + 7.0) * 3.14159;
            let s = dot(gp, vec2<f32>(cos(turn), sin(turn))) * 9.0;
            let fine = 1.0 - smoothstep(0.03, 0.08, a.px * 9.0);
            let stripe = 0.5 + 0.25 * sin(s * 6.2831853) * fine;
            let crop = mix(c, mix(art_rgb(0.70, 0.62, 0.34), art_rgb(0.84, 0.74, 0.44), stripe), 0.8);
            c = mix(c, crop, field * ground_k);
        }
    }
    if (ground_k > 0.0) {
        // No tile is one flat colour: broad patches and a finer grain.
        let mottle = art_noise(gp * 0.9) * 0.6 + art_noise(gp * 3.7 + 31.0) * 0.4;
        c *= 1.0 + (mottle - 0.5) * select(0.24, 0.10, terrain == T_WATER) * ground_k;
        // And no region is one tile repeated: lighter and darker country
        // several hexes across, drifting a little warmer and cooler.
        let broad = art_noise(gp * 0.17 + 70.0) - 0.5;
        let warm = art_noise(gp * 0.11 + 90.0) - 0.5;
        c *= (1.0 + broad * select(0.30, 0.10, terrain == T_WATER) * ground_k)
            * (1.0 + vec3<f32>(0.10, 0.0, -0.12) * warm * select(1.0, 0.3, terrain == T_WATER) * ground_k);
    }
    if (a.blend > 0.5) {
        let coast = select(art_shore(local, terrain, nb), a.shore, a.field > 0.5);
        if (coast < 1.0) {
            let wobble = (art_noise(gp * 4.0) - 0.5) * 0.10;
            let d = coast + wobble;
            if (terrain == T_WATER) {
                // Shallows, a surf line on the shore and two broken foam lines.
                let shallow = (1.0 - smoothstep(0.0, 0.5, d)) * 0.55 * (1.0 - a.mono);
                c = mix(c, art_rgb(0.36, 0.50, 0.53), shallow * a.k);
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
    let mountain = (hx.z & 1u) != 0u;

    // A corner of the hex drawn as its neighbour's terrain (the coast cut
    // across it) gets that ground and shore, not this hex's glyphs.
    if (a.own < 0.5) {
        return c;
    }
    if (!mountain) {
        if (terrain == T_ICE) {
            return art_ice(c, vec2<f32>(q.x * mirror, q.y), ag);
        }
        if (terrain == T_EXTREME_DESERT || terrain == T_SEMI_DESERT) {
            // Up to two dunes (one in semi-desert), each in a place, size
            // and presence of its own per hex, so the sand is not tiled with
            // one stamp. The lee side keeps one wind direction.
            let n_dunes = select(1u, 2u, terrain == T_EXTREME_DESERT);
            let turn = f32(art_hash(cell, 230u) % 6u) * SIXTY;
            let cs = vec2<f32>(cos(turn), sin(turn));
            for (var k = 0u; k < n_dunes; k++) {
                let hd = art_hash(cell, 231u + k);
                if (art_unit(hd, 0u) < select(0.35, 0.2, terrain == T_EXTREME_DESERT)) { continue; }
                var d = select(vec2<f32>(0.24, 0.02), vec2<f32>(-0.20, 0.20), k == 0u);
                d = vec2<f32>(d.x * cs.x - d.y * cs.y, d.x * cs.y + d.y * cs.x)
                    + (vec2<f32>(art_unit(hd, 8u), art_unit(hd, 16u)) - 0.5) * 0.26;
                let sz = mix(1.0, 1.6, art_unit(hd, 24u)) * a.size;
                c = art_dune(c, q - vec2<f32>(d.x * mirror * a.asp, d.y - 0.1), sz, ag);
            }
        }
    }
    // The hex's glyphs in drawing order, as art_glyph_list lays them out;
    // the list ends at the first empty entry.
    var shadow = 0.0;
    {
        // Prop shadows: this hex's, and near an edge the neighbour's across it.
        shadow = art_shadows_from(cell, q, a);
        var best = -1.0;
        var edge = 0u;
        for (var i = 0u; i < 6u; i++) {
            let d = dot(local, edge_normal(i));
            if (d > best) {
                best = d;
                edge = i;
            }
        }
        let nc = vec2<i32>(cell) + neighbour_offset(cell.x & 1u, edge);
        if (best > 0.45 && nc.x >= 0 && nc.y >= 0 && nc.x < i32(g.grid.x) && nc.y < i32(g.grid.y)) {
            let over = local - edge_normal(edge) * (2.0 * SQRT3_2);
            shadow = max(shadow, art_shadows_from(vec2<u32>(nc), vec2<f32>(over.x * a.asp, over.y), a));
        }
    }
    for (var n = 0u; n < ART_SLOTS; n++) {
        let e = textureLoad(art_tex, art_prop_texel(cell, n), 0);
        let kind = e.x & 0xffu;
        if (kind == K_NONE) { break; }
        let i = (e.x >> 8u) & 0xffu;
        let grow = art_sprout(i, cell, a.detail);
        if (grow <= 0.0) { continue; }
        let foot = vec2<f32>(bitcast<f32>(e.y), bitcast<f32>(e.z));
        let size = bitcast<f32>(e.w);
        let at = q - vec2<f32>(foot.x * a.asp, foot.y);
        // A prop (vs_prop): only its shadow is on the tile (above).
        if (kind <= K_HILL) { continue; }
        // Waves only close in: from further out they read as noise on the sea.
        if (kind == K_WAVE && a.detail < 0.5) { continue; }
        let sz = size * a.size * grow * art_shrink(kind, a.detail);
        // Every glyph fits in this circle; skip the work for pixels outside.
        if (length(at - vec2<f32>(0.0, 0.55 * sz)) > 0.7 * sz + 2.0 * a.px) { continue; }
        c = art_glyph(c, at, sz, kind, terrain, art_hash(cell, 140u + i), ag);
    }
    // Overlapping shadows merge (max), they do not stack. Off in flat lighting.
    return c * (1.0 - 0.5 * shadow * a.k * (1.0 - g.lines.w));
}

// ------------------------------------------------------------ art bake ----
// The printed layer used to work out, for every pixel, what each of the hex's
// glyph slots holds (kind, foot, size, hidden by a neighbour's ground) and,
// on mountains, lay the range out in a 3 x 8 loop. None of that depends on
// the pixel, only on the map and the edge-blend setting, so the bake pass
// works it out per hex into textures the pixel shader reads.

// (col, row) -> x: neighbours across edges 0-3, y: edges 4-5 (a byte each;
// off-board ones are the hex's own terrain), z: bit 0 draws as mountains.
@group(0) @binding(7) var hex_tex: texture_2d<u32>;
// The hex's glyphs in drawing order at art_prop_texel(cell, n), n = 0..:
// x: kind | slot << 8 (K_NONE ends the list), y, z: foot (hex-local, before
// the squash), w: size; floats as bits. Glyphs hidden by a neighbour's
// ground are left out.
@group(0) @binding(6) var art_tex: texture_2d<u32>;

fn art_unpack_neighbours(hx: vec4<u32>) -> array<u32, 6> {
    return array<u32, 6>(
        hx.x & 0xffu, (hx.x >> 8u) & 0xffu, (hx.x >> 16u) & 0xffu, (hx.x >> 24u) & 0xffu,
        hx.y & 0xffu, (hx.y >> 8u) & 0xffu,
    );
}

@fragment
fn fs_hex_bake(@builtin(position) pos: vec4<f32>) -> @location(0) vec4<u32> {
    let cell = vec2<u32>(pos.xy);
    if (cell.x >= u32(g.grid.x) || cell.y >= u32(g.grid.y)) {
        return vec4<u32>(0u);
    }
    let st = textureLoad(state_tex, vec2<i32>(cell), 0);
    let nb = art_neighbours(cell, st.r);
    let mountain = st.r < T_COUNT && art_is_mountain(st.r, (st.a >> 3u) & 3u);
    // w: the hex's ground for fs_board's field, read once per hex there
    // instead of from four textures: rgb its colour in this mode (square
    // root of linear, a byte each), then bit 24 wet, bits 25-31 hillshade.
    let c = vec2<i32>(cell);
    let col = sqrt(clamp(saturate_colour(ground_colour(st, c, u32(g.grid.z))), vec3<f32>(0.0), vec3<f32>(1.0)));
    let rgb = vec3<u32>(round(col * 255.0));
    let shade = min(textureLoad(elevation_tex, c, 0).g >> 1u, 127u);
    let wet = select(0u, 1u, st.r == TERRAIN_WATER);
    return vec4<u32>(
        nb[0] | (nb[1] << 8u) | (nb[2] << 16u) | (nb[3] << 24u),
        nb[4] | (nb[5] << 8u),
        // z: bit 0 mountain; bits 16-31 the surface height in metres + 1000
        // (fs_board's relief shading reads it with the ground in w).
        select(0u, 1u, mountain) | (u32(clamp(textureLoad(height_tex, c, 0).r + 1000, 0, 65535)) << 16u),
        rgb.x | (rgb.y << 8u) | (rgb.z << 16u) | (wet << 24u) | (shade << 25u),
    );
}

// Does something standing at `p` (hex-local) stand in a river's bed?
fn art_in_river(p: vec2<f32>, cell: vec2<u32>) -> bool {
    let bank = art_bank(art_global(p, cell));
    return bank.y > 0.0 && bank.x < RIVER_CLEAR;
}

// art_kind_on for a slot whose foot is at `foot` (hex-local), minding the
// camps and rivers: nothing in a clearing or a bed, riverside growth on the
// banks.
fn art_kind_by_river(terrain: u32, landform: u32, i: u32, skip: u32, foot: vec2<f32>, cell: vec2<u32>) -> u32 {
    let h = art_hash(cell, 100u + i);
    let kind = art_kind_on(terrain, landform, i, skip, h);
    if (terrain == T_WATER) {
        return kind;
    }
    if (art_camp(foot, cell) < 1.0) {
        return K_NONE;
    }
    let gp = art_global(foot, cell);
    if (kind >= K_CONIFER && kind <= K_SHRUB) {
        // Glades: woods thin out in patches that ignore the hex edges.
        let glade = smoothstep(0.5, 0.85, art_noise(gp * 0.33 + 50.0));
        if (art_unit(h, 16u) < glade * 0.5) {
            return K_NONE;
        }
        // People don't thin the woods: only a farming site's few field
        // plots, just outside its clearing, are bare of trees.
        if (art_field(foot, cell) > 0.5) {
            return K_NONE;
        }
    }
    let bank = art_bank(gp);
    if (bank.y <= 0.0 || bank.x >= RIVER_BANK) {
        return kind;
    }
    if (bank.x < RIVER_CLEAR) {
        return K_NONE;
    }
    return art_riparian(kind, terrain, h, bank.y);
}

fn art_glyph_entry(kind: u32, slot: u32, foot: vec2<f32>, size: f32) -> vec4<u32> {
    return vec4<u32>(kind | (slot << 8u), bitcast<u32>(foot.x), bitcast<u32>(foot.y), bitcast<u32>(size));
}

// Entry `want` of the hex's glyph list (see art_tex). Same layout and
// order as terrain_art drew them before the bake: mountains in three
// layers (northern foothills, peaks, southern foothills), other terrain in
// art_order.
fn art_glyph_list(cell: vec2<u32>, want: u32, blend: f32) -> vec4<u32> {
    let none = vec4<u32>(K_NONE, 0u, 0u, 0u);
    let st = textureLoad(state_tex, vec2<i32>(cell), 0);
    let terrain = st.r;
    if (terrain >= T_COUNT) {
        return none;
    }
    let nb = art_neighbours(cell, terrain);
    let h0 = art_hash(cell, 0u);
    let mirror = select(1.0, -1.0, (h0 & 1u) == 1u);
    let landform = (st.a >> 3u) & 3u;
    var found = 0u;
    if (art_is_mountain(terrain, landform)) {
        let mtn = art_mountain_neighbours(cell, true);
        let ps = art_peak_scale(cell, landform);
        let ms = art_massif(cell);
        let base = art_mountain_base(cell, h0, mirror, nb, mtn, ps, ms);
        var dressed: array<MassifSlot, ART_SLOTS>;
        for (var i = 0u; i < ART_SLOTS; i++) {
            dressed[i] = art_mountain_dressed(i, cell, terrain, base, ms);
        }
        // Crags 5 and 6 stand behind the main peaks, crag 7 in front; the
        // growth in the slots after them north or south of the peaks.
        var order = array<u32, 12>(8u, 9u, 5u, 6u, 0u, 1u, 7u, 2u, 3u, 4u, 10u, 11u);
        for (var layer = 0u; layer < 3u; layer++) {
            for (var n = 0u; n < 12u; n++) {
                let i = order[n];
                let m = dressed[i];
                // Peaks and the hills standing in for them (slots 0-1) in
                // the middle layer; foothills and growth north or south.
                let layer_of = select(select(2u, 0u, m.foot.y > 0.0), 1u, m.kind == K_PEAK || i < 2u);
                if (m.kind == K_NONE || layer_of != layer || art_relief_drops(i, cell, m, blend)) { continue; }
                if (m.kind != K_HILL && art_hidden(m.foot, cell, terrain, nb, blend)) { continue; }
                if (m.kind < K_PEAK) {
                    if (found == want) {
                        return art_glyph_entry(m.kind, i, m.foot - vec2<f32>(0.0, 0.15), m.size / 1.45);
                    }
                    found++;
                    continue;
                }
                let st = art_settle(m.kind, m.foot, m.size, cell, ms);
                if (st.z <= 0.0) { continue; }
                if (found == want) {
                    return art_glyph_entry(u32(st.w), i, st.xy, st.z);
                }
                found++;
            }
        }
        return none;
    }
    // Every slot's glyph, then the `want`-th from the back (north): the
    // layout is turned and shaken per hex, so the order is by where the
    // slots ended up, not by their number.
    let skip = (h0 >> 1u) % 5u;
    var kinds: array<u32, ART_SLOTS>;
    var feet: array<vec3<f32>, ART_SLOTS>;
    for (var i = 0u; i < ART_SLOTS; i++) {
        let s = art_slot(i, cell, mirror);
        let foot = s.xy + vec2<f32>(0.0, 0.15);
        var kind = art_kind_by_river(terrain, landform, i, skip, foot, cell);
        if (kind != K_NONE && art_hidden(foot, cell, terrain, nb, blend)) {
            kind = K_NONE;
        }
        var f = s;
        if (kind == K_HILL) {
            // Fitted as art_prop_layout fits the prop (whose foot is 0.15
            // further north and size 1.45 times the slot's).
            let st = art_settle(kind, foot, s.z * 1.45, cell, art_massif(cell));
            kind = select(K_NONE, u32(st.w), st.z > 0.0);
            f = vec3<f32>(st.xy - vec2<f32>(0.0, 0.15), st.z / 1.45);
        }
        if (kind != K_NONE && art_is_grove(terrain, i, kind)) {
            // Sized as art_prop_layout sizes the prop.
            f.z *= art_grove_size(terrain, kind, foot, s.z * 1.45, cell);
            kind |= ART_GROVE_BIT;
        }
        kinds[i] = kind;
        feet[i] = f;
    }
    for (var i = 0u; i < ART_SLOTS; i++) {
        if (kinds[i] == K_NONE) { continue; }
        var behind = 0u;
        for (var j = 0u; j < ART_SLOTS; j++) {
            if (kinds[j] != K_NONE && (feet[j].y > feet[i].y || (feet[j].y == feet[i].y && j < i))) {
                behind++;
            }
        }
        if (behind == want) {
            return art_glyph_entry(kinds[i], i, feet[i].xy, feet[i].z);
        }
    }
    return none;
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

// What covers a mountain's or hill's slopes in this biome (linear rgb) and
// how much of the rock it hides: forest slopes read green, desert ones sand,
// tundra and alpine ones mostly bare.
fn art_slope_cover(terrain: u32) -> vec4<f32> {
    // A shade lighter than the trees, so a wooded slope reads as green in
    // the sun rather than as dark rock.
    var c = vec4<f32>(pow(art_fill(terrain) * 1.35 + 0.05, vec3<f32>(2.2)), 0.45);
    switch terrain {
        case T_BOREAL_FOREST, T_TEMPERATE_FOREST, T_TROPICAL_FOREST: { c.w = 0.7; }
        case T_WOODLANDS, T_STEPPE_FOREST, T_FLOODPLAIN: { c.w = 0.6; }
        case T_EXTREME_DESERT: { c = vec4<f32>(art_rgb(0.80, 0.66, 0.46), 0.55); }
        case T_SEMI_DESERT: { c = vec4<f32>(art_rgb(0.72, 0.62, 0.44), 0.5); }
        case T_TUNDRA, T_ALPINE: { c.w = 0.3; }
        default: {}
    }
    return c;
}

// Canopy colour per terrain in the Ground map mode, as linear albedo: real
// foliage seen from above is dark and only mildly green (red about half of
// green, blue lower still; see data/terrain/SOURCES.md, "Micro-prop
// colours"), not the terrain map's saturated poster green. Scaled up about
// 1.5x like the ground covers, so trees sit a shade darker than the grass
// around them. Conifers darkest, sclerophyll and desert shrubs grey-olive.
fn art_fill_real(terrain: u32) -> vec3<f32> {
    var c = vec3<f32>(0.070, 0.105, 0.040);
    switch terrain {
        case T_BOREAL_FOREST: { c = vec3<f32>(0.040, 0.062, 0.040); }
        case T_TROPICAL_FOREST: { c = vec3<f32>(0.050, 0.092, 0.036); }
        case T_TEMPERATE_FOREST: { c = vec3<f32>(0.062, 0.100, 0.036); }
        case T_WOODLANDS: { c = vec3<f32>(0.078, 0.112, 0.042); }
        case T_STEPPE_FOREST: { c = vec3<f32>(0.058, 0.085, 0.045); }
        case T_SAVANNAH: { c = vec3<f32>(0.110, 0.118, 0.058); }
        case T_CHAPARRAL: { c = vec3<f32>(0.098, 0.106, 0.066); }
        case T_SEMI_DESERT: { c = vec3<f32>(0.150, 0.155, 0.105); }
        case T_TUNDRA: { c = vec3<f32>(0.100, 0.100, 0.062); }
        case T_ALPINE: { c = vec3<f32>(0.092, 0.098, 0.066); }
        case T_FLOODPLAIN: { c = vec3<f32>(0.072, 0.122, 0.042); }
        default: {}
    }
    return c;
}

// A prop's colour in the Ground map mode (linear): realistic foliage, grey
// bark, grey-brown rock and slopes in the hex's own ground colour.
fn art_prop_colour_real(kind: u32, band: u32, top: bool, terrain: u32, snow: bool) -> vec3<f32> {
    // Shaded underside to sunlit crown.
    var c = art_fill_real(terrain) * (0.80 + 0.35 * f32(band) * 0.5);
    let ground = textureLoad(palette_tex, vec2<i32>(i32(terrain), i32(MODE_GROUND)), 0).rgb;
    let rock = vec3<f32>(0.24, 0.225, 0.21);
    if (kind == K_PEAK) {
        let cover = art_slope_cover(terrain).w;
        if (band == 0u) {
            c = mix(rock, ground * 0.9, cover * select(1.0, 0.55, top));
        } else if (snow) {
            c = vec3<f32>(0.80, 0.82, 0.85);
        } else {
            c = mix(rock * 1.1, ground, cover * 0.3);
        }
    } else if (kind == K_HILL) {
        c = mix(rock, ground * 0.9, art_slope_cover(terrain).w);
    } else if (kind == K_PALM && band == 1u) {
        c = vec3<f32>(0.080, 0.110, 0.042);
    } else if (band == 0u && kind != K_SHRUB) {
        c = vec3<f32>(0.105, 0.085, 0.065); // bark
    }
    return c * select(0.85, 1.05, top);
}

// `snow`: the peak is high (or cold) enough to keep a cap.
fn art_prop_colour(kind: u32, band: u32, top: bool, terrain: u32, snow: bool) -> vec3<f32> {
    let f = art_fill(terrain);
    var c = pow(mix(f, f * 1.45 + 0.07, f32(band) * 0.5 - 0.25), vec3<f32>(2.2));
    if (kind == K_PEAK) {
        let cover = art_slope_cover(terrain);
        let rock = art_rgb(0.57, 0.52, 0.46);
        if (band == 0u) {
            // Lower slopes: the biome, thinning out towards the shoulder.
            c = mix(rock, cover.rgb, cover.w * select(1.0, 0.55, top));
        } else if (snow) {
            c = art_rgb(0.98, 0.98, 1.0);
        } else {
            c = mix(rock * 1.15, cover.rgb, cover.w * 0.3);
        }
    } else if (kind == K_HILL) {
        let cover = art_slope_cover(terrain);
        c = mix(art_rgb(0.52, 0.53, 0.38), cover.rgb, cover.w);
    } else if (kind == K_PALM && band == 1u) {
        c = art_rgb(0.16, 0.50, 0.16);
    } else if (band == 0u && kind != K_SHRUB) {
        c = art_rgb(0.42, 0.28, 0.16); // trunk
    }
    return c * select(0.82, 1.08, top);
}

// ------------------------------------------------------ prop layout bake ----
// What stands in each prop slot (kind, foot, size, hidden by a neighbour's
// ground) depends only on the map and the edge-blend setting, but takes a
// dozen neighbour fetches and some noise to work out. fs_slot_bake works it
// out once per (hex, slot) into prop_tex whenever those change, and the 30
// vertices of each prop just read it back.
//
// (col * 4 + slot % 4, row * 3 + slot / 4) -> x: kind (K_NONE when nothing
// stands there, or it is hidden), y, z: foot (hex-local), w: size; floats as
// bits. 4 × 3 slots per hex keeps it within WebGL2's 2048-texel limit.
@group(0) @binding(5) var prop_tex: texture_2d<u32>;

fn art_prop_texel(cell: vec2<u32>, slot: u32) -> vec2<i32> {
    return vec2<i32>(i32(cell.x * 4u + slot % 4u), i32(cell.y * 3u + slot / 4u));
}

// When the relief shapes the mountains (board.wgsl, surface_lift) the
// peak and hill props give way to it: only a summit at least ACCENT_ELEV
// metres high and higher than every neighbour's (Mont Blanc, Elbrus,
// Ararat) keeps its main peak, as a landmark; the rest is bare ground
// (growth on it stays). Shared by the props and their glyphs and shadows
// (art_glyph_list).
// A kept accent peak on heightmap-shaped ground, against a freestanding
// one: height and footprint scales, and how far (in units of its size) its
// foot sinks below the surface.
// Low, broad and sunk well in, so it reads as the top of the range it
// stands on rather than a pillar set on it (at 0.65 / 1.0 / 0.06 the
// Caucasus summits stood up like obelisks).
const ACCENT_HEIGHT: f32 = 0.5;
// The rise of real ground (metres) a modelled-size conifer matches in
// height, and the least tree size that leaves them (see vs_prop).
const TREE_RELIEF_M: f32 = 1000.0;
const TREE_MIN_SCALE: f32 = 0.15;
const ACCENT_WIDTH: f32 = 1.4;
const ACCENT_SINK: f32 = 0.14;
const ACCENT_SHOULDER: f32 = 0.6;
// An accent on a range with a grain runs along it: stretch along the
// strike and narrowing across it, at full coherence (cones keep round).
const ACCENT_STRETCH: vec2<f32> = vec2<f32>(1.6, 0.8);
const ACCENT_ELEV: f32 = 3500.0;

fn art_summit_elev(c: vec2<i32>) -> f32 {
    if (c.x < 0 || c.y < 0 || c.x >= i32(g.grid.x) || c.y >= i32(g.grid.y)) {
        return -9999.0;
    }
    let m = art_massif(vec2<u32>(c));
    return select(-9999.0, m.floor + art_summit(vec2<u32>(c), 0u).z, m.count > 0u);
}

fn art_relief_drops(slot: u32, cell: vec2<u32>, m: MassifSlot, blend: f32) -> bool {
    if (g.relief.w < 0.5 || blend < 0.5 || (m.kind != K_PEAK && m.kind != K_HILL)) {
        return false;
    }
    if (slot != 0u || m.kind != K_PEAK || m.elev < ACCENT_ELEV) {
        return true;
    }
    let c = vec2<i32>(cell);
    let own = art_summit_elev(c);
    for (var e = 0u; e < 6u; e++) {
        let o = art_summit_elev(c + neighbour_offset(cell.x & 1u, e));
        // Ties go to the lower edge index's side, so one of a pair stays.
        if (o > own || (o == own && e < 3u)) {
            return true;
        }
    }
    return false;
}

fn art_prop_layout(cell: vec2<u32>, slot: u32, blend: f32) -> vec4<u32> {
    let none = vec4<u32>(K_NONE, 0u, 0u, 0u);
    let st = textureLoad(state_tex, vec2<i32>(cell), 0);
    let terrain = st.r;
    if (terrain >= T_COUNT || terrain == T_WATER) {
        return none;
    }
    let h0 = art_hash(cell, 0u);
    let mirror = select(1.0, -1.0, (h0 & 1u) == 1u);
    let nb = art_neighbours(cell, terrain);

    var kind = K_NONE;
    var at = vec2<f32>(0.0);
    var size = 1.0;
    var elev = -9999.0;
    let landform = (st.a >> 3u) & 3u;
    let ms = art_massif(cell);
    if (art_is_mountain(terrain, landform)) {
        let base = art_mountain_base(cell, h0, mirror, nb, art_mountain_neighbours(cell, true), art_peak_scale(cell, landform), ms);
        let m = art_mountain_dressed(slot, cell, terrain, base, ms);
        kind = m.kind;
        if (art_relief_drops(slot, cell, m, blend)) {
            kind = K_NONE;
        }
        at = m.foot;
        size = m.size;
        elev = m.elev;
    } else {
        let s = art_slot(slot, cell, mirror);
        at = s.xy + vec2<f32>(0.0, 0.15);
        kind = art_kind_by_river(terrain, landform, slot, (h0 >> 1u) % 5u, at, cell);
        size = s.z * 1.45;
    }
    if (kind == K_NONE || kind > K_HILL) {
        return none;
    }
    if (kind != K_HILL && art_hidden(at, cell, terrain, nb, blend)) {
        return none;
    }
    if (kind == K_PEAK || kind == K_HILL) {
        let st = art_settle(kind, at, size, cell, ms);
        if (st.z <= 0.0) {
            return none;
        }
        // x: the kind, and the summit's elevation above it for the snow.
        return vec4<u32>(u32(st.w) | (art_elev_code(elev) << 16u), bitcast<u32>(st.x), bitcast<u32>(st.y), bitcast<u32>(st.z));
    }
    if (art_in_river(at, cell) || art_camp(at, cell) < 1.0) {
        return none;
    }
    if (!art_is_mountain(terrain, landform) && art_is_grove(terrain, slot, kind)) {
        size *= art_grove_size(terrain, kind, at, size, cell);
        return vec4<u32>(kind | K_GROVE_BIT, bitcast<u32>(at.x), bitcast<u32>(at.y), bitcast<u32>(size));
    }
    return vec4<u32>(kind, bitcast<u32>(at.x), bitcast<u32>(at.y), bitcast<u32>(size));
}

struct SlotBake {
    @location(0) props: vec4<u32>,
    @location(1) glyphs: vec4<u32>,
};

// Drawn over the whole of prop_tex and art_tex (same size: 4 x 3 texels per
// hex) with vs_fullscreen: texel n of a hex is the prop in slot n and the
// n-th glyph to draw.
@fragment
fn fs_slot_bake(@builtin(position) pos: vec4<f32>) -> SlotBake {
    var out: SlotBake;
    out.props = vec4<u32>(K_NONE, 0u, 0u, 0u);
    out.glyphs = out.props;
    let p = vec2<u32>(pos.xy);
    let cell = vec2<u32>(p.x / 4u, p.y / 3u);
    let n = (p.y % 3u) * 4u + p.x % 4u;
    if (n >= ART_SLOTS || cell.x >= u32(g.grid.x) || cell.y >= u32(g.grid.y)) {
        return out;
    }
    let blend = g.art.w * f32(terrain_like(u32(g.grid.z)));
    out.props = art_prop_layout(cell, n, blend);
    out.glyphs = art_glyph_list(cell, n, blend);
    return out;
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
    let lod = smoothstep(PROP_PX_LO, PROP_PX_HI, hex_px) * g.art.y;
    if (lod <= 0.0) {
        return out;
    }
    let slot = in.attrs.x;
    // Zoomed in, the detail slots sprout (same rule as the printed details).
    let detail = smoothstep(ART_DETAIL_LO, ART_DETAIL_HI, hex_px);
    let grow = art_sprout(slot, in.cell, detail);
    if (grow <= 0.0) {
        return out;
    }

    // What stands in this slot, baked by fs_slot_bake when the map changed.
    let lay = textureLoad(prop_tex, art_prop_texel(in.cell, slot), 0);
    // Peaks and hills carry their summit's elevation in the top 16 bits.
    let kind = lay.x & 0xffu;
    if (kind == K_NONE) {
        return out;
    }
    let elev_code = lay.x >> 16u;
    let summit = f32(elev_code) * 20.0 - 1000.0;
    let at = vec2<f32>(bitcast<f32>(lay.y), bitcast<f32>(lay.z));
    var size = bitcast<f32>(lay.w);
    let st = textureLoad(state_tex, vec2<i32>(in.cell), 0);
    let terrain = st.r;
    let band = in.attrs.y;
    let top = in.attrs.z == 1u;
    let mode = u32(g.grid.z);
    let grove = (lay.x & K_GROVE_BIT) != 0u;
    let prof = select(art_profile(kind, band), art_grove_profile(kind, band), grove);
    if (prof.x + prof.z <= 0.0) {
        return out;
    }

    // Squashed hexes get smaller props.
    let asp = mix(min(length(in.east) / unit_c, 1.0), 1.0, t);
    size *= sqrt(asp) * lod * grow * art_shrink_g(kind, grove, detail);
    let hs = art_hash(in.cell, 40u + slot);
    var r = select(prof.x, prof.z, top) * size;
    var h = select(prof.y, prof.w, top) * size;
    if (kind <= K_PALM) {
        // No two trees the same height.
        h *= 0.85 + 0.35 * art_unit(hs, 24u);
    }
    if (kind <= K_SHRUB) {
        // Trees in the relief's scale: a conifer stands as tall as
        // TREE_RELIEF_M of real ground at the current exaggeration, so a
        // low range rises over its forest instead of drowning in it. Height
        // in full, half (geometrically) in the crown, as "Mountain height"
        // does; never above the modelled size. Relief off: as modelled.
        let k = select(1.0, clamp(g.hex.z * TREE_RELIEF_M / (art_prop_dims(K_CONIFER).y * unit_c), TREE_MIN_SCALE, 1.0), g.hex.z > 0.0);
        h *= k;
        r *= sqrt(k);
    }
    var grove_lean = vec2<f32>(0.0);
    if (grove) {
        // Three crowns in a clump, each lumpy (every side of its ring its
        // own radius), its own height, its top a little off centre.
        let hc = art_hash(in.cell, 300u + slot * 4u + band);
        grove_lean = art_grove_crown(kind, band, art_unit(hs, 4u)) * size;
        if (top) {
            h *= 0.85 + 0.3 * art_unit(hc, 0u);
            let la = art_unit(hc, 8u) * 6.2831853;
            grove_lean += vec2<f32>(cos(la), sin(la)) * 0.05 * size;
        } else {
            r *= 0.72 + 0.56 * art_unit(art_hash(in.cell, 320u + slot * 16u + band * 5u + in.attrs.w), 0u);
        }
    }
    if (kind == K_PEAK || kind == K_HILL) {
        // Craggy: each side of the lathe has its own radius.
        r *= 0.78 + 0.44 * art_unit(art_hash(in.cell, 60u + slot * 8u + in.attrs.w), 0u);
    }
    var lean = vec2<f32>(0.0);
    if (kind == K_PEAK) {
        // No two peaks alike: tall and narrow to low and broad, leaning a
        // little, the lean growing with height so the foot stays put.
        // A peak standing on a raster summit is already sized by it, so it
        // varies less.
        let hp = art_hash(in.cell, 70u + slot);
        let v = art_unit(hp, 0u);
        let dem = elev_code != 0u;
        h *= select(mix(0.72, 1.3, v), mix(0.9, 1.12, v), dem);
        r *= select(mix(1.18, 0.86, v), mix(1.06, 0.94, v), dem);
        let la = art_unit(hp, 8u) * 6.2831853;
        lean = vec2<f32>(cos(la), sin(la)) * 0.16 * art_unit(hp, 16u) * size * (select(prof.y, prof.w, top) / 0.64)
            * select(1.0, 0.4, dem);
        // Low ranges stand lower than their footprint alone would make them.
        if (dem) {
            h *= mix(0.6, 1.0, smoothstep(300.0, 2300.0, summit - art_massif(in.cell).floor));
        } else {
            let st_lf = (st.a >> 3u) & 3u;
            h *= mix(0.55, 1.0, art_peak_scale(in.cell, st_lf));
        }
    }
    if (kind == K_PEAK || kind == K_HILL) {
        // Board style "Mountain height": all of it in the height, half of
        // it (geometrically) in the footprint.
        h *= g.wall_colour.w;
        r *= sqrt(g.wall_colour.w);
    }
    var dw = 0.0;
    if (kind == K_PEAK) {
        // On heightmap-shaped ground the mountain is already there: the
        // accent is a small crag on top, its foot sunk into the slope so it
        // grows out of the rock instead of sitting on it like a box.
        dw = dem_weight(art_global(at, in.cell));
        h *= mix(1.0, ACCENT_HEIGHT, dw);
        r *= mix(1.0, ACCENT_WIDTH, dw);
        h -= ACCENT_SINK * size * dw;
        // Lowered, the rock band's broad shoulder makes a boulder: pull it
        // in so the accent comes to a point like the crest it crowns.
        if ((band == 0u) == top) {
            r *= mix(1.0, ACCENT_SHOULDER, dw);
        }
    }
    let ang = (f32(in.attrs.w) + art_unit(hs, 0u)) * 1.2566371;
    var ring = vec2<f32>(cos(ang), sin(ang)) * r;
    if (kind == K_PEAK) {
        // Ridges run along their strike: long and narrow. The strike is
        // hex-local, and the board squashes x by `asp`.
        let ms = art_massif(in.cell);
        if (ms.kind == MK_RIDGE || (dw > 0.0 && ms.kind == MK_MASSIF)) {
            // An accent follows the range's grain too, so it lies along
            // the crest the relief draws instead of standing across it.
            let sk = mix(art_ridge_stretch(ms), ACCENT_STRETCH, dw * smoothstep(0.2, 0.6, ms.coherence));
            let d = normalize(vec2<f32>(ms.dir.x * asp, ms.dir.y));
            let n = vec2<f32>(-d.y, d.x);
            ring = d * dot(ring, d) * sk.x + n * dot(ring, n) * sk.y;
            // Pinched across the strike, a peak at full height reads as a
            // cardboard fin; a ridge is a long, low crest, so it loses more
            // height than width and tilts and leans less.
            h *= sk.y * sqrt(sk.y);
            lean *= sk.y;
        }
    }
    ring += lean + grove_lean;

    // Standing on the hex's tile, raised by the relief.
    var lift = ground_lift(vec2<i32>(in.cell), at);
    if (kind == K_PEAK || kind == K_HILL) {
        // Draped: the foot follows the ground under each vertex, so on a
        // slope the skirt meets the hillside instead of hanging off it,
        // easing to the centre's height up the flanks.
        let foot = ground_lift(vec2<i32>(in.cell), at + ring);
        let up = clamp(select(prof.y, prof.w, top) / max(max(art_profile(kind, 0u).w, art_profile(kind, 1u).w), 1e-4), 0.0, 1.0);
        lift = mix(min(foot, lift), lift, smoothstep(0.0, 0.6, up));
    }
    let curved = in.centre * (1.0 + lift) + in.east * at.x + in.north * (at.y / SQRT3_2)
        + (normalize(in.east) * ring.x + normalize(in.north) * ring.y + normalize(in.centre) * h) * unit_c;
    let flat_p = vec3<f32>(
        in.flat_pos.x + g.hex.x * at.x + ring.x * unit_f,
        1.0 + lift + h * unit_f,
        -(in.flat_pos.y + g.hex.y * at.y / SQRT3_2 + ring.y * unit_f),
    );
    let world = mix(curved, flat_p, t);

    // Snow on peaks standing high: the summit's own elevation where the
    // massif sketch gives it, else the hex's median height. Lower in cold
    // biomes.
    // A summit stands well above its hex's median, so it takes a higher line.
    let ground = select(f32(textureLoad(height_tex, vec2<i32>(in.cell), 0).r), summit, elev_code != 0u);
    let cold = terrain == T_ALPINE || terrain == T_TUNDRA || terrain == T_BOREAL_FOREST;
    let snow = ground > select(select(2200.0, 1100.0, cold), select(2900.0, 1900.0, cold), elev_code != 0u);
    // A grove is all foliage: shaded underside to sunlit crown, no trunk.
    let ck = select(kind, K_SHRUB, grove);
    var colour = art_prop_colour(ck, band, top, terrain, snow);
    if (mode == MODE_GROUND) {
        colour = art_prop_colour_real(ck, band, top, terrain, snow);
    }
    // Variation: stands of lighter and darker trees across the board (noise
    // on board-wide coordinates), and each prop a little off its neighbours.
    let own = art_unit(hs, 8u);
    if (kind <= K_SHRUB && (band > 0u || ck == K_SHRUB)) {
        let stand = art_noise(art_global(at, in.cell) * 0.45 + 3.0);
        let warm = (0.5 * stand + 0.5 * art_unit(hs, 16u)) * 2.0 - 1.0;
        colour *= (0.78 + 0.44 * (0.55 * stand + 0.45 * own))
            * vec3<f32>(1.0 + 0.18 * warm, 1.0 + 0.03 * warm, 1.0 - 0.14 * warm);
    } else if (kind == K_PEAK || kind == K_HILL) {
        colour *= 0.92 + 0.16 * own;
    }
    // Darker towards the foot, where less sky reaches (off in flat lighting).
    let rise = select(prof.y, prof.w, top) / art_dims(kind, grove).y;
    colour *= mix(mix(0.56, 1.0, smoothstep(0.0, 0.55, rise)), 1.0, g.lines.w);
    if (!terrain_like(mode)) {
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
    return vec4<f32>(haze(in.colour * lighting(n), in.world), 1.0);
}

// ------------------------------------------------------------- locating ----
// The hex whose tile is under board-wide point `gp` (art_global), clamped
// to the board.
fn art_locate(gp: vec2<f32>) -> vec2<i32> {
    let c0 = i32(round(gp.x / 1.5));
    var best = vec2<i32>(0);
    var bd = 1e9;
    for (var dc = -1; dc <= 1; dc++) {
        let c = c0 + dc;
        let par = f32(c & 1);
        let r = i32(round(-gp.y / 1.7320508 - 0.5 * par));
        let d = distance(gp, vec2<f32>(1.5 * f32(c), -1.7320508 * (f32(r) + 0.5 * par)));
        if (d < bd) {
            bd = d;
            best = vec2<i32>(c, r);
        }
    }
    return clamp(best, vec2<i32>(0), vec2<i32>(i32(g.grid.x) - 1, i32(g.grid.y) - 1));
}

// --------------------------------------------------------- micro-props ----
// The close-up layer: stones, grass tufts, flowers, reeds, ferns, stumps,
// scrub, cushion plants, the odd succulent or termite mound, scattered
// between the big props once a hex is MICRO_PX across. Terrain map only.
// Nothing is baked: each vertex hashes its slot's foot, finds the ground
// under it (micro_ground, the same field fs_board draws) and
// keeps clear of rivers, camps and the big props. Colours are linear albedo
// from measured references (see micro_colour), not the map's palette.

// MICRO_PX_LO, MICRO_PX_HI and MICRO_SLOTS come from renderer.rs.
const MICRO_SALT: u32 = 900u;
// All the profiles below, scaled: big enough to read at the closest zoom.
const MICRO_SCALE: f32 = 1.7;

const M_NONE: u32 = 0u;
const M_STONE: u32 = 1u;
const M_TUFT: u32 = 2u;
const M_FLOWER: u32 = 3u;
const M_REED: u32 = 4u;
const M_STUMP: u32 = 5u;
const M_FERN: u32 = 6u;
const M_SUCCULENT: u32 = 7u;
const M_MOUND: u32 = 8u;
const M_SCRUB: u32 = 9u;
const M_CUSHION: u32 = 10u;
const M_BOULDER: u32 = 11u;

// The terrain the ground field draws at `local` in `cell` (fs_board's A/B
// pick), for close views (warp fully in, seven-hex kernel). Must follow
// fs_board.
fn micro_ground(local: vec2<f32>, cellu: vec2<u32>) -> u32 {
    let cell = vec2<i32>(cellu);
    let own = textureLoad(state_tex, cell, 0).r;
    if (g.art.w < 0.5) {
        return own;
    }
    let gp = art_global(local, cellu);
    let warp = (vec2<f32>(art_noise(gp * 1.1 + 3.0), art_noise(gp * 1.1 + 41.0)) * 0.7
        + vec2<f32>(art_noise(gp * 3.3 + 19.0), art_noise(gp * 3.3 + 67.0)) * 0.3 - 0.5) * 2.0 * FIELD_WARP;
    let p = local + warp;
    let radius = FIELD_RADIUS - FIELD_WARP * 1.4143;
    let par = cellu.x & 1u;
    var cells: array<vec2<i32>, 7>;
    var keys: array<u32, 7>;
    var d2: array<f32, 7>;
    var offs: array<vec2<f32>, 7>;
    for (var i = 0u; i < 7u; i++) {
        var c = cell;
        var centre = vec2<f32>(0.0);
        if (i > 0u) {
            c = cell + neighbour_offset(par, i - 1u);
            centre = edge_normal(i - 1u) * 1.7320508;
        }
        let inside = c.x >= 0 && c.y >= 0 && c.x < i32(g.grid.x) && c.y < i32(g.grid.y);
        let off = p - centre;
        offs[i] = off;
        d2[i] = select(1e9, dot(off, off), inside);
        cells[i] = select(cell, c, inside);
        keys[i] = textureLoad(hex_tex, cells[i], 0).w & 0x1ffffffu;
    }
    var ia = 0u;
    for (var i = 1u; i < 7u; i++) {
        if (d2[i] < d2[ia]) { ia = i; }
    }
    let key_a = keys[ia];
    var ib = ia;
    for (var i = 0u; i < 7u; i++) {
        if (keys[i] != key_a && d2[i] < 1e8 && (ib == ia || d2[i] < d2[ib])) { ib = i; }
    }
    let key_b = keys[ib];
    var a_sum = 0.0;
    var b_sum = 0.0;
    var da = vec2<f32>(0.0);
    var db = vec2<f32>(0.0);
    for (var i = 0u; i < 7u; i++) {
        let off = offs[i];
        let q = max(1.0 - dot(off, off) / (radius * radius), 0.0);
        if (q <= 0.0) { continue; }
        let w = q * q * q;
        let gw = -6.0 * q * q * off / (radius * radius);
        // (cells[i] is this hex off the board, as in fs_board.)
        let key = keys[i];
        if (key == key_a) { a_sum += w; da += gw; }
        else if (key == key_b) { b_sum += w; db += gw; }
    }
    var take_a = true;
    if (key_b != key_a) {
        take_a = (a_sum - b_sum) / max(length(da - db), 1e-4) >= 0.0;
    }
    let pick = select(ib, ia, take_a);
    if (((keys[pick] >> 24u) & 1u) == 1u) {
        return T_WATER;
    }
    return textureLoad(state_tex, cells[pick], 0).r;
}

// What grows or lies at a micro slot, by the ground's terrain; `u` 0..1.
fn micro_kind(terrain: u32, u: f32) -> u32 {
    var k = M_NONE;
    switch terrain {
        case T_GRASSLAND, T_PLAINS, T_LAND, T_FREE: {
            if (u < 0.58) { k = M_TUFT; } else if (u < 0.74) { k = M_FLOWER; } else if (u < 0.84) { k = M_STONE; }
        }
        case T_STEPPE_FOREST: {
            if (u < 0.5) { k = M_TUFT; } else if (u < 0.64) { k = M_STONE; } else if (u < 0.72) { k = M_FLOWER; } else if (u < 0.8) { k = M_SCRUB; }
        }
        case T_SAVANNAH: {
            if (u < 0.6) { k = M_TUFT; } else if (u < 0.66) { k = M_MOUND; } else if (u < 0.75) { k = M_STONE; } else if (u < 0.82) { k = M_SCRUB; }
        }
        case T_TEMPERATE_FOREST, T_WOODLANDS: {
            if (u < 0.4) { k = M_FERN; } else if (u < 0.52) { k = M_STUMP; } else if (u < 0.64) { k = M_STONE; } else if (u < 0.74) { k = M_TUFT; }
        }
        case T_BOREAL_FOREST: {
            if (u < 0.3) { k = M_FERN; } else if (u < 0.45) { k = M_STUMP; } else if (u < 0.56) { k = M_BOULDER; } else if (u < 0.7) { k = M_CUSHION; }
        }
        case T_TROPICAL_FOREST: {
            if (u < 0.6) { k = M_FERN; } else if (u < 0.7) { k = M_STUMP; } else if (u < 0.75) { k = M_STONE; }
        }
        case T_CHAPARRAL: {
            if (u < 0.45) { k = M_SCRUB; } else if (u < 0.68) { k = M_STONE; } else if (u < 0.8) { k = M_TUFT; }
        }
        case T_SEMI_DESERT: {
            if (u < 0.33) { k = M_SCRUB; } else if (u < 0.62) { k = M_STONE; } else if (u < 0.72) { k = M_TUFT; } else if (u < 0.75) { k = M_SUCCULENT; }
        }
        case T_EXTREME_DESERT: {
            if (u < 0.45) { k = M_STONE; } else if (u < 0.55) { k = M_BOULDER; } else if (u < 0.6) { k = M_SCRUB; }
        }
        case T_TUNDRA: {
            if (u < 0.35) { k = M_CUSHION; } else if (u < 0.5) { k = M_BOULDER; } else if (u < 0.65) { k = M_STONE; } else if (u < 0.8) { k = M_TUFT; }
        }
        case T_ALPINE: {
            if (u < 0.3) { k = M_CUSHION; } else if (u < 0.6) { k = M_STONE; } else if (u < 0.72) { k = M_BOULDER; } else if (u < 0.8) { k = M_FLOWER; }
        }
        case T_FLOODPLAIN: {
            if (u < 0.55) { k = M_REED; } else if (u < 0.75) { k = M_TUFT; } else if (u < 0.8) { k = M_STONE; }
        }
        case T_MOUNTAINS: {
            if (u < 0.55) { k = M_STONE; } else if (u < 0.7) { k = M_BOULDER; } else if (u < 0.8) { k = M_TUFT; }
        }
        default: {}
    }
    return k;
}

// Two bands of a micro-prop's lathe (bottom radius, bottom height, top
// radius, top height), hex-local units; all zero = unused.
fn micro_profile(kind: u32, band: u32) -> vec4<f32> {
    var bands = array<vec4<f32>, 22>(
        // stone: flank, dome
        vec4<f32>(0.045, 0.0, 0.042, 0.018), vec4<f32>(0.042, 0.018, 0.0, 0.034),
        // grass tuft: a clump flaring up, closed at the top
        vec4<f32>(0.010, 0.0, 0.036, 0.060), vec4<f32>(0.036, 0.060, 0.0, 0.064),
        // flower: stem, bloom
        vec4<f32>(0.016, 0.0, 0.008, 0.050), vec4<f32>(0.024, 0.048, 0.0, 0.062),
        // reed: stems, seed head
        vec4<f32>(0.018, 0.0, 0.006, 0.120), vec4<f32>(0.010, 0.105, 0.0, 0.150),
        // stump: bark, cut face
        vec4<f32>(0.032, 0.0, 0.028, 0.030), vec4<f32>(0.028, 0.030, 0.0, 0.032),
        // fern: fronds flaring out, low crown
        vec4<f32>(0.010, 0.0, 0.065, 0.040), vec4<f32>(0.065, 0.040, 0.0, 0.046),
        // succulent: column, dome
        vec4<f32>(0.020, 0.0, 0.018, 0.100), vec4<f32>(0.018, 0.100, 0.0, 0.118),
        // termite mound: cone, tip
        vec4<f32>(0.045, 0.0, 0.016, 0.100), vec4<f32>(0.016, 0.100, 0.0, 0.120),
        // scrub: low bush
        vec4<f32>(0.040, 0.0, 0.052, 0.030), vec4<f32>(0.052, 0.030, 0.0, 0.052),
        // cushion plant: flat mat
        vec4<f32>(0.034, 0.0, 0.038, 0.010), vec4<f32>(0.038, 0.010, 0.0, 0.020),
        // boulder
        vec4<f32>(0.080, 0.0, 0.072, 0.036), vec4<f32>(0.072, 0.036, 0.0, 0.066),
    );
    return bands[(kind - 1u) * 2u + band];
}

// How dry a biome's grass is, 0 (green) to 1 (straw).
fn micro_dryness(terrain: u32) -> f32 {
    var d = 0.35;
    switch terrain {
        case T_FLOODPLAIN: { d = 0.08; }
        case T_TEMPERATE_FOREST, T_WOODLANDS, T_TROPICAL_FOREST, T_BOREAL_FOREST: { d = 0.15; }
        case T_ALPINE: { d = 0.3; }
        case T_PLAINS: { d = 0.42; }
        case T_TUNDRA: { d = 0.5; }
        case T_STEPPE_FOREST: { d = 0.6; }
        case T_CHAPARRAL, T_SEMI_DESERT, T_MOUNTAINS: { d = 0.72; }
        case T_SAVANNAH, T_EXTREME_DESERT: { d = 0.88; }
        default: {}
    }
    return d;
}

// Linear albedo of a micro-prop's band. Values are typical measured
// reflectances (visible band, see data/terrain/SOURCES.md, "Micro-prop colours"): green grass
// about 0.10-0.20, cured grass and straw 0.35-0.45, bark under 0.2, granite
// and limestone 0.25-0.55, basalt about 0.1, sandstone reddish 0.3-0.45,
// lateritic soil red-brown, crustose lichen pale grey-green.
fn micro_colour(kind: u32, band: u32, terrain: u32, h: u32, gp: vec2<f32>) -> vec3<f32> {
    let green = vec3<f32>(0.075, 0.150, 0.035);
    let straw = vec3<f32>(0.42, 0.34, 0.17);
    // Drier and greener swathes across the board, not hex by hex.
    let dry = clamp(micro_dryness(terrain) + (art_noise(gp * 0.6 + 501.0) - 0.5) * 0.35, 0.0, 1.0);
    let grass = mix(green, straw, dry);
    let cold = terrain == T_TUNDRA || terrain == T_ALPINE || terrain == T_BOREAL_FOREST;
    let desert = terrain == T_EXTREME_DESERT || terrain == T_SEMI_DESERT;
    var rock = vec3<f32>(0.30, 0.29, 0.27);
    if (desert) {
        rock = vec3<f32>(0.44, 0.30, 0.18); // sandstone
    } else if (terrain == T_CHAPARRAL || terrain == T_MOUNTAINS) {
        rock = vec3<f32>(0.50, 0.47, 0.41); // limestone
    }
    // A few dark (basalt) stones anywhere.
    if (art_unit(h, 24u) < 0.12) {
        rock = vec3<f32>(0.10, 0.10, 0.10);
    }
    let lichen = vec3<f32>(0.42, 0.45, 0.30);
    let moss = vec3<f32>(0.10, 0.16, 0.04);
    var c = grass;
    switch kind {
        case M_STONE, M_BOULDER: {
            c = rock;
            if (band == 1u) {
                if (cold) { c = mix(rock, lichen, 0.55); }
                else if (terrain == T_TEMPERATE_FOREST || terrain == T_WOODLANDS || terrain == T_TROPICAL_FOREST) { c = mix(rock, moss, 0.6); }
            }
        }
        case M_TUFT: { c = grass; }
        case M_FLOWER: {
            if (band == 0u) {
                c = mix(green, grass, 0.5);
            } else {
                var blooms = array<vec3<f32>, 5>(
                    vec3<f32>(0.78, 0.78, 0.72), // white (chamomile, yarrow)
                    vec3<f32>(0.72, 0.55, 0.04), // yellow (buttercup, adonis)
                    vec3<f32>(0.28, 0.10, 0.45), // purple (thyme, crocus)
                    vec3<f32>(0.58, 0.04, 0.03), // red (poppy, anemone)
                    vec3<f32>(0.20, 0.25, 0.60), // blue (gentian, cornflower)
                );
                c = blooms[(h >> 8u) % 5u];
            }
        }
        case M_REED: {
            c = select(vec3<f32>(0.20, 0.12, 0.06), mix(vec3<f32>(0.20, 0.26, 0.07), straw, dry * 0.6), band == 0u);
        }
        case M_STUMP: {
            c = select(vec3<f32>(0.42, 0.31, 0.18), vec3<f32>(0.15, 0.10, 0.065), band == 0u);
        }
        case M_FERN: {
            c = select(vec3<f32>(0.06, 0.20, 0.035), moss, terrain == T_BOREAL_FOREST);
        }
        case M_SUCCULENT: { c = vec3<f32>(0.11, 0.20, 0.12); }
        case M_MOUND: { c = vec3<f32>(0.40, 0.22, 0.12); }
        case M_SCRUB: { c = select(vec3<f32>(0.18, 0.20, 0.10), vec3<f32>(0.14, 0.16, 0.07), band == 0u); }
        case M_CUSHION: { c = select(vec3<f32>(0.16, 0.22, 0.08), lichen, terrain == T_TUNDRA && band == 1u); }
        default: {}
    }
    // Each one a little off its neighbours (value and warmth, about ±8 %).
    let v = art_unit(h, 16u) * 2.0 - 1.0;
    let warm = art_unit(h, 0u) * 2.0 - 1.0;
    return c * (1.0 + 0.08 * v) * vec3<f32>(1.0 + 0.05 * warm, 1.0, 1.0 - 0.05 * warm);
}

@vertex
fn vs_micro(in: PropIn) -> PropOut {
    var out: PropOut;
    out.clip = vec4<f32>(2.0, 2.0, 2.0, 1.0);
    out.world = vec3<f32>(0.0);
    out.colour = vec3<f32>(0.0);
    if (!terrain_like(u32(g.grid.z))) {
        return out;
    }
    let t = g.cam_pos.w;
    let unit_c = length(in.north) / SQRT3_2;
    let unit_f = g.hex.y / SQRT3_2;
    let centre = mix(in.centre, vec3<f32>(in.flat_pos.x, 1.0, -in.flat_pos.y), t);
    let hex_px = mix(unit_c, unit_f, t) * g.art.z / max(distance(g.cam_pos.xyz, centre), 1e-6);
    let lod = smoothstep(MICRO_PX_LO, MICRO_PX_HI, hex_px) * g.art.y;
    if (lod <= 0.0) {
        return out;
    }
    // The slots fill in one after another as the hex grows.
    let slot = in.attrs.x;
    let start = f32(slot) / f32(MICRO_SLOTS) * 0.85;
    let grow = clamp((lod - start) / 0.15, 0.0, 1.0);
    if (grow <= 0.0) {
        return out;
    }
    let band = in.attrs.y;
    let top = in.attrs.z == 1u;
    let side = in.attrs.w;
    let h = art_hash(in.cell, MICRO_SALT + slot);
    let h2 = art_hash(in.cell, MICRO_SALT + 64u + slot);
    // Anywhere in the hex's inscribed circle, evenly.
    let ang0 = f32(h2 & 0xffffu) / 65535.0 * 6.2831853;
    let foot = vec2<f32>(cos(ang0), sin(ang0)) * 0.85 * sqrt(f32(h2 >> 16u) / 65535.0);

    let terrain = micro_ground(foot, in.cell);
    if (terrain >= T_COUNT || terrain == T_WATER || terrain == T_ICE) {
        return out;
    }
    let kind = micro_kind(terrain, art_unit(h, 0u));
    if (kind == M_NONE) {
        return out;
    }
    let prof = micro_profile(kind, band);
    if (prof.x + prof.z <= 0.0) {
        return out;
    }
    if (art_in_river(foot, in.cell) || art_camp(foot, in.cell) < 1.0) {
        return out;
    }
    // Nothing on a field plot but the crop (no ferns or stumps in a field).
    if (art_field(foot, in.cell) > 0.5) {
        return out;
    }
    // Clear of the big props' feet.
    for (var s = 0u; s < ART_SLOTS; s++) {
        let lay = textureLoad(prop_tex, art_prop_texel(in.cell, s), 0);
        let k = lay.x & 0xffu;
        if (k == K_NONE) { continue; }
        let at = vec2<f32>(bitcast<f32>(lay.y), bitcast<f32>(lay.z));
        if (distance(foot, at) < art_dims(k, (lay.x & K_GROVE_BIT) != 0u).x * bitcast<f32>(lay.w) * 0.9 + 0.03) {
            return out;
        }
    }

    let asp = mix(min(length(in.east) / unit_c, 1.0), 1.0, t);
    let size = MICRO_SCALE * (0.75 + 0.5 * art_unit(h, 8u)) * sqrt(asp) * grow;
    var r = select(prof.x, prof.z, top) * size;
    let hh = select(prof.y, prof.w, top) * size;
    let hs = art_hash(in.cell, MICRO_SALT + 128u + slot * 8u + side);
    if (kind == M_STONE || kind == M_BOULDER || kind == M_SCRUB || kind == M_CUSHION) {
        // Lumpy: each side its own radius.
        r *= 0.7 + 0.6 * art_unit(hs, 0u);
    } else if ((kind == M_TUFT || kind == M_FERN || kind == M_REED) && top && band == 0u) {
        // Blades: alternate sides reach out and in.
        r *= select(0.45, 1.35, (side & 1u) == 1u) * (0.85 + 0.3 * art_unit(hs, 8u));
    }
    let ang = (f32(side) + art_unit(h, 16u)) * 1.2566371;
    let ring = vec2<f32>(cos(ang), sin(ang)) * r;

    let lift = ground_lift(vec2<i32>(in.cell), foot);
    let curved = in.centre * (1.0 + lift) + in.east * foot.x + in.north * (foot.y / SQRT3_2)
        + (normalize(in.east) * ring.x + normalize(in.north) * ring.y + normalize(in.centre) * hh) * unit_c;
    let flat_p = vec3<f32>(
        in.flat_pos.x + g.hex.x * foot.x + ring.x * unit_f,
        1.0 + lift + hh * unit_f,
        -(in.flat_pos.y + g.hex.y * foot.y / SQRT3_2 + ring.y * unit_f),
    );
    let world = mix(curved, flat_p, t);

    var colour = micro_colour(kind, band, terrain, h, art_global(foot, in.cell));
    // Darker towards the foot, where less sky reaches (off in flat lighting).
    let tall = max(micro_profile(kind, 0u).w, micro_profile(kind, 1u).w);
    let rise = select(prof.y, prof.w, top) / tall;
    colour *= mix(mix(0.5, 1.0, smoothstep(0.0, 0.7, rise)), 1.0, g.lines.w);
    out.clip = g.view_proj * vec4<f32>(world, 1.0);
    out.world = world;
    out.colour = colour;
    return out;
}

@fragment
fn fs_micro(in: PropOut) -> @location(0) vec4<f32> {
    var n = normalize(cross(dpdx(in.world), dpdy(in.world)));
    if (dot(n, g.cam_pos.xyz - in.world) < 0.0) {
        n = -n;
    }
    // Softer than the big props' facets: lean the normal towards the sky so
    // tiny solids read as rounded rather than as flashing shards.
    let up = normalize(mix(normalize(in.world), vec3<f32>(0.0, 1.0, 0.0), g.cam_pos.w));
    let soft = normalize(mix(n, up, 0.35));
    return vec4<f32>(haze(in.colour * lighting(soft), in.world), 1.0);
}

// ---------------------------------------------------------------------------
// Ground cover (the Ground map mode): procedural textures of grass, moss,
// sand, rock, snow and forest floor, in board-wide coordinates (hex units)
// so they run on across hex edges. Each multiplies the field's colour (the
// cover's mean, blended between covers) by a pattern that averages about 1,
// so from far out the map keeps its calm mean colours; every octave fades
// out before it is finer than a few pixels (`px`: hex units per pixel), so
// nothing shimmers.

// How much of an octave of frequency `f` (cycles per hex) to keep.
fn gc_keep(f: f32, px: f32) -> f32 {
    return 1.0 - smoothstep(0.12, 0.35, px * f);
}

// Signed fractal noise, about -0.5..0.5, from `f0` cycles per hex up.
fn gc_fbm(p: vec2<f32>, f0: f32, octaves: u32, px: f32) -> f32 {
    var sum = 0.0;
    var amp = 0.5;
    var f = f0;
    var norm = 0.0;
    for (var i = 0u; i < octaves; i++) {
        let keep = gc_keep(f, px);
        if (keep <= 0.0) {
            break;
        }
        sum += (art_noise(p * f + vec2<f32>(f32(i) * 17.3, f32(i) * 7.1)) - 0.5) * amp * keep;
        norm += amp;
        amp *= 0.55;
        f *= 2.07;
    }
    return sum / max(norm, 0.5) * 1.6;
}

// Ridged noise 0..1 (1 on the ridges), faded like an octave.
fn gc_ridge(p: vec2<f32>, f: f32, px: f32) -> f32 {
    return (1.0 - abs(art_noise(p * f) * 2.0 - 1.0)) * gc_keep(f, px);
}

// How lush the ground is, 0 (dry, NPP under 400 g/m²/yr) to 1 (over 1300),
// from the productivity band (255 = no data: middling).
fn gc_lush(npp: f32) -> f32 {
    if (npp > 254.0) {
        return 0.5;
    }
    return clamp((npp - 2.0) / 5.0, 0.0, 1.0);
}

fn gc_grass(p: vec2<f32>, px: f32, base: vec3<f32>, npp: f32) -> vec3<f32> {
    let lush = gc_lush(npp);
    // Dry grass cures to straw; lush grass deepens. Patches of each in
    // between, so a steppe is never one flat tone.
    let tuft = gc_fbm(p, 1.3, 3u, px);
    let dry = clamp(1.0 - lush + tuft * 0.6, 0.0, 1.0);
    let straw = vec3<f32>(1.55, 1.25, 0.72);
    let deep = vec3<f32>(0.86, 0.97, 0.80);
    var c = base * mix(deep, straw, dry * 0.45);
    // Clumps and tussocks, then blades (stretched north-south as if combed
    // by the wind), then bare soil showing through in the dry.
    let clump = gc_fbm(p + 3.1, 9.0, 3u, px);
    let blade = (art_noise(p * vec2<f32>(70.0, 22.0)) - 0.5) * gc_keep(70.0, px);
    c *= 1.0 + clump * 0.55 + blade * 0.45;
    let soil = smoothstep(0.62, 0.78, art_noise(p * 16.0 + 40.0)) * dry * 0.55 * gc_keep(16.0, px);
    c = mix(c, base * vec3<f32>(1.25, 1.0, 0.72) * 0.85, soil);
    return c;
}

fn gc_moss(p: vec2<f32>, px: f32, base: vec3<f32>, npp: f32) -> vec3<f32> {
    // Cushions of moss and heath, with pale lichen between.
    let blotch = gc_fbm(p, 5.0, 4u, px);
    let lichen = smoothstep(0.08, 0.22, blotch) * gc_keep(5.0, px);
    let green = mix(vec3<f32>(0.95, 1.05, 0.8), vec3<f32>(0.82, 1.12, 0.7), gc_lush(npp));
    var c = base * mix(green, vec3<f32>(1.35, 1.32, 1.15), lichen * 0.7);
    // Heather and crowberry: dark purplish speckle.
    let heath = smoothstep(0.6, 0.75, art_noise(p * 34.0 + 9.0)) * gc_keep(34.0, px);
    c = mix(c, base * vec3<f32>(0.72, 0.58, 0.62), heath * 0.5);
    c *= 1.0 + gc_fbm(p + 8.0, 40.0, 2u, px) * 0.35;
    return c;
}

fn gc_sand(p: vec2<f32>, px: f32, base: vec3<f32>) -> vec3<f32> {
    // Dunes: broad light and shade; ripples across the wind, bent by the dunes.
    let dune = gc_fbm(p, 1.6, 3u, px);
    let warp = gc_fbm(p + 21.0, 3.0, 2u, px);
    let along = dot(p, vec2<f32>(0.83, 0.56)) * 26.0 + warp * 9.0;
    let ripple = pow(0.5 + 0.5 * sin(along * 6.2831853), 3.0) - 0.3;
    var c = base * (1.0 + dune * 0.3 + ripple * 0.3 * gc_keep(26.0, px));
    // Grain and scattered dark gravel (desert pavement).
    c *= 1.0 + (art_noise(p * 110.0) - 0.5) * 0.2 * gc_keep(110.0, px);
    let gravel = smoothstep(0.7, 0.85, art_noise(p * 18.0 + 3.0)) * gc_keep(18.0, px);
    c = mix(c, base * vec3<f32>(0.72, 0.62, 0.55), gravel * 0.35);
    return c;
}

fn gc_rock(p: vec2<f32>, px: f32, base: vec3<f32>) -> vec3<f32> {
    // Massive rock: ridged tone and bedding planes that wander with the fold.
    let fold = gc_fbm(p, 2.2, 3u, px);
    var c = base * (1.0 + fold * 0.3 + (gc_ridge(p + 4.0, 6.0, px) - 0.5) * 0.25);
    let strata = 0.5 + 0.5 * sin((p.y * 14.0 + fold * 10.0) * 6.2831853);
    c *= 1.0 + (strata - 0.5) * 0.14 * gc_keep(14.0, px);
    // Cracks: dark lines along the noise's mid contour.
    let n = art_noise(p * 12.0 + 31.0);
    let crack = (1.0 - smoothstep(0.0, 0.035, abs(n - 0.5))) * gc_keep(24.0, px);
    c *= 1.0 - crack * 0.45;
    // Scree and lichen: pale specks, warm rust patches.
    c *= 1.0 + (art_noise(p * 90.0) - 0.5) * 0.18 * gc_keep(90.0, px);
    let rust = smoothstep(0.66, 0.8, art_noise(p * 7.0 + 55.0)) * gc_keep(7.0, px);
    c = mix(c, base * vec3<f32>(1.25, 1.0, 0.75), rust * 0.35);
    return c;
}

fn gc_snow(p: vec2<f32>, px: f32, base: vec3<f32>) -> vec3<f32> {
    // Wind-packed drifts, blue in their hollows; sastrugi across the wind.
    let drift = gc_fbm(p, 2.0, 4u, px);
    var c = mix(base, base * vec3<f32>(0.82, 0.9, 1.0), clamp(-drift * 1.6, 0.0, 1.0) * 0.6);
    c *= 1.0 + drift * 0.08;
    let sast = 0.5 + 0.5 * sin((dot(p, vec2<f32>(0.6, 0.8)) * 40.0 + drift * 6.0) * 6.2831853);
    c *= 1.0 + (sast - 0.5) * 0.05 * gc_keep(40.0, px);
    return c;
}

fn gc_litter(p: vec2<f32>, px: f32, base: vec3<f32>, npp: f32) -> vec3<f32> {
    // Dark humus with drifts of leaves, needles and moss.
    let drift = gc_fbm(p, 3.0, 3u, px);
    var c = base * (1.0 + drift * 0.4);
    let leaf = smoothstep(0.58, 0.72, art_noise(p * 60.0 + drift * 4.0)) * gc_keep(60.0, px);
    c = mix(c, base * vec3<f32>(1.75, 1.2, 0.7), leaf * 0.55);
    let moss = smoothstep(0.1, 0.3, gc_fbm(p + 13.0, 6.0, 2u, px)) * gc_keep(6.0, px);
    c = mix(c, base * vec3<f32>(0.95, 1.45, 0.75), moss * mix(0.2, 0.5, gc_lush(npp)));
    c *= 1.0 + (art_noise(p * 140.0) - 0.5) * 0.2 * gc_keep(140.0, px);
    return c;
}

// The ground of cover `cover` at board point `p`; `base` is the field's
// colour there (linear), `npp` the productivity band (eased between hexes).
fn ground_cover(cover: u32, p: vec2<f32>, px: f32, base: vec3<f32>, npp: f32) -> vec3<f32> {
    switch cover {
        case C_GRASS: { return gc_grass(p, px, base, npp); }
        case C_MOSS: { return gc_moss(p, px, base, npp); }
        case C_SAND: { return gc_sand(p, px, base); }
        case C_ROCK: { return gc_rock(p, px, base); }
        case C_SNOW: { return gc_snow(p, px, base); }
        case C_LITTER: { return gc_litter(p, px, base, npp); }
        default: { return base; }
    }
}
