"""
ML Readiness Agent.

Deterministic checks for whether a dataset is suitable for training a
model on. Target-column-specific checks (class imbalance, missing-target
rows, target leakage) only run when a target_column is explicitly
provided - this build does NOT guess which column is the target, since
that would be exactly the kind of invented result the architecture
principle forbids.

Implemented: constant features, duplicate observations, high-cardinality
categorical features, sparsity (overall missingness), suspicious
numeric-numeric correlations (possible redundant/leaked features).
Implemented only when target_column is given: class imbalance, missing-
target rows, near-perfect single-feature correlation with the target
(a proxy for leakage - not a guarantee of it, always labeled as such).

Explicitly NOT implemented: train/test contamination detection (requires
a train/test split to be provided, which this build doesn't accept as
input), automated target-column inference.
"""
import numpy as np
import pandas as pd

from app.config import CORRELATION_LEAKAGE_THRESHOLD


def _finding(check, severity, columns, description, confidence):
    return {"check": check, "severity": severity, "columns": columns,
            "description": description, "confidence": confidence}


def check_constant_features(df: pd.DataFrame) -> list:
    findings = []
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 1:
            findings.append(_finding(
                "constant_feature", "MEDIUM", [col],
                f"'{col}' has zero variance - useless as a model feature.",
                1.0,
            ))
    return findings


def check_duplicate_observations(df: pd.DataFrame) -> list:
    n_dupes = int(df.duplicated().sum())
    if n_dupes == 0:
        return []
    pct = round(n_dupes / len(df) * 100, 2) if len(df) else 0
    return [_finding(
        "duplicate_observations", "MEDIUM" if pct > 5 else "LOW", [],
        f"{n_dupes} duplicate rows ({pct}%) would let the same observation "
        f"leak across a train/test split if not deduplicated first.",
        1.0,
    )]


def check_high_cardinality_categoricals(df: pd.DataFrame) -> list:
    findings = []
    n = len(df)
    if n == 0:
        return findings
    for col in df.select_dtypes(include="object").columns:
        ratio = df[col].nunique(dropna=True) / n
        if ratio > 0.5:
            findings.append(_finding(
                "high_cardinality_categorical", "LOW", [col],
                f"'{col}' is {round(ratio*100,1)}% unique - one-hot encoding it "
                f"would explode dimensionality; consider hashing, embeddings, or dropping it.",
                0.8,
            ))
    return findings


def check_sparsity(df: pd.DataFrame) -> list:
    if df.size == 0:
        return []
    overall_missing_pct = round(df.isna().sum().sum() / df.size * 100, 2)
    if overall_missing_pct > 20:
        return [_finding(
            "high_sparsity", "HIGH" if overall_missing_pct > 40 else "MEDIUM", [],
            f"{overall_missing_pct}% of all cells in the dataset are missing overall.",
            1.0,
        )]
    return []


def check_suspicious_correlations(df: pd.DataFrame) -> list:
    findings = []
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return findings
    corr = numeric_df.corr(numeric_only=True).abs()
    seen = set()
    for col_a in corr.columns:
        for col_b in corr.columns:
            if col_a == col_b or (col_b, col_a) in seen:
                continue
            seen.add((col_a, col_b))
            val = corr.loc[col_a, col_b]
            if pd.notna(val) and val >= CORRELATION_LEAKAGE_THRESHOLD:
                findings.append(_finding(
                    "suspicious_correlation", "MEDIUM", [col_a, col_b],
                    f"'{col_a}' and '{col_b}' are correlated at {round(val,3)} - "
                    f"likely redundant, or one may leak information about the other.",
                    0.7,
                ))
    return findings


def check_target_specific(df: pd.DataFrame, target_column: str) -> list:
    findings = []
    if target_column not in df.columns:
        return [_finding(
            "target_not_found", "HIGH", [target_column],
            f"Specified target column '{target_column}' does not exist in this dataset.",
            1.0,
        )]

    missing_target = int(df[target_column].isna().sum())
    if missing_target > 0:
        findings.append(_finding(
            "missing_target_rows", "HIGH", [target_column],
            f"{missing_target} rows have no value for target '{target_column}' and cannot be used for training.",
            1.0,
        ))

    non_null_target = df[target_column].dropna()
    if not non_null_target.empty:
        value_counts = non_null_target.value_counts(normalize=True)
        if len(value_counts) <= 20:  # only meaningful for classification-shaped targets
            majority_share = value_counts.iloc[0]
            if majority_share > 0.9:
                findings.append(_finding(
                    "class_imbalance", "MEDIUM", [target_column],
                    f"The majority class in '{target_column}' makes up {round(majority_share*100,1)}% "
                    f"of labeled rows - a naive model could reach that accuracy by always predicting it.",
                    0.9,
                ))

    if pd.api.types.is_numeric_dtype(df[target_column]):
        numeric_df = df.select_dtypes(include=[np.number])
        for col in numeric_df.columns:
            if col == target_column:
                continue
            corr = numeric_df[col].corr(numeric_df[target_column])
            if pd.notna(corr) and abs(corr) >= CORRELATION_LEAKAGE_THRESHOLD:
                findings.append(_finding(
                    "possible_target_leakage", "HIGH", [col, target_column],
                    f"'{col}' correlates with target '{target_column}' at {round(corr,3)} - "
                    f"check whether '{col}' would actually be available at prediction time.",
                    0.6,
                ))
    return findings


def run_ml_readiness_agent(df: pd.DataFrame, target_column: str = None) -> dict:
    findings = (
        check_constant_features(df)
        + check_duplicate_observations(df)
        + check_high_cardinality_categoricals(df)
        + check_sparsity(df)
        + check_suspicious_correlations(df)
    )
    if target_column:
        findings += check_target_specific(df, target_column)

    return {"findings": findings, "finding_count": len(findings), "target_column": target_column}
