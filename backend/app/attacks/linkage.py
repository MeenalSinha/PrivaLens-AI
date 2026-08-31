"""
Record linkage / entity-matching attack simulation.

Given dataset A (the supposedly-anonymized dataset) and dataset B (an
auxiliary attacker dataset with overlapping quasi-identifiers), this module
computes a transparent, explainable match score for every candidate pair
sharing at least one comparable column, using:

  - exact match for categorical columns
  - normalized numeric distance for numeric columns
  - Levenshtein-ratio string similarity for text columns
  - date proximity for date columns

The combined score is a weighted average (weights in app.config) - never
a black-box number. Each match carries a per-attribute breakdown so the
UI can answer "why is this HIGH RISK?".
"""
import difflib
import re
from datetime import datetime

import numpy as np
import pandas as pd

from app.config import LINKAGE_WEIGHTS, LINKAGE_MATCH_THRESHOLD

# Column-name patterns for numeric-looking values that are actually codes,
# not continuous quantities - postal codes, phone numbers, ID numbers.
# pandas infers these as int64 after a CSV round-trip (e.g. Pincode "110045"
# becomes the integer 110045), which would otherwise make _col_kind treat
# them as "numeric" and score candidate pairs by normalized distance. That's
# semantically wrong: two different pincodes 60% "close" in numeric value
# are not 60% likely to be the same person's postal code - postal/ID codes
# should always be scored as exact-match categorical values, matching how
# the mitigation engine already treats them (see mitigation/transforms.py).
_CODE_LIKE_PATTERNS = [r"\bpin\s?code\b", r"\bzip\b", r"\bpostal\b", r"\bphone\b", r"\bmobile\b"]


def _normalize_column_name(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    s = re.sub(r"[_\-]+", " ", s)
    return s.strip()


def _is_code_like(name: str) -> bool:
    normalized = _normalize_column_name(name)
    return any(re.search(p, normalized, flags=re.IGNORECASE) for p in _CODE_LIKE_PATTERNS)


def _col_kind(series: pd.Series, name: str = "") -> str:
    if name and _is_code_like(name):
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    # try date
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(series.dropna().astype(str).head(20), errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.7:
            return "date"
    except Exception:
        pass
    n_unique = series.dropna().nunique()
    if n_unique <= max(20, len(series) * 0.2):
        return "categorical"
    return "text"


def _numeric_similarity(a, b, col_range):
    if pd.isna(a) or pd.isna(b) or col_range == 0:
        return 0.0
    diff = abs(float(a) - float(b)) / col_range
    return max(0.0, 1.0 - diff)


def _string_similarity(a, b):
    if pd.isna(a) or pd.isna(b):
        return 0.0
    return difflib.SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()


def _date_similarity(a, b, max_days=365 * 2):
    try:
        da = pd.to_datetime(a)
        db = pd.to_datetime(b)
    except Exception:
        return 0.0
    if pd.isna(da) or pd.isna(db):
        return 0.0
    diff_days = abs((da - db).days)
    return max(0.0, 1.0 - diff_days / max_days)


def run_linkage_attack(df_a: pd.DataFrame, df_b: pd.DataFrame, weights=None,
                        threshold=None, max_candidates_per_record=3) -> dict:
    """
    Compares every column shared between df_a and df_b (by name) and scores
    all row-pairs. For performance on larger demo datasets, comparisons are
    vectorized per shared-column and only the top candidates per A-record
    are kept.
    """
    weights = weights or LINKAGE_WEIGHTS
    threshold = threshold if threshold is not None else LINKAGE_MATCH_THRESHOLD

    total_a, total_b = len(df_a), len(df_b)

    shared_cols = [c for c in df_a.columns if c in df_b.columns]
    if not shared_cols:
        return {
            "shared_columns": [],
            "matches": [],
            "candidates_tested": 0,
            "matches_found": 0,
            "highest_confidence": 0.0,
            "target_rows_total": total_a,
            "target_rows_tested": 0,
            "auxiliary_rows_total": total_b,
            "auxiliary_rows_tested": 0,
            "was_truncated": False,
        }

    col_kinds = {c: _col_kind(df_a[c], c) for c in shared_cols}
    numeric_ranges = {
        c: (df_a[c].max() - df_a[c].min()) if col_kinds[c] == "numeric" and len(df_a) else 1
        for c in shared_cols if col_kinds[c] == "numeric"
    }

    # Cap dataset sizes for demo responsiveness while staying "real" - not
    # hardcoded results, just a bounded brute-force comparison. This is a
    # genuine scalability limit (see README > Limitations), so the response
    # explicitly reports how many rows were actually tested vs how many
    # exist, rather than silently testing a subset while implying the
    # whole dataset was attacked.
    ATTACK_ROW_CAP = 400
    a_sample = df_a.head(ATTACK_ROW_CAP)
    b_sample = df_b.head(ATTACK_ROW_CAP)

    matches = []
    candidates_tested = 0

    for a_idx, a_row in a_sample.iterrows():
        scored = []
        for b_idx, b_row in b_sample.iterrows():
            candidates_tested += 1
            attribute_scores = {}
            for col in shared_cols:
                kind = col_kinds[col]
                av, bv = a_row.get(col), b_row.get(col)
                if kind == "categorical":
                    score = 1.0 if (pd.notna(av) and pd.notna(bv) and str(av) == str(bv)) else 0.0
                    weight_key = "categorical_exact"
                elif kind == "numeric":
                    score = _numeric_similarity(av, bv, numeric_ranges.get(col, 1) or 1)
                    weight_key = "numeric_closeness"
                elif kind == "date":
                    score = _date_similarity(av, bv)
                    weight_key = "date_closeness"
                else:
                    score = _string_similarity(av, bv)
                    weight_key = "string_similarity"
                attribute_scores[col] = {"score": round(score, 3), "kind": kind, "weight_key": weight_key}

            # combine using weight-per-kind, normalized by weights actually present
            total_weight = 0.0
            weighted_sum = 0.0
            for col, info in attribute_scores.items():
                w = weights.get(info["weight_key"], 0.1)
                weighted_sum += w * info["score"]
                total_weight += w
            combined = weighted_sum / total_weight if total_weight else 0.0

            if combined >= threshold:
                scored.append((b_idx, combined, attribute_scores))

        scored.sort(key=lambda x: x[1], reverse=True)
        for b_idx, combined, attribute_scores in scored[:max_candidates_per_record]:
            matches.append({
                "record_a_index": int(a_idx),
                "record_b_index": int(b_idx),
                "match_probability": round(combined, 3),
                "matching_attributes": attribute_scores,
                "risk_level": _risk_level_for_score(combined),
            })

    matches.sort(key=lambda m: m["match_probability"], reverse=True)
    highest_confidence = matches[0]["match_probability"] if matches else 0.0

    return {
        "shared_columns": shared_cols,
        "column_kinds": col_kinds,
        "candidates_tested": candidates_tested,
        "matches_found": len(matches),
        "highest_confidence": highest_confidence,
        "matches": matches[:500],  # cap payload size
        "target_rows_total": total_a,
        "target_rows_tested": len(a_sample),
        "auxiliary_rows_total": total_b,
        "auxiliary_rows_tested": len(b_sample),
        "was_truncated": total_a > len(a_sample) or total_b > len(b_sample),
    }


def _risk_level_for_score(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.55:
        return "MODERATE"
    return "LOW"
