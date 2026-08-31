# API Reference

Base URL: `http://localhost:8000`. Interactive Swagger docs are always
available at `/docs` when the backend is running.

All responses are JSON unless noted. All dataset IDs are 12-character hex
strings returned from upload/generate endpoints.

---

### `POST /api/datasets/upload`

Multipart form upload. Fields: `file` (CSV or Parquet, ≤10MB), `role`
(optional, `main` or `auxiliary`, default `main`).

Returns: `{ dataset_id, role, profile }`

---

### `GET /api/datasets/{dataset_id}/profile`

Recomputes and returns the dataset profile (row/column counts, per-column
stats).

---

### `POST /api/datasets/{dataset_id}/analyze`

Runs profiling + identifier/QI/sensitive-attribute classification +
uniqueness analysis + k-anonymity report.

Returns: `{ profile, classification, uniqueness, k_anonymity }`

---

### `POST /api/datasets/{dataset_id}/attack`

Form field: `aux_dataset_id`. Runs the record linkage attack against the
given auxiliary dataset and recomputes the full risk score.

Returns: `{ linkage, risk, aux_dataset_id }`

---

### `GET /api/datasets/{dataset_id}/risks`

Returns the most recently computed risk score for the dataset (requires
`/attack` to have been run first).

---

### `GET /api/datasets/{dataset_id}/clusters?k=5`

Returns equivalence classes with fewer than `k` records (vulnerable
clusters), sorted by size ascending.

Returns: `{ clusters: [...], qi_columns, k, total_vulnerable_clusters }`

---

### `GET /api/datasets/{dataset_id}/explain/{match_index}`

Returns a human-readable, attribute-grounded explanation for the
`match_index`-th match from the most recent `/attack` call.

---

### `POST /api/datasets/{dataset_id}/mitigate`

JSON body: `{ dataset_id, mitigations: [...] | null }`. If `mitigations`
is omitted, PrivaLens generates its own recommendations from the dataset's
column statistics. Applies the mitigations to a copy of the dataset and
persists it as a new dataset.

Returns: `{ mitigations_applied, optimization, mitigated_dataset_id }`

---

### `POST /api/datasets/{dataset_id}/retest`

Form fields: `mitigated_dataset_id`, `aux_dataset_id`. Re-runs the full
pipeline on the mitigated dataset and diffs it against the original
dataset's risk score.

Returns: `{ comparison: { before, after, risk_score_delta }, after_analysis }`

---

### `GET /api/datasets/{dataset_id}/comparison`

Returns the most recent retest comparison for the dataset.

---

### `GET /api/datasets/{dataset_id}/report?format=json|markdown`

Assembles a full report from all prior analyses. `format=markdown`
returns `text/markdown`; otherwise JSON.

---

### `POST /api/synthetic/generate`

Form fields: `preset` (`healthcare` | `education` | `finance`), `n`
(record count, default 500). Generates and persists a synthetic dataset.

---

### `POST /api/demo/run`

JSON body: `{ preset, n }`. Runs the entire ATTACK → FIX → RE-TEST loop
server-side in one call: generates a synthetic dataset + auxiliary
dataset, profiles, attacks, scores, mitigates, and re-tests.

Returns: `{ main_dataset_id, aux_dataset_id, mitigated_dataset_id, before, mitigations, after, comparison }`

---

### `GET /api/audit?dataset_id=...`

Returns the audit log (action + timestamp, never raw record values),
optionally filtered to one dataset.

---

### `GET /health`

Liveness check: `{ "status": "healthy" }`
