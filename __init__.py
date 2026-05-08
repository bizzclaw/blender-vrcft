# Blender add-on init file
# Only import submodules when running in Blender (bpy is available)
# This allows pytest to import this file without errors when running unit tests

_in_blender = False
try:
    import bpy

    # Check if this is the real Blender bpy module, not a pytest mock
    # Real bpy has specific attributes that mocks don't have
    if hasattr(bpy, "app") and hasattr(bpy.app, "version"):
        _in_blender = True
except ImportError:
    pass

if _in_blender:
    # These imports only happen when running in actual Blender
    from . import properties
    from . import operators
    from . import ui_list
    from . import panel

    _modules = (properties, ui_list, operators, panel)

    def register():
        for m in _modules:
            m.register()

    def unregister():
        for m in reversed(_modules):
            m.unregister()
else:
    # When not in Blender (e.g., during pytest), provide empty stubs
    _modules = ()

    def register():
        pass

    def unregister():
        pass
