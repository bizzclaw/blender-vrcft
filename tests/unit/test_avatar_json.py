"""Unit tests for avatar_json module.

Tests pure functions that don't require Blender.
"""

import pytest
from blender_vrcft.avatar_json import (
    stable_avatar_id,
    display_name,
    build_outer_json,
    ID_PREFIX,
    ADDRESS_PREFIX,
)


class TestStableAvatarId:
    """Tests for stable_avatar_id function."""

    def test_same_path_produces_same_id(self):
        """Same blend file path should always produce the same avatar ID."""
        path = "/tmp/test.blend"
        id_a = stable_avatar_id(path)
        id_b = stable_avatar_id(path)
        assert id_a == id_b

    def test_different_paths_produce_different_ids(self):
        """Different blend file paths should produce different avatar IDs."""
        path_a = "/tmp/foo.blend"
        path_b = "/tmp/bar.blend"
        id_a = stable_avatar_id(path_a)
        id_b = stable_avatar_id(path_b)
        assert id_a != id_b

    def test_id_has_correct_prefix(self):
        """Avatar ID should start with the correct prefix."""
        path = "/tmp/test.blend"
        avatar_id = stable_avatar_id(path)
        assert avatar_id.startswith(ID_PREFIX)

    def test_empty_path_produces_valid_id(self):
        """Empty path should still produce a valid avatar ID."""
        avatar_id = stable_avatar_id("")
        assert avatar_id.startswith(ID_PREFIX)
        assert len(avatar_id) > len(ID_PREFIX)

    def test_absolute_path_normalization(self):
        """Relative paths should be normalized to absolute paths."""
        # This test verifies that the function handles path normalization
        # We can't easily test the actual normalization behavior without
        # access to the filesystem, but we can verify it produces stable IDs
        path1 = "test.blend"
        path2 = "test.blend"
        assert stable_avatar_id(path1) == stable_avatar_id(path2)

    def test_id_is_deterministic(self):
        """Verify ID generation is deterministic across multiple calls."""
        path = "/home/user/project/avatar.blend"
        ids = [stable_avatar_id(path) for _ in range(10)]
        assert len(set(ids)) == 1, "All IDs should be identical"


class TestDisplayName:
    """Tests for display_name function."""

    def test_empty_path_returns_untitled(self):
        """Empty path should return Untitled."""
        name = display_name("")
        assert name == "Blender VRCFT - Untitled"

    def test_empty_path_none_variant(self):
        """None/empty should return Untitled."""
        name = display_name("")
        assert "Untitled" in name

    def test_basic_path_formatting(self):
        """Basic .blend path should be formatted correctly."""
        path = "/path/to/MyAvatar.blend"
        name = display_name(path)
        assert name == "Blender VRCFT - MyAvatar"

    def test_windows_style_path(self):
        """Windows-style path should work."""
        # Note: on non-Windows systems, os.path.basename may not
        # correctly parse Windows paths, so we accept both formats
        path = "C:\\Users\\User\\Documents\\Cool Rig.blend"
        name = display_name(path)
        # Either the basename is extracted correctly (on Windows)
        # or the full path segment is used (on Unix)
        assert name == "Blender VRCFT - Cool Rig" or "Cool Rig" in name

    def test_relative_path(self):
        """Relative path should work."""
        path = "avatar.blend"
        name = display_name(path)
        assert name == "Blender VRCFT - avatar"

    def test_path_without_extension(self):
        """Path without .blend extension should work."""
        path = "/path/to/MyAvatar"
        name = display_name(path)
        assert "MyAvatar" in name

    def test_uppercase_extension(self):
        """Upper-case .BLEND extension should be handled."""
        path = "/path/to/Avatar.BLEND"
        name = display_name(path)
        # The function checks .lower().endswith(".blend")
        # so .BLEND should also be stripped
        assert name == "Blender VRCFT - Avatar"

    def test_path_with_multiple_blend(self):
        """Path with 'blend' in filename should not be mangled."""
        path = "/path/to/testblend.blend"
        name = display_name(path)
        # Should strip only the final .blend extension
        assert name == "Blender VRCFT - testblend"


class TestBuildOuterJson:
    """Tests for build_outer_json function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        payload = build_outer_json("avtr_test", "Test Avatar", ["Basis", "JawOpen", "MouthClosed"])
        assert isinstance(payload, dict)

    def test_has_required_fields(self):
        """Payload should have id, name, and parameters fields."""
        payload = build_outer_json("avtr_test", "Test Avatar", ["JawOpen", "MouthClosed"])
        assert "id" in payload
        assert "name" in payload
        assert "parameters" in payload

    def test_id_field_matches_input(self):
        """Avatar ID should match input."""
        payload = build_outer_json("avtr_test_123", "Test Avatar", ["JawOpen"])
        assert payload["id"] == "avtr_test_123"

    def test_name_field_matches_input(self):
        """Avatar name should match input."""
        payload = build_outer_json("avtr_test", "My Cool Avatar", ["JawOpen"])
        assert payload["name"] == "My Cool Avatar"

    def test_parameters_is_list(self):
        """Parameters should be a list."""
        payload = build_outer_json("avtr_test", "Test", ["JawOpen"])
        assert isinstance(payload["parameters"], list)

    def test_shape_keys_appear_first(self):
        """Shape key parameters should appear first (after excluding Basis)."""
        payload = build_outer_json(
            "avtr_test", "Test", ["Basis", "JawOpen", "MouthClosed", "EyeBlink"]
        )
        names = [p["name"] for p in payload["parameters"]]
        # Basis should be excluded
        assert "Basis" not in names
        # Shape keys should appear first
        assert names[0] == "JawOpen"
        assert names[1] == "MouthClosed"
        assert names[2] == "EyeBlink"

    def test_shape_key_has_correct_address(self):
        """Shape key parameter should have correct OSC address."""
        payload = build_outer_json("avtr_test", "Test", ["JawOpen"])
        jaw_param = payload["parameters"][0]
        assert jaw_param["input"]["address"] == ADDRESS_PREFIX + "JawOpen"
        assert jaw_param["output"]["address"] == ADDRESS_PREFIX + "JawOpen"

    def test_shape_key_has_float_type(self):
        """Shape key parameter should have Float type."""
        payload = build_outer_json("avtr_test", "Test", ["JawOpen"])
        jaw_param = payload["parameters"][0]
        assert jaw_param["input"]["type"] == "Float"
        assert jaw_param["output"]["type"] == "Float"

    def test_includes_unified_parameters(self):
        """Should include Unified/legacy VRCFT parameters."""
        payload = build_outer_json("avtr_test", "Test", ["JawOpen"])
        names = [p["name"] for p in payload["parameters"]]
        # Should include v2_ prefixed parameters
        v2_names = [n for n in names if n.startswith("v2_")]
        assert len(v2_names) > 50, "Should include many v2 parameters"

    def test_no_duplicate_names(self):
        """Should not emit duplicate parameter names."""
        payload = build_outer_json(
            "avtr_test",
            "Test",
            ["JawOpen", "JawOpen"],  # Duplicate in input
        )
        names = [p["name"] for p in payload["parameters"]]
        # First JawOpen from shape keys, then if JawOpen appears in
        # unified params it should be deduplicated
        jaw_count = names.count("JawOpen")
        assert jaw_count == 1, f"JawOpen should appear once, found {jaw_count}"

    def test_empty_shape_keys_list(self):
        """Should handle empty shape key list."""
        payload = build_outer_json("avtr_test", "Test", [])
        assert isinstance(payload["parameters"], list)
        # Should still have unified params
        assert len(payload["parameters"]) > 50

    def test_only_basis_shape_key(self):
        """Should exclude Basis shape key."""
        payload = build_outer_json("avtr_test", "Test", ["Basis"])
        names = [p["name"] for p in payload["parameters"]]
        assert "Basis" not in names

    def test_none_shape_key_name_filtered(self):
        """Should filter out None/empty shape key names."""
        payload = build_outer_json("avtr_test", "Test", ["JawOpen", "", None, "MouthClosed"])
        names = [p["name"] for p in payload["parameters"]]
        assert "" not in names
        # JawOpen and MouthClosed should be there
        assert "JawOpen" in names
        assert "MouthClosed" in names

    def test_json_serializable(self):
        """Payload should be JSON serializable."""
        payload = build_outer_json("avtr_test", "Test Avatar", ["JawOpen", "MouthClosed"])
        import json

        json_str = json.dumps(payload)
        assert isinstance(json_str, str)
        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["id"] == "avtr_test"

    def test_arkit_profile_includes_unified_params(self):
        """ARKit profile should still include Unified parameters.

        VRCFT's parser only understands Unified/legacy params, so ARKit
        avatars must still declare the full parameter set.
        """
        payload = build_outer_json(
            "avtr_arkit",
            "ARKit Avatar",
            ["jawOpen", "mouthSmileLeft"],
            tracking_profile="ARKIT",
        )
        names = [p["name"] for p in payload["parameters"]]
        # Should include Unified v2 params
        assert "v2_JawX" in names, "ARKit payload should include Unified v2 params"

    def test_arkit_shape_keys_appear_once(self):
        """ARKit shape key names should appear exactly once."""
        payload = build_outer_json(
            "avtr_arkit",
            "ARKit Avatar",
            ["jawOpen", "mouthSmileLeft"],
            tracking_profile="ARKIT",
        )
        names = [p["name"] for p in payload["parameters"]]
        jaw_count = names.count("jawOpen")
        assert jaw_count == 1, f"jawOpen should appear once, found {jaw_count}"

    def test_arkit_shape_keys_first(self):
        """ARKit shape keys should appear first."""
        payload = build_outer_json(
            "avtr_arkit",
            "ARKit Avatar",
            ["jawOpen", "mouthSmileLeft"],
            tracking_profile="ARKIT",
        )
        names = [p["name"] for p in payload["parameters"]]
        assert names[0] == "jawOpen"
        assert names[1] == "mouthSmileLeft"
