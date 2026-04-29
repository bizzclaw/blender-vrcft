"""LocalLow VRChat avatar JSON registration.

VRCFaceTracking decides which OSC parameters to emit by reading the JSON
file for the active avatar in
``%LocalAppData%Low\\VRChat\\vrchat\\OSC\\<userid>\\Avatars\\<avatarid>.json``.
When VRChat is not the one selecting the avatar, the most recently
modified file in that folder wins — which is why VRCFT shows the wrong
avatar name when Blender is the only listener.

We mirror the structure used by Lyuma's Av3Emulator so VRCFT recognises
the file unmodified, and we send ``/avatar/change <id>`` so it switches.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Iterable

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from . import unified_expressions

# Stable namespace so the same .blend always gets the same avatar id.
_NAMESPACE = uuid.UUID("8a1d2c0c-1f6f-4a7a-9b48-1234567890ab")

ID_PREFIX = "avtr_blender_vrcft_"
ADDRESS_PREFIX = "/avatar/parameters/"


def stable_avatar_id(blend_path: str) -> str:
    """Return a deterministic avatar id for a given .blend file path."""
    key = os.path.abspath(blend_path) if blend_path else "<unsaved>"
    # Use uuid5 so the same file always maps to the same id.
    digest = uuid.uuid5(_NAMESPACE, key).hex
    return ID_PREFIX + digest


def display_name(blend_path: str) -> str:
    if not blend_path:
        return "Blender VRCFT - Untitled"
    base = os.path.basename(blend_path)
    if base.lower().endswith(".blend"):
        base = base[: -len(".blend")]
    return f"Blender VRCFT - {base or 'Untitled'}"


def build_outer_json(avatar_id: str, name: str, shape_key_names: Iterable[str]) -> dict:
    """Build the OuterJson structure VRCFT/Av3Emulator expect.

    Declares every Unified Expressions parameter (v2 + legacy) plus the
    avatar's literal shape-key names. VRCFT only sends data for parameters
    listed here, so declaring the full UE set is what makes the bipolar /
    composite / simplified params actually flow.
    """
    parameters = []
    seen_names = set()

    def _emit(param_name: str, address: str) -> None:
        if param_name in seen_names:
            return
        seen_names.add(param_name)
        parameters.append(
            {
                "name": param_name,
                "input": {"address": address, "type": "Float"},
                "output": {"address": address, "type": "Float"},
            }
        )

    # Avatar shape keys first — they get the bare /avatar/parameters/<name>
    # address, which is what direct-match drives in tick().
    for sk_name in shape_key_names:
        if not sk_name or sk_name == "Basis":
            continue
        _emit(sk_name, ADDRESS_PREFIX + sk_name)

    # Full UE v2 parameter set.
    for ue_name in unified_expressions.V2_PARAMETERS:
        _emit("v2_" + ue_name, ADDRESS_PREFIX + "v2/" + ue_name)

    # Legacy / simplified parameter set (no v2/ prefix).
    for legacy_name in unified_expressions.LEGACY_PARAMETERS:
        if legacy_name in seen_names:
            continue
        _emit(legacy_name, ADDRESS_PREFIX + legacy_name)

    return {"id": avatar_id, "name": name, "parameters": parameters}


def _local_low_path() -> str | None:
    """Resolve %USERPROFILE%\\AppData\\LocalLow on Windows."""
    if sys.platform != "win32":
        return None
    user = os.environ.get("USERPROFILE")
    if not user:
        return None
    candidate = os.path.join(user, "AppData", "LocalLow")
    return candidate if os.path.isdir(candidate) else None


def _vrc_osc_root() -> str | None:
    base = _local_low_path()
    if base is None:
        return None
    root = os.path.join(base, "VRChat", "vrchat", "OSC")
    return root


def discover_user_id() -> str | None:
    """Pick the most-recently-modified userid folder under VRC's OSC dir."""
    root = _vrc_osc_root()
    if root is None or not os.path.isdir(root):
        return None
    best = None
    best_mtime = -1.0
    try:
        entries = os.listdir(root)
    except OSError:
        return None
    for entry in entries:
        full = os.path.join(root, entry)
        if not os.path.isdir(full):
            continue
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best = entry
    return best


def avatar_json_path(user_id: str, avatar_id: str) -> str:
    root = _vrc_osc_root()
    if root is None:
        raise RuntimeError("LocalLow path is unavailable on this platform")
    return os.path.join(root, user_id, "Avatars", avatar_id + ".json")


def write_avatar_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(payload, indent=4)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def send_avatar_change(host: str, port: int, avatar_id: str) -> str | None:
    """Send ``/avatar/change <avatar_id>`` to a VRCFT-style listener.

    Returns None on success or an error message on failure.
    """
    try:
        from pythonosc.udp_client import SimpleUDPClient
    except ImportError as e:  # pragma: no cover - vendored
        return f"python-osc not available: {e}"
    try:
        client = SimpleUDPClient(host, port)
        client.send_message("/avatar/change", avatar_id)
    except OSError as e:
        return str(e)
    return None


def register_blender_avatar(blend_path: str, shape_key_names: Iterable[str],
                            send_host: str, send_port: int) -> dict:
    """High-level: write JSON and notify VRCFT.

    Returns a dict with ``avatar_id``, ``name``, ``json_path`` (or None),
    ``user_id`` (or None), and ``error`` (or None).
    """
    avatar_id = stable_avatar_id(blend_path)
    name = display_name(blend_path)
    payload = build_outer_json(avatar_id, name, list(shape_key_names))

    user_id = discover_user_id()
    json_path: str | None = None
    error: str | None = None

    if user_id is None:
        error = "Could not find a VRChat user folder under LocalLow."
    else:
        try:
            json_path = avatar_json_path(user_id, avatar_id)
            write_avatar_json(json_path, payload)
        except OSError as e:
            error = f"Failed to write avatar JSON: {e}"
            json_path = None

    if error is None:
        send_err = send_avatar_change(send_host, send_port, avatar_id)
        if send_err is not None:
            error = f"Wrote JSON but /avatar/change failed: {send_err}"

    return {
        "avatar_id": avatar_id,
        "name": name,
        "json_path": json_path,
        "user_id": user_id,
        "error": error,
        "payload": payload,
    }
