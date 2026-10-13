"""Output formats: table, JSON, Markdown (job summary) and SARIF 2.1.0."""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from .rules import HIGH, LOW, MEDIUM, RULES, SEVERITY_RANK, at_or_above
from .scanner import Finding, ScanResult

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFO_URI = "https://github.com/basitalisandhu/skill-scan-gate"
SARIF_LEVEL = {HIGH: "error", MEDIUM: "warning", LOW: "note"}
# GitHub code scanning reads security-severity as a CVSS-style score and buckets it:
# 7.0 to 8.9 is shown as high, 4.0 to 6.9 as medium, 0.1 to 3.9 as low.
SECURITY_SEVERITY = {HIGH: "8.0", MEDIUM: "5.0", LOW: "2.0"}
MARKDOWN_ROW_LIMIT = 100


def gate(result: ScanResult, fail_on: str) -> str:
    return "fail" if any(at_or_above(f.severity, fail_on) for f in result.findings) else "pass"


def summary_line(result: ScanResult, fail_on: str) -> str:
    c = result.counts()
    parts = [
        f"{len(result.findings)} finding(s): {c[HIGH]} high, {c[MEDIUM]} medium, {c[LOW]} low",
    ]
    if result.suppressed_baseline or result.suppressed_allow:
        parts.append(
            f"suppressed {len(result.suppressed_baseline)} by baseline, {len(result.suppressed_allow)} by allowlist"
        )
    parts.append(f"gate {gate(result, fail_on)} (fail-on {fail_on})")
    return "; ".join(parts) + "."


# ---------------------------------------------------------------- table


def render_table(result: ScanResult, fail_on: str) -> str:
    out = [f"skill-scan-gate {__version__}: scanned {len(result.files)} file(s) under {result.root}", ""]
    if result.findings:
        loc = [f"{f.file}:{f.line}" for f in result.findings]
        w_loc = max(len("LOCATION"), *(len(x) for x in loc))
        out.append(f"{'SEVERITY':<9} {'RULE':<7} {'LOCATION':<{w_loc}} TITLE")
        out.append("-" * (9 + 1 + 7 + 1 + w_loc + 1 + 40))
        for f, where in zip(result.findings, loc, strict=True):
            out.append(f"{f.severity:<9} {f.rule:<7} {where:<{w_loc}} {f.title}")
            out.append(f"{'':<18}evidence: {f.evidence}")
            out.append(f"{'':<18}fix: {f.remediation}")
        out.append("")
    else:
        out.append("No findings.")
        out.append("")
    for w in result.warnings:
        out.append(f"warning: {w}")
    for e in result.errors:
        out.append(f"error: {e}")
    out.append(summary_line(result, fail_on))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- JSON


def to_json(result: ScanResult, fail_on: str) -> dict[str, Any]:
    c = result.counts()
    return {
        "tool": "skill-scan-gate",
        "version": __version__,
        "root": str(result.root),
        "filesScanned": len(result.files),
        "failOn": fail_on,
        "gate": gate(result, fail_on),
        "blobMin": result.blob_min,
        "summary": {
            "total": len(result.findings),
            **c,
            "maxSeverity": result.max_severity(),
            "suppressedByBaseline": len(result.suppressed_baseline),
            "suppressedByAllowlist": len(result.suppressed_allow),
        },
        "findings": [f.to_dict() for f in result.findings],
        "warnings": result.warnings,
        "errors": result.errors,
    }


def render_json(result: ScanResult, fail_on: str) -> str:
    return json.dumps(to_json(result, fail_on), indent=2) + "\n"


# ---------------------------------------------------------------- Markdown


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("`", "'").replace("<", "&lt;").replace("\r", " ").replace("\n", " ")


def render_markdown(result: ScanResult, fail_on: str) -> str:
    g = gate(result, fail_on)
    c = result.counts()
    out = [
        f"### skill-scan-gate: {'failed' if g == 'fail' else 'passed'}",
        "",
        f"Scanned {len(result.files)} file(s). Threshold: `{fail_on}`.",
        "",
        "| High | Medium | Low | Suppressed (baseline) | Suppressed (allowlist) |",
        "|---:|---:|---:|---:|---:|",
        f"| {c[HIGH]} | {c[MEDIUM]} | {c[LOW]} | {len(result.suppressed_baseline)} | {len(result.suppressed_allow)} |",
        "",
    ]
    if result.findings:
        out += ["| Severity | Rule | Location | Finding | Fix |", "|---|---|---|---|---|"]
        for f in result.findings[:MARKDOWN_ROW_LIMIT]:
            out.append(
                f"| {f.severity} | [{f.rule}]({RULES[f.rule].anchor}) | `{_md(f.file)}:{f.line}` "
                f"| {_md(f.title)} | {_md(f.remediation)} |"
            )
        if len(result.findings) > MARKDOWN_ROW_LIMIT:
            out.append("")
            out.append(f"{len(result.findings) - MARKDOWN_ROW_LIMIT} more finding(s) in the SARIF and JSON output.")
        out.append("")
    for w in result.warnings:
        out.append(f"- warning: {_md(w)}")
    for e in result.errors:
        out.append(f"- error: {_md(e)}")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- SARIF


def _sarif_rule(rule_id: str) -> dict[str, Any]:
    r = RULES[rule_id]
    return {
        "id": r.id,
        "name": "".join(w.capitalize() for w in r.title.replace("-", " ").split()[:8]),
        "shortDescription": {"text": r.title},
        "fullDescription": {"text": f"{r.title}. {r.remediation}"},
        "help": {
            "text": r.remediation,
            "markdown": f"**{r.title}** ({r.severity})\n\n{r.remediation}\n\n[Rule reference]({r.anchor})",
        },
        "helpUri": r.anchor,
        "defaultConfiguration": {"level": SARIF_LEVEL[r.severity]},
        "properties": {
            "tags": ["security", r.family],
            "security-severity": SECURITY_SEVERITY[r.severity],
            "precision": "medium",
        },
    }


def to_sarif(result: ScanResult, uri_prefix: str = "") -> dict[str, Any]:
    """SARIF 2.1.0. ``uri_prefix`` makes paths relative to the repository root when the
    scanned directory is a subdirectory of it (code scanning resolves URIs from the root)."""
    rule_ids = sorted(RULES)
    index = {rid: i for i, rid in enumerate(rule_ids)}
    prefix = uri_prefix.strip("/")
    results = []
    for f in result.findings:
        uri = f"{prefix}/{f.file}" if prefix else f.file
        results.append(
            {
                "ruleId": f.rule,
                "ruleIndex": index[f.rule],
                "level": SARIF_LEVEL[f.severity],
                "message": {"text": f"{f.title}: {f.evidence}. {f.remediation}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri, "uriBaseId": "%SRCROOT%"},
                            "region": {"startLine": max(1, f.line)},
                        }
                    }
                ],
                "partialFingerprints": {"skillScanGate/v1": f.fingerprint},
            }
        )
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skill-scan-gate",
                        "version": __version__,
                        "semanticVersion": __version__,
                        "informationUri": INFO_URI,
                        "rules": [_sarif_rule(rid) for rid in rule_ids],
                    }
                },
                "results": results,
            }
        ],
    }


def render_sarif(result: ScanResult, uri_prefix: str = "") -> str:
    return json.dumps(to_sarif(result, uri_prefix), indent=2) + "\n"


def by_rule(findings: list[Finding]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in findings:
        out[f.rule] = out.get(f.rule, 0) + 1
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- pull request comment

COMMENT_MARKER_PREFIX = "<!-- skill-scan-gate:comment"
COMMENT_TOP = 10


def comment_marker(name: str = "skill-scan-gate") -> str:
    """Hidden HTML marker that identifies the sticky comment; one per name (the Action passes its category)."""
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_.") or "skill-scan-gate"
    return f"{COMMENT_MARKER_PREFIX} {safe} -->"


def top_findings(findings: list[Finding], limit: int = COMMENT_TOP) -> list[Finding]:
    """Highest severity first, then by file and line, so the comment shows what matters most."""
    return sorted(findings, key=lambda f: (-SEVERITY_RANK[f.severity], f.file, f.line, f.rule))[:limit]


def render_comment(
    result: ScanResult,
    fail_on: str,
    *,
    marker: str = "skill-scan-gate",
    sarif_url: str = "",
    run_url: str = "",
    scanned: str = "",
) -> str:
    """Markdown body for the sticky pull request comment.

    Evidence is deliberately left out: the comment shows rule, location, title and fix only, so no
    matched text (redacted or not) reaches a pull request thread. Every value is escaped for tables.
    """
    g = gate(result, fail_on)
    c = result.counts()
    suppressed = len(result.suppressed_baseline) + len(result.suppressed_allow)
    where = f" under `{_md(scanned)}`" if scanned else ""
    head = "failed" if g == "fail" else "passed"
    out = [
        comment_marker(marker),
        f"### skill-scan-gate: gate {head}",
        "",
        f"{len(result.findings)} finding(s) in {len(result.files)} scanned file(s){where}. Threshold: `{fail_on}`.",
        "",
        "| High | Medium | Low | Suppressed | Gate |",
        "|---:|---:|---:|---:|:---:|",
        f"| {c[HIGH]} | {c[MEDIUM]} | {c[LOW]} | {suppressed} | {g} |",
        "",
    ]
    top = top_findings(result.findings)
    if top:
        label = f"Top {len(top)} of {len(result.findings)}" if len(result.findings) > len(top) else "Findings"
        out += [f"**{label}** (highest severity first):", ""]
        out += ["| Severity | Rule | Location | Finding | Fix |", "|---|---|---|---|---|"]
        for f in top:
            out.append(
                f"| {f.severity} | [{f.rule}]({RULES[f.rule].anchor}) | `{_md(f.file)}:{f.line}` "
                f"| {_md(f.title)} | {_md(f.remediation)} |"
            )
        out.append("")
    links = []
    if sarif_url:
        links.append(f"[full SARIF results in code scanning]({sarif_url})")
    if run_url:
        links.append(f"[job summary]({run_url})")
    if links:
        out += ["See the " + " and the ".join(links) + ".", ""]
    if result.errors:
        out += [f"{len(result.errors)} file(s) could not be read; see the job log.", ""]
    out.append(
        f"<sub>skill-scan-gate {__version__}. Matched text is not shown here; this comment is updated in place.</sub>"
    )
    return "\n".join(out) + "\n"
