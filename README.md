# PrivaLens DataRescue

**Think Like an Attacker. Protect Like a Defender.**

PrivaLens DataRescue is a privacy red-team platform. It attacks your own
"anonymized" datasets before someone else does — running a real
record-linkage simulation, scoring exactly how re-identifiable the data
is, recommending and applying fixes, and re-running the same attack to
prove the risk actually dropped.

The product loop: **ATTACK → DETECT → EXPLAIN → FIX → RE-TEST**

Built on top of that engine, **DataRescue** is an autonomous agent that
runs a broader OBSERVE → REASON → PLAN → ACT → VERIFY → ADAPT loop:
inspecting a messy dataset, detecting data-quality *and* privacy *and*
ML-readiness problems, auto-fixing what's safe, pausing for human
approval on anything privacy-sensitive, attacking its own output to
prove the fix worked, and never overwriting the original dataset. See
[DataRescue](#datarescue) below and [AUDIT_RESCUE.md](AUDIT_RESCUE.md)
for exactly what's real versus scoped down in that layer.

Every number shown in the UI is computed from the uploaded dataset at
request time. Nothing is hardcoded or fabricated — see [AUDIT.md](AUDIT.md)
for a line-by-line honesty check of the core PrivaLens engine and
[Limitations](#limitations) below.

---

## Overview

Organizations routinely strip obvious identifiers (name, email, phone,
patient ID) and assume a dataset is anonymous. But combinations of
harmless-looking attributes — age, gender, pincode, occupation, admission
date — can still uniquely identify a person once an attacker cross-references
a second, auxiliary dataset. PrivaLens answers the real question:

> "Can an attacker still identify someone from this dataset?"

not just "did we remove the names?"

## Problem

Removing direct identifiers does not eliminate re-identification risk.
Quasi-identifiers combine to create small, unique groups (equivalence
classes) that an attacker can narrow down using publicly available or
leaked auxiliary data. PrivaLens makes this risk measurable and fixable.

## Architecture

```
                    Frontend (React + Vite + Tailwind)
                               |
                          FastAPI backend
                               |
        ------------------------------------------------
        |                |                 |            |
    Profiler         Privacy Engine    Attack Engine   Mitigation
   (profiler.py)   (k_anonymity.py)   (linkage.py)   (transforms.py,
                                                        optimizer.py)
        |                |                 |            |
        -------------------------------------------------
                               |
                        Risk Scoring Engine
                        (risk_engine.py)
                               |
                ------------------------------------
                |              |                    |
          Explanation    Mitigation Engine       Reporting
        (llm_explain.py)  (already applied)  (report_generator.py)
                               |
                         Fix & Re-test loop
                     (pipeline.py: fix_and_retest)
```

Dataframes are stored on disk as Parquet under `backend/data/`; SQLite
(`backend/data/privalens.db`) stores only metadata, analysis results, and
an audit log — never raw record content, per the privacy-by-design
requirement this product itself demonstrates.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full data flow
and [`docs/API.md`](docs/API.md) for endpoint documentation.

## Folder structure

```
privalens-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app entrypoint
│   │   ├── config.py                All tunable weights/thresholds
│   │   ├── storage.py                Dataframe read/write (parquet)
│   │   ├── api/
│   │   │   └── routes.py            All REST endpoints
│   │   ├── services/
│   │   │   ├── profiler.py          Dataset profiling engine
│   │   │   ├── identifier_detection.py   Direct/quasi/sensitive classifier
│   │   │   ├── synthetic_data.py    Synthetic dataset + auxiliary generator
│   │   │   ├── pipeline.py          Orchestrates the full analysis loop
│   │   │   └── llm_explain.py       Optional LLM-grounded explanations
│   │   ├── privacy/
│   │   │   └── k_anonymity.py       k-anonymity, uniqueness, l-diversity
│   │   ├── attacks/
│   │   │   └── linkage.py           Record linkage attack simulation
│   │   ├── scoring/
│   │   │   └── risk_engine.py       Weighted 0-100 risk score
│   │   ├── mitigation/
│   │   │   ├── transforms.py        Generalization/suppression/bucketing
│   │   │   └── optimizer.py         Privacy/utility trade-off ranking
│   │   ├── reporting/
│   │   │   └── report_generator.py  JSON + Markdown report builder
│   │   └── models/
│   │       ├── db.py                 SQLite persistence
│   │       └── schemas.py            Pydantic request/response models
│   ├── tests/                        pytest suite (18 tests)
│   ├── data/                         uploads/ generated/ demo/ (runtime)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── pages/                    10 pages (see below)
│   │   ├── components/               Sidebar, RiskGauge, RiskBadge, UI kit
│   │   ├── context/DatasetContext.jsx   Shared app state
│   │   ├── api/client.js             Typed fetch wrapper for every endpoint
│   │   ├── App.jsx / main.jsx
│   │   └── index.css
│   ├── ssr_smoke_test.mjs            SSR smoke test for all 10 pages (npm run test:ssr)
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── Dockerfile
│   └── .env.example
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── API.md
├── scripts/
│   └── run_benchmark.py              Evaluation benchmark (real metrics)
├── docker-compose.yml
├── AUDIT.md                          Honest implementation-vs-claim audit
├── README.md
└── LICENSE
```

## Features (implemented)

- CSV/Parquet upload with size limits and validation
- Automatic dataset profiling (row/column counts, missing values,
  cardinality, duplicates, constant/high-cardinality columns)
- Rule-based, confidence-scored classification into direct identifiers,
  quasi-identifiers and sensitive attributes (camelCase/snake_case-aware
  column-name matching + statistical fallback)
- Uniqueness analysis and equivalence-class distribution
- k-anonymity checks at configurable k (2, 3, 5, 10) with violating-record
  counts
- l-diversity for the first detected sensitive attribute
- Record linkage attack: exact categorical matching, normalized numeric
  distance, fuzzy string similarity, and date-proximity scoring, combined
  with configurable weights (`app/config.py::LINKAGE_WEIGHTS`)
- Per-match explainability ("why is this HIGH RISK?") grounded in the
  underlying attribute-level scores
- Vulnerable-cluster explorer grouped by equivalence class
- Transparent, weighted 0-100 re-identification risk score
  (`app/config.py::RISK_WEIGHTS`)
- Mitigation recommendations (age/numeric bucketing, pincode truncation,
  date generalization, categorical suppression) generated from real
  column statistics, each with a stated reason
- A working **Fix & Re-test** loop: mitigations are actually applied to
  the dataframe, and the same attack is re-run to measure the before/after
  delta
- Privacy/utility trade-off optimizer that scores each candidate
  transformation by risk-reduction vs utility loss and recommends the best
  one
- Downloadable privacy report (JSON and Markdown)
- Synthetic dataset generator (healthcare, education, finance presets)
  plus a matching auxiliary "attacker" dataset
- One-click Demo Mode running the entire ATTACK → FIX → RE-TEST loop in
  a single API call
- SQLite audit log of every action taken on a dataset
- Optional LLM explanation layer (disabled without an API key; falls back
  to a deterministic template — the LLM never computes risk, only
  paraphrases already-computed structured findings)

## Roadmap (not implemented — do not assume otherwise)

- Membership inference attacks
- GNN-based risk modelling
- Federated privacy auditing across multiple organizations
- Continuous/scheduled privacy monitoring and CI/CD integration
- Enterprise SSO and government system integrations
- Production-grade synthetic data generation (differential-privacy backed)
- Multi-cloud deployment and horizontal scaling

## Installation

Requires Python 3.11+, Node 20+, and (optionally) Docker.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional: add ANTHROPIC_API_KEY for LLM explanations
uvicorn app.main:app --reload --port 8000
```

Backend is now available at `http://localhost:8000` (interactive API docs
at `/docs`).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

Frontend is now available at `http://localhost:5173`.

### One-command startup (Docker)

```bash
docker compose up --build
```

This builds and starts both services: backend on port 8000, frontend on
port 5173.

## Running the demo

From the frontend, open **Demo Mode** in the sidebar, pick a preset
(healthcare / education / finance), and click **Launch Demo**. This calls
`POST /api/demo/run`, which:

1. Generates a synthetic dataset with intentionally skewed quasi-identifier
   combinations (so real, small equivalence classes exist)
2. Generates a matching auxiliary "attacker" dataset
3. Profiles and classifies columns
4. Runs the linkage attack and computes the risk score
5. Recommends and applies mitigations
6. Re-runs the attack against the mitigated data and returns the before/after
   comparison

All of this happens server-side in one request; the frontend just renders
the result. On a typical laptop this completes in under 30 seconds for a
400-record demo dataset.

## API

See [`docs/API.md`](docs/API.md) for the full endpoint reference. Key
endpoints:

```
POST /api/datasets/upload
GET  /api/datasets/{id}/profile
POST /api/datasets/{id}/analyze
POST /api/datasets/{id}/attack
GET  /api/datasets/{id}/risks
GET  /api/datasets/{id}/clusters
POST /api/datasets/{id}/mitigate
POST /api/datasets/{id}/retest
GET  /api/datasets/{id}/comparison
GET  /api/datasets/{id}/report
POST /api/demo/run
GET  /api/audit
```

## Evaluation / Benchmark

`scripts/run_benchmark.py` generates a synthetic healthcare dataset with a
**known** ground truth (which columns are direct identifiers,
quasi-identifiers, and sensitive attributes), then measures:

- Detection precision / recall / F1 against that ground truth
- k-anonymity and uniqueness metrics
- Linkage attack candidates tested, matches found, and timing
- Risk score and its component breakdown
- Mitigation risk-reduction

Run it yourself:

```bash
python scripts/run_benchmark.py 1000
```

Sample output from an actual run on 1,000 synthetic records (your numbers
will vary slightly — a new random dataset is generated each run):

```
Direct identifiers    precision=1.0 recall=1.0 f1=1.0
Quasi-identifiers     precision=1.0 recall=1.0 f1=1.0
Sensitive attributes  precision=1.0 recall=1.0 f1=1.0

Minimum class size: 1
Matches found (>= threshold): 1181 / 160000 candidate pairs tested

Risk before: 91.25 (CRITICAL)
Risk after:  43.33 (MODERATE)
Risk reduction: 47.92 points
```

Detection scores are 1.0 on the bundled synthetic generator because its
column names are unambiguous (e.g. `PatientID`, `Diagnosis`); this is a
benchmark of the pipeline's correctness, not a claim about performance on
arbitrary real-world column naming — see Limitations.

## Security

- No real personal data is required — synthetic demo data is generated
  by default
- File uploads are capped at 10MB (`MAX_UPLOAD_BYTES` in `.env`)
- SQLite stores only metadata and structured analysis results, never raw
  record content
- The audit log records actions (upload, analyze, attack, mitigate,
  retest) with counts, never raw values
- No API keys are committed to source; `.env.example` files document what
  is required
- LLM usage is optional and, when enabled, receives only aggregated
  structured findings (risk scores, counts) — never the raw dataset
- CORS is restricted to configured origins (`CORS_ORIGINS`)
- Path traversal and SQL-injection-style dataset IDs tested live and
  confirmed non-exploitable — dataset lookups always go through SQLite
  with parameterized queries, never build a filesystem path from user
  input
- `npm audit` flags 4 known vulnerabilities in frontend dependencies
  (an esbuild dev-server issue and two react-router issues). Investigated
  rather than just reported: the esbuild issue only affects `npm run
  dev` (the production Docker image never runs the dev server), the SSR
  issue doesn't apply (this app has no real SSR in production), and the
  open-redirect issue requires a user-controlled navigation target,
  which doesn't occur anywhere in this codebase — every `navigate()`/
  `<Link>` call uses a hardcoded route string. See AUDIT.md for the full
  investigation. Recommended before any future work that adds dynamic
  navigation: upgrade `react-router-dom` to 7.18.2+.

## Responsible AI

PrivaLens provides a **technical privacy-risk assessment** under the
configured attack scenarios. It does not guarantee a dataset is
impossible to re-identify, and it does not constitute legal certification
of anonymization. The UI and reports use language like "no significant
re-identification risk detected under the configured attack scenarios,"
never "100% anonymous."

## Limitations

- The linkage attack is a bounded brute-force comparison (capped at the
  first 400 rows of each dataset) for interactive responsiveness; larger
  datasets will only have their first 400 rows compared. This is a
  genuine scalability limit, not a hidden shortcut — it's documented here
  and in the code.
- Column classification is rule-based (name-pattern matching + a
  statistical fallback), not a trained semantic model. It will miss
  quasi-identifiers with unconventional column names and can misclassify
  columns with high cardinality that aren't actually identifying.
- Numeric-looking code columns (postal codes, phone numbers) are scored
  as exact-match categorical values rather than by numeric distance, via
  a small set of name patterns (`pincode`, `zip`, `postal`, `phone`,
  `mobile`). A code-like column with an unrecognized name (e.g. a
  postal code called `Sector`) would still be scored by numeric
  distance, which is the same class of bug this patches for the common
  cases — see AUDIT.md for the specific bug this fixed.
- The privacy/utility optimizer scores each mitigation independently,
  not combinations of mitigations together — it's an explainable
  heuristic, not a full combinatorial search.
- l-diversity is computed for only the first detected sensitive
  attribute, not all of them.
- No authentication/authorization layer exists — this is a hackathon
  prototype meant to run locally or in a trusted environment, not a
  multi-tenant production deployment.
- The LLM explanation layer, when enabled, depends on external API
  availability; it always falls back to a deterministic template so the
  feature degrades gracefully rather than failing.

## DataRescue

DataRescue is an autonomous agent layer built on top of the core
PrivaLens engines. It runs the full lifecycle — inspect, detect, plan,
act, attack, verify — as a background job you can start, walk away from,
and come back to.

### Try it: Judge Mode

```
POST /api/rescue/judge-mode/prepare   -> {n: 300}
POST /api/rescue/start                -> {dataset_id, aux_dataset_id}
```

This generates a synthetic healthcare dataset with **genuinely injected**
data-quality problems (duplicate rows, missing values, mixed casing,
stray whitespace, malformed date formats) on top of the existing privacy
vulnerabilities, then immediately starts a rescue job against it. In the
UI: sidebar → **DataRescue** → **Judge Mode: Launch Demo Rescue**.

### What the agent actually does

```
INSPECT   -> loads the dataset, logs row/column counts
DETECT    -> Quality Agent + Privacy Agent + ML Readiness Agent run in
             parallel-in-spirit (sequentially in this build), each
             deterministic, each producing real findings
PLAN      -> proposed actions are built from those findings and
             classified AUTO / REVIEW by a fixed policy table
             (app/config.py::RESCUE_POLICY) — an LLM never overrides
             this table, because none is used in the decision path at all
ACT       -> AUTO actions apply immediately; REVIEW actions pause the
             job (status: awaiting_approval) and wait on a real
             asyncio.Event until POST .../approve or .../reject is called
ATTACK    -> the same linkage attack engine used elsewhere in PrivaLens
             re-runs against the rescued data
VERIFY    -> before/after Data Health is compared; if the plan made
             things worse overall, the agent rolls back to the original
             dataset rather than reporting a fabricated improvement
ADAPT     -> rejecting an action can trigger a documented milder
             alternative (currently: pincode truncation only) which is
             queued as a new approval request
FINALIZE  -> the rescued dataset is saved as a NEW dataset version
             (parent_id points at the original); the original is never
             modified
```

### API

```
POST /api/rescue/judge-mode/prepare   {n}
POST /api/rescue/start                {dataset_id, aux_dataset_id?, target_column?, objective?}
GET  /api/rescue/jobs
GET  /api/rescue/{job_id}
GET  /api/rescue/{job_id}/events
GET  /api/rescue/{job_id}/report      (?format=json|markdown)
POST /api/rescue/{job_id}/approve     {action_id}
POST /api/rescue/{job_id}/reject      {action_id}
GET  /api/datasets/{dataset_id}/download   (CSV — works for any dataset,
                                             including a rescued one)
```

### Scoring

- **Quality score**, **ML Readiness score** (0-100, higher is better):
  weighted penalty formulas in `app/scoring/quality_engine.py`, same
  transparent pattern as the core risk score.
- **Data Health** (0-100): the mean of Quality, `100 - privacy risk`,
  and ML Readiness.
- **Rescue Score** (0-100): how much of the *achievable* Data Health
  improvement was actually captured — 0 if the plan didn't help, never
  fabricated. See `test_rescue_score_clamps_to_zero_when_things_get_worse`.

### What's real vs. scoped down

This is a genuine, tested implementation of the core agent loop — not
all 40 sections of a much larger spec. Watch Mode / continuous
monitoring, a natural-language command interpreter, true distributed
background execution (there's no external job queue — background
execution here means the job keeps running in the same server process
after the HTTP request returns, which does not survive a server
restart), and dataset drift detection are **not implemented**. Every
scoped-down item, and the one real bug found and fixed while building
this (a `numpy.bool_` JSON-serialization crash), is documented in detail
in [AUDIT_RESCUE.md](AUDIT_RESCUE.md) — read that before presenting this
feature to anyone who will ask hard questions about it.

## Testing

```bash
cd backend
pytest tests/ -v
```

48 tests: the original 20 covering k-anonymity/uniqueness/l-diversity,
linkage attack, risk scoring, and mitigation (including regression tests
for two real bugs found during audit — see AUDIT.md); 18 covering the
new Quality Agent and ML Readiness Agent detectors; and 6 integration
tests for the DataRescue orchestrator that exercise the real async
approval loop end-to-end — including a regression test for a real
`numpy.bool_` JSON-serialization bug found during live testing (see
AUDIT_RESCUE.md).

The frontend has a server-side render smoke test that renders all 10 pages
plus the sidebar, in both empty and populated states, using Vite's own
module loader (the app's real JSX/ESM pipeline) — this catches component
crashes and React warnings that a plain `npm run build` won't:

```bash
cd frontend
npm run test:ssr
```

## License

See [LICENSE](LICENSE).
