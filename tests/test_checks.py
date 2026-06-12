"""Unit tests for the audit checks.

The checks are pure functions over parsed YAML, so no API mocking is needed.
We run every check against the insecure fixture (should fire) and the clean
fixture (should stay quiet).
"""

import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

import audit_workflows as aw  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        raw = fh.read()
    return yaml.safe_load(raw), raw


def checks_fired(name):
    parsed, raw = load(name)
    findings = aw.run_all_checks(parsed, raw, "repo", name)
    return {f["check"] for f in findings}


# Checks expected to fire on the insecure fixture (per the build brief).
EXPECTED_INSECURE = {
    "missing_permissions",
    "unpinned_action_tag",
    "action_on_branch",
    "unvetted_action_owner",
    "inline_package_install",
    "curl_pipe_shell",
    "pull_request_target",
    "untrusted_context_in_run",
    "deprecated_runner",
}


def test_insecure_fixture_fires_expected_checks():
    fired = checks_fired("insecure.yml")
    missing = EXPECTED_INSECURE - fired
    assert not missing, f"expected checks did not fire: {missing}"


def test_clean_fixture_fires_nothing():
    fired = checks_fired("clean.yml")
    assert fired == set(), f"clean fixture should fire no checks, got: {fired}"


def test_pwn_request_evidence_escalates():
    parsed, raw = load("insecure.yml")
    findings = aw.check_pull_request_target(parsed, raw, "repo", "insecure.yml")
    assert findings, "pull_request_target should fire"
    assert "pwn-request" in findings[0]["evidence"]


def test_inventory_classifies_pins():
    parsed, _ = load("clean.yml")
    refs = {ref: (owner, pin, kind) for ref, owner, pin, kind in aw.collect_uses(parsed)}
    assert refs["actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"][1] == "sha"


def test_parse_uses_local_and_docker():
    assert aw.parse_uses("./.github/actions/x")["pin_type"] == "local"
    assert aw.parse_uses("docker://alpine:3")["pin_type"] == "docker"
    assert aw.parse_uses("actions/checkout@v4")["pin_type"] == "tag"
    assert aw.parse_uses("actions/checkout@main")["pin_type"] == "branch"


def test_deprecated_runner_shapes():
    job_str = {"runs-on": "ubuntu-20.04", "steps": []}
    job_list = {"runs-on": ["self-hosted", "macos-12"], "steps": []}
    job_dict = {"runs-on": {"group": "ubuntu-runners", "labels": ["windows-2019"]}, "steps": []}
    for job in (job_str, job_list, job_dict):
        parsed = {"name": "t", "jobs": {"j": job}}
        assert aw.check_deprecated_runner(parsed, "", "repo", "t.yml")
