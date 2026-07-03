#!/usr/bin/env python3
"""GHAS Workflow Audit - v1.

Scans .github/workflows/*.yml files in a GitHub org and writes:
  - findings.csv          : security/quality findings
  - action_inventory.csv  : every action `uses:` reference, aggregated
  - summary.csv           : one-row scan summary for the org

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
# Major first-party vendors. If one of these is compromised the action pin is the
# least of our worries, so a version (tag) pin is acceptable and not flagged as
# unpinned. They are also treated as vetted owners.
MAJOR_VENDOR_OWNERS = {"aws-actions", "azure", "microsoft", "sonarsource", "sonarqube"}
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
    "reusable_workflow_call": "Review reusable-workflow call chains and ensure callees have equivalent guardrails.",
    "trigger_profile": "Review whether these triggers are appropriate for the workflow's risk profile.",
    "aws_secret": "AWS credentials are being deprecated; migrate to short-lived OIDC role assumption instead of static AWS secrets.",
    "app_rsa_key": "Move GitHub App RSA private-key usage to the App ACL model instead of storing the key as a workflow secret.",
}


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

class GitHubWorkflowLoader(yaml.SafeLoader):
    """Tolerant loader for GitHub workflow YAML.

    GitHub accepts a few expression patterns that generic YAML parsers treat as
    custom tags (for example `if: !cancelled()`). Unknown tags are preserved as
    plain values so the audit can continue instead of failing parse_error.
    """


def _construct_unknown_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


GitHubWorkflowLoader.add_multi_constructor("", _construct_unknown_tag)


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


def trigger_profile(parsed):
    """Return a compact trigger profile for reporting."""
    names = trigger_names(parsed)
    classes = []
    if {"pull_request", "pull_request_target"} & names:
        classes.append("pr")
    if "schedule" in names:
        classes.append("cron")
    if "push" in names:
        classes.append("push")
    if {"workflow_dispatch", "repository_dispatch"} & names:
        classes.append("manual_or_dispatch")
    if "workflow_run" in names:
        classes.append("workflow_run")
    if not classes:
        classes.append("other")
    return names, classes


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
    if owner in TIER1 or owner in TIER2 or owner in MAJOR_VENDOR_OWNERS:
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
        "scheduled": "no",
        "secrets_referenced": "no",
    }


# Matches explicit secret references like ${{ secrets.MY_TOKEN }} anywhere in
# the raw workflow text. Implicit access (auto-injected GITHUB_TOKEN, org/repo
# secrets available to the runner but never named) is NOT visible from the file
# and is intentionally out of scope here.
SECRET_REF_RE = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_-]*)")


def secret_names(raw):
    """Return the sorted set of explicitly referenced secret names."""
    if not raw:
        return []
    return sorted(set(SECRET_REF_RE.findall(raw)))


# Classifiers for referenced secret names, calibrated against the real Pfizer
# secrets naming breakdown (Tableau export) and the actual AWS names seen across
# all orgs. Matching is done on a normalised (uppercased, separators stripped)
# form of the secret name so AWS_ACCESS_KEY, AWS-ACCESS-KEY and awsAccessKey all
# match the same way.
#
#  - AWS: only STATIC CREDENTIAL names are flagged (deprecation targets). Config
#    such as region / account / bucket, and especially role / ARN / OIDC names
#    (which are the *preferred* short-lived pattern, not a static key), are NOT
#    flagged -- per security review, those are expected and not an issue.
#  - GitHub App RSA private keys should move to the App ACL model, so secrets
#    that look like an app private key / PEM are surfaced as migration targets.
AWS_SCOPE_RE = re.compile(r"AWS")
# Credential indicators: a secret/access key, session token, password or
# credential bundle. KEY$ catches AWS_KEY / DEPLOY_KEY / *_SECRET_KEY style
# names; ACCESSKEY / ACCESSID catch access-key identifiers; AWSAK / AWSSK catch
# the AK/SK abbreviations.
AWS_CRED_RE = re.compile(
    r"(SECRET|ACCESSKEY|ACCESSID|TOKEN|PASSWORD|PASSWD|CRED|AWSAK|AWSSK|KEY$)"
)
APP_RSA_SECRET_RE = re.compile(
    r"(PRIVATEKEY|RSA|PEM|APPKEY|APPPRIVATE|APPCERT|GITHUBAPPKEY|GHAPPKEY)"
)


def _normalise_secret(name):
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def classify_secrets(names):
    """Split referenced secret names into {'aws': [...], 'app_rsa': [...]}."""
    aws, app_rsa = [], []
    for n in names:
        norm = _normalise_secret(n)
        if AWS_SCOPE_RE.search(norm) and AWS_CRED_RE.search(norm):
            aws.append(n)
        if APP_RSA_SECRET_RE.search(norm):
            app_rsa.append(n)
    return {"aws": aws, "app_rsa": app_rsa}


# Ordered low->high. 'info' is non-security context and is never escalated.
SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def _escalate(severity):
    """Bump a security severity one level (capped at critical)."""
    if severity not in SEVERITY_ORDER:
        return severity
    idx = SEVERITY_ORDER.index(severity)
    return SEVERITY_ORDER[min(idx + 1, len(SEVERITY_ORDER) - 1)]


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


def _is_pin_exempt_owner(owner):
    """Owners we never flag for unpinned/branch refs: native GitHub + Pfizer-internal.

    Per Pfizer policy these actions are intentionally not SHA-pinned so they can
    pick up upstream updates.
    """
    if not owner:
        return False
    if owner in TIER1:
        return True
    if owner.startswith(INTERNAL_PREFIX):
        return True
    return False


def _is_version_pin_exempt_owner(owner):
    """Major first-party vendors exempt from the unpinned-tag check when version-pinned.

    A tag like `aws-actions/configure-aws-credentials@v4` is acceptable: if AWS /
    Microsoft / SonarQube were compromised, the action pin would be the least of
    our concerns. Branch refs are NOT covered here and are still flagged.
    """
    if not owner:
        return False
    return owner in MAJOR_VENDOR_OWNERS


def check_unpinned_action_tag(parsed, raw, repo, path):
    findings = []
    for job_name, uses in _iter_step_uses(parsed):
        info = parse_uses(uses)
        if info["pin_type"] == "tag":
            if _is_pin_exempt_owner(info["owner"]):
                continue
            if _is_version_pin_exempt_owner(info["owner"]):
                continue
            findings.append(_finding(parsed, repo, path, job_name, "unpinned_action_tag", "high",
                                     f"uses: {uses}"))
    return findings


def check_action_on_branch(parsed, raw, repo, path):
    findings = []
    for job_name, uses in _iter_step_uses(parsed):
        info = parse_uses(uses)
        if info["pin_type"] == "branch" and info["ref"]:
            if _is_pin_exempt_owner(info["owner"]):
                continue
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


# Inline package installs are only risky when they pull UNPINNED packages from a
# registry at run time. Per security review the following are NOT issues and are
# suppressed: commented-out lines; installs from a manifest/lockfile
# (pip -r requirements.txt, pip install .); pip/setuptools/wheel bootstrap; and
# anything where every package is version-pinned (== for pip, @version for
# npm/yarn).
SAFE_BOOTSTRAP_PKGS = {"pip", "setuptools", "wheel"}


def _tokens_after(stripped, pattern):
    """Non-flag tokens following an install verb (e.g. package names)."""
    parts = re.split(pattern, stripped, maxsplit=1)
    if len(parts) < 2:
        return []
    return [t for t in parts[-1].split() if not t.startswith("-")]


def _strip_pkg_name(tok):
    return re.split(r"[=<>~!@\[]", tok, maxsplit=1)[0].lower()


def _all_pinned_at(toks):
    """npm/yarn: every package token carries an @version (not just a leading
    scope @ like @actions/core)."""
    return bool(toks) and all(t.rfind("@") > 0 for t in toks)


def _inline_install_is_safe(stripped):
    s = stripped.strip()
    if s.startswith("#"):
        return True
    # Collapse ${{ ... }} expressions (which may contain spaces) to a single
    # token so a pinned version like pkg@${{ env.VERSION }} stays one piece.
    s = re.sub(r"\$\{\{.*?\}\}", "EXPR", s)
    if re.search(r"\bpip\d?\s+install\b", s):
        if re.search(r"\bpip\d?\s+install\b[^\n]*\s(?:-r|--requirement)\b", s):
            return True
        if re.search(r"\bpip\d?\s+install\s+\.", s):
            return True
        toks = _tokens_after(s, r"\bpip\d?\s+install\b")
        if any(t == "." or t.startswith(("./", ".\\")) for t in toks):
            return True
        names = [_strip_pkg_name(t) for t in toks]
        if names and all(n in SAFE_BOOTSTRAP_PKGS for n in names):
            return True
        if toks and all("==" in t for t in toks):
            return True
        return False
    if re.search(r"\bnpm\s+(?:install|i)\b", s):
        return _all_pinned_at(_tokens_after(s, r"\bnpm\s+(?:install|i)\b"))
    if re.search(r"\byarn\s+add\b", s):
        return _all_pinned_at(_tokens_after(s, r"\byarn\s+add\b"))
    if re.search(r"\bnpx\b", s):
        return _all_pinned_at(_tokens_after(s, r"\bnpx\b"))
    return False


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
                hit = stripped
            if hit and not _inline_install_is_safe(stripped):
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


def check_reusable_workflow_call(parsed, raw, repo, path):
    findings = []
    for job_name, job in iter_jobs(parsed):
        uses = job.get("uses")
        if not isinstance(uses, str):
            continue
        info = parse_uses(uses)
        if info["repo_path"].endswith((".yml", ".yaml")):
            findings.append(_finding(parsed, repo, path, job_name, "reusable_workflow_call", "info",
                                     f"job '{job_name}' calls {uses}"))
    return findings


def check_trigger_profile(parsed, raw, repo, path):
    names, classes = trigger_profile(parsed)
    if not names:
        return [_finding(parsed, repo, path, None, "trigger_profile", "info", "triggers: none")]
    return [_finding(parsed, repo, path, None, "trigger_profile", "info",
                     f"triggers: {', '.join(sorted(names))}; classes: {', '.join(classes)}")]


def check_aws_secret(parsed, raw, repo, path):
    """Flag workflows that reference AWS-credential secrets (deprecation target)."""
    cats = classify_secrets(secret_names(raw))
    if not cats["aws"]:
        return []
    return [_finding(parsed, repo, path, None, "aws_secret", "high",
                     "AWS secret(s): " + ", ".join(cats["aws"]))]


def check_app_rsa_key(parsed, raw, repo, path):
    """Flag workflows using a GitHub App RSA private key (move to App ACL)."""
    cats = classify_secrets(secret_names(raw))
    if not cats["app_rsa"]:
        return []
    return [_finding(parsed, repo, path, None, "app_rsa_key", "high",
                     "App RSA key secret(s): " + ", ".join(cats["app_rsa"]))]


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
    check_reusable_workflow_call,
    check_trigger_profile,
    check_aws_secret,
    check_app_rsa_key,
]


def run_all_checks(parsed, raw, repo, path):
    findings = []
    for check in CHECKS:
        try:
            findings.extend(check(parsed, raw, repo, path))
        except Exception as exc:  # a buggy check must never kill the scan
            findings.append(_finding(parsed if isinstance(parsed, dict) else {}, repo, path, None,
                                     check.__name__, "info", f"check error: {exc}"))
    # Cron/scheduled workflows run unattended (no PR review, nobody watching the
    # run), so they are held to a stricter standard: flag them and escalate the
    # severity of every security finding one level.
    _, classes = trigger_profile(parsed)
    is_cron = "cron" in classes
    # Workflows that explicitly reference secrets are a higher-value target, so
    # they act as a risk amplifier too (same escalation treatment as cron).
    secrets = secret_names(raw)
    uses_secrets = bool(secrets)
    for f in findings:
        f["scheduled"] = "yes" if is_cron else "no"
        f["secrets_referenced"] = "yes" if uses_secrets else "no"
        reasons = []
        if is_cron:
            reasons.append("scheduled/cron")
        if uses_secrets:
            reasons.append("uses secrets")
        if reasons:
            bumped = _escalate(f["severity"])
            if bumped != f["severity"]:
                f["severity"] = bumped
                f["evidence"] = (f["evidence"] + f" [escalated: {', '.join(reasons)}]")[:200]
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


def repo_default_is_write(session, org, repo, cache):
    """Return True if the repo's default workflow token is read-write, False if
    read-only, None if it could not be determined. Cached per repo.

    A missing-permissions finding only matters when the default token is write;
    if the repo default is read-only the workflow inherits least privilege so the
    finding is noise. Needs App permission administration:read.
    """
    if repo in cache:
        return cache[repo]
    url = f"{GITHUB_API}/repos/{org}/{repo}/actions/permissions/workflow"
    try:
        resp = github_get(session, url)
    except Exception:
        cache[repo] = None
        return None
    if resp.status_code != 200:
        cache[repo] = None
        return None
    result = (resp.json().get("default_workflow_permissions") == "write")
    cache[repo] = result
    return result


def refine_missing_permissions(session, org, findings, cache):
    """Drop missing_permissions findings for repos whose default token is
    read-only; keep them when write or unknown (fail-safe). Only repos that
    already have a finding are queried, each at most once via the cache."""
    kept = []
    for f in findings:
        if f.get("check") == "missing_permissions" and \
                repo_default_is_write(session, org, f["repo"], cache) is False:
            continue
        kept.append(f)
    return kept


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
                   "check", "severity", "scheduled", "secrets_referenced",
                   "evidence", "recommendation"]
INVENTORY_HEADER = ["action_ref", "owner", "pin_type", "is_vetted", "kind",
                    "repo_count", "total_uses"]
SUMMARY_HEADER = ["org", "repos_scanned", "workflows_scanned",
                  "repos_with_findings", "total_findings",
                  "critical", "high", "medium", "low", "info",
                  "distinct_actions"]


def write_findings(out_dir, org, findings):
    path = os.path.join(out_dir, "findings.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FINDINGS_HEADER)
        for f in findings:
            writer.writerow([
                org, f["repo"], f["workflow_file"], f["workflow_name"], f["job"],
                f["check"], f["severity"], f.get("scheduled", "no"),
                f.get("secrets_referenced", "no"), f["evidence"],
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


def write_summary(out_dir, org, repos_scanned, workflows_scanned,
                  findings, inventory, severity_counts):
    """Write a one-row per-org summary CSV.

    repos_with_findings counts unique repos that produced at least one finding,
    so a clean repo contributes 0 rows here (it's already silent in findings.csv).
    """
    path = os.path.join(out_dir, "summary.csv")
    repos_with_findings = len({f["repo"] for f in findings if f.get("repo")})
    row = [
        org,
        repos_scanned,
        workflows_scanned,
        repos_with_findings,
        len(findings),
        severity_counts.get("critical", 0),
        severity_counts.get("high", 0),
        severity_counts.get("medium", 0),
        severity_counts.get("low", 0),
        severity_counts.get("info", 0),
        len(inventory),
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SUMMARY_HEADER)
        writer.writerow(row)
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
                parsed = yaml.load(content, Loader=GitHubWorkflowLoader)
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

    perm_cache = {}
    all_findings = refine_missing_permissions(session, org, all_findings, perm_cache)
    severity_counts = {}
    for f in all_findings:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

    findings_path = write_findings(out_dir, org, all_findings)
    inventory_path = write_inventory(out_dir, inventory)
    summary_path = write_summary(out_dir, org, repos_scanned, workflows_scanned,
                                 all_findings, inventory, severity_counts)

    sev_summary = ", ".join(f"{k}={v}" for k, v in sorted(severity_counts.items())) or "none"
    print(
        f"\nSUMMARY [{org}]: scanned {repos_scanned} repo(s), {workflows_scanned} workflow file(s); "
        f"{len(all_findings)} finding(s) by severity ({sev_summary}); "
        f"{len(inventory)} distinct action reference(s). "
        f"Wrote {findings_path}, {inventory_path}, {summary_path}.",
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
