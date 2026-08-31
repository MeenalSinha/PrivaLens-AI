import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorCard, Loading, EmptyState } from "../components/UI.jsx";
import usePageTitle from "../lib/usePageTitle.js";
import { api } from "../api/client.js";

const STATUS_STYLE = {
  queued: "text-text-muted border-border bg-bg-elevated",
  running: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
  awaiting_approval: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  completed: "text-risk-low border-risk-low/40 bg-risk-low/10",
  failed: "text-risk-critical border-risk-critical/40 bg-risk-critical/10",
};

function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-mono border ${STATUS_STYLE[status] || STATUS_STYLE.queued}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function RescueJobs() {
  usePageTitle("DataRescue");
  const navigate = useNavigate();
  const [jobs, setJobs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const res = await api.listRescueJobs();
      setJobs(res.jobs);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const launchJudgeMode = async () => {
    setError(null);
    setLaunching(true);
    try {
      const prep = await api.prepareJudgeMode(300);
      const start = await api.startRescue(prep.dataset_id, prep.aux_dataset_id);
      navigate(`/rescue/${start.job_id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="DataRescue"
        title="Autonomous rescue jobs"
        description="Upload a dataset and the agent will inspect, detect, plan, act, attack, and verify its own work — pausing for your approval on anything privacy-sensitive."
        action={
          <Button onClick={launchJudgeMode} disabled={launching}>
            {launching ? "Preparing..." : "Judge Mode: Launch Demo Rescue"}
          </Button>
        }
      />

      <div className="px-8 py-8">
        {error && (
          <div className="mb-6">
            <ErrorCard what="Could not start a rescue job." why={error} next="Try again, or check that the backend is reachable." />
          </div>
        )}
        {launching && (
          <div className="mb-6">
            <Loading label="Generating a messy demo dataset with real, injected quality and privacy issues" />
          </div>
        )}

        <Card title="What Judge Mode does" eyebrow="deterministic showcase dataset" className="mb-8">
          <p className="text-text-secondary text-sm leading-relaxed">
            Generates a synthetic healthcare dataset with genuinely injected problems — duplicate rows,
            missing values, inconsistent casing, stray whitespace, malformed date formats, plus the
            existing quasi-identifier privacy vulnerabilities — and immediately starts a rescue job
            against it. Every issue the agent reports is actually present in the data; nothing is
            pre-labeled as already found.
          </p>
        </Card>

        {loading && <Loading label="Loading rescue job history" />}

        {jobs && jobs.length === 0 && !loading && (
          <EmptyState
            title="No rescue jobs yet"
            description="Launch Judge Mode above, or start a rescue from any uploaded dataset's page."
            action={<Button onClick={launchJudgeMode}>Launch Judge Mode</Button>}
          />
        )}

        {jobs && jobs.length > 0 && (
          <Card title="Job history" eyebrow={`${jobs.length} job${jobs.length !== 1 ? "s" : ""}`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted text-xs uppercase tracking-wide border-b border-border">
                    <th className="py-2 pr-4 font-mono font-normal">Job ID</th>
                    <th className="py-2 pr-4 font-mono font-normal">Status</th>
                    <th className="py-2 pr-4 font-mono font-normal">Started</th>
                    <th className="py-2 pr-4 font-mono font-normal">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr
                      key={j.job_id}
                      className="border-b border-border/60 hover:bg-bg-elevated cursor-pointer"
                      onClick={() => navigate(`/rescue/${j.job_id}`)}
                    >
                      <td className="py-2.5 pr-4 font-mono text-text-primary">{j.job_id}</td>
                      <td className="py-2.5 pr-4"><StatusBadge status={j.status} /></td>
                      <td className="py-2.5 pr-4 text-text-secondary font-mono text-xs">
                        {new Date(j.created_at * 1000).toLocaleString()}
                      </td>
                      <td className="py-2.5 pr-4 text-text-secondary font-mono text-xs">
                        {new Date(j.updated_at * 1000).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
