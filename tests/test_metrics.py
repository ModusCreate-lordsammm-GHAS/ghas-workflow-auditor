"""Unit tests for collect_platform_metrics parsing and aggregation.

These exercise the pure functions only (no network): the parse_* extractors
against fixture JSON, the repo-row aggregation, and the TOTAL-row math with the
n/a-vs-zero distinction. Run with: python -m pytest tests/ -v
"""

import json
import os
import sys

# Make bin/ importable without packaging.
BIN = os.path.join(os.path.dirname(__file__), os.pardir, "bin")
sys.path.insert(0, os.path.abspath(BIN))

import collect_platform_metrics as m  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


# --- parse_repo_security -------------------------------------------------

def test_parse_repo_security_enabled():
    row = m.parse_repo_security(load("repo_ghas_enabled.json"))
    assert row["repo"] == "service-api"
    assert row["visibility"] == "private"
    assert row["ghas_enabled"] is True
    assert row["secret_scanning_enabled"] is True
    assert row["secret_scanning_push_protection_enabled"] is True
    assert row["dependabot_security_updates_enabled"] is True
    assert row["secret_scanning_non_provider_patterns"] is False
    assert row["secret_scanning_validity_checks"] is True


def test_parse_repo_security_disabled():
    row = m.parse_repo_security(load("repo_ghas_disabled.json"))
    assert row["ghas_enabled"] is False
    assert row["secret_scanning_enabled"] is False


def test_parse_repo_security_absent_block_is_na():
    # No security_and_analysis block (no admin) -> features n/a, not false, so
    # the output cannot be misread as "everything disabled".
    row = m.parse_repo_security(load("repo_no_admin.json"))
    assert row["ghas_enabled"] is m.NA
    assert row["secret_scanning_enabled"] is m.NA
    assert row["visibility"] == "internal"


def test_feature_enabled_edges():
    assert m.feature_enabled(None, "advanced_security") is False
    assert m.feature_enabled({}, "advanced_security") is False
    assert m.feature_enabled({"advanced_security": None}, "advanced_security") is False
    assert m.feature_enabled({"advanced_security": {"status": "enabled"}}, "advanced_security") is True


# --- parse_copilot_billing ----------------------------------------------

def test_parse_copilot_billing_active():
    seats = m.parse_copilot_billing(load("copilot_billing_active.json"))
    assert seats["copilot_seats_total"] == 120
    assert seats["copilot_seats_active_this_cycle"] == 90
    assert seats["copilot_seats_inactive_this_cycle"] == 30
    assert seats["copilot_seats_pending"] == 5  # 3 invitation + 2 cancellation


def test_parse_copilot_billing_null_breakdown_is_zero():
    # seat_breakdown null (Copilot off) -> zeros, not an error.
    seats = m.parse_copilot_billing(load("copilot_billing_null.json"))
    assert seats["copilot_seats_total"] == 0
    assert seats["copilot_seats_active_this_cycle"] == 0
    assert seats["copilot_seats_pending"] == 0


# --- parse_actions_billing ----------------------------------------------

def test_parse_actions_billing():
    a = m.parse_actions_billing(load("actions_billing.json"))
    assert a["actions_minutes_used_total"] == 3050
    assert a["actions_minutes_used_paid"] == 550
    assert a["actions_minutes_included"] == 2500


# --- aggregate_repo_rows -------------------------------------------------

def test_aggregate_counts_and_visibility_breakdown():
    rows = [
        m.parse_repo_security(load("repo_ghas_enabled.json")),   # private, ghas on
        m.parse_repo_security(load("repo_ghas_disabled.json")),  # public, ghas off
    ]
    rows[0]["dependabot_config_present"] = True
    rows[1]["dependabot_config_present"] = False
    agg = m.aggregate_repo_rows(rows)
    assert agg["ghas_enabled"] == 1
    assert agg["ghas_enabled_private"] == 1
    assert agg["ghas_enabled_internal"] == 0
    assert agg["dependabot_config_present"] == 1


def test_aggregate_all_na_stays_na():
    # Every repo reported n/a (blanket permission gap) -> the aggregate is n/a,
    # not a misleading zero.
    rows = [m.parse_repo_security(load("repo_no_admin.json")) for _ in range(3)]
    agg = m.aggregate_repo_rows(rows)
    assert agg["ghas_enabled"] is m.NA


# --- total_row -----------------------------------------------------------

def test_total_row_sums_and_skips_na():
    org_a = {"org": "a", "total_repos_active": 10, "ghas_enabled": 4,
             "dependabot_alerts_open": 5, "copilot_seats_total": m.NA}
    org_b = {"org": "b", "total_repos_active": 20, "ghas_enabled": 9,
             "dependabot_alerts_open": 7, "copilot_seats_total": 30}
    total = m.total_row([org_a, org_b])
    assert total["org"] == "TOTAL"
    assert total["total_repos_active"] == 30
    assert total["ghas_enabled"] == 13
    assert total["dependabot_alerts_open"] == 12
    # org_a's n/a is skipped, so the total reflects only org_b's real value.
    assert total["copilot_seats_total"] == 30


def test_total_row_ignores_booleans():
    # Booleans belong to the by-repo CSV, never summed in the org TOTAL.
    total = m.total_row([{"ghas_enabled": True}, {"ghas_enabled": 3}])
    assert total["ghas_enabled"] == 3
