from app.scoring.risk_engine import compute_risk_score


def test_high_linkage_and_uniqueness_yields_high_risk():
    uniqueness = {"unique_pct": 90.0}
    k_anon = {"checks": [{"k": 5, "at_risk_pct": 85.0, "at_risk_records": 850}], "min_class_size": 1}
    linkage = {"highest_confidence": 0.95}
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct=20.0)
    assert risk["overall_score"] > 70
    assert risk["risk_level"] in ("HIGH", "CRITICAL")


def test_low_signals_yield_low_risk():
    uniqueness = {"unique_pct": 1.0}
    k_anon = {"checks": [{"k": 5, "at_risk_pct": 2.0, "at_risk_records": 20}], "min_class_size": 8}
    linkage = {"highest_confidence": 0.05}
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct=0.0)
    assert risk["overall_score"] < 25
    assert risk["risk_level"] == "LOW"


def test_score_bounded_0_to_100():
    uniqueness = {"unique_pct": 100.0}
    k_anon = {"checks": [{"k": 5, "at_risk_pct": 100.0, "at_risk_records": 1000}], "min_class_size": 1}
    linkage = {"highest_confidence": 1.0}
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct=100.0)
    assert 0 <= risk["overall_score"] <= 100


def test_weights_are_configurable():
    uniqueness = {"unique_pct": 50.0}
    k_anon = {"checks": [{"k": 5, "at_risk_pct": 50.0, "at_risk_records": 500}], "min_class_size": 2}
    linkage = {"highest_confidence": 0.5}
    custom_weights = {
        "linkage_confidence": 1.0, "uniqueness": 0.0,
        "equivalence_class_risk": 0.0, "sensitive_attribute_exposure": 0.0,
    }
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct=0.0, weights=custom_weights)
    assert risk["overall_score"] == 50.0
