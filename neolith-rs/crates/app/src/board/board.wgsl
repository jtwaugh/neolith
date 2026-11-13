// The board: one static mesh (top tiles, stepped walls, underside), coloured
// from a per-hex state texture through a palette texture.
//
// Sticks to what WebGL2 can do: textures only (no storage buffers) and
// textureLoad for the integer lookups.

struct Globals {
    view_proj: mat4x4<f32>,
    cam_pos: vec4<f32>,      // xyz = eye, w = morph t (0 curved, 1 flat)
    grid: vec4<f32>,         // cols, rows, map mode, board thickness
    key_light: vec4<f32>,    // xyz = direction towards the light, w = intensity
    fill_light: vec4<f32>,
    tile: vec4<f32>,         // grout, bevel, quantise levels (0 = off), saturation
    lines: vec4<f32>,        // region-border strength, hillshade strength, ambient, flat lighting (0/1)
    wall_colour: vec4<f32>,  // rgb (linear), a = mountain prop height (Board style)
    frame_colour: vec4<f32>, // rgb (linear), a = frame lip on (0/1)
    bg_top: vec4<f32>,
    bg_bottom: vec4<f32>,
    shadow: vec4<f32>,       // table height (y), half extent x, half extent z, strength
    art: vec4<f32>,          // printed detail strength (0 = art off), props (0/1), pixels per (size / distance), edge blending (0/1)
    hex: vec4<f32>,          // flat-board hex half width and half height (radians), relief (board units per metre; 0 = off), unused
    depth: vec4<f32>,        // focus distance (eye to the view's centre), haze strength (0 = off), unused (the blit's blur), unused
};

@group(0) @binding(0) var<uniform> g: Globals;
// (col, row) -> r: terrain, g: koeppen, b: population, a: flags
// (bit 0 selected, bit 1 hovered, bit 2 inside the lasso being drawn).
@group(0) @binding(1) var state_tex: texture_2d<u32>;
// 256 x 4: one row of colours per map mode.
@group(0) @binding(2) var palette_tex: texture_2d<f32>;
// (col, row) -> r: elevation band (neolith_core::elevation::band),
// g: hillshade (neolith_core::elevation::hillshade; 128 = level ground),
// b: productivity band (neolith_core::productivity::band),
// a: two bands of four bits, 15 meaning no data: low, biodiversity
// (neolith_core::forager::biodiversity_band); high, expected population
// (neolith_core::farming::band).
@group(0) @binding(3) var elevation_tex: texture_2d<u32>;

// (col, row) -> r: tile surface height in metres (Snapshot::height).
@group(0) @binding(4) var height_tex: texture_2d<i32>;

// (col, row) -> r: the selected evidence layer's code at the current year
// (neolith_core::evidence: confidence * 50 + bin, 255 = no value).
@group(0) @binding(8) var evidence_tex: texture_2d<u32>;

const MODE_ELEVATION: u32 = 3u;
const MODE_NPP: u32 = 4u;
const MODE_BIODIVERSITY: u32 = 5u;
const MODE_EXPECTED: u32 = 6u;
const MODE_EVIDENCE: u32 = 7u;
// Missing sites shares the evidence texture: the app uploads its bands
// (neolith_core::residuals::band, 255 = no figure) while that mode is shown.
const MODE_MISSING: u32 = 8u;
const NO_DATA: u32 = 255u;

// Tile mesh by zoom, from the hex radius on screen in pixels: grout and the
// bevel rim fade out below GROUT_PX, region borders below BORDER_PX, so
// the far view reads as a map, not a honeycomb.
const GROUT_PX_LO: f32 = 14.0;
const GROUT_PX_HI: f32 = 28.0;
const BORDER_PX_LO: f32 = 6.0;
const BORDER_PX_HI: f32 = 14.0;
// Closer still, with terrain art on, the mesh recedes again between these
// radii so the tiles read as ground under the trees: land keeps a faint
// grid (RECEDE_LAND of it), open water almost none.
const RECEDE_PX_LO: f32 = 30.0;
const RECEDE_PX_HI: f32 = 80.0;
const RECEDE_LAND: f32 = 0.35;
const RECEDE_ALWAYS: f32 = 0.4;
const RECEDE_WATER_GROUT: f32 = 0.12;

// How far a hex's tile is raised (board units); must match board::relief.
fn hex_lift(cell: vec2<i32>) -> f32 {
    return f32(textureLoad(height_tex, cell, 0).r) * g.hex.z;
}

// The byte the current map mode colours a hex by: a state channel, or the
// elevation band (the state texture's alpha holds flags, not a layer).
// Köppen and Population show the sea in one fixed colour (palette entry
// SEA_INDEX), not as a data value; coasts then get region borders too.
const SEA_INDEX: u32 = 254u;
const TERRAIN_WATER: u32 = 0u;

fn layer_value(st: vec4<u32>, cell: vec2<i32>, mode: u32) -> u32 {
    if (mode == MODE_ELEVATION) {
        return textureLoad(elevation_tex, cell, 0).r;
    }
    if (mode != 0u && st.r == TERRAIN_WATER) {
        return SEA_INDEX;
    }
    if (mode == MODE_NPP) {
        return textureLoad(elevation_tex, cell, 0).b;
    }
    if (mode == MODE_EVIDENCE || mode == MODE_MISSING) {
        return textureLoad(evidence_tex, cell, 0).r;
    }
    if (mode == MODE_BIODIVERSITY || mode == MODE_EXPECTED) {
        let packed = textureLoad(elevation_tex, cell, 0).a;
        let band = select(packed & 15u, packed >> 4u, mode == MODE_EXPECTED);
        return select(band, NO_DATA, band == 15u);
    }
    return st[mode];
}

const KIND_TOP: u32 = 0u;
const KIND_WALL: u32 = 1u;
const KIND_UNDERSIDE: u32 = 2u;
const KIND_STEP: u32 = 3u;
const KIND_GLOBE: u32 = 4u;
const KIND_TABLE: u32 = 5u;
const SQRT3_2: f32 = 0.8660254;
const SIXTY: f32 = 1.0471976;

// ---------------------------------------------------------------- board ----

struct BoardIn {
    @location(0) sphere: vec3<f32>,
    @location(1) flat_pos: vec2<f32>,
    @location(2) cell: vec2<u32>,
    @location(3) attrs: vec4<u32>, // corner, rim, kind, depth
};

struct BoardOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world: vec3<f32>,
    @location(1) local: vec2<f32>,
    @location(2) up: vec3<f32>,
    @location(3) depth: f32,
    @location(4) @interpolate(flat) cell: vec2<u32>,
    @location(5) @interpolate(flat) kind: u32,
    // Direction from the globe's centre (the table's own position), for
    // the fog's noise: the same for the board and the globe, at any morph.
    @location(6) dir: vec3<f32>,
};

@vertex
fn vs_board(in: BoardIn) -> BoardOut {
    let t = g.cam_pos.w;
    let kind = in.attrs.z;
    var depth = f32(in.attrs.w) / 255.0;
    var sink = depth * g.grid.w;
    // Relief: tile tops (and the tops of the outside walls) rise by their
    // hex's height; a step's lower edge sits on the neighbour's top.
    let cell = vec2<i32>(in.cell);
    var lift = 0.0;
    var out_cell = in.cell;
    if (kind == KIND_STEP) {
        let nc = cell + neighbour_offset(in.cell.x & 1u, in.attrs.x);
        let own = hex_lift(cell);
        let other = hex_lift(nc);
        lift = select(other, own, in.attrs.w == 0u);
        // The cliff belongs to the higher tile (all four vertices agree).
        if (other > own) {
            out_cell = vec2<u32>(nc);
        }
        sink = 0.0;
        depth = 0.0;
    } else if (kind != KIND_UNDERSIDE && in.attrs.w == 0u) {
        lift = hex_lift(cell);
    }
    // Curved: on the unit sphere, sunk radially. Flat: on the plane y = 1.
    let curved = in.sphere * (1.0 - sink + lift);
    let flat_p = vec3<f32>(in.flat_pos.x, 1.0 - sink + lift, -in.flat_pos.y);
    var world = mix(curved, flat_p, t);
    var up = mix(in.sphere, vec3<f32>(0.0, 1.0, 0.0), t);
    if (kind == KIND_TABLE) {
        // The table stays put; as the board flattens it sinks out of sight
        // under the fog sheet the globe becomes.
        world = in.sphere - vec3<f32>(0.0, 4.0 * t, 0.0);
        up = vec3<f32>(0.0, 1.0, 0.0);
    }

    var out: BoardOut;
    out.clip = g.view_proj * vec4<f32>(world, 1.0);
    out.world = world;
    // Hex-local coordinates: corners on the unit circle, centre at 0.
    let a = f32(in.attrs.x) * SIXTY;
    out.local = vec2<f32>(cos(a), sin(a)) * (f32(in.attrs.y) / 255.0);
    if (kind == KIND_GLOBE) {
        // The globe has no hexes; it carries its (λ, φ) for the graticule.
        out.local = in.flat_pos;
    }
    out.up = up;
    out.dir = in.sphere;
    out.depth = depth;
    out.cell = out_cell;
    out.kind = in.attrs.z;
    return out;
}

fn edge_normal(i: u32) -> vec2<f32> {
    let a = (f32(i) + 0.5) * SIXTY;
    return vec2<f32>(cos(a), sin(a));
}

// Same table as neolith_core::grid::NEIGHBOUR_OFFSETS: (dcol, drow) per edge
// (NE, N, NW, SW, S, SE), for even then odd columns.
fn neighbour_offset(parity: u32, edge: u32) -> vec2<i32> {
    var offs = array<vec2<i32>, 12>(
        vec2<i32>(1, -1), vec2<i32>(0, -1), vec2<i32>(-1, -1), vec2<i32>(-1, 0), vec2<i32>(0, 1), vec2<i32>(1, 0),
        vec2<i32>(1, 0), vec2<i32>(0, -1), vec2<i32>(-1, 0), vec2<i32>(-1, 1), vec2<i32>(0, 1), vec2<i32>(1, 1),
    );
    return offs[parity * 6u + edge];
}

fn lighting(n: vec3<f32>) -> f32 {
    let key = max(dot(n, g.key_light.xyz), 0.0) * g.key_light.w;
    let fill = max(dot(n, g.fill_light.xyz), 0.0) * g.fill_light.w;
    var light = key + fill + g.lines.z;
    let q = g.tile.z;
    if (q > 0.5) {
        // Mild posterisation: printed, not photographic.
        light = mix(light, floor(light * q + 0.5) / q, 0.6);
    }
    return mix(light, 1.0, g.lines.w);
}

// Aerial perspective: ground well beyond the point the camera looks at
// fades towards a pale, cool haze, so a tilted view has a far and a near.
const HAZE: vec3<f32> = vec3<f32>(0.58, 0.67, 0.76);

fn haze(c: vec3<f32>, world: vec3<f32>) -> vec3<f32> {
    let far = distance(g.cam_pos.xyz, world) / max(g.depth.x, 1e-6);
    return mix(c, HAZE, smoothstep(1.0, 2.0, far) * 0.5 * g.depth.y);
}

fn saturate_colour(c: vec3<f32>) -> vec3<f32> {
    let luma = dot(c, vec3<f32>(0.2126, 0.7152, 0.0722));
    return max(mix(vec3<f32>(luma), c, g.tile.w), vec3<f32>(0.0));
}

// ------------------------------------------------------- fog of war ----
// Everything off the board is unknown country: the globe is wrapped in a
// sepia parchment cloud, and the board's outermost hexes go under it too,
// with a ragged edge, so the map fades into the fog rather than stopping
// at a sawtooth of hexes.

fn fog_hash3(p: vec3<f32>) -> f32 {
    let q = vec3<u32>(vec3<i32>(floor(p)) + vec3<i32>(4096));
    return f32(art_pcg(q.x * 1973u + q.y * 9277u + q.z * 26699u) & 0xffffu) / 65535.0;
}

fn fog_noise3(p: vec3<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let x00 = mix(fog_hash3(i), fog_hash3(i + vec3<f32>(1.0, 0.0, 0.0)), u.x);
    let x10 = mix(fog_hash3(i + vec3<f32>(0.0, 1.0, 0.0)), fog_hash3(i + vec3<f32>(1.0, 1.0, 0.0)), u.x);
    let x01 = mix(fog_hash3(i + vec3<f32>(0.0, 0.0, 1.0)), fog_hash3(i + vec3<f32>(1.0, 0.0, 1.0)), u.x);
    let x11 = mix(fog_hash3(i + vec3<f32>(0.0, 1.0, 1.0)), fog_hash3(i + vec3<f32>(1.0, 1.0, 1.0)), u.x);
    return mix(mix(x00, x10, u.y), mix(x01, x11, u.y), u.z);
}

fn fog_fbm(p: vec3<f32>) -> f32 {
    return fog_noise3(p) * 0.5 + fog_noise3(p * 2.03 + 17.0) * 0.25 + fog_noise3(p * 4.1 + 31.0) * 0.15
        + fog_noise3(p * 8.3 + 47.0) * 0.1;
}

// Parchment cloud (linear colour) at a direction from the globe's centre.
fn fog_colour(dir: vec3<f32>) -> vec3<f32> {
    let d = normalize(dir);
    let f = fog_fbm(d * 7.0 + fog_fbm(d * 3.0) * 1.5);
    let shadow = vec3<f32>(0.30, 0.25, 0.185);
    let paper = vec3<f32>(0.47, 0.40, 0.29);
    let cloud = vec3<f32>(0.66, 0.61, 0.51);
    var c = mix(shadow, paper, smoothstep(0.2, 0.55, f));
    c = mix(c, cloud, smoothstep(0.55, 0.85, f));
    return c;
}

// How deep under the fog a point of the board is (0 clear, 1 hidden), from
// how many hexes it lies inside the board's edge, made ragged by noise.
const FOG_EDGE_HEXES: f32 = 5.0;
fn edge_fog(cell: vec2<u32>, local: vec2<f32>, dir: vec3<f32>) -> f32 {
    // Position in hex steps: columns 1.5 corner radii apart, rows √3, the
    // odd columns half a row lower; local y is north (up the rows).
    let x = f32(cell.x) + local.x / 1.5;
    let y = f32(cell.y) + 0.5 * f32(cell.x & 1u) - local.y / 1.7320508;
    let e = min(min(x + 0.5, g.grid.x - 0.5 - x), min(y + 0.5, g.grid.y - 0.5 - y));
    let rag = (fog_fbm(normalize(dir) * 45.0) - 0.5) * FOG_EDGE_HEXES * 1.6;
    return 1.0 - smoothstep(0.6, FOG_EDGE_HEXES, e + rag);
}

// Far out, a hex is only a few pixels across: its colour blends into its
// neighbours' (and the coast rounds off) between these radii, so the map
// reads as painted country, not a mosaic.
const BLEND_PX_LO: f32 = 6.0;
const BLEND_PX_HI: f32 = 18.0;

// The table: a polished walnut ring with a pale inlaid horizon band,
// engraved in degrees, and a brass bead round the hole.
fn table_colour(world: vec3<f32>, ng: vec3<f32>, view_dir: vec3<f32>) -> vec3<f32> {
    let r = length(world.xz);
    let a = atan2(world.z, world.x);
    let dark = vec3<f32>(0.075, 0.032, 0.013);
    let light = vec3<f32>(0.24, 0.095, 0.034);
    if (abs(ng.y) < 0.5) {
        // The apron and the hole's wall: grain running down.
        let grain = bg_noise(vec2<f32>(a * 140.0, world.y * 8.0));
        let c = mix(dark, light, 0.25 + 0.35 * grain) * 0.7;
        return c * lighting(ng);
    }
    // Twelve turned segments; the grain runs round each.
    let seg = floor((a + 3.14159265) / 0.5235988);
    // Figured walnut: broad wavy bands with finer figure and pores.
    let warp = bg_noise(vec2<f32>(a * 14.0 + seg * 7.0, r * 9.0)) * 3.0 + bg_noise(vec2<f32>(a * 40.0, r * 30.0));
    let grain = 0.5 + 0.5 * sin(r * 110.0 + warp * 5.0 + seg * 1.7);
    let figure = bg_noise(vec2<f32>(a * 60.0 + seg * 3.0, r * 25.0));
    let fine = bg_noise(vec2<f32>(a * 900.0, r * 60.0));
    var c = mix(dark, light, 0.35 + 0.25 * grain * grain + 0.25 * figure + 0.1 * fine);
    c *= 0.9 + 0.2 * fog_hash3(vec3<f32>(seg, 3.0, 1.0));
    let joint = abs(fract((a + 3.14159265) / 0.5235988) - 0.5) * 2.0;
    c *= mix(0.45, 1.0, smoothstep(0.995, 0.985, joint));
    // The horizon band: boxwood, with degree ticks (every 5°, longer each 30°).
    let band_lo = 1.035;
    let band_hi = 1.13;
    let band = smoothstep(band_lo, band_lo + 0.002, r) * (1.0 - smoothstep(band_hi - 0.002, band_hi, r));
    let fine_box = bg_noise(vec2<f32>(a * 300.0, r * 30.0));
    let box = vec3<f32>(0.52, 0.36, 0.17) * (0.92 + 0.08 * fine_box);
    c = mix(c, box, band);
    let deg = (a + 3.14159265) * 57.29578;
    let tick5 = abs(fract(deg / 5.0 + 0.5) - 0.5) * 5.0;
    let tick30 = abs(fract(deg / 30.0 + 0.5) - 0.5) * 30.0;
    let w = 0.12;
    let short = (1.0 - smoothstep(w, w * 2.0, tick5)) * smoothstep(band_hi - 0.03, band_hi - 0.028, r);
    let long = (1.0 - smoothstep(w * 1.5, w * 3.0, tick30)) * smoothstep(band_lo + 0.02, band_lo + 0.022, r);
    let rule = (1.0 - smoothstep(0.0008, 0.0016, abs(r - (band_hi - 0.03))))
        + (1.0 - smoothstep(0.0008, 0.0016, abs(r - (band_lo + 0.02))));
    c = mix(c, vec3<f32>(0.06, 0.035, 0.02), clamp(max(max(short, long), rule), 0.0, 1.0) * band * 0.85);
    // A dark line where the band is let in, and a brass bead round the hole.
    let edge_line = (1.0 - smoothstep(0.0, 0.002, abs(r - band_lo))) + (1.0 - smoothstep(0.0, 0.002, abs(r - band_hi)));
    c = mix(c, c * 0.3, clamp(edge_line, 0.0, 1.0));
    let bead = 1.0 - smoothstep(0.0, 0.012, r - 1.006);
    let brass = vec3<f32>(0.62, 0.42, 0.13);
    // Polished: a soft varnish highlight, sharper on the brass.
    let h = normalize(g.key_light.xyz + view_dir);
    let nh = max(h.y, 0.0);
    var lit = mix(c, brass, bead) * lighting(vec3<f32>(0.0, 1.0, 0.0));
    lit += vec3<f32>(1.0, 0.92, 0.8) * (pow(nh, 40.0) * 0.18 + pow(nh, 300.0) * 0.5 * bead);
    // The globe shades the ring just round the hole.
    lit *= mix(0.55, 1.0, smoothstep(1.004, 1.06, r));
    return lit;
}

@fragment
fn fs_board(in: BoardOut) -> @location(0) vec4<f32> {
    // All derivatives first, in uniform control flow.
    let dwx = dpdx(in.world);
    let dwy = dpdy(in.world);
    let dlx = dpdx(in.local);
    let dly = dpdy(in.local);
    // Survey hatching coordinate (one stripe per unit) and its pixel width.
    let hatch = (in.local.x + in.local.y) * 2.5;
    let hatch_w = max(fwidth(hatch), 1e-4);

    // Nearest hex edge and normalised distance to it (0 centre .. 1 edge).
    var best = -1.0;
    var edge = 0u;
    for (var i = 0u; i < 6u; i++) {
        let d = dot(in.local, edge_normal(i));
        if (d > best) {
            best = d;
            edge = i;
        }
    }
    let rim = best / SQRT3_2;
    let aa = max(fwidth(rim), 1e-4);
    // Tile details are too fine to show once a hex is only a few pixels wide.
    let detail = 1.0 - smoothstep(0.06, 0.30, aa);

    let view_dir = normalize(g.cam_pos.xyz - in.world);

    if (in.kind == KIND_GLOBE) {
        // Fog of war, with a faint graticule every 15° (from the board's
        // centre) showing through, lit as the sphere it is.
        var c = fog_colour(in.dir);
        let step = 0.2617994;
        let f = in.local / step;
        let fw = (abs(dlx) + abs(dly)) / step;
        let gl = abs(fract(f + 0.5) - 0.5);
        let line = (vec2<f32>(1.0) - smoothstep(fw * 0.5, fw * 1.5, gl)) * (vec2<f32>(1.0) - smoothstep(vec2<f32>(0.04), vec2<f32>(0.12), fw));
        c = mix(c, c * 0.55, max(line.x, line.y) * 0.5);
        let n = normalize(in.up);
        let limb = smoothstep(0.0, 0.45, dot(n, view_dir));
        c *= lighting(n) * mix(0.55, 1.0, limb);
        return vec4<f32>(haze(c, in.world), 1.0);
    }
    if (in.kind == KIND_TABLE) {
        var ng = normalize(cross(dwx, dwy));
        if (dot(ng, view_dir) < 0.0) {
            ng = -ng;
        }
        return vec4<f32>(table_colour(in.world, ng, view_dir), 1.0);
    }

    if (in.kind != KIND_TOP) {
        // Walls and underside: fixed material, face normal from derivatives.
        var ng = normalize(cross(dwx, dwy));
        if (dot(ng, view_dir) < 0.0) {
            ng = -ng;
        }
        if (in.kind == KIND_STEP) {
            // A cliff: the higher tile's own colour, darkened like a tile edge.
            let cell = vec2<i32>(in.cell);
            let mode = u32(g.grid.z);
            let st = textureLoad(state_tex, cell, 0);
            let albedo = saturate_colour(
                textureLoad(palette_tex, vec2<i32>(i32(layer_value(st, cell, mode)), i32(mode)), 0).rgb);
            let fogged = mix(albedo, fog_colour(in.dir), edge_fog(in.cell, vec2<f32>(0.0), in.dir));
            return vec4<f32>(haze(fogged * 0.62 * lighting(ng), in.world), 1.0);
        }
        if (in.kind == KIND_WALL) {
            // The board's edge stands a hair proud of the globe, under the
            // fog: lit like the surface round it, so it leaves no seam.
            return vec4<f32>(haze(fog_colour(in.dir) * lighting(normalize(in.up)), in.world), 1.0);
        }
        var colour = g.wall_colour.rgb * lighting(ng);
        if (in.kind == KIND_WALL) {
            colour *= mix(1.0, 0.72, smoothstep(0.55, 1.0, in.depth));
        } else {
            colour *= 0.55;
        }
        return vec4<f32>(colour, 1.0);
    }

    let n_top = normalize(in.up);
    // World-space direction towards the nearest edge (cotangent frame).
    let dp2perp = cross(dwy, n_top);
    let dp1perp = cross(n_top, dwx);
    let tangent = dp2perp * dlx.x + dp1perp * dly.x;
    let bitangent = dp2perp * dlx.y + dp1perp * dly.y;
    let inv = inverseSqrt(max(max(dot(tangent, tangent), dot(bitangent, bitangent)), 1e-30));
    let en = edge_normal(edge);
    let outward = (tangent * en.x + bitangent * en.y) * inv;

    let mode = u32(g.grid.z);
    let cell = vec2<i32>(in.cell);
    let st = textureLoad(state_tex, cell, 0);
    let value = layer_value(st, cell, mode);
    var albedo = textureLoad(palette_tex, vec2<i32>(i32(value), i32(mode)), 0).rgb;
    albedo = saturate_colour(albedo);

    // The neighbour across the nearest edge.
    let nc = cell + neighbour_offset(in.cell.x & 1u, edge);
    let inside = nc.x >= 0 && nc.y >= 0 && nc.x < i32(g.grid.x) && nc.y < i32(g.grid.y);
    var nst = st;
    var nvalue = value;
    if (inside) {
        nst = textureLoad(state_tex, nc, 0);
        nvalue = layer_value(nst, nc, mode);
    }

    // Hex radius on screen in pixels, measured as vs_prop does.
    let hex_px = (g.hex.y / SQRT3_2) * g.art.z / max(distance(g.cam_pos.xyz, in.world), 1e-6);
    let grout_k = smoothstep(GROUT_PX_LO, GROUT_PX_HI, hex_px);
    let border_k = smoothstep(BORDER_PX_LO, BORDER_PX_HI, hex_px);

    // Far out: blend into the neighbours, land with land and sea with sea,
    // and draw the coast where the blended wetness crosses a half, so it
    // rounds off instead of stepping round each hex. Each neighbour weighs
    // in towards their shared edge (equal shares on the edge, thirds at a
    // corner), so the colour is continuous across hexes.
    let far = 1.0 - smoothstep(BLEND_PX_LO, BLEND_PX_HI, hex_px);
    var far_shade = f32(textureLoad(elevation_tex, cell, 0).g) / 128.0;
    if (far > 0.001) {
        let own_wet = f32(st.r == TERRAIN_WATER);
        var land = albedo * (1.0 - own_wet);
        var land_w = 1.0 - own_wet;
        var sea = albedo * own_wet;
        var sea_w = own_wet;
        var shade_sum = far_shade * (1.0 - own_wet);
        for (var i = 0u; i < 6u; i++) {
            let w = smoothstep(0.15, 1.0, dot(in.local, edge_normal(i)) / SQRT3_2);
            let c = cell + neighbour_offset(in.cell.x & 1u, i);
            if (w <= 0.0 || c.x < 0 || c.y < 0 || c.x >= i32(g.grid.x) || c.y >= i32(g.grid.y)) {
                continue;
            }
            let s = textureLoad(state_tex, c, 0);
            let col = saturate_colour(textureLoad(palette_tex, vec2<i32>(i32(layer_value(s, c, mode)), i32(mode)), 0).rgb);
            let wet = f32(s.r == TERRAIN_WATER);
            land += col * w * (1.0 - wet);
            land_w += w * (1.0 - wet);
            sea += col * w * wet;
            sea_w += w * wet;
            shade_sum += f32(textureLoad(elevation_tex, c, 0).g) / 128.0 * w * (1.0 - wet);
        }
        let wet = sea_w / max(land_w + sea_w, 1e-4);
        let blended = mix(land / max(land_w, 1e-4), sea / max(sea_w, 1e-4), smoothstep(0.42, 0.58, wet));
        albedo = mix(albedo, blended, far);
        far_shade = mix(far_shade, shade_sum / max(land_w, 1e-4), far);
    }

    var normal = n_top;
    let lip = g.frame_colour.a > 0.5 && !inside && rim > 0.45;
    if (lip) {
        // Raised frame lip along the outside edge: its own material, with
        // sloped shoulders on both sides.
        albedo = g.frame_colour.rgb;
        let inner = 1.0 - smoothstep(0.45, 0.58, rim);
        let outer = smoothstep(0.88, 1.0, rim);
        normal = normalize(n_top + outward * (outer - inner) * 0.9);
    } else {
        // Terrain art, printed on the tile under the grout and borders. Too
        // fine to show once a hex is under about 20 pixels across.
        // (Two pixel-size estimates: either alone is unreliable where a
        // pixel quad straddles sub-pixel hexes.)
        let local_px = max(length(vec2<f32>(dlx.x, dly.x)), length(vec2<f32>(dlx.y, dly.y)));
        let art_fade = 1.0 - smoothstep(0.06, 0.14, max(aa, local_px));
        let art_on = g.art.x * art_fade;
        // Where biomes blend into each other the hard region border goes.
        var soften = 0.0;
        if (art_on > 0.004) {
            var art: Art;
            art.albedo = albedo;
            // East-west squash of the hex on the board (1 when flat).
            art.asp = clamp(sqrt(dot(bitangent, bitangent) / max(dot(tangent, tangent), 1e-30)), 0.2, 1.5);
            art.size = sqrt(min(art.asp, 1.0));
            art.px = max(length(vec2<f32>(dlx.x, dly.x)) * art.asp, length(vec2<f32>(dlx.y, dly.y)));
            art.mono = f32(mode != 0u);
            art.k = art_on * mix(1.0, 0.75, art.mono);
            art.clip = 1.0 - smoothstep(0.84, 0.90, rim);
            art.blend = g.art.w;
            art.detail = smoothstep(ART_DETAIL_LO, ART_DETAIL_HI, hex_px);
            // Prop shadows fall away from the key light, longer the lower it is.
            let key = g.key_light.xyz;
            art.sun = -vec2<f32>(dot(key, normalize(tangent)), dot(key, normalize(bitangent)))
                / max(dot(key, n_top), 0.35);
            art.lod = smoothstep(5.0, 11.0, hex_px);
            albedo = terrain_art(in.local, in.cell, st.r, art);
            if (g.art.w > 0.5 && mode == 0u && art_blends(st.r, nst.r)) {
                soften = art_on;
            }
        }
        // Hillshade on land: the elevation gradient, as a multiplier (it is
        // static, so the shore follows the year's Water, not today's coast).
        if (g.lines.y > 0.0 && st.r != T_WATER && st.r < T_COUNT) {
            albedo *= mix(1.0, far_shade, g.lines.y);
        }
        // Bevel: tip the normal outwards near the rim so tiles catch light.
        // (With the art on, the mesh is never at full strength on the terrain
        // map: the ground should read as country first, tiles second.)
        let recede = max(smoothstep(RECEDE_PX_LO, RECEDE_PX_HI, hex_px), RECEDE_ALWAYS)
            * f32(mode == 0u) * clamp(g.art.x, 0.0, 1.0);
        let is_water = st.r == T_WATER;
        let bevel = smoothstep(0.70, 0.94, rim) * g.tile.y * detail * grout_k
            * mix(1.0, select(RECEDE_LAND, 0.0, is_water), recede);
        normal = normalize(n_top + outward * bevel * 0.8);
        // Grout line between tiles.
        let grout = smoothstep(0.94 - aa, 0.94 + aa, rim) * g.tile.x * detail * grout_k
            * mix(1.0, select(RECEDE_LAND, RECEDE_WATER_GROUT, is_water), recede);
        albedo = mix(albedo, albedo * 0.42, grout);
        // Region border: the neighbour's value differs (in elevation mode,
        // these are the contour lines between bands).
        if (inside && nvalue != value) {
            let band = smoothstep(0.80 - aa, 0.80 + aa, rim) * g.lines.x * (1.0 - soften) * border_k;
            albedo = mix(albedo, albedo * 0.25, band);
        }
    }

    // Survey intensity (bits 5-6; scene::FLAG_SURVEY_*): land with few dated
    // records of any period, where an absence of sites says little. Close
    // up, diagonal hatching (denser for the least surveyed); far out, where
    // lines would alias, a grey wash instead.
    let survey_none = (st.a & 64u) != 0u;
    let survey_thin = (st.a & 32u) != 0u;
    if (g.hex.w > 0.5 && !lip && (survey_none || survey_thin) && st.r != T_WATER && st.r < T_COUNT) {
        // Hardly surveyed: every stripe, strong; thinly: every other, fainter.
        let strength = select(0.55, 1.0, survey_none);
        let period = select(2.0, 1.0, survey_none);
        let d = abs(fract(hatch / period) - 0.5) * period;
        let line = 1.0 - smoothstep(0.16 - hatch_w, 0.16 + hatch_w, d);
        let hatch_k = smoothstep(10.0, 24.0, hex_px);
        let ink = vec3<f32>(0.18, 0.16, 0.14);
        albedo = mix(albedo, ink, line * 0.7 * strength * hatch_k * detail);
        let grey = vec3<f32>(dot(albedo, vec3<f32>(0.299, 0.587, 0.114)));
        albedo = mix(albedo, mix(grey, vec3<f32>(0.55), 0.3), 0.35 * strength * (1.0 - hatch_k) * (1.0 - 0.6 * far));
    }

    // The board's rim goes under the fog of war.
    albedo = mix(albedo, fog_colour(in.dir), edge_fog(in.cell, in.local, in.dir));

    // Selection / lasso tints.
    let selected = (st.a & 1u) != 0u;
    let in_lasso = (st.a & 4u) != 0u;
    if (selected) {
        albedo = mix(albedo, vec3<f32>(1.0, 0.78, 0.15), 0.30);
    }
    if (in_lasso) {
        albedo = mix(albedo, vec3<f32>(0.25, 0.65, 1.0), 0.35);
    }

    var colour = albedo * lighting(normal);

    // Outlines (unlit): selection boundary, then hover.
    if (selected && (!inside || (nst.a & 1u) == 0u)) {
        let band = smoothstep(0.78 - aa, 0.78 + aa, rim);
        colour = mix(colour, vec3<f32>(1.0, 0.62, 0.0), band);
    }
    if ((st.a & 2u) != 0u) {
        let band = smoothstep(0.80 - aa, 0.80 + aa, rim);
        colour = mix(colour, vec3<f32>(1.0, 1.0, 1.0), band * 0.9);
    }
    return vec4<f32>(haze(colour, in.world), 1.0);
}

// ----------------------------------------------------------- background ----

struct ScreenOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_fullscreen(@builtin(vertex_index) i: u32) -> ScreenOut {
    // One triangle covering the screen.
    let p = vec2<f32>(f32((i << 1u) & 2u), f32(i & 2u));
    var out: ScreenOut;
    out.clip = vec4<f32>(p * 2.0 - 1.0, 1.0, 1.0);
    out.uv = vec2<f32>(p.x, 1.0 - p.y);
    return out;
}

// Smooth value noise for the tabletop grain.
fn bg_hash(p: vec2<f32>) -> f32 {
    let q = vec2<u32>(vec2<i32>(floor(p)) + vec2<i32>(4096));
    return f32(art_pcg(q.x * 1973u + q.y * 9277u) & 0xffffu) / 65535.0;
}

fn bg_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let a = bg_hash(i);
    let b = bg_hash(i + vec2<f32>(1.0, 0.0));
    let c = bg_hash(i + vec2<f32>(0.0, 1.0));
    let d = bg_hash(i + vec2<f32>(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

@fragment
fn fs_background(in: ScreenOut) -> @location(0) vec4<f32> {
    // A dim study round the globe table: warm near the light, falling off
    // to near black at the edges, dithered so the gradient doesn't band.
    let aspect = max(g.bg_bottom.w, 0.1);
    let p = (in.uv - vec2<f32>(0.42, 0.36)) * vec2<f32>(aspect, 1.0);
    let d = length(p);
    let warm = vec3<f32>(0.050, 0.040, 0.032);
    let dark = vec3<f32>(0.006, 0.005, 0.005);
    var c = mix(warm, dark, smoothstep(0.05, 1.1, d));
    c += (bg_hash(in.clip.xy) - 0.5) * 0.0025;
    return vec4<f32>(c, 1.0);
}

// -------------------------------------------------------- contact shadow ----

struct ShadowOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) p: vec2<f32>,
};

@vertex
fn vs_shadow(@builtin(vertex_index) i: u32) -> ShadowOut {
    var corners = array<vec2<f32>, 6>(
        vec2<f32>(-1.0, -1.0), vec2<f32>(1.0, -1.0), vec2<f32>(1.0, 1.0),
        vec2<f32>(-1.0, -1.0), vec2<f32>(1.0, 1.0), vec2<f32>(-1.0, 1.0),
    );
    let c = corners[i] * 1.8;
    var out: ShadowOut;
    out.p = c;
    out.clip = g.view_proj * vec4<f32>(c.x * g.shadow.y, g.shadow.x, c.y * g.shadow.z, 1.0);
    return out;
}

@fragment
fn fs_shadow(in: ShadowOut) -> @location(0) vec4<f32> {
    // Blurred rounded-rectangle falloff; no shadow maps.
    let q = abs(in.p);
    let r = pow(pow(q.x, 4.0) + pow(q.y, 4.0), 0.25);
    let a = (1.0 - smoothstep(0.55, 1.7, r)) * g.shadow.w;
    return vec4<f32>(0.0, 0.0, 0.0, a);
}

// ------------------------------------------------------ settlement pieces ----

struct PieceIn {
    @location(0) pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) colour: vec4<f32>,
};

struct PieceOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) colour: vec4<f32>,
    @location(2) world: vec3<f32>,
};

@vertex
fn vs_piece(in: PieceIn) -> PieceOut {
    var out: PieceOut;
    out.clip = g.view_proj * vec4<f32>(in.pos, 1.0);
    out.normal = in.normal;
    out.colour = in.colour;
    out.world = in.pos;
    return out;
}

@fragment
fn fs_piece(in: PieceOut) -> @location(0) vec4<f32> {
    // Opacity becomes MSAA coverage (alpha to coverage): smoke is see-through
    // in any draw order, and everything else is solid.
    return vec4<f32>(haze(in.colour.rgb * lighting(normalize(in.normal)), in.world), in.colour.a);
}

// ---------------------------------------------------------- line overlays ----
// Rivers, channel belts and lake shores: ribbons built on the CPU
// (board::lines), shaped here from the across-the-ribbon coordinate.

struct LineIn {
    @location(0) pos: vec3<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) along: f32,
    @location(3) colour: vec4<f32>,
    @location(4) params: vec4<f32>,
};

struct LineOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) along: f32,
    @location(2) colour: vec4<f32>,
    @location(3) params: vec4<f32>,
    @location(4) normal: vec3<f32>,
    @location(5) world: vec3<f32>,
};

const LINE_BED: u32 = 1u;
const LINE_WATER: u32 = 2u;

@vertex
fn vs_line(in: LineIn) -> LineOut {
    var out: LineOut;
    out.clip = g.view_proj * vec4<f32>(in.pos, 1.0);
    out.uv = in.uv;
    out.along = in.along;
    out.colour = in.colour;
    out.params = in.params;
    out.normal = mix(normalize(in.pos), vec3<f32>(0.0, 1.0, 0.0), g.cam_pos.w);
    out.world = in.pos;
    return out;
}

@fragment
fn fs_line(in: LineOut) -> @location(0) vec4<f32> {
    // 0 on the centreline, 1 at the edge (and round the caps).
    let d = length(in.uv);
    let aa = max(fwidth(d), 1e-4);
    let along_w = max(fwidth(in.along), 1e-5);
    let soft = max(aa, in.params.z);
    // World direction across the ribbon, towards its uv.x = 1 edge.
    let across = dpdx(in.world) * dpdx(in.uv.x) + dpdy(in.world) * dpdy(in.uv.x);
    // The profile across the ribbon (lines::Profile).
    let profile = u32(in.params.y * 3.0 + 0.5);
    var rgb = pow(in.colour.rgb, vec3<f32>(2.2));
    var normal = normalize(in.normal);
    var edge = d;
    if (profile == LINE_BED) {
        // A river bed. The water's edge is at 1 / RIVER_BED of its width.
        let shore = 1.0 / RIVER_BED;
        // The banks slope down to the water, so one catches the light and
        // the other is in shade: the channel reads as cut into the ground.
        let slope = smoothstep(shore - 0.05, shore + 0.12, d) * (1.0 - smoothstep(0.78, 1.0, d));
        let side = across * inverseSqrt(max(dot(across, across), 1e-30)) * sign(in.uv.x);
        normal = normalize(normal - side * slope * 1.1);
        // Wet mud by the water, drying to sand.
        rgb *= mix(0.55, 1.0, smoothstep(shore, shore + 0.3, d));
        // A ragged outer edge (finer than a pixel from far out: none).
        let rag = (art_noise(vec2<f32>(in.along * 11.0, in.uv.x * 1.5)) - 0.5) * 0.35;
        edge = d + rag * (1.0 - smoothstep(0.02, 0.2, along_w * 11.0));
    } else if (profile == LINE_WATER) {
        // Paler shallows towards the banks, and streaks drawn out along the flow.
        rgb = mix(rgb, rgb * vec3<f32>(1.12, 1.22, 1.12) + 0.02, smoothstep(0.45, 1.0, d) * 0.6);
        let streak = art_noise(vec2<f32>(in.along * 6.0, in.uv.x * 3.0 + 5.0));
        let fine = 1.0 - smoothstep(0.05, 0.3, along_w * 6.0);
        rgb = mix(rgb, rgb * 1.3 + 0.04, smoothstep(0.58, 0.8, streak) * 0.45 * fine);
        rgb = mix(rgb, rgb * 0.82, smoothstep(0.58, 0.8, 1.0 - streak) * 0.45 * fine);
    }
    var alpha = in.colour.a * (1.0 - smoothstep(1.0 - soft, 1.0, edge));
    let on = in.params.x;
    if (on > 0.0) {
        // Dashes with soft ends.
        let f = abs(fract(in.along) - 0.5 * on);
        alpha *= 1.0 - smoothstep(0.5 * on - along_w, 0.5 * on + along_w, f);
    }
    return vec4<f32>(haze(rgb * lighting(normal), in.world), alpha);
}

// ------------------------------------------------------------------ blit ----
// Shows the resolved offscreen target inside the egui panel.

struct BlitParams {
    // x = 1 when the destination is not an sRGB format (egui's usual case),
    // so the linear colour must be gamma-encoded by hand. y: the tilt-shift's
    // widest blur radius, as a fraction of the view's height (0 = off);
    // z: the view's aspect (width / height).
    flags: vec4<f32>,
};

@group(0) @binding(0) var blit_tex: texture_2d<f32>;
@group(0) @binding(1) var blit_sampler: sampler;
@group(0) @binding(2) var<uniform> blit: BlitParams;

fn linear_to_srgb(c: vec3<f32>) -> vec3<f32> {
    let lo = c * 12.92;
    let hi = 1.055 * pow(max(c, vec3<f32>(0.0)), vec3<f32>(1.0 / 2.4)) - 0.055;
    return select(hi, lo, c <= vec3<f32>(0.0031308));
}

@fragment
fn fs_blit(in: ScreenOut) -> @location(0) vec4<f32> {
    // Tilt-shift: sharp across the middle of the view, where the camera
    // looks, and out of focus towards the top (far) and, less, the bottom
    // (near). A disc of taps, wider the further from the band in focus.
    let off = in.uv.y - 0.5;
    let radius = blit.flags.y * smoothstep(0.17, 0.5, abs(off)) * select(1.0, 0.6, off > 0.0);
    var c = textureSampleLevel(blit_tex, blit_sampler, in.uv, 0.0).rgb;
    if (radius > 0.0003) {
        var taps = array<vec2<f32>, 12>(
            vec2<f32>(1.0, 0.0), vec2<f32>(0.5, 0.866), vec2<f32>(-0.5, 0.866),
            vec2<f32>(-1.0, 0.0), vec2<f32>(-0.5, -0.866), vec2<f32>(0.5, -0.866),
            vec2<f32>(0.433, 0.25), vec2<f32>(0.0, 0.5), vec2<f32>(-0.433, 0.25),
            vec2<f32>(-0.433, -0.25), vec2<f32>(0.0, -0.5), vec2<f32>(0.433, -0.25),
        );
        let scale = vec2<f32>(radius / max(blit.flags.z, 0.1), radius);
        for (var i = 0; i < 12; i++) {
            c += textureSampleLevel(blit_tex, blit_sampler, in.uv + taps[i] * scale, 0.0).rgb;
        }
        c /= 13.0;
    }
    if (blit.flags.x > 0.5) {
        return vec4<f32>(linear_to_srgb(c), 1.0);
    }
    return vec4<f32>(c, 1.0);
}
