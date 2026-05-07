"""Unit tests for osc_bridge module.

Tests pure functions that don't require Blender.
"""

import pytest
from blender_vrcft.osc_bridge import (
    canonical_name,
    candidate_names,
    resolve_targets,
    _normalize_arkit_name,
    _pascal_case_name,
    _identity,
    _positive_part,
    _negative_part,
    _eyelid_closed,
    _eyelid_open,
    _eyelid_wide,
    EYELID_OPEN_THRESHOLD,
)


class TestCandidateNames:
    """Tests for candidate_names generator function."""

    def test_simple_name_returns_itself(self):
        """Simple name without slashes should return just itself."""
        names = list(candidate_names("JawOpen"))
        assert names == ["JawOpen"]

    def test_v2_prefix_strip(self):
        """v2/ prefix should be stripped progressively."""
        names = list(candidate_names("v2/JawOpen"))
        assert names == ["v2/JawOpen", "JawOpen"]

    def test_multi_level_prefix_strip(self):
        """Multiple prefix levels should be stripped progressively."""
        names = list(candidate_names("FT/v2/JawOpen"))
        assert names == ["FT/v2/JawOpen", "v2/JawOpen", "JawOpen"]

    def test_deep_path_strip(self):
        """Deep path with multiple segments should strip all levels."""
        names = list(candidate_names("a/b/c/d/name"))
        assert names == ["a/b/c/d/name", "b/c/d/name", "c/d/name", "d/name", "name"]

    def test_empty_name(self):
        """Empty name should return empty string."""
        names = list(candidate_names(""))
        assert names == [""]

    def test_slash_only(self):
        """Name with only slashes should work."""
        names = list(candidate_names("a/b"))
        assert names == ["a/b", "b"]


class TestCanonicalName:
    """Tests for canonical_name function."""

    def test_direct_match(self, minimal_shape_keys):
        """Direct match should return the name with matched=True."""
        name, matched = canonical_name("JawOpen", minimal_shape_keys)
        assert name == "JawOpen"
        assert matched is True

    def test_v2_prefix_matches_base(self, minimal_shape_keys):
        """v2/ prefix should match the base shape key name."""
        name, matched = canonical_name("v2/JawOpen", minimal_shape_keys)
        assert name == "JawOpen"
        assert matched is True

    def test_ft_v2_prefix_matches_base(self, minimal_shape_keys):
        """FT/v2/ prefix should match the base shape key name."""
        name, matched = canonical_name("FT/v2/JawOpen", minimal_shape_keys)
        assert name == "JawOpen"
        assert matched is True

    def test_full_name_exact_match_wins(self, sample_shape_keys):
        """Exact full-name match should win over progressive stripping."""
        # Add a shape key with the full prefix
        sk = dict(sample_shape_keys)
        sk["FT/v2/JawOpen"] = None

        name, matched = canonical_name("FT/v2/JawOpen", sk)
        assert name == "FT/v2/JawOpen"
        assert matched is True

    def test_unmatched_returns_most_stripped(self, minimal_shape_keys):
        """Unmatched name should return the most-stripped form."""
        name, matched = canonical_name("FT/v2/NoseSneer", minimal_shape_keys)
        assert name == "NoseSneer"
        assert matched is False

    def test_none_shape_keys_dict(self):
        """None shape keys dict should return most-stripped name."""
        name, matched = canonical_name("v2/JawOpen", None)
        assert name == "JawOpen"
        assert matched is False

    def test_empty_shape_keys_dict(self):
        """Empty shape keys dict should return most-stripped name."""
        name, matched = canonical_name("v2/JawOpen", {})
        assert name == "JawOpen"
        assert matched is False

    def test_exact_match_preferred_when_both_exist(self):
        """When both v2/ and bare keys exist, exact match should win."""
        sk = {"v2/JawOpen": None, "JawOpen": None}
        name, matched = canonical_name("v2/JawOpen", sk)
        assert name == "v2/JawOpen"
        assert matched is True


class TestNormalizeArkitName:
    """Tests for _normalize_arkit_name function."""

    def test_pascal_to_camel_case(self):
        """PascalCase should be converted to camelCase."""
        assert _normalize_arkit_name("JawOpen") == "jawOpen"
        assert _normalize_arkit_name("MouthSmileLeft") == "mouthSmileLeft"

    def test_already_camel_case(self):
        """Already camelCase should stay camelCase."""
        assert _normalize_arkit_name("jawOpen") == "jawOpen"

    def test_single_char_lowercase(self):
        """Single character should be lowercased."""
        assert _normalize_arkit_name("X") == "x"

    def test_empty_string(self):
        """Empty string should return empty."""
        assert _normalize_arkit_name("") == ""

    def test_none_input(self):
        """None should return None."""
        assert _normalize_arkit_name(None) is None


class TestPascalCaseName:
    """Tests for _pascal_case_name function."""

    def test_camel_to_pascal_case(self):
        """camelCase should be converted to PascalCase."""
        assert _pascal_case_name("jawOpen") == "JawOpen"
        assert _pascal_case_name("mouthSmileLeft") == "MouthSmileLeft"

    def test_already_pascal_case(self):
        """Already PascalCase should stay PascalCase."""
        assert _pascal_case_name("JawOpen") == "JawOpen"

    def test_single_char_uppercase(self):
        """Single character should be uppercased."""
        assert _pascal_case_name("x") == "X"

    def test_empty_string(self):
        """Empty string should return empty."""
        assert _pascal_case_name("") == ""

    def test_none_input(self):
        """None should return None."""
        assert _pascal_case_name(None) is None


class TestValueTransforms:
    """Tests for value transformation functions."""

    def test_identity_clamps_to_valid_range(self):
        """Identity function should clamp to [0, 1]."""
        assert _identity(0.5) == 0.5
        assert _identity(0.0) == 0.0
        assert _identity(1.0) == 1.0
        assert _identity(-0.5) == 0.0  # Clamp negative
        assert _identity(1.5) == 1.0  # Clamp positive

    def test_positive_part_returns_positive_values(self):
        """Positive part should return positive values clamped."""
        assert _positive_part(0.6) == 0.6
        assert _positive_part(-0.6) == 0.0  # Negative becomes 0
        assert _positive_part(1.5) == 1.0  # Clamp to max

    def test_negative_part_returns_abs_negative(self):
        """Negative part should return absolute value of negative inputs."""
        assert abs(_negative_part(-0.6) - 0.6) < 1e-6
        assert _negative_part(0.6) == 0.0  # Positive becomes 0
        assert _negative_part(-1.5) == 1.0  # Clamp to max

    def test_eyelid_closed_at_zero(self):
        """Eyelid closed at v=0 should be fully closed (1.0)."""
        assert abs(_eyelid_closed(0.0) - 1.0) < 1e-6

    def test_eyelid_closed_at_threshold(self):
        """Eyelid closed at threshold should be relaxed (0.0)."""
        assert abs(_eyelid_closed(EYELID_OPEN_THRESHOLD)) < 1e-6

    def test_eyelid_closed_above_threshold(self):
        """Eyelid closed above threshold should stay 0."""
        assert abs(_eyelid_closed(0.9)) < 1e-6
        assert abs(_eyelid_closed(1.0)) < 1e-6

    def test_eyelid_closed_linear_interpolation(self):
        """Eyelid closed should interpolate linearly between 0 and threshold."""
        # At v=0.375 (half of threshold 0.75), should be 0.5
        assert abs(_eyelid_closed(0.375) - 0.5) < 1e-6

    def test_eyelid_open_at_zero(self):
        """Eyelid open at v=0 should be 0."""
        assert abs(_eyelid_open(0.0)) < 1e-6

    def test_eyelid_open_at_threshold(self):
        """Eyelid open at threshold should be fully open (1.0)."""
        assert abs(_eyelid_open(EYELID_OPEN_THRESHOLD) - 1.0) < 1e-6

    def test_eyelid_open_above_threshold(self):
        """Eyelid open above threshold should stay 1."""
        assert abs(_eyelid_open(0.9) - 1.0) < 1e-6

    def test_eyelid_open_linear_interpolation(self):
        """Eyelid open should interpolate linearly."""
        assert abs(_eyelid_open(0.375) - 0.5) < 1e-6

    def test_eyelid_wide_below_threshold(self):
        """Eyelid wide below threshold should be 0."""
        assert abs(_eyelid_wide(0.0)) < 1e-6
        assert abs(_eyelid_wide(EYELID_OPEN_THRESHOLD)) < 1e-6
        assert abs(_eyelid_wide(0.5)) < 1e-6

    def test_eyelid_wide_at_one(self):
        """Eyelid wide at v=1 should be fully wide (1.0)."""
        assert abs(_eyelid_wide(1.0) - 1.0) < 1e-6

    def test_eyelid_wide_linear_interpolation(self):
        """Eyelid wide should interpolate between threshold and 1."""
        # At v=0.875 (midpoint between 0.75 and 1.0), should be 0.5
        assert abs(_eyelid_wide(0.875) - 0.5) < 1e-6


class TestResolveTargets:
    """Tests for resolve_targets function."""

    def test_direct_match_returns_identity(self, minimal_shape_keys):
        """Direct shape key match should return identity function."""
        targets = resolve_targets("JawOpen", minimal_shape_keys)
        assert len(targets) == 1
        assert targets[0][0] == "JawOpen"
        assert targets[0][1] == _identity

    def test_unmatched_returns_empty(self, minimal_shape_keys):
        """Unmatched parameter should return empty list."""
        targets = resolve_targets("NonexistentParam", minimal_shape_keys)
        assert targets == []

    def test_none_shape_keys_returns_empty(self):
        """None shape keys dict should return empty."""
        targets = resolve_targets("JawOpen", None)
        assert targets == []

    def test_bipolar_jaw_x_positive(self, unified_shape_keys):
        """JawX positive value should drive JawRight."""
        targets = resolve_targets("JawX", unified_shape_keys)
        names = [t[0] for t in targets]
        assert "JawRight" in names

        # Positive part function should clamp positive values
        jaw_right_fn = next(t[1] for t in targets if t[0] == "JawRight")
        assert abs(jaw_right_fn(0.6) - 0.6) < 1e-6

    def test_bipolar_jaw_x_negative(self, unified_shape_keys):
        """JawX negative value should drive JawLeft."""
        targets = resolve_targets("JawX", unified_shape_keys)
        names = [t[0] for t in targets]
        assert "JawLeft" in names

        # Negative part function should return abs(negative)
        jaw_left_fn = next(t[1] for t in targets if t[0] == "JawLeft")
        assert abs(jaw_left_fn(-0.6) - 0.6) < 1e-6

    def test_bipolar_jaw_x_clamps_wrong_sign(self, unified_shape_keys):
        """Bipolar functions should clamp opposite-sign inputs."""
        targets = resolve_targets("JawX", unified_shape_keys)

        jaw_right_fn = next(t[1] for t in targets if t[0] == "JawRight")
        assert abs(jaw_right_fn(-0.6)) < 1e-6  # Negative input → 0

        jaw_left_fn = next(t[1] for t in targets if t[0] == "JawLeft")
        assert abs(jaw_left_fn(0.6)) < 1e-6  # Positive input → 0

    def test_bipolar_eye_left_x(self, unified_shape_keys):
        """EyeLeftX should map to EyeLookIn (positive) / EyeLookOut (negative)."""
        targets = resolve_targets("EyeLeftX", unified_shape_keys)
        names = [t[0] for t in targets]
        assert set(names) == {"EyeLookInLeft", "EyeLookOutLeft"}

    def test_bipolar_with_partial_targets(self):
        """Bipolar with only one side present should still work."""
        sk = {"JawRight": None}  # Only positive side
        targets = resolve_targets("JawX", sk)
        names = [t[0] for t in targets]
        assert names == ["JawRight"]

    def test_eyelid_closed_wide_combination(self, unified_shape_keys):
        """EyeLid should split into closed + wide shapes."""
        targets = resolve_targets("EyeLidLeft", unified_shape_keys)
        names = [t[0] for t in targets]
        assert "EyeClosedLeft" in names
        assert "EyeWideLeft" in names

    def test_eyelid_open_wide_combination(self):
        """EyeLid with EyeOpen should split into open + wide."""
        sk = {"EyeOpenLeft": None, "EyeWideLeft": None}
        targets = resolve_targets("EyeLidLeft", sk)
        names = [t[0] for t in targets]
        assert set(names) == {"EyeOpenLeft", "EyeWideLeft"}

    def test_smile_frown_bipolar(self):
        """SmileFrown should split into pull + frown."""
        sk = {
            "MouthCornerPullLeft": None,
            "MouthFrownLeft": None,
            "MouthCornerSlantLeft": None,
        }
        targets = resolve_targets("SmileFrownLeft", sk)
        names = sorted([t[0] for t in targets])
        expected = sorted(
            [
                "MouthCornerPullLeft",
                "MouthCornerSlantLeft",
                "MouthFrownLeft",
            ]
        )
        assert names == expected

    def test_unipolar_mouth_open(self):
        """MouthOpen should fan out to multiple shape keys."""
        sk = {
            "MouthUpperUpLeft": None,
            "MouthUpperUpRight": None,
            "MouthLowerDownLeft": None,
            "MouthLowerDownRight": None,
        }
        targets = resolve_targets("MouthOpen", sk)
        names = sorted([t[0] for t in targets])
        expected = sorted(list(sk.keys()))
        assert names == expected

    def test_arkit_direct_match(self, arkit_shape_keys):
        """ARKit mode should match camelCase shape keys."""
        targets = resolve_targets("JawOpen", arkit_shape_keys, tracking_profile="ARKIT")
        assert len(targets) == 1
        assert targets[0][0] == "jawOpen"

    def test_arkit_pascal_to_camel_conversion(self, arkit_shape_keys):
        """PascalCase input in ARKit mode should convert to camelCase."""
        targets = resolve_targets("MouthSmileLeft", arkit_shape_keys, tracking_profile="ARKIT")
        assert len(targets) == 1
        assert targets[0][0] == "mouthSmileLeft"

    def test_arkit_bipolar_eyelid(self, arkit_shape_keys):
        """ARKit EyeLid should map to blink + wide."""
        targets = resolve_targets("EyeLidLeft", arkit_shape_keys, tracking_profile="ARKIT")
        names = [t[0] for t in targets]
        assert set(names) == {"eyeBlinkLeft", "eyeWideLeft"}

    def test_arkit_blink_value_mapping(self, arkit_shape_keys):
        """ARKit blink function should map values correctly."""
        targets = resolve_targets("EyeLidLeft", arkit_shape_keys, tracking_profile="ARKIT")
        blink_fn = next(t[1] for t in targets if t[0] == "eyeBlinkLeft")

        # At v=0 (fully closed), blink should be 1.0
        assert abs(blink_fn(0.0) - 1.0) < 1e-6
        # At threshold, blink should be 0
        assert abs(blink_fn(EYELID_OPEN_THRESHOLD)) < 1e-6

    def test_arkit_wide_value_mapping(self, arkit_shape_keys):
        """ARKit wide function should map values correctly."""
        targets = resolve_targets("EyeLidLeft", arkit_shape_keys, tracking_profile="ARKIT")
        wide_fn = next(t[1] for t in targets if t[0] == "eyeWideLeft")

        # Below threshold should be 0
        assert abs(wide_fn(0.5)) < 1e-6
        # At v=0.9 should be (0.9 - 0.75) / 0.25 = 0.6
        assert abs(wide_fn(0.9) - 0.6) < 1e-6

    def test_priority_direct_match_over_bipolar(self):
        """Direct match should win over bipolar mapping."""
        # If JawX exists as a shape key, it should be driven directly
        # rather than being treated as a bipolar parameter
        sk = {"JawX": None, "JawRight": None}
        targets = resolve_targets("JawX", sk)
        assert len(targets) == 1
        assert targets[0][0] == "JawX"
        assert targets[0][1] == _identity
