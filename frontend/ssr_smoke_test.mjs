// Renders every page component server-side using Vite's own ssrLoadModule,
// so the exact same JSX/ESM pipeline the app ships with is exercised - no
// separate babel/CJS toolchain that could mask or introduce discrepancies.
import { createServer } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";

global.window = global.window || {};
global.window.matchMedia = global.window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));

async function main() {
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: "custom",
    optimizeDeps: { noDiscovery: true },
  });

  const { DatasetContext } = await vite.ssrLoadModule("/src/context/DatasetContext.jsx");
  const Home = (await vite.ssrLoadModule("/src/pages/Home.jsx")).default;
  const Upload = (await vite.ssrLoadModule("/src/pages/Upload.jsx")).default;
  const Profiler = (await vite.ssrLoadModule("/src/pages/Profiler.jsx")).default;
  const Dashboard = (await vite.ssrLoadModule("/src/pages/Dashboard.jsx")).default;
  const AttackSimulation = (await vite.ssrLoadModule("/src/pages/AttackSimulation.jsx")).default;
  const VulnerabilityExplorer = (await vite.ssrLoadModule("/src/pages/VulnerabilityExplorer.jsx")).default;
  const Mitigation = (await vite.ssrLoadModule("/src/pages/Mitigation.jsx")).default;
  const Comparison = (await vite.ssrLoadModule("/src/pages/Comparison.jsx")).default;
  const Report = (await vite.ssrLoadModule("/src/pages/Report.jsx")).default;
  const Demo = (await vite.ssrLoadModule("/src/pages/Demo.jsx")).default;
  const RescueJobs = (await vite.ssrLoadModule("/src/pages/RescueJobs.jsx")).default;
  const RescueJobDetail = (await vite.ssrLoadModule("/src/pages/RescueJobDetail.jsx")).default;
  const Sidebar = (await vite.ssrLoadModule("/src/components/Sidebar.jsx")).default;

  // -------------------------------------------------------------------
  // Mock data mirroring REAL response shapes captured from live backend
  // runs against this exact codebase (see AUDIT.md).
  // -------------------------------------------------------------------
  const profile = {
    row_count: 300, column_count: 8, duplicate_rows: 0, duplicate_pct: 0.0,
    total_missing_cells: 0,
    columns: [
      { name: "PatientID", dtype: "object", inferred_type: "text", missing_count: 0, missing_pct: 0, unique_count: 300, cardinality_ratio: 1.0, is_constant: false, is_high_cardinality: true, sample_values: ["P00000", "P00001"] },
      { name: "Age", dtype: "int64", inferred_type: "numeric", missing_count: 0, missing_pct: 0, unique_count: 70, cardinality_ratio: 0.23, is_constant: false, is_high_cardinality: false, sample_values: ["45", "30"] },
      { name: "Gender", dtype: "object", inferred_type: "categorical", missing_count: 0, missing_pct: 0, unique_count: 2, cardinality_ratio: 0.006, is_constant: false, is_high_cardinality: false, sample_values: ["Male", "Female"] },
      { name: "Pincode", dtype: "object", inferred_type: "categorical", missing_count: 0, missing_pct: 0, unique_count: 240, cardinality_ratio: 0.8, is_constant: false, is_high_cardinality: false, sample_values: ["110045"] },
      { name: "Occupation", dtype: "object", inferred_type: "categorical", missing_count: 0, missing_pct: 0, unique_count: 12, cardinality_ratio: 0.04, is_constant: false, is_high_cardinality: false, sample_values: ["Nurse"] },
      { name: "AdmissionDate", dtype: "object", inferred_type: "datetime", missing_count: 0, missing_pct: 0, unique_count: 280, cardinality_ratio: 0.93, is_constant: false, is_high_cardinality: true, sample_values: ["2026-01-15"] },
      { name: "Hospital", dtype: "object", inferred_type: "categorical", missing_count: 0, missing_pct: 0, unique_count: 4, cardinality_ratio: 0.01, is_constant: false, is_high_cardinality: false, sample_values: ["City General"] },
      { name: "Diagnosis", dtype: "object", inferred_type: "categorical", missing_count: 0, missing_pct: 0, unique_count: 10, cardinality_ratio: 0.03, is_constant: false, is_high_cardinality: false, sample_values: ["Hypertension"] },
    ],
  };

  const classification = {
    columns: [
      { column: "PatientID", category: "direct_identifier", confidence: 0.9, reasons: ["Column name matches direct-identifier pattern"] },
      { column: "Age", category: "quasi_identifier", confidence: 0.8, reasons: ["Column name matches quasi-identifier pattern"] },
    ],
    direct_identifiers: ["PatientID"],
    quasi_identifiers: ["Age", "Gender", "Pincode", "Occupation", "AdmissionDate", "Hospital"],
    sensitive_attributes: ["Diagnosis"],
    unclassified: [],
  };

  const uniqueness = {
    qi_columns: classification.quasi_identifiers, equivalence_classes: 300,
    unique_records: 300, unique_pct: 100.0,
    class_size_distribution: { "1": 300, "2-4": 0, "5-9": 0, "10-49": 0, "50+": 0 },
  };

  const k_anonymity = {
    qi_columns: classification.quasi_identifiers, total_records: 300, min_class_size: 1,
    checks: [
      { k: 2, at_risk_records: 300, at_risk_pct: 100.0, satisfies_k_anonymity: false },
      { k: 3, at_risk_records: 300, at_risk_pct: 100.0, satisfies_k_anonymity: false },
      { k: 5, at_risk_records: 300, at_risk_pct: 100.0, satisfies_k_anonymity: false },
      { k: 10, at_risk_records: 300, at_risk_pct: 100.0, satisfies_k_anonymity: false },
    ],
  };

  const linkage = {
    shared_columns: ["Age", "Gender", "Pincode", "Occupation"],
    column_kinds: { Age: "numeric", Gender: "categorical", Pincode: "categorical", Occupation: "categorical" },
    candidates_tested: 90000, matches_found: 900, highest_confidence: 1.0,
    matches: [
      { record_a_index: 0, record_b_index: 5, match_probability: 0.95, risk_level: "CRITICAL",
        matching_attributes: { Age: { score: 1.0, kind: "numeric", weight_key: "numeric_closeness" }, Gender: { score: 1.0, kind: "categorical", weight_key: "categorical_exact" } } },
    ],
  };

  const risk = {
    overall_score: 91.25, risk_level: "CRITICAL",
    components: { linkage_confidence: 100.0, uniqueness: 100.0, equivalence_class_risk: 100.0, sensitive_attribute_exposure: 12.5 },
    weights_used: { linkage_confidence: 0.4, uniqueness: 0.3, equivalence_class_risk: 0.2, sensitive_attribute_exposure: 0.1 },
    at_risk_records: 300, min_class_size: 1,
  };

  const mitigationResult = {
    mitigations_applied: [
      { column: "Age", action: "generalization_bucketing", description: "Bucket 'Age' into ranges", reason: "High cardinality ratio" },
      { column: "Pincode", action: "truncation_generalization", description: "Truncate 'Pincode'", reason: "Full postal codes are identifying" },
    ],
    optimization: {
      evaluations: [
        { column: "Age", action: "generalization_bucketing", risk_reduction_pct: 38.0, utility_loss_pct: 8.0, score: 30.0, weighted_score: 19.6 },
        { column: "Pincode", action: "truncation_generalization", risk_reduction_pct: 42.0, utility_loss_pct: 12.0, score: 30.0, weighted_score: 20.4 },
      ],
      recommended: { column: "Pincode", action: "truncation_generalization", risk_reduction_pct: 42.0, utility_loss_pct: 12.0, weighted_score: 20.4 },
      weights: { risk_weight: 0.6, utility_weight: 0.4 },
    },
    mitigated_dataset_id: "abc123def456",
  };

  const comparison = {
    before: { risk_score: 91.25, risk_level: "CRITICAL", at_risk_records: 300, min_class_size: 1 },
    after: { risk_score: 9.8, risk_level: "LOW", at_risk_records: 12, min_class_size: 6 },
    risk_score_delta: 81.45,
  };

  const report = {
    generated_at: "2026-08-20T00:00:00Z", dataset_name: "demo_healthcare.csv",
    executive_summary: { rows: 300, columns: 8, overall_risk_score: 91.25, overall_risk_level: "CRITICAL" },
    findings: { direct_identifiers: ["PatientID"], quasi_identifiers: classification.quasi_identifiers, sensitive_attributes: ["Diagnosis"], min_equivalence_class_size: 1, unique_records_pct: 100.0 },
    attack_summary: { shared_columns: linkage.shared_columns, candidates_tested: 90000, matches_found: 900, highest_confidence: 1.0 },
    risk_breakdown: risk.components,
    recommendations: mitigationResult.mitigations_applied,
    disclaimer: "PrivaLens provides a technical privacy-risk assessment...",
    llm_explanation: "This dataset was assessed as CRITICAL risk...",
  };

  const emptyCtx = {
    mainDataset: null, setMainDataset: () => {},
    auxDataset: null, setAuxDataset: () => {},
    mitigatedDataset: null, setMitigatedDataset: () => {},
    analysis: null, setAnalysis: () => {},
    attackResult: null, setAttackResult: () => {},
    mitigationResult: null, setMitigationResult: () => {},
    comparison: null, setComparison: () => {},
    reset: () => {}, loadFromDemo: () => {},
  };

  const loadedCtx = {
    mainDataset: { id: "main123", name: "demo_healthcare.csv", profile },
    setMainDataset: () => {},
    auxDataset: { id: "aux456", name: "demo_aux.csv" },
    setAuxDataset: () => {},
    mitigatedDataset: { id: "mit789", name: "demo_healthcare.csv (mitigated)" },
    setMitigatedDataset: () => {},
    analysis: { profile, classification, uniqueness, k_anonymity },
    setAnalysis: () => {},
    attackResult: { linkage, risk },
    setAttackResult: () => {},
    mitigationResult,
    setMitigationResult: () => {},
    comparison,
    setComparison: () => {},
    reset: () => {},
    loadFromDemo: () => {},
  };

  function renderWithCtx(Component, ctx) {
    const el = React.createElement(
      MemoryRouter,
      null,
      React.createElement(DatasetContext.Provider, { value: ctx }, React.createElement(Component))
    );
    return renderToStaticMarkup(el);
  }

  const pages = [
    ["Home", Home], ["Upload", Upload], ["Profiler", Profiler], ["Dashboard", Dashboard],
    ["AttackSimulation", AttackSimulation], ["VulnerabilityExplorer", VulnerabilityExplorer],
    ["Mitigation", Mitigation], ["Comparison", Comparison], ["Report", Report],
    ["Demo", Demo], ["RescueJobs", RescueJobs], ["RescueJobDetail", RescueJobDetail], ["Sidebar", Sidebar],
  ];

  let failures = 0;
  for (const [name, Component] of pages) {
    for (const [stateName, ctx] of [["empty", emptyCtx], ["loaded", loadedCtx]]) {
      try {
        const html = renderWithCtx(Component, ctx);
        if (!html || html.length < 10) throw new Error("suspiciously short output");
        console.log(`PASS  ${name} (${stateName})   [${html.length} chars]`);
      } catch (e) {
        failures++;
        console.log(`FAIL  ${name} (${stateName})   -> ${e.message}`);
      }
    }
  }

  console.log("\n" + (failures === 0 ? `ALL ${pages.length * 2} RENDER CHECKS PASSED` : `${failures} RENDER CHECK(S) FAILED`));
  await vite.close();
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("FATAL:", e);
  process.exit(1);
});
