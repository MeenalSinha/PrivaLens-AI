"""
Transparent rule-based classifier for direct identifiers, quasi-identifiers
and sensitive attributes.

This is deliberately NOT a black box: every classification carries a
confidence score and a human-readable reason built from explicit rules
(column name matching + statistical signal from the profiler). Per the
spec, the system must never claim it perfectly understands semantic
meaning - confidence is capped and reasons are always shown.
"""
import re

DIRECT_IDENTIFIER_PATTERNS = [
    r"\bname\b", r"\bfull[_ ]?name\b", r"\bemail\b", r"\bphone\b", r"\bmobile\b",
    r"\bssn\b", r"\bsocial[_ ]?security\b", r"\baadhaar\b", r"\baadhar\b",
    r"\bpatient[_ ]?id\b", r"\baccount[_ ]?id\b", r"\bnational[_ ]?id\b",
    r"\bpassport\b", r"\bcustomer[_ ]?id\b", r"\buser[_ ]?id\b", r"\bmrn\b",
    r"\bcredit[_ ]?card\b", r"\baddress\b",
]

QUASI_IDENTIFIER_PATTERNS = [
    r"\bage\b", r"\bgender\b", r"\bsex\b", r"\bpincode\b", r"\bzip\b",
    r"\bpostal\b", r"\boccupation\b", r"\bjob\b", r"\bprofession\b",
    r"\blocation\b", r"\bcity\b", r"\bregion\b", r"\bstate\b", r"\bdate\b",
    r"\beducation\b", r"\binstitution\b", r"\bschool\b", r"\buniversity\b",
    r"\bcourse\b", r"\bemployer\b", r"\bmarital\b", r"\bethnicity\b",
    r"\bnationality\b", r"\bdob\b", r"\bbirth\b",
]

SENSITIVE_ATTRIBUTE_PATTERNS = [
    r"\bdisease\b", r"\bdiagnosis\b", r"\bsalary\b", r"\bincome\b",
    r"\bfinancial\b", r"\bcredit[_ ]?score\b", r"\bpolitical\b",
    r"\breligion\b", r"\breligious\b", r"\bhiv\b", r"\bmental[_ ]?health\b",
    r"\bcondition\b", r"\btreatment\b", r"\bmedication\b", r"\bsexual\b",
    r"\bcriminal\b", r"\barrest\b", r"\bconviction\b",
]


def _normalize_column_name(name: str) -> str:
    """Splits camelCase / PascalCase / snake_case column names into space
    separated words so pattern matching works on names like 'AdmissionDate'
    or 'patient_id', not just literally-spaced names."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)  # camelCase boundary
    s = re.sub(r"[_\-]+", " ", s)
    return s.strip()


def _match_any(patterns, name: str):
    normalized = _normalize_column_name(name)
    for p in patterns:
        if re.search(p, normalized, flags=re.IGNORECASE):
            return p
    return None


def classify_columns(profile: dict) -> dict:
    """
    Returns per-column classification with confidence + reason, built from:
      1. Column-name pattern matching (primary signal)
      2. Cardinality / uniqueness ratio from the profiler (secondary signal)
    """
    results = []
    direct, quasi, sensitive, unclassified = [], [], [], []

    for col in profile["columns"]:
        name = col["name"]
        cardinality = col["cardinality_ratio"]
        inferred_type = col["inferred_type"]

        matched_direct = _match_any(DIRECT_IDENTIFIER_PATTERNS, name)
        matched_quasi = _match_any(QUASI_IDENTIFIER_PATTERNS, name)
        matched_sensitive = _match_any(SENSITIVE_ATTRIBUTE_PATTERNS, name)

        category = "unclassified"
        confidence = 0.35
        reasons = []

        if matched_direct:
            category = "direct_identifier"
            confidence = 0.90
            reasons.append(f"Column name matches direct-identifier pattern '{matched_direct}'")
            if cardinality > 0.85:
                confidence = min(0.98, confidence + 0.05)
                reasons.append("Very high uniqueness ratio confirms identifying nature")
        elif matched_sensitive:
            category = "sensitive_attribute"
            confidence = 0.85
            reasons.append(f"Column name matches sensitive-attribute pattern '{matched_sensitive}'")
        elif matched_quasi:
            category = "quasi_identifier"
            confidence = 0.80
            reasons.append(f"Column name matches quasi-identifier pattern '{matched_quasi}'")
        else:
            # Fall back to statistical signal only - lower confidence, always disclosed.
            if cardinality > 0.9 and inferred_type in ("text", "numeric"):
                category = "possible_direct_identifier"
                confidence = 0.55
                reasons.append("No name match, but near-unique values suggest an identifier")
            elif inferred_type == "categorical" and 0.001 < cardinality < 0.5:
                category = "possible_quasi_identifier"
                confidence = 0.45
                reasons.append("Categorical column with moderate cardinality; may combine with others to identify individuals")
            else:
                reasons.append("No strong signal found; classify manually if needed")

        entry = {
            "column": name,
            "category": category,
            "confidence": confidence,
            "reasons": reasons,
        }
        results.append(entry)

        if category in ("direct_identifier", "possible_direct_identifier"):
            direct.append(name)
        elif category in ("quasi_identifier", "possible_quasi_identifier"):
            quasi.append(name)
        elif category == "sensitive_attribute":
            sensitive.append(name)
        else:
            unclassified.append(name)

    return {
        "columns": results,
        "direct_identifiers": direct,
        "quasi_identifiers": quasi,
        "sensitive_attributes": sensitive,
        "unclassified": unclassified,
    }
