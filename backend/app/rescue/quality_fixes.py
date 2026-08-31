"""
Data quality fix transforms - real dataframe transformations, each
directly reversible by re-loading the preserved original dataset (see
AUDIT_RESCUE.md for the exact reversibility model). No transform here
modifies the dataframe in place; each returns a new dataframe.
"""
import warnings

import pandas as pd


def trim_whitespace(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df = df.copy()
    if column in df.columns:
        df[column] = df[column].astype(str).str.strip()
    return df


def standardize_case(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Standardizes to title case for values that are letters-only-ish,
    the most common real-world convention for categorical labels (e.g.
    'MALE'/'male' -> 'Male'). Does not touch values containing digits,
    since those are more likely codes than free-text labels."""
    df = df.copy()
    if column not in df.columns:
        return df

    def _norm(v):
        s = str(v)
        if any(ch.isdigit() for ch in s):
            return v
        return s.strip().title()

    df[column] = df[column].apply(_norm)
    return df


def standardize_date_format(df: pd.DataFrame, column: str, output_format: str = "%Y-%m-%d") -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
    df[column] = parsed.dt.strftime(output_format)
    return df


def drop_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates().reset_index(drop=True)


def impute_missing_median(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    median = pd.to_numeric(df[column], errors="coerce").median()
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(median)
    return df


def impute_missing_mode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df = df.copy()
    if column not in df.columns:
        return df
    mode_vals = df[column].mode(dropna=True)
    if len(mode_vals) == 0:
        return df
    df[column] = df[column].fillna(mode_vals.iloc[0])
    return df


def remove_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Removes rows whose value in `column` falls outside the IQR fence -
    the same method used to detect them in quality_agent.py, so the
    fix and the detector agree on what counts as an outlier."""
    df = df.copy()
    if column not in df.columns:
        return df
    series = pd.to_numeric(df[column], errors="coerce")
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return df
    lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
    mask = series.between(lower, upper) | series.isna()
    return df[mask].reset_index(drop=True)


QUALITY_FIX_DISPATCH = {
    "trim_whitespace": lambda df, params: trim_whitespace(df, params["column"]),
    "standardize_case": lambda df, params: standardize_case(df, params["column"]),
    "standardize_date_format": lambda df, params: standardize_date_format(df, params["column"]),
    "drop_exact_duplicates": lambda df, params: drop_exact_duplicates(df),
    "impute_missing_median": lambda df, params: impute_missing_median(df, params["column"]),
    "impute_missing_mode": lambda df, params: impute_missing_mode(df, params["column"]),
    "remove_outliers": lambda df, params: remove_outliers(df, params["column"]),
}
