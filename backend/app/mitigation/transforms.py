"""
Mitigation engine: generalization, suppression, bucketing and date
generalization transforms, plus recommendation logic that ties each
recommendation to the actual column statistics observed.
"""
import numpy as np
import pandas as pd

# A categorical quasi-identifier at or below this cardinality is already
# about as generalized as it can usefully get (e.g. a 2-3 value column
# like Gender or a broad Region). Recommending further generalization or
# suppression here would only destroy utility for negligible privacy
# gain - the spec explicitly warns against blindly destroying data to
# achieve privacy, so these columns are left alone rather than being
# suppressed by default (see AUDIT.md for the bug this replaced).
LOW_CARDINALITY_SKIP_THRESHOLD = 5


def recommend_mitigations(profile: dict, classification: dict, k_anon: dict) -> list:
    """Builds a recommendation list grounded in real column stats -
    not a static template. Each entry explains *why* it reduces risk.
    Columns that are already low-cardinality/well-generalized are
    skipped rather than recommended for suppression."""
    recs = []
    qi_cols = classification["quasi_identifiers"]
    col_info = {c["name"]: c for c in profile["columns"]}

    for col in qi_cols:
        info = col_info.get(col)
        if not info:
            continue
        inferred = info["inferred_type"]
        name_l = col.lower()
        unique_count = info.get("unique_count", 0)

        if inferred == "numeric" and ("age" in name_l or info["cardinality_ratio"] > 0.05):
            recs.append({
                "column": col,
                "action": "generalization_bucketing",
                "description": f"Bucket '{col}' into ranges (e.g. 5-year bands) to reduce its "
                                f"contribution to unique equivalence classes.",
                "reason": f"'{col}' has a cardinality ratio of {info['cardinality_ratio']}, "
                          f"making it a strong driver of unique records.",
            })
        elif "pincode" in name_l or "zip" in name_l or "postal" in name_l:
            recs.append({
                "column": col,
                "action": "truncation_generalization",
                "description": f"Truncate '{col}' to a broader region prefix (e.g. keep first 3 digits).",
                "reason": f"Full postal codes are highly identifying when combined with age/gender.",
            })
        elif inferred == "datetime" or "date" in name_l:
            recs.append({
                "column": col,
                "action": "date_generalization",
                "description": f"Generalize '{col}' to month or quarter granularity.",
                "reason": f"Exact dates combined with other quasi-identifiers create small, "
                          f"highly-identifying equivalence classes.",
            })
        elif inferred == "categorical" and unique_count <= LOW_CARDINALITY_SKIP_THRESHOLD:
            # Already well-generalized (e.g. Gender with 2 values, or a
            # broad Region with 3-5 values) - no mitigation recommended.
            continue
        elif inferred == "categorical" and info["cardinality_ratio"] > 0.5:
            # Very high cardinality categorical (close to a free-text
            # identifier) - generalization would leave it almost as
            # identifying, so suppression is the honest recommendation.
            recs.append({
                "column": col,
                "action": "suppression",
                "description": f"Suppress '{col}' entirely.",
                "reason": f"'{col}' has very high cardinality (ratio {info['cardinality_ratio']}) "
                          f"relative to dataset size - generalization would not meaningfully "
                          f"reduce its uniqueness, so removal is the only effective option.",
            })
        else:
            # Moderate-cardinality categorical: real generalization
            # (collapse the long tail of rare categories into "Other"),
            # not suppression - this actually changes the label from
            # "generalize" to a transform that keeps the column and its
            # most common values, rather than deleting it outright.
            recs.append({
                "column": col,
                "action": "generalization",
                "description": f"Generalize '{col}' by keeping its most common categories and "
                                f"grouping the rest into 'Other'.",
                "reason": f"'{col}' is a quasi-identifier with {unique_count} distinct values "
                          f"contributing to small equivalence classes; collapsing rare "
                          f"categories reduces uniqueness while keeping the column usable.",
            })

    return recs


# ---------------------------------------------------------------------------
# Actual transform implementations - operate on a copy of the dataframe.
# ---------------------------------------------------------------------------

def apply_age_bucketing(df: pd.DataFrame, column: str, band_size: int = 5) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    numeric = pd.to_numeric(df[column], errors="coerce")
    lower = (numeric // band_size * band_size).astype("Int64")
    upper = lower + band_size - 1
    df[column] = [
        f"{lo}-{hi}" if pd.notna(lo) else None for lo, hi in zip(lower, upper)
    ]
    return df


def apply_pincode_generalization(df: pd.DataFrame, column: str, keep_digits: int = 3) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    df[column] = df[column].astype(str).apply(
        lambda v: v[:keep_digits] + "*" * max(0, len(v) - keep_digits) if v and v != "nan" else v
    )
    return df


def apply_date_generalization(df: pd.DataFrame, column: str, granularity: str = "month") -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    parsed = pd.to_datetime(df[column], errors="coerce")
    if granularity == "month":
        df[column] = parsed.dt.strftime("%B %Y")
    elif granularity == "quarter":
        df[column] = parsed.dt.to_period("Q").astype(str)
    else:
        df[column] = parsed.dt.strftime("%Y")
    return df


def apply_bucketing(df: pd.DataFrame, column: str, bucket_size: int = 10000) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    numeric = pd.to_numeric(df[column], errors="coerce")
    lower = (numeric // bucket_size * bucket_size).astype("Int64")
    upper = lower + bucket_size
    df[column] = [
        f"{lo}-{hi}" if pd.notna(lo) else None for lo, hi in zip(lower, upper)
    ]
    return df


def apply_suppression(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df = df.copy()
    if column in df.columns:
        df = df.drop(columns=[column])
    return df


def apply_categorical_generalization(df: pd.DataFrame, column: str, keep_top_n: int = 5) -> pd.DataFrame:
    """Real generalization for a categorical column: keeps the keep_top_n
    most frequent values as-is and collapses every other value into
    'Other'. This reduces the column's cardinality (and therefore its
    contribution to small equivalence classes) while keeping the column
    itself usable, unlike suppression which deletes it outright. This
    replaced a bug where the 'generalization' action silently mapped to
    full-column suppression - see AUDIT.md."""
    df = df.copy()
    if column not in df.columns:
        return df
    top_values = df[column].value_counts().head(keep_top_n).index
    df[column] = df[column].apply(lambda v: v if v in top_values else "Other")
    return df


ACTION_DISPATCH = {
    "generalization_bucketing": lambda df, col: apply_age_bucketing(df, col),
    "truncation_generalization": lambda df, col: apply_pincode_generalization(df, col),
    "date_generalization": lambda df, col: apply_date_generalization(df, col),
    "generalization": lambda df, col: apply_categorical_generalization(df, col),
    "suppression": lambda df, col: apply_suppression(df, col),
    "bucketing": lambda df, col: apply_bucketing(df, col),
}


def apply_mitigations(df: pd.DataFrame, mitigations: list) -> pd.DataFrame:
    """Applies a list of {column, action} mitigations sequentially and
    returns the transformed dataframe. Real transformation, not simulated."""
    out = df.copy()
    for m in mitigations:
        fn = ACTION_DISPATCH.get(m["action"])
        if fn:
            out = fn(out, m["column"])
    return out
