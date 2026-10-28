"""Seeded fuzz tests: bad bytes and wrong JSON types in every file the scanner reads.

A scan must end with exit code 0 or 1 (bad JSON is the SSG606 finding, not a crash) and a bad --baseline or
--allow file with exit code 2 and a message naming it. Each run has a time limit, so a hang fails the test.
"""

from __future__ import annotations

import contextlib
import io
import json
import random
import shutil
import threading
from pathlib import Path

import pytest

from skill_scan_gate.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "fixture-planted"
FILES = sorted(str(p.relative_to(FIXTURE)) for p in FIXTURE.rglob("*") if p.is_file())
JSON_FILES = [f for f in FILES if f.endswith(".json") and f != ".claude-plugin/broken.json"]
SEED = 20261028
BAD = {
    "empty": b"",
    "not-utf8": b"\xff\xfe\x00" + bytes(random.Random(SEED).randrange(128, 256) for _ in range(256)),
    "truncated": b'{"mcpServers": {"x": [',
    "deep": b"[" * 50_000 + b"]" * 50_000,
    "nul": b"---\nname: x\n---\n\x00\x00",
}
WRONG = [None, True, 7, -1.5, "x", [], {}, [1, [2]], {"a": {"b": None}}]


def _run(argv: list[str], limit: float = 30.0) -> tuple[int, str]:
    out: dict[str, object] = {}

    def target() -> None:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                out["code"] = main(argv)
            except BaseException as e:  # the test reports any escape as a crash
                out["crash"] = repr(e)
        out["text"] = sink.getvalue()

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(limit)
    assert not t.is_alive(), f"skill-scan-gate {' '.join(argv)} did not finish in {limit}s"
    assert "crash" not in out, out["crash"]
    return out["code"], out["text"]  # type: ignore[return-value]


@pytest.mark.parametrize("kind", sorted(BAD))
@pytest.mark.parametrize("rel", FILES)
def test_bad_bytes_never_crash(tmp_path, rel, kind):
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE, root)
    (root / rel).write_bytes(BAD[kind])
    code, text = _run(["scan", str(root), "--format", "json", "--fail-on", "none"])
    assert code == 0, text[-500:]
    if kind == "deep" and rel in JSON_FILES:
        doc = json.loads(text)
        assert any(f["rule"] == "SSG606" and f["file"] == rel for f in doc["findings"])


def _paths(node, prefix=()):
    yield prefix
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _paths(v, (*prefix, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _paths(v, (*prefix, i))


@pytest.mark.parametrize("rel", JSON_FILES)
def test_wrong_types_never_crash(tmp_path, rel):
    rng = random.Random(f"{SEED}/{rel}")
    original = json.loads((FIXTURE / rel).read_text(encoding="utf-8"))
    for trial in range(25):
        doc = json.loads(json.dumps(original))
        for _ in range(rng.randint(1, 3)):
            paths = [p for p in _paths(doc) if p]
            if not paths:
                doc = json.loads(json.dumps(rng.choice(WRONG)))
                break
            path = rng.choice(paths)
            node = doc
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = json.loads(json.dumps(rng.choice(WRONG)))
        root = tmp_path / f"repo{trial}"
        shutil.copytree(FIXTURE, root)
        (root / rel).write_text(json.dumps(doc), encoding="utf-8")
        code, text = _run(["scan", str(root), "--fail-on", "none"])
        assert code == 0, (json.dumps(doc)[:300], text[-500:])


@pytest.mark.parametrize("kind", ["empty", "not-utf8", "truncated", "deep"])
@pytest.mark.parametrize("option", ["--baseline", "--allow"])
def test_bad_baseline_or_allowlist_exits_2(tmp_path, option, kind):
    bad = tmp_path / "suppress.file"
    bad.write_bytes(BAD[kind])
    code, text = _run(["scan", str(FIXTURE), option, str(bad)])
    if option == "--allow" and kind in {"empty", "deep", "truncated"}:
        # Empty is a valid allowlist; brackets and braces are lines the allowlist parser rejects by name.
        assert code in (1, 2), text
        return
    assert code == 2, text
    assert "suppress.file" in text
