const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {
      /* ignore parse errors */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export const api = {
  base: BASE_URL,

  uploadDataset: (file, role = "main") => {
    const form = new FormData();
    form.append("file", file);
    form.append("role", role);
    return fetch(`${BASE_URL}/api/datasets/upload`, { method: "POST", body: form }).then(handle);
  },

  getProfile: (datasetId) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/profile`).then(handle),

  analyzeDataset: (datasetId) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/analyze`, { method: "POST" }).then(handle),

  attackDataset: (datasetId, auxDatasetId) => {
    const form = new FormData();
    form.append("aux_dataset_id", auxDatasetId);
    return fetch(`${BASE_URL}/api/datasets/${datasetId}/attack`, { method: "POST", body: form }).then(handle);
  },

  getRisks: (datasetId) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/risks`).then(handle),

  getClusters: (datasetId, k = 5) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/clusters?k=${k}`).then(handle),

  explainMatch: (datasetId, matchIndex) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/explain/${matchIndex}`).then(handle),

  mitigateDataset: (datasetId, mitigations = null) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/mitigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId, mitigations }),
    }).then(handle),

  retestDataset: (datasetId, mitigatedDatasetId, auxDatasetId) => {
    const form = new FormData();
    form.append("mitigated_dataset_id", mitigatedDatasetId);
    form.append("aux_dataset_id", auxDatasetId);
    return fetch(`${BASE_URL}/api/datasets/${datasetId}/retest`, { method: "POST", body: form }).then(handle);
  },

  getComparison: (datasetId) =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/comparison`).then(handle),

  getReport: (datasetId, format = "json") =>
    fetch(`${BASE_URL}/api/datasets/${datasetId}/report?format=${format}`).then((res) =>
      format === "markdown" ? res.text() : handle(res)
    ),

  generateSynthetic: (preset, n = 500) => {
    const form = new FormData();
    form.append("preset", preset);
    form.append("n", n);
    return fetch(`${BASE_URL}/api/synthetic/generate`, { method: "POST", body: form }).then(handle);
  },

  runDemo: (preset = "healthcare", n = 500) =>
    fetch(`${BASE_URL}/api/demo/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset, n }),
    }).then(handle),

  getAudit: (datasetId = null) => {
    const q = datasetId ? `?dataset_id=${datasetId}` : "";
    return fetch(`${BASE_URL}/api/audit${q}`).then(handle);
  },

  // -------------------------------------------------------------------
  // DataRescue
  // -------------------------------------------------------------------
  prepareJudgeMode: (n = 300) =>
    fetch(`${BASE_URL}/api/rescue/judge-mode/prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n }),
    }).then(handle),

  startRescue: (datasetId, auxDatasetId = null, targetColumn = null, objective = null) =>
    fetch(`${BASE_URL}/api/rescue/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId, aux_dataset_id: auxDatasetId,
        target_column: targetColumn, objective,
      }),
    }).then(handle),

  listRescueJobs: () => fetch(`${BASE_URL}/api/rescue/jobs`).then(handle),

  getRescueJob: (jobId) => fetch(`${BASE_URL}/api/rescue/${jobId}`).then(handle),

  getRescueEvents: (jobId) => fetch(`${BASE_URL}/api/rescue/${jobId}/events`).then(handle),

  approveRescueAction: (jobId, actionId) =>
    fetch(`${BASE_URL}/api/rescue/${jobId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId }),
    }).then(handle),

  rejectRescueAction: (jobId, actionId) =>
    fetch(`${BASE_URL}/api/rescue/${jobId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId }),
    }).then(handle),
};
