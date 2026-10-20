"""Command-line error paths and the rules listing."""

import json

from skill_scan_gate.cli import EXIT_ERROR, EXIT_OK, main
from skill_scan_gate.rules import RULES

from conftest import CLEAN, PLANTED


def test_baseline_rejects_small_blob_min(tmp_path, capsys):
    assert main(["baseline", str(CLEAN), "--out", str(tmp_path / "b.json"), "--blob-min", "10"]) == EXIT_ERROR
    assert "--blob-min must be at least 64" in capsys.readouterr().err


def test_baseline_rejects_a_missing_directory(tmp_path, capsys):
    assert main(["baseline", str(tmp_path / "nope"), "--out", str(tmp_path / "b.json")]) == EXIT_ERROR
    assert "not a directory" in capsys.readouterr().err


def test_baseline_with_a_bad_allowlist_is_exit_2(tmp_path, capsys):
    allow = tmp_path / "allow.txt"
    allow.write_text("this is not an allowlist entry\n", encoding="utf-8")
    assert main(["baseline", str(PLANTED), "--out", str(tmp_path / "b.json"), "--allow", str(allow)]) == EXIT_ERROR
    assert capsys.readouterr().err.startswith("skill-scan-gate: ")


def test_rules_table_lists_every_rule(capsys):
    assert main(["rules"]) == EXIT_OK
    out = capsys.readouterr().out
    assert all(rule_id in out for rule_id in RULES)


def test_rules_json(capsys):
    assert main(["rules", "--format", "json"]) == EXIT_OK
    doc = json.loads(capsys.readouterr().out)
    assert {r["id"] for r in doc} == set(RULES)


def test_unwritable_output_is_exit_2_with_a_message(tmp_path, capsys):
    out = tmp_path / "missing-dir" / "report.txt"
    assert main(["scan", str(CLEAN), "--output", str(out)]) == EXIT_ERROR
    assert "skill-scan-gate: " in capsys.readouterr().err


def test_output_file_gets_the_report_and_stderr_the_summary(tmp_path, capsys):
    out = tmp_path / "report.txt"
    assert main(["scan", str(CLEAN), "--output", str(out)]) == EXIT_OK
    assert out.read_text(encoding="utf-8").startswith("skill-scan-gate ")
    assert "finding(s)" in capsys.readouterr().err


def test_broken_pipe_is_not_an_error(monkeypatch, capsys):
    import skill_scan_gate.cli as cli

    def boom(_a):
        raise BrokenPipeError

    monkeypatch.setattr(cli, "_cmd_rules", boom)

    class FakeStdout:
        def fileno(self):
            return 1

    monkeypatch.setattr(cli.os, "dup2", lambda *a: None)
    monkeypatch.setattr(cli.sys, "stdout", FakeStdout())
    assert main(["rules"]) == EXIT_OK


def test_empty_directory_warns_that_nothing_was_scanned(tmp_path, capsys):
    assert main(["scan", str(tmp_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "scanned 0 file(s)" in out and "warning: no skill, instruction, plugin" in out


def test_no_warning_when_files_were_scanned(capsys):
    main(["scan", str(CLEAN)])
    assert "is this the right directory" not in capsys.readouterr().out
