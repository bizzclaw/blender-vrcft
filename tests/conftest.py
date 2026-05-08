"""pytest configuration and shared fixtures for unit tests.

This conftest provides fixtures for testing pure functions that don't
require Blender. Integration tests that need Blender should use the
phase*_smoke.py scripts instead.
"""

import importlib.util
import os
import sys
from types import ModuleType
import pytest


# Pytest hook to prevent treating the project root __init__.py as a test module
def pytest_ignore_collect(collection_path, config):
    """Ignore the project root __init__.py file (Blender add-on init, not Python package)."""
    # Skip the project root __init__.py which is a Blender add-on init file
    if collection_path.name == "__init__.py":
        # Check if this is the project root init file
        if collection_path.parent == config.rootpath:
            return True  # Ignore this file
    return False  # Don't ignore other files


# Mock bpy module so we can import blender_vrcft modules without Blender
# Create this BEFORE any test imports happen
if "bpy" not in sys.modules:
    # Create a minimal mock for bpy that allows imports to succeed
    # This is only for unit tests - integration tests use real Blender

    def make_property_class(name):
        """Create a mock property class."""

        def property_factory(**kwargs):
            return None

        property_factory.__name__ = name
        return property_factory

    # Create bpy.props submodule
    bpy_props = ModuleType("bpy.props")
    bpy_props.FloatProperty = make_property_class("FloatProperty")
    bpy_props.IntProperty = make_property_class("IntProperty")
    bpy_props.StringProperty = make_property_class("StringProperty")
    bpy_props.BoolProperty = make_property_class("BoolProperty")
    bpy_props.EnumProperty = make_property_class("EnumProperty")
    bpy_props.CollectionProperty = make_property_class("CollectionProperty")
    bpy_props.PointerProperty = make_property_class("PointerProperty")

    # Create bpy.types submodule
    bpy_types = ModuleType("bpy.types")
    bpy_types.PropertyGroup = type("PropertyGroup", (), {})
    bpy_types.Object = type("Object", (), {})
    bpy_types.Mesh = type("Mesh", (), {})
    bpy_types.Armature = type("Armature", (), {})
    bpy_types.UIList = type("UIList", (), {})
    bpy_types.Panel = type("Panel", (), {})
    bpy_types.Operator = type("Operator", (), {})

    # Create bpy module
    bpy = ModuleType("bpy")
    bpy.props = bpy_props
    bpy.types = bpy_types

    # Create minimal context and data mocks
    bpy.context = type("context", (), {"scene": None})()
    bpy.data = type("data", (), {"objects": {}, "meshes": {}, "armatures": {}})()

    # Mock ops module
    class MockOps:
        @staticmethod
        def wm_read_factory_settings(**kwargs):
            return {"FINISHED"}

        class vrcft:
            @staticmethod
            def start_test():
                return {"FINISHED"}

            @staticmethod
            def stop_test():
                return {"FINISHED"}

            @staticmethod
            def start_capture():
                return {"FINISHED"}

            @staticmethod
            def stop_capture():
                return {"FINISHED"}

            @staticmethod
            def start_session():
                return {"FINISHED"}

            @staticmethod
            def stop_session():
                return {"FINISHED"}

            @staticmethod
            def clear_params():
                return {"FINISHED"}

    bpy.ops = MockOps()

    # Register modules in sys.modules
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy_props
    sys.modules["bpy.types"] = bpy_types

# Add project root to Python path so blender_vrcft module can be imported
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add vendor path for pythonosc
vendor_path = os.path.join(project_root, "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

# Create the blender_vrcft package structure without loading __init__.py
# This allows modules to use relative imports
if "blender_vrcft" not in sys.modules:
    # Create the package container
    blender_vrcft = ModuleType("blender_vrcft")
    blender_vrcft.__path__ = [project_root]  # This makes it a package
    sys.modules["blender_vrcft"] = blender_vrcft

    # Load submodules individually
    def load_module(name, path):
        """Load a module from file path and register it under blender_vrcft."""
        full_name = f"blender_vrcft.{name}"
        spec = importlib.util.spec_from_file_location(full_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        setattr(blender_vrcft, name, module)
        spec.loader.exec_module(module)
        return module

    # Load unified_expressions first (no dependencies)
    load_module("unified_expressions", os.path.join(project_root, "unified_expressions.py"))

    # Load avatar_json (depends on unified_expressions)
    load_module("avatar_json", os.path.join(project_root, "avatar_json.py"))

    # Load osc_bridge (depends on unified_expressions)
    load_module("osc_bridge", os.path.join(project_root, "osc_bridge.py"))


# ============================================
# Test fixtures
# ============================================


@pytest.fixture
def sample_shape_keys():
    """Provide a dictionary of sample shape key names (as strings, not Blender objects).

    This fixture allows unit tests to test shape-key matching logic without
    needing actual Blender mesh objects.
    """
    return {
        "JawOpen": None,
        "JawLeft": None,
        "JawRight": None,
        "MouthClosed": None,
        "MouthUpperLeft": None,
        "MouthUpperRight": None,
        "MouthLowerLeft": None,
        "MouthLowerRight": None,
        "EyeLookInLeft": None,
        "EyeLookOutLeft": None,
        "EyeLookInRight": None,
        "EyeLookOutRight": None,
        "EyeLookUpLeft": None,
        "EyeLookDownLeft": None,
        "EyeClosedLeft": None,
        "EyeClosedRight": None,
        "EyeOpenLeft": None,
        "EyeOpenRight": None,
        "EyeWideLeft": None,
        "EyeWideRight": None,
        "MouthCornerPullLeft": None,
        "MouthCornerPullRight": None,
        "MouthFrownLeft": None,
        "MouthFrownRight": None,
        "TongueOut": None,
        # ARKit-style names
        "jawOpen": None,
        "mouthSmileLeft": None,
        "eyeBlinkLeft": None,
        "eyeWideLeft": None,
    }


@pytest.fixture
def minimal_shape_keys():
    """Minimal shape key set for simple tests."""
    return {
        "JawOpen": None,
        "MouthClosed": None,
    }


@pytest.fixture
def arkit_shape_keys():
    """ARKit-style shape key set."""
    return {
        "jawOpen": None,
        "mouthSmileLeft": None,
        "mouthSmileRight": None,
        "eyeBlinkLeft": None,
        "eyeBlinkRight": None,
        "eyeWideLeft": None,
        "eyeWideRight": None,
        "eyeLookDownLeft": None,
        "eyeLookDownRight": None,
        "eyeLookInLeft": None,
        "eyeLookInRight": None,
        "eyeLookOutLeft": None,
        "eyeLookOutRight": None,
        "eyeLookUpLeft": None,
        "eyeLookUpRight": None,
    }


@pytest.fixture
def unified_shape_keys():
    """Unified-style shape key set with bipolar split keys."""
    return {
        "JawOpen": None,
        "JawLeft": None,
        "JawRight": None,
        "EyeLookInLeft": None,
        "EyeLookOutLeft": None,
        "EyeClosedLeft": None,
        "EyeWideLeft": None,
        "MouthCornerPullLeft": None,
        "MouthFrownLeft": None,
    }
