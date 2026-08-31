import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, Stat, EmptyState } from "../components/UI.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import usePageTitle from "../lib/usePageTitle.js";

// Color the risk-components chart by what the value MEANS (severity),
// not by its position in the array - a bar showing 92 must always read
// as high-risk red regardless of which component it happens to be.
function colorForComponentValue(value) {
  if (value >= 75) return "#E24C4C"; // risk-critical
  if (value >= 50) return "#E8763C"; // risk-high
  if (value >= 25) return "#E8B339"; // risk-moderate
  return "#3FD6C7"; // risk-low
}

const TITLE_CASE = {
  linkage_confidence: "Linkage Confidence",
  uniqueness: "Uniqueness",
  equivalence_class_risk: "Equivalence Class Risk",
  sensitive_attribute_exposure: "Sensitive Attribute Exposure",
};

export default function Dashboard() {
  usePageTitle("Risk Dashboard");
  const navigate = useNavigate();
  const { mainDataset, analysis, attackResult } = useDataset();

  if (!mainDataset || !analysis) {
    return (
      <div>
        <PageHeader eyebrow="Risk Overview" title="Privacy risk dashboard" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title="No analysis available"
            description="Upload a dataset and run the profiler to see the risk dashboard."
            action={<Button onClick={() => navigate("/upload")}>Go to Upload</Button>}
          />
        </div>
      </div>
    );
  }

  const risk = attackResult?.risk;
  const distribution = analysis.uniqueness.class_size_distribution || {};
  const distributionData = Object.entries(distribution).map(([bucket, count]) => ({ bucket, count }));

  const componentsData = risk
    ? Object.entries(risk.components).map(([key, value]) => ({
        name: TITLE_CASE[key] || key.replace(/_/g, " "),
        value,
      }))
    : [];

  return (
    <div>
      <PageHeader
        eyebrow="Risk Overview"
        title="Privacy risk dashboard"
        description={mainDataset.name}
        action={<Button onClick={() => navigate("/report")}>Generate Report</Button>}
      />

      <div className="px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="lg:col-span-1 flex flex-col items-center justify-center py-8" title="Overall Dataset Risk">
            {risk ? (
              <>
                <RiskGauge score={risk.overall_score} level={risk.risk_level} />
                <div className="mt-4"><RiskBadge level={risk.risk_level} /></div>
              </>
            ) : (
              <p className="text-text-secondary text-sm text-center">
                Run the attack simulation to compute a full risk score. Showing structural
                metrics only for now.
              </p>
            )}
          </Card>

          <div className="lg:col-span-2 grid grid-cols-2 gap-4 content-start">
            <Card><Stat label="At-risk records" value={risk ? risk.at_risk_records : analysis.uniqueness.unique_records} valueClassName="text-risk-high" /></Card>
            <Card><Stat label="Min k-anonymity class" value={analysis.k_anonymity.min_class_size ?? "—"} /></Card>
            <Card><Stat label="Linkage confidence" value={risk ? `${(attackResult.linkage.highest_confidence * 100).toFixed(0)}%` : "—"} valueClassName="text-risk-critical" /></Card>
            <Card><Stat label="Unique records" value={`${analysis.uniqueness.unique_pct}%`} /></Card>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <Card title="Equivalence class size distribution" eyebrow="uniqueness engine">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#26313D" />
                <XAxis dataKey="bucket" stroke="#7E8A9A" fontSize={12} />
                <YAxis stroke="#7E8A9A" fontSize={12} />
                <Tooltip contentStyle={{ background: "#19222C", border: "1px solid #26313D", fontSize: 12 }} />
                <Bar dataKey="count" fill="#3FD6C7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Risk score components" eyebrow="colored by severity, not position — higher = redder">
            {componentsData.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={componentsData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#26313D" />
                  <XAxis type="number" domain={[0, 100]} stroke="#7E8A9A" fontSize={12} />
                  <YAxis type="category" dataKey="name" stroke="#7E8A9A" fontSize={11} width={150} />
                  <Tooltip contentStyle={{ background: "#19222C", border: "1px solid #26313D", fontSize: 12 }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {componentsData.map((entry, i) => (
                      <Cell key={i} fill={colorForComponentValue(entry.value)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-text-secondary text-sm">Run the attack simulation to populate this breakdown.</p>
            )}
          </Card>
        </div>

        <Card title="k-anonymity checkpoints" eyebrow="configurable k thresholds">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {analysis.k_anonymity.checks.map((c) => (
              <div key={c.k} className="border border-border rounded-md p-4">
                <div className="font-mono text-text-muted text-xs uppercase mb-1">k = {c.k}</div>
                <div className={`font-mono text-xl font-semibold ${c.satisfies_k_anonymity ? "text-risk-low" : "text-risk-high"}`}>
                  {c.at_risk_pct}%
                </div>
                <div className="text-text-secondary text-xs mt-1">{c.at_risk_records} at-risk records</div>
              </div>
            ))}
          </div>
        </Card>

        <div className="mt-8 flex gap-3">
          <Button onClick={() => navigate("/mitigation")}>Go to Fix &amp; Re-test</Button>
        </div>
      </div>
    </div>
  );
}
