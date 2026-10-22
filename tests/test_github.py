from dataclasses import replace
from pathlib import Path

from skill_scan_gate.cli import main
from skill_scan_gate.report import render_github
from skill_scan_gate.scanner import Finding, ScanResult

from conftest import PLANTED


def test_workflow_command_escaping_and_severity():
    findings = [
        Finding("SSG501", "a,b:c%\r\nx.py", 2, "bad%\r\n::error::injected", "a"),
        Finding("SSG301", "hook.json", 1, "unsafe", "b"),
        Finding("SSG203", "config.json", 3, "broad", "c"),
        Finding("SSG607", "SKILL.md", 0, "review", "d"),
        Finding("SSG701", ".", 0, "missing", "e"),
    ]
    output = render_github(ScanResult(Path("."), findings, []))
    lines = output.splitlines()
    assert len(lines) == 5
    assert lines[0] == (
        "::error file=a%2Cb%3Ac%25%0D%0Ax.py,line=2,title=SSG501::"
        "Private key block: bad%25%0D%0A::error::injected. "
        "Remove the key, rotate it, and load keys from a secret store at run time."
    )
    assert lines[1].startswith("::error ")
    assert lines[2].startswith("::warning ")
    assert lines[3].startswith("::notice ") and ",line=" not in lines[3]
    assert lines[4].startswith("::notice title=SSG701::")


def test_planted_golden():
    from skill_scan_gate.scanner import scan

    expected = Path(__file__).parent / "fixtures" / "planted.github.txt"
    result = scan(PLANTED)
    # CPython minor versions use different JSONDecodeError wording and locations.
    result.findings = [
        replace(finding, evidence="<invalid JSON>", line=0) if finding.rule == "SSG606" else finding
        for finding in result.findings
    ]
    assert render_github(result) == expected.read_text(encoding="utf-8")


def test_cli_preserves_fail_on_and_suppression(tmp_path, capsys):
    output = tmp_path / "annotations.txt"
    args = ["scan", str(PLANTED), "--format", "github"]
    assert main([*args, "--output", str(output)]) == 1
    assert "::error " in output.read_text(encoding="utf-8")
    assert main([*args, "--fail-on", "none"]) == 0
    assert "::error " in capsys.readouterr().out


def test_absolute_and_windows_paths():
    finding = Finding("SSG301", r"hooks\hooks.json", 1, "unsafe", "a")
    assert "file=hooks/hooks.json," in render_github(ScanResult(Path("."), [finding], []))
    assert render_github(ScanResult(Path("."), [], [])) == ""


def test_metadata_is_not_interpolated_unescaped():
    finding = Finding("SSG301", "safe.json", 1, "message", "a")
    # Rule titles are deliberately not used as workflow-command properties.
    assert "title=SSG301::" in render_github(ScanResult(Path("."), [finding], []))


def test_baseline_and_subdirectory_prefix(tmp_path, capsys):
    from conftest import write_tree

    root = write_tree(
        tmp_path / "plugin",
        {
            "hooks/hooks.json": {
                "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "printenv"}]}]},
            }
        },
    )
    assert main(["scan", str(root), "--format", "github", "--sarif-root", str(tmp_path)]) == 1
    assert "file=plugin/hooks/hooks.json" in capsys.readouterr().out
    baseline = tmp_path / "baseline.json"
    assert main(["baseline", str(root), "--out", str(baseline)]) == 0
    capsys.readouterr()
    assert main(["scan", str(root), "--format", "github", "--baseline", str(baseline)]) == 0
    assert capsys.readouterr().out == ""
