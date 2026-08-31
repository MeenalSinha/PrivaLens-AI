# Architecture

## Data flow

```
1. Upload
   CSV/Parquet -> pandas.DataFrame -> saved as Parquet under
   backend/data/uploads/{dataset_id}.parquet
   Metadata (name, row/col count, path) saved to SQLite `datasets` table.

2. Profile
   profiler.py computes per-column stats directly from the dataframe:
   missing %, unique count, cardinality ratio, inferred semantic type.

3. Classify
   identifier_detection.py takes the profile and classifies each column
   into direct_identifier / quasi_identifier / sensitive_attribute /
   unclassified, using column-name pattern matching (primary signal) and
   cardinality (secondary, lower-confidence signal). Every classification
   carries a confidence score and human-readable reasons.

4. Privacy engine
   k_anonymity.py groups the dataframe by the detected quasi-identifier
   columns to compute real equivalence classes, uniqueness percentages,
   and k-anonymity violations at configurable k thresholds (2, 3, 5, 10).

5. Attack
   linkage.py compares every row of the target dataset against every row
   of an auxiliary dataset on shared columns, using per-column-type
   similarity functions (exact categorical match, normalized numeric
   distance, fuzzy string ratio, date proximity), combined via
   configurable weights into a single match_probability per candidate
   pair. Pairs above LINKAGE_MATCH_THRESHOLD are returned as matches.

6. Risk scoring
   risk_engine.py combines linkage confidence, uniqueness, equivalence-
   class risk (at k=5), and sensitive-attribute exposure into one 0-100
   score using configurable weights (RISK_WEIGHTS in config.py), then
   maps it to LOW/MODERATE/HIGH/CRITICAL bands.

7. Mitigation
   transforms.py recommends mitigations by inspecting real column stats
   (not templates keyed only on column name), then actually applies them
   (age bucketing, pincode truncation, date generalization, suppression)
   to produce a transformed dataframe. optimizer.py independently scores
   each candidate mitigation by risk-reduction vs utility-loss.

8. Re-test
   pipeline.py::fix_and_retest re-runs the ENTIRE pipeline (steps 3-6) on
   the transformed dataframe against the same auxiliary dataset, and the
   API layer diffs the before/after risk scores.

9. Report
   report_generator.py assembles all of the above into one structured
   JSON object, rendered to Markdown for download. If an LLM key is
   configured, llm_explain.py asks the LLM to phrase the ALREADY-COMPUTED
   structured findings in prose — the LLM never sees the raw dataset and
   never computes a risk number itself.
```

## Why the LLM is optional and sits at the end

The architecture deliberately keeps risk computation entirely
deterministic. An LLM hallucinating a risk score would be a security
liability in a privacy tool. The only LLM touchpoint (`llm_explain.py`)
receives a small JSON object of already-computed numbers and is asked to
paraphrase them — never to calculate anything. Without an API key, a
template-based fallback produces the same structure, so every feature
still works end-to-end with zero external dependencies.

## Why dataframes aren't in SQLite

Storing raw record content in a queryable database would work against
the product's own privacy-by-design principle. Parquet files on disk
(under `backend/data/`) hold the actual data; SQLite holds only metadata,
JSON-serialized *aggregate* analysis results, and an audit trail of
actions taken — never individual record values.

## Frontend state model

`DatasetContext.jsx` holds the current main/auxiliary/mitigated dataset
IDs plus the latest analysis/attack/mitigation/comparison results in
React state, shared across all 10 pages via context. There is no backend
session concept — the frontend simply calls the stateless REST API and
keeps the results client-side for the duration of the browser session.
