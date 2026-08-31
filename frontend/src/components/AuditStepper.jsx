import { useNavigate, useLocation } from "react-router-dom";
import { useDataset } from "../context/DatasetContext.jsx";

/**
 * Maps the 9-stage Attack -> Detect -> Explain -> Fix -> Re-test pipeline
 * to real completion state pulled from DatasetContext - never marks a
 * step complete just because the user visited its page. Replaces the
 * disconnected "Step N" page-header text + flat sidebar list, which gave
 * no honest sense of where the user actually was in the pipeline.
 */
const STEPS = [
  { key: "upload", label: "Upload", path: "/upload", requires: null },
  { key: "profile", label: "Profile", path: "/profiler", requires: "upload" },
  { key: "detect", label: "Detect", path: "/profiler", requires: "upload" },
  { key: "attack", label: "Attack", path: "/attack", requires: "profile" },
  { key: "explain", label: "Explain", path: "/attack", requires: "attack" },
  { key: "mitigate", label: "Mitigate", path: "/mitigation", requires: "attack" },
  { key: "retest", label: "Re-test", path: "/mitigation", requires: "mitigate" },
  { key: "compare", label: "Compare", path: "/comparison", requires: "retest" },
  { key: "report", label: "Report", path: "/report", requires: "attack" },
];

export function useStepCompletion() {
  const { mainDataset, auxDataset, analysis, attackResult, mitigationResult, comparison } = useDataset();

  return {
    upload: !!mainDataset,
    profile: !!analysis,
    detect: !!analysis?.classification,
    attack: !!attackResult,
    // "explain" is satisfied once an attack has actually run - zero
    // matches is a legitimate, valid outcome (an already-safe dataset),
    // not an incomplete state, so this must not require matches.length.
    explain: !!attackResult,
    mitigate: !!mitigationResult,
    retest: !!comparison,
    compare: !!comparison,
    report: false, // report generation isn't tracked in shared state; never fake this as done
    hasAux: !!auxDataset,
  };
}

export default function AuditStepper({ compact = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const completion = useStepCompletion();

  const doneCount = STEPS.filter((s) => completion[s.key]).length;
  const currentIdx = STEPS.findIndex((s) => !completion[s.key]);
  const activeIdx = currentIdx === -1 ? STEPS.length - 1 : currentIdx;

  return (
    <div
      className={`flex items-center gap-0.5 overflow-x-auto ${compact ? "px-4 py-2" : "px-8 py-3"} border-b border-border bg-bg-surface/60`}
      role="navigation"
      aria-label="Privacy audit pipeline progress"
    >
      <span className="text-text-muted text-[10px] font-mono uppercase tracking-widest mr-3 shrink-0">
        Audit &middot; {doneCount}/{STEPS.length}
      </span>
      {STEPS.map((s, i) => {
        const isDone = completion[s.key];
        const isActive = i === activeIdx && !isDone;
        const isReachable = s.requires === null || completion[s.requires];
        const isCurrentPage = location.pathname === s.path;

        return (
          <button
            key={s.key}
            onClick={() => isReachable && navigate(s.path)}
            disabled={!isReachable}
            aria-current={isCurrentPage ? "step" : undefined}
            title={
              isDone ? `${s.label} — complete` : isReachable ? `${s.label} — available` : `${s.label} — locked, complete earlier steps first`
            }
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono whitespace-nowrap transition-colors shrink-0
              ${isCurrentPage ? "bg-accent-cyan/10 border border-accent-cyan/40 text-accent-cyan" : "border border-transparent"}
              ${isDone && !isCurrentPage ? "text-risk-low hover:bg-bg-elevated" : ""}
              ${isActive && !isCurrentPage ? "text-text-primary hover:bg-bg-elevated" : ""}
              ${!isReachable ? "text-text-disabled cursor-not-allowed" : ""}
              ${!isDone && !isActive && isReachable && !isCurrentPage ? "text-text-muted hover:bg-bg-elevated hover:text-text-secondary" : ""}
            `}
          >
            <span aria-hidden="true">{isDone ? "\u2713" : isActive ? "\u25CF" : isReachable ? "\u25CB" : "\u2013"}</span>
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
