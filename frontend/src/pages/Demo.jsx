import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorBanner, Loading, RiskChangeSummary } from "../components/UI.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

const PRESETS = [
  { id: "healthcare", label: "Healthcare", desc: "Patients, diagnoses, admission dates" },
  { id: "education", label: "Education", desc: "Students, institutions, scores" },
  { id: "finance", label: "Finance", desc: "Accounts, income bands, transactions" },
];

const STAGES = [
  "Generating synthetic data",
  "Profiling & detecting identifiers",
  "Generating linkage candidates",
  "Calculating re-identification risk",
  "Applying mitigations",
  "Re-testing against the same attack",
];

// Never claims improvement unless the actual delta shows it - mirrors the
// same honest branching used in Comparison.jsx, fixing a real bug where
// this page previously said "Risk score dropped by X points" even when
// X was zero or negative.
function riskChangeHeadline(comparison) {
  const delta = comparison.risk_score_delta;
  if (delta > 0) return "Risk score decreased";
  if (delta < 0) return "Risk score increased";
  return "Risk score remained unchanged";
}

function riskChangeSentence(comparison) {
  const delta = comparison.risk_score_delta;
  if (delta > 0) return `Risk score decreased by ${Math.abs(delta)} points after mitigation.`;
  if (delta < 0) return `Risk score increased by ${Math.abs(delta)} points after mitigation - the applied fixes did not reduce risk here.`;
  return "Risk score remained unchanged after mitigation.";
}

export default function Demo() {
  usePageTitle("Demo Mode");
  const navigate = useNavigate();
  const { loadFromDemo } = useDataset();
  const [preset, setPreset] = useState("healthcare");
  const [loading, setLoading] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const launchDemo = async () => {
    setError(null);
    setResult(null);
    setLoading(true);
    setStageIdx(0);

    const interval = setInterval(() => {
      setStageIdx((i) => (i < STAGES.length - 1 ? i + 1 : i));
    }, 500);

    try {
      const res = await api.runDemo(preset, 400);
      setResult(res);
      loadFromDemo(res);
    } catch (e) {
      setError(e.message);
    } finally {
      clearInterval(interval);
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="One-click showcase"
        title="Demo mode"
        description="Generates a synthetic dataset with intentional vulnerabilities, attacks it, fixes it, and re-tests it — end to end, in under 90 seconds."
      />

      <div className="px-8 py-8">
        {!result && (
          <Card title="Choose a scenario" className="mb-6 max-w-2xl">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPreset(p.id)}
                  className={`text-left border rounded-md p-4 transition-colors ${
                    preset === p.id ? "border-accent-cyan bg-accent-cyan/5" : "border-border hover:border-border-light"
                  }`}
                >
                  <div className="font-display font-semibold text-text-primary text-sm">{p.label}</div>
                  <div className="text-text-muted text-xs mt-1">{p.desc}</div>
                </button>
              ))}
            </div>
            <Button onClick={launchDemo} disabled={loading}>
              {loading ? "Running demo..." : "Launch Demo"}
            </Button>
          </Card>
        )}

        {error && <div className="mb-6"><ErrorBanner message={error} /></div>}

        {loading && (
          <Card className="max-w-2xl">
            <Loading label={STAGES[stageIdx]} />
            <div className="mt-4 space-y-1.5">
              {STAGES.map((s, i) => (
                <div key={s} className={`text-xs font-mono flex items-center gap-2 ${i <= stageIdx ? "text-accent-cyan" : "text-text-muted"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${i <= stageIdx ? "bg-accent-cyan" : "bg-border"}`} />
                  {s}
                </div>
              ))}
            </div>
          </Card>
        )}

        {result && !loading && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
              <Card title="Before mitigation" eyebrow="attack succeeded" className="flex flex-col items-center py-8">
                <RiskGauge score={result.before.risk.overall_score} level={result.before.risk.risk_level} />
                <RiskBadge level={result.before.risk.risk_level} className="mt-3" />
                <p className="text-text-secondary text-sm text-center mt-3">
                  {result.before.linkage.matches_found} candidate matches found against the auxiliary dataset.
                </p>
              </Card>
              <Card title="After mitigation" eyebrow="risk re-tested" className="flex flex-col items-center py-8">
                <RiskGauge score={result.after.risk.overall_score} level={result.after.risk.risk_level} />
                <RiskBadge level={result.after.risk.risk_level} className="mt-3" />
                <p className="text-text-secondary text-sm text-center mt-3">{riskChangeSentence(result.comparison)}</p>
              </Card>
            </div>

            <Card
              title={riskChangeHeadline(result.comparison)}
              eyebrow="net change, recomputed by re-running the attack"
              className="mb-8"
            >
              <RiskChangeSummary before={result.comparison.before} after={result.comparison.after} />
            </Card>

            <Card title="Mitigations applied" className="mb-8">
              <div className="space-y-2">
                {result.mitigations.map((m, i) => (
                  <div key={i} className="text-sm text-text-secondary">
                    <span className="font-mono text-accent-cyan">{m.column}</span> &rarr; {m.description}
                  </div>
                ))}
              </div>
            </Card>

            <div className="flex gap-3">
              <Button onClick={() => navigate("/dashboard")}>Explore Risk Dashboard</Button>
              <Button variant="secondary" onClick={() => navigate("/comparison")}>View Full Comparison</Button>
              <Button variant="secondary" onClick={() => navigate("/report")}>Generate Report</Button>
              <Button variant="ghost" onClick={() => setResult(null)}>Run another demo</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
