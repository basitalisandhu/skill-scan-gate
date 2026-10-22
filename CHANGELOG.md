# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- SSG307 flags missing, empty, `*` and `.*` matchers on tool-event hook groups; low by default and medium only when the same group contains a command that produces SSG202 or invokes `curl`/`wget` (#3).

## [0.5.0] - 2026-10-28

### Changed

- SSG603 follows the reserved-name rules in the Claude Code plugin documentation, checked on 2026-10-28 (#8): all official, community and plugin directory marketplace names, another spelling of one (`claude.code.plugins`, a trailing dot), the names Claude Code uses itself (`inline`, `builtin`, `skills-dir`, `synced`, `npm`, `github` and others), JavaScript object member names, `claudeai-` names, non-ASCII names, and plugin names `claude plugin validate` rejects (`claude-code`, `claude-mods`, `cc-plugin-*`, official beside claude or anthropic). The finding's evidence now says why the name is reserved.

### Fixed

- A JSON file nested too deeply to parse is reported as SSG606 instead of ending the scan with a traceback.
- A `--baseline` or `--allow` file that is not UTF-8, or a baseline nested too deeply, exits with code 2 and a message naming the file instead of a traceback.
- The FAQ said `--changed-only` did not exist yet; it does, since 0.4.0.

### Added

- Seeded fuzz tests: every file the scanner reads replaced with empty, non-UTF-8, truncated, deeply nested or NUL bytes, and JSON values replaced with values of the wrong type; each run has a time limit.
- A scaling test (10 and 100 plugins, a 2,000 and a 20,000 line SKILL.md).
- A CI job that installs with pipx from the checkout and compares the README quick start output line by line.
- A Troubleshooting section in the README.

## [0.4.0] - 2026-10-20

### Added

- `scan --changed-only BASE_REF`: report only findings in files changed since `BASE_REF` (`git diff --name-only --relative BASE_REF...HEAD` in the scanned directory); the repository checks (SSG7xx) still run, and a note gives the number of findings left out. A missing `git`, a directory outside a repository or an unknown ref is exit code 2 (#2).
- Action input `changed-only` (default `false`): on pull requests, passes the base commit to `--changed-only`. Needs `actions/checkout` with `fetch-depth: 0`; see docs/action.md.
- JSON output has a `notes` list; the table and Markdown outputs print notes.
- `scan` warns when it found no skill, instruction, plugin, MCP, hook, settings or script files under the path, so a wrong path no longer looks like a clean result.

### Fixed

- `.claude/settings.local.json` is now scanned like `settings.json`. Claude Code reads it as project-local settings, so a committed copy that turned off permission prompts or ran a hook command used to pass without a finding.

### Changed

- README: the first screen has a three-line command-line quick start with real output, ahead of the Actions quick start.
- Workflows and repository policy hardened for the OpenSSF Scorecard (#26), the roadmap and Discussions links (#22, #25), and a dependency update for the SARIF upload action (#27).

## [0.3.0] - 2026-10-13

### Added

- Action input `comment` (default `false`): on pull requests, post or update one sticky comment (found by a hidden `<!-- skill-scan-gate:comment CATEGORY -->` marker) with counts by severity, the gate result, the top 10 findings with rule id, `file:line` and remediation, and links to code scanning and the workflow run. Posted with `gh api` from the runner; never shows matched text; skipped with a notice on forks or when the token cannot write, and never fails the job.
- Action input `github-token` (default `${{ github.token }}`) and output `comment-file` (the comment body, written before posting).
- `scan --comment FILE`, `--comment-marker NAME`, `--comment-sarif-url URL` and `--comment-run-url URL` write the same comment body from the command line.
- Ready-made workflow `examples/skill-scan-gate.yml` (pull requests touching skills, plugins, `.mcp.json`, hooks and agent instructions; least-privilege job permissions) and a Quick start at the top of the README.
- `docs/action.md`: inputs, outputs, permissions, the comment and the fork caveat.
- Self-test job that runs the Action with `comment: true` on the planted and secret-shaped fixtures and checks the comment body file.

### Changed

- Action description shortened to under 125 characters for the GitHub Marketplace listing.
- Markdown table cells escape line breaks as well as pipes, backticks and angle brackets.

## [0.2.0] - 2026-10-09

### Added

- Action input `blob-min`, passed to `scan --blob-min`, so the Action can lower the SSG203 threshold like the CLI.
- Add SSG607 (low) for unrestricted Bash in skill `allowed-tools`, with scoped-command negatives and a planted fixture.
- `scan --blob-min N` and `baseline --blob-min N`: configurable minimum length for SSG203 base64 blob detection (default 200, minimum 64; hex threshold stays 56 characters longer); threshold is recorded in the JSON report as `blobMin`.

## [0.1.0] - 2026-10-04

### Added

- `skill-scan-gate scan PATH`: walks `SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json`, `.claude-plugin/*.json`, `.mcp.json`, `settings.json` and scripts under `scripts/` or `hooks/`, and applies 31 rules in seven families: instruction overrides (SSG101 to SSG104), exfiltration shapes (SSG201 to SSG204), commands in hooks, scripts and skills (SSG301 to SSG306), MCP server declarations (SSG401 to SSG406), secret-shaped strings (SSG501 to SSG503), manifests and skill front matter (SSG601 to SSG606), and repository files (SSG701, SSG702).
- Output as a table, JSON, Markdown and SARIF 2.1.0, with `--output`, `--sarif`, `--summary` and `--github-output` side outputs; `--fail-on low|medium|high|none`; exit codes 0, 1 and 2. Secret values are redacted in every format.
- `skill-scan-gate baseline PATH --out FILE` and `scan --baseline FILE`: line-shift-tolerant fingerprints so only new findings fail.
- `scan --allow FILE`: allowlist of rule and path-glob entries with reasons; unused entries are reported. `--exclude GLOB` skips paths.
- `skill-scan-gate rules`: lists every rule.
- Composite GitHub Action (`action.yml`) with inputs `path`, `fail-on`, `baseline`, `allow`, `exclude`, `sarif`, `sarif-file`, `upload-sarif`, `category` and `python-version`; job summary; SARIF upload with `github/codeql-action/upload-sarif` pinned by commit.
- Planted and clean fixtures, a run-time secret fixture generator, a self-test workflow that runs the Action on them, CI on Python 3.11, 3.12 and 3.13, a container image `ghcr.io/basitalisandhu/skill-scan-gate` published on version tags with an SPDX SBOM, a build provenance attestation and a keyless cosign signature, and PyPI trusted publishing (off until the repository variable `PYPI_PUBLISH` is set).

[Unreleased]: https://github.com/basitalisandhu/skill-scan-gate/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/basitalisandhu/skill-scan-gate/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/basitalisandhu/skill-scan-gate/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/basitalisandhu/skill-scan-gate/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/basitalisandhu/skill-scan-gate/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/basitalisandhu/skill-scan-gate/releases/tag/v0.1.0
