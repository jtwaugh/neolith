# Agent harness

Lets an agent play the native app: it reads the game state straight out of the app's
memory, takes screenshots and sends mouse and keyboard input. It's the same idea as
a RAM-reading harness for an emulator. The app opens a localhost-only TCP server
when it starts with `--harness`:

```sh
harness/neolith.py launch          # builds, starts `neolith --harness 7878 --size 1600x1000`, waits for the world
harness/neolith.py start           # Start screen -> map
harness/neolith.py state --brief   # JSON: year, clock, map mode, camera, hover/inspected hex, labels, settlements …
harness/neolith.py ui              # every widget on screen: role, label, toggled/selected, rect and centre in pixels
harness/neolith.py press "Köppen"  # click a widget by its label
harness/neolith.py shot            # PNG of the whole window -> build/critic/shots/
harness/neolith.py refs            # Steam store screenshots of Victoria 3, CK3, EU4, HOI4, Old World, Civ VI -> build/critic/refs/
harness/neolith.py quit
```

`harness/neolith.py --help` lists every command. The critic agent that uses all
this is `.claude/agents/gsg-critic.md`, and it scores against [`CRITIC.md`](CRITIC.md).

Every action (`set`, `camera`, `click`, `drag`, `scroll`, `key`, …) replies with
`after`: the camera, year, mode, hover, inspected hex and open popup once the app has
settled. So `camera` echoes where the camera actually ended up after clamping.

**Run one app per port.** Set `NEOLITH_HARNESS_PORT` (or pass `--port`) when more than
one agent or session drives Neolith at once. Otherwise one session's `launch`/`quit`
acts on another's app.

**Real input is ignored by default.** In harness mode the app drops real mouse and
keyboard events, so a human cursor drifting over the window can't orbit the camera
mid-run. `set --user-input true` lets them through.

The harness works while the window is behind other windows. Each request sends egui's
`RequestPaintWhileHidden`, and the harness turns vsync off so a covered window can't
stall on present.

## Coordinates

Every x/y is in **screenshot pixels**, so you can read a position off the PNG and
click it. Add `"space": "pt"` to a raw request to use egui points instead
(`pixels = points × pixels_per_point`, which `state` reports). `state` gives screen
positions in pixels too: `board_rect_px`, `settlements.pieces[].screen_px` and
`labels_drawn[].rect_px`.

## Protocol

One JSON object per line in, one per line out, on `127.0.0.1:<port>`. Every reply
has `"ok"`. Input commands reply once the events have gone through egui and the app
has had a few frames to respond, so a `state` sent next sees the result.

| cmd | fields | does |
|---|---|---|
| `ping` | | |
| `state` | `brief?` (keyframe count, 10 pieces, label names), `fields?` (top-level keys to keep) | the whole readout (see below) |
| `ui` | `filter?` (label substring) | widgets from the last painted frame (egui's AccessKit tree): role, label, toggled, selected, value, `rect_px`, `centre_px` |
| `screenshot` | `path` | saves a PNG of the window, replies with its size |
| `start` | `year?` | leaves the start screen |
| `set` | `year`, `playing`, `speed`, `mode` (terrain/koeppen/pop/elevation/npp/biodiversity/expected/evidence), `evidence` (layer id, e.g. `domestic_livestock`), `editor`, `tool`, `flat`, `relief`, `art` (off/on), `rivers`, `survey` (hatching of thinly surveyed land), `style_window`, `inspect` (hex id or null), `settlement` (name or null), `user_input` | the top-bar and timeline controls, set directly |
| `camera` | `lon`, `lat`, `yaw`, `pitch` (degrees), `dist` | moves the camera, clamped like user input |
| `hex` | `id`, or `lon` + `lat` (CLI: `hex LON LAT`, `hex --lon --lat` or `hex --id`) | one hex's values at the current year |
| `pick` | `x`, `y` | the hex under a screen pixel |
| `project` | `lon`, `lat` (CLI: `project LON LAT` or `--lon --lat`) | screen pixel of a point, or null if it's off screen |
| `move`, `click`, `double_click` | `x`, `y`, `button` (left/right/middle), `modifiers` (shift/ctrl/alt/cmd) | synthetic pointer input |
| `drag` | `x`, `y`, `to_x`, `to_y`, `button`, `modifiers`, `steps` | left: pan (or paint with editor tools); right: orbit |
| `scroll` | `x`, `y`, `dy` (positive zooms in), `dx` | wheel |
| `key` | `key`: egui names (`Space`, `Z`, `1`, `ArrowUp`, `Escape`, `F1` …), case-insensitive, plus aliases `Num1`/`Digit1`, `KeyA`, `esc`, `return`, `up`/`down`/`left`/`right`; `modifiers` | key press and release. Unknown names list the valid ones. A known key that does nothing means the app has no binding for it |
| `text` | `text` | typed text (for focused text fields) |
| `wait` | `seconds` or `frames` | lets the app run (for example while the clock plays) |
| `quit` | | closes the app |

`state` covers: `screen`, `window_px`, `pixels_per_point`, `year`/`year_label`, `clock`,
`keyframes`, `map_mode`, `evidence_layer` (and `evidence_layers`, every id), `editor`/`tool`, `history`, `selection_count`, `camera`,
`flat`, `style`, `board_rect_px`, `hover`/`inspected` (terrain, Köppen, population,
elevation, rivers, lakes), `settlement_popup`, `settlements` (founded so far, on
screen, the 60 biggest on screen with click positions, and the labels actually
drawn), and `view_summary` (on-screen hex counts by the current mode's values,
skipping hexes hidden behind the curve), and `map_labels` (sea, region, mountain,
river and lake names drawn, with kind, font size and rectangle).

`style.terrain_art` uses the button labels (`Off`, `On`). With the Board-style
option "Fill the screen" on (the default), the camera keeps the board covering the
view, except for an "Edge room" margin (`fill_margin`, default 25% per side) where the
map's edge may show. Zooming out tilts towards top-down, and `dist` stops at about 1.6
(about 0.7 with `set --fill-margin 0`). `set --fill false` gives the free tabletop
camera (`dist` up to 3.6). `set` also takes the Board-style layers (`hillshade`,
`borders`, `grout`, `bevel`, `art_strength`, `art_blend`, `saturation`,
`flat_lighting`, `relief_exaggeration`, `depth`), so a critic can turn layers off one at a time.

Code: `crates/app/src/harness.rs` (server and commands), plus `Drawn` in
`crates/app/src/view.rs`, which records what the board drew each frame.
