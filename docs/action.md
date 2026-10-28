# The skill-scan-gate GitHub Action

`basitalisandhu/skill-scan-gate` is a composite Action. It runs the scanner from the Action's own
checkout (so the code that runs is the code at the ref you pinned), writes a job summary, optionally
uploads SARIF to code scanning, optionally posts one sticky comment on the pull request, and fails the
job when a finding is at or above `fail-on`.

The ready-made workflow is [examples/skill-scan-gate.yml](../examples/skill-scan-gate.yml): copy it to
`.github/workflows/skill-scan-gate.yml`.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | Directory to scan, relative to the workspace. |
| `fail-on` | `high` | Lowest severity that fails the job: `low`, `medium`, `high` or `none`. |
| `baseline` | empty | Baseline file from `skill-scan-gate baseline`; only findings not in it count. |
| `blob-min` | `200` | Minimum base64 run length for SSG203 (minimum 64). |
| `changed-only` | `false` | On pull requests, report only findings in the files the pull request changes; repository checks (SSG7xx) still run. Needs the base commit in the clone (see below). |
| `allow` | empty | Allowlist file of documented exceptions ([false-positives.md](false-positives.md)). |
| `exclude` | empty | Path globs to skip, one per line. |
| `sarif` | `true` | Write a SARIF 2.1.0 report. |
| `sarif-file` | `skill-scan-gate.sarif` | Where to write it. |
| `upload-sarif` | `true` | Upload it to code scanning (needs `security-events: write`). |
| `category` | `skill-scan-gate` | Code scanning category; also names the sticky comment, so two scans in one repository keep two comments. |
| `comment` | `false` | On `pull_request` and `pull_request_target` events, post or update one comment on the pull request. |
| `github-token` | `${{ github.token }}` | Token for the comment. The job token is enough when the job grants `pull-requests: write`. |
| `python-version` | empty | Install this Python with actions/setup-python; empty uses the runner's `python3` (3.11 or newer). |

## Outputs

| Output | Meaning |
|---|---|
| `finding-count` | Findings after baseline and allowlist suppression, at every severity. |
| `highest-severity` | `high`, `medium`, `low` or `none`. |
| `gate` | `pass` or `fail`, according to `fail-on`. |
| `suppressed-count` | Findings suppressed by the baseline or the allowlist. |
| `sarif-file` | Path of the SARIF report, empty when `sarif` is false. |
| `comment-file` | Path of the comment body (Markdown), empty when `comment` is false. Written on every event, posted only on pull requests. |

## The pull request comment

With `comment: "true"` the Action writes the comment body to a file first (the `comment-file` output),
then posts it with `gh api` from the runner; no third-party action is involved. The comment holds:

- a heading with the gate result (passed or failed) and the threshold;
- a table of counts by severity, suppressed findings and the gate;
- the top 10 findings, highest severity first, each with its rule id (linked to [rules.md](rules.md)),
  `file:line`, title and one-sentence fix;
- a link to the open results for this pull request in code scanning when the SARIF upload is on, and a
  link to the workflow run, whose job summary lists up to 100 findings.

The matched text (evidence) is never put in the comment, so no secret value reaches the pull request
thread, redacted or not. The comment starts with a hidden marker,
`<!-- skill-scan-gate:comment CATEGORY -->`; later runs find that comment and edit it instead of adding
a new one.

## Only the files a pull request changes

On a large skills repository, `changed-only: "true"` keeps the report to the files the pull request touches. The Action passes `github.event.pull_request.base.sha` to `scan --changed-only`, which runs `git diff --name-only BASE...HEAD` in the scanned directory. The scanner still reads every file; findings in other files are left out of the report, the gate, the SARIF and the comment, and a note says how many. The SECURITY.md and LICENSE checks still run.

`git diff` needs the base commit, so check out the full history:

```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: basitalisandhu/skill-scan-gate@<commit SHA>
        with:
          changed-only: "true"
```

With the default shallow checkout the scan stops with exit code 2 and a message naming `fetch-depth: 0`. On events other than pull requests the input is ignored with a notice and every file is reported.

## Permissions

| Permission | Needed for |
|---|---|
| `contents: read` | Checking out the repository. Always. |
| `pull-requests: write` | The comment. Only when `comment` is `true`. |
| `security-events: write` | The SARIF upload. Only when `upload-sarif` is `true`. |

Grant them on the job, not the workflow, and keep the workflow default at `contents: read`.

## Forks, Dependabot and read-only tokens

Pull requests from forks, and Dependabot pull requests, get a read-only `GITHUB_TOKEN`:

- **Comment:** for a `pull_request` from a fork the Action logs a notice and skips the comment. Any other
  refusal from the API (a read-only token, a missing permission) also becomes a notice; the comment step
  never fails the job.
- **SARIF upload:** the upload fails with a read-only token, so turn it off for forks:
  `upload-sarif: ${{ github.event.pull_request.head.repo.full_name == github.repository }}` (the example
  workflow does this).
- **Gate:** the scan and the pass or fail result work the same on forks, and the job summary always has
  the results.

Do not switch to `pull_request_target` just to get a comment on forks: that event runs with a write
token and must never check out or scan the fork's code with it.

## Pinning

Pin the Action to a full commit SHA with the version in a comment, for example
`basitalisandhu/skill-scan-gate@<sha> # v0.6.0`; Dependabot keeps both up to date. Look up the SHA of a
tag with `gh api repos/basitalisandhu/skill-scan-gate/commits/v0.6.0 --jq .sha`.
