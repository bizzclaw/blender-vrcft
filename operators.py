import os

import bpy
from bpy.types import Operator

from . import avatar_json
from . import capture as capture_mod
from . import osc_bridge


def _resolve_capture_path(raw):
    p = bpy.path.abspath(raw)
    if p.startswith("//"):
        p = p[2:]
    return os.path.abspath(p)


def _shape_key_names(mesh):
    if mesh is None or mesh.data.shape_keys is None:
        return []
    return [kb.name for kb in mesh.data.shape_keys.key_blocks if kb.name != "Basis"]


class VRCFT_OT_start_test(Operator):
    bl_idname = "vrcft.start_test"
    bl_label = "Start Test"
    bl_description = "Begin listening for VRCFT OSC and driving shape keys"

    def execute(self, context):
        s = context.scene.vrcft
        if s.is_running:
            return {'CANCELLED'}
        if s.head_mesh is None:
            self.report({'ERROR'}, "Assign a Head Mesh first.")
            return {'CANCELLED'}
        if s.head_mesh.type != 'MESH':
            self.report({'ERROR'}, "Head Mesh must be a mesh object.")
            return {'CANCELLED'}
        if s.head_mesh.data.shape_keys is None:
            self.report({'ERROR'}, "Head Mesh has no shape keys.")
            return {'CANCELLED'}

        b = osc_bridge.get_bridge()
        b.address_prefix = s.address_prefix
        b.touched_keys.clear()
        err = b.acquire(s.osc_port)
        if err:
            self.report({'ERROR'}, f"Could not bind UDP {s.osc_port}: {err}")
            return {'CANCELLED'}

        # Register a Blender-owned avatar JSON with VRCFT so its Avatar
        # Status shows our name (and so VRCFT sends every parameter we
        # actually have a shape key for).
        result = avatar_json.register_blender_avatar(
            blend_path=bpy.data.filepath,
            shape_key_names=_shape_key_names(s.head_mesh),
            send_host="127.0.0.1",
            send_port=s.vrcft_send_port,
            tracking_profile=s.tracking_profile,
        )
        if result["error"]:
            s.avatar_status = result["error"]
            self.report({'WARNING'}, result["error"])
        else:
            profile_label = "ARKit" if s.tracking_profile == 'ARKIT' else "Unified"
            s.avatar_status = f"Registered as {result['name']} ({profile_label})"
            print(
                f"[VRCFT] avatar JSON: {result['json_path']} "
                f"(id={result['avatar_id']})"
            )

        s.is_running = True
        if not bpy.app.timers.is_registered(osc_bridge.tick):
            bpy.app.timers.register(
                osc_bridge.tick, first_interval=0.016, persistent=True
            )
        print(f"[VRCFT] start_test on UDP :{s.osc_port}")
        return {'FINISHED'}


class VRCFT_OT_stop_test(Operator):
    bl_idname = "vrcft.stop_test"
    bl_label = "Stop Test"
    bl_description = "Stop the OSC test session"

    def execute(self, context):
        s = context.scene.vrcft
        if not s.is_running:
            return {'CANCELLED'}
        s.is_running = False
        if bpy.app.timers.is_registered(osc_bridge.tick):
            bpy.app.timers.unregister(osc_bridge.tick)

        # Reset every shape key we drove during this session before
        # tearing the server down. Do it on the active scene, not via
        # context (context.scene can be None during teardown in some
        # callers).
        osc_bridge.reset_touched_shape_keys(context.scene)
        s.params.clear()
        s.active_param_index = 0

        osc_bridge.get_bridge().release()
        print("[VRCFT] stop_test")
        return {'FINISHED'}


class VRCFT_OT_start_session(Operator):
    bl_idname = "vrcft.start_session"
    bl_label = "Start"
    bl_description = "Start the selected mode (Test or Capture)"

    def execute(self, context):
        s = context.scene.vrcft
        if s.is_running:
            return {'CANCELLED'}
        # Always start Test first; in CAPTURE we additionally engage
        # the keyframer (added in phase 5c).
        result = bpy.ops.vrcft.start_test()
        if 'FINISHED' not in result:
            return {'CANCELLED'}
        s.active_mode = s.mode
        if s.mode == 'CAPTURE':
            b = osc_bridge.get_bridge()
            try:
                from . import keyframer as kf_mod
            except ImportError:
                kf_mod = None
            if kf_mod is not None:
                start_frame = context.scene.frame_current
                kf = kf_mod.Keyframer(
                    mesh=s.head_mesh,
                    armature=s.eye_armature,
                    left_bone=s.left_eye_bone,
                    right_bone=s.right_eye_bone,
                )
                try:
                    kf.start(start_frame)
                    b.keyframer = kf
                    print(f"[VRCFT] capture start at frame {start_frame}")
                except Exception as e:
                    self.report({'WARNING'}, f"Capture init failed: {e}")
        return {'FINISHED'}


class VRCFT_OT_stop_session(Operator):
    bl_idname = "vrcft.stop_session"
    bl_label = "Stop"
    bl_description = "Stop the running session"

    def execute(self, context):
        s = context.scene.vrcft
        if not s.is_running:
            return {'CANCELLED'}
        b = osc_bridge.get_bridge()
        kf = getattr(b, 'keyframer', None)
        if kf is not None:
            try:
                kf.stop(context.scene.frame_current)
            except Exception as e:
                print(f"[VRCFT] capture stop error: {e}")
            b.keyframer = None
            print("[VRCFT] capture stop")
        bpy.ops.vrcft.stop_test()
        s.active_mode = 'IDLE'
        return {'FINISHED'}



class VRCFT_OT_start_capture(Operator):
    bl_idname = "vrcft.start_capture"
    bl_label = "Start Capture"
    bl_description = "Log all incoming OSC messages to the capture file"

    def execute(self, context):
        s = context.scene.vrcft
        if s.is_capturing:
            return {'CANCELLED'}
        path = _resolve_capture_path(s.capture_path)

        b = osc_bridge.get_bridge()
        b.address_prefix = s.address_prefix
        writer = capture_mod.CaptureWriter(path)
        try:
            writer.open()
        except OSError as e:
            self.report({'ERROR'}, f"Could not open capture file: {e}")
            return {'CANCELLED'}

        err = b.acquire(s.osc_port)
        if err:
            writer.close()
            self.report({'ERROR'}, f"Could not bind UDP {s.osc_port}: {err}")
            return {'CANCELLED'}

        b.capture_writer = writer
        s.is_capturing = True
        print(f"[VRCFT] start_capture -> {path}")
        return {'FINISHED'}


class VRCFT_OT_stop_capture(Operator):
    bl_idname = "vrcft.stop_capture"
    bl_label = "Stop Capture"
    bl_description = "Stop the OSC capture logger"

    def execute(self, context):
        s = context.scene.vrcft
        if not s.is_capturing:
            return {'CANCELLED'}
        b = osc_bridge.get_bridge()
        writer = b.capture_writer
        b.capture_writer = None
        if writer is not None:
            writer.close()
        b.release()
        s.is_capturing = False
        print("[VRCFT] stop_capture")
        return {'FINISHED'}


class VRCFT_OT_clear_params(Operator):
    bl_idname = "vrcft.clear_params"
    bl_label = "Clear"
    bl_description = "Clear the live parameter list"

    def execute(self, context):
        s = context.scene.vrcft
        s.params.clear()
        s.active_param_index = 0
        b = osc_bridge.get_bridge()
        b.unmatched.clear()
        return {'FINISHED'}


_classes = (
    VRCFT_OT_start_test,
    VRCFT_OT_stop_test,
    VRCFT_OT_start_session,
    VRCFT_OT_stop_session,
    VRCFT_OT_start_capture,
    VRCFT_OT_stop_capture,
    VRCFT_OT_clear_params,
)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    if bpy.app.timers.is_registered(osc_bridge.tick):
        bpy.app.timers.unregister(osc_bridge.tick)
    osc_bridge.reset_bridge()
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
