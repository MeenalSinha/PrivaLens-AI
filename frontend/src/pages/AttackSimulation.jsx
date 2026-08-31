import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorCard, Loading, Stat, EmptyState } from "../components/UI.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import Expandable from "../components/Expandable.jsx";
import RiskHeatmap from "../components/RiskHeatmap.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

export default function AttackSimulation() {
  usePageTitle("Attack Simulation");
  const navigate = useNavigate();
  const { mainDataset, auxDataset, attackResult, setAttackResult } = useDataset();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [explainOpen, setExplainOpen] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [explainLoading, setExplainLoading] = useState(false);
  // Guards against a real bug: if the user clicks match A then quickly
  // clicks match B, A's slower response must never overwrite B's UI.
  // Each request is stamped with the index it was requested for; only
  // the response matching the CURRENT explainOpen index is applied.
  const requestIdRef = useRef(0);

  const runAttack = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.attackDataset(mainDataset.id, auxDataset.id);
      setAttackResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleExplain = async (idx) => {
    if (explainOpen === idx) {
      setExplainOpen(null);
      setExplanation(null);
      return;
    }
    // Clear immediately - never show the previous match's explanation
    // under the newly selected row, even briefly.
    setExplainOpen(idx);
    setExplanation(null);
    setExplainLoading(true);
    const myRequestId = ++requestIdRef.current;
    try {
      const res = await api.explainMatch(mainDataset.id, idx);
      // Ignore stale responses: only apply this result if no newer
      // request has been issued since.
      if (myRequestId === requestIdRef.current) {
        setExplanation(res);
      }
    } catch (e) {
      if (myRequestId === requestIdRef.current) {
        setExplanation(null);
      }
    } finally {
      if (myRequestId === requestIdRef.current) {
        setExplainLoading(false);
      }
    }
  };

  const closeExplain = () => {
    setExplainOpen(null);
    setExplanation(null);
  };

  if (!mainDataset || !auxDataset) {
    const missingMain = !mainDataset;
    const missingAux = !auxDataset && !!mainDataset;
    return (
      <div>
        <PageHeader eyebrow="Step 3" title="Attack simulation" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title={missingMain ? "Target dataset required" : "Auxiliary dataset required"}
            description={
              missingMain
                ? "Attack simulation needs a target dataset (the one you believe is anonymized) plus an auxiliary dataset an attacker might already hold. Neither is loaded yet."
                : "A target dataset is loaded, but the linkage attack also needs an auxiliary dataset with overlapping quasi-identifiers to cross-reference against."
            }
            action={
              <Button onClick={() => navigate("/upload")}>
                {missingMain ? "Upload datasets" : "Upload auxiliary dataset"}
              </Button>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 3"
        title="Attack simulation"
        description={`Simulating an attacker cross-referencing "${mainDataset.name}" with "${auxDataset.name}" using shared quasi-identifiers.`}
        action={
          <Button onClick={runAttack} disabled={loading}>
            {loading ? "Running attack..." : attackResult ? "Re-run attack" : "Run attack"}
          </Button>
        }
      />

      <div className="px-8 py-8">
        {error && (
          <div className="mb-6">
            <ErrorCard
              what="Attack simulation could not complete."
              why={error}
              next="Check that both datasets uploaded correctly and share at least one comparable column, then try again."
              action={<Button variant="secondary" onClick={runAttack}>Retry attack</Button>}
            />
          </div>
        )}
        {loading && <Loading label="Generating linkage candidates" />}

        {!attackResult && !loading && (
          <EmptyState
            title="No attack run yet"
            description="Run the linkage attack to see how many records could be re-identified using the auxiliary dataset."
            action={<Button onClick={runAttack}>Run attack</Button>}
          />
        )}

        {attackResult && (
          <>
            {attackResult.linkage.was_truncated && (
              <div className="mb-6 border border-risk-moderate/40 bg-risk-moderate/10 text-risk-moderate text-sm rounded-md px-4 py-3">
                Only the first {attackResult.linkage.target_rows_tested} of {attackResult.linkage.target_rows_total} target rows
                and {attackResult.linkage.auxiliary_rows_tested} of {attackResult.linkage.auxiliary_rows_total} auxiliary rows were
                tested against each other (a bounded comparison for interactive response times — see README &gt; Limitations).
                Results below reflect that subset, not the full dataset.
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 mb-8">
              <Card><Stat label="Shared columns" value={attackResult.linkage.shared_columns.length} /></Card>
              <Card><Stat label="Pairs tested" value={attackResult.linkage.candidates_tested.toLocaleString()} /></Card>
              <Card><Stat label="Matches found" value={attackResult.linkage.matches_found} valueClassName="text-risk-high" /></Card>
              <Card><Stat label="Highest confidence" value={`${(attackResult.linkage.highest_confidence * 100).toFixed(0)}%`} valueClassName="text-risk-critical" /></Card>
            </div>

            {attackResult.linkage.matches.length > 0 && (
              <Card title="Attribute contribution heatmap" eyebrow="top matches × shared columns, real per-attribute scores" className="mb-6">
                <RiskHeatmap
                  rowLabel="Column"
                  columnLabel="Match"
                  rows={attackResult.linkage.shared_columns}
                  columns={attackResult.linkage.matches.slice(0, 10).map((_, i) => `#${i + 1}`)}
                  cells={attackResult.linkage.shared_columns.map((col) =>
                    attackResult.linkage.matches.slice(0, 10).map((m) => {
                      const attr = m.matching_attributes[col];
                      if (!attr) return null;
                      return {
                        display: attr.score.toFixed(2),
                        intensity: attr.score,
                        tooltip: `${col} in match #: ${attr.kind} similarity ${attr.score.toFixed(2)}`,
                      };
                    })
                  )}
                  legendLabels={["No similarity (0.0)", "Exact match (1.0)"]}
                />
              </Card>
            )}

            <Card
              title="Top candidate matches"
              eyebrow={`showing up to ${Math.min(attackResult.linkage.matches.length, 25)} of ${attackResult.linkage.matches_found}`}
            >
              {attackResult.linkage.matches.length === 0 ? (
                <p className="text-text-secondary text-sm">No candidate pairs crossed the match threshold. This is a good sign.</p>
              ) : (
                <div className="space-y-2">
                  {attackResult.linkage.matches.slice(0, 25).map((m, idx) => (
                    <div key={idx} className="border border-border rounded-md">
                      <Expandable
                        expanded={explainOpen === idx}
                        onToggle={() => toggleExplain(idx)}
                        onClose={closeExplain}
                        ariaLabel={`Match between target row ${m.record_a_index} and auxiliary row ${m.record_b_index}, ${(m.match_probability * 100).toFixed(1)} percent confidence. Press Enter to see why.`}
                        className="flex items-center justify-between px-4 py-3 hover:bg-bg-elevated"
                      >
                        <div className="font-mono text-sm text-text-secondary flex items-center gap-2">
                          <span aria-hidden="true" className="text-text-muted">{explainOpen === idx ? "\u25BE" : "\u25B8"}</span>
                          Target row #{m.record_a_index} &harr; Auxiliary row #{m.record_b_index}
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-sm text-text-primary">{(m.match_probability * 100).toFixed(1)}%</span>
                          <RiskBadge level={m.risk_level} />
                        </div>
                      </Expandable>
                      {explainOpen === idx && (
                        <div className="px-4 pb-3 pt-0 border-t border-border/60 bg-bg-elevated/40">
                          {explainLoading ? (
                            <div className="pt-3"><Loading label="Evaluating contributing factors" /></div>
                          ) : explanation ? (
                            <>
                              <div className="text-text-muted text-[10px] uppercase tracking-wide mt-3 mb-1.5">
                                Why this is {explanation.risk_level}
                              </div>
                              <ul className="text-text-secondary text-xs space-y-1 font-mono">
                                {explanation.contributing_factors.map((f, i) => <li key={i}>&bull; {f}</li>)}
                              </ul>
                            </>
                          ) : (
                            <p className="text-text-secondary text-xs pt-3">Explanation unavailable for this match.</p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <div className="mt-8 flex gap-3">
              <Button onClick={() => navigate("/dashboard")}>View Risk Dashboard</Button>
              <Button variant="secondary" onClick={() => navigate("/vulnerabilities")}>Explore Vulnerable Clusters</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
