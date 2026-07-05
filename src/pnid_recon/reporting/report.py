"""Render ConflictReport artifacts for API and file output."""

from __future__ import annotations

import json

from pnid_recon.schemas.conflicts import ConflictReport, Severity


def report_to_json(report: ConflictReport) -> str:
    """Serialize a conflict report to pretty-printed JSON."""
    return json.dumps(report.model_dump(mode="json"), indent=2) + "\n"


def report_to_markdown(report: ConflictReport) -> str:
    """Render a human-readable Markdown conflict report."""
    lines = [
        "# Conflict Report",
        "",
        f"Generated at: {report.generated_at}",
        "",
        "## Summary",
        "",
    ]

    if report.summary:
        lines.append("| Metric | Count |")
        lines.append("| --- | ---: |")
        for key, value in sorted(report.summary.items()):
            lines.append(f"| {key} | {value} |")
    else:
        lines.append("_No conflicts detected._")

    lines.extend(["", "## Conflicts", ""])
    if not report.conflicts:
        lines.append("_No conflicts detected._")
    else:
        for index, conflict in enumerate(report.conflicts, start=1):
            lines.extend(
                [
                    f"### {index}. {conflict.tag} — {conflict.conflict_type.value}",
                    "",
                    f"- **Severity:** {conflict.severity.value}",
                    f"- **Sources:** {', '.join(conflict.sources)}",
                ]
            )
            if conflict.field:
                lines.append(f"- **Field:** {conflict.field}")
            if conflict.values:
                value_parts = [
                    f"{source}={value}" for source, value in conflict.values.items()
                ]
                lines.append(f"- **Values:** {', '.join(value_parts)}")
            if conflict.low_confidence_input:
                lines.append("- **Low-confidence input:** yes")
            lines.extend(["", conflict.message, ""])

    return "\n".join(lines).rstrip() + "\n"


def severity_rank(severity: Severity) -> int:
    """Order conflicts HIGH before MEDIUM before LOW."""
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    return order[severity]
