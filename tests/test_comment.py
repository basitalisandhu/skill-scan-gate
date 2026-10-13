"""The pull request comment body: counts, gate, top findings, links, marker and no evidence."""

import re

from skill_scan_gate.cli import main
from skill_scan_gate.report import COMMENT_TOP, comment_marker, render_comment, top_findings
from skill_scan_gate.rules import SEVERITY_RANK
from skill_scan_gate.scanner import Finding, ScanResult, scan

from conftest import CLEAN, PLANTED
from make_secret_fixture import build, tokens

ROW = re.compile(r"^\| (high|medium|low) \| \[(SSG\d{3})\]\([^)]+\) \| `([^`]+):(\d+)` \| [^|]+ \| .+ \|$")


def _rows(body: str) -> list[re.Match]:
    return [m for line in body.splitlines() if (m := ROW.match(line))]


def test_marker_is_first_line_and_sanitised():
    body = render_comment(scan(CLEAN), "high", marker="my cat<egory>")
    assert body.splitlines()[0] == comment_marker("my cat<egory>") == "<!-- skill-scan-gate:comment mycategory -->"
    assert comment_marker("") == "<!-- skill-scan-gate:comment skill-scan-gate -->"


def test_planted_body_has_counts_gate_and_top_ten():
    result = scan(PLANTED)
    c = result.counts()
    body = render_comment(result, "high", scanned="tests/fixtures/fixture-planted")
    assert "### skill-scan-gate: gate failed" in body
    assert f"{len(result.findings)} finding(s) in {len(result.files)} scanned file(s)" in body
    assert "under `tests/fixtures/fixture-planted`" in body
    assert f"| {c['high']} | {c['medium']} | {c['low']} | 0 | fail |" in body
    rows = _rows(body)
    assert len(rows) == COMMENT_TOP < len(result.findings)
    assert f"**Top {COMMENT_TOP} of {len(result.findings)}**" in body
    ranks = [SEVERITY_RANK[m.group(1)] for m in rows]
    assert ranks == sorted(ranks, reverse=True)
    assert all(m.group(1) == "high" for m in rows)  # the planted fixture has more than 10 high findings
    for m in rows:
        assert (PLANTED / m.group(3)).is_file()


def test_clean_body_passes_without_table():
    body = render_comment(scan(CLEAN), "low")
    assert "gate passed" in body and "| 0 | 0 | 0 | 0 | pass |" in body
    assert _rows(body) == [] and "Top " not in body


def test_links_only_when_given():
    result = scan(CLEAN)
    assert "code scanning" not in render_comment(result, "high")
    body = render_comment(result, "high", sarif_url="https://x/security/code-scanning?q", run_url="https://x/runs/1")
    assert "[full SARIF results in code scanning](https://x/security/code-scanning?q)" in body
    assert "[job summary](https://x/runs/1)" in body


def test_top_findings_order_and_limit():
    fs = [
        Finding("SSG602", "b.json", 1, "", "1"),  # low
        Finding("SSG203", "a.md", 9, "", "2"),  # medium
        Finding("SSG101", "z.md", 3, "", "3"),  # high
        Finding("SSG101", "a.md", 7, "", "4"),  # high
    ]
    assert [(f.rule, f.file) for f in top_findings(fs)] == [
        ("SSG101", "a.md"),
        ("SSG101", "z.md"),
        ("SSG203", "a.md"),
        ("SSG602", "b.json"),
    ]
    assert len(top_findings(fs * 5, limit=10)) == 10


def test_table_cells_are_escaped(tmp_path):
    f = Finding("SSG101", "skills/a|b`c<d>\ne/SKILL.md", 2, "ignore", "x")
    body = render_comment(ScanResult(root=tmp_path, findings=[f], files=["x"]), "high")
    row = next(line for line in body.splitlines() if line.startswith("| high |"))
    assert "a\\|b'c&lt;d> e/SKILL.md:2" in row
    assert len(_rows(body)) == 1


def test_no_evidence_or_secret_values(tmp_path):
    repo = tmp_path / "secrets"
    build(repo)
    result = scan(repo, blob_min=120)
    assert result.findings
    body = render_comment(result, "high")
    for label, value in tokens().items():
        assert value not in body, label
    for f in result.findings:
        if f.evidence:
            assert f.evidence not in body
    assert "redacted" not in body and "not-a-key" not in body


def test_cli_writes_comment_file(tmp_path, capsys):
    out = tmp_path / "comment.md"
    code = main(
        [
            "scan",
            str(PLANTED),
            "--comment",
            str(out),
            "--comment-marker",
            "ci",
            "--comment-run-url",
            "https://example.test/runs/7",
        ]
    )
    assert code == 1
    body = out.read_text()
    assert body.startswith("<!-- skill-scan-gate:comment ci -->\n")
    assert "[job summary](https://example.test/runs/7)" in body
    assert len(_rows(body)) == COMMENT_TOP
