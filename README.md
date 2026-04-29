# Blender VRCFT

A Blender 5 add-on that drives your avatar's shape keys and eye bones from
live [VRCFaceTracking](https://github.com/benaclejames/VRCFaceTracking) data,
so you can preview expressions in the viewport and bake them to keyframes
for animation.

## What it does

- Listens to VRCFT over OSC and updates matching shape keys in real time.
- Registers itself with VRCFT as a custom avatar (`Blender VRCFT - <blend
  name>`), so the VRCFT app knows what parameters to send.
- Drives the eye bones from the gaze parameters with a configurable angle
  range.
- Has two modes:
  - **Test** — preview only.
  - **Capture** — same as Test, but records keyframes on the shape keys and
    eye bones as you go.
- Smooths and rounds incoming values to take the jitter out of the tracking.

## Install

1. On the repo page, click **Code → Download ZIP**.
2. In Blender, open **Edit → Preferences → Get Extensions → ▾ menu →
   Install from Disk…** and pick the zip.
3. Enable the **VRCFT** extension.

## Use

In the **3D Viewport → N panel → VRCFT** tab:

1. Set **Head Mesh** to the mesh that has your visemes / face shape keys.
2. (Optional) Assign **Left Eye Bone** and **Right Eye Bone**, and set the
   eye angle range.
3. Pick a **Mode**:
   - **Test** — live preview, nothing is recorded.
   - **Capture** — records keyframes. Each Start clears the previous capture
     so you can iterate quickly.
4. Click **Start**. Make faces. Click **Stop** when you're done.
5. In Capture mode, the resulting keyframes live on the head mesh's shape
   keys and on the eye bones, ready to export or edit like any other
   animation.

## Settings worth knowing

- **Smoothing** (default `0.3`): higher = snappier, lower = softer.
- **Rounding** (default `0.07`): values must change by at least this much
  before the target updates. Endpoints (0 and 1) snap immediately so things
  like the mouth still fully open and close.
- **OSC Port** (default `9000`): receive port. Must match VRCFT's send port.
- **VRCFT Send Port** (default `9001`): used to tell VRCFT which avatar to
  emit for.

## Troubleshooting

- **Some shape keys don't move** — make sure the names match Unified
  Expressions (`JawOpen`, `MouthSmileLeft`, `EyeOpenLeft`, …). The combined
  parameters are split automatically; the per-side names need to match.
- **Eyes look the wrong way** — check the eye bone roll in Edit Mode (VRChat
  expects each eye bone's local axis to point up).
- **VRCFT shows the wrong avatar** — hit Stop, then Start again. The add-on
  registers the avatar on each Start.
- **Nothing's coming in** — confirm VRCFT is running, that its OSC output
  is enabled, and that the ports match.

## License

GPL-3.0-or-later.
