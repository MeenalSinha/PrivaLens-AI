import pandas as pd

from app.attacks.linkage import run_linkage_attack


def test_exact_match_produces_high_confidence():
    df_a = pd.DataFrame({
        "Age": [30], "Gender": ["Male"], "Pincode": ["110001"], "Occupation": ["Nurse"],
    })
    df_b = pd.DataFrame({
        "Age": [30], "Gender": ["Male"], "Pincode": ["110001"], "Occupation": ["Nurse"],
    })
    result = run_linkage_attack(df_a, df_b)
    assert result["matches_found"] == 1
    assert result["highest_confidence"] > 0.9
    assert result["matches"][0]["risk_level"] in ("HIGH", "CRITICAL")


def test_no_shared_columns_returns_empty():
    df_a = pd.DataFrame({"X": [1, 2, 3]})
    df_b = pd.DataFrame({"Y": [1, 2, 3]})
    result = run_linkage_attack(df_a, df_b)
    assert result["shared_columns"] == []
    assert result["matches_found"] == 0


def test_dissimilar_records_do_not_match():
    df_a = pd.DataFrame({"Age": [20], "Gender": ["Male"]})
    df_b = pd.DataFrame({"Age": [80], "Gender": ["Female"]})
    result = run_linkage_attack(df_a, df_b, threshold=0.55)
    assert result["matches_found"] == 0


def test_explain_grounded_in_attribute_scores():
    df_a = pd.DataFrame({"Age": [30], "Gender": ["Male"]})
    df_b = pd.DataFrame({"Age": [30], "Gender": ["Male"]})
    result = run_linkage_attack(df_a, df_b)
    match = result["matches"][0]
    assert "Age" in match["matching_attributes"]
    assert "Gender" in match["matching_attributes"]


def test_pincode_is_scored_categorically_not_numerically():
    """Regression test for a real bug found during verification: pandas
    infers all-digit postal codes as int64 after a CSV round-trip, which
    made the old _col_kind() treat Pincode as a continuous numeric
    quantity. That scored numerically-close-but-different pincodes as
    near-perfect matches (e.g. 110045 vs 110099 scored 1.0), massively
    inflating false-positive linkage confidence. Pincode-like columns must
    be scored as exact-match categorical values regardless of dtype."""
    df_a = pd.DataFrame({"Pincode": [110045], "Gender": ["Male"]})
    df_b = pd.DataFrame({"Pincode": [110099], "Gender": ["Male"]})  # different pincode, numerically close
    result = run_linkage_attack(df_a, df_b, threshold=0.0)  # threshold 0 to inspect the raw score
    assert result["column_kinds"]["Pincode"] == "categorical"
    match = result["matches"][0]
    assert match["matching_attributes"]["Pincode"]["score"] == 0.0, (
        "Different pincodes must score 0 (no match), not receive partial "
        "credit for being numerically close"
    )


def test_identical_pincode_still_matches_exactly():
    df_a = pd.DataFrame({"Pincode": [110045]})
    df_b = pd.DataFrame({"Pincode": [110045]})
    result = run_linkage_attack(df_a, df_b)
    assert result["matches"][0]["matching_attributes"]["Pincode"]["score"] == 1.0


def test_truncation_is_disclosed_for_large_datasets():
    """Regression test for a real transparency gap found during audit:
    the attack silently compares only the first 400 rows of each dataset,
    but the response gave no way to tell a 10,000-row dataset only had
    400 rows tested. The response must report actual vs tested row
    counts and flag was_truncated so the UI can disclose it."""
    df_a = pd.DataFrame({"Age": range(500), "Gender": ["Male"] * 500})
    df_b = pd.DataFrame({"Age": range(500), "Gender": ["Male"] * 500})
    result = run_linkage_attack(df_a, df_b)
    assert result["target_rows_total"] == 500
    assert result["target_rows_tested"] == 400
    assert result["was_truncated"] is True


def test_no_truncation_flag_for_small_datasets():
    df_a = pd.DataFrame({"Age": [30, 40]})
    df_b = pd.DataFrame({"Age": [30, 40]})
    result = run_linkage_attack(df_a, df_b)
    assert result["was_truncated"] is False
    assert result["target_rows_tested"] == result["target_rows_total"] == 2
