# GitHub Platform Strategic Roadmap
## Expanded GitHub Advanced Security, CodeQL, Copilot & Token-Based Billing

**Author:** Lordsammm
**Baseline date:** 2026-08-04
**Enterprise:** `Pfizer` (EMU) — 24 GitHub organizations
**Status:** Baseline established; roadmap proposed for review

> **Mandate:** *Develop a roadmap for expanded GitHub Advanced Security, CodeQL, Copilot, and
> Token-Based Billing growth — a strategic plan supporting long-term security, productivity, and
> platform consumption growth.*

> **How to read the chart callouts:** blocks marked **📊 Suggested visual** describe a
> recommended chart, its type, and the exact data behind it. They are guidance for the final
> formatted document, not chart images. A consolidated chart list is in
> [§7 Measurement Framework](#7-measurement-framework) and the closing note.

---

## 1. Purpose of this Document

This document establishes a **defensible, data-driven current-state baseline** of GitHub platform
adoption across all 24 organizations in Pfizer's enterprise, and sets out a **phased strategic
roadmap** to grow four capabilities in a coordinated way:

- **GitHub Advanced Security (GHAS)** — code security across the estate
- **CodeQL** — static analysis / code scanning coverage and findings
- **GitHub Copilot** — AI-assisted developer productivity
- **Token-Based Billing** — platform consumption and spend as a governance instrument

It is intended for **platform, security, and engineering leadership** as the input to funding and
sequencing decisions. Every figure in this document was measured directly from the GitHub API and
is **reproducible on demand** (see [§12 References](#12-references)); none is estimated.

The document deliberately treats security, productivity, and consumption as **three views of one
expansion program** rather than three separate initiatives, because the same underlying action —
enabling capabilities on more repositories and for more developers — drives all three.

---

## 2. Executive Summary

Across 24 organizations and **16,989 active repositories**, each of the four capabilities today is
effectively a **single-organization proof-of-concept that has already succeeded at scale**. The
strategic opportunity is not to invent anything new — it is to **propagate proven patterns to the
remaining ~20 organizations** in a sequenced, measured way.

**The five findings that frame the roadmap:**

1. **GHAS works here — in one org.** `pfizer-eps` runs code security on **all 1,359 of its
   repositories (100%)**, which is **96% of the entire enterprise's GHAS footprint**. Enterprise
   GHAS coverage is 8.3%; **14 of 24 orgs have zero GHAS repos**. `pfizer-eps` is the existence
   proof that GHAS scales past 1,300 repos in this environment.
2. **CodeQL trails its own licensing.** 987 repos actively scan (70% of GHAS-licensed repos),
   already surfacing **10,915 open code-scanning findings**. The cheapest security win available
   is turning scanning on where GHAS is *already paid for*.
3. **Copilot is a live, concentrated productivity pilot.** 3,560 seats exist, but **3,551 are in
   `pfizer-devex`**, and **37% of all seats were inactive this cycle**. Right-sizing precedes
   expansion.
4. **Spend is dominated by one line item.** Total platform spend is **$18,458 per period, 96% of
   it Copilot** ($17,781). Actions, packages, and storage are modest today but will grow as the
   other pillars expand — which is exactly why billing must become a governance instrument now.
5. **There is a large latent risk and hygiene surface.** **423,294 open Dependabot alerts** (a
   floor — two orgs hit the counting cap), and **39% of all repositories are archived**, inflating
   both risk and licensing baselines until reconciled.

**The thesis:** turning GHAS on generates CodeQL findings (security outcome); Copilot adoption
lifts developer output (productivity outcome); both increase token consumption (billing outcome).
Sequenced correctly and measured against this baseline, expansion is self-evidencing — leadership
can see security, productivity, and consumption growth on the same instrument.

> **📊 Suggested visual — Executive scorecard (six big-number tiles):** Active repos **16,989** ·
> GHAS coverage **8.3%** · CodeQL active repos **987** · Copilot seats **3,560 (63% active)** ·
> Open security alerts **436k+** · Spend/period **$18,458**. Simple KPI tiles, no axes.

---

## 3. Current State Baseline

*All figures are the enterprise `TOTAL` across 24 orgs unless a specific org is named. Source:
`platform_metrics_by_org.csv`.*

### 3.1 Security Posture

Secret scanning and push protection — the no-cost GHAS features — are **effectively universal**.
The gap is **licensed code security** and the **triage of existing findings**.

| Control | Repos enabled | Coverage |
|---|---|---|
| Secret scanning | 16,989 | 100% of active repos |
| Secret-scanning push protection | 16,989 | 100% |
| Dependabot security updates | 16,906 | 99.5% |
| **GHAS (code security, licensed)** | **1,411** | **8.3%** |
| — of which private / internal | 875 / 536 | |

**Open alert inventory (latent risk):**

| Alert type | Open count | Note |
|---|---|---|
| Dependabot | **423,294** | **Floor** — `pfizer` and `pfizer-business-services` each hit the 100,000 cap |
| Code scanning (CodeQL) | 10,915 | Real findings awaiting triage |
| Secret scanning | 1,809 | |

**Concentration:** GHAS adoption is almost entirely one org.

| Org | GHAS repos | % of enterprise GHAS |
|---|---|---|
| `pfizer-eps` | 1,359 | 96.3% |
| `pfizer` | 18 | 1.3% |
| `pfizer-rd` | 16 | 1.1% |
| `pfizer-analytics` | 11 | 0.8% |
| All others (20 orgs) | 7 | 0.5% |

**14 orgs with zero GHAS repos:** `pfizer-business-services`, `pfizer-clinical-supply`,
`pfizer-compliance`, `pfizer-devex`, `pfizer-digital-supply`, `pfizer-eps-dpp`, `pfizer-esc`,
`pfizer-finance`, `pfizer-fit`, `pfizer-ld`, `pfizer-marm`, `pfizer-oneweb`, `pfizer-pic`,
`pfizer-utils`.

> **📊 Suggested visual — Pareto bar chart:** GHAS-enabled repos per org, descending. One tall bar
> (`pfizer-eps`) then a long flat tail. Instantly communicates the concentration.

> **📊 Suggested visual — Grouped bar:** open alerts by type (Dependabot / code scanning / secret
> scanning). Annotate Dependabot as a capped floor.

### 3.2 Development Platform

The development platform (repositories + CodeQL scanning + Actions) shows a **coverage funnel**
where scanning lags licensing, and a significant **archived-repo overhang**.

| Metric | Value |
|---|---|
| Active repositories | 16,989 |
| Archived repositories | 11,022 (**39.3%** of all repos) |
| Private / Internal / Public | 14,723 / 2,266 / 0 |
| **CodeQL active repos** | **987 (5.8% of active; 70% of GHAS-licensed)** |
| Actions minutes used (period) | 99,883 (64,987 paid) |

The 70% figure is the actionable one: **~30% of GHAS-licensed repos are not yet scanning** — paid
capability sitting idle.

> **📊 Suggested visual — Funnel chart:** Active repos **16,989** → GHAS-licensed **1,411** →
> CodeQL scanning **987**. Shows both the licensing gap and the license-to-scan gap in one image.

> **📊 Suggested visual — Donut:** Active **16,989** vs Archived **11,022** — the hygiene overhang.

### 3.3 Productive Tooling (Copilot)

Copilot is a real, funded productivity capability, but **concentrated and under-utilized**.

| Metric | Value |
|---|---|
| Total seats | 3,560 |
| Active this cycle | 2,247 (63.1%) |
| **Inactive this cycle** | **1,313 (36.9%)** |
| Pending | 35 |
| Seats in `pfizer-devex` | 3,551 (99.7%) |
| Seats in `pfizer-utils` | 9 |
| Engagement (active/engaged *users*) | **n/a** — see [§9](#9-risk-and-dependencies) |

The 1,313 inactive seats represent the single largest efficiency lever in the portfolio: they can
partly **fund expansion** to other orgs without new net spend.

> **📊 Suggested visual — Donut:** seat utilization (Active 2,247 / Inactive 1,313 / Pending 35).

> **📊 Suggested visual — Bar:** Copilot seats by org (one dominant bar) — mirrors the GHAS
> concentration story for productivity.

### 3.4 Platform Consumption

Token-based consumption is currently **small and Copilot-dominated**, which makes now the right
time to instrument it — before the other pillars grow the other product families.

| Product family | Spend / period | Share |
|---|---|---|
| **Copilot** | $17,781.48 | 96.3% |
| Actions | $676.88 | 3.7% |
| Packages | $0.00 | 0% (consumption in GB-hours) |
| Storage | $0.00 | 0% (consumption in GB-hours) |
| **Total** | **$18,458.36** | 100% |

Consumption (non-billed usage) is also tracked: **2,258 GB-hours** packages storage and
**293,281 GB-hours** shared storage (Actions artifacts + Git LFS).

**Spend by org** is as concentrated as everything else: `pfizer-devex` $17,738 (Copilot);
`pfizer` $497 (Actions); all others under $80 each.

> **📊 Suggested visual — Donut/pie:** spend by product family (Copilot 96.3% / Actions 3.7%).

> **📊 Suggested visual — Horizontal bar:** total spend by org (log scale or annotated, given the
> one-org dominance).

### 3.5 Cross-cutting view — adoption heatmap

The most decision-useful single visual is a **matrix of the 24 orgs against the four capabilities**,
showing where each is present, partial, or absent. It makes the expansion targets self-selecting.

> **📊 Suggested visual — Heatmap (orgs × capabilities):** rows = 24 orgs; columns = GHAS %,
> CodeQL %, Copilot seats, Spend. Colour intensity = adoption. `pfizer-eps` lights up on security;
> `pfizer-devex` on Copilot; the large orgs (`pfizer`, `pfizer-rd`) show big repo counts with thin
> coverage — the prime expansion targets.

---

## 4. Strategic Vision

Four guiding principles translate the baseline into direction. Each maps to a pillar and to a
measurable outcome.

### 4.1 Security-by-default
Code security should be the **default posture** for internal and private repositories, not an
opt-in exception. `pfizer-eps` proves this is operationally achievable at scale. The vision:
GHAS + CodeQL enabled by default across the top-tier orgs, with alert triage as a managed SLA
rather than an unbounded backlog.

### 4.2 Developer productivity uplift
Copilot should be deployed where it demonstrably **changes developer throughput**, and measured on
*engagement*, not seat count. The vision: every licensed seat is an active seat, expansion
decisions are evidence-based, and productivity gains are reported alongside cost.

### 4.3 Supply-chain discipline
Dependency and workflow integrity are first-class. This spans Dependabot (423k+ open alerts to
burn down), CodeQL findings, **and** the workflow-security controls from the companion GHAS
Workflow Audit tool (action pinning, least-privilege permissions). The vision: a shrinking,
governed alert surface and a vetted, pinned action allowlist enterprise-wide.

### 4.4 Cost-aware growth
Consumption growth is expected and welcome — provided it is **visible, attributed, and tied to
outcomes**. The vision: every expansion wave carries a predicted consumption delta, actuals are
tracked monthly against it, and leadership sees **cost-per-outcome** (e.g., $/GHAS-covered repo,
$/active Copilot user), not just a rising bill.

---

## 5. Growth Tracks

Four parallel tracks, each with a current position, a 12-month target, the key moves, and the KPI
it is judged on. Tracks are sequenced in [§6](#6-phased-roadmap).

### Track A — GHAS expansion (Security)
- **Current:** 1,411 repos (8.3%); 96% in one org; 14 orgs at zero.
- **12-month target:** enable the top-5 orgs by repo count; enterprise coverage **25–30%**.
- **Key moves:** codify the `pfizer-eps` rollout as a runbook; enable largest-untapped orgs first
  (`pfizer`, `pfizer-rd`, `pfizer-digital-manufacuring`, `pfizer-fit`); reconcile archived repos
  before licensing.
- **KPI:** % active repos with code security enabled.

### Track B — CodeQL coverage & findings (Security outcome)
- **Current:** 987 active repos (70% of GHAS-licensed); 10,915 open findings.
- **12-month target:** CodeQL-active ≥ **90% of GHAS-licensed**; open findings on a managed
  burn-down.
- **Key moves:** enable code-scanning default setup on GHAS-licensed-but-unscanned repos; stand up
  a triage SLA and mean-time-to-remediate tracking.
- **KPI:** CodeQL-active as % of GHAS-licensed; open code-scanning alerts (trend ↓).

### Track C — Copilot adoption (Productivity)
- **Current:** 3,560 seats; 63% active; one org.
- **12-month target:** active-to-licensed **≥ 85%**; controlled expansion to 2–3 additional
  high-developer orgs; engagement telemetry live.
- **Key moves:** monthly idle-seat reclamation; unblock engagement reporting (infra); fund pilot #2
  partly from reclaimed seats with a defined productivity metric.
- **KPI:** active seats ÷ licensed seats; engaged users (once unblocked).

### Track D — Token-based billing governance (Consumption)
- **Current:** $18,458/period, 96% Copilot; per-org attribution available.
- **12-month target:** monthly refresh live; per-org guardrails; cost-per-outcome reporting.
- **Key moves:** enable the scheduled baseline; publish trend + guardrails; attach a predicted
  consumption delta to every wave in Tracks A–C.
- **KPI:** total spend + cost-per-outcome, tracked against roadmap predictions.

---

## 6. Phased Roadmap

A three-horizon plan. Phase 0 is complete; Phases 1–3 sequence the tracks so cheap, no-new-spend
wins come first and expansion is always instrumented before it scales.

### Phase 0 — Baseline established ✅ (complete)
Reproducible, per-org, enterprise-wide baseline for all four pillars, captured via GitHub Actions.
*This document is its output.*

### Phase 1 — "Now" (0–3 months) · tidy the house, no new spend
- **Track B:** close the CodeQL license-to-scan gap (~30% of GHAS repos not scanning).
- **Track C:** reclaim the 1,313 inactive Copilot seats via a monthly active-vs-licensed review.
- **Track A/hygiene:** reconcile/confirm the 11,022 archived repos so metrics track live risk.
- **Track D:** enable the monthly baseline refresh (flip the `schedule` cron on).
- **Enabler:** unblock Copilot engagement telemetry (runner proxy allow-list) — *infra-dependent.*

### Phase 2 — "Next" (3–9 months) · expand the proven pillars
- **Track A:** GHAS wave 1 — next 2–3 largest untapped orgs (`pfizer`, `pfizer-rd`,
  `pfizer-digital-manufacuring`) using the `pfizer-eps` runbook.
- **Track B:** CodeQL follows each GHAS wave; alert-triage SLA + findings burn-down live.
- **Track C:** Copilot pilot #2 in one additional high-developer org, measured on productivity.
- **Track D:** first monthly spend trend + per-org guardrails published.

### Phase 3 — "Later" (9–18 months) · scale to enterprise default
- **Track A/B:** GHAS + CodeQL as the default posture for internal/private repos across the top-10
  orgs.
- **Track C:** Copilot rollout decisions driven by engagement, not seat count.
- **Track D:** cost-per-outcome reporting embedded in leadership review; consumption growth
  explicitly tied to security and productivity gains.

> **📊 Suggested visual — Roadmap swimlane / Gantt:** rows = Tracks A–D; columns = Now / Next /
> Later; cells = the milestones above. The single clearest "what happens when" visual for leadership.

---

## 7. Measurement Framework

This baseline **is** the measuring instrument. Each track has a headline KPI already captured, so
progress is simply a diff against this document. Re-running the workflow monthly regenerates every
number with zero manual effort.

| Track | Headline KPI | Baseline (2026-08-04) | Direction / 12-mo target |
|---|---|---|---|
| A — GHAS | % active repos with code security | 8.3% | ↑ 25–30% |
| B — CodeQL | CodeQL-active ÷ GHAS-licensed | 70% | ↑ ≥90% |
| B — CodeQL | Open code-scanning alerts | 10,915 | ↓ (burn-down) |
| C — Copilot | Active ÷ licensed seats | 63% | ↑ ≥85% |
| C — Copilot | Engaged users | n/a | establish |
| D — Billing | Total spend + cost-per-outcome | $18,458 | governed ↑ |
| Hygiene | Archived-repo ratio | 39.3% | ↓ (reconciled) |
| Supply chain | Open Dependabot alerts | 423,294 (floor) | ↓ |

**Cadence & ownership:** monthly automated refresh (scheduled workflow); each track has a named
owner; the enterprise trend is reviewed in the platform governance forum ([§10](#10-governance-alignment)).

**Recommended standing charts (regenerated monthly):**
1. GHAS coverage % — trend line vs target band.
2. CodeQL license-to-scan gap — funnel, month over month.
3. Copilot active-vs-licensed — donut + trend.
4. Spend by product family + per org — stacked bar trend.
5. Open alerts by type — burn-down lines.
6. Org × capability adoption — heatmap (progress map).
7. Four-pillar maturity — radar (current vs target), for the exec one-pager.

> **📊 Suggested visual — Radar/spider chart:** four axes (GHAS %, CodeQL-of-GHAS %, Copilot
> active %, billing-governed), plotting **current vs 12-month target**. Ideal single-image summary
> of the whole roadmap.

---

## 8. Investment and Cost Dependencies

Expansion has real but **sequenced and partly self-funding** cost implications. This section frames
the drivers; precise figures require the licensing/committer confirmation noted below.

**Cost drivers by track:**

- **Track A (GHAS):** GHAS is billed on **unique active committers** across licensed repos, not
  per repo. Enabling more orgs raises the committer count; the archived-repo reconciliation
  (Phase 1) directly reduces this. *Dependency: enterprise-level committer count is currently
  `n/a` from the org API (enterprise-scoped) — confirm with enterprise admin before waves.*
- **Track B (CodeQL):** no incremental license cost beyond GHAS (CodeQL is included); the cost is
  **Actions minutes** consumed by scans — modest today (99,883 min/period) but grows with coverage.
- **Track C (Copilot):** per-seat. The **1,313 inactive seats** are the primary funding lever —
  reclaiming/redeploying them offsets expansion before net-new seats are purchased.
- **Track D (Billing):** negligible cost; the monthly refresh runs on existing self-hosted runners.

**Self-funding logic:** Phase 1 is explicitly no-new-spend (turn on paid-but-idle CodeQL; reclaim
idle Copilot seats; reconcile archived repos). Phases 2–3 expansions should each carry a predicted
consumption delta (Track D) and, where possible, be partly funded by Phase 1 reclamation.

**Enabling (near-zero-cost) dependencies:**
- Runner proxy allow-list for the Copilot engagement report host (unblocks Track C engagement KPI).
- Enterprise-admin confirmation of committer billing figures (sizes Track A accurately).

---

## 9. Risk and Dependencies

**Program risks**

| Risk | Impact | Mitigation |
|---|---|---|
| Alert-backlog shock — enabling CodeQL/GHAS surfaces large finding volumes | Triage capacity overwhelmed; teams disengage | Phase in with a triage SLA and burn-down; enable by wave, not big-bang |
| Idle Copilot spend persists | Continued 37% waste; expansion harder to justify | Monthly active-vs-licensed reclamation (Phase 1) |
| Archived-repo overhang distorts baselines | Over-licensing; inflated risk numbers | Reconcile 11,022 archived repos in Phase 1 |
| Consumption grows faster than governance | Surprise bills | Enable monthly refresh + per-org guardrails before Phase 2 |
| Rollout without a runbook | Inconsistent, slow org onboarding | Codify `pfizer-eps` as the reference implementation |

**Data caveats (why some numbers are floors or `n/a`)**

1. **Dependabot alerts (423,294) are a floor** — `pfizer` and `pfizer-business-services` each hit
   the 100,000 per-org counting cap; true totals are higher.
2. **CodeQL coverage (987) is a lower bound** — counts distinct repos with *open* code-scanning
   alerts (per-repo code-scanning endpoints commonly return 403); a repo scanning cleanly with
   zero open alerts is not counted.
3. **Copilot engagement is `n/a`** — inline metrics endpoints are retired (404); the report
   endpoint returns download links to `copilot-reports.github.com`, which the self-hosted
   `bolt-ubuntu` runner's proxy blocks (403). *Dependency: allow-list that host, then wire the
   report fetch into the collector.*
4. **GHAS active committers is `n/a`** — the org committer endpoint returns 422; committer billing
   is enterprise-scoped. *Dependency: enterprise-admin access.*
5. **Storage figures are gigabyte-hours** (usage-API unit), not point-in-time GB.

None of these block the roadmap; each is a scoped enhancement or an external dependency.

---

## 10. Governance Alignment

- **Reproducible evidence base.** The baseline is regenerated by a version-controlled tool
  (read-only GitHub App auth, least-privilege scopes) — auditable and repeatable, not a one-off
  spreadsheet.
- **Cadence.** Monthly automated refresh (scheduled workflow) feeds the platform governance forum;
  each track KPI has a named owner.
- **Least-privilege & security-by-design.** Collection uses a read-only App with five explicit
  scopes and OIDC-minted, org-scoped tokens; no standing broad credentials.
- **Alignment with existing controls.** Complements the companion **GHAS Workflow Audit** (workflow
  security: action pinning, least-privilege permissions, untrusted-input checks), giving governance
  both a *posture* view (this baseline) and a *configuration-hygiene* view (the audit).
- **Decision rights.** Expansion waves, guardrails, and reclamation actions are approved through the
  governance forum against the KPI targets in [§7](#7-measurement-framework).

---

## 11. What This Document Does Not Cover

- **Remediation of individual alerts.** This is a posture baseline and roadmap, not a triage plan
  for the 423k+ open Dependabot / 10,915 code-scanning findings.
- **Copilot engagement depth.** Active/engaged *user* metrics are `n/a` pending the runner proxy
  allow-list (see [§9](#9-risk-and-dependencies)); only seat and spend data are covered.
- **Enterprise-level committer billing.** GHAS active-committer counts are `n/a` at org level;
  precise GHAS license sizing requires enterprise-admin data.
- **Workflow-file security findings.** Covered by the separate GHAS Workflow Audit capability, not
  repeated here.
- **Public-repo posture.** The EMU has no public repos; out of scope by definition.
- **Point-in-time snapshot.** Figures are as of 2026-08-04; trends require the monthly refresh.
- **Vendor pricing / contract terms.** Cost drivers are described qualitatively ([§8](#8-investment-and-cost-dependencies)); commercial figures are out of scope.

---

## 12. References

| Reference | Description |
|---|---|
| `platform_metrics_by_org.csv` | Per-org baseline + enterprise `TOTAL` row (source for all figures) |
| `platform_metrics_by_repo.csv` | Per-repo drill-down ("which repos are missing which control") |
| `bin/collect_platform_metrics.py` | The collector (read-only GitHub API, graceful degradation) |
| `.github/workflows/platform-metrics.yml` | The Actions workflow (per-org matrix → merge → TOTAL); scheduled refresh ready to enable |
| `bin/audit_workflows.py` / `.github/workflows/ghas-audit.yml` | Companion GHAS Workflow Audit capability (workflow-security posture) |
| `README.md` | Tool documentation, exact permission key names, billing semantics, `n/a` vs `0` |
| GitHub enhanced-billing usage API | Source of consumption/spend figures |
| GitHub org security/alerts APIs | Source of GHAS, CodeQL, Dependabot, secret-scanning figures |

---

### Appendix — Top organizations by scale (expansion-target reference)

| Org | Active repos | GHAS | CodeQL active | Open Dependabot | Spend/period |
|---|---|---|---|---|---|
| `pfizer` | 6,692 | 18 | 17 | 100,000* | $497.23 |
| `pfizer-rd` | 3,191 | 16 | 13 | 63,140 | $34.20 |
| `pfizer-eps` | 1,359 | **1,359** | 944 | 14,179 | $37.13 |
| `pfizer-analytics` | 1,146 | 11 | 7 | 41,130 | $75.66 |
| `pfizer-digital-manufacuring` | 998 | 1 | 1 | 34,986 | $6.75 |
| `pfizer-fit` | 863 | 0 | 0 | 17,486 | $13.33 |
| `pfizer-business-services` | 607 | 0 | 0 | 100,000* | $1.36 |
| `pfizer-devex` | 37 | 0 | 0 | 220 | $17,737.99 (Copilot) |

*\* capped at 100,000 (floor). Full detail for all 24 orgs is in `platform_metrics_by_org.csv`.*
