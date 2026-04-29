"""Phase 1 smoke test.

Run headlessly:
    "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
        --background --factory-startup --python tests/phase1_smoke.py

Verifies the add-on registers, properties attach to Scene, defaults are
correct, head_mesh validation works, and stub operators flip state. Does
NOT exercise the extension manifest path — that is covered by manual
"Install from Disk" testing.
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _addon  # noqa: E402,F401

import bpy  # noqa: E402
import blender_vrcft  # noqa: E402


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fail(msg):
    print(f"[smoke] FAIL: {msg}")
    sys.exit(1)


def expect(cond, msg):
    if not cond:
        fail(msg)


print("[smoke] registering add-on...")
blender_vrcft.register()

scene = bpy.context.scene
expect(hasattr(scene, "vrcft"), "Scene.vrcft missing after register")

s = scene.vrcft
print(
    f"[smoke] defaults: osc_port={s.osc_port}, http_port={s.oscquery_http_port}, "
    f"service='{s.service_name}', smoothing={s.smoothing:.3f}, "
    f"prefix='{s.address_prefix}', capture='{s.capture_path}'"
)

expect(s.osc_port == 9000, f"osc_port default wrong: {s.osc_port}")
expect(s.oscquery_http_port == 0, "oscquery_http_port default should be 0")
expect(s.service_name == "Blender VRCFT", "service_name default wrong")
expect(abs(s.smoothing - 0.3) < 1e-6, "smoothing default wrong")
expect(s.address_prefix == "/avatar/parameters/", "address_prefix default wrong")
expect(s.capture_path == "//vrcft_capture.log", "capture_path default wrong")
expect(s.is_running is False, "is_running should default False")
expect(s.is_capturing is False, "is_capturing should default False")

s.osc_port = 9100
expect(scene.vrcft.osc_port == 9100, "property write did not persist")
s.osc_port = 9000

for opname in (
    "vrcft.start_test",
    "vrcft.stop_test",
    "vrcft.start_capture",
    "vrcft.stop_capture",
):
    mod, name = opname.split(".")
    expect(
        hasattr(getattr(bpy.ops, mod), name),
        f"operator {opname} not registered",
    )

bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
cube.shape_key_add(name="Basis")
cube.shape_key_add(name="JawOpen")
s.head_mesh = cube
s.osc_port = _free_port()

bpy.ops.vrcft.start_test()
expect(s.is_running is True, "is_running should be True after start_test")
bpy.ops.vrcft.stop_test()
expect(s.is_running is False, "is_running should be False after stop_test")

bpy.ops.vrcft.start_capture()
expect(s.is_capturing is True, "is_capturing should be True after start_capture")
bpy.ops.vrcft.stop_capture()
expect(s.is_capturing is False, "is_capturing should be False after stop_capture")

s.head_mesh = None
try:
    bpy.ops.vrcft.start_test()
except RuntimeError as e:
    print(f"[smoke] start_test without mesh raised (expected): {e}")
expect(
    s.is_running is False,
    "start_test should refuse to flip is_running without a head_mesh",
)

print("[smoke] unregistering...")
blender_vrcft.unregister()

print("[smoke] PASS")
