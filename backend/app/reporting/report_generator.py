"""
Privacy report generator. Assembles a structured, JSON-serializable report
from the results of previously-run analyses (profile, classification,
attack, risk, mitigation, retest). Also renders a plain-text / Markdown
version suitable for download.

If LLM explanation is enabled (app.config.LLM_ENABLED), the LLM is used
ONLY to phrase the structured findings in readable prose - it never
computes or alters the underlying numbers, per the architecture
requirement: Dataset -> Deterministic Analysis -> Risk Engine ->
Structured Findings -> LLM -> Human-readable Explanation.
"""
from datetime import datetime


DISCLAIMER = (
    "PrivaLens provides a technical privacy-risk assessment and does not "
    "guarantee that a dataset is impossible to re-identify. This report "
    "reflects analysis under the configured attack scenarios only and does "
    "not constitute legal certification of anonymization."
)


def build_report(dataset_name: str, profile: dict, classification: dict,
                  k_anon: dict, uniqueness: dict, linkage: dict, risk: dict,
                  mitigations: list = None, after: dict = None) -> dict:
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_name": dataset_name,
        "executive_summary": {
            "rows": profile["row_count"],
            "columns": profile["column_count"],
            "overall_risk_score": risk["overall_score"],
            "overall_risk_level": risk["risk_level"],
        },
        "findings": {
            "direct_identifiers": classification["direct_identifiers"],
            "quasi_identifiers": classification["quasi_identifiers"],
            "sensitive_attributes": classification["sensitive_attributes"],
            "min_equivalence_class_size": k_anon.get("min_class_size"),
            "unique_records_pct": uniqueness.get("unique_pct"),
        },
        "attack_summary": {
            "shared_columns": linkage.get("shared_columns"),
            "candidates_tested": linkage.get("candidates_tested"),
            "matches_found": linkage.get("matches_found"),
            "highest_confidence": linkage.get("highest_confidence"),
        },
        "risk_breakdown": risk["components"],
        "recommendations": mitigations or [],
        "disclaimer": DISCLAIMER,
    }

    if after:
        report["before_after"] = {
            "before": {
                "risk_score": risk["overall_score"],
                "risk_level": risk["risk_level"],
                "at_risk_records": risk["at_risk_records"],
                "min_class_size": k_anon.get("min_class_size"),
            },
            "after": after,
        }

    return report


def render_markdown(report: dict) -> str:
    lines = []
    lines.append(f"# PrivaLens DataRescue - Privacy Risk Assessment Report\n")
    lines.append(f"**Dataset:** {report['dataset_name']}  ")
    lines.append(f"**Generated:** {report['generated_at']}\n")

    lines.append("## Executive Summary\n")
    es = report["executive_summary"]
    lines.append(f"- Rows: {es['rows']}")
    lines.append(f"- Columns: {es['columns']}")
    lines.append(f"- Overall Risk: **{es['overall_risk_level']}** ({es['overall_risk_score']}/100)\n")

    lines.append("## Findings\n")
    f = report["findings"]
    lines.append(f"- Direct identifiers: {', '.join(f['direct_identifiers']) or 'none detected'}")
    lines.append(f"- Quasi-identifiers: {', '.join(f['quasi_identifiers']) or 'none detected'}")
    lines.append(f"- Sensitive attributes: {', '.join(f['sensitive_attributes']) or 'none detected'}")
    lines.append(f"- Minimum equivalence class size: {f['min_equivalence_class_size']}")
    lines.append(f"- Records unique on quasi-identifiers: {f['unique_records_pct']}%\n")

    lines.append("## Attack Summary\n")
    a = report["attack_summary"]
    lines.append(f"- Shared columns tested: {', '.join(a['shared_columns']) or 'none'}")
    lines.append(f"- Candidate pairs tested: {a['candidates_tested']}")
    lines.append(f"- Matches found (>= threshold): {a['matches_found']}")
    lines.append(f"- Highest linkage confidence: {a['highest_confidence']}\n")

    lines.append("## Risk Breakdown\n")
    for k, v in report["risk_breakdown"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")
    lines.append("")

    if report.get("recommendations"):
        lines.append("## Recommendations\n")
        for r in report["recommendations"]:
            lines.append(f"- **{r['column']}** -> {r['action']}: {r['description']}")
            lines.append(f"  - Reason: {r['reason']}")
        lines.append("")

    if "before_after" in report:
        lines.append("## Before / After Comparison\n")
        b, a2 = report["before_after"]["before"], report["before_after"]["after"]
        lines.append("| Metric | Before | After |")
        lines.append("|---|---|---|")
        lines.append(f"| Risk Level | {b['risk_level']} | {a2['risk_level']} |")
        lines.append(f"| Risk Score | {b['risk_score']} | {a2['risk_score']} |")
        lines.append(f"| At-risk Records | {b['at_risk_records']} | {a2['at_risk_records']} |")
        lines.append(f"| Min Equivalence Class Size | {b['min_class_size']} | {a2['min_class_size']} |\n")

    lines.append("## Disclaimer\n")
    lines.append(report["disclaimer"])

    return "\n".join(lines)
