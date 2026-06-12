#!/usr/bin/env python3
"""GHAS Workflow Audit - v1.

Scans .github/workflows/*.yml files in a GitHub org and writes two CSVs:
  - findings.csv          : security/quality findings
  - action_inventory.csv  : every action `uses:` reference, aggregated

Design notes for maintainers:
  - Single file on purpose. Read it top to bottom.
  - Each check is a small pure function: check_x(parsed, raw, repo, path) -> list[dict].
    To add a check later: write one function, add it to CHECKS, add a line to
    RECOMMENDATIONS. That's it.
  - Network code is isolated at the bottom (github_get, list_repos, ...).
    The check functions never touch the network, so they are trivially testable.

Usage:
    python3 audit_workflows.py --org ORG --output-dir DIR [--repo-limit N]

Auth:
    Reads the token from the GH_TOKEN environment variable. In production this is
    the GitHub App installation token minted by the workflow's OIDC step.
"""

import argparse
import base64
import csv
import os
import re
import sys
import time

import requests
import yaml

GITHUB_API = "https://api.github.com"

# Action owners we trust. Anything else is flagged unvetted_action_owner.
TIER1 = {"actions", "github"}
TIER2 = {"aws-actions", "azure", "google-github-actions", "docker", "hashicorp", "codecov"}
# Internal owners: any owner whose name starts with "pfizer" is trusted.
INTERNAL_PREFIX = "pfizer"

DEPRECATED_RUNNERS = {"ubuntu-18.04", "ubuntu-20.04", "macos-11", "macos-12", "windows-2019"}

# One fixed recommendation sentence per check id.
RECOMMENDATIONS = {
    "parse_error": "Fix the YAML syntax so the workflow can be parsed and audited.",
    "missing_permissions": "Declare an explicit least-privilege `permissions:` block at the workflow or job level.",
    "write_all_permissions": "Replace `write-all` with the specific minimum permissions the workflow needs.",
    "unpinned_action_tag": "Pin the action to a full 40-character commit SHA instead of a mutable tag.",
    "action_on_branch": "Pin the action to a full 40-character commit SHA instead of a branch reference.",
    "unvetted_action_owner": "Use a vetted action owner or add this owner to the enterprise allowlist after review.",
    "inline_package_install": "Install pinned dependencies from a manifest/lockfile instead of inline package installs.",
    "curl_pipe_shell": "Download, verify (checksum/signature), then execute scripts instead of piping straight to a shell.",
    "pull_request_target": "Avoid `pull_request_target`, or never check out and run untrusted PR head code with it.",
    "untrusted_context_in_run": "Pass untrusted context through an `env:` variable and quote it; never inline it into `run:`.",
    "deprecated_runner": "Move to a supported runner image (e.g. ubuntu-latest / ubuntu-22.04).",
}


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

def get_triggers(parsed):
    """Return the value of the workflow `on:` key.

    PyYAML quirk: a bare `on:` key parses to the boolean True, so we check both.
    """
    if not isinstance(parsed, dict):
        return None
    if "on" in parsed:
        return parsed["on"]
    if True in parsed:
        return parsed[True]
    return None


def trigger_names(parsed):
    """Return the set of trigger names regardless of on: shape (str/list/dict)."""
    triggers = get_triggers(parsed)
    if triggers is None:
        return set()
    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return {str(t) for t in triggers}
    if isinstance(triggers, dict):
        return {str(k) for k in triggers.keys()}
    return set()


def iter_jobs(parsed):
    """Yield (job_name, job_dict) for every job in the workflow."""
    if not isinstance(parsed, dict):
        return
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        return
    for name, job in jobs.items():
        if isinstance(job, dict):
            yield name, job


def iter_steps(job):
    """Yield step dicts for a job."""
    steps = job.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                yield step


def runs_on_labels(job):
    """Return runs-on as a list of label strings, handling str/list/dict shapes."""
    ro = job.get("runs-on")
    if ro is None:
        return []
    if isinstance(ro, str):
        return [ro]
    if isinstance(ro, list):
        return [str(x) for x in ro]
    if isinstance(ro, dict):
        labels = ro.get("labels", [])
        if isinstance(labels, str):
            labels = [labels]
        out = [str(x) for x in labels]
        if ro.get("group"):
            out.append(str(ro["group"]))
        return out
    return []


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SEMVER_TAG_RE = re.compile(r"^v?\d")


def classify_ref(ref):
    """Classify a git ref used to pin an action."""
    if SHA_RE.match(ref):
        return "sha"
    if SEMVER_TAG_RE.match(ref):
        return "tag"
    return "branch"


def parse_uses(uses):
    """Parse a `uses:` string into structured fields.

    Returns a dict: {ref_str, owner, repo_path, ref, pin_type}
    pin_type is one of: sha | tag | branch | local | docker
    """
    uses = uses.strip()
    if uses.startswith("./") or uses.startswith("../") or uses == "." or uses.startswith(".\\"):
        return {"ref_str": uses, "owner": "", "repo_path": uses, "ref": "", "pin_type": "local"}
    if uses.startswith("docker://"):
        return {"ref_str": uses, "owner": "", "repo_path": uses, "ref": "", "pin_type": "docker"}

    if "@" in uses:
        repo_path, ref = uses.rsplit("@", 1)
    else:
        repo_path, ref = uses, ""
    owner = repo_path.split("/")[0] if "/" in repo_path else repo_path
    pin_type = classify_ref(ref) if ref else "branch"
    return {"ref_str": uses, "owner": owner, "repo_path": repo_path, "ref": ref, "pin_type": pin_type}


def owner_is_vetted(owner):
    if not owner:
        return True  # local/docker have no owner to vet
    if owner in TIER1 or owner in TIER2:
        return True
    if owner.startswith(INTERNAL_PREFIX):
        return True
    return False


def iter_run_blocks(parsed):
    """Yield (job_name, run_text) for every step that has a `run:` string."""
    for job_name, job in iter_jobs(parsed):
        for step in iter_steps(job):
            run = step.get("run")
            if isinstance(run, str):
                yield job_name, run


# --------------------------------------------------------------------------
# Checks (each: parsed, raw, repo, path -> list[finding dict])
# A finding dict carries: workflow_name, job, check, severity, evidence.
# org / workflow_file / recommendation are filled in by the writer.
# --------------------------------------------------------------------------

def _finding(parsed, repo, path, job, check, severity, evidence):
    name = parsed.get("name") if isinstance(parsed, dict) else None
    return {
        "repo": repo,
        "workflow_file": path,
        "workflow_name": name or os.path.basename(path),
        "job": job or "",
        "check": check,
        "severity": severity,
        "evidence": str(evidence)[:200],
    }


def check_missing_permissions(parsed, raw, repo, path):
    if not isinstance(parsed, dict):
        return []
    top_has = "permissions" in parsed
    if top_has:
        return []
    # Top level missing: flag if any job also lacks job-level permissions.
    for job_name, job in iter_jobs(parsed):
        if "permissions" not in job:
            return [_finding(parsed, repo, path, None, "missing_permissions", "high",
                             f"workflow '{parsed.get('name') or os.path.basename(path)}' has no permissions block")]
    return []


def check_write_all_permissions(parsed, raw, repo, path):
    findings = []
    if not isinstance(parsed, dict):
        return findings
    if parsed.get("permissions") == "write-all":
        findings.append(_finding(parsed, repo, path, None, "write_all_permissions", "critical",
                                 "permissions: write-all (workflow level)"))
    for job_name, job in iter_jobs(parsed):
        if job.get("permissions") == "write-all":
            findings.append(_finding(parsed, repo, path, job_name, "write_all_permissions", "critical",
                                     "permissions: write-all (job level)"))
    return findings


def _iter_step_uses(parsed):
    """Yield (job_name, uses_str) for step-level uses only (not job-level)."""
    for job_name, job in iter_jobs(parsed):
        for step in iter_steps(job):
            uses = step.get("uses")
            if isinstance(uses, str):
                yield job_name, uses


def check_unpinned_action_tag(parsed, raw, repo, path):
    findings = []
    for job_name, uses in _iter_step_uses(parsed):
        info = parse_uses(uses)
        if info["pin_type"] == "tag":
            findings.append(_finding(parsed, repo, path, job_name, "unpinned_action_tag", "high",
                                     f"uses: {uses}"))
    return findings


def check_action_on_branch(parsed, raw, repo, path):
    findings = []
    for job_name, uses in _iter_step_uses(parsed):
        info = parse_uses(uses)
        if info["pin_type"] == "branch" and info["ref"]:
            findings.append(_finding(parsed, repo, path, job_name, "action_on_branch", "critical",
                                     f"uses: {uses}"))
    return findings


def check_unvetted_action_owner(parsed, raw, repo, path):
    findings = []
    for job_name, uses in _iter_step_uses(parsed):
        info = parse_uses(uses)
        if info["pin_type"] in ("local", "docker"):
            continue
        if not owner_is_vetted(info["owner"]):
            findings.append(_finding(parsed, repo, path, job_name, "unvetted_action_owner", "high",
                                     f"uses: {uses}"))
    return findings


# run: text checks ----------------------------------------------------------

def _npm_install_is_pkg(line):
    """True only if it's `npm install <pkg>` / `npm i <pkg>`, not bare or `npm ci`."""
    m = re.search(r"\bnpm\s+(install|i)\b(.*)", line)
    if not m:
        return False
    rest = m.group(2).strip()
    if not rest:
        return False  # bare `npm install`
    # ignore pure flags like `npm install --production`
    tokens = [t for t in rest.split() if not t.startswith("-")]
    return len(tokens) > 0


def check_inline_package_install(parsed, raw, repo, path):
    findings = []
    for job_name, run in iter_run_blocks(parsed):
        for line in run.splitlines():
            stripped = line.strip()
            hit = None
            if re.search(r"\bnpm\s+(install|i)\b", stripped) and _npm_install_is_pkg(stripped):
                hit = stripped
            elif re.search(r"\bnpx\s+\S+", stripped):
                hit = stripped
            elif re.search(r"\byarn\s+add\s+\S+", stripped):
                hit = stripped
            elif re.search(r"\bpip\d?\s+install\b", stripped):
                if (not re.search(r"\bpip\d?\s+install\s+-r\b", stripped)
                        and not re.search(r"\bpip\d?\s+install\s+\.", stripped)
                        and "==" not in stripped):
                    hit = stripped
            if hit:
                findings.append(_finding(parsed, repo, path, job_name, "inline_package_install", "medium",
                                         hit))
    return findings


CURL_PIPE_RE = re.compile(
    r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b"
    r"|(curl|wget)\b[^\n|]*\|\s*(python\d?|node)\b",
    re.IGNORECASE,
)


def check_curl_pipe_shell(parsed, raw, repo, path):
    findings = []
    for job_name, run in iter_run_blocks(parsed):
        for line in run.splitlines():
            if CURL_PIPE_RE.search(line):
                findings.append(_finding(parsed, repo, path, job_name, "curl_pipe_shell", "critical",
                                         line.strip()))
    return findings


def check_pull_request_target(parsed, raw, repo, path):
    if "pull_request_target" not in trigger_names(parsed):
        return []
    evidence = "trigger: pull_request_target"
    # Escalate evidence if a checkout pulls the PR head (pwn-request pattern).
    for job_name, job in iter_jobs(parsed):
        for step in iter_steps(job):
            uses = step.get("uses", "")
            with_ = step.get("with") or {}
            ref = with_.get("ref", "") if isinstance(with_, dict) else ""
            if isinstance(uses, str) and "checkout" in uses and "github.event.pull_request.head" in str(ref):
                evidence = "pull_request_target + checkout of PR head ref (pwn-request pattern)"
    return [_finding(parsed, repo, path, None, "pull_request_target", "critical", evidence)]


UNTRUSTED_CONTEXTS = [
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.comment.body",
    "github.head_ref",
    "github.event.head_commit.message",
]
EXPR_RE = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)


def check_untrusted_context_in_run(parsed, raw, repo, path):
    findings = []
    for job_name, run in iter_run_blocks(parsed):
        for expr in EXPR_RE.findall(run):
            for ctx in UNTRUSTED_CONTEXTS:
                if ctx in expr:
                    findings.append(_finding(parsed, repo, path, job_name, "untrusted_context_in_run", "high",
                                             "${{" + expr.strip() + "}}"))
                    break
    return findings


def check_deprecated_runner(parsed, raw, repo, path):
    findings = []
    for job_name, job in iter_jobs(parsed):
        for label in runs_on_labels(job):
            if label in DEPRECATED_RUNNERS:
                findings.append(_finding(parsed, repo, path, job_name, "deprecated_runner", "high",
                                         f"runs-on: {label}"))
    return findings


CHECKS = [
    check_missing_permissions,
    check_write_all_permissions,
    check_unpinned_action_tag,
    check_action_on_branch,
    check_unvetted_action_owner,
    check_inline_package_install,
    check_curl_pipe_shell,
    check_pull_request_target,
    check_untrusted_context_in_run,
    check_deprecated_runner,
]


def run_all_checks(parsed, raw, repo, path):
    findings = []
    for check in CHECKS:
        try:
            findings.extend(check(parsed, raw, repo, path))
        except Exception as exc:  # a buggy check must never kill the scan
            findings.append(_finding(parsed if isinstance(parsed, dict) else {}, repo, path, None,
                                     check.__name__, "info", f"check error: {exc}"))
    return findings


# --------------------------------------------------------------------------
# Action inventory
# --------------------------------------------------------------------------

def collect_uses(parsed):
    """Yield (ref_str, owner, pin_type, kind) for every uses: in the workflow.

    kind: 'reusable_workflow' for job-level uses ending in .yml/.yaml, else 'action'.
    """
    for job_name, job in iter_jobs(parsed):
        # job-level uses (reusable workflow call)
        juses = job.get("uses")
        if isinstance(juses, str):
            info = parse_uses(juses)
            path_part = info["repo_path"]
            kind = "reusable_workflow" if path_part.endswith((".yml", ".yaml")) else "action"
            yield info["ref_str"], info["owner"], info["pin_type"], kind
        # step-level uses (actions)
        for step in iter_steps(job):
            suses = step.get("uses")
            if isinstance(suses, str):
                info = parse_uses(suses)
                yield info["ref_str"], info["owner"], info["pin_type"], "action"


# --------------------------------------------------------------------------
# Network layer
# --------------------------------------------------------------------------

def github_get(session, url, params=None):
    """GET with simple rate-limit handling and one 5xx retry."""
    for attempt in range(2):
        resp = session.get(url, params=params, timeout=30)
        remaining = resp.headers.get("x-ratelimit-remaining")
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


def list_repos(session, org, repo_limit=None):
    """List active (non-archived, non-disabled) repos in an org."""
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API}/orgs/{org}/repos"
        resp = github_get(session, url, params={"per_page": 100, "page": page, "type": "all"})
        if resp.status_code != 200:
            print(f"  failed to list repos for {org} (page {page}): {resp.status_code}", flush=True)
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            if r.get("archived") or r.get("disabled"):
                continue
            repos.append(r["name"])
            if repo_limit and len(repos) >= repo_limit:
                return repos
        page += 1
    return repos


def list_workflow_files(session, org, repo):
    """Return list of (path, name) for files in .github/workflows. [] if none."""
    url = f"{GITHUB_API}/repos/{org}/{repo}/contents/.github/workflows"
    resp = github_get(session, url)
    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        print(f"  {org}/{repo}: workflows dir error {resp.status_code}", flush=True)
        return []
    out = []
    for entry in resp.json():
        if entry.get("type") == "file" and entry.get("name", "").endswith((".yml", ".yaml")):
            out.append((entry["path"], entry["name"]))
    return out


def fetch_file_content(session, org, repo, path):
    url = f"{GITHUB_API}/repos/{org}/{repo}/contents/{path}"
    resp = github_get(session, url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("encoding") == "base64" and data.get("content"):
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content")


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

FINDINGS_HEADER = ["org", "repo", "workflow_file", "workflow_name", "job",
                   "check", "severity", "evidence", "recommendation"]
INVENTORY_HEADER = ["action_ref", "owner", "pin_type", "is_vetted", "kind",
                    "repo_count", "total_uses"]


def write_findings(out_dir, org, findings):
    path = os.path.join(out_dir, "findings.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FINDINGS_HEADER)
        for f in findings:
            writer.writerow([
                org, f["repo"], f["workflow_file"], f["workflow_name"], f["job"],
                f["check"], f["severity"], f["evidence"],
                RECOMMENDATIONS.get(f["check"], ""),
            ])
    return path


def write_inventory(out_dir, inventory):
    """inventory: {ref_str: {owner, pin_type, kind, is_vetted, repos:set, total:int}}"""
    path = os.path.join(out_dir, "action_inventory.csv")
    rows = []
    for ref, info in inventory.items():
        rows.append([
            ref, info["owner"], info["pin_type"], str(info["is_vetted"]).lower(),
            info["kind"], len(info["repos"]), info["total"],
        ])
    rows.sort(key=lambda r: r[6], reverse=True)  # total_uses desc
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(INVENTORY_HEADER)
        writer.writerows(rows)
    return path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def audit_org(session, org, out_dir, repo_limit=None):
    os.makedirs(out_dir, exist_ok=True)
    all_findings = []
    inventory = {}  # ref_str -> aggregate
    severity_counts = {}
    repos_scanned = 0
    workflows_scanned = 0

    repos = list_repos(session, org, repo_limit)
    print(f"{org}: {len(repos)} active repo(s) to scan", flush=True)

    for repo in repos:
        repos_scanned += 1
        try:
            files = list_workflow_files(session, org, repo)
        except Exception as exc:
            print(f"  {org}/{repo}: listing error, skipping: {exc}", flush=True)
            continue

        for path, name in files:
            try:
                content = fetch_file_content(session, org, repo, path)
            except Exception as exc:
                print(f"  {org}/{repo}/{path}: fetch error, skipping: {exc}", flush=True)
                continue
            if content is None:
                continue
            workflows_scanned += 1

            try:
                parsed = yaml.safe_load(content)
            except Exception as exc:
                all_findings.append({
                    "repo": repo, "workflow_file": path,
                    "workflow_name": os.path.basename(path), "job": "",
                    "check": "parse_error", "severity": "info",
                    "evidence": str(exc)[:200],
                })
                severity_counts["info"] = severity_counts.get("info", 0) + 1
                continue

            if not isinstance(parsed, dict):
                continue

            for f in run_all_checks(parsed, content, repo, path):
                all_findings.append(f)
                severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

            for ref, owner, pin_type, kind in collect_uses(parsed):
                agg = inventory.get(ref)
                if agg is None:
                    agg = {"owner": owner, "pin_type": pin_type, "kind": kind,
                           "is_vetted": owner_is_vetted(owner), "repos": set(), "total": 0}
                    inventory[ref] = agg
                agg["repos"].add(repo)
                agg["total"] += 1

    findings_path = write_findings(out_dir, org, all_findings)
    inventory_path = write_inventory(out_dir, inventory)

    sev_summary = ", ".join(f"{k}={v}" for k, v in sorted(severity_counts.items())) or "none"
    print(
        f"\nSUMMARY [{org}]: scanned {repos_scanned} repo(s), {workflows_scanned} workflow file(s); "
        f"{len(all_findings)} finding(s) by severity ({sev_summary}); "
        f"{len(inventory)} distinct action reference(s). "
        f"Wrote {findings_path} and {inventory_path}.",
        flush=True,
    )
    return all_findings, inventory


def build_session(token):
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ghas-workflow-audit/1.0",
    })
    return session


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit GitHub Actions workflow files in an org.")
    parser.add_argument("--org", required=True, help="GitHub org/login to scan")
    parser.add_argument("--output-dir", required=True, help="Directory for output CSVs")
    parser.add_argument("--repo-limit", type=int, default=None, help="Cap repos scanned (for testing)")
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: GH_TOKEN environment variable is not set.", file=sys.stderr)
        return 2

    session = build_session(token)
    audit_org(session, args.org, args.output_dir, args.repo_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
