"""Canonical Unified Expressions parameter list for VRCFaceTracking.

VRCFT only sends OSC for parameters declared in the avatar JSON it loads.
If we declare only the avatar's literal shape-key names, VRCFT will skip
anything bipolar / simplified / composite — even if our ``tick()`` knows
how to decompose those into shape keys.

Declaring every UE parameter we recognize lets VRCFT pump the full
"50 v2 + 48 legacy" stream at us. Mismatches stay harmless: anything we
can't route to a shape key shows up as an unmatched row in the live UI.
"""
from __future__ import annotations

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


def all_known_addresses(address_prefix: str = "/avatar/parameters/") -> list[str]:
    """Every OSC address VRCFT might emit, with both v2 and legacy names.

    Order is deterministic so the JSON is stable across runs. Duplicates
    (legacy names that match v2 names like ``JawOpen``) are kept once.
    """
    seen = set()
    out: list[str] = []
    for n in V2_PARAMETERS:
        addr = address_prefix + "v2/" + n
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    for n in LEGACY_PARAMETERS:
        addr = address_prefix + n
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out
