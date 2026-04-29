# BlenderVRCFT

A Blender add-on for previewing [VRCFaceTracking](https://docs.vrcft.io)
Unified Expressions on an avatar in real time, driven by live OSC.

**Status:** Phase 3+ — UI skeleton, OSC reception, capture logger, live
parameter list, bipolar v2-parameter splitting, blendshape reset on Stop,
and LocalLow avatar-JSON registration so VRCFT shows
`Blender VRCFT - <blend filename>` instead of your last VRChat avatar.
OSCQuery (mDNS + HTTP) discovery is the only remaining phase. See
[docs/TDD.md](docs/TDD.md) for the full design and roadmap.

## Requirements

- Blender 5.0 or newer.
- Windows (other platforms not yet tested).

## Install (development build)

1. Zip the `blender_vrcft/` folder so the manifest sits at the root of the
   archive (include the `vendor/` directory — `python-osc` is bundled
   there):
   ```
   blender_vrcft.zip
     blender_manifest.toml
     __init__.py
     panel.py
     operators.py
     properties.py
     osc_bridge.py
     capture.py
     ui_list.py
     vendor/
       pythonosc/...
   ```
2. In Blender: **Edit → Preferences → Get Extensions → ▼ menu →
   Install from Disk…** and pick the zip.
3. Open the 3D Viewport, press **N** to open the side panel, switch to the
   **VRCFT** tab.

## What works through Phase 3+

- The **VRCFT** side panel with all configurable settings.
- Settings persist with the .blend file.
- Start Test binds the configured UDP port and listens for OSC. Messages
  matching the address prefix drive the assigned mesh's shape keys, with
  per-tick smoothing.
- `v2/` prefix is stripped transparently — `/avatar/parameters/v2/JawOpen`
  matches a shape key named `JawOpen`.
- **Bipolar / composite / simplified parameters are decomposed** to the
  underlying per-side shape keys when the combined parameter is not itself
  a shape key. Examples:
  - `JawX` → `JawRight` (positive) / `JawLeft` (negative); `JawZ`,
    `MouthUpperX`, `MouthLowerX`, `MouthX` similarly.
  - `EyeLeftX/Y`, `EyeRightX/Y`, `EyeX`, `EyeY` → `EyeLookIn/Out/Up/Down*`.
  - `CheekPuffSuck[Left|Right]` → `CheekPuff*` / `CheekSuck*`.
  - `BrowExpression*`, `BrowDown*`, `BrowOuterUp`, `BrowInnerUp`, `BrowUp`
    → the four `Brow*` per-side shape keys.
  - `SmileFrown*`, `SmileSad*`, `MouthSmile*`, `MouthSad*` → corner pull /
    slant / frown / stretch shape keys.
  - `MouthOpen`, `MouthUpperUp`, `MouthLowerDown`, `LipSuck*`, `LipFunnel*`,
    `LipPucker*`, `NoseSneer`, `CheekSquint`, `EyeSquint` → per-side fan-out.
  - `EyeLid` / `EyeLidLeft` / `EyeLidRight` drive whichever of
    `EyeClosed*` (UE base, fires when v < 0.75), `EyeOpen*` (inverse,
    legacy), and `EyeWide*` (fires when v > 0.75) the avatar exposes.
  - `JawClench1`/`JawMandibleRaise1` aliases.
- Out-of-bounds values are clamped to `[0, 1]`.
- **Rounding** slider acts as a **deadband on the smoothing target**:
  the target only updates when the incoming raw value moves more than
  this from the last committed value. While the raw is jittering inside
  the deadband, the smoothing target stays put, so the shape key holds
  rock-steady at whatever exact value it last committed to. Smoothing
  still applies normally between committed targets — the output is never
  quantized, only the target. **Saturation values (raw at 0 or 1) always
  commit immediately**, so shape keys can fully open/close even with a
  large deadband. 0 = off.
- **Smoothed shape keys keep converging** even after VRCFT throttles
  steady-state OSC. The bridge caches the last raw value per parameter
  and, when smoothing < 1, re-applies it every tick until the shape key
  reaches the target. Without this a single retract event followed by
  silence (e.g. Quest Pro tongue retract) would leave the shape key
  stuck part-way through its fade.
- **On Stop Test, every shape key the session drove is reset to 0**, and
  any assigned eye bones are returned to their identity rotation.
- **Eye bones (optional).** Assign an armature plus a left- and right-eye
  pose bone in the **Eye Bones** panel. While Test is running, VRCFT's
  `EyeX`/`EyeY` (and per-eye `EyeLeftX/Y`, `EyeRightX/Y` when streamed)
  drive each bone's local pitch/yaw, smoothed and deadbanded just like
  shape keys. The four **Range Up/Down/Left/Right** angles (default 30°
  each = 60° total per axis) clamp the bone rotation per direction.
  Convention: **tail-up** eye bones (the standard for VRChat humanoid
  rigs in Blender — bone extends upward out of the head). Pitch is
  applied to local −X, yaw to local +Y, and the bone's local Z (roll)
  is preserved. If a rig's local axes are mirrored, enter a negative
  range angle to flip that axis. Eye bones run alongside any matching
  shape keys (e.g. `EyeLookInLeft`), so avatars can use either or both.
- **VRCFT Avatar Status** correctly shows `Blender VRCFT - <blend filename>`:
  on Start Test the add-on writes
  `LocalLow\VRChat\vrchat\OSC\<userid>\Avatars\avtr_blender_vrcft_<guid>.json`
  listing the avatar's shape keys **plus the full Unified Expressions
  parameter set** (≈86 v2 names + ≈48 legacy / simplified names), then
  sends `/avatar/change` to VRCFT (default port 9001 — configurable as
  **VRCFT Input Port**). Declaring the full UE set is what makes VRCFT
  actually emit all 50+48 parameters; otherwise it would only send to the
  literal shape-key names. The GUID is deterministic per `.blend` path, so
  the same file always gets the same registration.
- **Capture mode** bakes the live preview into Blender animation data.
  Pick **Capture** in the **Mode** dropdown and click **Start**. Every
  tick, the add-on inserts sparse keyframes into a `VRCFT_Capture_*`
  action — anchoring at the current scene frame, advancing one frame
  per tick, and only writing keys when a value actually changes
  (`>1e-5`). On Start, only the F-curves the bridge will overwrite are
  cleared from the action; any other curves on it are preserved. On
  Stop, a final key is force-anchored. The Mode dropdown is greyed out
  while running — flip back to **Test** or **Stop** first to change
  modes.
- **OSC Log** (separate, optional) writes every inbound OSC message to
  the configured TSV file. Independent of Test/Capture; cap is 50 MB
  per session. Use it for debugging the wire protocol.
- The OSC socket is reference-counted, so Capture and the OSC Log can
  run simultaneously.
- A live **Live Parameters** list shows every received parameter as a
  0–1 progress bar, labeled with its name. Unmatched parameters (no
  shape key on the assigned mesh and no bipolar split landed) show with
  a warning icon and can be hidden via the question-mark toggle.
  **Freeze Sort** switches from most-recently-updated-first to
  alphabetical. The X icon clears the list.

## What does not work yet

- No OSCQuery discovery (Phase 4). VRCFT will not find Blender on its own
  yet — for now you must manually point an OSC sender at the configured
  port.

## Headless smoke tests

```
"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
    --background --factory-startup --python tests/phase1_smoke.py

"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
    --background --factory-startup --python tests/phase2_smoke.py

"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
    --background --factory-startup --python tests/phase3_smoke.py

"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
    --background --factory-startup --python tests/phase4_smoke.py
```

Each exits 0 on success and prints `[smoke] PASS`.

## License

GPL-3.0-or-later.
