#!/usr/bin/env python3
"""GHAS Platform Metrics - v1.

Collects an enterprise-wide baseline of GHAS feature adoption per org and writes:
  - platform_metrics_by_org.csv   : one row per org, plus a TOTAL summary row
  - platform_metrics_by_repo.csv  : one row per repo (drill-down)

This is a separate capability from audit_workflows.py. It shares only the auth
pattern (GH_TOKEN -> requests.Session) and the org list. It does NOT modify or
import the audit script.

Design notes for maintainers:
  - Single file on purpose. Read it top to bottom.
  - The response-parsing functions (parse_*) are pure: they take a parsed JSON
    dict and return values, no network. That is what the unit tests exercise.
  - Network code is isolated in the middle (github_get, get_json, list_repos).
  - Every collector degrades gracefully. On 403 (permission denied) a metric is
    marked "n/a" so a reader can tell "we could not read this" apart from a real
    zero. On 404 (not enabled) a count metric is 0 and a boolean is false. One
    missing permission never aborts the run.

Usage:
    python3 collect_platform_metrics.py --org ORG --output-dir DIR \
        [--repo-limit N] [--skip-repo-scan]

    --repo-limit    cap the repo-level scan (test runs)
    --skip-repo-scan  produce only org-level metrics, skip iterating all repos

Auth:
    Reads the token from the GH_TOKEN environment variable. In production this is
    the GitHub App installation token minted by the workflow's OIDC step. The App
    needs contents/metadata/administration/copilot/organization_administration
    read. Where a grant is missing the affected metric is written as "n/a".
"""

import argparse
import csv
import datetime
import os
import sys
import time

import requests

GITHUB_API = "https://api.github.com"

# Sentinel for "we could not read this metric" (a permission gap), kept distinct
# from a real zero. Written verbatim to the CSV; excluded from the TOTAL row sum.
NA = "n/a"

# security_and_analysis feature -> the by-repo CSV column it drives. The value in
# GitHub's response is a nested {"status": "enabled"|"disabled"} block.
SECURITY_FEATURES = [
    ("advanced_security", "ghas_enabled"),
    ("secret_scanning", "secret_scanning_enabled"),
    ("secret_scanning_push_protection", "secret_scanning_push_protection_enabled"),
    ("dependabot_security_updates", "dependabot_security_updates_enabled"),
    ("secret_scanning_non_provider_patterns", "secret_scanning_non_provider_patterns"),
    ("secret_scanning_validity_checks", "secret_scanning_validity_checks"),
]


# --------------------------------------------------------------------------
# Parsing helpers (pure - no network, unit tested)
# --------------------------------------------------------------------------

def feature_enabled(security_and_analysis, feature):
    """True if a security_and_analysis feature block reports status "enabled".

    security_and_analysis may be None or missing the feature entirely (e.g. the
    caller lacks admin on the repo, so GitHub omits the block). Absence is False,
    not an error - the caller decides whether to escalate absence to n/a.
    """
    if not security_and_analysis:
        return False
    block = security_and_analysis.get(feature)
    if not isinstance(block, dict):
        return False
    return block.get("status") == "enabled"


def parse_repo_security(repo_obj):
    """Extract per-repo security fields from a GET /repos/{org}/{repo} object.

    Returns a dict of the by-repo CSV columns that come from the repo object.
    security_and_analysis may be absent (no admin) -> the feature booleans are
    reported as n/a so the output is not misread as "everything disabled".
    """
    sa = repo_obj.get("security_and_analysis")
    row = {
        "repo": repo_obj.get("name", ""),
        "visibility": repo_obj.get("visibility", ""),
        "archived": bool(repo_obj.get("archived", False)),
        "disabled": bool(repo_obj.get("disabled", False)),
        "default_branch": repo_obj.get("default_branch", ""),
        "pushed_at": repo_obj.get("pushed_at", "") or "",
        "updated_at": repo_obj.get("updated_at", "") or "",
    }
    for feature, column in SECURITY_FEATURES:
        row[column] = NA if sa is None else feature_enabled(sa, feature)
    return row


def parse_copilot_billing(billing_obj):
    """Extract Copilot seat totals from GET /orgs/{org}/copilot/billing.

    seat_breakdown is null when Copilot is not enabled for the org - treat that
    as zero seats, not an error (per the endpoint's documented behaviour).
    """
    breakdown = (billing_obj or {}).get("seat_breakdown") or {}
    active = breakdown.get("active_this_cycle", 0) or 0
    inactive = breakdown.get("inactive_this_cycle", 0) or 0
    pending = (breakdown.get("pending_invitation", 0) or 0) + \
              (breakdown.get("pending_cancellation", 0) or 0)
    return {
        "copilot_seats_total": breakdown.get("total", 0) or 0,
        "copilot_seats_active_this_cycle": active,
        "copilot_seats_inactive_this_cycle": inactive,
        "copilot_seats_pending": pending,
    }


def parse_actions_billing(billing_obj):
    """Extract Actions minutes from GET /orgs/{org}/settings/billing/actions."""
    b = billing_obj or {}
    return {
        "actions_minutes_used_total": b.get("total_minutes_used", 0) or 0,
        "actions_minutes_used_paid": b.get("total_paid_minutes_used", 0) or 0,
        "actions_minutes_included": b.get("included_minutes", 0) or 0,
    }


# --------------------------------------------------------------------------
# Network layer
# --------------------------------------------------------------------------

class ApiResult:
    """Outcome of a GET: the parsed JSON (or None) plus a classification the
    collectors branch on. status is one of "ok", "denied" (403), "not_found"
    (404), "error" (any other failure)."""

    def __init__(self, status, data=None, code=None):
        self.status = status
        self.data = data
        self.code = code

    @property
    def ok(self):
        return self.status == "ok"

    @property
    def denied(self):
        return self.status == "denied"


# Module-level call counter so we can log rate-limit status every 100 calls, the
# same "so a big org does not look hung" behaviour as the audit script.
_call_count = 0


def github_get(session, url, params=None):
    """GET with the audit script's rate-limit handling and one 5xx retry.

    When x-ratelimit-remaining drops below 50, sleep until x-ratelimit-reset.
    Retry once on 5xx. Logs rate-limit status every 100 calls.
    """
    global _call_count
    for attempt in range(2):
        resp = session.get(url, params=params, timeout=30)
        _call_count += 1
        remaining = resp.headers.get("x-ratelimit-remaining")
        if _call_count % 100 == 0 and remaining is not None:
            print(f"  [rate] {_call_count} calls made; {remaining} remaining", flush=True)
        if remaining is not None and remaining.isdigit() and int(remaining) < 50:
            reset = resp.headers.get("x-ratelimit-reset")
            if reset and reset.isdigit():
                sleep_for = max(0, int(reset) - int(time.time())) + 2
                print(f"  rate limit low ({remaining}); sleeping {sleep_for}s", flush=True)
                time.sleep(sleep_for)
        if resp.status_code >= 500 and attempt == 0:
            time.sleep(2)
            continue
        return resp
    return resp


def get_json(session, url, params=None):
    """GET one endpoint and classify the outcome as an ApiResult.

    This is the single choke point for graceful degradation: a 403 anywhere
    becomes ApiResult(denied) that a collector turns into n/a; a 404 becomes
    not_found that a collector turns into 0/false.
    """
    try:
        resp = github_get(session, url, params=params)
    except Exception as exc:
        print(f"  request error for {url}: {exc}", flush=True)
        return ApiResult("error")
    if resp.status_code == 200:
        try:
            return ApiResult("ok", resp.json(), 200)
        except ValueError:
            return ApiResult("error", code=200)
    if resp.status_code == 403:
        print(f"  403 permission denied: {url}", flush=True)
        return ApiResult("denied", code=403)
    if resp.status_code == 404:
        return ApiResult("not_found", code=404)
    print(f"  unexpected {resp.status_code} for {url}", flush=True)
    return ApiResult("error", code=resp.status_code)


def count_paginated(session, url, params=None):
    """Count items across all pages of a list endpoint. Returns an int, or NA on
    403. Used for the open-alert counts (we only need the count, not the items).
    """
    total = 0
    page = 1
    params = dict(params or {})
    while True:
        params.update({"per_page": 100, "page": page})
        res = get_json(session, url, params=params)
        if res.denied:
            return NA
        if not res.ok or not res.data:
            break
        total += len(res.data)
        if len(res.data) < 100:
            break
        page += 1
    return total


def list_repos_full(session, org, repo_limit=None):
    """List repo objects in an org (all types), paginated. Returns (repos, denied).

    Unlike the audit script's list_repos we keep the full objects (we need
    archived/disabled/visibility/security_and_analysis) and we keep archived
    repos too, since the by-org CSV reports an archived count. denied is True if
    the very first page was a 403 (org repos unreadable).
    """
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API}/orgs/{org}/repos"
        res = get_json(session, url, params={"per_page": 100, "page": page, "type": "all"})
        if res.denied and page == 1:
            return [], True
        if not res.ok or not res.data:
            break
        repos.extend(res.data)
        if repo_limit and len(repos) >= repo_limit:
            return repos[:repo_limit], False
        if len(res.data) < 100:
            break
        page += 1
    return repos, False


# --------------------------------------------------------------------------
# Org-level collection
# --------------------------------------------------------------------------

def collect_org_billing(session, org, metrics, skipped):
    """Fill Copilot / Actions / storage metrics into `metrics`. Records any metric
    group whose endpoint returned 403 in `skipped` so the summary can report it.
    """
    # Copilot seats
    res = get_json(session, f"{GITHUB_API}/orgs/{org}/copilot/billing")
    if res.denied:
        skipped.append("copilot_seats")
        for k in ("copilot_seats_total", "copilot_seats_active_this_cycle",
                  "copilot_seats_inactive_this_cycle", "copilot_seats_pending"):
            metrics[k] = NA
    elif res.status == "not_found":
        # Copilot not enabled for the org: zero seats, not an error.
        metrics.update(parse_copilot_billing(None))
    else:
        metrics.update(parse_copilot_billing(res.data if res.ok else None))

    # Actions minutes
    res = get_json(session, f"{GITHUB_API}/orgs/{org}/settings/billing/actions")
    if res.denied:
        skipped.append("actions_minutes")
        for k in ("actions_minutes_used_total", "actions_minutes_used_paid",
                  "actions_minutes_included"):
            metrics[k] = NA
    else:
        metrics.update(parse_actions_billing(res.data if res.ok else None))

    # Packages storage
    res = get_json(session, f"{GITHUB_API}/orgs/{org}/settings/billing/packages")
    if res.denied:
        skipped.append("packages_storage")
        metrics["packages_storage_gb"] = NA
    elif res.ok:
        metrics["packages_storage_gb"] = res.data.get("total_gigabytes_bandwidth_used", 0) or 0
    else:
        metrics["packages_storage_gb"] = 0

    # Shared storage
    res = get_json(session, f"{GITHUB_API}/orgs/{org}/settings/billing/shared-storage")
    if res.denied:
        skipped.append("shared_storage")
        metrics["shared_storage_estimated_paid"] = NA
    elif res.ok:
        metrics["shared_storage_estimated_paid"] = res.data.get("estimated_paid_storage_for_month", 0) or 0
    else:
        metrics["shared_storage_estimated_paid"] = 0


def collect_org_alerts(session, org, metrics, skipped):
    """Fill the three open-alert counts into `metrics`."""
    endpoints = [
        ("dependabot_alerts_open", f"{GITHUB_API}/orgs/{org}/dependabot/alerts"),
        ("secret_scanning_alerts_open", f"{GITHUB_API}/orgs/{org}/secret-scanning/alerts"),
        ("code_scanning_alerts_open", f"{GITHUB_API}/orgs/{org}/code-scanning/alerts"),
    ]
    for column, url in endpoints:
        count = count_paginated(session, url, params={"state": "open"})
        if count is NA:
            skipped.append(column)
        metrics[column] = count


# --------------------------------------------------------------------------
# Repo-level collection
# --------------------------------------------------------------------------

def collect_repo(session, org, repo_obj, collected_at):
    """Build one by-repo row and return it. repo_obj comes from the org repo
    list; we re-fetch the single repo only if the list object lacks the
    security_and_analysis block (the list endpoint sometimes omits it)."""
    if "security_and_analysis" not in repo_obj:
        name = repo_obj.get("name", "")
        res = get_json(session, f"{GITHUB_API}/repos/{org}/{name}")
        if res.ok:
            repo_obj = res.data
    row = parse_repo_security(repo_obj)
    repo = row["repo"]

    # CodeQL default setup: 200 -> configured, 404 -> not, 403 -> n/a
    res = get_json(session, f"{GITHUB_API}/repos/{org}/{repo}/code-scanning/default-setup")
    if res.denied:
        row["codeql_default_setup"] = NA
    elif res.ok:
        row["codeql_default_setup"] = (res.data.get("state") == "configured")
    else:
        row["codeql_default_setup"] = False

    # CodeQL workflow file present (codeql*.yml under .github/workflows)
    row["codeql_workflow_present"] = codeql_workflow_present(session, org, repo)

    # Dependabot config present: contents 200 -> present, 404 -> absent
    res = get_json(session, f"{GITHUB_API}/repos/{org}/{repo}/contents/.github/dependabot.yml")
    if res.denied:
        row["dependabot_config_present"] = NA
    else:
        row["dependabot_config_present"] = res.ok

    row["org"] = org
    row["collected_at"] = collected_at
    return row


def codeql_workflow_present(session, org, repo):
    """True if a codeql*.yml exists under .github/workflows. NA on 403."""
    url = f"{GITHUB_API}/repos/{org}/{repo}/contents/.github/workflows"
    res = get_json(session, url)
    if res.denied:
        return NA
    if not res.ok or not isinstance(res.data, list):
        return False
    for entry in res.data:
        name = (entry.get("name") or "").lower()
        if entry.get("type") == "file" and name.startswith("codeql") and \
                name.endswith((".yml", ".yaml")):
            return True
    return False


def aggregate_repo_rows(repo_rows):
    """Aggregate by-repo rows into the by-org security columns, including the
    public/private/internal breakdown for GHAS. A column is NA only if every
    repo reported NA (a blanket permission gap); otherwise NA rows are treated
    as "not enabled" for the count so partial reads still produce a number."""
    def count_true(column):
        vals = [r.get(column) for r in repo_rows]
        if vals and all(v is NA for v in vals):
            return NA
        return sum(1 for v in vals if v is True)

    private = [r for r in repo_rows if r.get("visibility") == "private"]
    internal = [r for r in repo_rows if r.get("visibility") == "internal"]

    def count_true_in(rows, column):
        vals = [r.get(column) for r in rows]
        if vals and all(v is NA for v in vals):
            return NA
        return sum(1 for v in vals if v is True)

    return {
        "ghas_enabled": count_true("ghas_enabled"),
        "ghas_enabled_private": count_true_in(private, "ghas_enabled"),
        "ghas_enabled_internal": count_true_in(internal, "ghas_enabled"),
        "secret_scanning_enabled": count_true("secret_scanning_enabled"),
        "secret_scanning_push_protection_enabled": count_true("secret_scanning_push_protection_enabled"),
        "dependabot_security_updates_enabled": count_true("dependabot_security_updates_enabled"),
        "dependabot_config_present": count_true("dependabot_config_present"),
        "codeql_default_setup": count_true("codeql_default_setup"),
        "codeql_workflow_present": count_true("codeql_workflow_present"),
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

BY_ORG_HEADER = [
    "org",
    "total_repos_active", "total_repos_archived",
    "public_repos", "private_repos", "internal_repos",
    "ghas_enabled", "ghas_enabled_private", "ghas_enabled_internal",
    "secret_scanning_enabled", "secret_scanning_push_protection_enabled",
    "dependabot_security_updates_enabled", "dependabot_config_present",
    "codeql_default_setup", "codeql_workflow_present",
    "dependabot_alerts_open", "secret_scanning_alerts_open", "code_scanning_alerts_open",
    "copilot_seats_total", "copilot_seats_active_this_cycle",
    "copilot_seats_inactive_this_cycle", "copilot_seats_pending",
    "actions_minutes_used_total", "actions_minutes_used_paid", "actions_minutes_included",
    "packages_storage_gb", "shared_storage_estimated_paid",
    "collected_at",
]

BY_REPO_HEADER = [
    "org", "repo", "visibility", "archived", "disabled",
    "ghas_enabled", "secret_scanning_enabled", "secret_scanning_push_protection_enabled",
    "dependabot_security_updates_enabled", "secret_scanning_non_provider_patterns",
    "secret_scanning_validity_checks",
    "codeql_default_setup", "codeql_workflow_present", "dependabot_config_present",
    "default_branch", "pushed_at", "updated_at",
    "collected_at",
]

# Columns in the by-org CSV that the TOTAL row sums (everything numeric, i.e.
# not org, not collected_at). NA cells are skipped in the sum.
TOTAL_NUMERIC_COLUMNS = [c for c in BY_ORG_HEADER if c not in ("org", "collected_at")]


def _cell(value):
    """Render a metric for the CSV: booleans as true/false, NA verbatim."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return value


def write_by_org(out_dir, org_metrics):
    path = os.path.join(out_dir, "platform_metrics_by_org.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(BY_ORG_HEADER)
        writer.writerow([_cell(org_metrics.get(c, "")) for c in BY_ORG_HEADER])
    return path


def write_by_repo(out_dir, repo_rows):
    path = os.path.join(out_dir, "platform_metrics_by_repo.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(BY_REPO_HEADER)
        for r in repo_rows:
            writer.writerow([_cell(r.get(c, "")) for c in BY_REPO_HEADER])
    return path


def total_row(org_rows):
    """Build the TOTAL summary row from a list of by-org metric dicts. Sums each
    numeric column across orgs, skipping NA cells so a permission gap in one org
    does not poison the enterprise total."""
    row = {"org": "TOTAL", "collected_at": ""}
    for column in TOTAL_NUMERIC_COLUMNS:
        acc = 0
        for m in org_rows:
            v = m.get(column)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                acc += v
        row[column] = acc
    return row


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def collect_org(session, org, out_dir, repo_limit=None, skip_repo_scan=False):
    """Collect all metrics for one org and write both CSVs. Returns the by-org
    metrics dict (so a caller merging orgs can build a TOTAL row)."""
    collected_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics = {"org": org, "collected_at": collected_at}
    skipped = []

    # Org-level: repos list drives the repo counts and the repo-level scan.
    repos, denied = list_repos_full(session, org, repo_limit)
    if denied:
        skipped.append("repos")
        for c in ("total_repos_active", "total_repos_archived",
                  "public_repos", "private_repos", "internal_repos"):
            metrics[c] = NA
    else:
        active = [r for r in repos if not r.get("archived") and not r.get("disabled")]
        metrics["total_repos_active"] = len(active)
        metrics["total_repos_archived"] = sum(1 for r in repos if r.get("archived"))
        metrics["public_repos"] = sum(1 for r in active if r.get("visibility") == "public")
        metrics["private_repos"] = sum(1 for r in active if r.get("visibility") == "private")
        metrics["internal_repos"] = sum(1 for r in active if r.get("visibility") == "internal")

    collect_org_alerts(session, org, metrics, skipped)
    collect_org_billing(session, org, metrics, skipped)

    # Repo-level scan (aggregated back into the by-org row).
    repo_rows = []
    if skip_repo_scan:
        print(f"  --skip-repo-scan set: org-level metrics only", flush=True)
        for c in ("ghas_enabled", "ghas_enabled_private", "ghas_enabled_internal",
                  "secret_scanning_enabled", "secret_scanning_push_protection_enabled",
                  "dependabot_security_updates_enabled", "dependabot_config_present",
                  "codeql_default_setup", "codeql_workflow_present"):
            metrics[c] = NA
    elif not denied:
        active = [r for r in repos if not r.get("archived") and not r.get("disabled")]
        for i, repo_obj in enumerate(active, 1):
            try:
                repo_rows.append(collect_repo(session, org, repo_obj, collected_at))
            except Exception as exc:
                print(f"  {org}/{repo_obj.get('name')}: skipping ({exc})", flush=True)
        metrics.update(aggregate_repo_rows(repo_rows))

    os.makedirs(out_dir, exist_ok=True)
    by_org_path = write_by_org(out_dir, metrics)
    by_repo_path = write_by_repo(out_dir, repo_rows)

    total_metrics = len(BY_ORG_HEADER) - 2  # excludes org, collected_at
    unique_skipped = sorted(set(skipped))
    collected = total_metrics - len(unique_skipped)
    skip_note = f"; {len(unique_skipped)} skipped due to permissions: {unique_skipped}" \
        if unique_skipped else ""
    print(
        f"[org={org}] collected {collected}/{total_metrics} metrics{skip_note}. "
        f"Wrote {by_org_path}, {by_repo_path} ({len(repo_rows)} repo rows).",
        flush=True,
    )
    return metrics


def build_session(token):
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ghas-platform-metrics/1.0",
    })
    return session


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect GHAS platform metrics for an org.")
    parser.add_argument("--org", required=True, help="GitHub org/login to scan")
    parser.add_argument("--output-dir", required=True, help="Directory for output CSVs")
    parser.add_argument("--repo-limit", type=int, default=None, help="Cap repos scanned (for testing)")
    parser.add_argument("--skip-repo-scan", action="store_true",
                        help="Org-level metrics only; skip iterating repos")
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: GH_TOKEN environment variable is not set.", file=sys.stderr)
        return 2

    session = build_session(token)
    collect_org(session, args.org, args.output_dir, args.repo_limit, args.skip_repo_scan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
