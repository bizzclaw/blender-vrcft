"""Eye-bone driver.

VRCFT eye conventions (per VRCFaceTracking/Avatars docs):
  EyeX: -1..1, positive = looking right  (avatar's right)
  EyeY: -1..1, positive = looking up
Per-eye variants ``EyeLeftX/Y`` and ``EyeRightX/Y`` override the combined
``EyeX/Y`` when streamed.

Bone-axis convention: **tail-up** (the standard for VRChat humanoid eye
bones in Blender — the bone extends upward out of the head, so the
bone's local Y axis points up, X = right, Z = back).

With tail-up bones, pose-space Euler maps to gaze as:

    rotation_euler.x = -pitch          (look up  -> -X rotation)
    rotation_euler.y = -yaw            (look right -> -Y rotation)
    rotation_euler.z =  preserved      (bone roll, untouched)

If a particular rig's eye axes are mirrored, set the corresponding
``eye_range_*`` property to a negative value to invert that axis.
"""
from __future__ import annotations

import math


def compute_angles(
    eye_x: float, eye_y: float,
    range_up: float, range_down: float,
    range_left: float, range_right: float,
) -> tuple[float, float]:
    """Map normalized eye params to (pitch, yaw) in radians.

    All four range values are positive magnitudes (radians). The function
    applies the up-range when ``eye_y`` is positive, etc.
    """
    eye_x = max(-1.0, min(1.0, eye_x))
    eye_y = max(-1.0, min(1.0, eye_y))
    pitch = eye_y * (range_up if eye_y >= 0.0 else range_down)
    yaw = eye_x * (range_right if eye_x >= 0.0 else range_left) * -1
    return pitch, yaw


def _read_euler_xyz(pose_bone) -> tuple[float, float, float]:
    """Return (x, y, z) Euler XYZ regardless of pose_bone.rotation_mode."""
    mode = pose_bone.rotation_mode
    if mode == 'QUATERNION':
        eul = pose_bone.rotation_quaternion.to_euler('XYZ')
    elif mode == 'AXIS_ANGLE':
        from mathutils import Quaternion
        aa = pose_bone.rotation_axis_angle
        q = Quaternion((aa[1], aa[2], aa[3]), aa[0])
        eul = q.to_euler('XYZ')
    else:
        eul = pose_bone.rotation_euler
    return float(eul[0]), float(eul[1]), float(eul[2])


def _write_euler_xyz(pose_bone, x: float, y: float, z: float) -> None:
    mode = pose_bone.rotation_mode
    if mode == 'QUATERNION':
        from mathutils import Euler
        pose_bone.rotation_quaternion = Euler((x, y, z), 'XYZ').to_quaternion()
    elif mode == 'AXIS_ANGLE':
        from mathutils import Euler
        q = Euler((x, y, z), 'XYZ').to_quaternion()
        ax, angle = q.to_axis_angle()
        pose_bone.rotation_axis_angle = (angle, ax.x, ax.y, ax.z)
    else:
        pose_bone.rotation_euler = (x, y, z)


# Back-compat aliases (older code/tests imported these names).
_read_current_xz = _read_euler_xyz
_write_xz = _write_euler_xyz


def apply_eye_pose(pose_bone, target_pitch: float, target_yaw: float,
                   smoothing: float) -> bool:
    """Lerp pose_bone rotation toward (pitch, yaw). Returns True if it changed.

    Tail-up bone convention: pitch -> local -X, yaw -> local -Y.
    The bone's existing local Z (roll) is preserved.
    """
    target_x = -target_pitch
    target_y = -target_yaw
    cx, cy, cz = _read_euler_xyz(pose_bone)
    if smoothing >= 1.0:
        nx, ny = target_x, target_y
    else:
        nx = cx + (target_x - cx) * smoothing
        ny = cy + (target_y - cy) * smoothing
    if abs(nx - cx) < 1e-5 and abs(ny - cy) < 1e-5:
        return False
    _write_euler_xyz(pose_bone, nx, ny, cz)
    return True


def reset_eye_pose(pose_bone) -> None:
    """Zero out the X and Y rotation, preserve Z (any roll on the bone)."""
    cx, cy, cz = _read_euler_xyz(pose_bone)
    if abs(cx) < 1e-6 and abs(cy) < 1e-6:
        return
    _write_euler_xyz(pose_bone, 0.0, 0.0, cz)


DEFAULT_RANGE_RAD = math.radians(30.0)
