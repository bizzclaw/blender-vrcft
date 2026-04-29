import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Object, PropertyGroup


def _poll_mesh(self, obj):
    return obj.type == 'MESH'


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
        default=0.1,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    address_prefix: StringProperty(
        name="Address Prefix",
        description="OSC address prefix to match. Trailing slash recommended",
        default="/avatar/parameters/",
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
