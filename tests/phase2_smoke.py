"""Phase 2 smoke test.

    "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
        --background --factory-startup --python tests/phase2_smoke.py

Exercises: OSC server start/stop, message receipt, name matching with
v2/ prefix stripping, smoothing snap mode, capture file format, and
graceful unregister while running.
"""
import os
import socket
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "blender_vrcft", "vendor"))

import bpy  # noqa: E402

import blender_vrcft  # noqa: E402
from blender_vrcft import osc_bridge  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402


def fail(msg):
    print(f"[smoke] FAIL: {msg}")
    sys.exit(1)


def expect(cond, msg):
    if not cond:
        fail(msg)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(predicate, timeout=2.0, interval=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


print("[smoke] registering add-on...")
blender_vrcft.register()

# Pure-function canonicalization tests.
print("[smoke] canonical_name unit checks...")
expect(
    osc_bridge.canonical_name("JawOpen", {"JawOpen": None}) == ("JawOpen", True),
    "raw name should match",
)
expect(
    osc_bridge.canonical_name("v2/JawOpen", {"JawOpen": None}) == ("JawOpen", True),
    "v2/ prefix should strip",
)
expect(
    osc_bridge.canonical_name("FT/v2/JawOpen", {"JawOpen": None}) == ("JawOpen", True),
    "FT/v2/ prefix should strip",
)
expect(
    osc_bridge.canonical_name("FT/v2/JawOpen", {"FT/v2/JawOpen": None}) == ("FT/v2/JawOpen", True),
    "exact full-name match should win over progressive stripping",
)
expect(
    osc_bridge.canonical_name("FT/v2/NoseSneer", {}) == ("NoseSneer", False),
    "no-match should return most-stripped form",
)
expect(
    osc_bridge.canonical_name("v2/JawOpen", {"v2/JawOpen": None, "JawOpen": None}) == ("v2/JawOpen", True),
    "exact match preferred when both v2/ and bare keys exist",
)

# Clean scene + cube with shape keys.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
cube.shape_key_add(name="Basis")
cube.shape_key_add(name="JawOpen")
cube.shape_key_add(name="MouthClosed")

s = bpy.context.scene.vrcft
s.head_mesh = cube
s.osc_port = free_port()
s.smoothing = 1.0  # snap so a single tick reaches the target

print(f"[smoke] using port {s.osc_port}")

# ---- OSC reception + name matching ----
expect(bpy.ops.vrcft.start_test() == {'FINISHED'}, "start_test failed")
expect(s.is_running, "is_running should be True")

client = SimpleUDPClient("127.0.0.1", s.osc_port)
client.send_message("/avatar/parameters/JawOpen", 0.7)               # raw
client.send_message("/avatar/parameters/MouthClosed", 0.42)          # raw
client.send_message("/avatar/parameters/v2/JawOpen", 0.85)           # v2/ prefix
client.send_message("/avatar/parameters/FT/v2/JawOpen", 0.9)         # FT/v2/ prefix
client.send_message("/avatar/parameters/FT/v2/NotAShapeKey", 0.5)    # unmatched
client.send_message("/some/other/route", 1.0)                        # outside prefix

bridge = osc_bridge.get_bridge()
expect(
    wait_for(lambda: bridge.queue.qsize() >= 5, timeout=2.0),
    f"OSC messages did not arrive (queue size {bridge.queue.qsize()})",
)

osc_bridge.tick()

sk = cube.data.shape_keys.key_blocks
print(f"[smoke] JawOpen={sk['JawOpen'].value:.3f} MouthClosed={sk['MouthClosed'].value:.3f}")
# All three JawOpen variants coalesce to one update; last value wins (0.9).
expect(abs(sk["JawOpen"].value - 0.9) < 1e-3, f"JawOpen wrong: {sk['JawOpen'].value}")
expect(abs(sk["MouthClosed"].value - 0.42) < 1e-3, f"MouthClosed wrong: {sk['MouthClosed'].value}")
expect("NotAShapeKey" in bridge.unmatched, "unmatched param (most-stripped) should be tracked")

# ---- Smoothing math ----
s.smoothing = 0.5
sk["JawOpen"].value = 0.0
client.send_message("/avatar/parameters/JawOpen", 1.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 1.0), "smoothing msg lost")
osc_bridge.tick()
expect(
    abs(sk["JawOpen"].value - 0.5) < 1e-3,
    f"smoothing: expected ~0.5 after one tick from 0->1 with alpha 0.5, got {sk['JawOpen'].value}",
)

bpy.ops.vrcft.stop_test()
expect(not s.is_running, "is_running should be False after stop")
expect(bridge.server is None, "server should be torn down")

# ---- Capture logger ----
log_path = os.path.join(tempfile.gettempdir(), "vrcft_phase2_capture.log")
if os.path.exists(log_path):
    os.remove(log_path)
s.capture_path = log_path
s.osc_port = free_port()  # fresh port, previous server was closed

expect(bpy.ops.vrcft.start_capture() == {'FINISHED'}, "start_capture failed")
expect(s.is_capturing, "is_capturing should be True")

cap_client = SimpleUDPClient("127.0.0.1", s.osc_port)
cap_client.send_message("/avatar/parameters/JawOpen", 0.5)
cap_client.send_message("/foo/bar", 1.23)  # outside prefix — capture must still record

# Capture flushes line by line; just give it a moment.
time.sleep(0.2)
bpy.ops.vrcft.stop_capture()
expect(not s.is_capturing, "is_capturing should be False after stop")

with open(log_path, encoding="utf-8") as f:
    log = f.read()
print(f"[smoke] capture log:\n{log}")

expect("/avatar/parameters/JawOpen" in log, "JawOpen missing from capture")
expect("/foo/bar" in log, "/foo/bar missing — catch-all not capturing outside prefix")
expect("# vrcft capture started" in log, "header missing")
expect("# vrcft capture ended" in log, "footer missing")

# ---- Refcounted server: simultaneous test + capture ----
s.osc_port = free_port()
expect(bpy.ops.vrcft.start_test() == {'FINISHED'}, "start_test failed (combo)")
expect(bpy.ops.vrcft.start_capture() == {'FINISHED'}, "start_capture failed (combo)")
expect(bridge.server is not None, "server should be alive")
bpy.ops.vrcft.stop_test()
expect(bridge.server is not None, "server should still be alive after stopping test only")
bpy.ops.vrcft.stop_capture()
expect(bridge.server is None, "server should be down after stopping both")

# ---- Unregister while running ----
s.osc_port = free_port()
bpy.ops.vrcft.start_test()
expect(bridge.server is not None, "server should be running before unregister")
print("[smoke] unregistering while running...")
blender_vrcft.unregister()
# After reset_bridge() the bridge module is reset; re-acquire to verify
bridge = osc_bridge.get_bridge()
expect(bridge.server is None, "server should be down after unregister")

print("[smoke] PASS")
