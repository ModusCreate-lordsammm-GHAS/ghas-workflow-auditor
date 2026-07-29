# GHAS Workflow Audit (v1)

Scans `.github/workflows/*.yml` files across one or more GitHub orgs and produces
two CSVs: security/quality **findings** and an **action usage inventory**.

This is a deliberately small first iteration: **workflow-file scanning only**.
Branch protection / repo access review, reusable-workflow chain resolution,
redirect detection, SARIF, posture scores and dashboards are out of scope for v1.

## Files

| Path | Purpose |
|------|---------|
| `.github/workflows/ghas-audit.yml` | The audit workflow (OIDC auth, per-org matrix, merge) |
| `.github/workflows/platform-metrics.yml` | The platform-metrics workflow (same pattern, adds a `TOTAL` row) |
| `orgs.txt` | The list of orgs to scan (one per line) |
| `bin/audit_workflows.py` | The single-file audit script |
| `bin/collect_platform_metrics.py` | The single-file platform-metrics collector |
| `bin/requirements.txt` | Python dependencies (`requests`, `pyyaml`, `pytest`) |
| `tests/` | Fixture workflows + pytest checks |

## How to trigger the workflow

1. Go to **Actions → GHAS Workflow Audit → Run workflow**.
2. Leave **org-names** blank to scan every org listed in `orgs.txt` (the normal case).
   To scan a different set just once, type a comma-separated list here to override `orgs.txt`.
3. Optionally set **repo-limit** to cap repos per org for a quick test run.
4. Run. Each org is scanned in parallel (`continue-on-error`), then a `merge`
   job combines everything.

The app cannot enumerate orgs at the enterprise level, so the org list is
maintained in `orgs.txt` (one org per line; `#` comments and blank lines ignored).
The GitHub App must be installed in every org listed.

## How to read the results

Download artifacts from the run page:

- `audit-<org>` — per-org `findings.csv` and `action_inventory.csv`.
- `audit-combined` — `findings_all.csv` and `action_inventory_all.csv` across all orgs.

### `findings.csv`
`org, repo, workflow_file, workflow_name, job, check, severity, evidence, recommendation`

`evidence` is the offending value; `recommendation` is a fixed remediation sentence
per check. Sort/filter by `severity` (`critical` > `high` > `medium` > `info`).

### `action_inventory.csv`
`action_ref, owner, pin_type, is_vetted, kind, repo_count, total_uses`

- `pin_type`: `sha` | `tag` | `branch` | `local` | `docker`
- `kind`: `action` (step-level) | `reusable_workflow` (job-level `uses:` ending in `.yml`/`.yaml`)
- Sorted by `total_uses` descending. This feeds the enterprise action allowlist.

## The checks (v1)

| check id | severity |
|----------|----------|
| `missing_permissions` | high |
| `write_all_permissions` | critical |
| `unpinned_action_tag` | high |
| `action_on_branch` | critical |
| `unvetted_action_owner` | high |
| `inline_package_install` | medium |
| `curl_pipe_shell` | critical |
| `pull_request_target` | critical |
| `untrusted_context_in_run` | high |
| `deprecated_runner` | high |

A `parse_error` (info) finding is recorded for any file that fails to parse; the
scan never crashes on a bad file, a 404, or an odd `runs-on` shape.

## Run the tests

The checks are pure functions over parsed YAML, so they run with no token and no
network access:

```bash
pip install -r bin/requirements.txt pytest
pytest tests/
```

## Adding a new check (3 steps)

1. Write a function `check_xyz(parsed, raw, repo, path)` returning a list of
   finding dicts (use the `_finding(...)` helper).
2. Add the function to the `CHECKS` list.
3. Add a `check_xyz` entry to the `RECOMMENDATIONS` dict.

---

# GHAS Platform Metrics

A second, separate capability that produces a point-in-time baseline of GHAS
feature adoption per org for leadership reporting. It shares only the OIDC auth
pattern and `orgs.txt` with the audit tool; it does not modify the audit script
or workflow.

Script: `bin/collect_platform_metrics.py`. Workflow: `.github/workflows/platform-metrics.yml`.

## How to trigger the workflow

1. Go to **Actions → GHAS Platform Metrics → Run workflow**.
2. Leave **org-names** blank to scan every org in `orgs.txt`, or type a
   comma-separated list to override just once.
3. Optionally set **repo-limit** to cap repos per org, or **skip-repo-scan** =
   `true` for a fast org-level-only run.
4. Run. Orgs are scanned in parallel (`continue-on-error`), then a `merge` job
   combines the CSVs and appends the enterprise `TOTAL` row.

The workflow needs the App to be granted `copilot: read` and
`organization_administration: read` in addition to the audit's
`contents`/`metadata`/`administration` read.

## How to read the results

Download from the run page:

- `metrics-<org>` — per-org `platform_metrics_by_org.csv` and `platform_metrics_by_repo.csv`.
- `metrics-combined` — the same two files across all orgs; the by-org file ends
  with a `TOTAL` row summing the numeric columns.

### `platform_metrics_by_org.csv`
One row per org (plus `TOTAL`): repo footprint (active/archived, public/private/
internal), GHAS/secret-scanning/push-protection/Dependabot/CodeQL adoption
counts, open alert counts, Copilot seats, Actions minutes, and storage.

### `platform_metrics_by_repo.csv`
One row per repo — the drill-down for "which repos are missing which controls."

### `n/a` vs `0`

A metric the token cannot read is written as **`n/a`** (a permission gap),
distinct from a real **`0`**. Each per-org run logs a summary line, e.g.
`[org=pfizer-devex] collected 25/26 metrics; 1 skipped due to permissions: ['copilot_seats']`.
The per-repo `security_and_analysis` block requires `administration: read`;
without it, per-repo GHAS status reads `n/a` rather than a misleading `false`.

## Run the tests

The parsing/aggregation functions are pure (no token, no network):

```bash
pip install -r bin/requirements.txt
pytest tests/test_metrics.py
```
