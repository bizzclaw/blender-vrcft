# Blender VRCFT

A Blender 5 add-on that drives your avatar's shape keys and eye bones from
live [VRCFaceTracking](https://github.com/benaclejames/VRCFaceTracking) data,
so you can preview expressions in the viewport and bake them to keyframes
for animation.

## What it does

- Listens to VRCFT over OSC and updates matching shape keys in real time.
- Registers itself with VRCFT as a custom avatar (`Blender VRCFT - <blend
  name>`), so the VRCFT app knows what parameters to send.
- Lets you choose which blendshape vocabulary the avatar uses:
  - **Unified** — VRCFaceTracking Unified Expressions v2 plus legacy compatibility names.
  - **ARKit** — Apple's 52 lower-camel face coefficients (`jawOpen`, `mouthSmileLeft`, `eyeBlinkRight`, ...).
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
2. Pick a **Blendshape Set**:
  - **Unified** if the avatar uses Unified Expressions / VRCFT-style names.
  - **ARKit** if the avatar uses Apple's ARKit coefficient names.
3. (Optional) Assign **Left Eye Bone** and **Right Eye Bone**, and set the
  eye angle range.
4. Pick a **Mode**:
   - **Test** — live preview, nothing is recorded.
   - **Capture** — records keyframes. Each Start clears the previous capture
     so you can iterate quickly.
5. Click **Start**. Make faces. Click **Stop** when you're done.
6. In Capture mode, the resulting keyframes live on the head mesh's shape
   keys and on the eye bones, ready to export or edit like any other
   animation.

## Settings worth knowing

- **Smoothing** (default `0.3`): higher = snappier, lower = softer.
- **Rounding** (default `0.07`): values must change by at least this much
  before the target updates. Endpoints (0 and 1) snap immediately so things
  like the mouth still fully open and close.
- **Blendshape Set**: controls which parameter family Blender asks VRCFT to
  emit and how incoming values are matched to the avatar rig.
- **OSC Port** (default `9000`): receive port. Must match VRCFT's send port.
- **VRCFT Send Port** (default `9001`): used to tell VRCFT which avatar to
  emit for.

## Troubleshooting

- **Some shape keys don't move** — make sure the selected **Blendshape Set**
  matches the avatar. Unified expects VRCFT / Unified Expressions-style names
  (`JawOpen`, `MouthSmileLeft`, `EyeOpenLeft`, …). ARKit expects Apple's
  lower-camel names (`jawOpen`, `mouthSmileLeft`, `eyeBlinkLeft`, …) and will
  also bridge common ARKit coefficients onto equivalent Unified split shapes
  when possible.
- **Eyes look the wrong way** — check the eye bone roll in Edit Mode (VRChat
  expects each eye bone's local axis to point up).
- **VRCFT shows the wrong avatar** — hit Stop, then Start again. The add-on
  registers the avatar on each Start.
- **Nothing's coming in** — confirm VRCFT is running, that its OSC output
  is enabled, and that the ports match.

## Testing

### Unit Tests (Fast)

Unit tests verify pure functions that don't require Blender. Run them with pytest:

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test files
pytest tests/unit/test_avatar_json.py
pytest tests/unit/test_osc_bridge.py

# Run with verbose output
pytest -v tests/unit/
```

#### Coverage (Optional)

To generate coverage reports, first install pytest-cov:

```bash
pip install pytest-cov
```

Then run with coverage:

```bash
pytest --cov=blender_vrcft tests/unit/
pytest --cov=blender_vrcft --cov-report=html tests/unit/
```

### Integration Tests (Blender Required)

Smoke tests verify end-to-end functionality in Blender headless mode. These tests
require Blender to be installed and accessible from your system.

Run all smoke tests:

```bash
blender --background --factory-startup --python tests/phase1_smoke.py
blender --background --factory-startup --python tests/phase2_smoke.py
blender --background --factory-startup --python tests/phase3_smoke.py
blender --background --factory-startup --python tests/phase4_smoke.py
blender --background --factory-startup --python tests/phase5_smoke.py
```

On Windows, adjust the Blender path:

```bash
"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
    --background --factory-startup --python tests/phase1_smoke.py
```

### Test Organization

- `tests/unit/` — Fast unit tests for pure functions (no Blender needed)
- `tests/phase*_smoke.py` — Integration tests requiring Blender headless mode
- `tests/conftest.py` — Shared pytest fixtures for unit tests

### Requirements

- **Unit tests**: Python 3.11+, pytest
- **Integration tests**: Blender 5.0+

Install pytest:

```bash
pip install pytest
```

For coverage reporting (optional):

```bash
pip install pytest-cov
```

## CI/CD

This project uses GitLab CI/CD for automated testing. The pipeline includes:

### Stages

1. **Lint** - Code quality checks with ruff
2. **Unit Tests** - Fast pytest runs without Blender (87 tests)
3. **Integration Tests** - Blender smoke tests (5 phases)

### Pipeline Behavior

- **Merge Requests**: Unit tests run automatically; integration tests run manually
- **Main branch**: All tests run automatically
- **Coverage**: Reported in merge requests via Cobertura XML

### Running CI Locally

You can simulate CI jobs locally using Docker:

```bash
# Unit tests
docker run --rm -v $(pwd):/app -w /app python:3.11-slim \
    bash -c "pip install -r requirements-dev.txt && pytest tests/unit/"

# Integration tests (requires Blender)
docker run --rm -v $(pwd):/app -w /app nytimes/blender:5.0 \
    blender --background --factory-startup --python tests/phase1_smoke.py
```

## License

GPL-3.0-or-later.
