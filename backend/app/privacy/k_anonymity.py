"""
Real k-anonymity, uniqueness and l-diversity computation.

All numbers here come from actual groupby operations on the dataframe -
none of it is fabricated. This is the statistical core the rest of the
product (risk scoring, mitigation, re-test) builds on.
"""
import pandas as pd

from app.config import K_VALUES


def _equivalence_classes(df: pd.DataFrame, qi_columns: list) -> pd.Series:
    """Returns the size of the equivalence class each row belongs to,
    based on the given quasi-identifier columns."""
    if not qi_columns:
        return pd.Series([len(df)] * len(df), index=df.index)
    sub = df[qi_columns].astype(str).fillna("__MISSING__")
    class_sizes = sub.groupby(qi_columns).transform("size")
    return class_sizes if isinstance(class_sizes, pd.Series) else class_sizes.iloc[:, 0]


def uniqueness_analysis(df: pd.DataFrame, qi_columns: list) -> dict:
    n = len(df)
    if n == 0 or not qi_columns:
        return {
            "qi_columns": qi_columns,
            "equivalence_classes": 0,
            "unique_records": 0,
            "unique_pct": 0.0,
            "class_size_distribution": {},
        }

    class_sizes = _equivalence_classes(df, qi_columns)
    n_classes = int(df[qi_columns].astype(str).fillna("__MISSING__").drop_duplicates().shape[0])
    unique_records = int((class_sizes == 1).sum())

    # distribution buckets
    buckets = {"1": 0, "2-4": 0, "5-9": 0, "10-49": 0, "50+": 0}
    for size in class_sizes:
        if size == 1:
            buckets["1"] += 1
        elif size <= 4:
            buckets["2-4"] += 1
        elif size <= 9:
            buckets["5-9"] += 1
        elif size <= 49:
            buckets["10-49"] += 1
        else:
            buckets["50+"] += 1

    return {
        "qi_columns": qi_columns,
        "equivalence_classes": n_classes,
        "unique_records": unique_records,
        "unique_pct": round((unique_records / n) * 100, 2),
        "class_size_distribution": buckets,
    }


def k_anonymity_report(df: pd.DataFrame, qi_columns: list, k_values=None) -> dict:
    """Computes minimum class size and at-risk record counts for each
    requested k threshold. Never hardcoded - derived from real groupby."""
    k_values = k_values or K_VALUES
    n = len(df)
    if n == 0 or not qi_columns:
        return {"qi_columns": qi_columns, "min_class_size": None, "checks": []}

    class_sizes = _equivalence_classes(df, qi_columns)
    min_class_size = int(class_sizes.min())

    checks = []
    for k in k_values:
        at_risk = int((class_sizes < k).sum())
        checks.append({
            "k": k,
            "at_risk_records": at_risk,
            "at_risk_pct": round((at_risk / n) * 100, 2),
            "satisfies_k_anonymity": at_risk == 0,
        })

    return {
        "qi_columns": qi_columns,
        "total_records": n,
        "min_class_size": min_class_size,
        "checks": checks,
    }


def l_diversity_report(df: pd.DataFrame, qi_columns: list, sensitive_column: str) -> dict:
    """For each equivalence class defined by qi_columns, counts the number
    of distinct sensitive-attribute values (distinct l). Low l means an
    attacker who narrows a victim to that class can still infer the
    sensitive value with high confidence."""
    if not qi_columns or sensitive_column not in df.columns:
        return {"qi_columns": qi_columns, "sensitive_column": sensitive_column, "min_l": None, "classes": []}

    sub = df[qi_columns + [sensitive_column]].astype(str).fillna("__MISSING__")
    grouped = sub.groupby(qi_columns)[sensitive_column].nunique().reset_index(name="distinct_l")
    grouped_size = sub.groupby(qi_columns).size().reset_index(name="class_size")
    merged = grouped.merge(grouped_size, on=qi_columns)

    min_l = int(merged["distinct_l"].min()) if not merged.empty else None
    low_diversity_classes = merged[merged["distinct_l"] == 1]

    return {
        "qi_columns": qi_columns,
        "sensitive_column": sensitive_column,
        "min_l": min_l,
        "classes_with_l1": int(len(low_diversity_classes)),
        "records_at_risk": int(low_diversity_classes["class_size"].sum()) if not low_diversity_classes.empty else 0,
        "total_classes": int(len(merged)),
    }
