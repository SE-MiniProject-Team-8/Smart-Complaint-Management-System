"""RoutingPolicy (C05): pure routing decisions with no persistent state.

Centralizing these rules means the escalation hierarchy can change in one
place (NFR-MAIN-01) and the Dean ceiling is enforced everywhere.
"""
from .errors import AppError, conflict

LEVEL_FACULTY = 1
LEVEL_COMMITTEE = 2
LEVEL_DEAN = 3

SEVERITIES = ("Low", "Medium", "High")

ROLE_TO_LEVEL = {"Faculty": LEVEL_FACULTY, "Committee": LEVEL_COMMITTEE, "Dean": LEVEL_DEAN}
LEVEL_TO_ROLE = {level: role for role, level in ROLE_TO_LEVEL.items()}

# Human-readable queue names used in API responses and the UI.
LEVEL_TO_DISPLAY = {
    LEVEL_FACULTY: "Faculty-in-Charge",
    LEVEL_COMMITTEE: "Grievance Committee",
    LEVEL_DEAN: "Dean",
}


def initial_level(severity):
    """REQ-3.1 / REQ-3.2: Low and Medium go to L1; High goes to L2."""
    if severity not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {severity!r}")
    return LEVEL_COMMITTEE if severity == "High" else LEVEL_FACULTY


def next_level(level):
    """REQ-4.3: L1 -> L2 -> L3. Escalation above the Dean is rejected."""
    if level >= LEVEL_DEAN:
        raise conflict("ESCALATION_LIMIT",
                       "Escalation ceiling reached. The Dean cannot escalate further.")
    return level + 1


def appeal_target(rejected_level):
    """REQ-5.x: appeal goes one level above the rejecting level; a Dean rejection
    stays at L3 and is flagged for final review.

    Returns (target_level, final_review).
    """
    if rejected_level >= LEVEL_DEAN:
        return LEVEL_DEAN, True
    return rejected_level + 1, False


def display_name(level):
    return LEVEL_TO_DISPLAY[level]


__all__ = [
    "AppError", "LEVEL_FACULTY", "LEVEL_COMMITTEE", "LEVEL_DEAN", "SEVERITIES",
    "ROLE_TO_LEVEL", "LEVEL_TO_ROLE", "initial_level", "next_level", "appeal_target",
    "display_name",
]
