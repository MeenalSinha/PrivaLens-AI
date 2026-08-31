import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorBanner, Loading, EmptyState } from "../components/UI.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

export default function Report() {
  usePageTitle("Report");
  const navigate = useNavigate();
  const { mainDataset, attackResult } = useDataset();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.getReport(mainDataset.id, "json");
      setReport(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadMarkdown = async () => {
    const md = await api.getReport(mainDataset.id, "markdown");
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `privalens_report_${mainDataset.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `privalens_report_${mainDataset.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!mainDataset || !attackResult) {
    return (
      <div>
        <PageHeader eyebrow="Step 6" title="Privacy report" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title="Analysis + attack required"
            description="Run the profiler and attack simulation before generating a report."
            action={<Button onClick={() => navigate("/attack")}>Go to Attack Simulation</Button>}
          />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 6"
        title="Privacy report"
        description="A downloadable, structured summary — every figure traces back to a computed analysis, none of it is written by hand."
        action={
          <Button onClick={generate} disabled={loading}>
            {loading ? "Generating..." : report ? "Regenerate" : "Generate report"}
          </Button>
        }
      />

      <div className="px-8 py-8">
        {error && <div className="mb-6"><ErrorBanner message={error} /></div>}
        {loading && <Loading label="Assembling structured findings" />}

        {!report && !loading && (
          <EmptyState
            title="No report generated yet"
            description="Generate the technical privacy-risk assessment report for this dataset."
            action={<Button onClick={generate}>Generate report</Button>}
          />
        )}

        {report && (
          <>
            <div className="flex gap-3 mb-6">
              <Button variant="secondary" onClick={downloadMarkdown}>Download Markdown</Button>
              <Button variant="secondary" onClick={downloadJson}>Download JSON</Button>
            </div>

            <Card title="Executive summary" className="mb-6">
              <div className="flex items-center gap-6 flex-wrap">
                <div><span className="text-text-muted text-xs uppercase font-mono">Rows</span><div className="font-mono text-text-primary">{report.executive_summary.rows}</div></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Columns</span><div className="font-mono text-text-primary">{report.executive_summary.columns}</div></div>
                <div>
                  <span className="text-text-muted text-xs uppercase font-mono">Overall risk</span>
                  <div className="mt-1 flex items-center gap-2">
                    <RiskBadge level={report.executive_summary.overall_risk_level} />
                    <span className="font-mono text-text-primary">{report.executive_summary.overall_risk_score}/100</span>
                  </div>
                </div>
              </div>
            </Card>

            <Card title="Findings" className="mb-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-text-muted text-xs uppercase font-mono">Direct identifiers</span><p className="text-text-secondary mt-1">{report.findings.direct_identifiers.join(", ") || "none detected"}</p></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Quasi-identifiers</span><p className="text-text-secondary mt-1">{report.findings.quasi_identifiers.join(", ") || "none detected"}</p></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Sensitive attributes</span><p className="text-text-secondary mt-1">{report.findings.sensitive_attributes.join(", ") || "none detected"}</p></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Min equivalence class</span><p className="text-text-secondary mt-1">{report.findings.min_equivalence_class_size}</p></div>
              </div>
            </Card>

            <Card title="Attack summary" className="mb-6">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                <div><span className="text-text-muted text-xs uppercase font-mono">Candidates tested</span><p className="text-text-primary font-mono mt-1">{report.attack_summary.candidates_tested}</p></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Matches found</span><p className="text-text-primary font-mono mt-1">{report.attack_summary.matches_found}</p></div>
                <div><span className="text-text-muted text-xs uppercase font-mono">Highest confidence</span><p className="text-text-primary font-mono mt-1">{(report.attack_summary.highest_confidence * 100).toFixed(1)}%</p></div>
              </div>
            </Card>

            {report.recommendations?.length > 0 && (
              <Card title="Recommendations" className="mb-6">
                <div className="space-y-2">
                  {report.recommendations.map((r, i) => (
                    <div key={i} className="text-sm">
                      <span className="font-mono text-accent-cyan">{r.column}</span>
                      <span className="text-text-secondary"> &rarr; {r.description}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {report.llm_explanation && (
              <Card title="Explanation" eyebrow="grounded in structured findings above">
                <p className="text-text-secondary text-sm leading-relaxed">{report.llm_explanation}</p>
              </Card>
            )}

            <div className="mt-6 text-text-muted text-xs border-t border-border pt-4">{report.disclaimer}</div>
          </>
        )}
      </div>
    </div>
  );
}
