"""
Policy engine: classifies every proposed fix action as AUTO, REVIEW, or
BLOCK using the deterministic table in app.config.RESCUE_POLICY. This is
intentionally the only place that decision is made - the orchestrator
must consult this module rather than hardcoding policy inline, so the
policy stays auditable and cannot silently drift out of sync with what's
documented in README/AUDIT_RESCUE.md.
"""
from app.config import RESCUE_POLICY, RESCUE_ALTERNATIVES


def classify_action(action_type: str) -> str:
    """Returns AUTO, REVIEW, or BLOCK. Unknown action types default to
    REVIEW (never AUTO) - an unrecognized action is never assumed safe."""
    return RESCUE_POLICY.get(action_type, "REVIEW")


def build_proposed_action(source: str, issue_or_mitigation: dict, action_type: str,
                           expected_benefit: str, params: dict) -> dict:
    """Wraps a raw quality-issue or privacy-mitigation dict into a
    standard 'proposed action' shape the orchestrator and API share."""
    return {
        "action_id": None,  # assigned by the orchestrator when queued
        "source": source,   # "quality" | "privacy"
        "action_type": action_type,
        "column": params.get("column"),
        "params": params,
        "policy": classify_action(action_type),
        "description": issue_or_mitigation.get("description") or issue_or_mitigation.get("suggested_action", ""),
        "reason": issue_or_mitigation.get("reason", issue_or_mitigation.get("description", "")),
        "expected_benefit": expected_benefit,
        "status": "pending",  # pending | approved | rejected | applied | skipped
    }


def milder_alternative(action_type: str, params: dict):
    """Returns a milder variant of the given action if one is defined, or
    None if no documented alternative exists for this action type. This
    is a real, narrow implementation of 'the agent reconsiders
    alternatives after rejection' - not a general search, just the one
    concrete case (pincode truncation) documented in config.py."""
    alt = RESCUE_ALTERNATIVES.get(action_type)
    if not alt:
        return None
    new_params = {**params, **alt}
    return new_params
