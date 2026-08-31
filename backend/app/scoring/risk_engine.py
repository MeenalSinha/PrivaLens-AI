"""
Re-identification risk scoring engine.

Combines signals from the k-anonymity/uniqueness engine and the linkage
attack engine into a single 0-100 risk score, using the documented,
configurable weights in app.config.RISK_WEIGHTS. This module performs no
attack or profiling logic itself - it only aggregates already-computed
structured findings, keeping the scoring transparent and auditable.
"""
from app.config import RISK_WEIGHTS, RISK_BANDS


def _band_for_score(score: float) -> str:
    for lo, hi, label in RISK_BANDS:
        if lo <= score < hi:
            return label
    return "CRITICAL"


def compute_risk_score(uniqueness: dict, k_anon: dict, linkage: dict,
                        sensitive_exposure_pct: float, weights=None) -> dict:
    weights = weights or RISK_WEIGHTS

    # 1. linkage confidence component (0-100)
    linkage_component = round((linkage.get("highest_confidence") or 0.0) * 100, 2)

    # 2. uniqueness component (0-100) - % of records in equivalence classes of size 1
    uniqueness_component = round(uniqueness.get("unique_pct") or 0.0, 2)

    # 3. equivalence-class risk - use the k=5 check as the representative
    #    "practical" threshold; % of records violating k=5.
    k5 = next((c for c in k_anon.get("checks", []) if c["k"] == 5), None)
    equivalence_component = round(k5["at_risk_pct"], 2) if k5 else uniqueness_component

    # 4. sensitive attribute exposure - passed in directly (from l-diversity or
    #    simply the proportion of sensitive columns present)
    sensitive_component = round(sensitive_exposure_pct, 2)

    overall = (
        weights["linkage_confidence"] * linkage_component
        + weights["uniqueness"] * uniqueness_component
        + weights["equivalence_class_risk"] * equivalence_component
        + weights["sensitive_attribute_exposure"] * sensitive_component
    )
    overall = round(min(100.0, max(0.0, overall)), 2)

    return {
        "overall_score": overall,
        "risk_level": _band_for_score(overall),
        "components": {
            "linkage_confidence": linkage_component,
            "uniqueness": uniqueness_component,
            "equivalence_class_risk": equivalence_component,
            "sensitive_attribute_exposure": sensitive_component,
        },
        "weights_used": weights,
        "at_risk_records": k5["at_risk_records"] if k5 else uniqueness.get("unique_records", 0),
        "min_class_size": k_anon.get("min_class_size"),
    }


def explain_record_risk(match: dict) -> dict:
    """Builds a human-readable 'Why is this HIGH RISK' explanation for a
    single matched record pair, grounded entirely in the structured
    attribute-level scores already computed by the linkage engine."""
    factors = []
    for col, info in match["matching_attributes"].items():
        score = info["score"]
        if score >= 0.85:
            factors.append(f"{col}: strong match ({info['kind']}, score {score})")
        elif score >= 0.5:
            factors.append(f"{col}: partial match ({info['kind']}, score {score})")
        else:
            factors.append(f"{col}: weak/no match ({info['kind']}, score {score})")

    return {
        "risk_level": match["risk_level"],
        "overall_linkage_confidence": match["match_probability"],
        "contributing_factors": factors,
    }
