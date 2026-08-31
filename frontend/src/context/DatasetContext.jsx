import React, { createContext, useContext, useState, useCallback } from "react";

export const DatasetContext = createContext(null);

export function DatasetProvider({ children }) {
  const [mainDataset, setMainDataset] = useState(null); // {id, name, profile}
  const [auxDataset, setAuxDataset] = useState(null);
  const [mitigatedDataset, setMitigatedDataset] = useState(null);

  const [analysis, setAnalysis] = useState(null); // classification + uniqueness + k-anon
  const [attackResult, setAttackResult] = useState(null); // linkage + risk
  const [mitigationResult, setMitigationResult] = useState(null);
  const [comparison, setComparison] = useState(null);

  const reset = useCallback(() => {
    setMainDataset(null);
    setAuxDataset(null);
    setMitigatedDataset(null);
    setAnalysis(null);
    setAttackResult(null);
    setMitigationResult(null);
    setComparison(null);
  }, []);

  const loadFromDemo = useCallback((demoResult) => {
    setMainDataset({ id: demoResult.main_dataset_id, name: `Demo dataset`, profile: demoResult.before.profile });
    setAuxDataset({ id: demoResult.aux_dataset_id, name: "Demo auxiliary dataset" });
    setMitigatedDataset({ id: demoResult.mitigated_dataset_id, name: "Mitigated dataset" });
    setAnalysis({
      profile: demoResult.before.profile,
      classification: demoResult.before.classification,
      uniqueness: demoResult.before.uniqueness,
      k_anonymity: demoResult.before.k_anonymity,
    });
    setAttackResult({ linkage: demoResult.before.linkage, risk: demoResult.before.risk });
    setMitigationResult({ mitigations_applied: demoResult.mitigations, mitigated_dataset_id: demoResult.mitigated_dataset_id });
    setComparison(demoResult.comparison);
  }, []);

  return (
    <DatasetContext.Provider
      value={{
        mainDataset, setMainDataset,
        auxDataset, setAuxDataset,
        mitigatedDataset, setMitigatedDataset,
        analysis, setAnalysis,
        attackResult, setAttackResult,
        mitigationResult, setMitigationResult,
        comparison, setComparison,
        reset,
        loadFromDemo,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
}

export function useDataset() {
  const ctx = useContext(DatasetContext);
  if (!ctx) throw new Error("useDataset must be used within DatasetProvider");
  return ctx;
}
