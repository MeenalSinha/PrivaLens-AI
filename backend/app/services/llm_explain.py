"""
Optional LLM-grounded explanation service.

Only used to phrase already-computed structured findings into readable
prose. Disabled unless GEMINI_API_KEY is configured. Never sends the
raw dataset - only aggregated, non-identifying structured findings, per
the security requirement in the spec section 26.
"""
import json

from app.config import LLM_ENABLED, LLM_MODEL, GEMINI_API_KEY


def explain_findings(structured_findings: dict) -> str:
    if not LLM_ENABLED:
        return _fallback_explanation(structured_findings)

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            "You are summarizing a privacy risk assessment for a data analyst. "
            "Use ONLY the structured findings below - do not invent numbers. "
            "Write 3-5 concise sentences, plain language, no exaggeration.\n\n"
            f"Structured findings:\n{json.dumps(structured_findings, indent=2)}"
        )
        resp = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )
        return resp.text if resp.text else _fallback_explanation(structured_findings)
    except Exception:
        return _fallback_explanation(structured_findings)


def _fallback_explanation(f: dict) -> str:
    """Deterministic template-based explanation used when no LLM key is
    configured, so the feature still works end-to-end without external
    dependencies (LLM functionality is optional per spec)."""
    risk_level = f.get("risk_level", "UNKNOWN")
    score = f.get("overall_score", "N/A")
    at_risk = f.get("at_risk_records", "N/A")
    min_class = f.get("min_class_size", "N/A")
    return (
        f"This dataset was assessed as {risk_level} risk with an overall "
        f"re-identification risk score of {score}/100. Approximately "
        f"{at_risk} records fall into small equivalence classes "
        f"(minimum observed class size: {min_class}), meaning an attacker "
        f"with access to an auxiliary dataset sharing similar quasi-identifiers "
        f"could plausibly narrow these records down to a small group of "
        f"candidates or a single individual. Review the recommended "
        f"mitigations to reduce this risk before publishing or sharing the data."
    )
