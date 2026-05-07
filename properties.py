import math

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Object, PropertyGroup

from . import unified_expressions


def _poll_mesh(self, obj):
    return obj.type == 'MESH'


def _poll_armature(self, obj):
    return obj.type == 'ARMATURE'


class VRCFT_ParamItem(PropertyGroup):
    """One row in the live parameters UIList."""

    # `name` is inherited from PropertyGroup and is what CollectionProperty
    # uses as the key for .get() / .find().
    value: FloatProperty(default=0.0, min=0.0, max=1.0)
    matched: BoolProperty(default=False)
    last_seen: FloatProperty(default=0.0)


class VRCFT_Settings(PropertyGroup):
    head_mesh: PointerProperty(
        type=Object,
        name="Head Mesh",
        description="Mesh whose shape keys are driven by VRCFT",
        poll=_poll_mesh,
    )

    osc_port: IntProperty(
        name="OSC Port",
        description="UDP port we listen on for VRCFT face-tracking values",
        default=9000,
        min=1,
        max=65535,
    )

    vrcft_send_port: IntProperty(
        name="VRCFT Input Port",
        description="UDP port VRCFT listens on (we send /avatar/change here"
        " on Start Test). Default VRCFT setup is 9001",
        default=9001,
        min=1,
        max=65535,
    )

    oscquery_http_port: IntProperty(
        name="OSCQuery HTTP Port",
        description="HTTP port for the OSCQuery JSON endpoint. 0 picks a free port at start",
        default=0,
        min=0,
        max=65535,
    )

    service_name: StringProperty(
        name="Service Name",
        description="mDNS service instance name advertised to OSCQuery clients",
        default="Blender VRCFT",
    )

    smoothing: FloatProperty(
        name="Smoothing",
        description="Lerp alpha per drained tick. 0 = none, 1 = snap",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    rounding: FloatProperty(
        name="Rounding",
        description=(
            "Deadband on the smoothing target. The target only updates when "
            "the incoming raw value moves more than this from the last "
            "committed value. Smoothing then continues to lerp the shape "
            "key toward the held target. Saturation values (0 and 1) "
            "always commit immediately so shape keys can fully open/close. "
            "0 = off"
        ),
        default=0.07,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    tracking_profile: EnumProperty(
        name="Blendshape Set",
        description=(
            "Which face-tracking blendshape vocabulary the avatar expects. "
            "Unified uses VRCFaceTracking Unified Expressions v2 plus legacy "
            "compatibility parameters. ARKit uses Apple's 52 blendshape "
            "coefficients"
        ),
        items=unified_expressions.TRACKING_PROFILE_ITEMS,
        default=unified_expressions.DEFAULT_TRACKING_PROFILE,
    )

    address_prefix: StringProperty(
        name="Address Prefix",
        description="OSC address prefix to match. Trailing slash recommended",
        default="/avatar/parameters/",
    )

    eye_armature: PointerProperty(
        type=Object,
        name="Eye Armature",
        description="Armature containing the left and right eye bones",
        poll=_poll_armature,
    )

    left_eye_bone: StringProperty(
        name="Left Eye Bone",
        description="Pose bone driven by the left-eye gaze parameters",
        default="",
    )

    right_eye_bone: StringProperty(
        name="Right Eye Bone",
        description="Pose bone driven by the right-eye gaze parameters",
        default="",
    )

    eye_range_up: FloatProperty(
        name="Range Up",
        description="Maximum upward eye-bone pitch when EyeY = +1",
        default=math.radians(30.0),
        subtype='ANGLE',
        unit='ROTATION',
    )
    eye_range_down: FloatProperty(
        name="Range Down",
        description="Maximum downward eye-bone pitch when EyeY = -1",
        default=math.radians(30.0),
        subtype='ANGLE',
        unit='ROTATION',
    )
    eye_range_left: FloatProperty(
        name="Range Left",
        description="Maximum leftward eye-bone yaw when EyeX = -1",
        default=math.radians(30.0),
        subtype='ANGLE',
        unit='ROTATION',
    )
    eye_range_right: FloatProperty(
        name="Range Right",
        description="Maximum rightward eye-bone yaw when EyeX = +1",
        default=math.radians(30.0),
        subtype='ANGLE',
        unit='ROTATION',
    )

    capture_path: StringProperty(
        name="Capture Path",
        description="Where the OSC capture log is written. // is relative to the .blend file",
        default="//vrcft_capture.log",
        subtype='FILE_PATH',
    )

    is_running: BoolProperty(
        name="Test Running",
        description="True while the OSC test session is active",
        default=False,
    )

    mode: EnumProperty(
        name="Mode",
        description=(
            "Test = preview only. Capture = preview AND record keyframes "
            "into a VRCFT_Capture action, advancing the scene frame each "
            "tick"
        ),
        items=[
            ('TEST', "Test", "Preview OSC values on the avatar without recording"),
            ('CAPTURE', "Capture", "Preview AND record keyframes into a VRCFT_Capture action"),
        ],
        default='TEST',
    )

    active_mode: EnumProperty(
        name="Active Mode",
        description="The mode the session was started in. IDLE while stopped",
        items=[
            ('IDLE', "Idle", ""),
            ('TEST', "Test", ""),
            ('CAPTURE', "Capture", ""),
        ],
        default='IDLE',
    )

    avatar_status: StringProperty(
        name="Avatar Status",
        description="Last result from the avatar JSON registration",
        default="",
    )

    is_capturing: BoolProperty(
        name="Capture Running",
        description="True while OSC traffic is being logged to disk",
        default=False,
    )

    params: CollectionProperty(type=VRCFT_ParamItem)
    active_param_index: IntProperty(default=0)

    sort_alphabetical: BoolProperty(
        name="Sort Alphabetical",
        description="When on, the parameter list is alphabetical."
        " When off, parameters appear in the order they were first received"
        " and stay put",
        default=False,
    )

    show_unmatched: BoolProperty(
        name="Show Unmatched",
        description="Show parameters with no matching shape key on the"
        " assigned mesh",
        default=True,
    )


_classes = (VRCFT_ParamItem, VRCFT_Settings)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.vrcft = PointerProperty(type=VRCFT_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "vrcft"):
        del bpy.types.Scene.vrcft
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
