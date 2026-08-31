import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorCard, Loading } from "../components/UI.jsx";
import usePageTitle from "../lib/usePageTitle.js";
import { api } from "../api/client.js";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

const STATUS_STYLE = {
  queued: "text-text-muted border-border bg-bg-elevated",
  running: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
  awaiting_approval: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  completed: "text-risk-low border-risk-low/40 bg-risk-low/10",
  failed: "text-risk-critical border-risk-critical/40 bg-risk-critical/10",
};

function StatusBadge({ status }) {
  return (
    <span className={`px-2.5 py-1 rounded text-xs font-mono border ${STATUS_STYLE[status] || STATUS_STYLE.queued}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

const STAGES = ["inspect", "detect", "plan", "execute", "attack", "verify", "finalize", "complete"];

function StageTracker({ currentStage }) {
  const idx = STAGES.indexOf(currentStage);
  return (
    <div className="flex items-center gap-1 overflow-x-auto">
      {STAGES.map((s, i) => {
        const done = idx > i || currentStage === "complete";
        const active = s === currentStage;
        return (
          <div key={s} className="flex items-center gap-1 shrink-0">
            <span
              className={`px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wide border
                ${active ? "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10" : ""}
                ${done && !active ? "text-risk-low border-risk-low/30" : ""}
                ${!done && !active ? "text-text-muted border-border" : ""}`}
            >
              {done && !active ? "\u2713 " : active ? "\u25CF " : ""}{s}
            </span>
            {i < STAGES.length - 1 && <span className="text-text-disabled text-xs">&rarr;</span>}
          </div>
        );
      })}
    </div>
  );
}

// "Higher is better" metric - Quality, Privacy score, ML Readiness, Data
// Health all share this direction (unlike the core PrivaLens risk score,
// which is "lower is better" - see quality_engine.py's inversion note).
function HealthMetric({ label, before, after }) {
  const hasAfter = after !== undefined && after !== null;
  const delta = hasAfter ? Math.round((after - before) * 100) / 100 : null;
  const direction = delta === null ? null : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const colors = { up: "text-risk-low", down: "text-risk-critical", flat: "text-text-secondary" };
  const arrows = { up: "\u2191", down: "\u2193", flat: "\u2192" };

  return (
    <div className="border border-border rounded-md p-4">
      <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-2">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold text-text-primary">
          {hasAfter ? after.toFixed(1) : before.toFixed(1)}
        </span>
        {hasAfter && direction && (
          <span className={`font-mono text-sm ${colors[direction]}`}>
            {arrows[direction]} {Math.abs(delta).toFixed(1)}
          </span>
        )}
      </div>
      {hasAfter && <div className="text-text-muted text-xs mt-1 font-mono">was {before.toFixed(1)}</div>}
    </div>
  );
}

export default function RescueJobDetail() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  usePageTitle(`Rescue Job ${jobId}`);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const timelineRef = useRef(null);

  const poll = useCallback(async () => {
    try {
      const res = await api.getRescueJob(jobId);
      setJob(res);
      return res;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    let cancelled = false;
    let intervalId;

    const tick = async () => {
      const res = await poll();
      if (cancelled) return;
      if (res && TERMINAL_STATUSES.has(res.status) && intervalId) {
        clearInterval(intervalId);
      }
    };

    tick();
    intervalId = setInterval(tick, 900);
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [poll]);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [job?.audit_events?.length]);

  const decide = async (decision) => {
    if (!job?.pending_action_id) return;
    setActionBusy(true);
    setError(null);
    try {
      if (decision === "approved") {
        await api.approveRescueAction(jobId, job.pending_action_id);
      } else {
        await api.rejectRescueAction(jobId, job.pending_action_id);
      }
      await poll();
    } catch (e) {
      setError(e.message);
    } finally {
      setActionBusy(false);
    }
  };

  if (!job) {
    return (
      <div>
        <PageHeader eyebrow="DataRescue" title="Rescue job" />
        <div className="px-8 py-8">
          {error ? <ErrorCard what="Could not load this rescue job." why={error} /> : <Loading label="Loading job state" />}
        </div>
      </div>
    );
  }

  const pendingAction = job.pending_action_id
    ? job.proposed_actions.find((a) => a.action_id === job.pending_action_id)
    : null;

  const before = job.before_metrics;
  const after = job.after_metrics;

  return (
    <div>
      <PageHeader
        eyebrow="DataRescue"
        title={`Rescue job ${jobId}`}
        description={job.target_column ? `Target column: ${job.target_column}` : "No target column specified — target-specific ML checks skipped."}
        action={<StatusBadge status={job.status} />}
      />

      <div className="px-8 py-8">
        {error && <div className="mb-6"><ErrorCard what="An action failed." why={error} /></div>}

        <Card title="Agent pipeline" eyebrow="reflects real backend stage, not a fixed animation" className="mb-6">
          <StageTracker currentStage={job.current_stage} />
        </Card>

        {pendingAction && (
          <Card title="Action requires approval" eyebrow="human-in-the-loop" className="mb-6 border-risk-moderate/40">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-text-primary text-sm">
                {pendingAction.action_type.replace(/_/g, " ")}
                {pendingAction.column ? ` on ${pendingAction.column}` : ""}
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded border border-risk-moderate/40 text-risk-moderate bg-risk-moderate/10">
                REVIEW
              </span>
            </div>
            <p className="text-text-secondary text-sm mb-1">{pendingAction.description}</p>
            <p className="text-text-muted text-xs mb-4">{pendingAction.reason}</p>
            <p className="text-text-secondary text-xs mb-4">
              <span className="text-text-muted uppercase tracking-wide text-[10px]">Expected benefit: </span>
              {pendingAction.expected_benefit}
            </p>
            <div className="flex gap-3">
              <Button onClick={() => decide("approved")} disabled={actionBusy}>
                {actionBusy ? "Working..." : "Approve"}
              </Button>
              <Button variant="secondary" onClick={() => decide("rejected")} disabled={actionBusy}>
                Reject
              </Button>
            </div>
          </Card>
        )}

        {before && (
          <Card title="Data Health" eyebrow="quality + privacy + ML readiness, unified" className="mb-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <HealthMetric label="Data Health" before={before.data_health} after={after?.data_health} />
              <HealthMetric label="Quality" before={before.quality_score} after={after?.quality_score} />
              <HealthMetric label="Privacy score" before={100 - before.privacy_risk_score} after={after ? 100 - after.privacy_risk_score : undefined} />
              <HealthMetric label="ML Readiness" before={before.ml_readiness_score} after={after?.ml_readiness_score} />
            </div>
            <div className="mt-4 text-text-secondary text-xs font-mono">
              Privacy risk: {before.privacy_risk_level}
              {after && after.privacy_risk_level !== before.privacy_risk_level ? ` \u2192 ${after.privacy_risk_level}` : after ? " (unchanged)" : ""}
            </div>
          </Card>
        )}

        {job.verification && (
          <Card
            title={job.verification.passed ? "Verification passed" : "Verification failed — rolled back"}
            eyebrow="the agent checks its own work before finishing"
            className="mb-6"
          >
            <p className="text-text-secondary text-sm">{job.verification.reason}</p>
          </Card>
        )}

        {job.status === "completed" && (
          <Card title="Rescue complete" eyebrow="final results" className="mb-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">Rescue Score</div>
                <div className="font-mono text-2xl font-semibold text-accent-cyan">{job.rescue_score}/100</div>
              </div>
              <div>
                <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">Rows retained</div>
                <div className="font-mono text-2xl font-semibold text-text-primary">{job.utility?.row_retention_pct}%</div>
              </div>
              <div>
                <div className="text-text-muted text-[10px] font-mono uppercase tracking-widest mb-1">Avg. cardinality retained</div>
                <div className="font-mono text-2xl font-semibold text-text-primary">{job.utility?.avg_cardinality_retention_pct}%</div>
              </div>
            </div>
            <p className="text-text-secondary text-xs mb-4">
              Rescue Score reflects how much of the possible Data Health improvement was actually
              captured — 100 only if Data Health reached a perfect 100, 0 if it didn't improve at all.
              It is never inflated above what the before/after numbers actually show.
            </p>
            {job.final_dataset_id && (
              <p className="text-text-secondary text-xs font-mono">
                Rescued dataset saved as a new version (id: {job.final_dataset_id}) — the original
                dataset was never modified.
              </p>
            )}
            <div className="flex gap-3 mt-4">
              {job.final_dataset_id && (
                <a href={`${api.base}/api/datasets/${job.final_dataset_id}/download`}>
                  <Button variant="secondary">Download rescued dataset</Button>
                </a>
              )}
              <a href={`${api.base}/api/rescue/${jobId}/report?format=markdown`}>
                <Button variant="secondary">Download rescue report</Button>
              </a>
            </div>
          </Card>
        )}

        <Card title="Agent activity" eyebrow={`${job.audit_events.length} events, real-time from the backend`}>
          <div ref={timelineRef} className="max-h-96 overflow-y-auto space-y-2 pr-1">
            {job.audit_events.map((e, i) => (
              <div key={i} className="flex gap-3 text-xs border-b border-border/40 pb-2 last:border-0">
                <span className="text-text-muted font-mono shrink-0 w-20">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className="text-accent-cyan font-mono shrink-0 w-32 truncate">{e.agent}</span>
                <span className="text-text-secondary">{e.message}</span>
              </div>
            ))}
          </div>
        </Card>

        <div className="mt-8">
          <Button variant="secondary" onClick={() => navigate("/rescue")}>Back to job list</Button>
        </div>
      </div>
    </div>
  );
}
