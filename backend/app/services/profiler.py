"""
Dataset profiling engine.

Computes real statistics from the uploaded dataframe - nothing here is
hardcoded. All numbers are derived directly from df at call time.
"""
import pandas as pd
import numpy as np
import re

# Same code-like column patterns as attacks/linkage.py - postal codes, phone
# numbers etc. are numeric-looking but not continuous quantities, so they
# should be displayed and treated as categorical, not "numeric".
_CODE_LIKE_PATTERNS = [r"\bpin\s?code\b", r"\bzip\b", r"\bpostal\b", r"\bphone\b", r"\bmobile\b"]


def _normalize_column_name(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    s = re.sub(r"[_\-]+", " ", s)
    return s.strip()


def _is_code_like(name: str) -> bool:
    normalized = _normalize_column_name(name)
    return any(re.search(p, normalized, flags=re.IGNORECASE) for p in _CODE_LIKE_PATTERNS)


def profile_dataset(df: pd.DataFrame) -> dict:
    n_rows, n_cols = df.shape
    columns = []

    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        n_unique = int(non_null.nunique())
        cardinality_ratio = round(n_unique / n_rows, 4) if n_rows else 0.0
        dtype = str(series.dtype)

        inferred_type = _infer_semantic_type(series, dtype, col)

        columns.append({
            "name": col,
            "dtype": dtype,
            "inferred_type": inferred_type,
            "missing_count": int(series.isna().sum()),
            "missing_pct": round(float(series.isna().mean()) * 100, 2),
            "unique_count": n_unique,
            "cardinality_ratio": cardinality_ratio,
            "is_constant": n_unique <= 1,
            "is_high_cardinality": cardinality_ratio > 0.9,
            "sample_values": [str(v) for v in non_null.unique()[:5].tolist()],
        })

    duplicate_rows = int(df.duplicated().sum())

    return {
        "row_count": int(n_rows),
        "column_count": int(n_cols),
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round((duplicate_rows / n_rows) * 100, 2) if n_rows else 0.0,
        "total_missing_cells": int(df.isna().sum().sum()),
        "columns": columns,
    }


def _infer_semantic_type(series: pd.Series, dtype: str, name: str = "") -> str:
    """Lightweight heuristic type inference used purely for display -
    NOT the same as identifier classification (see identifier_detection.py)."""
    if name and _is_code_like(name):
        return "categorical"
    if "int" in dtype or "float" in dtype:
        return "numeric"
    if "datetime" in dtype:
        return "datetime"

    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return "text"

    # try datetime parse
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.8:
            return "datetime"
    except Exception:
        pass

    avg_len = sample.str.len().mean()
    n_unique = sample.nunique()
    if n_unique <= max(20, len(sample) * 0.2) and avg_len < 25:
        return "categorical"
    return "text"
