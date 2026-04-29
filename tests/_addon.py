"""Loads the (now flat) addon as a `blender_vrcft` package for tests.

The addon used to live in `blender_vrcft/`; it now sits at the repo root so a
plain GitHub source zip is install-ready in Blender. Tests still want to
`from blender_vrcft import ...`, so we synthesize that package here.
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.path.join(REPO_ROOT, "vendor") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "vendor"))

if "blender_vrcft" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "blender_vrcft",
        os.path.join(REPO_ROOT, "__init__.py"),
        submodule_search_locations=[REPO_ROOT],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["blender_vrcft"] = module
    spec.loader.exec_module(module)

import blender_vrcft  # noqa: E402,F401
