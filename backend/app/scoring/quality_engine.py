"""
Quality and ML-readiness scoring.

Same pattern as scoring/risk_engine.py: aggregates already-computed
structured findings into a transparent 0-100 score using documented,
configurable weights. Performs no detection logic itself.
"""
from app.config import QUALITY_WEIGHTS, ML_READINESS_WEIGHTS

SEVERITY_POINTS = {"LOW": 5, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 50}


def compute_quality_score(quality_result: dict) -> dict:
    issues = quality_result["issues"]

    def bucket_penalty(issue_types):
        relevant = [i for i in issues if i["issue_type"] in issue_types]
        penalty = sum(SEVERITY_POINTS.get(i["severity"], 10) * i["confidence"] for i in relevant)
        return min(100, penalty)

    missing_penalty = bucket_penalty({"missing_values"})
    duplicate_penalty = bucket_penalty({"duplicate_rows"})
    structural_penalty = bucket_penalty({
        "whitespace", "case_inconsistency", "malformed_dates",
        "inconsistent_date_format", "constant_column", "near_constant_column",
        "high_cardinality_column",
    })
    outlier_penalty = bucket_penalty({"outliers", "possible_unit_inconsistency"})

    weighted_penalty = (
        QUALITY_WEIGHTS["missing_values"] * missing_penalty
        + QUALITY_WEIGHTS["duplicate_rows"] * duplicate_penalty
        + QUALITY_WEIGHTS["structural_issues"] * structural_penalty
        + QUALITY_WEIGHTS["outliers"] * outlier_penalty
    )
    score = round(max(0.0, min(100.0, 100 - weighted_penalty)), 2)

    return {
        "score": float(score),
        "components": {
            "missing_values_penalty": round(missing_penalty, 2),
            "duplicate_rows_penalty": round(duplicate_penalty, 2),
            "structural_issues_penalty": round(structural_penalty, 2),
            "outliers_penalty": round(outlier_penalty, 2),
        },
        "weights_used": QUALITY_WEIGHTS,
        "issue_count": len(issues),
    }


def compute_ml_readiness_score(ml_result: dict) -> dict:
    findings = ml_result["findings"]

    def bucket_penalty(checks):
        relevant = [f for f in findings if f["check"] in checks]
        penalty = sum(SEVERITY_POINTS.get(f["severity"], 10) * f["confidence"] for f in relevant)
        return min(100, penalty)

    constant_penalty = bucket_penalty({"constant_feature"})
    duplicate_penalty = bucket_penalty({"duplicate_observations"})
    cardinality_penalty = bucket_penalty({"high_cardinality_categorical"})
    sparsity_penalty = bucket_penalty({"high_sparsity"})
    correlation_penalty = bucket_penalty({
        "suspicious_correlation", "possible_target_leakage",
        "class_imbalance", "missing_target_rows", "target_not_found",
    })

    weighted_penalty = (
        ML_READINESS_WEIGHTS["constant_features"] * constant_penalty
        + ML_READINESS_WEIGHTS["duplicate_observations"] * duplicate_penalty
        + ML_READINESS_WEIGHTS["high_cardinality_features"] * cardinality_penalty
        + ML_READINESS_WEIGHTS["sparsity"] * sparsity_penalty
        + ML_READINESS_WEIGHTS["suspicious_correlation"] * correlation_penalty
    )
    score = round(max(0.0, min(100.0, 100 - weighted_penalty)), 2)

    return {
        "score": float(score),
        "components": {
            "constant_features_penalty": round(constant_penalty, 2),
            "duplicate_observations_penalty": round(duplicate_penalty, 2),
            "high_cardinality_penalty": round(cardinality_penalty, 2),
            "sparsity_penalty": round(sparsity_penalty, 2),
            "correlation_penalty": round(correlation_penalty, 2),
        },
        "weights_used": ML_READINESS_WEIGHTS,
        "finding_count": len(findings),
    }


def compute_data_health(quality_score: float, privacy_risk_score: float, ml_readiness_score: float) -> dict:
    """Composite 'Data Health' shown at the top of the dashboard. Privacy
    risk is inverted (100 - risk) so all three components share the same
    "higher is better" direction - explicitly documented so the inversion
    is never silently ambiguous to someone reading this later.

    Every value is cast to a native Python float before returning. This
    is not cosmetic: pandas/numpy scalar types (e.g. from .max()/.min()
    on a numeric column upstream in the linkage engine) can silently
    taint downstream arithmetic with numpy.float64. That type is a
    genuine subclass of Python's float so it serializes to JSON fine on
    its own - but a COMPARISON between two numpy.float64 values (e.g.
    `after_health >= before_health`) produces numpy.bool_, which is NOT
    a subclass of Python's bool and is not JSON-serializable, crashing
    any endpoint that returns it. Casting to float() here, at the single
    place these three scores are combined, stops the taint before it can
    ever reach a comparison downstream."""
    privacy_score = round(100 - float(privacy_risk_score), 2)
    composite = round((float(quality_score) + privacy_score + float(ml_readiness_score)) / 3, 2)
    return {
        "data_health": float(composite),
        "quality": float(quality_score),
        "privacy_score": float(privacy_score),
        "privacy_risk_score": float(privacy_risk_score),
        "ml_readiness": float(ml_readiness_score),
    }
