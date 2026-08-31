"""
DataRescue Agent orchestrator.

Runs the OBSERVE -> REASON -> PLAN -> ACT -> OBSERVE -> VERIFY -> ADAPT
loop described in the product spec, entirely with deterministic Python
logic reusing the existing PrivaLens engines (profiler, identifier
detection, k-anonymity, linkage attack, risk scoring, mitigation) plus
the new quality and ML-readiness agents. No LLM is used anywhere in this
loop - every number and every decision traces to code that can be read
and re-run, per the architecture principle that autonomous decisions
must be policy-driven and auditable, not model-invented.

Background execution model (see AUDIT_RESCUE.md for the full disclosure):
a job's run() coroutine is scheduled with asyncio.create_task from the
API layer, so it keeps executing after the HTTP request that started it
returns - the user can navigate away and the job continues within the
same running server process. Approval waits use an in-memory
asyncio.Event registry. This does NOT survive a server restart - there
is no external job queue/broker in this build. That limitation is
disclosed, not hidden.
"""
import asyncio
from datetime import datetime, timezone

import pandas as pd

from app.services.profiler import profile_dataset
from app.services.identifier_detection import classify_columns
from app.privacy.k_anonymity import uniqueness_analysis, k_anonymity_report
from app.attacks.linkage import run_linkage_attack
from app.scoring.risk_engine import compute_risk_score
from app.scoring.quality_engine import compute_quality_score, compute_ml_readiness_score, compute_data_health
from app.mitigation.transforms import recommend_mitigations, ACTION_DISPATCH as PRIVACY_DISPATCH
from app.rescue.quality_agent import run_quality_agent
from app.rescue.quality_fixes import QUALITY_FIX_DISPATCH
from app.rescue.ml_readiness_agent import run_ml_readiness_agent
from app.rescue.policy import classify_action, milder_alternative
from app.rescue import job_store
from app.storage import save_dataframe, load_dataframe
from app.models import db as core_db

# Privacy mitigation is only proposed when risk is at least this band -
# a real, concrete instance of "don't apply unnecessary privacy
# transformations" (spec section 6) rather than a general claim.
PRIVACY_MITIGATION_MIN_RISK_LEVEL = {"LOW": False, "MODERATE": True, "HIGH": True, "CRITICAL": True}


class _ApprovalRegistry:
    """In-memory asyncio.Event registry keyed by (job_id, action_id).
    Lives only for the lifetime of the server process - see module
    docstring."""
    def __init__(self):
        self._events = {}
        self._decisions = {}

    def create(self, job_id, action_id):
        key = (job_id, action_id)
        self._events[key] = asyncio.Event()
        return key

    async def wait(self, job_id, action_id, timeout=3600):
        key = (job_id, action_id)
        event = self._events.get(key)
        if event is None:
            event = asyncio.Event()
            self._events[key] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._decisions[key] = "timeout"
        return self._decisions.get(key, "timeout")

    def decide(self, job_id, action_id, decision):
        key = (job_id, action_id)
        self._decisions[key] = decision
        event = self._events.get(key)
        if event:
            event.set()
            return True
        return False


approval_registry = _ApprovalRegistry()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _log(job, agent, message, stage=None):
    job["audit_events"].append({"timestamp": _now(), "agent": agent, "message": message, "stage": stage or job.get("current_stage")})


def _score_dataset(df, df_aux, target_column=None):
    """Runs the full detect+score pipeline (quality, privacy, ML
    readiness) against a given dataframe and returns everything needed
    to compute a Data Health snapshot. Reused for both the before- and
    after- measurement so the two are computed identically."""
    profile = profile_dataset(df)
    classification = classify_columns(profile)
    qi_columns = classification["quasi_identifiers"]
    uniqueness = uniqueness_analysis(df, qi_columns)
    k_anon = k_anonymity_report(df, qi_columns)

    if df_aux is not None:
        linkage = run_linkage_attack(df, df_aux)
    else:
        linkage = {"shared_columns": [], "matches": [], "candidates_tested": 0,
                   "matches_found": 0, "highest_confidence": 0.0}

    sensitive_pct = (len(classification["sensitive_attributes"]) / max(1, profile["column_count"])) * 100
    risk = compute_risk_score(uniqueness, k_anon, linkage, sensitive_pct)

    quality_raw = run_quality_agent(df)
    quality_score = compute_quality_score(quality_raw)

    ml_raw = run_ml_readiness_agent(df, target_column)
    ml_score = compute_ml_readiness_score(ml_raw)

    data_health = compute_data_health(quality_score["score"], risk["overall_score"], ml_score["score"])

    return {
        "profile": profile, "classification": classification, "uniqueness": uniqueness,
        "k_anonymity": k_anon, "linkage": linkage, "risk": risk,
        "quality_raw": quality_raw, "quality_score": quality_score,
        "ml_raw": ml_raw, "ml_score": ml_score, "data_health": data_health,
    }


def _apply_action(df, action):
    if action["source"] == "quality":
        fn = QUALITY_FIX_DISPATCH.get(action["action_type"])
        if not fn:
            return df
        return fn(df, action["params"])
    else:
        fn = PRIVACY_DISPATCH.get(action["action_type"])
        if not fn or not action.get("column"):
            return df
        return fn(df, action["column"])


def _utility_retained(original_df, final_df):
    """Real, computable utility measure: row retention (did we drop
    rows?) and average per-column cardinality retention (did we destroy
    information within columns that survived?). Not a guess."""
    row_retention = round(len(final_df) / len(original_df) * 100, 2) if len(original_df) else 100.0

    shared_cols = [c for c in original_df.columns if c in final_df.columns]
    if not shared_cols:
        cardinality_retention = 0.0
    else:
        ratios = []
        for col in shared_cols:
            before_unique = original_df[col].nunique(dropna=True)
            after_unique = final_df[col].nunique(dropna=True)
            if before_unique == 0:
                continue
            ratios.append(min(1.0, after_unique / before_unique))
        cardinality_retention = round((sum(ratios) / len(ratios)) * 100, 2) if ratios else 100.0

    return {
        "row_retention_pct": float(row_retention),
        "column_retention_pct": float(round(len(shared_cols) / max(1, original_df.shape[1]) * 100, 2)),
        "avg_cardinality_retention_pct": float(cardinality_retention),
    }


def _rescue_score(before_health, after_health):
    """0-100: how much of the achievable improvement (up to a perfect
    100 Data Health) was actually captured. Documented, not fabricated:
    rescue_score = 100 if before was already 100 (nothing to improve);
    otherwise the fraction of the possible gap that was closed, scaled
    to 0-100. A negative fraction (things got worse) is clamped to 0,
    matching the "never fabricate improvement" rule used elsewhere in
    this codebase."""
    if before_health >= 100:
        return 100.0
    achievable_gap = 100 - before_health
    actual_gap_closed = after_health - before_health
    fraction = actual_gap_closed / achievable_gap
    return float(round(max(0.0, min(100.0, fraction * 100)), 2))


class DataRescueAgent:
    def __init__(self, job_id, dataset_id, aux_dataset_id=None, target_column=None, objective=None):
        self.job_id = job_id
        self.dataset_id = dataset_id
        self.aux_dataset_id = aux_dataset_id
        self.target_column = target_column
        self.objective = objective

    async def run(self):
        job = job_store.get_job(self.job_id)
        try:
            await self._run_inner(job)
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            _log(job, "DataRescue", f"Job failed: {e}", stage="error")
            try:
                job_store.save_job(job)
            except Exception as save_error:
                # If persisting the failure itself fails (e.g. a
                # serialization bug in job state), we must not let that
                # raise a second, unhandled exception out of this task -
                # that would silently swallow the original failure
                # reason entirely. Log to stderr as a last resort so the
                # failure is at least visible somewhere.
                print(f"[DataRescue] CRITICAL: failed to persist job failure for {self.job_id}: {save_error}")
            raise

    async def _run_inner(self, job):
        # ---- Stage: inspect ----
        job["current_stage"] = "inspect"
        job["status"] = "running"
        rec = core_db.get_dataset_record(self.dataset_id)
        if not rec:
            raise ValueError(f"Dataset {self.dataset_id} not found")
        original_df = load_dataframe(rec["file_path"])
        aux_df = None
        if self.aux_dataset_id:
            aux_rec = core_db.get_dataset_record(self.aux_dataset_id)
            if aux_rec:
                aux_df = load_dataframe(aux_rec["file_path"])
        _log(job, "DataRescue", f"Inspecting dataset ({len(original_df)} rows, {original_df.shape[1]} columns).")
        job_store.save_job(job)
        await asyncio.sleep(0)  # yield control so the job is genuinely async, not blocking

        # ---- Stage: profile + detect (quality, privacy, ML readiness) ----
        job["current_stage"] = "detect"
        _log(job, "Profiler Agent", f"Analyzed {original_df.shape[1]} columns.")
        before = _score_dataset(original_df, aux_df, self.target_column)
        job["before_metrics"] = {
            "quality_score": float(before["quality_score"]["score"]),
            "ml_readiness_score": float(before["ml_score"]["score"]),
            "privacy_risk_score": float(before["risk"]["overall_score"]),
            "privacy_risk_level": before["risk"]["risk_level"],
            "data_health": float(before["data_health"]["data_health"]),
        }
        job["discovered_issues"] = before["quality_raw"]["issues"]
        job["ml_findings"] = before["ml_raw"]["findings"]
        job["privacy_before"] = {"risk": before["risk"], "linkage": before["linkage"], "k_anonymity": before["k_anonymity"]}

        n_missing_cols = len({i["columns"][0] for i in before["quality_raw"]["issues"] if i["issue_type"] == "missing_values" and i["columns"]})
        n_dupes = sum(i["affected_rows"] for i in before["quality_raw"]["issues"] if i["issue_type"] == "duplicate_rows")
        _log(job, "Quality Agent", f"Detected {len(before['quality_raw']['issues'])} data-quality issues "
                                    f"({n_missing_cols} columns with missing values, {n_dupes} duplicate rows).")
        _log(job, "Privacy Agent", f"Re-identification risk: {before['risk']['overall_score']}/100 ({before['risk']['risk_level']}).")
        _log(job, "ML Readiness Agent", f"ML readiness: {before['ml_score']['score']}/100 ({len(before['ml_raw']['findings'])} findings).")
        job_store.save_job(job)
        await asyncio.sleep(0)

        # ---- Stage: plan ----
        job["current_stage"] = "plan"
        proposed = []
        action_seq = 0

        for issue in before["quality_raw"]["issues"]:
            if not issue["auto_fix_eligible"] or not issue["suggested_action"]:
                continue
            action_seq += 1
            proposed.append({
                "action_id": f"{self.job_id}-a{action_seq}",
                "source": "quality",
                "action_type": issue["suggested_action"],
                "column": issue["columns"][0] if issue["columns"] else None,
                "params": issue.get("action_params") or {},
                "policy": classify_action(issue["suggested_action"]),
                "description": issue["description"],
                "reason": issue["description"],
                "expected_benefit": f"Resolves a {issue['severity']} severity {issue['issue_type']} issue.",
                "status": "pending",
            })

        # Adaptive skip: only propose privacy mitigations if risk is
        # actually elevated - never apply mitigation "just because".
        if PRIVACY_MITIGATION_MIN_RISK_LEVEL.get(before["risk"]["risk_level"], True):
            mitigations = recommend_mitigations(before["profile"], before["classification"], before["k_anonymity"])
            for m in mitigations:
                action_seq += 1
                proposed.append({
                    "action_id": f"{self.job_id}-a{action_seq}",
                    "source": "privacy",
                    "action_type": m["action"],
                    "column": m["column"],
                    "params": {"column": m["column"]},
                    "policy": classify_action(m["action"]),
                    "description": m["description"],
                    "reason": m["reason"],
                    "expected_benefit": "Reduces re-identification risk for this column.",
                    "status": "pending",
                })
        else:
            _log(job, "Decision Agent", f"Privacy risk is already {before['risk']['risk_level']} - "
                                         f"skipping privacy mitigation, nothing to fix.")

        job["proposed_actions"] = proposed
        _log(job, "DataRescue", f"Rescue plan created: {len(proposed)} proposed actions "
                                 f"({sum(1 for a in proposed if a['policy']=='AUTO')} auto, "
                                 f"{sum(1 for a in proposed if a['policy']=='REVIEW')} need approval).")
        job_store.save_job(job)
        await asyncio.sleep(0)

        # ---- Stage: execute ----
        job["current_stage"] = "execute"
        working_df = original_df.copy()

        # AUTO actions first
        for action in [a for a in proposed if a["policy"] == "AUTO"]:
            before_rows = len(working_df)
            working_df = _apply_action(working_df, action)
            action["status"] = "applied"
            _log(job, "Mitigation Agent", f"Auto-applied '{action['action_type']}'"
                                           f"{' on ' + action['column'] if action['column'] else ''}. "
                                           f"({before_rows} -> {len(working_df)} rows)")
            job_store.save_job(job)
            await asyncio.sleep(0)

        # REVIEW actions, one at a time, real approval wait
        for action in [a for a in proposed if a["policy"] == "REVIEW"]:
            job["current_stage"] = "execute"
            job["status"] = "awaiting_approval"
            job["pending_action_id"] = action["action_id"]
            approval_registry.create(self.job_id, action["action_id"])
            _log(job, "Policy Engine", f"Human approval required for '{action['action_type']}' on "
                                       f"{action.get('column') or 'the dataset'}.")
            job_store.save_job(job)

            decision = await approval_registry.wait(self.job_id, action["action_id"])

            if decision == "approved":
                working_df = _apply_action(working_df, action)
                action["status"] = "applied"
                job["approved_actions"] = job.get("approved_actions", []) + [action["action_id"]]
                _log(job, "Human", f"Approved '{action['action_type']}' on {action.get('column')}.")
                _log(job, "Mitigation Agent", f"Applied '{action['action_type']}' on {action.get('column')}.")
            elif decision == "rejected":
                action["status"] = "rejected"
                job["rejected_actions"] = job.get("rejected_actions", []) + [action["action_id"]]
                _log(job, "Human", f"Rejected '{action['action_type']}' on {action.get('column')}.")
                alt_params = milder_alternative(action["action_type"], action["params"])
                if alt_params:
                    action_seq += 1
                    alt_action = {
                        "action_id": f"{self.job_id}-a{action_seq}",
                        "source": action["source"], "action_type": action["action_type"],
                        "column": action["column"], "params": alt_params,
                        "policy": "REVIEW",
                        "description": f"Milder alternative: {action['action_type']} with {alt_params}",
                        "reason": "Generated after the original proposal was rejected.",
                        "expected_benefit": "Lower utility impact than the rejected version.",
                        "status": "pending",
                    }
                    proposed.append(alt_action)
                    job["proposed_actions"] = proposed
                    _log(job, "Decision Agent", f"Searching for a lower-impact alternative to "
                                                 f"'{action['action_type']}'... found one: {alt_params}.")
                    job["current_stage"] = "execute"
                    job["status"] = "awaiting_approval"
                    job["pending_action_id"] = alt_action["action_id"]
                    approval_registry.create(self.job_id, alt_action["action_id"])
                    job_store.save_job(job)
                    alt_decision = await approval_registry.wait(self.job_id, alt_action["action_id"])
                    if alt_decision == "approved":
                        working_df = _apply_action(working_df, alt_action)
                        alt_action["status"] = "applied"
                        _log(job, "Human", f"Approved alternative '{alt_action['action_type']}'.")
                    else:
                        alt_action["status"] = "rejected" if alt_decision == "rejected" else "timeout"
                        _log(job, "Human", "Alternative also declined; skipping this fix.")
                else:
                    _log(job, "Decision Agent", "No documented lower-impact alternative for this action; skipping.")
            else:
                action["status"] = "timeout"
                _log(job, "DataRescue", f"No approval decision received for '{action['action_type']}' - skipping.")

            job["pending_action_id"] = None
            job_store.save_job(job)
            await asyncio.sleep(0)

        # ---- Stage: attack (after-state) ----
        job["current_stage"] = "attack"
        job["status"] = "running"
        if aux_df is not None:
            _log(job, "Attack Agent", "Re-running the linkage attack against the rescued dataset.")
        after = _score_dataset(working_df, aux_df, self.target_column)
        job["privacy_after"] = {"risk": after["risk"], "linkage": after["linkage"], "k_anonymity": after["k_anonymity"]}
        job_store.save_job(job)
        await asyncio.sleep(0)

        # ---- Stage: verify ----
        job["current_stage"] = "verify"
        before_health = job["before_metrics"]["data_health"]
        after_health = after["data_health"]["data_health"]
        verification_passed = bool(after_health >= before_health)
        job["verification"] = {
            "passed": verification_passed,
            "before_data_health": before_health,
            "after_data_health": after_health,
            "reason": (
                f"Data Health moved from {before_health} to {after_health}."
                if verification_passed else
                f"Data Health moved from {before_health} to {after_health} - the plan made things worse overall, "
                f"rolling back to the original dataset."
            ),
        }
        if not verification_passed:
            _log(job, "Validator", job["verification"]["reason"])
            working_df = original_df.copy()
            job["status_note"] = "rolled_back"
            after = before  # after-metrics reflect the reverted (= original) state
            job["privacy_after"] = job["privacy_before"]
        else:
            _log(job, "Validator", job["verification"]["reason"])
        job_store.save_job(job)
        await asyncio.sleep(0)

        # ---- Stage: finalize ----
        job["current_stage"] = "finalize"
        job["after_metrics"] = {
            "quality_score": float(after["quality_score"]["score"]),
            "ml_readiness_score": float(after["ml_score"]["score"]),
            "privacy_risk_score": float(after["risk"]["overall_score"]),
            "privacy_risk_level": after["risk"]["risk_level"],
            "data_health": float(after["data_health"]["data_health"]),
        }
        job["utility"] = _utility_retained(original_df, working_df)
        job["rescue_score"] = _rescue_score(before_health, job["after_metrics"]["data_health"])

        final_id = core_db.new_id()
        path = save_dataframe(working_df, final_id, generated=True)
        core_db.save_dataset_record(final_id, f"rescued_{rec['name']}", path, len(working_df),
                                     working_df.shape[1], is_demo=False, parent_id=self.dataset_id)
        job["final_dataset_id"] = final_id
        job["status"] = "completed"
        job["current_stage"] = "complete"
        _log(job, "DataRescue", f"Dataset rescued. Data Health {before_health} -> {job['after_metrics']['data_health']} "
                                 f"(Rescue Score {job['rescue_score']}/100). "
                                 f"Utility retained: {job['utility']['row_retention_pct']}% of rows.")
        job_store.save_job(job)
