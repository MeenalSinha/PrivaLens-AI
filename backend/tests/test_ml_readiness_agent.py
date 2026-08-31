import pandas as pd
import numpy as np

from app.rescue.ml_readiness_agent import run_ml_readiness_agent


def test_detects_constant_feature():
    df = pd.DataFrame({"A": [1, 2, 3], "Constant": ["x", "x", "x"]})
    result = run_ml_readiness_agent(df)
    findings = [f for f in result["findings"] if f["check"] == "constant_feature"]
    assert len(findings) == 1
    assert findings[0]["columns"] == ["Constant"]


def test_detects_duplicate_observations():
    df = pd.DataFrame({"A": [1, 1, 2], "B": ["x", "x", "y"]})
    result = run_ml_readiness_agent(df)
    findings = [f for f in result["findings"] if f["check"] == "duplicate_observations"]
    assert len(findings) == 1


def test_detects_high_cardinality_categorical():
    df = pd.DataFrame({"ID": [f"id_{i}" for i in range(100)], "Val": range(100)})
    result = run_ml_readiness_agent(df)
    findings = [f for f in result["findings"] if f["check"] == "high_cardinality_categorical"]
    assert len(findings) == 1
    assert findings[0]["columns"] == ["ID"]


def test_detects_suspicious_correlation():
    x = np.arange(100)
    df = pd.DataFrame({"A": x, "B": x * 2 + 1})  # perfectly correlated
    result = run_ml_readiness_agent(df)
    findings = [f for f in result["findings"] if f["check"] == "suspicious_correlation"]
    assert len(findings) == 1


def test_no_target_checks_without_target_column():
    df = pd.DataFrame({"A": [1, 2, 3], "Label": ["yes", "no", "yes"]})
    result = run_ml_readiness_agent(df, target_column=None)
    target_checks = {"class_imbalance", "missing_target_rows", "possible_target_leakage", "target_not_found"}
    findings = [f for f in result["findings"] if f["check"] in target_checks]
    assert findings == []


def test_detects_class_imbalance_with_target():
    df = pd.DataFrame({"A": range(100), "Label": ["majority"] * 95 + ["minority"] * 5})
    result = run_ml_readiness_agent(df, target_column="Label")
    findings = [f for f in result["findings"] if f["check"] == "class_imbalance"]
    assert len(findings) == 1


def test_detects_missing_target_rows():
    df = pd.DataFrame({"A": range(10), "Label": ["x"] * 8 + [None, None]})
    result = run_ml_readiness_agent(df, target_column="Label")
    findings = [f for f in result["findings"] if f["check"] == "missing_target_rows"]
    assert len(findings) == 1
    assert findings[0]["columns"] == ["Label"]


def test_target_not_found_reported_honestly():
    df = pd.DataFrame({"A": [1, 2, 3]})
    result = run_ml_readiness_agent(df, target_column="DoesNotExist")
    findings = [f for f in result["findings"] if f["check"] == "target_not_found"]
    assert len(findings) == 1


def test_possible_target_leakage():
    x = np.arange(200)
    df = pd.DataFrame({"Feature": x, "Target": x * 3})  # perfectly correlated numeric target
    result = run_ml_readiness_agent(df, target_column="Target")
    findings = [f for f in result["findings"] if f["check"] == "possible_target_leakage"]
    assert len(findings) == 1
