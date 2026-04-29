# BlenderVRCFT — Technical Design Document (Draft v0.2)

**Status:** Draft, pre-implementation.
**Last updated:** 2026-04-28
**Target:** Blender 5.0 (Python 3.11), VRCFaceTracking via OSCQuery.

A Blender add-on that lets a rigger preview VRChat Face Tracking (VRCFT)
Unified Expressions on an avatar inside Blender, driven by live OSC messages
from a running VRCFT instance, without round-tripping through Unity / VRChat.

Discovery is via **OSCQuery** (mDNS + HTTP), so VRCFT auto-finds Blender
and starts streaming with no manual config and no files written to
`LocalLow`.

---

## 1. Goals

1. From inside Blender, animate an avatar's shape keys in real time using OSC
   data emitted by VRCFT.
2. Advertise an OSCQuery service so the latest VRCFT discovers Blender as a
   tracking target automatically.
3. Show every detected blendshape as a 0–1 progress bar live, labeled with the
   shape-key name it drives.
4. Be installable as a single `.zip` extension with no manual `pip` step.
5. Provide a one-click capture mode that logs incoming OSC traffic to a file
   for debugging.

## 2. Non-goals (for v1)

- Bone-driven tracking (eye-gaze rotation, head pose).
- Animation recording / keyframe baking. Live preview only.
- Multi-mesh fan-out (e.g. separate body + face meshes). Single assigned mesh
  in v1.
- Any export / FBX / VRChat SDK integration.
- Cross-network OSC. Localhost only (advertised on `127.0.0.1`-bound
  interfaces only by default).
- Legacy `LocalLow\VRChat\...\Avatars\<id>.json` discovery. May be added
  later as a fallback if OSCQuery proves unreliable.

## 3. Glossary

| Term | Meaning |
|------|---------|
| **VRCFT** | VRCFaceTracking, the desktop app that fuses face-tracker data and emits OSC. |
| **Unified Expressions (UE)** | VRCFT's standard parameter set, e.g. `JawOpen`, `MouthClosed`. v2 module prefixes addresses with `v2/`. |
| **Shape key** | Blender's name for a blendshape on a mesh's `data.shape_keys.key_blocks`. |
| **OSCQuery** | mDNS- and HTTP-based service discovery used by VRCFT. We advertise `_osc._udp` (the OSC receive port) and `_oscjson._tcp` (an HTTP port that returns the parameter tree as JSON). |

## 4. High-level architecture

```
                            mDNS announce
                       _osc._udp       _oscjson._tcp
                            |              |
+---------------------------v--------------v---------------+
|                       Blender add-on                      |
|                                                           |
|  [mDNS responder]                                         |
|  [HTTP server] ----------------+   GET /  -> param tree   |
|                                |                          |
|  [OSC UDP receiver] <----------+--- VRCFT ---> face data  |
|        |                                                  |
|        v                                                  |
|  thread-safe queue                                        |
|        |                                                  |
|        v                                                  |
|  [bpy.app.timers drain] -> shape_keys.key_blocks[name]    |
+----------------------------------------------------------+
```

Threads inside the add-on:

- **Main (Blender) thread** — owns `bpy`. Reads from queue, writes shape-key
  values, drives UI redraw.
- **OSC receive thread** — `python-osc` UDP server.
- **HTTP thread** — stdlib `http.server.ThreadingHTTPServer` for OSCQuery
  responses. Trivial: returns a precomputed JSON blob.
- **Zeroconf thread** — managed internally by the `zeroconf` library.

Bridging is done with `queue.Queue` (push from OSC thread) and
`bpy.app.timers.register(...)` (drain on main thread, ~60 Hz).
Reason: `bpy` is **not** thread-safe; touching it off the main thread crashes
Blender intermittently.

## 5. Component breakdown

### 5.1 Add-on skeleton
- Single Python package, registered as a Blender 5.0 extension via
  `blender_manifest.toml`. No legacy `bl_info` dual-path.
- Side-panel category: **VRCFT** in the 3D Viewport's N-panel.
- Persistent settings on `bpy.types.Scene` via a `PropertyGroup` (so they
  save with the .blend file).

### 5.2 Properties (shown in the panel)
| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `head_mesh` | Object pointer (MESH) | None | Required. Must have shape keys. |
| `osc_port` | int | 9000 | UDP port we listen on for face tracking values. Advertised via `_osc._udp`. |
| `oscquery_http_port` | int | 0 | HTTP port for OSCQuery JSON responses. `0` = pick a free ephemeral port at start. Advertised via `_oscjson._tcp`. |
| `service_name` | str | `Blender VRCFT` | mDNS service instance name. |
| `smoothing` | float [0,1] | 0.1 | Lerp alpha per drained tick. 0 = none, 1 = snap. |
| `address_prefix` | str | `/avatar/parameters/` | For overriding if a sender uses a non-default route. |
| `is_running` | bool | False | Read-only state. |
| `capture_path` | str | `//vrcft_capture.log` | Where the capture logger writes. `//` = next to the .blend file. |
| `is_capturing` | bool | False | Read-only state. |

Outgoing port is gone from the spec — under OSCQuery, the OSC receive port
*is* the advertised port, and we don't need a separate outbound channel for
`/avatar/change`.

### 5.3 Operators
- `vrcft.start_test` — spins up OSC server + HTTP server + Zeroconf
  announcement, builds the OSCQuery JSON tree from current shape keys,
  registers timer.
- `vrcft.stop_test` — tears all of that down.
- `vrcft.refresh_param_tree` — re-scans the assigned mesh's shape keys and
  re-publishes the OSCQuery tree without restarting OSC. Useful after
  adding/renaming a shape key.
- `vrcft.start_capture` / `vrcft.stop_capture` — toggle capture logger.
- `vrcft.open_capture_folder` — convenience: open the folder containing
  the capture log.

All `start_*` operators auto-stop their counterpart on `unregister()`,
on `load_post`, and on add-on disable.

### 5.4 OSC receiver (background thread)
- Library: **`python-osc`**, vendored under `vendor/` inside the add-on.
- Filter inbound to messages starting with `address_prefix`.
- Push `(param_name, float_value, monotonic_timestamp)` to a
  `queue.Queue(maxsize=4096)`. Drop oldest on overflow; log once.
- Failure modes handled: port already in use (display friendly error in
  panel), malformed packet (log & ignore).

### 5.5 Drain timer (main thread)
- `bpy.app.timers.register(drain, persistent=True)` at ~16 ms.
- Drains queue into `dict[name] -> latest_target_value` (coalesces multiple
  updates per frame).
- Per-parameter state holds `current` value. Each tick:
  `current += (target - current) * smoothing_lerp_alpha`.
- Writes to `mesh.data.shape_keys.key_blocks[name].value` only if the value
  changed by > epsilon (1e-3), to keep depsgraph churn down.
- Tags `mesh.data.shape_keys` for update.

### 5.6 Name matching rule
1. Take the incoming OSC address, e.g. `/avatar/parameters/v2/JawOpen`.
2. Strip the `address_prefix` -> `v2/JawOpen`.
3. Strip a leading `v2/` if present -> `JawOpen`.
4. Look up `JawOpen` exactly in `shape_keys.key_blocks`. No case folding,
   no fuzzy matching.

If no shape key matches, the parameter still appears in the live UI list
under "Unmatched" so the user can rename their shape keys to fit.

### 5.7 OSCQuery discovery service
The mechanism modern VRCFT uses to find us:

**mDNS announcement** (via `zeroconf`):
- `_osc._udp.local.` with port = `osc_port` (advertises the UDP receiver).
- `_oscjson._tcp.local.` with port = `oscquery_http_port` (advertises the
  HTTP query endpoint).
- Service instance name: `service_name` (default `Blender VRCFT`).
- TXT records: `txtvers=1`. Add `OSCQueryHostName` if VRCFT requires it
  (verify in Phase 4 spike).

**HTTP server** (stdlib `http.server.ThreadingHTTPServer`):
- `GET /` returns the OSCQuery parameter tree as JSON, content-type
  `application/json`.
- Tree is built once at start and rebuilt on `refresh_param_tree`.
- Tree shape (OSCQuery 1.0):
  ```json
  {
    "DESCRIPTION": "Blender VRCFT",
    "FULL_PATH": "/",
    "ACCESS": 0,
    "CONTENTS": {
      "avatar": {
        "FULL_PATH": "/avatar",
        "ACCESS": 0,
        "CONTENTS": {
          "parameters": {
            "FULL_PATH": "/avatar/parameters",
            "ACCESS": 0,
            "CONTENTS": {
              "JawOpen": {
                "FULL_PATH": "/avatar/parameters/JawOpen",
                "ACCESS": 3,
                "TYPE": "f",
                "VALUE": [0.0]
              },
              ...
            }
          }
        }
      }
    }
  }
  ```
- One `CONTENTS` entry per shape key on the assigned mesh (excluding
  `Basis`). Type `f` (float), `ACCESS=3` (read/write).

Sources of parameter list:
1. Every shape key on the assigned mesh (excluding `Basis`).
2. Optionally union with the canonical UE list (bundled as
   `data/unified_expressions.json`). User toggle, default off — keeps the
   tree minimal so VRCFT only sends what we can actually animate.

### 5.8 Live parameter list UI
- Panel section: scrollable `UIList` of detected parameters.
- Each row: name (left) + value bar (right), using
  `layout.progress(factor=v, text=name)` (Blender 4.0+, available in 5.0).
- Sort: most-recently-updated first, with a **Freeze sort** toggle so the
  list doesn't reshuffle while reading.
- **Show unmatched** toggle: include params we received that have no
  matching shape key, drawn in muted color.

### 5.9 OSC capture logger
- Operator `vrcft.start_capture` opens the configured `capture_path` for
  append, writes a header line with timestamp + Blender version + addon
  version, then writes one line per inbound OSC message:
  ```
  {iso8601_ts}\t{address}\t{type_tag}\t{value}
  ```
- Capture is independent of Test mode — you can capture without driving
  shape keys (useful for sniffing what VRCFT actually sends so we can
  refine the matching rule).
- Internally hooks the OSC dispatcher's catch-all path, so it captures
  messages outside `address_prefix` too.
- `vrcft.stop_capture` flushes and closes the file.
- Bounded: stop after `max_capture_bytes` (default 50 MB) to avoid
  filling disks.

## 6. Threading model & failure handling

| Concern | Strategy |
|---------|----------|
| Blender API on background thread | Never. OSC + HTTP threads only touch queues / precomputed strings. |
| Add-on disabled while running | `unregister()` calls `stop_test` + `stop_capture`; sockets closed; timer unregistered; mDNS unannounced. |
| .blend reload | `@persistent` `load_post` handler stops everything cleanly. |
| Port collision (UDP or HTTP) | Catch `OSError` on bind, surface message in the panel, do not raise into Blender. For HTTP, default `oscquery_http_port=0` lets the OS pick a free port. |
| Shape key missing | Track in "unmatched" set, show in UI when toggled on. |
| User assigns object without shape keys | Operator refuses to start; panel shows guidance. |
| mDNS conflict (another service same name) | `zeroconf` returns a renamed service; surface the actual name in the panel status line. |
| Crash during test | UDP socket uses `SO_REUSEADDR`; HTTP server too; restart should always succeed. |

## 7. Distribution

- Single `.zip` named `blender_vrcft-<version>.zip`, installed via Blender
  5.0's **Get Extensions** > **Install from Disk**.
- Layout:
  ```
  blender_vrcft/
    blender_manifest.toml
    __init__.py
    panel.py
    operators.py
    properties.py
    osc_server.py
    oscquery.py
    capture.py
    ui_list.py
    vendor/
      pythonosc/...
      zeroconf/...
    data/
      unified_expressions.json    # bundled for the optional UE union
  ```
- Vendored deps:
  - **python-osc** (MIT)
  - **zeroconf** (LGPL-2.1) — GPL-compatible, fine to bundle in a Blender
    (GPL) add-on.
- README with install instructions; no manual VRCFT config required.

## 8. Open questions / risks

1. **VRCFT TXT-record expectations.** Some OSCQuery clients require
   specific TXT records (e.g. `OSCQueryHostName`, version flags). To be
   confirmed against a real VRCFT capture in Phase 4.
2. **Timer cadence vs viewport redraw.** 60 Hz drain is fine for preview
   but under heavy depsgraph load the viewport may stutter. Mitigation:
   skip writes when delta < 1e-3.
3. **Shape-key name collisions.** If two shape keys differ only by case,
   first-write-wins. Document.
4. **OSCQuery on Windows + firewall.** First-run firewall prompt for the
   HTTP listener. Document in README.
5. **Blender 5.0 extension API stability.** 5.0 just shipped; if
   manifest format details shift, may need tweaks. Pin to 5.0.x in
   manifest.

## 9. Phased delivery plan

Each phase is sized to be an independently demoable prompt.

### Phase 1 — Add-on skeleton (no OSC yet)
**Goal:** Install the add-on into Blender 5.0, see the **VRCFT** panel,
assign a head mesh, set ports + smoothing, click Start/Stop that toggles
state and prints to console.
- `blender_manifest.toml` for Blender 5.0.
- `PropertyGroup` for settings on `Scene`.
- Panel drawing all configured properties.
- Stub Start/Stop operators.
- README with install steps.
- **Smoke test:** `blender.exe --background --python tests/phase1_smoke.py`
  loads a `.blend`, verifies the add-on registers and the property group
  is attached. Headless OK because no UI rendering yet.

**Done when:** the add-on enables/disables cleanly, the panel renders,
properties persist with the .blend.

### Phase 2 — OSC reception + live shape-key drive + capture logger
**Goal:** Press Start, send OSC manually with a tiny test client, see
shape keys move. Press Capture to log everything to a file.
- Vendor `python-osc` (pulled fresh from PyPI).
- Background OSC server thread + queue + drain timer.
- Smoothing applied.
- Capture logger (independent operator).
- Friendly error if port is busy.
- **Smoke test:** headless Blender + `tests/phase2_smoke.py` opens a .blend
  with a cube with shape keys, starts the OSC server, sends a couple of
  OSC messages from the test script itself, drives a few timer ticks
  manually, asserts shape-key value moved.

**Done when:** sending `/avatar/parameters/JawOpen 0.7` to localhost:9000
visibly moves a `JawOpen` shape key in the viewport, and the capture log
contains the message.

### Phase 3 — Live parameter list UI
**Goal:** While Test is running, the panel shows a live list of detected
parameters with progress bars.
- `UIList` of detected names.
- Per-row 0–1 bar via `layout.progress`.
- Freeze-sort + Show-unmatched toggles.
- **Smoke test:** mostly manual — headless can't render the UI. Add a
  unit test for the parameter-list state machine (sort, dedup, decay).

**Done when:** sending three different params at varying values shows
three live bars with correct labels, in a stable order when frozen.

### Phase 4 — OSCQuery responder (mDNS + HTTP)
**Goal:** VRCFT discovers Blender automatically. No file writes, no
manual VRCFT config.
- Vendor `zeroconf` (or custom mDNS — see §8 #1).
- HTTP server returning the OSCQuery JSON tree.
- mDNS announce on Start, withdraw on Stop.
- Tree rebuild operator.
- **Smoke test:** spin up the responder in a subprocess, query `GET /`
  with `urllib.request`, parse the JSON, assert the parameter shape.
  Validate the mDNS announcement is visible to a `zeroconf.Browser` in
  the same test.

**Done when:** with VRCFT running, starting the test makes Blender
appear in VRCFT's discovered-targets list and parameters start flowing
without us touching VRCFT's UI.

### Phase 5 — Robustness, polish
- `@persistent` load handlers for safe teardown.
- Better status surfaces in the panel (status line: "Listening on :9000",
  "Discovered as 'Blender VRCFT'", "Port in use", "No mesh assigned").
- Unmatched-parameter inspector.
- Optional: legacy LocalLow JSON fallback if user requests it.

### Phase 6 — Packaging & docs
- Build script that produces the zip with vendored deps.
- README with screenshots, troubleshooting (firewall, port collisions,
  VRCFT version notes).
- LICENSE attribution for vendored libs.

## 10. Reference material

- Blender install on this machine:
  `C:/Program Files/Blender Foundation/Blender 5.0/blender.exe`.
  Headless invocation:
  `blender.exe --background --python <script.py> -- <args>`.
- Lyuma Av3Emulator OSC config (kept as legacy reference for the JSON-on-
  disk fallback should we ever need it):
  `F:/OpenSource/Av3Emulator/Runtime/Scripts/A3EOSCConfiguration.cs`.
- VRCFT parameter list:
  https://docs.vrcft.io/docs/tutorial-avatars/tutorial-avatars-extras/parameters
- python-osc: https://pypi.org/project/python-osc/
- python-zeroconf: https://pypi.org/project/zeroconf/
- OSCQuery 1.0 proposal:
  https://github.com/Vidvox/OSCQueryProposal
- Blender 5.0 extension docs:
  https://docs.blender.org/manual/en/5.0/advanced/extensions/index.html
