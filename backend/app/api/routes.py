"""
REST API routes. Implements the endpoint list from the product spec
(section 25) and wires the frontend to the real analysis engines - no
endpoint here returns a hardcoded/fabricated value.
"""
import io
import json

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import JSONResponse

from app.config import MAX_UPLOAD_BYTES, GENERATED_DIR
from app.models import db
from app.models.schemas import MitigateRequest, DemoRunRequest
from app.storage import save_dataframe, load_dataframe
from app.services.profiler import profile_dataset
from app.services.identifier_detection import classify_columns
from app.services.pipeline import full_analysis, fix_and_retest
from app.services.synthetic_data import (
    generate_preset, generate_healthcare_auxiliary,
)
from app.services.llm_explain import explain_findings
from app.privacy.k_anonymity import uniqueness_analysis, k_anonymity_report
from app.attacks.linkage import run_linkage_attack
from app.scoring.risk_engine import compute_risk_score, explain_record_risk
from app.mitigation.transforms import recommend_mitigations, apply_mitigations
from app.mitigation.optimizer import optimize
from app.reporting.report_generator import build_report, render_markdown

router = APIRouter(prefix="/api")


def _read_upload(file: UploadFile) -> pd.DataFrame:
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds maximum upload size (10MB).")
    name = file.filename or "upload.csv"
    if name.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(content))
    try:
        return pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse file as CSV/Parquet: {e}")


def _load_df_or_404(dataset_id: str) -> pd.DataFrame:
    rec = db.get_dataset_record(dataset_id)
    if not rec:
        raise HTTPException(404, "Dataset not found")
    return load_dataframe(rec["file_path"])


# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), role: str = Form("main")):
    df = _read_upload(file)
    if df.empty:
        raise HTTPException(400, "Uploaded dataset is empty.")

    dataset_id = db.new_id()
    path = save_dataframe(df, dataset_id)
    db.save_dataset_record(dataset_id, file.filename, path, len(df), df.shape[1])
    db.log_audit(dataset_id, "upload", f"role={role}, rows={len(df)}, cols={df.shape[1]}")

    profile = profile_dataset(df)
    return {"dataset_id": dataset_id, "role": role, "profile": profile}


# ---------------------------------------------------------------------------
# 2. Profile
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/profile")
def get_profile(dataset_id: str):
    df = _load_df_or_404(dataset_id)
    profile = profile_dataset(df)
    db.save_analysis(dataset_id, "profile", profile)
    return profile


# ---------------------------------------------------------------------------
# 3. Analyze (classification + uniqueness + k-anonymity)
# ---------------------------------------------------------------------------
@router.post("/datasets/{dataset_id}/analyze")
def analyze_dataset(dataset_id: str):
    df = _load_df_or_404(dataset_id)
    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]

    uniqueness = uniqueness_analysis(df, qi_columns)
    k_anon = k_anonymity_report(df, qi_columns)

    result = {
        "profile": profile,
        "classification": classification,
        "uniqueness": uniqueness,
        "k_anonymity": k_anon,
    }
    db.save_analysis(dataset_id, "analyze", result)
    db.log_audit(dataset_id, "analyze", f"qi_columns={qi_columns}")
    return result


# ---------------------------------------------------------------------------
# 4. Attack (record linkage against an auxiliary dataset)
# ---------------------------------------------------------------------------
@router.post("/datasets/{dataset_id}/attack")
def attack_dataset(dataset_id: str, aux_dataset_id: str = Form(...)):
    df = _load_df_or_404(dataset_id)
    df_aux = _load_df_or_404(aux_dataset_id)

    linkage = run_linkage_attack(df, df_aux)

    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]
    uniqueness = uniqueness_analysis(df, qi_columns)
    k_anon = k_anonymity_report(df, qi_columns)
    sensitive_exposure_pct = (
        (len(classification["sensitive_attributes"]) / max(1, profile["column_count"])) * 100
    )
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_exposure_pct)

    result = {"linkage": linkage, "risk": risk, "aux_dataset_id": aux_dataset_id}
    db.save_analysis(dataset_id, "attack", result)
    db.save_analysis(dataset_id, "risk", risk)
    db.log_audit(dataset_id, "attack", f"aux={aux_dataset_id}, matches={linkage['matches_found']}")
    return result


# ---------------------------------------------------------------------------
# 5. Risks
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/risks")
def get_risks(dataset_id: str):
    analysis = db.get_latest_analysis(dataset_id, "risk")
    if not analysis:
        raise HTTPException(404, "No risk analysis found. Run /attack first.")
    return analysis["result"]


# ---------------------------------------------------------------------------
# 6. Vulnerable clusters
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/clusters")
def get_clusters(dataset_id: str, k: int = 5):
    df = _load_df_or_404(dataset_id)
    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]

    if not qi_columns:
        return {"clusters": [], "qi_columns": []}

    sub = df[qi_columns].astype(str).fillna("__MISSING__")
    grouped = sub.groupby(qi_columns).size().reset_index(name="size")
    at_risk = grouped[grouped["size"] < k].sort_values("size")

    clusters = []
    for i, (_, row) in enumerate(at_risk.iterrows()):
        qi_values = {col: row[col] for col in qi_columns}
        size = int(row["size"])
        risk_level = "CRITICAL" if size == 1 else "HIGH" if size < k / 2 else "MODERATE"
        clusters.append({
            "cluster_id": i + 1,
            "records": size,
            "risk_level": risk_level,
            "quasi_identifiers": qi_values,
        })

    return {"clusters": clusters[:100], "qi_columns": qi_columns, "k": k,
            "total_vulnerable_clusters": len(at_risk)}


@router.get("/datasets/{dataset_id}/explain/{match_index}")
def explain_match(dataset_id: str, match_index: int):
    analysis = db.get_latest_analysis(dataset_id, "attack")
    if not analysis:
        raise HTTPException(404, "Run /attack first.")
    matches = analysis["result"]["linkage"]["matches"]
    if match_index < 0 or match_index >= len(matches):
        raise HTTPException(404, "Match index out of range.")
    return explain_record_risk(matches[match_index])


# ---------------------------------------------------------------------------
# 7. Mitigate
# ---------------------------------------------------------------------------
@router.post("/datasets/{dataset_id}/mitigate")
def mitigate_dataset(dataset_id: str, body: MitigateRequest):
    df = _load_df_or_404(dataset_id)
    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]
    k_anon = k_anonymity_report(df, qi_columns)

    mitigations = body.mitigations or recommend_mitigations(profile, classification, k_anon)
    optimization = optimize(df, mitigations, qi_columns)

    transformed = apply_mitigations(df, mitigations)
    mitigated_id = db.new_id()
    path = save_dataframe(transformed, mitigated_id, generated=True)
    db.save_dataset_record(mitigated_id, f"mitigated_{dataset_id}", path,
                            len(transformed), transformed.shape[1],
                            is_demo=False, parent_id=dataset_id)

    result = {
        "mitigations_applied": mitigations,
        "optimization": optimization,
        "mitigated_dataset_id": mitigated_id,
    }
    db.save_analysis(dataset_id, "mitigation", result)
    db.log_audit(dataset_id, "mitigate", f"mitigated_dataset_id={mitigated_id}")
    return result


# ---------------------------------------------------------------------------
# 8. Retest (fix & re-test loop)
# ---------------------------------------------------------------------------
@router.post("/datasets/{dataset_id}/retest")
def retest_dataset(dataset_id: str, mitigated_dataset_id: str = Form(...),
                    aux_dataset_id: str = Form(...)):
    original_attack = db.get_latest_analysis(dataset_id, "attack")
    original_risk = db.get_latest_analysis(dataset_id, "risk")
    if not original_risk:
        raise HTTPException(400, "Run /attack on the original dataset before retesting.")

    mitigated_df = _load_df_or_404(mitigated_dataset_id)
    aux_df = _load_df_or_404(aux_dataset_id)

    after_analysis = full_analysis(mitigated_df, aux_df)

    comparison = {
        "before": {
            "risk_score": original_risk["result"]["overall_score"],
            "risk_level": original_risk["result"]["risk_level"],
            "at_risk_records": original_risk["result"]["at_risk_records"],
            "min_class_size": original_risk["result"]["min_class_size"],
        },
        "after": {
            "risk_score": after_analysis["risk"]["overall_score"],
            "risk_level": after_analysis["risk"]["risk_level"],
            "at_risk_records": after_analysis["risk"]["at_risk_records"],
            "min_class_size": after_analysis["risk"]["min_class_size"],
        },
    }
    comparison["risk_score_delta"] = round(
        comparison["before"]["risk_score"] - comparison["after"]["risk_score"], 2
    )

    result = {"comparison": comparison, "after_analysis": after_analysis}
    db.save_analysis(dataset_id, "retest", result)
    db.log_audit(dataset_id, "retest", f"delta={comparison['risk_score_delta']}")
    return result


# ---------------------------------------------------------------------------
# 9. Comparison
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/comparison")
def get_comparison(dataset_id: str):
    analysis = db.get_latest_analysis(dataset_id, "retest")
    if not analysis:
        raise HTTPException(404, "No retest found. Run /retest first.")
    return analysis["result"]["comparison"]


# ---------------------------------------------------------------------------
# 10. Report
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/report")
def get_report(dataset_id: str, format: str = "json"):
    rec = db.get_dataset_record(dataset_id)
    if not rec:
        raise HTTPException(404, "Dataset not found")

    analyze_res = db.get_latest_analysis(dataset_id, "analyze")
    attack_res = db.get_latest_analysis(dataset_id, "attack")
    mitigation_res = db.get_latest_analysis(dataset_id, "mitigation")
    retest_res = db.get_latest_analysis(dataset_id, "retest")

    if not analyze_res or not attack_res:
        raise HTTPException(400, "Run /analyze and /attack before generating a report.")

    profile = analyze_res["result"]["profile"]
    classification = analyze_res["result"]["classification"]
    k_anon = analyze_res["result"]["k_anonymity"]
    uniqueness = analyze_res["result"]["uniqueness"]
    linkage = attack_res["result"]["linkage"]
    risk = attack_res["result"]["risk"]
    mitigations = mitigation_res["result"]["mitigations_applied"] if mitigation_res else []
    after = retest_res["result"]["comparison"]["after"] if retest_res else None

    report = build_report(rec["name"], profile, classification, k_anon,
                           uniqueness, linkage, risk, mitigations, after)
    report["llm_explanation"] = explain_findings(risk)

    db.log_audit(dataset_id, "report_generated")

    if format == "markdown":
        md = render_markdown(report)
        return Response(content=md, media_type="text/markdown")
    return JSONResponse(content=report)


# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------
@router.post("/synthetic/generate")
def generate_synthetic(preset: str = Form("healthcare"), n: int = Form(500)):
    try:
        df = generate_preset(preset, n)
    except ValueError as e:
        raise HTTPException(400, str(e))

    dataset_id = db.new_id()
    path = save_dataframe(df, dataset_id, generated=True)
    db.save_dataset_record(dataset_id, f"synthetic_{preset}", path, len(df), df.shape[1], is_demo=True)
    db.log_audit(dataset_id, "synthetic_generate", f"preset={preset}, n={n}")

    profile = profile_dataset(df)
    return {"dataset_id": dataset_id, "preset": preset, "profile": profile}


# ---------------------------------------------------------------------------
# 11. Demo mode - runs the entire ATTACK -> FIX -> RE-TEST loop in one call
# ---------------------------------------------------------------------------
@router.post("/demo/run")
def run_demo(body: DemoRunRequest):
    df_main = generate_preset(body.preset, body.n)

    if body.preset == "healthcare":
        df_aux = generate_healthcare_auxiliary(df_main)
    else:
        # generic auxiliary: sample overlapping quasi-identifier columns
        df_aux = df_main.sample(frac=0.6, random_state=3).drop(
            columns=[c for c in df_main.columns if c.lower() in
                     ("diagnosis", "incomeband", "score", "creditcategory")],
            errors="ignore",
        )

    main_id = db.new_id()
    aux_id = db.new_id()
    db.save_dataset_record(main_id, f"demo_{body.preset}",
                            save_dataframe(df_main, main_id, generated=True),
                            len(df_main), df_main.shape[1], is_demo=True)
    db.save_dataset_record(aux_id, f"demo_{body.preset}_auxiliary",
                            save_dataframe(df_aux, aux_id, generated=True),
                            len(df_aux), df_aux.shape[1], is_demo=True)
    db.log_audit(main_id, "demo_run", f"preset={body.preset}")

    # STEP: profile + detect
    before_analysis = full_analysis(df_main, df_aux)

    # STEP: recommend + apply mitigation
    mitigations = recommend_mitigations(
        before_analysis["profile"], before_analysis["classification"], before_analysis["k_anonymity"]
    )
    mitigated_df = apply_mitigations(df_main, mitigations)
    mitigated_id = db.new_id()
    db.save_dataset_record(mitigated_id, f"demo_{body.preset}_mitigated",
                            save_dataframe(mitigated_df, mitigated_id, generated=True),
                            len(mitigated_df), mitigated_df.shape[1],
                            is_demo=True, parent_id=main_id)

    # STEP: re-test
    after_analysis = full_analysis(mitigated_df, df_aux)

    comparison = {
        "before": {
            "risk_score": before_analysis["risk"]["overall_score"],
            "risk_level": before_analysis["risk"]["risk_level"],
            "at_risk_records": before_analysis["risk"]["at_risk_records"],
            "min_class_size": before_analysis["k_anonymity"].get("min_class_size"),
        },
        "after": {
            "risk_score": after_analysis["risk"]["overall_score"],
            "risk_level": after_analysis["risk"]["risk_level"],
            "at_risk_records": after_analysis["risk"]["at_risk_records"],
            "min_class_size": after_analysis["k_anonymity"].get("min_class_size"),
        },
    }
    comparison["risk_score_delta"] = round(
        comparison["before"]["risk_score"] - comparison["after"]["risk_score"], 2
    )

    db.save_analysis(main_id, "attack", {"linkage": before_analysis["linkage"], "risk": before_analysis["risk"]})
    db.save_analysis(main_id, "risk", before_analysis["risk"])
    db.save_analysis(main_id, "analyze", {
        "profile": before_analysis["profile"],
        "classification": before_analysis["classification"],
        "uniqueness": before_analysis["uniqueness"],
        "k_anonymity": before_analysis["k_anonymity"],
    })
    db.save_analysis(main_id, "mitigation", {"mitigations_applied": mitigations, "mitigated_dataset_id": mitigated_id})
    db.save_analysis(main_id, "retest", {"comparison": comparison, "after_analysis": after_analysis})

    return {
        "main_dataset_id": main_id,
        "aux_dataset_id": aux_id,
        "mitigated_dataset_id": mitigated_id,
        "before": before_analysis,
        "mitigations": mitigations,
        "after": after_analysis,
        "comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Audit log (transparency / security requirement)
# ---------------------------------------------------------------------------
@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: str):
    """Downloads a dataset (original, mitigated, or rescued) as CSV.
    This was a real gap found during audit: every other part of the app
    could reference a dataset by ID, but nothing actually let a user get
    the file back out. Works for any dataset_id in the datasets table -
    core PrivaLens mitigated datasets and DataRescue's rescued datasets
    both use the same table, so this one endpoint covers both."""
    rec = db.get_dataset_record(dataset_id)
    if not rec:
        raise HTTPException(404, "Dataset not found")
    df = load_dataframe(rec["file_path"])
    csv_bytes = df.to_csv(index=False)
    safe_name = rec["name"].replace('"', "").replace("/", "_")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
    )


@router.get("/audit")
def get_audit(dataset_id: str = None):
    return {"entries": db.list_audit(dataset_id)}
