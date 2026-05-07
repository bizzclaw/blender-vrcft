import bpy
from bpy.types import Panel


class VRCFT_PT_main(Panel):
    bl_idname = "VRCFT_PT_main"
    bl_label = "VRCFT"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRCFT"

    def draw(self, context):
        layout = self.layout
        s = context.scene.vrcft

        box = layout.box()
        box.label(text="Setup", icon='OUTLINER_OB_MESH')
        box.prop(s, "head_mesh")
        profile_col = box.column()
        profile_col.enabled = not s.is_running
        profile_col.prop(s, "tracking_profile")
        box.prop(s, "smoothing")
        box.prop(s, "rounding")

        box = layout.box()
        box.label(text="Eye Bones", icon='HIDE_OFF')
        box.prop(s, "eye_armature")
        if s.eye_armature is not None and s.eye_armature.type == 'ARMATURE':
            box.prop_search(s, "left_eye_bone", s.eye_armature.data, "bones")
            box.prop_search(s, "right_eye_bone", s.eye_armature.data, "bones")
        sub = box.column(align=True)
        sub.label(text="Eye Range")
        row = sub.row(align=True)
        row.prop(s, "eye_range_up", text="Up")
        row.prop(s, "eye_range_down", text="Down")
        row = sub.row(align=True)
        row.prop(s, "eye_range_left", text="Left")
        row.prop(s, "eye_range_right", text="Right")

        box = layout.box()
        box.label(text="Network", icon='WORLD')
        box.prop(s, "osc_port")
        box.prop(s, "vrcft_send_port")
        box.prop(s, "oscquery_http_port")
        box.prop(s, "service_name")
        box.prop(s, "address_prefix")

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Session", icon='PLAY')
        row.label(text=("Running: " + s.active_mode.title()) if s.is_running else "Stopped")
        sub = box.row(align=True)
        sub.enabled = not s.is_running
        sub.prop(s, "mode", expand=True)
        if s.is_running:
            box.operator("vrcft.stop_session", icon='PAUSE', text="Stop")
        else:
            box.operator("vrcft.start_session", icon='PLAY', text="Start")
        if s.avatar_status:
            box.label(text=s.avatar_status, icon='INFO')
        if s.is_running and s.active_mode == 'CAPTURE':
            box.label(
                text=f"Recording \u2192 frame {context.scene.frame_current}",
                icon='REC',
            )

        box = layout.box()
        row = box.row(align=True)
        row.label(text="OSC Log", icon='FILE_TEXT')
        row.label(text="Logging" if s.is_capturing else "Idle")
        box.prop(s, "capture_path")
        if s.is_capturing:
            box.operator("vrcft.stop_capture", icon='SNAP_FACE', text="Stop Log")
        else:
            box.operator("vrcft.start_capture", icon='REC', text="Start Log")

        box = layout.box()
        header = box.row(align=True)
        header.label(text=f"Live Parameters ({len(s.params)})", icon='GRAPH')
        header.prop(s, "sort_alphabetical", text="", icon='SORTALPHA', toggle=True)
        header.prop(s, "show_unmatched", text="", icon='QUESTION', toggle=True)
        header.operator("vrcft.clear_params", text="", icon='X')
        box.template_list(
            "VRCFT_UL_params",
            "",
            s,
            "params",
            s,
            "active_param_index",
            rows=10,
        )


_classes = (VRCFT_PT_main,)


def register():
    for c in _classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
