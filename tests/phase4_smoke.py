"""Phase 4 smoke test: bipolar param splitting, reset-on-stop, and avatar JSON.

    "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" \
        --background --factory-startup --python tests/phase4_smoke.py
"""
import json
import os
import socket
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "blender_vrcft", "vendor"))

import bpy  # noqa: E402

import blender_vrcft  # noqa: E402
from blender_vrcft import avatar_json, osc_bridge  # noqa: E402
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


# ---- avatar_json pure-function checks ----
print("[smoke] avatar_json checks...")
id_a = avatar_json.stable_avatar_id("/tmp/foo.blend")
id_b = avatar_json.stable_avatar_id("/tmp/foo.blend")
id_c = avatar_json.stable_avatar_id("/tmp/bar.blend")
expect(id_a == id_b, "stable_avatar_id should be deterministic")
expect(id_a != id_c, "different .blend paths should produce different ids")
expect(id_a.startswith(avatar_json.ID_PREFIX), "id should be prefixed")

expect(
    avatar_json.display_name("") == "Blender VRCFT - Untitled",
    "empty path should yield Untitled name",
)
expect(
    avatar_json.display_name("/x/y/Cool Rig.blend") == "Blender VRCFT - Cool Rig",
    "display_name should strip directory and .blend",
)

payload = avatar_json.build_outer_json(
    "avtr_test", "Blender VRCFT - Cool Rig", ["Basis", "JawOpen", "JawX", "MouthClosed"]
)
expect(payload["id"] == "avtr_test", "id field wrong")
expect(payload["name"].startswith("Blender VRCFT"), "name field wrong")
names = [p["name"] for p in payload["parameters"]]
# The avatar shape keys (minus Basis) come first, then the UE set.
expect(names[0] == "JawOpen", f"first param should be JawOpen shape key, got {names[0]}")
expect("JawOpen" in names, "JawOpen param missing")
# v2 names are emitted with a v2_ prefix in the parameter ``name`` field
# but the ``address`` carries the /v2/ path so VRCFT routes correctly.
v2_names = [p for p in payload["parameters"] if p["name"].startswith("v2_")]
expect(len(v2_names) >= 80, f"expected ~86 v2 params, got {len(v2_names)}")
v2_jaw = next(p for p in payload["parameters"] if p["name"] == "v2_JawX")
expect(
    v2_jaw["input"]["address"] == "/avatar/parameters/v2/JawX",
    f"v2/JawX address wrong: {v2_jaw['input']['address']}",
)
# Legacy simplified param
legacy = [p for p in payload["parameters"] if p["name"] == "SmileFrown"]
expect(legacy, "SmileFrown legacy param should be declared")
expect(
    legacy[0]["input"]["address"] == "/avatar/parameters/SmileFrown",
    "SmileFrown should not have a v2/ prefix",
)
expect(
    payload["parameters"][0]["input"]["type"] == "Float",
    "input type wrong",
)
# Should be valid JSON (no surprises with escapes etc.)
json.dumps(payload)


# ---- bipolar resolve_targets unit checks ----
print("[smoke] resolve_targets unit checks...")
sk = {"JawOpen": None, "JawLeft": None, "JawRight": None,
      "EyeLookInLeft": None, "EyeLookOutLeft": None,
      "EyeOpenLeft": None, "EyeWideLeft": None,
      "MouthUpperRight": None}

# Direct match wins.
direct = osc_bridge.resolve_targets("JawOpen", sk)
expect(direct == [("JawOpen", osc_bridge._identity)], f"direct match wrong: {direct}")

# JawX -> JawRight (positive) / JawLeft (negative).
jaw = osc_bridge.resolve_targets("JawX", sk)
expect(
    [t[0] for t in jaw] == ["JawRight", "JawLeft"],
    f"JawX targets wrong: {[t[0] for t in jaw]}",
)
expect(abs(jaw[0][1](0.6) - 0.6) < 1e-6, "positive arm wrong")
expect(abs(jaw[1][1](-0.6) - 0.6) < 1e-6, "negative arm wrong")
expect(abs(jaw[0][1](-0.6)) < 1e-6, "positive arm should clamp on negative input")
expect(abs(jaw[1][1](0.6)) < 1e-6, "negative arm should clamp on positive input")

# MouthUpperX with only the Right side present.
mu = osc_bridge.resolve_targets("MouthUpperX", sk)
expect(
    [t[0] for t in mu] == ["MouthUpperRight"],
    f"MouthUpperX with only Right shape: {[t[0] for t in mu]}",
)

# EyeLeftX -> in (positive) / out (negative).
el = osc_bridge.resolve_targets("EyeLeftX", sk)
expect(
    [t[0] for t in el] == ["EyeLookInLeft", "EyeLookOutLeft"],
    f"EyeLeftX targets wrong: {[t[0] for t in el]}",
)

# EyeLid: 0..0.75 close, 0.75..1 widen. Avatars usually have EyeClosed*
# (UE base) and EyeWide*. Some have EyeOpen* (inverse of close).
sk_close = {"EyeClosedLeft": None, "EyeClosedRight": None,
            "EyeWideLeft": None, "EyeWideRight": None}
lid_c = osc_bridge.resolve_targets("EyeLid", sk_close)
names_c = [t[0] for t in lid_c]
expect(set(names_c) == {"EyeClosedLeft", "EyeClosedRight",
                         "EyeWideLeft", "EyeWideRight"},
       f"EyeLid -> EyeClosed*/EyeWide*: {names_c}")

# Closed at v=0 should be 1 (fully closed).
closed_fn = next(t[1] for t in lid_c if t[0] == "EyeClosedLeft")
expect(abs(closed_fn(0.0) - 1.0) < 1e-6, f"closed(0)={closed_fn(0.0)} should be 1")
expect(abs(closed_fn(0.375) - 0.5) < 1e-6, f"closed(0.375)={closed_fn(0.375)}")
expect(abs(closed_fn(0.75)) < 1e-6, f"closed(0.75)={closed_fn(0.75)} should be 0")
expect(abs(closed_fn(1.0)) < 1e-6, f"closed(1.0)={closed_fn(1.0)} should be 0")

# EyeOpen branch (legacy / alternative).
sk_open = {"EyeOpenLeft": None, "EyeWideLeft": None}
lid_o = osc_bridge.resolve_targets("EyeLid", sk_open)
names_o = [t[0] for t in lid_o]
expect(set(names_o) == {"EyeOpenLeft", "EyeWideLeft"}, f"EyeOpen path: {names_o}")
open_fn = next(t[1] for t in lid_o if t[0] == "EyeOpenLeft")
expect(abs(open_fn(0.0)) < 1e-6, "open at 0 should be 0")
expect(abs(open_fn(0.375) - 0.5) < 1e-6, f"open at half threshold: {open_fn(0.375)}")
expect(abs(open_fn(0.75) - 1.0) < 1e-6, f"open at threshold should saturate: {open_fn(0.75)}")
wide_fn = next(t[1] for t in lid_o if t[0] == "EyeWideLeft")
expect(abs(wide_fn(0.5)) < 1e-6, "wide below threshold should be 0")
expect(abs(wide_fn(0.875) - 0.5) < 1e-6, f"wide at midpoint: {wide_fn(0.875)}")
expect(abs(wide_fn(1.0) - 1.0) < 1e-6, "wide at 1.0 should be 1.0")

# SmileFrown bipolar: positive = corner pull/slant, negative = frown.
sk_smile = {"MouthCornerPullRight": None, "MouthCornerSlantRight": None,
            "MouthFrownRight": None}
sf = osc_bridge.resolve_targets("SmileFrownRight", sk_smile)
sf_names = sorted(t[0] for t in sf)
expect(sf_names == ["MouthCornerPullRight", "MouthCornerSlantRight", "MouthFrownRight"],
       f"SmileFrownRight targets: {sf_names}")

# Unipolar composite: MouthOpen fans to upper-up + lower-down.
sk_mo = {"MouthUpperUpRight": None, "MouthUpperUpLeft": None,
         "MouthLowerDownRight": None, "MouthLowerDownLeft": None}
mo = osc_bridge.resolve_targets("MouthOpen", sk_mo)
mo_names = sorted(t[0] for t in mo)
expect(mo_names == sorted(sk_mo.keys()), f"MouthOpen targets: {mo_names}")

# JawClench1 -> JawClench legacy alias.
jc = osc_bridge.resolve_targets("JawClench1", {"JawClench": None})
expect(jc and jc[0][0] == "JawClench", f"JawClench1 alias: {jc}")


# ---- end-to-end: bipolar OSC drives the right shape keys ----
print("[smoke] registering add-on for end-to-end...")
blender_vrcft.register()

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
cube.shape_key_add(name="Basis")
for n in ("JawOpen", "JawLeft", "JawRight",
          "MouthUpperLeft", "MouthUpperRight",
          "EyeLookInLeft", "EyeLookOutLeft",
          "EyeOpenLeft", "EyeOpenRight", "EyeWideLeft", "EyeWideRight"):
    cube.shape_key_add(name=n)

s = bpy.context.scene.vrcft
s.head_mesh = cube
s.osc_port = free_port()
s.smoothing = 1.0  # snap

bpy.ops.vrcft.start_test()

client = SimpleUDPClient("127.0.0.1", s.osc_port)
client.send_message("/avatar/parameters/v2/JawX", -0.7)         # -> JawLeft 0.7
client.send_message("/avatar/parameters/v2/MouthUpperX", 0.4)   # -> MouthUpperRight 0.4
client.send_message("/avatar/parameters/v2/EyeLeftX", 0.6)      # -> EyeLookInLeft 0.6
client.send_message("/avatar/parameters/v2/EyeLid", 0.9)        # -> EyeOpen* 1.0, EyeWide* 0.6
client.send_message("/avatar/parameters/JawOpen", 0.55)         # direct match

bridge = osc_bridge.get_bridge()
expect(wait_for(lambda: bridge.queue.qsize() >= 5, 2.0), "OSC msgs did not arrive")
osc_bridge.tick()

kb = cube.data.shape_keys.key_blocks
print("[smoke] post-tick values:")
for n in ("JawOpen", "JawLeft", "JawRight", "MouthUpperLeft", "MouthUpperRight",
          "EyeLookInLeft", "EyeLookOutLeft",
          "EyeOpenLeft", "EyeOpenRight", "EyeWideLeft", "EyeWideRight"):
    print(f"  {n} = {kb[n].value:.3f}")

expect(abs(kb["JawOpen"].value - 0.55) < 1e-3, f"JawOpen direct: {kb['JawOpen'].value}")
expect(abs(kb["JawLeft"].value - 0.7) < 1e-3, f"JawLeft from -JawX: {kb['JawLeft'].value}")
expect(abs(kb["JawRight"].value) < 1e-3, f"JawRight should be 0: {kb['JawRight'].value}")
expect(abs(kb["MouthUpperRight"].value - 0.4) < 1e-3, "MouthUpperRight wrong")
expect(abs(kb["MouthUpperLeft"].value) < 1e-3, "MouthUpperLeft should be 0")
expect(abs(kb["EyeLookInLeft"].value - 0.6) < 1e-3, "EyeLookInLeft wrong")
expect(abs(kb["EyeLookOutLeft"].value) < 1e-3, "EyeLookOutLeft should be 0")
# EyeLid 0.9: open saturates to 1.0, wide = (0.9 - 0.75) / 0.25 = 0.6
expect(abs(kb["EyeOpenLeft"].value - 1.0) < 1e-3, f"EyeOpenLeft: {kb['EyeOpenLeft'].value}")
expect(abs(kb["EyeOpenRight"].value - 1.0) < 1e-3, f"EyeOpenRight: {kb['EyeOpenRight'].value}")
expect(abs(kb["EyeWideLeft"].value - 0.6) < 1e-3, f"EyeWideLeft: {kb['EyeWideLeft'].value}")
expect(abs(kb["EyeWideRight"].value - 0.6) < 1e-3, f"EyeWideRight: {kb['EyeWideRight'].value}")

# touched_keys should include every shape key we just drove.
expected_touched = {
    "JawOpen", "JawLeft", "MouthUpperRight",
    "EyeLookInLeft",
    "EyeOpenLeft", "EyeOpenRight", "EyeWideLeft", "EyeWideRight",
}
missing = expected_touched - bridge.touched_keys
expect(not missing, f"touched_keys missing: {missing}")

# JawX live row should be matched (because at least one split target landed).
jaw_x_item = s.params.get("JawX")
expect(jaw_x_item is not None, "JawX param row missing")
expect(jaw_x_item.matched, "JawX should be marked matched (split landed)")

# ---- reset on stop ----
print("[smoke] stop_test should zero touched shape keys...")
bpy.ops.vrcft.stop_test()

for n in expected_touched:
    expect(
        abs(kb[n].value) < 1e-6,
        f"{n} should be 0 after stop_test, got {kb[n].value}",
    )
expect(len(s.params) == 0, "params list should be cleared on stop")
expect(len(bridge.touched_keys) == 0, "touched_keys should be cleared on stop")

# ---- partial smoothing: shape key must converge across multiple ticks
# even when VRCFT only sends a value once and then goes silent ----
print("[smoke] smoothing convergence check...")
tongue_block = cube.shape_key_add(name="TongueOut")
tongue_block.value = 0.0  # shape_key_add() creates with value=1.0 in Blender 5
s.smoothing = 0.3  # partial — typical user value
bpy.ops.vrcft.start_test()

client = SimpleUDPClient("127.0.0.1", s.osc_port)
# Pretend tongue went out then was retracted; only the final 0 keeps
# arriving once, then VRCFT throttles silent.
client.send_message("/avatar/parameters/v2/TongueOut", 1.0)
bridge = osc_bridge.get_bridge()
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "first tongue msg")
osc_bridge.tick()
# After one smoothing step toward 1.0 from 0.0: 0 + (1-0)*0.3 = 0.3
expect(0.25 < kb["TongueOut"].value < 0.35,
       f"first tick should smooth toward 1.0, got {kb['TongueOut'].value}")

# Run several ticks with no new OSC — should converge toward 1.0.
for _ in range(60):
    osc_bridge.tick()
expect(kb["TongueOut"].value > 0.95,
       f"should converge to ~1.0, got {kb['TongueOut'].value}")

# Now send a single 0 and let it converge back. This is the actual bug:
# previously the shape key would stick at ~0.7 because only one smoothing
# step fired before VRCFT went silent.
client.send_message("/avatar/parameters/v2/TongueOut", 0.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "retract tongue msg")
osc_bridge.tick()
# One step: 1.0 + (0-1)*0.3 = 0.7
expect(0.65 < kb["TongueOut"].value < 0.75,
       f"first retract step should be ~0.7, got {kb['TongueOut'].value}")

for _ in range(60):
    osc_bridge.tick()
expect(kb["TongueOut"].value < 0.05,
       f"should converge to ~0.0 after retract, got {kb['TongueOut'].value}")

bpy.ops.vrcft.stop_test()

# ---- rounding deadband: target only updates on big-enough raw changes,
# but smoothing continues normally toward the held target ----
print("[smoke] rounding deadband check...")
tongue_block.value = 0.0
s.smoothing = 1.0  # snap so we isolate deadband behavior
s.rounding = 0.1
bpy.ops.vrcft.start_test()
client = SimpleUDPClient("127.0.0.1", s.osc_port)

# First value commits (no prior value to compare against).
client.send_message("/avatar/parameters/v2/TongueOut", 0.50)
bridge = osc_bridge.get_bridge()
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "first deadband msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.50) < 1e-3,
       f"first value commits, got {kb['TongueOut'].value}")

# Tiny jitter inside the deadband: target must NOT change. Note value
# is exact (no quantization to 0.6 bucket).
client.send_message("/avatar/parameters/v2/TongueOut", 0.55)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "jitter msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.50) < 1e-3,
       f"jitter inside deadband must not move shape key, got {kb['TongueOut'].value}")

# Hovering at the same edge — jittering between 0.55 and 0.59 — also
# stays put because each delta from committed (0.50) is <= 0.10.
for v in (0.55, 0.58, 0.59, 0.55):
    client.send_message("/avatar/parameters/v2/TongueOut", v)
    expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), f"hover msg {v}")
    osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.50) < 1e-3,
       f"edge-hover must not jitter, got {kb['TongueOut'].value}")

# Move past the deadband: target updates to the new exact raw value.
client.send_message("/avatar/parameters/v2/TongueOut", 0.72)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "past-deadband msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.72) < 1e-3,
       f"past deadband should commit exact 0.72, got {kb['TongueOut'].value}")

# Smoothing still applies between committed targets (no quantized output).
s.smoothing = 0.5
s.rounding = 0.1
tongue_block.value = 0.0
bridge.committed_values.pop("TongueOut", None)
bridge.latest_values.pop("TongueOut", None)
client.send_message("/avatar/parameters/v2/TongueOut", 0.80)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "smoothing msg")
osc_bridge.tick()
# After one smoothing step from 0 toward 0.80 with alpha=0.5: 0.40
expect(0.35 < kb["TongueOut"].value < 0.45,
       f"first smoothing step toward 0.80 should be ~0.4 (not quantized), got {kb['TongueOut'].value}")
for _ in range(60):
    osc_bridge.tick()
# Should converge to the exact committed value, NOT a 0.1 bucket.
expect(abs(kb["TongueOut"].value - 0.80) < 1e-3,
       f"should converge to exact 0.80 (not rounded), got {kb['TongueOut'].value}")

bpy.ops.vrcft.stop_test()

# ---- saturation snap: raw values at 0 or 1 always commit even inside
# the deadband, so shape keys can fully open/close ----
print("[smoke] saturation snap check...")
tongue_block.value = 0.0
s.smoothing = 1.0
s.rounding = 0.5  # huge deadband to prove saturation overrides it
bpy.ops.vrcft.start_test()
client = SimpleUDPClient("127.0.0.1", s.osc_port)
client.send_message("/avatar/parameters/v2/TongueOut", 0.6)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "sat init msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.6) < 1e-3, f"init: {kb['TongueOut'].value}")
# 0.7 is well within deadband of 0.6 — would normally hold.
client.send_message("/avatar/parameters/v2/TongueOut", 0.7)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "sat hold msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 0.6) < 1e-3,
       f"non-saturation should hold: {kb['TongueOut'].value}")
# 1.0 saturation must commit immediately.
client.send_message("/avatar/parameters/v2/TongueOut", 1.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "sat 1 msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value - 1.0) < 1e-3,
       f"raw=1 must snap regardless of deadband: {kb['TongueOut'].value}")
# 0.0 saturation must commit immediately too.
client.send_message("/avatar/parameters/v2/TongueOut", 0.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "sat 0 msg")
osc_bridge.tick()
expect(abs(kb["TongueOut"].value) < 1e-3,
       f"raw=0 must snap regardless of deadband: {kb['TongueOut'].value}")

bpy.ops.vrcft.stop_test()
s.rounding = 0.0  # leave defaults clean for next runs

# ---- eye-bone driver: gaze maps to bone pitch/yaw, clamped by ranges ----
print("[smoke] eye-bone driver check...")
import math as _math
arma_data = bpy.data.armatures.new("VRCFT_TestArm")
arma = bpy.data.objects.new("VRCFT_TestArm", arma_data)
bpy.context.collection.objects.link(arma)
bpy.context.view_layer.objects.active = arma
bpy.ops.object.mode_set(mode='EDIT')
for bn, x in (("LeftEye", -0.05), ("RightEye", 0.05)):
    eb = arma_data.edit_bones.new(bn)
    eb.head = (x, 0.0, 1.7)
    eb.tail = (x, 0.1, 1.7)
bpy.ops.object.mode_set(mode='OBJECT')

s.eye_armature = arma
s.left_eye_bone = "LeftEye"
s.right_eye_bone = "RightEye"
s.eye_range_up = _math.radians(15)
s.eye_range_down = _math.radians(15)
s.eye_range_left = _math.radians(15)
s.eye_range_right = _math.radians(15)
s.smoothing = 1.0

bpy.ops.vrcft.start_test()
client = SimpleUDPClient("127.0.0.1", s.osc_port)
# Look full right + full up
client.send_message("/avatar/parameters/v2/EyeX", 1.0)
client.send_message("/avatar/parameters/v2/EyeY", 1.0)
bridge = osc_bridge.get_bridge()
expect(wait_for(lambda: bridge.queue.qsize() >= 2, 2.0), "eye msgs")
osc_bridge.tick()

from blender_vrcft import eye_bones as eb_mod
left_pb = arma.pose.bones["LeftEye"]
right_pb = arma.pose.bones["RightEye"]
lx, ly, _ = eb_mod._read_euler_xyz(left_pb)
expect(abs(lx - (-_math.radians(15))) < 1e-4,
       f"left pitch (-X for tail-up) should be -15deg at EyeY=1, got {_math.degrees(lx):.2f}")
expect(abs(ly - (-_math.radians(15))) < 1e-4,
       f"left yaw (-Y for tail-up) should be -15deg at EyeX=1, got {_math.degrees(ly):.2f}")

# Per-eye override: streaming EyeRightX = 0 should isolate right eye.
client.send_message("/avatar/parameters/v2/EyeRightX", 0.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "per-eye override msg")
osc_bridge.tick()
_, ry, _ = eb_mod._read_euler_xyz(right_pb)
expect(abs(ry) < 1e-4,
       f"per-eye override: right yaw should be 0, got {_math.degrees(ry):.4f}")
# Left still at +15 yaw (driven by combined EyeX).
_, ly2, _ = eb_mod._read_euler_xyz(left_pb)
expect(abs(ly2 - (-_math.radians(15))) < 1e-4,
       f"left yaw still from combined: got {_math.degrees(ly2):.2f}")

# Range clamping: ranges in radians directly, not extrapolated.
# Look full down with range_down=30deg.
s.eye_range_down = _math.radians(30)
client.send_message("/avatar/parameters/v2/EyeY", -1.0)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 2.0), "down msg")
osc_bridge.tick()
lx2, _, _ = eb_mod._read_euler_xyz(left_pb)
expect(abs(lx2 - _math.radians(30)) < 1e-4,
       f"left pitch (-X*-1=+X) at EyeY=-1, range_down=30: got {_math.degrees(lx2):.2f}")

# Stop must reset eye bones.
bpy.ops.vrcft.stop_test()
lx3, ly3, _ = eb_mod._read_euler_xyz(left_pb)
rx3, ry3, _ = eb_mod._read_euler_xyz(right_pb)
expect(abs(lx3) < 1e-5 and abs(ly3) < 1e-5,
       f"left bone should be identity after stop: ({lx3}, {ly3})")
expect(abs(rx3) < 1e-5 and abs(ry3) < 1e-5,
       f"right bone should be identity after stop: ({rx3}, {ry3})")

blender_vrcft.unregister()
print("[smoke] PASS")
