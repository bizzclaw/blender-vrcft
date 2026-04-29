"""Sparse keyframe recorder for VRCFT capture mode.

A ``Keyframer`` instance owns the bookkeeping for a single capture
session. It writes keyframes onto Blender actions named
``VRCFT_Capture_<datablock>`` for the head-mesh shape keys and the eye
armature, but only on data paths the bridge actually drives. Existing
F-curves on those actions for *other* data paths are preserved.

Design notes:
* All keyframe insertion goes through ``key_blocks[...].keyframe_insert``
  / ``pose_bone.keyframe_insert`` so Blender handles action creation
  and curve registration. We then post-process to set linear interp.
* We *sample* the current value of every shape key (not just the ones
  the bridge wrote), so manual / pre-existing keys evaluated at the
  scene frame still get baked into the capture action. The user's
  source action stays untouched.
* Sparse: per channel we remember the last keyed value; we only
  insert when the new value differs by more than ``EPSILON``. We
  always force-anchor at start() and stop().
"""
from __future__ import annotations

EPSILON = 1e-5
ACTION_PREFIX = "VRCFT_Capture_"


def _ensure_action(id_data, name: str):
    """Get-or-create an action and bind it to ``id_data.animation_data``."""
    import bpy

    if id_data.animation_data is None:
        id_data.animation_data_create()
    ad = id_data.animation_data
    action = bpy.data.actions.get(name)
    if action is None:
        action = bpy.data.actions.new(name)
    ad.action = action
    return action


def _action_fcurves(action):
    """Return an iterable of all F-curves on an Action.

    Blender 5.0 introduced layered actions where F-curves live on
    channelbags inside layer strips. Older code accessed
    ``action.fcurves`` directly. We support both.
    """
    fcurves_attr = getattr(action, "fcurves", None)
    if fcurves_attr is not None:
        try:
            # Force a tuple to detect the legacy collection
            return list(fcurves_attr)
        except TypeError:
            pass
    out = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            channelbags = getattr(strip, "channelbags", None)
            if channelbags is None:
                continue
            for cb in channelbags:
                out.extend(list(cb.fcurves))
    return out


def _find_fcurve(action, data_path: str, array_index: int):
    for fc in _action_fcurves(action):
        if fc.data_path == data_path and fc.array_index == array_index:
            return fc
    return None


def _remove_fcurve(action, fc):
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        try:
            legacy.remove(fc)
            return
        except (RuntimeError, TypeError):
            pass
    # Layered: walk channelbags to find owner.
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for cb in getattr(strip, "channelbags", []) or []:
                if fc in list(cb.fcurves):
                    cb.fcurves.remove(fc)
                    return


def _clear_fcurves(action, data_paths_indices):
    """Remove F-curves whose (data_path, array_index) appears in
    ``data_paths_indices``. Other curves on the action are preserved.
    """
    targets = set(data_paths_indices)
    to_remove = [
        fc for fc in _action_fcurves(action)
        if (fc.data_path, fc.array_index) in targets
    ]
    for fc in to_remove:
        _remove_fcurve(action, fc)


def _set_linear(action, data_path: str, array_index: int) -> None:
    """Best-effort set the most-recent key on (path, idx) to LINEAR."""
    fc = _find_fcurve(action, data_path, array_index)
    if fc is None or not fc.keyframe_points:
        return
    kp = fc.keyframe_points[-1]
    kp.interpolation = 'LINEAR'


class Keyframer:
    def __init__(self, mesh, armature, left_bone: str, right_bone: str):
        self.mesh = mesh
        self.armature = armature
        self.left_bone = (left_bone or "").strip()
        self.right_bone = (right_bone or "").strip()
        # last_keyed[(id_kind, key, idx)] = float
        # id_kind: 'shape' for shape-keys, 'bone' for armature pose bones
        # key: shape key name OR pose bone name
        # idx: 0 for shape values, 0/1 for bone rotation_euler X/Y
        self.last_keyed: dict[tuple[str, str, int], float] = {}
        self.start_frame = 0
        self._mesh_action = None
        self._arm_action = None
        self._shape_key_names: list[str] = []
        self._bone_names: list[str] = []

    # ---- helpers -----------------------------------------------------
    def _shape_keys_block(self):
        if self.mesh is None or self.mesh.type != 'MESH':
            return None
        if self.mesh.data.shape_keys is None:
            return None
        return self.mesh.data.shape_keys

    def _shape_keys_id(self):
        sk = self._shape_keys_block()
        return sk

    def _drive_able_shape_key_names(self) -> list[str]:
        sk = self._shape_keys_block()
        if sk is None:
            return []
        return [kb.name for kb in sk.key_blocks if kb.name != "Basis"]

    def _bone_targets(self) -> list[str]:
        if self.armature is None or self.armature.type != 'ARMATURE':
            return []
        names = []
        for n in (self.left_bone, self.right_bone):
            if n and n in self.armature.pose.bones:
                names.append(n)
        return names

    # ---- lifecycle ---------------------------------------------------
    def start(self, frame: int) -> None:
        self.start_frame = frame
        sk = self._shape_keys_block()
        self._shape_key_names = self._drive_able_shape_key_names()
        self._bone_names = self._bone_targets()

        if sk is not None and self._shape_key_names:
            self._mesh_action = _ensure_action(
                sk, f"{ACTION_PREFIX}{self.mesh.name}_Shapes"
            )
            paths = {
                (f'key_blocks["{n}"].value', 0)
                for n in self._shape_key_names
            }
            _clear_fcurves(self._mesh_action, paths)
            for n in self._shape_key_names:
                kb = sk.key_blocks[n]
                value = float(kb.value)
                kb.keyframe_insert(data_path="value", frame=frame)
                _set_linear(self._mesh_action,
                            f'key_blocks["{n}"].value', 0)
                self.last_keyed[('shape', n, 0)] = value

        if self._bone_names:
            self._arm_action = _ensure_action(
                self.armature, f"{ACTION_PREFIX}{self.armature.name}"
            )
            paths = set()
            for bn in self._bone_names:
                for idx in (0, 1):
                    paths.add(
                        (f'pose.bones["{bn}"].rotation_euler', idx)
                    )
            _clear_fcurves(self._arm_action, paths)
            for bn in self._bone_names:
                pb = self.armature.pose.bones[bn]
                # Force euler mode so rotation_euler keyframes work
                # cleanly; the rest of the add-on already writes through
                # rotation_euler regardless of mode, but for capture
                # we anchor on euler curves.
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_mode = 'XYZ'
                for idx in (0, 1):
                    pb.keyframe_insert(
                        data_path="rotation_euler",
                        index=idx,
                        frame=frame,
                    )
                    _set_linear(
                        self._arm_action,
                        f'pose.bones["{bn}"].rotation_euler',
                        idx,
                    )
                    self.last_keyed[('bone', bn, idx)] = float(
                        pb.rotation_euler[idx]
                    )

    def tick(self, frame: int) -> int:
        """Insert sparse keys at ``frame``. Returns count of keys inserted."""
        n_inserted = 0
        sk = self._shape_keys_block()
        if sk is not None and self._mesh_action is not None:
            for name in self._shape_key_names:
                kb = sk.key_blocks.get(name)
                if kb is None:
                    continue
                cur = float(kb.value)
                key = ('shape', name, 0)
                last = self.last_keyed.get(key)
                if last is None or abs(cur - last) > EPSILON:
                    kb.keyframe_insert(data_path="value", frame=frame)
                    _set_linear(
                        self._mesh_action,
                        f'key_blocks["{name}"].value',
                        0,
                    )
                    self.last_keyed[key] = cur
                    n_inserted += 1

        if self._arm_action is not None:
            for bn in self._bone_names:
                pb = self.armature.pose.bones.get(bn)
                if pb is None:
                    continue
                for idx in (0, 1):
                    cur = float(pb.rotation_euler[idx])
                    key = ('bone', bn, idx)
                    last = self.last_keyed.get(key)
                    if last is None or abs(cur - last) > EPSILON:
                        pb.keyframe_insert(
                            data_path="rotation_euler",
                            index=idx,
                            frame=frame,
                        )
                        _set_linear(
                            self._arm_action,
                            f'pose.bones["{bn}"].rotation_euler',
                            idx,
                        )
                        self.last_keyed[key] = cur
                        n_inserted += 1
        return n_inserted

    def stop(self, frame: int) -> None:
        """Force-anchor a final key at ``frame`` for every channel."""
        sk = self._shape_keys_block()
        if sk is not None and self._mesh_action is not None:
            for name in self._shape_key_names:
                kb = sk.key_blocks.get(name)
                if kb is None:
                    continue
                kb.keyframe_insert(data_path="value", frame=frame)
                _set_linear(
                    self._mesh_action,
                    f'key_blocks["{name}"].value',
                    0,
                )
                self.last_keyed[('shape', name, 0)] = float(kb.value)
        if self._arm_action is not None:
            for bn in self._bone_names:
                pb = self.armature.pose.bones.get(bn)
                if pb is None:
                    continue
                for idx in (0, 1):
                    pb.keyframe_insert(
                        data_path="rotation_euler",
                        index=idx,
                        frame=frame,
                    )
                    _set_linear(
                        self._arm_action,
                        f'pose.bones["{bn}"].rotation_euler',
                        idx,
                    )
                    self.last_keyed[('bone', bn, idx)] = float(
                        pb.rotation_euler[idx]
                    )
