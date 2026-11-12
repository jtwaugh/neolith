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
    wall_colour: vec4<f32>,  // rgb (linear)
    frame_colour: vec4<f32>, // rgb (linear), a = frame lip on (0/1)
    bg_top: vec4<f32>,
    bg_bottom: vec4<f32>,
    shadow: vec4<f32>,       // table height (y), half extent x, half extent z, strength
    art: vec4<f32>,          // 2D art strength (0 = off), 3D props (0/1), pixels per (size / distance), edge blending (0/1)
    hex: vec4<f32>,          // flat-board hex half width and half height (radians), relief (board units per metre; 0 = off), unused
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
    if (mode == MODE_EVIDENCE) {
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
    let world = mix(curved, flat_p, t);

    var out: BoardOut;
    out.clip = g.view_proj * vec4<f32>(world, 1.0);
    out.world = world;
    // Hex-local coordinates: corners on the unit circle, centre at 0.
    let a = f32(in.attrs.x) * SIXTY;
    out.local = vec2<f32>(cos(a), sin(a)) * (f32(in.attrs.y) / 255.0);
    out.up = mix(in.sphere, vec3<f32>(0.0, 1.0, 0.0), t);
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

fn saturate_colour(c: vec3<f32>) -> vec3<f32> {
    let luma = dot(c, vec3<f32>(0.2126, 0.7152, 0.0722));
    return max(mix(vec3<f32>(luma), c, g.tile.w), vec3<f32>(0.0));
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
            return vec4<f32>(albedo * 0.62 * lighting(ng), 1.0);
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
            art.raised = g.art.y;
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
            let shade = f32(textureLoad(elevation_tex, cell, 0).g) / 128.0;
            albedo *= mix(1.0, shade, g.lines.y);
        }
        // Bevel: tip the normal outwards near the rim so tiles catch light.
        let recede = smoothstep(RECEDE_PX_LO, RECEDE_PX_HI, hex_px) * f32(mode == 0u) * clamp(g.art.x, 0.0, 1.0);
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
        albedo = mix(albedo, mix(grey, vec3<f32>(0.55), 0.3), 0.35 * strength * (1.0 - hatch_k));
    }

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
    return vec4<f32>(colour, 1.0);
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
    // The table the board rests on: dark walnut planks with a running grain,
    // lit warmly from above-left and falling off into shadow at the edges.
    let aspect = max(g.bg_bottom.w, 0.1);
    let p = vec2<f32>(in.uv.x * aspect, in.uv.y);
    let plank = floor(p.y * 5.0);
    let along = p.x * 1.6 + bg_hash(vec2<f32>(plank, 7.0)) * 13.0;
    let warp = bg_noise(vec2<f32>(along * 2.0, p.y * 40.0)) * 2.2 + bg_noise(vec2<f32>(along * 0.5, p.y * 6.0)) * 3.0;
    let grain = 0.5 + 0.5 * sin((p.y * 5.0 - plank) * 38.0 + warp * 3.0);
    let fine = bg_noise(vec2<f32>(along * 30.0, p.y * 400.0));
    var wood = mix(g.bg_bottom.rgb, g.bg_top.rgb, 0.35 + 0.4 * grain * grain + 0.15 * fine);
    wood *= 0.88 + 0.24 * bg_hash(vec2<f32>(plank, 3.0));
    // Seams between planks.
    let seam = abs(fract(p.y * 5.0) - 0.5) * 2.0;
    wood *= mix(0.55, 1.0, smoothstep(0.96, 0.9, seam));
    let d = length(in.uv - vec2<f32>(0.42, 0.38));
    return vec4<f32>(wood * (1.15 - 0.75 * smoothstep(0.2, 0.95, d)), 1.0);
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
};

@vertex
fn vs_piece(in: PieceIn) -> PieceOut {
    var out: PieceOut;
    out.clip = g.view_proj * vec4<f32>(in.pos, 1.0);
    out.normal = in.normal;
    out.colour = in.colour;
    return out;
}

@fragment
fn fs_piece(in: PieceOut) -> @location(0) vec4<f32> {
    // Opacity becomes MSAA coverage (alpha to coverage): smoke is see-through
    // in any draw order, and everything else is solid.
    return vec4<f32>(in.colour.rgb * lighting(normalize(in.normal)), in.colour.a);
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
};

@vertex
fn vs_line(in: LineIn) -> LineOut {
    var out: LineOut;
    out.clip = g.view_proj * vec4<f32>(in.pos, 1.0);
    out.uv = in.uv;
    out.along = in.along;
    out.colour = in.colour;
    out.params = in.params;
    out.normal = mix(normalize(in.pos), vec3<f32>(0.0, 1.0, 0.0), g.cam_pos.w);
    return out;
}

@fragment
fn fs_line(in: LineOut) -> @location(0) vec4<f32> {
    // 0 on the centreline, 1 at the edge (and round the caps).
    let d = length(in.uv);
    let aa = max(fwidth(d), 1e-4);
    let along_w = max(fwidth(in.along), 1e-5);
    let soft = max(aa, in.params.z);
    var alpha = in.colour.a * (1.0 - smoothstep(1.0 - soft, 1.0, d));
    let on = in.params.x;
    if (on > 0.0) {
        // Dashes with soft ends.
        let f = abs(fract(in.along) - 0.5 * on);
        alpha *= 1.0 - smoothstep(0.5 * on - along_w, 0.5 * on + along_w, f);
    }
    let rgb = pow(in.colour.rgb, vec3<f32>(2.2));
    return vec4<f32>(rgb * lighting(normalize(in.normal)), alpha);
}

// ------------------------------------------------------------------ blit ----
// Shows the resolved offscreen target inside the egui panel.

struct BlitParams {
    // x = 1 when the destination is not an sRGB format (egui's usual case),
    // so the linear colour must be gamma-encoded by hand.
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
    let c = textureSample(blit_tex, blit_sampler, in.uv).rgb;
    if (blit.flags.x > 0.5) {
        return vec4<f32>(linear_to_srgb(c), 1.0);
    }
    return vec4<f32>(c, 1.0);
}
