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

    # Coalesce by canonical (matched) name so different prefix variants of
    # the same parameter merge to a single row and a single shape-key write.
    targets = {}
    while True:
        try:
            raw_name, value = b.queue.get_nowait()
        except queue.Empty:
            break
        canonical, matched = canonical_name(raw_name, sk)
        targets[canonical] = (value, matched)

    smoothing = float(s.smoothing)
    now = time.monotonic()
    touched = bool(targets)

    for name, (target, matched) in targets.items():
        target = max(0.0, min(1.0, target))

        if matched:
            block = sk[name]
            if smoothing >= 1.0:
                new = target
            else:
                current = block.value
                new = current + (target - current) * smoothing
            if abs(new - block.value) > 1e-4:
                block.value = new
            display = new
        else:
            b.unmatched.add(name)
            display = target

        item = s.params.get(name)
        if item is None:
            item = s.params.add()
            item.name = name
        item.value = display
        item.matched = matched
        item.last_seen = now

    if touched:
        _tag_panel_redraw()

    return 1.0 / 60.0


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
