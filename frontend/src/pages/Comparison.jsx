import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, EmptyState, RiskChangeSummary } from "../components/UI.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import usePageTitle from "../lib/usePageTitle.js";

export default function Comparison() {
  usePageTitle("Before / After");
  const navigate = useNavigate();
  const { mainDataset, comparison } = useDataset();

  if (!mainDataset || !comparison) {
    return (
      <div>
        <PageHeader eyebrow="Step 5" title="Before / After comparison" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title="No re-test results yet"
            description="Run Fix & Re-test from the Mitigation page to generate a before/after comparison."
            action={<Button onClick={() => navigate("/mitigation")}>Go to Mitigation</Button>}
          />
        </div>
      </div>
    );
  }

  const { before, after, risk_score_delta } = comparison;
  const chartData = [
    { metric: "Risk score", Before: before.risk_score, After: after.risk_score },
    { metric: "At-risk records", Before: before.at_risk_records, After: after.at_risk_records },
  ];
  const headline = risk_score_delta > 0 ? "Risk decreased" : risk_score_delta < 0 ? "Risk increased" : "No material change";

  return (
    <div>
      <PageHeader
        eyebrow="Step 5"
        title="Before / After comparison"
        description="The same attack, re-run against the mitigated dataset — proving the risk change instead of assuming it."
        action={<Button onClick={() => navigate("/report")}>Generate Report</Button>}
      />

      <div className="px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Card title="Before" eyebrow="original dataset" className="flex flex-col items-center py-8">
            <RiskGauge score={before.risk_score} level={before.risk_level} />
            <RiskBadge level={before.risk_level} className="mt-3" />
            <div className="mt-4 text-text-secondary text-sm text-center">
              {before.at_risk_records} at-risk records &middot; min class size {before.min_class_size}
            </div>
          </Card>
          <Card title="After" eyebrow="mitigated dataset" className="flex flex-col items-center py-8">
            <RiskGauge score={after.risk_score} level={after.risk_level} />
            <RiskBadge level={after.risk_level} className="mt-3" />
            <div className="mt-4 text-text-secondary text-sm text-center">
              {after.at_risk_records} at-risk records &middot; min class size {after.min_class_size}
            </div>
          </Card>
        </div>

        <Card title={headline} eyebrow="net change, recomputed by re-running the attack" className="mb-8">
          <RiskChangeSummary before={before} after={after} />
          <p className="text-text-secondary text-sm mt-4">
            Overall re-identification risk score moved from {before.risk_score} ({before.risk_level}) to{" "}
            {after.risk_score} ({after.risk_level}).
          </p>
        </Card>

        <Card title="Metric comparison" eyebrow="recomputed from actual data">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#26313D" />
              <XAxis dataKey="metric" stroke="#7E8A9A" fontSize={12} />
              <YAxis stroke="#7E8A9A" fontSize={12} />
              <Tooltip contentStyle={{ background: "#19222C", border: "1px solid #26313D", fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Before" fill="#E24C4C" radius={[4, 4, 0, 0]} />
              <Bar dataKey="After" fill="#3FD6C7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
