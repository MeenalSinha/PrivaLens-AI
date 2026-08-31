"""
Central configuration for PrivaLens DataRescue backend.

All tunable weights, thresholds and paths live here so the risk/scoring
logic documented in the README stays auditable in one place instead of
being scattered as magic numbers across the codebase.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the backend directory (one level up from this file's app/ dir)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
DEMO_DIR = DATA_DIR / "demo"
DB_PATH = DATA_DIR / "privalens.db"

for d in (DATA_DIR, UPLOAD_DIR, GENERATED_DIR, DEMO_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Max upload size in bytes (10 MB) - security requirement: file-size limits.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))

# ---------------------------------------------------------------------------
# Re-identification risk score weights (must sum to 1.0)
# Documented in README section "Risk Scoring Methodology".
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    "linkage_confidence": 0.40,
    "uniqueness": 0.30,
    "equivalence_class_risk": 0.20,
    "sensitive_attribute_exposure": 0.10,
}

RISK_BANDS = [
    (0, 25, "LOW"),
    (25, 50, "MODERATE"),
    (50, 75, "HIGH"),
    (75, 101, "CRITICAL"),
]

# ---------------------------------------------------------------------------
# Linkage attack scoring weights (must sum to 1.0). Configurable per README
# section 9 - "Make the weights configurable."
# ---------------------------------------------------------------------------
LINKAGE_WEIGHTS = {
    "categorical_exact": 0.30,   # exact categorical match (gender, occupation, region...)
    "numeric_closeness": 0.30,   # normalized numeric distance (age, income...)
    "string_similarity": 0.20,   # fuzzy string similarity on free text fields
    "date_closeness": 0.20,      # date proximity
}

# Minimum combined linkage score to be considered a "candidate match"
LINKAGE_MATCH_THRESHOLD = 0.55

# k-anonymity check points used across the UI
K_VALUES = [2, 3, 5, 10]

# LLM usage is optional; disabled unless ANTHROPIC_API_KEY is present.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_ENABLED = bool(ANTHROPIC_API_KEY)
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# ---------------------------------------------------------------------------
# DataRescue: Quality score weights (0-100, higher is better - the inverse
# convention of RISK_WEIGHTS above, documented explicitly so the two scores
# are never confused). Each component is a 0-100 "badness" measure that gets
# subtracted from 100, weighted by how much it matters to analytical use of
# the dataset. Must sum to 1.0.
# ---------------------------------------------------------------------------
QUALITY_WEIGHTS = {
    "missing_values": 0.30,
    "duplicate_rows": 0.25,
    "structural_issues": 0.25,   # malformed dates, inconsistent labels/case, whitespace
    "outliers": 0.20,
}

# ---------------------------------------------------------------------------
# DataRescue: ML-readiness score weights (0-100, higher is better).
# ---------------------------------------------------------------------------
ML_READINESS_WEIGHTS = {
    "constant_features": 0.20,
    "duplicate_observations": 0.20,
    "high_cardinality_features": 0.20,
    "sparsity": 0.20,
    "suspicious_correlation": 0.20,
}

# Pearson correlation above this between two numeric columns is flagged as
# a possible redundant-feature / leakage risk (ML readiness agent).
CORRELATION_LEAKAGE_THRESHOLD = 0.95

# ---------------------------------------------------------------------------
# DataRescue: autonomy policy. Every fix action type is classified AUTO
# (applied immediately, no approval), REVIEW (queued for human approval),
# or BLOCK (never auto-applied in this build - listed for completeness/
# transparency per spec section 27, surfaced in the UI, but nothing in the
# current fix catalog is actually classified BLOCK because every
# implemented transform is reversible given the preserved original
# dataset - see AUDIT_RESCUE.md for what a genuinely irreversible action
# would need before it could ever be AUTO).
# The agent follows this table even if an LLM-driven suggestion (none are
# used for fix selection in this build) proposed otherwise - policy is
# deterministic and cannot be overridden by model output.
# ---------------------------------------------------------------------------
RESCUE_POLICY = {
    "trim_whitespace": "AUTO",
    "standardize_case": "AUTO",
    "standardize_date_format": "AUTO",
    "drop_exact_duplicates": "AUTO",
    "impute_missing_median": "REVIEW",
    "impute_missing_mode": "REVIEW",
    "remove_outliers": "REVIEW",
    "generalization_bucketing": "REVIEW",
    "truncation_generalization": "REVIEW",
    "date_generalization": "REVIEW",
    "generalization": "REVIEW",
    "suppression": "REVIEW",
}

# Milder fallback offered when a human rejects a REVIEW action - a real,
# concrete instance of "the agent reconsiders alternatives" rather than a
# generic claim. Only pincode truncation has a documented milder variant
# in this build; other rejected actions are simply dropped from the plan
# and logged, not silently retried with invented alternatives.
RESCUE_ALTERNATIVES = {
    "truncation_generalization": {"keep_digits": 4},  # milder than the default 3
}
