"""Canonical face-tracking parameter catalogs.

The add-on can target either VRCFaceTracking's Unified Expressions set or
Apple's ARKit 52-coefficient blendshape set *for the local avatar rig*.

Important: VRCFT's file-based avatar parser only recognizes its built-in
Unified/legacy output parameter surface. That means Blender must always
register the Unified parameter set with VRCFT, then locally translate the
incoming Unified stream onto ARKit-named shape keys when ARKit mode is
selected.

Mismatches stay harmless: anything we can't route to a shape key shows up
as an unmatched row in the live UI.
"""
from __future__ import annotations

TRACKING_PROFILE_UNIFIED = "UNIFIED"
TRACKING_PROFILE_ARKIT = "ARKIT"
DEFAULT_TRACKING_PROFILE = TRACKING_PROFILE_UNIFIED

TRACKING_PROFILE_ITEMS = (
    (
        TRACKING_PROFILE_UNIFIED,
        "Unified",
        "Use VRCFaceTracking Unified Expressions v2 plus legacy compatibility parameters",
    ),
    (
        TRACKING_PROFILE_ARKIT,
        "ARKit",
        "Use Apple's 52 ARKit blendshape coefficients",
    ),
)

# ---- v2 (Unified Expressions) parameter names ----
# Source: https://docs.vrcft.io/docs/tutorial-avatars/tutorial-avatars-extras/parameters
# These are the names sent under the ``v2/`` namespace by VRCFT.

V2_PARAMETERS: tuple[str, ...] = (
    # Eye gaze
    "EyeLeftX", "EyeLeftY", "EyeRightX", "EyeRightY",
    # Eye expression
    "EyeLidRight", "EyeLidLeft", "EyeLid",
    "EyeSquintRight", "EyeSquintLeft", "EyeSquint",
    "PupilDilation", "PupilDiameterRight", "PupilDiameterLeft", "PupilDiameter",
    # Brow
    "BrowPinchRight", "BrowPinchLeft",
    "BrowLowererRight", "BrowLowererLeft",
    "BrowInnerUpRight", "BrowInnerUpLeft",
    "BrowOuterUpRight", "BrowOuterUpLeft",
    # Nose
    "NoseSneerRight", "NoseSneerLeft",
    "NasalDilationRight", "NasalDilationLeft",
    "NasalConstrictRight", "NasalConstrictLeft",
    # Cheek
    "CheekSquintRight", "CheekSquintLeft",
    "CheekPuffSuckRight", "CheekPuffSuckLeft",
    # Jaw
    "JawOpen", "MouthClosed", "JawX", "JawZ",
    "JawClench1", "JawMandibleRaise1",
    # Lip
    "LipSuckUpperRight", "LipSuckUpperLeft",
    "LipSuckLowerRight", "LipSuckLowerLeft",
    "LipSuckCornerRight", "LipSuckCornerLeft",
    "LipFunnelUpperRight", "LipFunnelUpperLeft",
    "LipFunnelLowerRight", "LipFunnelLowerLeft",
    "LipPuckerUpperRight", "LipPuckerUpperLeft",
    "LipPuckerLowerRight", "LipPuckerLowerLeft",
    # Mouth
    "MouthUpperUpRight", "MouthUpperUpLeft",
    "MouthLowerDownRight", "MouthLowerDownLeft",
    "MouthUpperDeepenRight", "MouthUpperDeepenLeft",
    "MouthUpperX", "MouthLowerX",
    "MouthCornerPullRight", "MouthCornerPullLeft",
    "MouthCornerSlantRight", "MouthCornerSlantLeft",
    "MouthDimpleRight", "MouthDimpleLeft",
    "MouthFrownRight", "MouthFrownLeft",
    "MouthStretchRight", "MouthStretchLeft",
    "MouthRaiserUpper", "MouthRaiserLower",
    "MouthPressRight", "MouthPressLeft",
    "MouthTightenerRight", "MouthTightenerLeft",
    # Tongue
    "TongueOut", "TongueX", "TongueY", "TongueRoll",
    "TongueArchY", "TongueShape",
    "TongueTwistRight", "TongueTwistLeft",
    # Neck / throat
    "SoftPalateClose", "ThroatSwallow",
    "NeckFlexRight", "NeckFlexLeft",
)


# ---- Simplified ("legacy") parameters (no ``v2/`` prefix) ----
# These are the older simplified parameters. Some duplicate v2 names; that's
# intentional — VRCFT sends to whatever the avatar declares.

LEGACY_PARAMETERS: tuple[str, ...] = (
    # Eye gaze (combined)
    "EyeX", "EyeY",
    # Eye open/close (full / per-side)
    "EyeLid", "EyeLidLeft", "EyeLidRight",
    # Eye squint
    "EyeSquint", "EyeSquintRight", "EyeSquintLeft",
    # Pupil
    "PupilDilation", "PupilDiameter",
    # Brow simplified
    "BrowDownRight", "BrowDownLeft",
    "BrowOuterUp", "BrowInnerUp", "BrowUp",
    "BrowExpressionRight", "BrowExpressionLeft", "BrowExpression",
    # Cheek / nose simplified
    "NoseSneer",
    "CheekSquint",
    "CheekPuffSuck",
    # Jaw / mouth simplified
    "JawOpen", "JawX", "JawZ",
    "JawClench", "JawMandibleRaise",
    "MouthClosed",
    "MouthOpen", "MouthX",
    "MouthUpperUp", "MouthLowerDown",
    "MouthSmileRight", "MouthSmileLeft",
    "MouthSadRight", "MouthSadLeft",
    "SmileFrownRight", "SmileFrownLeft", "SmileFrown",
    "SmileSadRight", "SmileSadLeft", "SmileSad",
    # Lip simplified
    "LipSuckUpper", "LipSuckLower", "LipSuck",
    "LipFunnelUpper", "LipFunnelLower", "LipFunnel",
    "LipPuckerUpper", "LipPuckerLower", "LipPucker",
    # Tongue simplified
    "TongueOut",
)


# ---- Apple ARKit blendshape coefficients ----
# Source: https://developer.apple.com/documentation/arkit/arfaceanchor/blendshapelocation

ARKIT_PARAMETERS: tuple[str, ...] = (
    # Left eye
    "eyeBlinkLeft", "eyeLookDownLeft", "eyeLookInLeft",
    "eyeLookOutLeft", "eyeLookUpLeft", "eyeSquintLeft", "eyeWideLeft",
    # Right eye
    "eyeBlinkRight", "eyeLookDownRight", "eyeLookInRight",
    "eyeLookOutRight", "eyeLookUpRight", "eyeSquintRight", "eyeWideRight",
    # Jaw
    "jawForward", "jawLeft", "jawRight", "jawOpen",
    # Mouth
    "mouthClose", "mouthFunnel", "mouthPucker",
    "mouthLeft", "mouthRight",
    "mouthSmileLeft", "mouthSmileRight",
    "mouthFrownLeft", "mouthFrownRight",
    "mouthDimpleLeft", "mouthDimpleRight",
    "mouthStretchLeft", "mouthStretchRight",
    "mouthRollLower", "mouthRollUpper",
    "mouthShrugLower", "mouthShrugUpper",
    "mouthPressLeft", "mouthPressRight",
    "mouthLowerDownLeft", "mouthLowerDownRight",
    "mouthUpperUpLeft", "mouthUpperUpRight",
    # Brows, cheeks, nose
    "browDownLeft", "browDownRight", "browInnerUp",
    "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "noseSneerLeft", "noseSneerRight",
    # Tongue
    "tongueOut",
)


def normalize_tracking_profile(tracking_profile: str | None) -> str:
    """Clamp unknown profile values back to the default profile."""
    if tracking_profile == TRACKING_PROFILE_ARKIT:
        return TRACKING_PROFILE_ARKIT
    return DEFAULT_TRACKING_PROFILE


def iter_declared_parameters(
    tracking_profile: str = DEFAULT_TRACKING_PROFILE,
    address_prefix: str = "/avatar/parameters/",
) -> list[tuple[str, str]]:
    """Return ``(parameter_name, address)`` pairs for a local rig profile."""
    profile = normalize_tracking_profile(tracking_profile)
    if profile == TRACKING_PROFILE_ARKIT:
        return [(name, address_prefix + name) for name in ARKIT_PARAMETERS]

    out: list[tuple[str, str]] = []
    seen_names: set[str] = set()

    for name in V2_PARAMETERS:
        param_name = "v2_" + name
        if param_name in seen_names:
            continue
        seen_names.add(param_name)
        out.append((param_name, address_prefix + "v2/" + name))

    for name in LEGACY_PARAMETERS:
        if name in seen_names:
            continue
        seen_names.add(name)
        out.append((name, address_prefix + name))

    return out


def iter_vrcft_registration_parameters(
    address_prefix: str = "/avatar/parameters/",
) -> list[tuple[str, str]]:
    """Return the parameter surface VRCFT's avatar parser actually understands.

    Even when Blender is driving an ARKit rig locally, the avatar JSON we
    hand to VRCFT must stay on the Unified/legacy parameter surface so VRCFT
    keeps the full stream relevant and continues sending updates.
    """
    return iter_declared_parameters(TRACKING_PROFILE_UNIFIED, address_prefix)


def all_known_addresses(
    address_prefix: str = "/avatar/parameters/",
    tracking_profile: str = DEFAULT_TRACKING_PROFILE,
) -> list[str]:
    """Every OSC address the selected tracking profile might emit.

    Order is deterministic so the JSON is stable across runs. Duplicates
    are kept once.
    """
    seen: set[str] = set()
    out: list[str] = []
    for _param_name, address in iter_declared_parameters(tracking_profile, address_prefix):
        if address in seen:
            continue
        seen.add(address)
        out.append(address)
    return out
