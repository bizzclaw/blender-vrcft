import os

import bpy
from bpy.types import Operator

from . import capture as capture_mod
from . import osc_bridge


def _resolve_capture_path(raw):
    p = bpy.path.abspath(raw)
    if p.startswith("//"):
        p = p[2:]
    return os.path.abspath(p)


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
        err = b.acquire(s.osc_port)
        if err:
            self.report({'ERROR'}, f"Could not bind UDP {s.osc_port}: {err}")
            return {'CANCELLED'}

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
        osc_bridge.get_bridge().release()
        print("[VRCFT] stop_test")
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
