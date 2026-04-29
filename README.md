# Blender VRCFT

A Blender 5 add-on that pipes live VRCFaceTracking (VRCFT) face data into
your avatar so you can preview expressions, dial in shape-key behavior,
and bake the result into Blender keyframes for export.

It works as a drop-in alternative to "load my avatar in Unity to see if
the shape keys are right" — the avatar stays in Blender, VRCFT thinks
it's a normal VRChat avatar, and you watch the result update in real
time in the viewport.

---

## Capabilities

- **Live OSC preview.** Listens on UDP for VRCFaceTracking's standard
  `/avatar/parameters/...` messages and drives matching shape keys on
  the head mesh you assign.
- **Full Unified Expressions parameter set.** Receives all ~86 v2
  parameters and ~48 legacy / simplified parameters. Bipolar / composite
  / simplified params (e.g. `JawX`, `MouthUpper`, `EyeLidLeft`) are
  decomposed into the correct positive/negative components automatically
  (e.g. `JawX → JawLeft / JawRight`).
- **OSCQuery + avatar JSON.** On Start, the add-on writes a Blender-owned
  avatar JSON into `LocalLow/VRChat/vrchat/OSC/<userid>/Avatars/` and
  sends `/avatar/change` to VRCFT, so the **VRCFT Avatar Status** panel
  shows `Blender VRCFT - <your blend filename>` and VRCFT actually emits
  every parameter — not just the literal shape-key names.
- **Smoothing + deadband.**
  - **Smoothing** (default 0.3) lerps every shape key toward its target
    each frame. Even when VRCFT throttles steady-state OSC, the bridge
    keeps converging — no shape keys stuck partway through their fade
    (a real problem on Quest Pro with the tongue family).
  - **Rounding** (default 0.07) is a *deadband on the smoothing target*,
    not a quantizer. Small jitter inside the deadband doesn't move the
    target, so the shape key holds steady; the smoothed output itself is
    never quantized. Saturation values (raw 0 or ±1) always commit
    immediately, so shape keys can fully open/close.
- **Eye-bone driving.** Optionally assign an armature plus a left- and
  right-eye pose bone. `EyeX` / `EyeY` (and per-eye `EyeLeftX/Y`,
  `EyeRightX/Y` when streamed) drive each bone's local pitch/yaw,
  smoothed and deadbanded just like shape keys. Per-direction range
  sliders (Up/Down/Left/Right, default 30°) clamp the rotation. Eye
  bones run alongside any matching shape keys, so avatars with bone
  eye-look, blendshape eye-look, or both, all work.
- **Capture mode.** Bakes the live preview into Blender animation data.
  Switches the session into recording: every tick inserts sparse
  keyframes into a `VRCFT_Capture_*` action and advances the scene
  frame by 1. Re-entering Capture clears just the F-curves the bridge
  is going to overwrite, so a record-export-record loop is one
  click.
- **Live parameter viewer.** A panel UI list shows every received
  parameter as a 0–1 progress bar with a name and "matched / unmatched"
  indicator, sortable alphabetically or by arrival order.
- **OSC log capture (optional).** A separate sub-panel writes every
  inbound OSC message to a TSV log for protocol debugging. Independent
  from Test / Capture; capped at 50 MB per session.
- **Clean session lifecycle.** Stop returns every shape key the session
  drove to 0 and every assigned eye bone to its identity rotation
  (preserving any rest-pose roll on the bone).

---

## Installation

**Requirements**
- Blender **5.0** or newer.
- Windows. Other platforms haven't been tested.
- VRCFaceTracking (current build) running locally, with OSC enabled.

**Install the add-on**
1. Download the latest `blender_vrcft_<n>.zip` from this repo.
2. In Blender: `Edit → Preferences → Get Extensions → ▼ → Install from
   Disk…` and pick the zip. (Or, if you prefer, use the legacy
   `Add-ons → Install…` flow — it accepts the same zip.)
3. Enable **VRCFT** in the extensions list.
4. The **VRCFT** panel now appears in the 3D viewport's **N-panel**
   (press `N` in the viewport, then click the **VRCFT** tab).

The add-on bundles its dependencies (`python-osc`, `zeroconf`); nothing
else needs installing.

**Set up VRCFaceTracking**
1. Run VRCFT and confirm at least one tracking module is connected.
2. In VRCFT settings, make sure **OSC sender** is enabled and pointed at
   `127.0.0.1`. The default send port is `9000` — match this in the
   add-on's **OSC Port** field.
3. The add-on will auto-register a Blender-owned avatar with VRCFT on
   Start and send `/avatar/change`, so VRCFT picks it up automatically.

---

## How to use it

### 1. Assign your head mesh

In the **VRCFT** panel:
- **Head Mesh** — pick the mesh that owns the VRChat / VRCFT shape keys
  (`JawOpen`, `EyeOpenLeft`, `MouthSmileLeft`, etc.). Shape-key naming
  must match the VRCFT Unified Expressions names; the bridge handles
  the standard composites for you (e.g. `JawX` is split into `JawLeft`
  / `JawRight` automatically — you only need the per-direction keys).

### 2. (Optional) Eye-bone setup

If your avatar uses bone-rotated eyes instead of (or in addition to)
shape keys:
- **Eye Armature** — pick the armature that owns the eye bones.
- **Left Eye Bone / Right Eye Bone** — pick the pose bones. The
  dropdowns filter to the assigned armature.
- **Range Up / Down / Left / Right** — maximum rotation in degrees per
  direction. Default 30° each (60° total per axis). If a particular rig
  has a mirrored axis, type a negative angle into that range slider to
  flip it.

### 3. Tune smoothing + rounding

- **Smoothing** — lerp factor per frame. 0 = none (raw, jittery), 1 =
  snap. Default 0.3 is a good starting point.
- **Rounding** — deadband. The smoothed target only updates when the
  raw value moves more than this from the last committed value, so
  micro-jitter on a sensor doesn't propagate. Default 0.07. Set to 0 to
  disable.

### 4. Network

- **OSC Port** — UDP port we listen on. Default `9000`. Match VRCFT's
  send port.
- **VRCFT Input Port** — UDP port VRCFT itself listens on. We send
  `/avatar/change` here on Start so VRCFT switches to our Blender-owned
  avatar JSON. Default `9001`.
- **OSCQuery HTTP Port** — `0` picks a free port at start. Most users
  can leave this alone.
- **Service Name** — mDNS name advertised to OSCQuery clients. Default
  `Blender VRCFT`.
- **Address Prefix** — `/avatar/parameters/` by default; the `v2/`
  segment is stripped transparently.

### 5. Run

Use the **Session** box:

- **Mode** — `Test` or `Capture`.
- **Start** — begins the session in the selected mode.
- **Stop** — ends the session. Every shape key the session drove is
  reset to 0 and every assigned eye bone is returned to its identity
  rotation (any rest-pose roll on the bone is preserved).

While running, the mode selection is greyed out — stop first if you want to
switch modes.

#### Test mode

Pure preview. The avatar moves with VRCFT in the viewport. No
animation data is written. Use this to dial in smoothing, rounding,
and eye ranges.

#### Capture mode

Same as Test, plus:
- An action named `VRCFT_Capture_<mesh>_Shapes` is created (or
  re-used) on the head mesh's shape keys, and a similarly-named action
  on the eye armature. **Only the F-curves the bridge will overwrite**
  are cleared from the action — any other curves on it are preserved.
- A keyframe is anchored at the current `scene.frame_current` for every
  driven channel.
- Every tick (~60 fps), the bridge inserts **sparse** keyframes (only
  on channels whose value changed since the last key, threshold
  `1e-5`) and advances `scene.frame_current` by 1. Interpolation is
  linear.
- On Stop, a final key is force-anchored on every channel.

When you're happy with the take, scrub the timeline to verify, then
export normally (FBX, glTF, etc.) — the action is just a regular
Blender action.

A typical workflow:
1. Set Mode → `Capture`, Start, perform expression, Stop.
2. Scrub / play. Like it? Export. Don't like it? Hit Start again — the
   driven curves are wiped, fresh anchor at the current frame, you
   record over.

#### Live parameters

Below the session box is the live parameter list — every received
parameter as a 0-1 bar, with a `?` icon for unmatched parameters
(arrived but no shape key on the assigned mesh). Use it to confirm
naming. Toggle **Sort Alphabetical** and **Show Unmatched** at the
top of the list. The `X` button clears the list.

#### OSC Log (optional)

A separate sub-panel. Toggle it on to dump every inbound OSC message
to a TSV file (capped at 50 MB per session). Useful for debugging
the wire protocol; independent from Test / Capture.

---

## Troubleshooting

- **Nothing moves on the avatar.** Check the live parameter list.
  If you see parameters arriving but they're all unmatched, your
  shape-key names don't match the VRCFT Unified Expressions naming.
  If nothing arrives, VRCFT isn't sending OSC — check VRCFT's OSC
  settings and that the port matches.
- **Avatar Status shows the wrong avatar.** Toggle Stop / Start; the
  add-on rewrites and re-broadcasts its avatar JSON each time.
- **Tongue (or other smoothed key) stays stuck partway.** Make sure
  you're on a recent build — the bridge re-applies the cached raw value
  every tick until the smoothing converges. If it still happens, send
  the OSC log.
- **Eyes look the wrong way / rotate on the wrong axis.** The default
  convention assumes **tail-up** eye bones (the standard for VRChat
  humanoid rigs in Blender). If a rig has a mirrored axis, put a
  negative angle in the affected Range slider.
- **Capture didn't keyframe a channel.** Capture only writes channels
  the bridge actively drives — the head mesh's shape keys and the two
  assigned eye bones. Other animation on the same action is preserved
  but isn't extended by capture.

---

## Repo layout

- `blender_vrcft/` — the add-on package (this is what gets zipped).
- `blender_vrcft_<n>.zip` — built extension archives.
- `tests/phaseN_smoke.py` — Blender-driven smoke tests.
  Run any of them with:
  ```
  "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" ^
      --background --factory-startup --python tests/phase5_smoke.py
  ```
- `docs/` — design notes (TDDs).

---

## License

See `blender_vrcft/blender_manifest.toml` for license / metadata.
