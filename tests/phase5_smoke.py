"""Phase 5 smoke test: capture mode (state machine + keyframer + bridge).

    "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \\
        --background --factory-startup --python tests/phase5_smoke.py
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _addon  # noqa: E402,F401

import bpy  # noqa: E402
import math  # noqa: E402

import blender_vrcft  # noqa: E402
from blender_vrcft import keyframer as kf_mod, osc_bridge  # noqa: E402
from blender_vrcft.keyframer import _action_fcurves, _find_fcurve  # noqa: E402
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


def make_mesh_with_keys(name, key_names):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (1, 1, 0)], [], [(0, 1, 2)]
    )
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    for kn in key_names:
        kb = obj.shape_key_add(name=kn)
        kb.value = 0.0
    return obj


def make_eye_armature():
    arma_data = bpy.data.armatures.new("EyeArm")
    arma = bpy.data.objects.new("EyeArm", arma_data)
    bpy.context.collection.objects.link(arma)
    bpy.context.view_layer.objects.active = arma
    bpy.ops.object.mode_set(mode='EDIT')
    for bn, x in (("LeftEye", -0.05), ("RightEye", 0.05)):
        eb = arma_data.edit_bones.new(bn)
        eb.head = (x, 0.0, 1.7)
        eb.tail = (x, 0.1, 1.7)
    bpy.ops.object.mode_set(mode='OBJECT')
    return arma


# ============================================================
# Phase 5b: keyframer module unit checks
# ============================================================
print("[smoke] phase5b keyframer unit checks...")
blender_vrcft.register()

mesh = make_mesh_with_keys("Phase5Mesh", ["JawOpen", "MouthSmileLeft"])
arma = make_eye_armature()
kf = kf_mod.Keyframer(
    mesh=mesh, armature=arma,
    left_bone="LeftEye", right_bone="RightEye",
)
kf.start(frame=10)

# After start, both actions exist with anchor keys at frame 10.
sk_action = mesh.data.shape_keys.animation_data.action
arm_action = arma.animation_data.action
expect(sk_action is not None, "shape-key action created")
expect(arm_action is not None, "armature action created")
expect(sk_action.name.startswith("VRCFT_Capture_"), "action name prefix")

jaw_curve = _find_fcurve(sk_action, 'key_blocks["JawOpen"].value', 0)
expect(jaw_curve is not None, "JawOpen f-curve exists after start")
expect(len(jaw_curve.keyframe_points) == 1, f"anchor key count: {len(jaw_curve.keyframe_points)}")
expect(jaw_curve.keyframe_points[0].co[0] == 10, "anchor at frame 10")

# Sparse: tick at same value -> no new key
mesh.data.shape_keys.key_blocks["JawOpen"].value = 0.0
n = kf.tick(frame=11)
expect(n == 0, f"sparse tick with no change should insert 0, got {n}")

# Tick with changed value -> new key
mesh.data.shape_keys.key_blocks["JawOpen"].value = 0.5
n = kf.tick(frame=12)
expect(n == 1, f"changed value tick should insert 1, got {n}")
expect(len(jaw_curve.keyframe_points) == 2, "JawOpen now has 2 keys")

# Bone rotation: change pose, tick
import math as _m
arma.pose.bones["LeftEye"].rotation_euler[1] = _m.radians(10)
n = kf.tick(frame=13)
expect(n == 1, f"bone change tick should insert 1, got {n}")
left_y_curve = _find_fcurve(arm_action, 
    'pose.bones["LeftEye"].rotation_euler', 1)
expect(left_y_curve is not None and len(left_y_curve.keyframe_points) == 2,
       "LeftEye rot_euler[1] should have 2 keys (anchor + change)")

# stop() force-anchors a final key on every channel
kf.stop(frame=20)
expect(len(jaw_curve.keyframe_points) >= 3, "stop adds final key on JawOpen")

# Pre-existing curve on a non-driven path is preserved across a fresh start()
extra_kb = mesh.shape_key_add(name="ManualKey")
extra_kb.value = 0.7
extra_kb.keyframe_insert(data_path="value", frame=5)
extra_curve = _find_fcurve(sk_action, 'key_blocks["ManualKey"].value', 0)
expect(extra_curve is not None and len(extra_curve.keyframe_points) >= 1,
       "manual key inserted")

# A new Keyframer that *does not* know about ManualKey shouldn't touch it.
kf2 = kf_mod.Keyframer(
    mesh=mesh, armature=arma,
    left_bone="LeftEye", right_bone="RightEye",
)
# Force kf2 to skip ManualKey by hacking its driveable list — same as
# the real bridge would: only drive the *known* shape keys we provide.
# (In production, every shape key gets driven, but we intentionally
# verify the clear-fcurves code only nukes paths in our list.)
kf2._drive_able_shape_key_names = lambda: ["JawOpen", "MouthSmileLeft"]
kf2.start(frame=30)
post = _find_fcurve(sk_action, 'key_blocks["ManualKey"].value', 0)
expect(post is not None,
       "ManualKey curve should be preserved when it isn't in driven list")

bpy.data.objects.remove(mesh, do_unlink=True)
bpy.data.objects.remove(arma, do_unlink=True)
print("[smoke] phase5b OK")


# ============================================================
# Phase 5a: state machine + Phase 5c: end-to-end OSC -> keyframes
# ============================================================
print("[smoke] phase5a/c session state machine + e2e capture...")
mesh = make_mesh_with_keys(
    "Phase5Avatar", ["JawOpen", "MouthSmileLeft", "EyeOpenLeft", "EyeOpenRight"]
)
arma = make_eye_armature()

s = bpy.context.scene.vrcft
s.head_mesh = mesh
s.eye_armature = arma
s.left_eye_bone = "LeftEye"
s.right_eye_bone = "RightEye"
s.osc_port = free_port()
s.smoothing = 1.0
s.rounding = 0.0
s.avatar_status = ""

# Validate dropdown items
expect(s.mode in {'TEST', 'CAPTURE'}, "mode default")
expect(s.active_mode == 'IDLE', "active_mode default IDLE")

# Idle -> Test
s.mode = 'TEST'
res = bpy.ops.vrcft.start_session()
expect('FINISHED' in res, "start_session in TEST should finish")
expect(s.is_running, "is_running True after start")
expect(s.active_mode == 'TEST', "active_mode = TEST")
b = osc_bridge.get_bridge()
expect(b.keyframer is None, "no keyframer in TEST mode")
bpy.ops.vrcft.stop_session()
expect(not s.is_running, "stopped")
expect(s.active_mode == 'IDLE', "active_mode -> IDLE on stop")

# Idle -> Capture (engages keyframer)
bpy.context.scene.frame_set(7)
s.mode = 'CAPTURE'
res = bpy.ops.vrcft.start_session()
expect('FINISHED' in res, "start_session CAPTURE should finish")
expect(s.is_running and s.active_mode == 'CAPTURE',
       "active_mode = CAPTURE")
expect(b.keyframer is not None, "keyframer engaged in CAPTURE mode")
expect(b.keyframer.start_frame == 7,
       f"keyframer should start at scene frame 7, got {b.keyframer.start_frame}")

# Drive a sequence of OSC events; tick after each so frame advances.
client = SimpleUDPClient("127.0.0.1", s.osc_port)
sequence = [
    ("JawOpen", 0.5),
    ("JawOpen", 0.8),
    ("EyeX", 1.0),
    ("EyeY", -0.5),
]
for addr, val in sequence:
    client.send_message(f"/avatar/parameters/v2/{addr}", val)
    expect(wait_for(lambda: b.queue.qsize() >= 1, 2.0), f"queued {addr}")
    osc_bridge.tick()
    time.sleep(0.01)

end_frame = bpy.context.scene.frame_current
expect(end_frame > 7,
       f"scene frame should advance during capture, got {end_frame}")

# Stop session: keyframer.stop must be called and frame stops advancing.
bpy.ops.vrcft.stop_session()
expect(b.keyframer is None, "keyframer cleared on stop")
expect(s.active_mode == 'IDLE', "active_mode = IDLE after stop")
final_frame = bpy.context.scene.frame_current
# After stop, ticking should NOT advance (timer is gone, but make sure
# explicit tick is a no-op).
osc_bridge.tick()
expect(bpy.context.scene.frame_current == final_frame,
       "frame should not advance after stop")

# Verify recorded keyframes
sk_action = mesh.data.shape_keys.animation_data.action
arm_action = arma.animation_data.action
expect(sk_action is not None and sk_action.name.startswith("VRCFT_Capture_"),
       "shape-key capture action exists")
jaw = _find_fcurve(sk_action, 'key_blocks["JawOpen"].value', 0)
expect(jaw is not None, "JawOpen curve recorded")
expect(len(jaw.keyframe_points) >= 2,
       f"JawOpen should have anchor + change keys, got {len(jaw.keyframe_points)}")
# Sparse: MouthSmileLeft was never driven; should only have the
# anchor + final stop key (= 2 keys), not one per tick.
ms = _find_fcurve(sk_action, 'key_blocks["MouthSmileLeft"].value', 0)
expect(ms is not None and len(ms.keyframe_points) <= 3,
       f"undriven MouthSmileLeft should be sparse, got {len(ms.keyframe_points)}")

eye_y = _find_fcurve(arm_action, 
    'pose.bones["LeftEye"].rotation_euler', 1)
expect(eye_y is not None, "LeftEye rotation_euler[1] curve recorded")
expect(len(eye_y.keyframe_points) >= 2,
       f"LeftEye yaw should have keys, got {len(eye_y.keyframe_points)}")

# Re-entering CAPTURE clears the existing driven f-curves (start=10)
bpy.context.scene.frame_set(10)
res = bpy.ops.vrcft.start_session()
expect('FINISHED' in res, "second capture start")
jaw2 = _find_fcurve(sk_action, 'key_blocks["JawOpen"].value', 0)
expect(jaw2 is not None and len(jaw2.keyframe_points) == 1,
       f"second start should clear+anchor JawOpen, got {len(jaw2.keyframe_points)}")
bpy.ops.vrcft.stop_session()

blender_vrcft.unregister()
print("[smoke] PASS")
