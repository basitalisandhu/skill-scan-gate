"""Files changed on a branch, for `scan --changed-only BASE_REF`.

Runs `git diff --name-only --relative BASE_REF...HEAD` in the scanned directory, so paths come back relative to it,
like finding paths. The scanner still reads every file; only the reported findings are narrowed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .scanner import Finding

REPOSITORY_RULE_PREFIX = "SSG7"  # SECURITY.md and LICENSE checks are about the repository, not a file


class ChangedFilesError(Exception):
    """git is missing, the directory is not in a repository, or the base ref is unknown."""


def changed_files(root: Path, base_ref: str) -> set[str]:
    if not base_ref or base_ref.startswith("-") or any(c.isspace() for c in base_ref):
        raise ChangedFilesError(f"--changed-only: {base_ref!r} is not a git ref")
    git = shutil.which("git")
    if git is None:
        raise ChangedFilesError("--changed-only needs the git command, which is not on PATH")
    try:
        proc = subprocess.run(
            [git, "-C", str(root), "diff", "--name-only", "--relative", "-z", f"{base_ref}...HEAD", "--"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ChangedFilesError(f"--changed-only: could not run git: {e}") from e
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no error message"])[0]
        raise ChangedFilesError(
            f"--changed-only: git diff {base_ref}...HEAD failed ({detail}). The base commit must be in the clone: "
            "in GitHub Actions, check out with fetch-depth: 0."
        )
    return {p for p in proc.stdout.split("\0") if p}


def keep_changed(findings: list[Finding], changed: set[str]) -> tuple[list[Finding], int]:
    """Findings in changed files plus repository findings; and how many were left out."""
    kept = [f for f in findings if f.file in changed or f.rule.startswith(REPOSITORY_RULE_PREFIX)]
    return kept, len(findings) - len(kept)
