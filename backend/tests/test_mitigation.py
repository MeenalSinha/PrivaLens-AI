import pandas as pd

from app.mitigation.transforms import (
    apply_age_bucketing, apply_pincode_generalization, apply_date_generalization,
    apply_suppression, apply_categorical_generalization, recommend_mitigations,
)
from app.privacy.k_anonymity import k_anonymity_report


def test_age_bucketing_reduces_cardinality():
    df = pd.DataFrame({"Age": [21, 22, 23, 24, 25, 26, 27, 28, 29]})
    before_unique = df["Age"].nunique()
    transformed = apply_age_bucketing(df, "Age", band_size=5)
    after_unique = transformed["Age"].nunique()
    assert after_unique < before_unique


def test_pincode_generalization_masks_suffix():
    df = pd.DataFrame({"Pincode": ["110001", "110002"]})
    transformed = apply_pincode_generalization(df, "Pincode", keep_digits=3)
    assert all(v.startswith("110") for v in transformed["Pincode"])
    assert "*" in transformed["Pincode"].iloc[0]


def test_date_generalization_to_month():
    df = pd.DataFrame({"AdmissionDate": ["2026-01-15", "2026-01-28"]})
    transformed = apply_date_generalization(df, "AdmissionDate", granularity="month")
    assert transformed["AdmissionDate"].nunique() == 1


def test_suppression_removes_column():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    transformed = apply_suppression(df, "A")
    assert "A" not in transformed.columns
    assert "B" in transformed.columns


def test_categorical_generalization_keeps_column_but_reduces_cardinality():
    """Regression test for a real bug found during audit: the
    'generalization' action silently mapped to full-column suppression,
    so a recommendation described as 'generalize to fewer categories'
    actually deleted the column entirely. Real generalization must keep
    the column and just collapse the long tail into 'Other'."""
    df = pd.DataFrame({"City": ["Delhi"] * 5 + ["Mumbai"] * 3 + ["Pune"] * 1 + ["Nagpur"] * 1})
    before_unique = df["City"].nunique()
    transformed = apply_categorical_generalization(df, "City", keep_top_n=2)
    assert "City" in transformed.columns, "generalization must not delete the column"
    after_unique = transformed["City"].nunique()
    assert after_unique < before_unique
    assert "Other" in transformed["City"].values
    assert "Delhi" in transformed["City"].values  # most frequent value kept as-is


def test_recommend_mitigations_skips_already_low_cardinality_columns():
    """Regression test: a categorical QI column that's already
    well-generalized (few distinct values, e.g. a 2-value Gender or a
    3-value broad Region) should not be recommended for further
    mitigation - doing so would only destroy utility for negligible
    privacy gain, which the spec explicitly warns against."""
    profile = {
        "columns": [
            {"name": "Region", "inferred_type": "categorical", "cardinality_ratio": 0.02, "unique_count": 3},
        ]
    }
    classification = {"quasi_identifiers": ["Region"]}
    k_anon = {}
    recs = recommend_mitigations(profile, classification, k_anon)
    assert recs == [], "a 3-value column should not be recommended for mitigation"


def test_fix_and_retest_actually_changes_metrics():
    """Verifies transformations actually change computed k-anonymity
    metrics, per the spec's testing requirement (section 28)."""
    df = pd.DataFrame({
        "Age": [21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
        "Gender": ["M"] * 10,
        "Pincode": [f"11000{i}" for i in range(10)],
    })
    qi = ["Age", "Gender", "Pincode"]
    before = k_anonymity_report(df, qi, k_values=[5])
    before_at_risk = before["checks"][0]["at_risk_records"]

    transformed = apply_age_bucketing(df, "Age", band_size=5)
    transformed = apply_pincode_generalization(transformed, "Pincode", keep_digits=3)
    after = k_anonymity_report(transformed, qi, k_values=[5])
    after_at_risk = after["checks"][0]["at_risk_records"]

    assert after_at_risk <= before_at_risk
    assert before != after
