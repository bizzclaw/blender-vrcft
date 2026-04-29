# TDD: Keyframe-Capture Mode

## Goal
Replace the primary meaning of "Capture" with a **keyframe-recording**
mode that bakes the live OSC-driven preview into Blender animation data.
The existing OSC-log JSON capture stays as a separate optional toggle.

## Workflow
1. User assigns head mesh + (optionally) eye bones, configures smoothing
   / rounding / ranges.
2. User selects **Capture** in the Mode dropdown and clicks Apply.
3. Add-on:
   - clears existing keyframes on the data paths it will write,
   - starts the OSC bridge (same as Test),
   - on every tick, after applying values to the model, inserts
     keyframes on changed channels at the current scene frame, then
     advances the scene frame by 1.
4. User performs whatever expression(s) they want to record.
5. User flips the Mode dropdown back to Test (continue previewing,
   capture stops, frame stops advancing) or Idle (everything stops).
6. User reviews the timeline in Blender and exports manually.

## State machine
Mode dropdown values: `IDLE`, `TEST`, `CAPTURE`.

Transition matrix (apply-button driven):

| From \ To | IDLE              | TEST              | CAPTURE                                        |
|-----------|-------------------|-------------------|------------------------------------------------|
| IDLE      | no-op             | start_test        | start_test + clear_anim + start_capture        |
| TEST      | stop_test         | no-op             | clear_anim + start_capture (test stays alive)  |
| CAPTURE   | stop_capture + stop_test | stop_capture | no-op                                          |

`stop_capture` does NOT stop OSC; `stop_test` always also calls
`stop_capture` for safety.

## Channels recorded
Per tick we keyframe the union of:
1. Every shape key on the head mesh whose value changed since its last
   inserted keyframe (or has no keyframe yet this session).
2. Every shape key the user has *pre-existing* keyframes on (from any
   other action) whose value changed — this satisfies "all driven
   values plus any keys the user has manually animated". The user's own
   keyframes from the previous action are NOT inserted into ours; we
   sample the current value and write it into the new action so manual
   work is preserved as it actually appears.
3. Each assigned eye bone's `rotation_euler` X and Y components.

We never keyframe Z (bone roll) or Y location/scale — those aren't
driven.

## Sparse insertion
For each channel:
- track `last_keyed_value` per data-path index.
- on tick, compare current value; if `abs(current - last_keyed) > 1e-5`
  (or no previous key), insert a keyframe at the current scene frame
  with linear interpolation, and update `last_keyed_value`.
- on capture START we force-insert a keyframe for every channel at the
  starting frame so curves are anchored.
- on capture STOP we force-insert a final keyframe so the last value is
  recorded.

## Action handling
- Mesh shape-key animation lives on `mesh.data.shape_keys.animation_data.action`.
- Bone animation lives on `armature.animation_data.action`.
- On capture START, we ensure each has an action named
  `VRCFT_Capture_<mesh.name>` / `VRCFT_Capture_<armature.name>`. If one
  already exists with that name, **clear only the F-curves whose
  data_path matches what we're going to write** (per question 4). Other
  curves on the same action are preserved.

## Frame advancement
- On capture START: remember `start_frame = scene.frame_current`.
- On every tick during capture, after writing keyframes, advance
  `scene.frame_current += 1`.
- Scene FPS is honoured by Blender; we just step one frame per tick
  (~60Hz). If user wants exact 30fps timing they can change scene FPS.

## UI changes
Replace the current Test box (Start/Stop) and Capture box (Start/Stop)
with a single **Mode** box:

```
+ Mode -----------------+
| [ Mode ▾ ] [ Apply ]  |
| Status: <text>        |
| Start frame: <n>      |   (only visible while CAPTURE is the
| Frames captured: <n>  |    *current* mode)
+-----------------------+
```

The OSC-log JSON capture moves to its own little box below, with the
existing path field and a single toggle button (no behaviour change for
the JSON capture itself).

## Properties / state
New on `VRCFT_Settings`:
- `mode: EnumProperty('IDLE','TEST','CAPTURE')` — what the dropdown is
  currently *set to*.
- `current_mode: EnumProperty(...)` (read-only display) — what the bridge
  is *actually* in. Updated by the operator.
- `capture_start_frame: IntProperty` (read-only display).
- `capture_frame_count: IntProperty` (read-only display).
- `osc_log_path` — renamed from `capture_path` to disambiguate.
- `is_osc_logging: BoolProperty` (read-only) — replaces `is_capturing`.

`is_running` becomes derived: `current_mode != 'IDLE'`.

State on `OSCBridge`:
- `keyframer: Keyframer | None` — owns last-keyed value caches and
  performs sparse insertion. Created in `start_capture`, finalized in
  `stop_capture`.

## Implementation phases (TDD)

### Phase 5a: scaffolding + state machine (no recording yet)
**Tests** (`tests/phase5_smoke.py`):
1. Import + register doesn't error.
2. `mode` property exists with correct items + default `IDLE`.
3. Apply-mode operator exists; running it from `IDLE` -> `TEST` starts
   the bridge; `TEST` -> `IDLE` stops it; `IDLE` -> `CAPTURE` starts the
   bridge AND sets `current_mode` to `CAPTURE`.
4. `current_mode` reflects the actual bridge state after each
   transition, even on errors (e.g. trying to enter capture without a
   mesh assigned -> error and `current_mode` stays `IDLE`).

### Phase 5b: keyframer module (pure)
New file `blender_vrcft/keyframer.py` with:
- `Keyframer` class taking (mesh, armature, left_bone, right_bone).
- `start(frame)` -> ensures actions, clears matching f-curves, anchors
  every channel at `frame`, records `start_frame`.
- `tick(frame, eye_param_committed)` -> walks shape keys + bone
  rotations, inserts keys for channels whose current value differs
  enough from `last_keyed`. Returns the count of keys inserted.
- `stop(frame)` -> force-anchors every channel at `frame`.

**Tests** (`tests/phase5_keyframer.py`):
1. Building a mesh with two shape keys + an armature with two bones,
   running `start()` at frame 5, ticking three times with changed
   values, then `stop()`, produces F-curves with the expected key
   counts and the values match what we wrote.
2. Sparse: ticking with the SAME values produces no new keys after the
   anchor.
3. Pre-existing keyframe on a non-driven shape key on the same action
   is preserved (not deleted) when capture starts.

### Phase 5c: bridge integration
In `osc_bridge.tick`:
- after the shape-key + eye-bone passes, if `b.keyframer` is not None,
  call `b.keyframer.tick(scene.frame_current, b.committed_values)` and
  advance `scene.frame_current += 1`.

In operator:
- `apply_mode` operator drives transitions per the table above; on
  CAPTURE it instantiates `Keyframer` with the current settings.

**Tests** (extend phase5_smoke):
1. End-to-end: assign mesh+armature+bones, set mode CAPTURE, send a
   sequence of OSC values for JawOpen + EyeX, tick N times, set mode
   IDLE, then assert the mesh shape-key action has `JawOpen` curve with
   keys at frame_start, frame_start+1, ... and the eye bone's
   `rotation_euler[0]` curve has keys with the right approximate
   values.

### Phase 5d: panel UI rebuild
- Replace test/capture boxes with the single Mode box described above.
- OSC JSON log moves to its own collapsible box.
- `start_test` / `stop_test` / `start_capture` / `stop_capture`
  operators are kept internally but become thin wrappers around the new
  state machine, so external scripts and the existing test files don't
  break.

(No new automated test for UI; phase1_smoke continues to validate
register/unregister.)

### Phase 5e: docs + ship
- README: replace "Capture" section with a "Capture mode" section
  describing the workflow + keep a small "OSC log" subsection.
- Bump manifest to `0.6.0`, rebuild zip.

## Open questions / risks
- **Auto frame advance** while user is also playing the timeline: not
  expected to be an issue because Test mode doesn't advance frames; only
  Capture does. If user starts playback during capture there will be
  contention — out of scope, document as "don't do that".
- **Manual-keyframed channels** (channels we don't drive but the user
  has keys on in another action): we *sample* current value each tick,
  but if the user's only animation source is the *other* action, that
  value won't change unless they're playing back. We document this as
  "manual keys are preserved on their own action; capture only writes
  what we currently see." For the new capture action, we'll snapshot
  the merged result of (driver + user keys evaluated at scene frame)
  via `mesh.data.shape_keys.key_blocks[name].value`, which is exactly
  what we already read.
- **Action collisions** if user already has a `VRCFT_Capture_*` action
  bound to the data block: we clear only matching f-curves, so other
  curves on that action survive. If user has different content named
  the same way but on different paths, they're fine.
