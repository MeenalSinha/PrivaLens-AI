import pandas as pd
import numpy as np

from app.rescue.quality_agent import run_quality_agent


def test_detects_missing_values():
    df = pd.DataFrame({"A": [1, 2, None, None], "B": [1, 2, 3, 4]})
    result = run_quality_agent(df)
    missing_issues = [i for i in result["issues"] if i["issue_type"] == "missing_values"]
    assert len(missing_issues) == 1
    assert missing_issues[0]["columns"] == ["A"]
    assert missing_issues[0]["affected_rows"] == 2


def test_detects_duplicate_rows():
    df = pd.DataFrame({"A": [1, 1, 2, 3], "B": ["x", "x", "y", "z"]})
    result = run_quality_agent(df)
    dupe_issues = [i for i in result["issues"] if i["issue_type"] == "duplicate_rows"]
    assert len(dupe_issues) == 1
    assert dupe_issues[0]["affected_rows"] == 1
    assert dupe_issues[0]["auto_fix_eligible"] is True


def test_no_duplicate_issue_when_none_exist():
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    result = run_quality_agent(df)
    dupe_issues = [i for i in result["issues"] if i["issue_type"] == "duplicate_rows"]
    assert dupe_issues == []


def test_detects_case_inconsistency():
    df = pd.DataFrame({"Gender": ["Male", "MALE", "male", "Female"] * 5})
    result = run_quality_agent(df)
    case_issues = [i for i in result["issues"] if i["issue_type"] == "case_inconsistency"]
    assert len(case_issues) == 1
    assert case_issues[0]["columns"] == ["Gender"]


def test_detects_whitespace():
    df = pd.DataFrame({"Name": ["Alice", " Bob", "Carl ", "Dana"]})
    result = run_quality_agent(df)
    ws_issues = [i for i in result["issues"] if i["issue_type"] == "whitespace"]
    assert len(ws_issues) == 1
    assert ws_issues[0]["affected_rows"] == 2


def test_detects_malformed_dates():
    df = pd.DataFrame({"AdmissionDate": ["2026-01-15", "2026-02-20", "not-a-date", "2026-03-10"] * 5})
    result = run_quality_agent(df)
    date_issues = [i for i in result["issues"] if i["issue_type"] == "malformed_dates"]
    assert len(date_issues) == 1
    assert date_issues[0]["affected_rows"] == 5  # 5 "not-a-date" occurrences


def test_detects_constant_column():
    df = pd.DataFrame({"A": [1, 2, 3], "Source": ["x", "x", "x"]})
    result = run_quality_agent(df)
    const_issues = [i for i in result["issues"] if i["issue_type"] == "constant_column"]
    assert len(const_issues) == 1
    assert const_issues[0]["columns"] == ["Source"]


def test_detects_outliers():
    values = list(range(1, 51)) + [10000]  # one extreme outlier
    df = pd.DataFrame({"Value": values})
    result = run_quality_agent(df)
    outlier_issues = [i for i in result["issues"] if i["issue_type"] == "outliers"]
    assert len(outlier_issues) == 1
    assert outlier_issues[0]["affected_rows"] == 1


def test_clean_dataset_has_minimal_issues():
    """A genuinely clean dataset should not trigger the strong-signal
    detectors (missing values, duplicates, whitespace). Uses a row index
    column to guarantee no duplicate full rows can occur by chance -
    plain Age+Gender columns collide too often (birthday paradox) to
    reliably test this."""
    df = pd.DataFrame({
        "RecordID": [f"R{i:04d}" for i in range(50)],
        "Age": np.random.randint(18, 80, 50),
        "Gender": np.random.choice(["Male", "Female"], 50),
    })
    result = run_quality_agent(df)
    strong_signal_types = {"missing_values", "duplicate_rows", "whitespace", "malformed_dates"}
    strong_issues = [i for i in result["issues"] if i["issue_type"] in strong_signal_types]
    assert strong_issues == []
