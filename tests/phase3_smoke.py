"""Phase 3 smoke test.

Exercises the live-parameters CollectionProperty: items are created on
first sighting, updated thereafter, the matched flag tracks whether the
mesh has a corresponding shape key, the UIList filter+sort produces a
sane order, and Clear wipes the list.
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _addon  # noqa: E402,F401

import bpy  # noqa: E402

import blender_vrcft  # noqa: E402
from blender_vrcft import osc_bridge  # noqa: E402
from blender_vrcft.ui_list import compute_filter_and_order  # noqa: E402
from pythonosc.udp_client import SimpleUDPClient  # noqa: E402

BITFLAG = 1 << 30


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

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
cube.shape_key_add(name="Basis")
cube.shape_key_add(name="JawOpen")

s = bpy.context.scene.vrcft
s.head_mesh = cube
s.osc_port = free_port()
s.smoothing = 1.0

bpy.ops.vrcft.start_test()

client = SimpleUDPClient("127.0.0.1", s.osc_port)
client.send_message("/avatar/parameters/JawOpen", 0.6)         # matched
client.send_message("/avatar/parameters/MouthClosed", 0.4)     # unmatched
client.send_message("/avatar/parameters/v2/JawOpen", 0.8)      # matched, v2 stripped

bridge = osc_bridge.get_bridge()
expect(
    wait_for(lambda: bridge.queue.qsize() >= 3, 2.0),
    "OSC messages did not arrive",
)
osc_bridge.tick()

print(f"[smoke] params: {[(p.name, p.value, p.matched) for p in s.params]}")
expect(len(s.params) == 2, f"expected 2 params, got {len(s.params)}")

jaw = s.params.get("JawOpen")
mouth = s.params.get("MouthClosed")
expect(jaw is not None, "JawOpen item missing")
expect(mouth is not None, "MouthClosed item missing")
expect(jaw.matched, "JawOpen should be matched")
expect(not mouth.matched, "MouthClosed should be unmatched")
expect(abs(jaw.value - 0.8) < 1e-3, f"JawOpen value wrong: {jaw.value}")
expect(abs(mouth.value - 0.4) < 1e-3, f"MouthClosed value wrong: {mouth.value}")

# Second sighting updates the existing item, doesn't add a new one.
client.send_message("/avatar/parameters/JawOpen", 0.3)
expect(wait_for(lambda: bridge.queue.qsize() >= 1, 1.0), "second JawOpen lost")
osc_bridge.tick()
expect(len(s.params) == 2, f"item count grew unexpectedly: {len(s.params)}")
expect(abs(s.params.get("JawOpen").value - 0.3) < 1e-3, "JawOpen did not update in place")

# Default is insertion order — empty order_map tells Blender to use it.
items = list(s.params)
flt_flags, order_map = compute_filter_and_order(
    items, sort_alphabetical=False, show_unmatched=True, filter_name="", bitflag=BITFLAG
)
expect(len(flt_flags) == 2, "filter flags length mismatch")
expect(
    order_map == [],
    f"default sort should return empty order_map (insertion order), got {order_map}",
)

# Hide unmatched.
mouth_idx = next(i for i, it in enumerate(items) if it.name == "MouthClosed")
flt_flags, _ = compute_filter_and_order(
    items, sort_alphabetical=False, show_unmatched=False, filter_name="", bitflag=BITFLAG
)
expect(
    flt_flags[mouth_idx] & BITFLAG == 0,
    "MouthClosed should be filtered out when show_unmatched=False",
)

# Filter by name.
flt_flags, _ = compute_filter_and_order(
    items, sort_alphabetical=False, show_unmatched=True, filter_name="jaw", bitflag=BITFLAG
)
expect(
    flt_flags[mouth_idx] & BITFLAG == 0,
    "MouthClosed should be filtered out by name 'jaw'",
)

# Alphabetical sort -> explicit ordering map.
flt_flags, order_map = compute_filter_and_order(
    items, sort_alphabetical=True, show_unmatched=True, filter_name="", bitflag=BITFLAG
)
expect(len(order_map) == 2, "alphabetical mode should produce a non-empty order map")
ranked = [None, None]
for i, pos in enumerate(order_map):
    ranked[pos] = items[i].name
print(f"[smoke] alphabetical order: {ranked}")
expect(ranked == sorted(ranked), f"alphabetical sort wrong: {ranked}")

# Clear.
bpy.ops.vrcft.clear_params()
expect(len(s.params) == 0, "clear should empty params")

bpy.ops.vrcft.stop_test()
blender_vrcft.unregister()

print("[smoke] PASS")
