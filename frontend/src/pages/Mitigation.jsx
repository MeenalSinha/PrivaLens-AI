import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorCard, Loading, EmptyState, RiskChangeSummary } from "../components/UI.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

export default function Mitigation() {
  usePageTitle("Fix & Re-test");
  const navigate = useNavigate();
  const {
    mainDataset, auxDataset, attackResult,
    mitigationResult, setMitigationResult,
    setMitigatedDataset, comparison, setComparison,
  } = useDataset();
  const [loadingMitigate, setLoadingMitigate] = useState(false);
  const [loadingRetest, setLoadingRetest] = useState(false);
  const [error, setError] = useState(null);

  const runMitigate = async () => {
    setError(null);
    setLoadingMitigate(true);
    try {
      const res = await api.mitigateDataset(mainDataset.id);
      setMitigationResult(res);
      setMitigatedDataset({ id: res.mitigated_dataset_id, name: `${mainDataset.name} (mitigated)` });
      setComparison(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMitigate(false);
    }
  };

  const runFixAndRetest = async () => {
    if (!auxDataset) {
      setError("An auxiliary dataset is required to re-run the attack against the mitigated data.");
      return;
    }
    setError(null);
    setLoadingRetest(true);
    try {
      const res = await api.retestDataset(mainDataset.id, mitigationResult.mitigated_dataset_id, auxDataset.id);
      setComparison(res.comparison);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingRetest(false);
    }
  };

  if (!mainDataset || !attackResult) {
    return (
      <div>
        <PageHeader eyebrow="Step 4" title="Mitigation & Fix + Re-test" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title="Run the attack first"
            description="PrivaLens recommends mitigations based on the risk findings — run the attack simulation before generating fixes."
            action={<Button onClick={() => navigate("/attack")}>Go to Attack Simulation</Button>}
          />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 4"
        title="Mitigation & Fix + Re-test"
        description="Generalization, bucketing and suppression recommendations, each explained and ranked by risk-reduction vs utility loss."
        action={
          <Button onClick={runMitigate} disabled={loadingMitigate}>
            {loadingMitigate ? "Generating fixes..." : "Recommend & Apply Fixes"}
          </Button>
        }
      />

      <div className="px-8 py-8">
        {error && (
          <div className="mb-6">
            <ErrorCard
              what="Mitigation could not complete."
              why={error}
              next="Confirm an auxiliary dataset is loaded, then try again."
            />
          </div>
        )}
        {loadingMitigate && <Loading label="Computing mitigations and optimizing privacy/utility trade-offs" />}

        {!mitigationResult && !loadingMitigate && (
          <EmptyState
            title="No mitigations generated yet"
            description="Click 'Recommend & Apply Fixes' to generate and apply column-level mitigations."
            action={<Button onClick={runMitigate}>Recommend & Apply Fixes</Button>}
          />
        )}

        {mitigationResult && (
          <>
            {mitigationResult.mitigations_applied.length === 0 ? (
              <Card title="No mitigations recommended" eyebrow="dataset already well-generalized" className="mb-6">
                <p className="text-text-secondary text-sm">
                  Every quasi-identifier column is already at or below a low-cardinality threshold, so no further
                  generalization or suppression was recommended — applying one would only destroy data for negligible
                  privacy gain. If risk is still high, it's likely coming from linkage confidence or sensitive-attribute
                  exposure rather than these columns; review the Risk Dashboard for the breakdown.
                </p>
              </Card>
            ) : (
              <Card title="Recommended mitigations" eyebrow={`${mitigationResult.mitigations_applied.length} transformations applied`} className="mb-6">
                <div className="space-y-3">
                  {mitigationResult.mitigations_applied.map((m, i) => (
                    <div key={i} className="border border-border rounded-md p-4">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono text-text-primary text-sm">{m.column}</span>
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded border border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10">
                          {m.action.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-text-secondary text-sm mb-1">{m.description}</p>
                      <p className="text-text-muted text-xs">{m.reason}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {mitigationResult.optimization.evaluations.length > 0 && (
              <Card title="Privacy / utility trade-off" eyebrow="optimizer ranking" className="mb-6">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-text-muted text-xs uppercase tracking-wide border-b border-border">
                        <th className="py-2 pr-4 font-mono font-normal">Column</th>
                        <th className="py-2 pr-4 font-mono font-normal">Action</th>
                        <th className="py-2 pr-4 font-mono font-normal">Risk reduction</th>
                        <th className="py-2 pr-4 font-mono font-normal">Utility loss</th>
                        <th className="py-2 pr-4 font-mono font-normal">Weighted score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mitigationResult.optimization.evaluations.map((e, i) => (
                        <tr key={i} className="border-b border-border/60">
                          <td className="py-2 pr-4 font-mono text-text-primary">{e.column}</td>
                          <td className="py-2 pr-4 text-text-secondary">{e.action.replace(/_/g, " ")}</td>
                          <td className="py-2 pr-4 font-mono text-risk-low">{e.risk_reduction_pct}%</td>
                          <td className="py-2 pr-4 font-mono text-risk-high">{e.utility_loss_pct}%</td>
                          <td className="py-2 pr-4 font-mono text-text-primary">{e.weighted_score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {mitigationResult.optimization.recommended && (
                  <p className="text-text-secondary text-xs mt-3">
                    Best single trade-off: <span className="text-accent-cyan font-mono">{mitigationResult.optimization.recommended.column}</span> via{" "}
                    {mitigationResult.optimization.recommended.action.replace(/_/g, " ")}.
                  </p>
                )}
              </Card>
            )}

            <Card title="Fix & Re-test" eyebrow="closes the loop">
              <p className="text-text-secondary text-sm mb-4">
                Re-run the same attack against the mitigated dataset to measure whether risk actually changed —
                this is a real recomputation, not an assumed improvement.
              </p>
              <Button onClick={runFixAndRetest} disabled={loadingRetest || mitigationResult.mitigations_applied.length === 0}>
                {loadingRetest ? "Re-testing..." : "Fix & Re-test"}
              </Button>
              {loadingRetest && <div className="mt-4"><Loading label="Comparing before/after risk" /></div>}
              {comparison && !loadingRetest && (
                <div className="mt-6 pt-6 border-t border-border">
                  <RiskChangeSummary before={comparison.before} after={comparison.after} />
                  <div className="mt-4">
                    <Button variant="secondary" onClick={() => navigate("/comparison")}>View full comparison</Button>
                  </div>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
