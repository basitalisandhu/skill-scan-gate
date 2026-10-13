"""Action metadata and workflow hygiene."""

import re

import pytest

from conftest import ROOT

yaml = pytest.importorskip("yaml")

ACTION = yaml.safe_load((ROOT / "action.yml").read_text())
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def _uses(doc):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k == "uses" and isinstance(v, str):
                yield v
            else:
                yield from _uses(v)
    elif isinstance(doc, list):
        for item in doc:
            yield from _uses(item)


def test_action_is_composite_with_metadata():
    assert ACTION["runs"]["using"] == "composite"
    assert ACTION["name"] and ACTION["description"] and ACTION["branding"]["icon"]
    assert len(ACTION["description"]) <= 200


def test_action_has_required_inputs_with_defaults():
    inputs = ACTION["inputs"]
    for name in ("path", "fail-on", "baseline", "sarif", "upload-sarif"):
        assert name in inputs, name
        assert "default" in inputs[name] and inputs[name]["description"]
    assert inputs["fail-on"]["default"] == "high"
    assert inputs["sarif"]["default"] in ("true", "false")
    assert inputs["upload-sarif"]["default"] in ("true", "false")


def test_every_input_is_referenced_in_steps():
    body = (ROOT / "action.yml").read_text().split("runs:", 1)[1]
    for name in ACTION["inputs"]:
        assert f"inputs.{name}" in body, name


def test_outputs_map_to_scan_step():
    steps = {s.get("id") for s in ACTION["runs"]["steps"]}
    assert "scan" in steps
    for name, spec in ACTION["outputs"].items():
        assert spec["value"] == f"${{{{ steps.scan.outputs.{name} }}}}"


def test_action_runs_scanner_from_its_own_path():
    scan = next(s for s in ACTION["runs"]["steps"] if s.get("id") == "scan")
    assert scan["env"]["ACTION_PATH"] == "${{ github.action_path }}"
    assert "$ACTION_PATH/src" in scan["run"] and "python3 -m skill_scan_gate" in scan["run"]
    assert "set +e" in scan["run"]


def test_sarif_upload_is_conditional_and_pinned():
    upload = next(s for s in ACTION["runs"]["steps"] if "upload-sarif" in s.get("uses", ""))
    assert upload["uses"].startswith("github/codeql-action/upload-sarif@")
    assert SHA_PIN.match(upload["uses"])
    assert "inputs.upload-sarif == 'true'" in upload["if"] and "inputs.sarif == 'true'" in upload["if"]
    assert upload["with"]["sarif_file"] == "${{ inputs.sarif-file }}"


def test_gate_step_fails_last():
    last = ACTION["runs"]["steps"][-1]
    assert "steps.scan.outputs.gate == 'fail'" in last["if"]
    assert "exit 1" in last["run"]


def test_inputs_never_interpolated_into_run_scripts():
    for step in ACTION["runs"]["steps"]:
        assert "${{ inputs." not in step.get("run", ""), step.get("name")


@pytest.mark.parametrize("path", [ROOT / "action.yml", *WORKFLOWS], ids=lambda p: p.name)
def test_third_party_actions_are_sha_pinned(path):
    doc = yaml.safe_load(path.read_text())
    for ref in _uses(doc):
        if ref.startswith("./"):
            continue
        assert SHA_PIN.match(ref), f"{path.name}: {ref}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflows_default_to_read_only_token(path):
    doc = yaml.safe_load(path.read_text())
    assert doc["permissions"] == {"contents": "read"}


def test_self_test_expects_failure_on_planted_and_success_on_clean():
    doc = yaml.safe_load((ROOT / ".github/workflows/self-test.yml").read_text())
    steps = {s.get("id"): s for s in doc["jobs"]["self-test"]["steps"] if s.get("id")}
    assert steps["planted"]["uses"] == "./" and steps["planted"]["continue-on-error"] is True
    assert steps["planted"]["with"]["path"] == "tests/fixtures/fixture-planted"
    assert steps["clean"]["with"]["path"] == "tests/fixtures/fixture-clean"
    assert "continue-on-error" not in steps["clean"]
    text = (ROOT / ".github/workflows/self-test.yml").read_text()
    assert 'test "$PLANTED_OUTCOME" = "failure"' in text
    assert 'test "$CLEAN_OUTCOME" = "success"' in text


def test_release_workflow_is_guarded():
    doc = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    for job in doc["jobs"].values():
        assert job["if"] == "vars.PYPI_PUBLISH == 'true'"


EXAMPLE = ROOT / "examples" / "skill-scan-gate.yml"


def test_marketplace_metadata():
    # GitHub Marketplace: a name, a description under 125 characters, an author and branding.
    assert ACTION["name"] == "Skill Scan Gate"
    assert len(ACTION["description"]) < 125
    assert ACTION["author"]
    assert ACTION["branding"]["icon"] == "shield"
    assert ACTION["branding"]["color"] in (
        "white",
        "black",
        "yellow",
        "blue",
        "green",
        "orange",
        "red",
        "purple",
        "gray-dark",
    )


def test_comment_inputs_and_step():
    inputs = ACTION["inputs"]
    assert inputs["comment"]["default"] == "false"
    assert inputs["github-token"]["default"] == "${{ github.token }}"
    assert ACTION["outputs"]["comment-file"]["value"] == "${{ steps.scan.outputs.comment-file }}"
    steps = ACTION["runs"]["steps"]
    names = [s["name"] for s in steps]
    comment = steps[names.index("Comment on the pull request")]
    assert names.index("Comment on the pull request") < len(steps) - 1  # the gate still fails last
    assert "inputs.comment == 'true'" in comment["if"] and "pull_request" in comment["if"]
    assert comment["env"]["GH_TOKEN"] == "${{ inputs.github-token }}"
    assert "uses" not in comment  # gh api from the runner, no third-party action
    run = comment["run"]
    assert "gh api" in run and "startswith(env.MARKER)" in run
    assert "exit 1" not in run and "skip()" in run and "exit 0" in run
    assert '"$HEAD_REPO" != "$GITHUB_REPOSITORY"' in run


def test_example_workflow_is_least_privilege_and_pinned():
    from skill_scan_gate import __version__

    text = EXAMPLE.read_text()
    doc = yaml.safe_load(text)
    on = doc[True] if True in doc else doc["on"]  # PyYAML reads the key `on` as True
    paths = on["pull_request"]["paths"]
    for needle in ("SKILL.md", "plugins", ".mcp.json", "hooks"):
        assert any(needle in p for p in paths), needle
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["scan"]
    assert job["permissions"] == {"contents": "read", "pull-requests": "write", "security-events": "write"}
    refs = list(_uses(doc))
    assert SHA_PIN.match(refs[0].split()[0]) and refs[0].startswith("actions/checkout@")
    ssg = next(s for s in job["steps"] if "skill-scan-gate" in s.get("uses", ""))
    assert ssg["with"]["comment"] == "true"
    # Pinned to this release: the commit SHA with a version comment, or the tag itself.
    m = re.search(r"uses: basitalisandhu/skill-scan-gate@(\S+)(?: # (v\S+))?", text)
    assert m, "example does not use the Action"
    ref, comment = m.groups()
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        assert comment == f"v{__version__}", comment
    else:
        assert ref == f"v{__version__}", ref


def test_quoted_step_names_with_colon_space():
    for path in [*WORKFLOWS, EXAMPLE, ROOT / "action.yml"]:
        for line in path.read_text().splitlines():
            s = line.strip()
            if s.startswith(("- name: ", "name: ")):
                value = s.split("name: ", 1)[1]
                if ": " in value:
                    assert value[0] in "\"'", f"{path.name}: {s}"
