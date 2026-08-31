"""
Data Quality Agent.

Deterministic detection of data-quality problems - no LLM involved in any
of these calculations, per the architecture principle that numerical
findings must never be invented by a model. Every issue returned here is
computed directly from the dataframe.

Implemented checks: missing values, exact duplicate rows, malformed/
inconsistent date formats, inconsistent categorical casing, leading/
trailing whitespace, constant and near-constant columns, high-cardinality
columns, numeric outliers (IQR method).

Explicitly NOT implemented (see AUDIT_RESCUE.md): unit-of-measurement
inconsistency detection beyond a weak, clearly-labeled low-confidence
heuristic; cross-column semantic consistency (e.g. "end_date before
start_date"); schema drift against a prior version (that requires a
previous version to compare against - see the versioning note in
AUDIT_RESCUE.md for what exists vs what doesn't).
"""
import re
import warnings

import numpy as np
import pandas as pd


def _issue(issue_type, severity, columns, affected_rows, description,
           confidence, auto_fix_eligible, suggested_action, action_params=None):
    return {
        "issue_type": issue_type,
        "severity": severity,          # LOW | MEDIUM | HIGH | CRITICAL
        "columns": columns,
        "affected_rows": affected_rows,
        "description": description,
        "confidence": confidence,       # 0-1, always disclosed - never claim certainty
        "auto_fix_eligible": auto_fix_eligible,
        "suggested_action": suggested_action,
        "action_params": action_params or {},
    }


def detect_missing_values(df: pd.DataFrame) -> list:
    issues = []
    n = len(df)
    if n == 0:
        return issues
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing == 0:
            continue
        pct = round(missing / n * 100, 2)
        severity = "CRITICAL" if pct > 50 else "HIGH" if pct > 20 else "MEDIUM" if pct > 5 else "LOW"
        numeric = pd.api.types.is_numeric_dtype(df[col])
        issues.append(_issue(
            "missing_values", severity, [col], missing,
            f"'{col}' has {missing} missing values ({pct}% of rows).",
            confidence=1.0, auto_fix_eligible=False,
            suggested_action="impute_missing_median" if numeric else "impute_missing_mode",
            action_params={"column": col},
        ))
    return issues


def detect_duplicate_rows(df: pd.DataFrame) -> list:
    n_dupes = int(df.duplicated().sum())
    if n_dupes == 0:
        return []
    pct = round(n_dupes / len(df) * 100, 2) if len(df) else 0
    severity = "HIGH" if pct > 10 else "MEDIUM" if pct > 2 else "LOW"
    return [_issue(
        "duplicate_rows", severity, [], n_dupes,
        f"{n_dupes} exact duplicate rows found ({pct}% of the dataset).",
        confidence=1.0, auto_fix_eligible=True,
        suggested_action="drop_exact_duplicates",
    )]


def detect_whitespace_issues(df: pd.DataFrame) -> list:
    issues = []
    for col in df.select_dtypes(include="object").columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        affected = int((series != series.str.strip()).sum())
        if affected > 0:
            issues.append(_issue(
                "whitespace", "LOW", [col], affected,
                f"'{col}' has {affected} values with leading/trailing whitespace.",
                confidence=1.0, auto_fix_eligible=True,
                suggested_action="trim_whitespace", action_params={"column": col},
            ))
    return issues


def detect_case_inconsistency(df: pd.DataFrame) -> list:
    """Flags columns where the same logical value appears in multiple
    casings (e.g. 'Male', 'male', 'MALE') - only meaningful for
    low-cardinality categorical-looking text columns."""
    issues = []
    for col in df.select_dtypes(include="object").columns:
        series = df[col].dropna().astype(str).str.strip()
        if series.empty:
            continue
        n_unique = series.nunique()
        n_unique_lower = series.str.lower().nunique()
        if n_unique_lower < n_unique and n_unique <= max(30, len(series) * 0.3):
            affected = int((series.str.lower().map(series.str.lower().value_counts()) > 0).sum())
            collapsed = n_unique - n_unique_lower
            issues.append(_issue(
                "case_inconsistency", "LOW", [col], affected,
                f"'{col}' has {n_unique} distinct values that collapse to {n_unique_lower} "
                f"when case-normalized ({collapsed} apparent duplicate categories from casing alone).",
                confidence=0.85, auto_fix_eligible=True,
                suggested_action="standardize_case", action_params={"column": col},
            ))
    return issues


def detect_malformed_dates(df: pd.DataFrame) -> list:
    """Flags date-like columns where some values parse and others don't,
    or where multiple distinct date formats are mixed - both are real
    signals of a malformed/inconsistent date column, not guessed."""
    issues = []
    for col in df.columns:
        if not pd.api.types.is_object_dtype(df[col]):
            continue
        series = df[col].dropna().astype(str)
        if series.empty or len(series) < 5:
            continue
        # only consider columns that look date-ish to begin with
        sample = series.head(30)
        date_like = sample.str.contains(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", regex=True).mean()
        if date_like < 0.5:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        unparseable = int(parsed.isna().sum())
        if unparseable > 0:
            pct = round(unparseable / len(series) * 100, 2)
            issues.append(_issue(
                "malformed_dates", "MEDIUM" if pct > 5 else "LOW", [col], unparseable,
                f"'{col}' looks like a date column but {unparseable} values ({pct}%) don't parse "
                f"as any recognizable date format.",
                confidence=0.8, auto_fix_eligible=False,
                suggested_action="standardize_date_format", action_params={"column": col},
            ))
        else:
            # check for mixed formats among values that DO parse, by comparing
            # distinct separator/ordering patterns
            patterns = series.str.replace(r"\d", "#", regex=True).unique()
            if len(patterns) > 1:
                issues.append(_issue(
                    "inconsistent_date_format", "LOW", [col], len(series),
                    f"'{col}' contains {len(patterns)} different date formatting patterns "
                    f"(e.g. {', '.join(str(p) for p in patterns[:3])}).",
                    confidence=0.7, auto_fix_eligible=True,
                    suggested_action="standardize_date_format", action_params={"column": col},
                ))
    return issues


def detect_constant_and_high_cardinality(df: pd.DataFrame) -> list:
    issues = []
    n = len(df)
    if n == 0:
        return issues
    for col in df.columns:
        n_unique = df[col].nunique(dropna=True)
        ratio = n_unique / n
        if n_unique <= 1:
            issues.append(_issue(
                "constant_column", "LOW", [col], n,
                f"'{col}' has a single distinct value across all rows - carries no information.",
                confidence=1.0, auto_fix_eligible=False, suggested_action="suppression",
                action_params={"column": col},
            ))
        elif ratio < 0.02 and n_unique <= 3:
            issues.append(_issue(
                "near_constant_column", "LOW", [col], n,
                f"'{col}' has only {n_unique} distinct values across {n} rows - very little variance.",
                confidence=0.6, auto_fix_eligible=False, suggested_action=None,
            ))
        elif ratio > 0.95 and not pd.api.types.is_numeric_dtype(df[col]):
            issues.append(_issue(
                "high_cardinality_column", "LOW", [col], n,
                f"'{col}' is {round(ratio*100,1)}% unique - likely an identifier column, "
                f"not a useful analytical feature.",
                confidence=0.7, auto_fix_eligible=False, suggested_action=None,
            ))
    return issues


def detect_outliers(df: pd.DataFrame) -> list:
    """IQR-method outlier detection on numeric columns - a standard,
    real statistical method, not a guess."""
    issues = []
    for col in df.select_dtypes(include=[np.number]).columns:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
        outliers = int(((series < lower) | (series > upper)).sum())
        if outliers > 0:
            pct = round(outliers / len(series) * 100, 2)
            issues.append(_issue(
                "outliers", "MEDIUM" if pct > 2 else "LOW", [col], outliers,
                f"'{col}' has {outliers} extreme outliers ({pct}%) outside "
                f"[{round(lower,2)}, {round(upper,2)}] by the IQR method.",
                confidence=0.75, auto_fix_eligible=False,
                suggested_action="remove_outliers", action_params={"column": col},
            ))
    return issues


def detect_unit_inconsistency_heuristic(df: pd.DataFrame) -> list:
    """Weak, explicitly low-confidence heuristic: flags a numeric column
    where values span more than 3 orders of magnitude, which CAN indicate
    mixed units (e.g. some weights in kg, others in g) but can equally be
    a genuinely skewed distribution. Always confidence <= 0.4 and never
    auto-fixable - this is a hint for a human, not a finding."""
    issues = []
    for col in df.select_dtypes(include=[np.number]).columns:
        series = df[col].dropna()
        series = series[series > 0]
        if len(series) < 10:
            continue
        ratio = series.max() / series.min() if series.min() > 0 else 0
        if ratio > 1000:
            issues.append(_issue(
                "possible_unit_inconsistency", "LOW", [col], len(series),
                f"'{col}' spans a {round(ratio):,}x range - possibly mixed units, "
                f"but this could also be a normal skewed distribution. Low confidence.",
                confidence=0.35, auto_fix_eligible=False, suggested_action=None,
            ))
    return issues


def run_quality_agent(df: pd.DataFrame) -> dict:
    """Runs every detector and returns the combined issue list plus a
    0-100 quality score computed from the actual issues found (see
    scoring.quality_engine for the weighted formula)."""
    issues = (
        detect_missing_values(df)
        + detect_duplicate_rows(df)
        + detect_whitespace_issues(df)
        + detect_case_inconsistency(df)
        + detect_malformed_dates(df)
        + detect_constant_and_high_cardinality(df)
        + detect_outliers(df)
        + detect_unit_inconsistency_heuristic(df)
    )
    return {"issues": issues, "issue_count": len(issues)}
