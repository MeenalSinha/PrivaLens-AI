"""
Privacy/utility trade-off optimizer.

For each candidate single-column transformation, measures:
  - risk reduction: drop in the % of records in equivalence classes < k=5,
    computed on the QI-column subset with just that one transform applied
  - utility loss: normalized change in column cardinality (unique_count),
    used as a simple, explainable proxy for information loss

Then ranks candidates by a configurable weighted combination and returns
the best trade-off. This is intentionally a simple, explainable heuristic
optimizer rather than a full search over combined transformation sets -
documented as such in README > Limitations.
"""
import pandas as pd

from app.mitigation.transforms import ACTION_DISPATCH
from app.privacy.k_anonymity import k_anonymity_report


def evaluate_candidate(df: pd.DataFrame, qi_columns: list, column: str, action: str) -> dict:
    fn = ACTION_DISPATCH.get(action)
    if not fn:
        return None

    before_report = k_anonymity_report(df, qi_columns, k_values=[5])
    before_risk_pct = before_report["checks"][0]["at_risk_pct"] if before_report["checks"] else 0.0
    before_unique = df[column].nunique() if column in df.columns else 0

    transformed = fn(df, column)
    remaining_qi = [c for c in qi_columns if c in transformed.columns]
    after_report = k_anonymity_report(transformed, remaining_qi, k_values=[5])
    after_risk_pct = after_report["checks"][0]["at_risk_pct"] if after_report["checks"] else 0.0
    after_unique = transformed[column].nunique() if column in transformed.columns else 0

    risk_reduction_pct = round(max(0.0, before_risk_pct - after_risk_pct), 2)
    utility_loss_pct = round(
        (1 - (after_unique / before_unique)) * 100, 2
    ) if before_unique else 0.0
    utility_loss_pct = max(0.0, utility_loss_pct)

    return {
        "column": column,
        "action": action,
        "risk_reduction_pct": risk_reduction_pct,
        "utility_loss_pct": utility_loss_pct,
        "score": round(risk_reduction_pct - utility_loss_pct, 2),
    }


def optimize(df: pd.DataFrame, mitigations: list, qi_columns: list,
             risk_weight: float = 0.6, utility_weight: float = 0.4) -> dict:
    """Scores each proposed mitigation independently and ranks them by a
    weighted combination of risk reduction and (negative) utility loss."""
    evaluations = []
    for m in mitigations:
        result = evaluate_candidate(df, qi_columns, m["column"], m["action"])
        if result:
            result["weighted_score"] = round(
                risk_weight * result["risk_reduction_pct"] - utility_weight * result["utility_loss_pct"], 2
            )
            evaluations.append(result)

    evaluations.sort(key=lambda e: e["weighted_score"], reverse=True)
    return {
        "evaluations": evaluations,
        "recommended": evaluations[0] if evaluations else None,
        "weights": {"risk_weight": risk_weight, "utility_weight": utility_weight},
    }
