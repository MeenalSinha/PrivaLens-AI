"""
DataRescue API. Endpoints match the spec's section 13 list exactly:
POST /api/rescue/start, GET /api/rescue/{job_id}, GET /api/rescue/{job_id}/events,
POST /api/rescue/{job_id}/approve, POST /api/rescue/{job_id}/reject
plus GET /api/rescue/jobs for the job list/history view,
GET /api/rescue/{job_id}/report for the assembled rescue report (JSON/Markdown),
and GET /api/datasets/{dataset_id}/download (in app/api/routes.py) for
downloading the rescued dataset itself as CSV.
"""
import asyncio

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.rescue import job_store
from app.rescue.orchestrator import DataRescueAgent, approval_registry

router = APIRouter(prefix="/api/rescue")


class RescueStartRequest(BaseModel):
    dataset_id: str
    aux_dataset_id: str | None = None
    target_column: str | None = None
    objective: str | None = None


class ApprovalRequest(BaseModel):
    action_id: str


class JudgeModeRequest(BaseModel):
    n: int = 500


@router.post("/judge-mode/prepare")
def prepare_judge_mode(body: JudgeModeRequest):
    """Generates the deterministic Judge Mode showcase dataset (spec
    section 20): a synthetic healthcare dataset with real, injected
    data-quality problems (duplicates, missing values, case
    inconsistency, whitespace, malformed dates) PLUS the existing
    privacy vulnerabilities the healthcare generator already produces,
    plus a matching auxiliary attacker dataset. Returns dataset IDs
    ready to hand straight to POST /api/rescue/start - this endpoint
    only prepares the data, it does not run the agent."""
    from app.services.synthetic_data import (
        generate_healthcare_dataset, generate_healthcare_auxiliary, inject_quality_issues,
    )
    from app.services.profiler import profile_dataset
    from app.storage import save_dataframe
    from app.models import db as core_db

    clean_df = generate_healthcare_dataset(body.n)
    messy_df = inject_quality_issues(clean_df)
    aux_df = generate_healthcare_auxiliary(clean_df)

    main_id = core_db.new_id()
    aux_id = core_db.new_id()
    core_db.save_dataset_record(main_id, "judge_mode_messy_hospital_dataset.csv",
                                 save_dataframe(messy_df, main_id, generated=True),
                                 len(messy_df), messy_df.shape[1], is_demo=True)
    core_db.save_dataset_record(aux_id, "judge_mode_auxiliary.csv",
                                 save_dataframe(aux_df, aux_id, generated=True),
                                 len(aux_df), aux_df.shape[1], is_demo=True)
    core_db.log_audit(main_id, "judge_mode_prepare", f"n={body.n}")

    return {
        "dataset_id": main_id,
        "aux_dataset_id": aux_id,
        "profile": profile_dataset(messy_df),
    }


@router.post("/start")
async def start_rescue(body: RescueStartRequest):
    job = job_store.create_job(body.dataset_id, body.aux_dataset_id, body.target_column, body.objective)
    agent = DataRescueAgent(job["job_id"], body.dataset_id, body.aux_dataset_id, body.target_column, body.objective)
    # Scheduled as a background task - the HTTP response returns immediately
    # and the job keeps running in this server process regardless of
    # whether the caller stays connected. See orchestrator.py docstring
    # for the exact disclosed scope of "background execution" here.
    task = asyncio.create_task(agent.run())

    def _log_unhandled(t: asyncio.Task):
        # Without this, an exception in a fire-and-forget task is only
        # ever printed by asyncio's default handler when the task is
        # garbage-collected - which can be much later, or never during
        # a short-lived dev server. The orchestrator already records
        # failures into job state; this just guarantees the exception
        # itself is never silently lost from the server logs too.
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            print(f"[DataRescue] job {job['job_id']} background task raised: {exc!r}")

    task.add_done_callback(_log_unhandled)
    return {"job_id": job["job_id"], "status": job["status"]}


@router.get("/jobs")
def list_rescue_jobs():
    return {"jobs": job_store.list_jobs()}


@router.get("/{job_id}")
def get_rescue_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Rescue job not found")
    return job


@router.get("/{job_id}/events")
def get_rescue_events(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Rescue job not found")
    return {"events": job["audit_events"]}


@router.post("/{job_id}/approve")
def approve_action(job_id: str, body: ApprovalRequest):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Rescue job not found")
    if job.get("pending_action_id") != body.action_id:
        raise HTTPException(400, f"Action {body.action_id} is not currently awaiting approval for this job.")
    ok = approval_registry.decide(job_id, body.action_id, "approved")
    if not ok:
        raise HTTPException(409, "No pending approval wait found for this action (job may have already moved on).")
    return {"status": "approved", "action_id": body.action_id}


@router.post("/{job_id}/reject")
def reject_action(job_id: str, body: ApprovalRequest):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Rescue job not found")
    if job.get("pending_action_id") != body.action_id:
        raise HTTPException(400, f"Action {body.action_id} is not currently awaiting approval for this job.")
    ok = approval_registry.decide(job_id, body.action_id, "rejected")
    if not ok:
        raise HTTPException(409, "No pending approval wait found for this action (job may have already moved on).")
    return {"status": "rejected", "action_id": body.action_id}


@router.get("/{job_id}/report")
def get_rescue_report(job_id: str, format: str = "json"):
    """Assembles the rescue report (spec section 20/24): executive
    summary, problems discovered, privacy/quality/ML-readiness
    assessment, autonomous decisions, human approvals, transformations
    applied, attack results, utility impact, before/after, and the full
    audit trail - all pulled directly from the job's real recorded
    state, nothing recomputed or invented for the report. A real gap
    found during audit: the job state was queryable but there was no
    endpoint that assembled it into an actual report document, and no
    way to download the rescued dataset at all (see
    GET /api/datasets/{id}/download, added alongside this)."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Rescue job not found")
    if job["status"] not in ("completed", "failed"):
        raise HTTPException(400, f"Job is still {job['status']} - a report is only available once it finishes.")

    actions_by_status = {"applied": [], "rejected": [], "skipped_no_approval": [], "pending": []}
    for a in job["proposed_actions"]:
        if a["status"] == "applied":
            actions_by_status["applied"].append(a)
        elif a["status"] == "rejected":
            actions_by_status["rejected"].append(a)
        elif a["status"] == "timeout":
            actions_by_status["skipped_no_approval"].append(a)
        else:
            actions_by_status["pending"].append(a)

    report = {
        "job_id": job_id,
        "generated_at": job["updated_at"],
        "status": job["status"],
        "objective": job.get("objective"),
        "target_column": job.get("target_column"),
        "executive_summary": {
            "data_health_before": job["before_metrics"]["data_health"] if job["before_metrics"] else None,
            "data_health_after": job["after_metrics"]["data_health"] if job["after_metrics"] else None,
            "rescue_score": job.get("rescue_score"),
            "verification_passed": job["verification"]["passed"] if job["verification"] else None,
        },
        "problems_discovered": {
            "quality_issues": job["discovered_issues"],
            "ml_readiness_findings": job["ml_findings"],
        },
        "privacy_assessment": {"before": job["privacy_before"], "after": job["privacy_after"]},
        "quality_and_ml_assessment": {"before": job["before_metrics"], "after": job["after_metrics"]},
        "decisions": {
            "total_proposed": len(job["proposed_actions"]),
            "applied": [{"action_type": a["action_type"], "column": a["column"], "policy": a["policy"], "description": a["description"]} for a in actions_by_status["applied"]],
            "rejected_by_human": [{"action_type": a["action_type"], "column": a["column"]} for a in actions_by_status["rejected"]],
            "skipped_no_response": [{"action_type": a["action_type"], "column": a["column"]} for a in actions_by_status["skipped_no_approval"]],
            "still_pending": [{"action_type": a["action_type"], "column": a["column"]} for a in actions_by_status["pending"]],
        },
        "human_approvals": job.get("approved_actions", []),
        "utility_impact": job.get("utility"),
        "final_dataset_id": job.get("final_dataset_id"),
        "error": job.get("error"),
        "audit_trail": job["audit_events"],
        "disclaimer": (
            "This report reflects the rescue job's own recorded state - every figure here was "
            "computed by deterministic detection and scoring code during the job run, not "
            "regenerated for this report. See AUDIT_RESCUE.md for what this agent does and does not do."
        ),
    }

    if format == "markdown":
        lines = [f"# DataRescue Report — Job {job_id}\n"]
        lines.append(f"**Status:** {report['status']}  ")
        if report["objective"]:
            lines.append(f"**Objective:** {report['objective']}  ")
        lines.append("")
        lines.append("## Executive Summary\n")
        es = report["executive_summary"]
        if es["data_health_before"] is not None:
            lines.append(f"- Data Health: {es['data_health_before']} -> {es['data_health_after']}")
            lines.append(f"- Rescue Score: {es['rescue_score']}/100")
            lines.append(f"- Verification passed: {es['verification_passed']}")
        lines.append("")
        lines.append("## Problems Discovered\n")
        lines.append(f"- {len(report['problems_discovered']['quality_issues'])} data-quality issues")
        lines.append(f"- {len(report['problems_discovered']['ml_readiness_findings'])} ML-readiness findings")
        lines.append("")
        lines.append("## Decisions\n")
        d = report["decisions"]
        lines.append(f"- {len(d['applied'])} actions applied")
        lines.append(f"- {len(d['rejected_by_human'])} rejected by human")
        lines.append(f"- {len(d['skipped_no_response'])} skipped (no response)")
        for a in d["applied"]:
            lines.append(f"  - **{a['action_type']}** on {a['column']} ({a['policy']}): {a['description']}")
        lines.append("")
        if report["utility_impact"]:
            lines.append("## Utility Impact\n")
            u = report["utility_impact"]
            lines.append(f"- Rows retained: {u['row_retention_pct']}%")
            lines.append(f"- Avg. cardinality retained: {u['avg_cardinality_retention_pct']}%")
            lines.append("")
        lines.append("## Audit Trail\n")
        for e in report["audit_trail"]:
            lines.append(f"- `{e['timestamp'][:19]}` **{e['agent']}**: {e['message']}")
        lines.append("")
        lines.append(f"## Disclaimer\n\n{report['disclaimer']}")
        return Response(content="\n".join(lines), media_type="text/markdown")

    return report
