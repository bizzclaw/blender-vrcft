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
