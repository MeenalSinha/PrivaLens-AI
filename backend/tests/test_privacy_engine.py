import pandas as pd

from app.privacy.k_anonymity import uniqueness_analysis, k_anonymity_report, l_diversity_report


def make_df():
    return pd.DataFrame({
        "Age": [25, 25, 25, 40, 40, 55],
        "Gender": ["M", "M", "M", "F", "F", "M"],
        "Pincode": ["1100", "1100", "1100", "4000", "4000", "5600"],
        "Diagnosis": ["Flu", "Flu", "Asthma", "Diabetes", "Diabetes", "HIV"],
    })


def test_uniqueness_analysis_basic():
    df = make_df()
    result = uniqueness_analysis(df, ["Age", "Gender", "Pincode"])
    assert result["equivalence_classes"] == 3
    # last row (55, M, 5600) is a unique class of size 1
    assert result["unique_records"] == 1
    assert result["unique_pct"] > 0


def test_uniqueness_empty_qi_returns_zero():
    df = make_df()
    result = uniqueness_analysis(df, [])
    assert result["equivalence_classes"] == 0


def test_k_anonymity_report_detects_violations():
    df = make_df()
    report = k_anonymity_report(df, ["Age", "Gender", "Pincode"], k_values=[2, 3])
    assert report["min_class_size"] == 1
    k2_check = next(c for c in report["checks"] if c["k"] == 2)
    assert k2_check["at_risk_records"] >= 1
    assert k2_check["satisfies_k_anonymity"] is False


def test_k_anonymity_satisfied_when_k_low_enough():
    df = make_df()
    report = k_anonymity_report(df, ["Age", "Gender", "Pincode"], k_values=[1])
    k1_check = next(c for c in report["checks"] if c["k"] == 1)
    assert k1_check["at_risk_records"] == 0
    assert k1_check["satisfies_k_anonymity"] is True


def test_l_diversity_flags_single_value_classes():
    df = make_df()
    report = l_diversity_report(df, ["Age", "Gender", "Pincode"], "Diagnosis")
    # (25, M, 1100) class has both Flu and Asthma -> l=2 for that class
    # (40, F, 4000) class has only Diabetes -> l=1
    assert report["min_l"] == 1
    assert report["classes_with_l1"] >= 1
