"""
Orchestrates the full ATTACK -> DETECT -> EXPLAIN -> FIX -> RE-TEST loop by
wiring together the individual engines. Kept separate from the API layer
so it can be reused by both the REST endpoints and the demo-mode script.
"""
import pandas as pd

from app.services.profiler import profile_dataset
from app.services.identifier_detection import classify_columns
from app.privacy.k_anonymity import uniqueness_analysis, k_anonymity_report, l_diversity_report
from app.attacks.linkage import run_linkage_attack
from app.scoring.risk_engine import compute_risk_score
from app.mitigation.transforms import recommend_mitigations, apply_mitigations


def full_analysis(df: pd.DataFrame, df_aux: pd.DataFrame = None) -> dict:
    """Runs profiling, classification, uniqueness/k-anonymity, and (if an
    auxiliary dataset is provided) a linkage attack + full risk score."""
    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]

    uniqueness = uniqueness_analysis(df, qi_columns)
    k_anon = k_anonymity_report(df, qi_columns)

    l_diversity = None
    if classification["sensitive_attributes"]:
        l_diversity = l_diversity_report(df, qi_columns, classification["sensitive_attributes"][0])

    if df_aux is not None:
        linkage = run_linkage_attack(df, df_aux)
    else:
        linkage = {"shared_columns": [], "matches": [], "candidates_tested": 0,
                   "matches_found": 0, "highest_confidence": 0.0}

    sensitive_exposure_pct = (
        (len(classification["sensitive_attributes"]) / max(1, profile["column_count"])) * 100
    )

    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct)

    return {
        "profile": profile,
        "classification": classification,
        "uniqueness": uniqueness,
        "k_anonymity": k_anon,
        "l_diversity": l_diversity,
        "linkage": linkage,
        "risk": risk,
    }


def fix_and_retest(df: pd.DataFrame, df_aux: pd.DataFrame, mitigations: list) -> dict:
    """Applies mitigations, re-runs the full pipeline on the transformed
    dataframe, and returns both the transformed dataframe and the new
    analysis results so before/after can be compared."""
    transformed = apply_mitigations(df, mitigations)
    # auxiliary dataset's overlap with transformed df is recomputed automatically
    # since run_linkage_attack only compares columns present in both.
    after_analysis = full_analysis(transformed, df_aux)
    return {"transformed_df": transformed, "analysis": after_analysis}
