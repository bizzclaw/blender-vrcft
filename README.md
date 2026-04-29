# BlenderVRCFT

A Blender add-on for previewing [VRCFaceTracking](https://docs.vrcft.io)
Unified Expressions on an avatar in real time, driven by live OSC.

**Status:** Phase 3 — UI skeleton, OSC reception, capture logger, and a live
parameter list with progress bars. OSCQuery discovery is the only remaining
phase. See [docs/TDD.md](docs/TDD.md) for the full design and roadmap.

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

## What works through Phase 2

- The **VRCFT** side panel with all configurable settings.
- Settings persist with the .blend file.
- Start Test binds the configured UDP port and listens for OSC. Messages
  matching the address prefix drive the assigned mesh's shape keys, with
  per-tick smoothing.
- `v2/` prefix is stripped transparently — `/avatar/parameters/v2/JawOpen`
  matches a shape key named `JawOpen`.
- Out-of-bounds values are clamped to `[0, 1]`.
- Start Capture writes every inbound OSC message (including those outside
  the address prefix) to the configured file as TSV, with a header and
  footer. Capped at 50 MB per session.
- Test and Capture can run independently or together; the underlying OSC
  socket is reference-counted.
- A live **Live Parameters** list shows every received parameter as a
  0–1 progress bar, labeled with its name. Unmatched parameters (no
  shape key on the assigned mesh) show with a warning icon and can be
  hidden via the question-mark toggle. **Freeze Sort** switches from
  most-recently-updated-first to alphabetical. The X icon clears the
  list.

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
```

Each exits 0 on success and prints `[smoke] PASS`.

## License

GPL-3.0-or-later.
