import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { Card, Button, ErrorCard, Loading, Stat, EmptyState } from "../components/UI.jsx";
import Expandable from "../components/Expandable.jsx";
import { useDataset } from "../context/DatasetContext.jsx";
import { api } from "../api/client.js";
import usePageTitle from "../lib/usePageTitle.js";

const CATEGORY_STYLE = {
  direct_identifier: "text-risk-critical border-risk-critical/40 bg-risk-critical/10",
  possible_direct_identifier: "text-risk-high border-risk-high/40 bg-risk-high/10",
  quasi_identifier: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  possible_quasi_identifier: "text-risk-moderate border-risk-moderate/40 bg-risk-moderate/10",
  sensitive_attribute: "text-accent-cyan border-accent-cyan/40 bg-accent-cyan/10",
  unclassified: "text-text-muted border-border bg-bg-elevated",
};

function CategoryTag({ category }) {
  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-mono border ${CATEGORY_STYLE[category] || CATEGORY_STYLE.unclassified}`}>
      {category.replace(/_/g, " ")}
    </span>
  );
}

// Direct identifiers must visually dominate, quasi-identifiers next,
// then sensitive attributes, with anything unclassified last - this
// ordering replaces a flat, unsorted table that buried the highest-risk
// columns wherever the source CSV happened to put them.
const GROUP_ORDER = [
  { categories: ["direct_identifier", "possible_direct_identifier"], label: "Direct identifiers", eyebrow: "highest priority — these alone can identify someone", tone: "text-risk-critical" },
  { categories: ["quasi_identifier", "possible_quasi_identifier"], label: "Quasi-identifiers", eyebrow: "identifying only in combination", tone: "text-risk-moderate" },
  { categories: ["sensitive_attribute"], label: "Sensitive attributes", eyebrow: "not identifying, but exposes protected information if linked", tone: "text-accent-cyan" },
  { categories: ["unclassified"], label: "Other / unclassified", eyebrow: "no strong signal found", tone: "text-text-muted" },
];

function ColumnRow({ c, profileCol, isOpen, onToggle, onClose }) {
  return (
    <div className="border border-border rounded-md mb-2 last:mb-0">
      <Expandable
        expanded={isOpen}
        onToggle={onToggle}
        onClose={onClose}
        ariaLabel={`${c.column}, classified as ${c.category.replace(/_/g, " ")} with ${(c.confidence * 100).toFixed(0)} percent confidence. Press Enter for details.`}
        className="flex items-center justify-between gap-4 px-4 py-2.5 hover:bg-bg-elevated"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden="true" className="text-text-muted shrink-0">{isOpen ? "\u25BE" : "\u25B8"}</span>
          <span className="font-mono text-text-primary text-sm truncate">{c.column}</span>
          <span className="text-text-secondary text-xs shrink-0">{profileCol?.inferred_type}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="font-mono text-xs text-text-secondary">{(c.confidence * 100).toFixed(0)}% confidence</span>
          <CategoryTag category={c.category} />
        </div>
      </Expandable>
      {isOpen && (
        <div className="px-4 pb-3 pt-0 border-t border-border/60 bg-bg-elevated/40">
          <div className="mt-3 mb-1 text-text-muted uppercase tracking-wide text-[10px]">Why this classification</div>
          <ul className="list-disc list-inside space-y-0.5 text-text-secondary text-xs">
            {c.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
          {profileCol?.sample_values?.length > 0 && (
            <div className="mt-2 font-mono text-[11px] text-text-muted">
              sample: {profileCol.sample_values.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Profiler() {
  usePageTitle("Profiler");
  const navigate = useNavigate();
  const { mainDataset, analysis, setAnalysis } = useDataset();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const runAnalyze = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.analyzeDataset(mainDataset.id);
      setAnalysis(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!mainDataset) {
    return (
      <div>
        <PageHeader eyebrow="Step 2" title="Dataset profiler" />
        <div className="px-8 py-8 max-w-2xl">
          <EmptyState
            title="No dataset loaded"
            description="Upload a dataset first so it can be profiled and classified."
            action={<Button onClick={() => navigate("/upload")}>Go to Upload</Button>}
          />
        </div>
      </div>
    );
  }

  // Real grouping used to render the table below - this used to be
  // computed and then silently discarded, leaving columns in a flat,
  // unsorted list. Now it actually drives the layout.
  const columnsByCat = analysis
    ? analysis.classification.columns.reduce((acc, c) => {
        (acc[c.category] ||= []).push(c);
        return acc;
      }, {})
    : {};

  return (
    <div>
      <PageHeader
        eyebrow="Step 2"
        title="Dataset profiler"
        description="Every column is classified with a visible confidence score and reason — nothing here is a black box."
        action={
          !analysis && (
            <Button onClick={runAnalyze} disabled={loading}>
              {loading ? "Analyzing..." : "Run analysis"}
            </Button>
          )
        }
      />

      <div className="px-8 py-8">
        {error && (
          <div className="mb-6">
            <ErrorCard
              what="Dataset analysis could not complete."
              why={error}
              next="Confirm the file uploaded correctly, then try running the analysis again."
              action={<Button variant="secondary" onClick={runAnalyze}>Retry analysis</Button>}
            />
          </div>
        )}
        {loading && <Loading label="Detecting identifiers and computing equivalence classes" />}

        {!analysis && !loading && (
          <EmptyState
            title="Ready to analyze"
            description={`${mainDataset.name} has ${mainDataset.profile.row_count} rows and ${mainDataset.profile.column_count} columns. Run the analysis to classify each column.`}
            action={<Button onClick={runAnalyze}>Run analysis</Button>}
          />
        )}

        {analysis && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 mb-8">
              <Card><Stat label="Direct identifiers" value={analysis.classification.direct_identifiers.length} valueClassName="text-risk-critical" /></Card>
              <Card><Stat label="Quasi-identifiers" value={analysis.classification.quasi_identifiers.length} valueClassName="text-risk-moderate" /></Card>
              <Card><Stat label="Sensitive attributes" value={analysis.classification.sensitive_attributes.length} valueClassName="text-accent-cyan" /></Card>
              <Card><Stat label="Min equivalence class" value={analysis.k_anonymity.min_class_size ?? "—"} /></Card>
            </div>

            <div className="space-y-6">
              {GROUP_ORDER.map((group) => {
                const cols = group.categories.flatMap((cat) => columnsByCat[cat] || []);
                if (cols.length === 0) return null;
                return (
                  <Card
                    key={group.label}
                    title={group.label}
                    eyebrow={`${cols.length} column${cols.length !== 1 ? "s" : ""} — ${group.eyebrow}`}
                  >
                    {cols.map((c) => {
                      const profileCol = analysis.profile.columns.find((p) => p.name === c.column);
                      const isOpen = expanded === c.column;
                      return (
                        <ColumnRow
                          key={c.column}
                          c={c}
                          profileCol={profileCol}
                          isOpen={isOpen}
                          onToggle={() => setExpanded(isOpen ? null : c.column)}
                          onClose={() => setExpanded(null)}
                        />
                      );
                    })}
                  </Card>
                );
              })}
            </div>

            <div className="mt-8 flex gap-3">
              <Button onClick={() => navigate("/attack")}>Continue to Attack Simulation</Button>
              <Button variant="secondary" onClick={() => navigate("/dashboard")}>Skip to Risk Dashboard</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
