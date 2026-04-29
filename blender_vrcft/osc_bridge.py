"""Bridge between python-osc (background thread) and Blender's main thread.

Receives OSC messages on a UDP port, pushes them onto a thread-safe queue,
and exposes a `tick()` callable that the main thread drains and applies
to shape keys. Capture writing is done from the OSC thread (file I/O is
fine off the main thread; only `bpy` is not).
"""
import os
import queue
import sys
import threading
import time

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from pythonosc.dispatcher import Dispatcher  # noqa: E402
from pythonosc.osc_server import ThreadingOSCUDPServer  # noqa: E402

QUEUE_MAX = 4096


# Bipolar VRCFT v2 parameters: positive value drives the first target tuple,
# negative value drives the second. Each target uses ``abs(value)``. Multiple
# targets per side mean every existing shape key in that tuple is driven by
# the same value (left+right pairs, brow up/down combos, etc.).
BIPOLAR_MAP = {
    # Jaw
    "JawX":        (("JawRight",),    ("JawLeft",)),
    "JawZ":        (("JawForward",),  ("JawBackward",)),
    # Mouth shift (per-lip and combined)
    "MouthUpperX": (("MouthUpperRight",), ("MouthUpperLeft",)),
    "MouthLowerX": (("MouthLowerRight",), ("MouthLowerLeft",)),
    "MouthX":      (("MouthUpperRight", "MouthLowerRight"),
                    ("MouthUpperLeft",  "MouthLowerLeft")),
    # Eye gaze (per-eye)
    "EyeLeftX":    (("EyeLookInLeft",),   ("EyeLookOutLeft",)),
    "EyeRightX":   (("EyeLookOutRight",), ("EyeLookInRight",)),
    "EyeLeftY":    (("EyeLookUpLeft",),   ("EyeLookDownLeft",)),
    "EyeRightY":   (("EyeLookUpRight",),  ("EyeLookDownRight",)),
    # Eye gaze (combined / simplified)
    "EyeX":        (("EyeLookOutRight", "EyeLookInLeft"),
                    ("EyeLookOutLeft",  "EyeLookInRight")),
    "EyeY":        (("EyeLookUpRight",   "EyeLookUpLeft"),
                    ("EyeLookDownRight", "EyeLookDownLeft")),
    # Cheek puff vs suck
    "CheekPuffSuckRight": (("CheekPuffRight",), ("CheekSuckRight",)),
    "CheekPuffSuckLeft":  (("CheekPuffLeft",),  ("CheekSuckLeft",)),
    "CheekPuffSuck":      (("CheekPuffRight", "CheekPuffLeft"),
                           ("CheekSuckRight", "CheekSuckLeft")),
    # Brow up / down (simplified)
    "BrowExpressionRight": (("BrowOuterUpRight", "BrowInnerUpRight"),
                            ("BrowLowererRight", "BrowPinchRight")),
    "BrowExpressionLeft":  (("BrowOuterUpLeft",  "BrowInnerUpLeft"),
                            ("BrowLowererLeft",  "BrowPinchLeft")),
    "BrowExpression": (
        ("BrowOuterUpRight", "BrowInnerUpRight", "BrowOuterUpLeft", "BrowInnerUpLeft"),
        ("BrowLowererRight", "BrowPinchRight",   "BrowLowererLeft", "BrowPinchLeft"),
    ),
    # Smile / frown / sad (simplified)
    "SmileFrownRight": (("MouthCornerPullRight", "MouthCornerSlantRight"),
                        ("MouthFrownRight",)),
    "SmileFrownLeft":  (("MouthCornerPullLeft",  "MouthCornerSlantLeft"),
                        ("MouthFrownLeft",)),
    "SmileFrown": (
        ("MouthCornerPullRight", "MouthCornerSlantRight",
         "MouthCornerPullLeft",  "MouthCornerSlantLeft"),
        ("MouthFrownRight", "MouthFrownLeft"),
    ),
    "SmileSadRight": (("MouthCornerPullRight", "MouthCornerSlantRight"),
                      ("MouthFrownRight", "MouthStretchRight")),
    "SmileSadLeft":  (("MouthCornerPullLeft",  "MouthCornerSlantLeft"),
                      ("MouthFrownLeft",  "MouthStretchLeft")),
    "SmileSad": (
        ("MouthCornerPullRight", "MouthCornerSlantRight",
         "MouthCornerPullLeft",  "MouthCornerSlantLeft"),
        ("MouthFrownRight", "MouthFrownLeft",
         "MouthStretchRight", "MouthStretchLeft"),
    ),
    # Tongue
    "TongueX":     (("TongueRight",),     ("TongueLeft",)),
    "TongueY":     (("TongueUp",),        ("TongueDown",)),
    "TongueArchY": (("TongueBendDown",),  ("TongueCurlUp",)),
    "TongueShape": (("TongueSquish",),    ("TongueFlat",)),
}


# Unipolar composites: a single VRCFT parameter drives multiple shape keys
# at the same value. Used when the param itself doesn't appear as a shape
# key on the avatar.
UNIPOLAR_MAP = {
    # Mouth open (simplified)
    "MouthOpen": ("MouthUpperUpRight", "MouthUpperUpLeft",
                  "MouthLowerDownRight", "MouthLowerDownLeft"),
    "MouthUpperUp":   ("MouthUpperUpRight", "MouthUpperUpLeft"),
    "MouthLowerDown": ("MouthLowerDownRight", "MouthLowerDownLeft"),
    # Smile / sad (unipolar simplified)
    "MouthSmileRight": ("MouthCornerPullRight", "MouthCornerSlantRight"),
    "MouthSmileLeft":  ("MouthCornerPullLeft",  "MouthCornerSlantLeft"),
    "MouthSadRight":   ("MouthFrownRight", "MouthStretchRight"),
    "MouthSadLeft":    ("MouthFrownLeft",  "MouthStretchLeft"),
    # Lip simplified
    "LipSuckUpper":   ("LipSuckUpperRight", "LipSuckUpperLeft"),
    "LipSuckLower":   ("LipSuckLowerRight", "LipSuckLowerLeft"),
    "LipSuck":        ("LipSuckUpperRight", "LipSuckUpperLeft",
                       "LipSuckLowerRight", "LipSuckLowerLeft",
                       "LipSuckCornerRight", "LipSuckCornerLeft"),
    "LipFunnelUpper": ("LipFunnelUpperRight", "LipFunnelUpperLeft"),
    "LipFunnelLower": ("LipFunnelLowerRight", "LipFunnelLowerLeft"),
    "LipFunnel":      ("LipFunnelUpperRight", "LipFunnelUpperLeft",
                       "LipFunnelLowerRight", "LipFunnelLowerLeft"),
    "LipPuckerUpper": ("LipPuckerUpperRight", "LipPuckerUpperLeft"),
    "LipPuckerLower": ("LipPuckerLowerRight", "LipPuckerLowerLeft"),
    "LipPucker":      ("LipPuckerUpperRight", "LipPuckerUpperLeft",
                       "LipPuckerLowerRight", "LipPuckerLowerLeft"),
    # Nose / cheek / eye-squint simplified
    "NoseSneer":   ("NoseSneerRight", "NoseSneerLeft"),
    "CheekSquint": ("CheekSquintRight", "CheekSquintLeft"),
    "EyeSquint":   ("EyeSquintRight", "EyeSquintLeft"),
    # Brow simplified (ARKit-style)
    "BrowDownRight": ("BrowLowererRight", "BrowPinchRight"),
    "BrowDownLeft":  ("BrowLowererLeft",  "BrowPinchLeft"),
    "BrowOuterUp":   ("BrowOuterUpRight", "BrowOuterUpLeft"),
    "BrowInnerUp":   ("BrowInnerUpRight", "BrowInnerUpLeft"),
    "BrowUp":        ("BrowOuterUpRight", "BrowInnerUpRight",
                      "BrowOuterUpLeft",  "BrowInnerUpLeft"),
    # VRCFT-suffixed legacy parameter aliases (some emitters add a ``1``
    # to disambiguate from boolean variants).
    "JawClench1":        ("JawClench",),
    "JawMandibleRaise1": ("JawMandibleRaise",),
}


# Composite eyelid parameters. VRCFT semantics:
#   v in [0.0, 0.75]  -> 0 = fully closed, 0.75 = relaxed open
#   v in [0.75, 1.0]  -> 0.75 = relaxed open, 1.0 = widened
# Avatars typically expose either ``EyeClosed*`` (UE base shape, fires when
# v < 0.75) or ``EyeOpen*`` (less common, fires opposite); plus ``EyeWide*``
# for v > 0.75. We drive whichever exist on the mesh.
EYELID_SIDES = {
    "EyeLid":      ("Left", "Right"),
    "EyeLidLeft":  ("Left",),
    "EyeLidRight": ("Right",),
}

EYELID_OPEN_THRESHOLD = 0.75


class OSCBridge:
    def __init__(self):
        self.queue = queue.Queue(maxsize=QUEUE_MAX)
        self.address_prefix = "/avatar/parameters/"
        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._on_any, needs_reply_address=False)
        self.server = None
        self.thread = None
        self._refcount = 0
        self.unmatched = set()
        self.dropped = 0
        self.capture_writer = None  # CaptureWriter or None
        # Names of shape keys we have written to during the current Test
        # session. Used so Stop Test can zero them back out.
        self.touched_keys = set()
        # Most-recent raw value per canonical parameter name. Used so
        # tick() can keep advancing partial-smoothing toward the latest
        # target on every frame, even when VRCFT throttles steady-state
        # updates and stops emitting (Quest Pro does this aggressively
        # for the tongue family — without this the shape key gets stuck
        # part-way through its smoothing fade).
        self.latest_values = {}
        # Last *committed* raw value per parameter — the value we used to
        # compute the smoothing target. Only updated when the new raw
        # differs from the committed value by more than the Rounding
        # deadband. Smoothing then lerps the shape key toward
        # ``fn(committed_raw)`` even while raw values jitter inside the
        # deadband, eliminating jitter without quantizing the output.
        self.committed_values = {}
        # (armature_name, bone_name) for any pose bone we've rotated
        # this session. Used so Stop Test can return them to identity.
        self.touched_bones = set()
        # Active capture keyframer (Phase 5b/5c). None when not capturing.
        self.keyframer = None
        self._lock = threading.Lock()

    def _on_any(self, address, *args):
        cw = self.capture_writer
        if cw is not None:
            cw.write(address, args)

        if not address.startswith(self.address_prefix):
            return
        if not args:
            return
        try:
            value = float(args[0])
        except (TypeError, ValueError):
            return

        # Push the post-prefix name as-is. Canonicalization (matching against
        # actual shape keys) happens in tick() on the main thread.
        name = address[len(self.address_prefix):]
        try:
            self.queue.put_nowait((name, value))
        except queue.Full:
            self.dropped += 1

    def acquire(self, port):
        """Start the server if not running, increment refcount.

        Returns None on success or an error string on bind failure.
        """
        with self._lock:
            if self._refcount == 0:
                try:
                    self.server = ThreadingOSCUDPServer(
                        ("127.0.0.1", port), self.dispatcher
                    )
                except OSError as e:
                    self.server = None
                    return str(e)
                self.thread = threading.Thread(
                    target=self.server.serve_forever,
                    name="VRCFT-OSC",
                    daemon=True,
                )
                self.thread.start()
            self._refcount += 1
            return None

    def release(self):
        with self._lock:
            if self._refcount == 0:
                return
            self._refcount -= 1
            if self._refcount == 0 and self.server is not None:
                self.server.shutdown()
                self.server.server_close()
                self.thread.join(timeout=2)
                self.server = None
                self.thread = None
                # Drop any queued messages so a fresh start has clean state.
                while True:
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        break

    def force_stop(self):
        """Stop the server unconditionally (used on add-on unregister)."""
        with self._lock:
            self._refcount = 0
            if self.server is not None:
                self.server.shutdown()
                self.server.server_close()
                self.thread.join(timeout=2)
                self.server = None
                self.thread = None
            self.capture_writer = None
            self.touched_keys.clear()
            self.touched_bones.clear()
            self.latest_values.clear()
            self.committed_values.clear()


_bridge = None


def get_bridge():
    global _bridge
    if _bridge is None:
        _bridge = OSCBridge()
    return _bridge


def reset_bridge():
    global _bridge
    if _bridge is not None:
        _bridge.force_stop()
    _bridge = None


def candidate_names(name):
    """Yield successive simplifications of an OSC parameter name.

    'FT/v2/NoseSneer' -> 'FT/v2/NoseSneer', 'v2/NoseSneer', 'NoseSneer'
    'JawOpen'         -> 'JawOpen'
    """
    yield name
    while "/" in name:
        name = name.split("/", 1)[1]
        yield name


def canonical_name(name, sk):
    """Map an incoming OSC parameter name to a shape-key name.

    Tries the full name, then progressively strips leading path segments
    until a shape key matches. If no candidate matches, returns the most-
    stripped form so the unmatched UI row shows a clean name.

    Returns (canonical_name, matched: bool).
    """
    most_stripped = name
    if sk is not None:
        for candidate in candidate_names(name):
            if candidate in sk:
                return candidate, True
            most_stripped = candidate
        return most_stripped, False

    for candidate in candidate_names(name):
        most_stripped = candidate
    return most_stripped, False


def resolve_targets(name, sk):
    """Decide which shape-key names a canonical OSC param drives.

    Returns a list of ``(shape_key_name, computed_value_fn)`` pairs where
    ``computed_value_fn(raw)`` produces the per-target value in [0, 1].

    Matching priority:
      1. If ``name`` is itself a shape key, drive it directly.
      2. If ``name`` is a bipolar composite, fan out to its
         positive/negative split shape keys that exist on the mesh.
      3. If ``name`` is a unipolar composite, fan out to all listed
         shape keys that exist on the mesh.
      4. If ``name`` is an eyelid composite, split into close + open + wide
         contributions using whichever side-suffixed shape keys exist
         (``EyeClosed*``, ``EyeOpen*``, ``EyeWide*``).
      5. Otherwise empty -> caller marks it unmatched.
    """
    if sk is None:
        return []

    if name in sk:
        return [(name, _identity)]

    targets = []

    bp = BIPOLAR_MAP.get(name)
    if bp is not None:
        pos_targets, neg_targets = bp
        for t in pos_targets:
            if t in sk:
                targets.append((t, _positive_part))
        for t in neg_targets:
            if t in sk:
                targets.append((t, _negative_part))
        if targets:
            return targets

    up = UNIPOLAR_MAP.get(name)
    if up is not None:
        for t in up:
            if t in sk:
                targets.append((t, _identity))
        if targets:
            return targets

    sides = EYELID_SIDES.get(name)
    if sides is not None:
        for side in sides:
            closed = "EyeClosed" + side
            opened = "EyeOpen" + side
            wide = "EyeWide" + side
            if closed in sk:
                targets.append((closed, _eyelid_closed))
            if opened in sk:
                targets.append((opened, _eyelid_open))
            if wide in sk:
                targets.append((wide, _eyelid_wide))
        if targets:
            return targets

    return []


def _identity(v):
    return max(0.0, min(1.0, v))


def _positive_part(v):
    return max(0.0, min(1.0, v))


def _negative_part(v):
    return max(0.0, min(1.0, -v))


def _eyelid_closed(v):
    # 0 -> 1 (fully closed), 0.75 -> 0 (relaxed), >0.75 stays 0.
    if v <= 0.0:
        return 1.0
    if v >= EYELID_OPEN_THRESHOLD:
        return 0.0
    return 1.0 - (v / EYELID_OPEN_THRESHOLD)


def _eyelid_open(v):
    # Inverse of EyeClosed: 0 -> 0, 0.75 -> 1, > 0.75 stays at 1 (the
    # widen shape takes over). Used when the avatar exposes EyeOpen*
    # instead of (or in addition to) EyeClosed*.
    if v <= 0.0:
        return 0.0
    if v >= EYELID_OPEN_THRESHOLD:
        return 1.0
    return v / EYELID_OPEN_THRESHOLD


def _eyelid_wide(v):
    if v <= EYELID_OPEN_THRESHOLD:
        return 0.0
    if v >= 1.0:
        return 1.0
    return (v - EYELID_OPEN_THRESHOLD) / (1.0 - EYELID_OPEN_THRESHOLD)


def tick():
    """Drain queued OSC messages and apply them to shape keys.

    Returns the next interval (seconds), or None to stop the timer.
    Called by `bpy.app.timers` on the main thread, and directly from
    smoke tests.
    """
    import bpy  # local import: timer may fire after bpy is fully torn down

    scene = bpy.context.scene
    if scene is None:
        return None
    s = getattr(scene, "vrcft", None)
    if s is None:
        return None
    if not s.is_running:
        return None

    b = get_bridge()

    mesh = s.head_mesh
    sk = (
        mesh.data.shape_keys.key_blocks
        if mesh is not None and mesh.data.shape_keys is not None
        else None
    )

    # Coalesce by canonical name (after prefix stripping) so different
    # variants of the same parameter merge to a single update.
    incoming = {}
    while True:
        try:
            raw_name, value = b.queue.get_nowait()
        except queue.Empty:
            break
        canonical, _matched = canonical_name(raw_name, sk)
        # Even if not directly matched, the canonical (most-stripped) form
        # may be a known bipolar/eyelid name. We let resolve_targets decide.
        incoming[canonical] = value

    smoothing = float(s.smoothing)
    rounding = float(getattr(s, "rounding", 0.0))
    now = time.monotonic()

    # Update the latest-raw cache with whatever arrived this tick. The
    # *committed* value (what smoothing actually targets) is updated
    # separately below, only when the latest raw moves outside the
    # rounding deadband.
    # Saturation snap epsilon: raw values within this distance of 0 or 1
    # always commit immediately, regardless of the deadband. Keeps shape
    # keys from getting stuck slightly open / not quite fully closed.
    SAT_EPS = 1e-3

    for name, raw_value in incoming.items():
        b.latest_values[name] = raw_value
        committed = b.committed_values.get(name)
        at_saturation = (raw_value <= SAT_EPS) or (raw_value >= 1.0 - SAT_EPS) \
            or (raw_value <= -1.0 + SAT_EPS)
        if (
            committed is None
            or at_saturation
            or abs(raw_value - committed) > rounding
        ):
            b.committed_values[name] = raw_value

    if smoothing >= 1.0:
        # Fully snapped — no need to revisit cached params.
        params_to_apply = list(incoming.keys())
    else:
        # Snapshot — we may delete converged entries from the caches
        # inside the loop below.
        params_to_apply = list(b.latest_values.keys())

    touched = bool(params_to_apply)
    any_shape_key_changed = False

    for name in params_to_apply:
        raw_value = b.latest_values.get(name)
        if raw_value is None:
            continue
        # The smoothing target uses the *committed* raw, which only
        # changes when the live raw moves outside the rounding deadband.
        committed = b.committed_values.get(name, raw_value)

        # VRCFT bipolar params arrive in [-1, 1]; everything else in [0, 1].
        # Targets unpack the value themselves; only the unmatched UI row
        # needs a clamped scalar for display.
        targets = resolve_targets(name, sk)
        matched = bool(targets)

        all_converged = True
        if matched:
            for sk_name, fn in targets:
                target_value = fn(committed)
                block = sk[sk_name]
                if smoothing >= 1.0:
                    new = target_value
                else:
                    current = block.value
                    new = current + (target_value - current) * smoothing
                    if abs(target_value - new) > 1e-4:
                        all_converged = False
                if abs(new - block.value) > 1e-4:
                    block.value = new
                    any_shape_key_changed = True
                b.touched_keys.add(sk_name)
            # Show the live raw on the UI row, clamped to [0, 1].
            display = max(0.0, min(1.0, abs(raw_value)))
        else:
            b.unmatched.add(name)
            display = max(0.0, min(1.0, abs(raw_value)))
            all_converged = True  # nothing to converge

        # Once a smoothed param has fully reached its target, drop it
        # from latest_values so future ticks don't re-walk it. We keep
        # the entry in committed_values so other consumers (eye-bone
        # driver, etc.) can still observe the last committed raw.
        if matched and all_converged and name not in incoming:
            b.latest_values.pop(name, None)

        # Only update the UI row when fresh OSC arrives — we don't want
        # `last_seen` ticking forward for cached entries.
        if name in incoming:
            item = s.params.get(name)
            if item is None:
                item = s.params.add()
                item.name = name
            item.value = display
            item.matched = matched
            item.last_seen = now

    # ---- eye-bone driver ----
    if _drive_eye_bones(s, b, smoothing):
        any_shape_key_changed = True

    # ---- keyframe capture ----
    if b.keyframer is not None:
        try:
            frame = scene.frame_current
            b.keyframer.tick(frame)
            scene.frame_set(frame + 1)
        except Exception as e:
            print(f"[VRCFT] keyframer tick error: {e}")

    if touched or any_shape_key_changed:
        _tag_panel_redraw()

    return 1.0 / 60.0


_EYE_PARAM_NAMES = ("EyeX", "EyeY", "EyeLeftX", "EyeLeftY", "EyeRightX", "EyeRightY")


def _drive_eye_bones(s, b, smoothing) -> bool:
    """If eye bones are configured, lerp their pose toward the committed
    EyeX/EyeY (or per-eye) values. Returns True if any bone changed.
    """
    arma = s.eye_armature
    if arma is None or arma.type != 'ARMATURE':
        return False
    left_name = (s.left_eye_bone or "").strip()
    right_name = (s.right_eye_bone or "").strip()
    if not left_name and not right_name:
        return False

    cm = b.committed_values
    have_any = any(k in cm for k in _EYE_PARAM_NAMES)
    if not have_any:
        return False

    from . import eye_bones

    base_x = cm.get("EyeX", 0.0)
    base_y = cm.get("EyeY", 0.0)
    left_x = cm.get("EyeLeftX", base_x)
    left_y = cm.get("EyeLeftY", base_y)
    right_x = cm.get("EyeRightX", base_x)
    right_y = cm.get("EyeRightY", base_y)

    range_args = (
        float(s.eye_range_up),
        float(s.eye_range_down),
        float(s.eye_range_left),
        float(s.eye_range_right),
    )

    pose = arma.pose
    changed = False
    for bone_name, ex, ey in (
        (left_name, left_x, left_y),
        (right_name, right_x, right_y),
    ):
        if not bone_name:
            continue
        pb = pose.bones.get(bone_name)
        if pb is None:
            continue
        pitch, yaw = eye_bones.compute_angles(ex, ey, *range_args)
        if eye_bones.apply_eye_pose(pb, pitch, yaw, smoothing):
            changed = True
        b.touched_bones.add((arma.name, bone_name))
    return changed


def reset_touched_shape_keys(scene):
    """Zero every shape key the bridge has driven this session.

    Safe to call multiple times. Quietly no-ops if the mesh / keys are gone.
    """
    s = getattr(scene, "vrcft", None)
    if s is None:
        return
    b = get_bridge()
    names = list(b.touched_keys)
    b.touched_keys.clear()
    mesh = s.head_mesh
    if mesh is not None and mesh.data.shape_keys is not None:
        sk = mesh.data.shape_keys.key_blocks
        for name in names:
            block = sk.get(name)
            if block is None:
                continue
            if abs(block.value) > 1e-6:
                block.value = 0.0

    # Eye bones too — restore identity rotation on whatever we drove.
    bones = list(b.touched_bones)
    b.touched_bones.clear()
    if bones:
        import bpy
        from . import eye_bones
        for arma_name, bone_name in bones:
            arma = bpy.data.objects.get(arma_name)
            if arma is None or arma.type != 'ARMATURE':
                continue
            pb = arma.pose.bones.get(bone_name)
            if pb is None:
                continue
            eye_bones.reset_eye_pose(pb)
    # And clear committed cache so a future Test session starts fresh.
    b.committed_values.clear()
    b.latest_values.clear()


def _tag_panel_redraw():
    import bpy

    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
