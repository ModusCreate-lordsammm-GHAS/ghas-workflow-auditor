# Roadmap update pack — paste this whole file into the document chat

Paste this **entire file** into the Claude chat that generated *Pfizer Strategic Enterprise GitHub
Expansion Roadmap*. It contains everything needed to produce the corrected document and my replies
to the reviewers.

---

## ►► INSTRUCTION TO THE AI — DO THIS

You generated the document "Pfizer Strategic Enterprise GitHub Expansion Roadmap" earlier in this
chat. Using that document, produce **two outputs**:

**OUTPUT 1 — The corrected document (full).** Regenerate the *complete* document with every edit in
**PART 1** applied. **Show every changed or newly added passage in RED text** so I can see exactly
what changed at a glance (keep unchanged text in the normal colour). Apply the two global changes
first, then EDIT 0 through EDIT 14, then add NEW SECTIONS A, B and C and Appendix A. Where you see
**[PLACEHOLDER: …]**, insert that bracketed text **verbatim in red** — do NOT invent numbers; I
will fill those in later. Give me the whole document so I can copy and paste it out myself.

**OUTPUT 2 — Responses to reviewer comments.** After the document, reproduce the list in **PART 2A**
exactly — my reply to each reviewer comment (C1–C13) — formatted as a clean list so I can copy each
reply straight into its comment thread.

**Ignore PART 2B** — those are my private working notes, not part of either output.

Do not summarise or shorten the document; I need the full corrected text. If any FIND text doesn't
match your current version word-for-word, apply the change to the closest matching passage and flag
it in red.

---

# PART 1 — THE EDITS (apply all of these to OUTPUT 1)

Apply the two global changes first, then each numbered edit. For each edit: find the quoted
**FIND** text and make the change described; **ADD** items are new text to insert at the location
noted. Remember: every change and addition shows in **red**.

**Three global changes first:**
- **Keep the org count at 23** (the document already uses 23 — do not introduce "24" anywhere).
- **Rename the metric column "GHAS" to "Code Scanning enabled"** everywhere it appears in tables
  (it measures repos with code scanning switched on, not all of GHAS).
- Remove any invented governance bodies (e.g. "GHAS Delivery Office", "Control Board", "Executive
  Steering Committee", "GHAS Governance and Rollout Outline") and the "IT Finance partnership"
  line — these cannot be verified.

---

### EDIT 0 — Add a "Baseline at a glance" summary near the top (NEW)
**Where:** at the very start of the **Current State Baseline** section, immediately after the
sentence that ends "…both included alongside this report." (Note: the document has no six-tile
scorecard — just place this summary table here.)
**ADD this compact summary table** (the full 23-org breakdown stays in Appendix A):

> **Baseline at a glance** (all 23 organizations, via the GitHub API — coverage 4 Aug 2026, spend July 2026)
>
> | Metric | Enterprise total |
> |---|---|
> | Active repositories | 16,989 |
> | Code scanning enabled | 1,411 (8.3%) |
> | Code scanning producing alerts | 987 |
> | Secret scanning + push protection | 16,989 (100%) |
> | Open secret-scanning alerts | 1,809 |
> | Dependabot updates configured | 16,906 |
> | Copilot seats assigned | 3,560 (3,551 in pfizer-devex) |
> | Copilot spend (July 2026) | $236,466 |
>
> *Where the metric is concentrated: code scanning is almost entirely in pfizer-eps (1,359 repos);
> Copilot is almost entirely in pfizer-devex (3,551 seats). Full per-org detail: Appendix A.*

### EDIT 1 — Add data provenance (Executive Summary)
**Where:** the first paragraph of the Executive Summary.
**ADD this sentence:** "All coverage figures are per-organization, collected via the GitHub API
across all 23 organizations on 4 August 2026; the full per-org breakdown is in Appendix A."

### EDIT 2 — Remove the "pilot" wording
**FIND:** "pfizer-eps is not just a pilot anymore. It is evidence that GHAS with Code Scanning
enabled is scalable past 1,300 repositories in this environment"
**REPLACE WITH:** "pfizer-eps runs GHAS with code scanning across all 1,359 of its repositories,
showing the configuration works at scale (1,300+ repos) in Pfizer's environment"

### EDIT 3 — Copilot concentration is by design
**FIND:** "Copilot is an active productivity pilot, concentrated in pfizer-devex. There are 3,560
total seats assigned enterprise wide, where 3,551 of them sit in pfizer-devex"
**REPLACE WITH:** "Copilot is currently deployed mainly through pfizer-devex (3,551 of 3,560
seats). This concentration is by design: per GitHub's guidance (meeting of 05/08/2026), Copilot
deployment is moving to enterprise-level management as the default path. The relevant measure is
enterprise-wide utilization, not per-org expansion"

### EDIT 4 — Copilot seat economics
**FIND:** "Of those seats, 37% were inactive during the most recent billing cycle. Before any
conversation about expanding Copilot to new organizations, the more immediate opportunity is
making sure the seats already purchased are being used."
**REPLACE WITH:** "Of those seats, 37% were inactive last cycle. Since each seat includes a token
allowance before usage-based charges apply, inactive seats mean unused licence value while
overall token consumption is already over budget." [OPTIONAL: add a token allowance vs actual
consumption figure later if available — not required.]

### EDIT 5 — Fix the spend figure (this was wrong)
**FIND:** "Total platform consumption spend for the period was 18,458 dollars, and 96 percent of
that, 17,781 dollars, was Copilot."
**REPLACE WITH:** "Platform consumption is dominated by Copilot. Per the GitHub billing API,
Copilot spend was $236,466 in July 2026 (of $248,163 total platform spend — Copilot is 95% of
it), and is projected to reach roughly $400,000 by September/October 2026, partly because a
discount is ending. (The earlier $18,458 figure was a 4-day partial pull and has been corrected.)"
Then add the trend sentence: "Over the last six complete months, Copilot spend rose steadily from
$51,705 (February 2026) to $236,466 (July 2026) — roughly a 4.6× increase; see the spend-trend
table in Section C."

### EDIT 5b — Replace the Platform Consumption spend table (it shows the wrong 4-day figures)
**FIND** the product-family spend table in the **Platform Consumption** section — the one with rows
Copilot **$17,781.48** (96.3%) / Actions $676.88 / Packages $0.00 / Storage $0.00 / **Total
$18,458.36**.
**REPLACE the whole table** with the latest complete month (the six-month trend is added separately
in NEW SECTION C):

| Product Family | Spend (July 2026) | Share |
|---|---|---|
| Copilot | $236,466 | 95% |
| Actions + other | $11,697 | 5% |
| **Total** | **$248,163** | 100% |

### EDIT 5c — Fix the per-organization spend sentence
**FIND:** "pfizer-devex accounts for 17,738 dollars, almost entirely Copilot. pfizer accounts for
497 dollars, mostly Actions. Every other organization sits under 80 dollars."
**REPLACE WITH:** "In July 2026, pfizer-devex accounted for approximately 231,573 dollars, almost
entirely Copilot. Every other organization is immaterial by comparison."

### EDIT 5d — Fix the Measurement Framework billing baseline
**FIND:** the Billing row baseline value **"$18,458"** (in the row "Total spend and cost per outcome
| $18,458 | Governed growth").
**REPLACE "$18,458" WITH:** "$236K Copilot (July; up ~4.6× over six months)".

### EDIT 6 — Plain-language rewrite (flagged as LLM-generated)
**FIND:** the paragraph beginning "The thread running through all five findings is the same."
**REPLACE WITH:** "These findings connect: enabling GHAS produces CodeQL results (security),
Copilot adoption affects developer output (productivity), and both drive platform consumption
(cost). The roadmap tracks all three on one baseline."

### EDIT 7 — Point to the data
**FIND:** "platform_metrics_by_org.csv and platform_metrics_by_repo.csv"
**CHANGE:** add "(the full per-org table is in Appendix A; raw CSV attached)" right after it.

### EDIT 8 — Correct "costs nothing"
**FIND:** "costs nothing beyond the license Pfizer already holds"
**REPLACE WITH:** "requires no new tooling licence, though it does consume Actions minutes and,
where it extends GHAS to new repositories, adds to committer-based GHAS cost"

### EDIT 9 — Add SonarQube → CodeQL framing (and fix an overstated Sonar claim)
**First, FIND:** "However, the implementation of SonarQube accounts for the remaining Code Scanning
coverage." (in the Development Platform section)
**REPLACE WITH:** "SonarQube is also deployed (sonar.pfizer.com), but it is not equivalent to CodeQL
for security coverage — see the comparison below."

**Then, Where:** right after the paragraph that starts "The 70% figure is the one worth sitting with".
**ADD this paragraph:** "Pfizer currently runs SonarQube (sonar.pfizer.com). The roadmap's direction
is to standardise on CodeQL/GHAS as the primary application-security scanner and evaluate
consolidating away from SonarQube over time. A July 2026 proof-of-concept on the 3 repositories
where both tools were active found CodeQL surfaced 90 open findings, all security-relevant (100%),
versus SonarQube's 4,646 open findings of which only 181 (3.9%) were security-related — roughly 25
non-security findings for every security one. CodeQL maps every finding to a CWE (28 unique) and
needs no dedicated infrastructure, running inside GitHub Actions. Stated for balance: the sample is
3 repositories (directional, not enterprise-wide); about half of CodeQL's 90 findings (46) are
GitHub Actions workflow-permission issues rather than application-code vulnerabilities; and
SonarQube additionally covers code quality (~4,465 code-smell/bug findings) that CodeQL does not, so
any SonarQube decommissioning must first replace that gap (e.g. GitHub Code Quality, GA July 2026).
See the CodeQL vs SonarQube comparison report for the full data."

### EDIT 10 — Zero-GHAS orgs clarification
**FIND:** "Fourteen organizations currently have zero GHAS enabled repositories"
**ADD immediately after that sentence:** "This reflects that code scanning has not yet been
enabled in these organizations, not a deliberate exclusion. Which are priority candidates for
enablement is a business decision to confirm with the platform and security teams."

### EDIT 11 — CodeQL rollout batch limit
**Where:** in the CodeQL rollout / Phase 1 area.
**ADD:** "Enabling code scanning default setup at scale is subject to GitHub's batch-enablement
limits, so rollout proceeds in batches." [OPTIONAL: state the exact batch number if known — not required.]

### EDIT 12 — Consumption is not "small"
**FIND:** the sentence starting "Token-based consumption is currently small in absolute terms"
**REPLACE WITH:** "Token-based consumption is growing rapidly and is dominated by Copilot (July
2026 actual: $236,466 Copilot of $248,163 total, per the GitHub billing API); projected Copilot
spend for September/October 2026 is approximately $400,000. Consumption governance already exists
at Pfizer — the priority is extending it to cover productivity and consumption metrics rather than
creating new structures." [OPTIONAL: add specific governance shortcomings later if the team wants
— not required.]

### EDIT 13 — Expand Supply Chain section
**Where:** the Supply Chain Discipline section.
**ADD these as items the roadmap addresses:** "release-process maturity (many teams lack a
defined release process), credentials still present in code, secret-management practices, and
artifact/binary management (e.g. JFrog Artifactory)." [OPTIONAL: expand the JFrog current-state
detail later if the team provides it — not required.]

### EDIT 14 — Copilot utilization table (real data — no external input needed)
**Where:** the Copilot / Productive Tooling section, wherever seats are discussed.
**ADD this table.** These are real figures collected per organization from each org's Copilot
billing data (`/orgs/{org}/copilot/billing`). Only two orgs hold seats; the other 21 have none, so
this utilization is effectively pfizer-devex's:

> **Copilot seat utilization, by organization** (per-org seat billing data, 4 Aug 2026)
>
> | Organization | Assigned seats | Active (current cycle) | Idle (current cycle) |
> |---|---|---|---|
> | pfizer-devex | 3,551 | 2,239 (63%) | 1,312 (37%) |
> | pfizer-utils | 9 | 8 | 1 |
> | All other 21 organizations | 0 | — | — |
> | **Total** | **3,560** | **2,247 (63%)** | **1,313 (37%)** |
>
> *Optional enterprise metric (to be supplied by an enterprise admin): active users, last 60 days
> = [PLACEHOLDER — do not invent a number].*

**ADD this sentence under the table:** "Copilot seats are held almost entirely in pfizer-devex
(3,551 of 3,560), so this utilization is effectively pfizer-devex's. The 37% of seats idle this
cycle quantify the utilization gap — unused licence value while token consumption is over budget.
Enterprise-level engagement (active users over a rolling 60-day window) is managed at the GitHub
enterprise level and can be added by an enterprise administrator, but the picture above stands
complete without it."

### EDIT 15 — Delete the "External Dependencies" section entirely
**DELETE the whole "External Dependencies" subsection** — its heading and the paragraph beginning
"This roadmap depends on continued execution of the existing GHAS Governance and Rollout Outline…".
It names three workstreams ("GHAS Governance and Rollout Outline", "RAM integration workstream",
"EMU readiness workstream") that cannot be verified and were never part of the source data. Remove
it completely — do not replace it — and remove its entry from the Table of Contents.

### NEW SECTION A — CI/CD Pipeline Security (add to the Current State Baseline)
Add a subsection with this text and numbers (from the GHAS Workflow Audit scan of every workflow
file across all orgs; figures as of the last audit run):

"A scan of every GitHub Actions workflow across all 23 organizations found 51,090 security issues
in CI/CD pipelines (43,448 critical, 7,194 high, 448 medium) across 9,113 repositories (the repos
that contain workflow files — a subset of the 16,989 active repositories). The most common issues
are missing workflow permissions (17,445), unvetted action publishers (12,533), and actions pinned
to a tag rather than a commit SHA (12,097)."

### NEW SECTION B — Secrets Management (add to the Current State Baseline)
Add a subsection with this text and numbers:

"Secret scanning and push protection are enabled on all 16,989 active repositories (100%), with
1,809 open secret-scanning alerts. Separately, the pipeline scan found approximately 4,572
hardcoded secrets and keys committed directly in workflow files (3,210 AWS secrets, 1,362 RSA
keys), indicating credentials-in-code remains an active risk to remediate."

### NEW SECTION C — Platform spend trend (last 6 complete months)
Add a "Platform Spend Trend" subsection under Platform Consumption. All figures are pulled from
the GitHub billing API (enterprise-wide, summed across all 23 organizations); each is a complete
calendar month.

"Copilot is the dominant and fastest-growing platform cost. Over the last six complete months,
Copilot spend rose steadily from $51,705 (February) to $236,466 (July 2026) — roughly a 4.6×
increase, doubling about every three months. On that trajectory it is projected to reach
approximately $400,000 by September/October 2026, partly because a current discount is ending.
Total platform spend is volatile month to month (driven by variable Actions usage), so the stable,
material signal is the Copilot line itself."

**Data table for the chart** (paste as-is):

| Month | Copilot spend | Total platform spend |
|---|---|---|
| Feb 2026 | $51,705 | $65,504 |
| Mar 2026 | $65,200 | $99,644 |
| Apr 2026 | $77,659 | $211,315 |
| May 2026 | $126,179 | $202,359 |
| June 2026 | $149,247 | $198,602 |
| July 2026 | $236,466 | $248,163 |
| Aug 2026 | *in progress — partial month, not plotted* | — |
| Sep/Oct 2026 (projected) | ~$400,000 | — |

*Note: the trend uses complete calendar months only. August 2026 is still in progress, so it is
deliberately not shown as a data point — a partial month understates the total (this is the same
reason the earlier $18,458 four-day figure was wrong). The next complete month resumes the line;
the ~$400K figure is the Sep/Oct projection along the Feb→Jul trajectory.*

**Chart guidance:** plot **Copilot spend by month** as the primary series — a rising column/line
Feb→Jul with the ~$400K projection as a dashed/forecast bar. This is a clean, monotonic climb and
is the headline. Do **not** plot "total spend" as a trend line — it is erratic (April spikes on
Actions usage) and undercuts the story; if you must show it, show it as faint context bars behind
the Copilot line, not as the message.

### NEW — Appendix A (full per-org table)
Add an "Appendix A: Per-organization baseline" with the table below (also attached as
`platform_metrics_by_org.csv`).

Column note (GHAS = Secret Scanning + Code Scanning + Dependabot):
- **Code Scanning enabled** = repos with the Advanced Security / code-scanning switch ON.
- **Code Scanning w/ alerts** = of those, repos currently producing code-scanning (CodeQL) alerts.
- **Secret scanning** and **Dependabot** are separate switches — that's why they're near 100%.

| Organization | Active repos | Code Scanning enabled | Code Scanning w/ alerts | Secret scanning | Dependabot updates | Open Dependabot alerts | Copilot seats |
|---|---|---|---|---|---|---|---|
| pfizer | 6,692 | 18 | 17 | 6,692 | 6,692 | 100,000* | 0 |
| pfizer-rd | 3,191 | 16 | 13 | 3,191 | 3,191 | 63,140 | 0 |
| pfizer-eps | 1,359 | 1,359 | 944 | 1,359 | 1,276 | 14,179 | 0 |
| pfizer-analytics | 1,146 | 11 | 7 | 1,146 | 1,146 | 41,130 | 0 |
| pfizer-digital-manufacuring | 998 | 1 | 1 | 998 | 998 | 34,986 | 0 |
| pfizer-fit | 863 | 0 | 0 | 863 | 863 | 17,486 | 0 |
| pfizer-business-services | 607 | 0 | 0 | 607 | 607 | 100,000* | 0 |
| pfizer-esc | 550 | 0 | 0 | 550 | 550 | 2,366 | 0 |
| pfizer-seagen | 253 | 1 | 1 | 253 | 253 | 14,310 | 0 |
| pfizer-operations-and-insights | 236 | 1 | 1 | 236 | 236 | 5,555 | 0 |
| pfizer-commercial | 194 | 3 | 3 | 194 | 194 | 4,198 | 0 |
| pfizer-evgen | 160 | 1 | 0 | 160 | 160 | 573 | 0 |
| pfizer-marm | 157 | 0 | 0 | 157 | 157 | 4,940 | 0 |
| pfizer-digital-supply | 152 | 0 | 0 | 152 | 152 | 1,717 | 0 |
| pfizer-oneweb | 127 | 0 | 0 | 127 | 127 | 960 | 0 |
| pfizer-finance | 104 | 0 | 0 | 104 | 104 | 3,491 | 0 |
| pfizer-eps-dpp | 64 | 0 | 0 | 64 | 64 | 2,049 | 0 |
| pfizer-clinical-supply | 53 | 0 | 0 | 53 | 53 | 6,929 | 0 |
| pfizer-devex | 37 | 0 | 0 | 37 | 37 | 220 | 3,551 |
| pfizer-pic | 25 | 0 | 0 | 25 | 25 | 4,923 | 0 |
| pfizer-ld | 13 | 0 | 0 | 13 | 13 | 128 | 0 |
| pfizer-compliance | 4 | 0 | 0 | 4 | 4 | 14 | 0 |
| pfizer-utils | 4 | 0 | 0 | 4 | 4 | 0 | 9 |
| **TOTAL** | **16,989** | **1,411** | **987** | **16,989** | **16,906** | **423,294** | **3,560** |

*\* capped at 100,000 by the API's counting limit — true figure is higher.*

---
---

# PART 2A — RESPONSES TO REVIEWER COMMENTS (reproduce these in OUTPUT 2)

For each comment below, the text in quotes is **my reply** — reproduce this list so I can paste
each reply into its comment thread. The "→ EDIT" pointer is only an internal cross-reference to
where the fix lives in the document; it is NOT part of the reply.
- **C1 (Sean — where did the numbers come from?):** "Per-org, via the GitHub API across all 23
  orgs on 4 Aug 2026. Full table added as Appendix A; raw CSV attached." → EDIT 0/1, Appendix A.
- **C2 (Sean — was pfizer-eps a pilot?):** "Reworded to drop 'pilot' and state only the verified
  fact." → EDIT 2.
- **C3 (Philippe — Copilot concentration is by design):** "Agreed; reframed as by-design and noted
  the move to enterprise-level deployment per the 05/08 GitHub meeting." → EDIT 3.
- **C4 (Philippe — seat/token economics):** "Added the seat-includes-token-allowance economics;
  idle seats = unused value while tokens are already over budget." → EDIT 4.
- **C5 (Philippe — spend is wrong):** "Correct — that was an Aug 1–4 partial pull. Replaced with
  the full July figure ($236,466 Copilot / $248,163 total) straight from the billing API, plus the
  ~$400k projection and the discount-ending driver." → EDIT 5, 5b, 5c, 5d, 12.
- **C6 (Philippe — review LLM content):** "Rewritten in plain language." → EDIT 6.
- **C7 (Sean — link the CSVs):** "Attached the raw per-org CSV and added Appendix A." → EDIT 7,
  Appendix A.
- **C8 (Philippe — licences are pay-as-you-go):** "Corrected — removed 'costs nothing'; noted
  Actions-minute and committer-based cost." → EDIT 8.
- **C9 (Sean — frame Sonar→CodeQL):** "Framed as standardising on CodeQL and consolidating away from
  SonarQube, using the July PoC — 100% vs 3.9% security signal, CWE mapping, no infrastructure — and
  corrected the doc's claim that Sonar 'accounts for the remaining coverage.' Included the balance
  caveats (3-repo sample; ~half of CodeQL's findings are workflow-permission; Sonar's code-quality
  findings need a replacement before any decommission). See the comparison report." → EDIT 9.
- **C10 (Sean — 14 zero-GHAS orgs by design?):** "Clarified: not excluded, just not enabled yet;
  prioritization to confirm with platform/security." → EDIT 10.
- **C11 (Philippe — repo/batch limit ~10?):** "Noted the batch-enablement limit; rollout runs in
  batches. Confirming the exact cap." → EDIT 11.
- **C12 (Philippe — consumption isn't 'small', add period, governance shortcomings):** "Reframed as
  growing; added July actual + ~$400k projection; pointed to existing governance to extend rather
  than new bodies." → EDIT 12.
- **C13 (Philippe — missing supply-chain items):** "Added release-process maturity, credentials-in-
  code, secret management, and artifact/JFrog to the Supply Chain section." → EDIT 13, Sections A/B.

---

# PART 2B — MY PRIVATE NOTES (ignore — not part of either output)

## Bottom line (read first)
- **Your coverage data is accurate** — GHAS/code-scanning 1,411 · CodeQL-with-alerts 987 · secret
  scanning 16,989 · Dependabot alerts 423,294 · Copilot 3,560 seats · per-org table. All verified
  against the raw scan; none disputed.
- **The one real error (spend) is now fixed with real data, and we have a verified 6-month trend.**
  Pulled directly from the GitHub billing API (all 23 orgs summed), Copilot spend climbed steadily:
  $51,705 (Feb) → $65,200 (Mar) → $77,659 (Apr) → $126,179 (May) → $149,247 (Jun) → $236,466 (Jul
  2026) — ~4.6× in five months. July matches the ~$250k Philippe quoted, so it's no longer hearsay.
  Honest caveat for the deck: plot **Copilot dollars**, not total spend or "% of total" — total is
  erratic (April Actions spike). See Section C.
- **This is not a rewrite** — ~14 targeted edits plus two new sections (CI/CD, Secrets).

## Questions still open (only ask if leadership presses — everything else is resolved)
- **Q6 — Release process / pipeline readiness (Philippe):** which specific release-process gaps to
  call out (no standard release process, manual promotion, missing gates)? *Optional detail for
  Section A.*
- **Q7 — JFrog / artifact management (Philippe):** does he want current artifact/binary management
  (JFrog Artifactory) and its gaps covered? *Optional detail for EDIT 13.*

## Notes
- **"External Dependencies" section — being deleted (EDIT 15).** It named three unverifiable
  workstreams ("GHAS Governance and Rollout Outline", "RAM integration workstream", "EMU readiness
  workstream") that were never in the source data. Decision: cut the whole section.
- **All `FIND:` text in Part 1 was checked against the actual document** — EDIT 2/3/4/5/6/7/8/10/12
  match word-for-word; EDIT 5b/5c/5d/9 target the real tables and sentences. The doc already uses
  "23 organizations". There is no six-tile scorecard (EDIT 0 places the summary at the top of the
  baseline instead).

**Already resolved — do NOT re-ask Philippe:**
- Spend: pulled from the billing API ourselves (July $236,466 / $248,163). Confirmed matches his
  ~$250k. No longer hearsay.
- Copilot Metrics API access: confirmed on. Only enterprise-level *engagement* is outside our
  org-scoped token — handled with the EDIT 14 caveat.
- The old note that "the tool undercounts Copilot / use Philippe's numbers not the tool's" was
  **wrong** and has been removed — the tool's billing pull captures the full enterprise Copilot
  spend (all 23 orgs summed).

## OPTIONAL — if Philippe sends the enterprise active-users number (last 60 days)
**You do not need this.** EDIT 14 already stands on real data: 3,560 seats, 2,247 active (63%),
1,313 idle (37%). If he sends the enterprise "active users, last 60 days" figure, it's a single
optional add — here's exactly where it goes:

1. **EDIT 14 table, last row** — replace `[PLACEHOLDER: to be supplied by enterprise admin]` with
   his number (e.g. "2,100 (59%)"). That's the only edit strictly needed.
2. **If his enterprise "total seats" differs from our 3,560** — our figure is the sum across all 23
   orgs. If his enterprise-consolidated total is very close, say they agree. If it differs, note
   it's enterprise-consolidated vs org-summed accounting; keep 3,560 in Appendix A either way.
3. **Slide deck one-liner** — the idle-seat point is your headline cost-efficiency line: *"We pay
   for 3,560 seats but 37% sit idle — unused licence value while token spend climbs toward $400K."*
   His 60-day number, if it arrives, just makes that line even tighter.

**Bottom line: finalize now.** The 37% idle figure is real and sufficient; the enterprise 60-day
number is a bonus, not a dependency.
