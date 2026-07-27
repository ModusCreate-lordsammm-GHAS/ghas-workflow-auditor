# GHAS Platform Metrics Extension — Build Brief

## Context

This brief extends the existing `ghas-audit` tool in `pfizer-devex/ghas-enablement`. The existing tool scans workflow files and produces `findings.csv` and `action_inventory.csv`. This brief adds a **platform-metrics** capability that produces enterprise-wide baseline data on GHAS feature adoption per organization.

**Purpose:** produce a defensible current-state baseline of Pfizer's GitHub platform for a leadership roadmap document. The output is a spreadsheet of real numbers per org — not estimates, not speculation.

## What to Build

A new script `bin/collect_platform_metrics.py` alongside the existing `bin/audit_workflows.py`. A new workflow `.github/workflows/platform-metrics.yml` alongside the existing `ghas-audit.yml`. The metrics workflow follows the same pattern as the audit workflow: `prepare` job builds an org matrix from `orgs.txt`, then a matrix job runs the metrics script per org with a per-org OIDC token, then a `merge` job concatenates the per-org CSVs into combined enterprise CSVs uploaded as an artifact.

**Do not modify the existing audit script or workflow.** This is a separate capability that shares only the auth pattern and the org list.

## Auth

Reuse the exact same auth pattern as the existing audit workflow:

```yaml
- name: Generate installation token
  uses: pfizer-github-automation/github-oidc-action@f5262de087feab1ec962d1348bce634037611b93
  id: app-token
  with:
    github-app-name: 'oidc-emu-migration'
    permissions: '{"contents": "read", "metadata": "read", "administration": "read", "copilot": "read", "organization_administration": "read"}'
    org: ${{ matrix.org }}
```

Note the expanded permissions block — this script needs more than the audit script does. If the App does not currently have these grants, the script must fail gracefully per endpoint: log the permission denial, write the affected metric as `n/a` in the CSV, continue with the other metrics. Do not crash the whole run because one permission is missing.

## Metrics to Collect

For each organization in `orgs.txt`, collect the following. Each metric maps to a specific API endpoint. Handle 403 (permission denied) and 404 (not enabled) gracefully.

### Organization-Level Metrics

| Metric | Endpoint | Notes |
|---|---|---|
| Total repos (active, non-archived) | `GET /orgs/{org}/repos?type=all&per_page=100` (paginate) | Filter out `archived: true` and `disabled: true` |
| Total repos (archived) | Same as above, count `archived: true` | For context |
| Dependabot alerts (open) | `GET /orgs/{org}/dependabot/alerts?state=open&per_page=100` (paginate, count only) | Cap at first page count if pagination is expensive; note the cap in output |
| Secret scanning alerts (open) | `GET /orgs/{org}/secret-scanning/alerts?state=open&per_page=100` (paginate, count only) | Same pagination approach |
| Code scanning alerts (open) | `GET /orgs/{org}/code-scanning/alerts?state=open&per_page=100` (paginate, count only) | Same |
| Copilot seats billing | `GET /orgs/{org}/copilot/billing` | Returns `seat_breakdown` with `total`, `added_this_cycle`, `pending_invitation`, `pending_cancellation`, `active_this_cycle`, `inactive_this_cycle` |
| Actions minutes consumption | `GET /orgs/{org}/settings/billing/actions` | Returns `total_minutes_used`, `total_paid_minutes_used`, `included_minutes`, `minutes_used_breakdown` |
| Packages storage | `GET /orgs/{org}/settings/billing/packages` | Returns `total_gigabytes_bandwidth_used` |
| Shared storage | `GET /orgs/{org}/settings/billing/shared-storage` | Returns `days_left_in_billing_cycle`, `estimated_paid_storage_for_month`, `estimated_storage_for_month` |

### Repo-Level Metrics (aggregated to org level)

For each repo in the org, fetch `GET /repos/{org}/{repo}` and read the `security_and_analysis` block. Count per org:

| Metric | Field in `security_and_analysis` |
|---|---|
| Repos with GHAS (Advanced Security) enabled | `advanced_security.status == "enabled"` |
| Repos with Secret Scanning enabled | `secret_scanning.status == "enabled"` |
| Repos with Secret Scanning Push Protection enabled | `secret_scanning_push_protection.status == "enabled"` |
| Repos with Dependabot Security Updates enabled | `dependabot_security_updates.status == "enabled"` |
| Repos with Secret Scanning Non-Provider Patterns enabled | `secret_scanning_non_provider_patterns.status == "enabled"` |
| Repos with Secret Scanning Validity Checks enabled | `secret_scanning_validity_checks.status == "enabled"` |

For each repo, also check:

| Metric | Endpoint |
|---|---|
| Code Scanning (CodeQL) configured | `GET /repos/{org}/{repo}/code-scanning/default-setup` — 200 if default setup configured; also check for presence of `.github/workflows/codeql*.yml` in workflows list from the existing audit's inventory |
| Dependabot config present | `GET /repos/{org}/{repo}/contents/.github/dependabot.yml` — 200 if present, 404 if not |

**Public vs private breakdown:** for each of the security_and_analysis metrics above, also count separately by `visibility` (`public`, `private`, `internal`). This matters because GHAS billing works differently for public repos.

## Output Format

Two CSVs per org, merged into two enterprise-wide CSVs.

### `platform_metrics_by_org.csv`

One row per organization. Columns:

```
org,
total_repos_active, total_repos_archived,
public_repos, private_repos, internal_repos,
ghas_enabled, ghas_enabled_private, ghas_enabled_internal,
secret_scanning_enabled, secret_scanning_push_protection_enabled,
dependabot_security_updates_enabled, dependabot_config_present,
codeql_default_setup, codeql_workflow_present,
dependabot_alerts_open, secret_scanning_alerts_open, code_scanning_alerts_open,
copilot_seats_total, copilot_seats_active_this_cycle, copilot_seats_inactive_this_cycle, copilot_seats_pending,
actions_minutes_used_total, actions_minutes_used_paid, actions_minutes_included,
packages_storage_gb, shared_storage_estimated_paid,
collected_at
```

### `platform_metrics_by_repo.csv`

One row per repo. Columns:

```
org, repo, visibility, archived, disabled,
ghas_enabled, secret_scanning_enabled, secret_scanning_push_protection_enabled,
dependabot_security_updates_enabled, secret_scanning_non_provider_patterns,
secret_scanning_validity_checks,
codeql_default_setup, codeql_workflow_present, dependabot_config_present,
default_branch, pushed_at, updated_at,
collected_at
```

The by-repo CSV is what enables leadership to drill into "which specific repos are missing controls" if they want to.

## Enterprise Summary Row

At the end of `platform_metrics_by_org.csv`, append a `TOTAL` row that sums numeric columns across all orgs. This is the row that becomes Exhibit A in the roadmap document — the single line that says "across 23 orgs, X repos, Y with GHAS, Z with secret scanning."

## Script Structure

Single Python file (`bin/collect_platform_metrics.py`), same style as `bin/audit_workflows.py` — top-to-bottom readable, no package hierarchy. Uses `requests` and standard library only. Reads `GH_TOKEN` from environment. CLI:

```
python3 bin/collect_platform_metrics.py --org ORG --output-dir DIR [--repo-limit N] [--skip-repo-scan]
```

`--repo-limit` caps the repo-level scan for test runs. `--skip-repo-scan` produces only the org-level metrics without iterating all repos — useful for a fast smoke test.

## Rate Limiting

Same pattern as the existing audit script — when `x-ratelimit-remaining` drops below 50, sleep until `x-ratelimit-reset`. Retry once on 5xx. Log rate limit status every 100 API calls so runners don't look hung on a big org.

At scale, the repo-level scan is `total_repos × 2` API calls (one for security_and_analysis, one for CodeQL default-setup) per org. For an org with 500 repos that's 1,000 calls. With per-org tokens at 15K/hour each, this is well within limits per org, but the org matrix in the workflow means all orgs run in parallel — no cross-org rate limit contention because tokens are independent.

## Handling Missing Permissions

Every API call is wrapped in try/except. On 403, log which permission is missing and mark the metric as `n/a` (not zero, not empty — `n/a` so the CSV reader knows the difference between "zero repos" and "we could not read this"). On 404, mark as `0` for count-type metrics or `false` for boolean-type metrics. Do not let a single permission gap prevent collecting the other metrics.

At the end of each per-org run, log a summary line: `[org=pfizer-devex] collected 14/16 metrics; 2 skipped due to permissions: [copilot_seats, actions_minutes]`. This surfaces auth gaps immediately without breaking the run.

## Workflow File

`.github/workflows/platform-metrics.yml` follows the exact same structure as `ghas-audit.yml`:

1. `prepare` job — read `orgs.txt`, build matrix output
2. `metrics` job — matrix per org, `continue-on-error: true`, uses the OIDC action, runs the script, uploads a per-org artifact
3. `merge` job — downloads all per-org artifacts, concatenates the two CSVs, writes the `TOTAL` summary row, uploads combined enterprise artifact

Trigger: `workflow_dispatch` (manual) and optionally `schedule: cron: '0 6 1 * *'` for a monthly refresh once the tool is validated.

## Testing

Same pattern as the existing audit tool:

- `tests/test_metrics.py` with unit tests for the response-parsing functions using fixture JSON in `tests/fixtures/`
- Local dev with a PAT: `GH_TOKEN=ghp_xxx python3 bin/collect_platform_metrics.py --org pfizer-devex --repo-limit 5 --output-dir /tmp/out --skip-repo-scan` for a fast smoke test

## Definition of Done

1. Script runs against a single org with a PAT locally and produces both CSVs correctly
2. Script handles missing permissions gracefully — no crashes on 403
3. Workflow runs the matrix across all orgs in `orgs.txt` and produces combined enterprise CSVs as a downloadable artifact
4. The `TOTAL` summary row is present and mathematically correct
5. README updated to document the new command and the expected output

## Explicitly Out of Scope

- Historical trend data (this is a point-in-time snapshot)
- Copilot per-user usage detail (only seat-level totals)
- Cross-org repo counts by tier (tiering is a Pfizer-side classification not present in the API)
- Cost attribution to business units (that's a Phase 1 activity of Track D in the roadmap, not this baseline)
- Any modification to the existing `audit_workflows.py` or `ghas-audit.yml`

## Notes for the Implementer

Two things worth being aware of that trip people up on this kind of collection:

**The Copilot billing endpoint returns null seat_breakdown if Copilot is not enabled for the org.** Handle this — treat null as zero seats, not as an error.

**The `security_and_analysis` block only appears on the repo GET response if the authenticated user has admin access to the repo.** With `administration: read` on the App, this works. Without it, the field is absent and you cannot determine GHAS status. If `administration: read` is not granted, the script must fall back to a lower-fidelity check via `GET /orgs/{org}/settings/billing/advanced-security` which returns aggregate committer counts but no per-repo detail. Log clearly when this fallback is in use so the output is not misinterpreted.
