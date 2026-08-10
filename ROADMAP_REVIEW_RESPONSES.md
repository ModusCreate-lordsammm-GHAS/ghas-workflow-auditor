# Roadmap Review — Responses, Edits & Questions

A working sheet for addressing every comment on *Pfizer Strategic Enterprise GitHub
Expansion Roadmap*. For each comment: **who** raised it, **what** they said, **the reply
you can post**, and **the exact edit** to make in the document.

---

## Bottom line (read first)

- **Your coverage data is accurate.** GHAS 1,411 · CodeQL 987 · secret scanning 16,989 ·
  Dependabot alerts 423,294 · Copilot 3,560 seats · repo counts · per-org table — all
  verified against the raw scan. None of these were disputed.
- **Only one real data error: the spend figure** ($18,458 / $17,781). It was only the
  first 4 days of August, not a full month. Being fixed with a multi-month pull.
- **This is not a rewrite.** ~12 targeted edits + the spend fix.

---

## Part 1 — Comment-by-comment

### C1 — Sean Clayton · Executive Summary (on the numbers)
**Said:** "Where did these numbers come from?"
**Reply to post:** "All coverage figures are per-organization, collected directly via the
GitHub API across all 23 orgs on 4 Aug 2026. Full per-org table added as Appendix A; raw
CSV attached."
**Edit:** Add to the top of the Executive Summary: *"All coverage figures are per-organization,
collected via the GitHub API across all 23 organizations on 4 August 2026; the full
breakdown is in Appendix A."*

### C2 — Sean Clayton · "pfizer-eps is not just a pilot anymore… scalable past 1,300 repositories"
**Said:** "Was it intended to be a pilot?" + "rewrite this sentence or cut it — my vote is cut."
**Reply to post:** "Reworded to drop the 'pilot' framing and state only the verified fact."
**Edit:** Replace that sentence with: *"pfizer-eps runs GHAS with code scanning across all
1,359 of its repositories, showing the configuration works at scale (1,300+ repos) in
Pfizer's environment."*

### C3 — Philippe Armando · Copilot "concentrated in pfizer-devex" (Exec Summary)
**Said:** "This is by design — has to move to enterprise, since the enterprise team will be
the default to deploy Copilot soon (from GitHub, meeting 05/08/2026)."
**Reply to post:** "Agreed — reframed as by-design and noted the move to enterprise-level
deployment per the 05/08 GitHub meeting."
**Edit:** Replace with: *"Copilot is currently deployed mainly through pfizer-devex (3,551 of
3,560 seats). This concentration is by design: per GitHub's guidance (meeting of 05/08/2026),
Copilot deployment is moving to enterprise-level management as the default path. The relevant
measure is enterprise-wide utilization, not per-org expansion."* (Delete the word "pilot.")

### C4 — Philippe Armando · "37% of seats inactive… make sure seats are used"
**Said:** "Need more details — a seat provides a free token allowance, and we've already
overconsumed tokens, so a figure on the economics would be nice."
**Reply to post:** "Added the seat/token economics — see the token-allowance vs actual-
consumption figure now included."
**Edit:** Replace with: *"Of those seats, 37% were inactive last cycle. Since each seat
includes a token allowance before usage-based charges apply, inactive seats mean unused
licence value while overall token consumption is already over budget."* Then insert the
figure from **Question 2** below.

### C5 — Philippe Armando · SPEND ("Total platform consumption spend for the period was 18,458 dollars…")  ← the one real error
**Said:** "This is wrong — we spend 100k this month (June was lower). Add the specific period."
**Reply to post:** "Correct — that figure was month-to-date (Aug 1–4 only), not a full month.
Replaced with complete-month figures and a 3–6 month trend, with the period labeled."
**Edit:** **Delete $18,458 and $17,781.** Replace with the multi-month figures (being pulled)
or the authoritative number from **Question 1**. Never re-insert a partial-month number.

### C6 — Philippe Armando · "The thread running through all five findings…"
**Said:** "Please review LLM-generated content."
**Reply to post:** "Rewritten in plain language."
**Edit:** Replace the paragraph with: *"These findings connect: enabling GHAS produces CodeQL
results (security), Copilot adoption affects developer output (productivity), and both drive
platform consumption (cost). The roadmap tracks all three on one baseline."*

### C7 — Sean Clayton · "platform_metrics_by_org.csv / platform_metrics_by_repo.csv"
**Said:** "Can we provide a link to these or add as an addenda?"
**Reply to post:** "Attached the raw per-org CSV and added the full per-org table as Appendix A."
**Edit:** Attach `platform_metrics_by_org.csv`; add "(see Appendix A)"; paste the Appendix A
table (Part 3 below).

### C8 — Philippe Armando · CodeQL "cheapest security improvement… costs nothing beyond the license"
**Said:** "Licences are pay-as-you-go, so all of this is extra cost."
**Reply to post:** "Corrected — enabling scanning consumes Actions minutes, and extending
GHAS to new repos adds committer-based cost. Removed the 'costs nothing' wording."
**Edit:** Replace "costs nothing beyond the license Pfizer already holds" with: *"requires no
new tooling licence, though it does consume Actions minutes and, where it extends GHAS to new
repositories, adds to committer-based GHAS cost."*

### C9 — Sean Clayton · Section 3.2 "The 70% figure…" (SonarQube)
**Said:** "Understand SonarQube coverage. Frame this as switching Sonar→CodeQL. Include
Fernando's figures and explain why CodeQL is better than Sonar."
**Reply to post:** "Added a Sonar→CodeQL framing using the July 2026 PoC comparison (attached),
including the security-signal, infrastructure, and CWE points."
**Edit:** Add: *"Pfizer currently runs SonarQube (sonar.pfizer.com). A July 2026 proof-of-
concept on 3 repositories where both tools were active found CodeQL surfaced 90 open findings,
all security-relevant (100%), versus SonarQube's 4,646 open findings of which 181 (3.9%) were
security-related. CodeQL needs no dedicated infrastructure and maps every finding to CWE.
(PoC caveats: 3-repo sample, directional; SonarQube also covers code-quality, which CodeQL
does not — see the CodeQL vs SonarQube comparison report.)"*
**Note:** You no longer need Fernando's data separately — the comparison doc you added supplies it.

### C10 — Sean Clayton · "Fourteen organizations have zero GHAS enabled repositories" (x2 comments)
**Said:** "Is this by design? Are they good candidates?"
**Reply to post:** "Clarified these aren't deliberately excluded — GHAS just hasn't been
enabled yet. Candidate prioritization to be confirmed with platform/security (see open question)."
**Edit:** Add: *"This reflects that GHAS code scanning has not yet been enabled in these
organizations, not a deliberate exclusion. Which are priority candidates for enablement is a
business decision to confirm with the platform and security teams."* (Answer from **Question 5**.)

### C11 — Philippe Armando · near the Dependabot/hygiene paragraph
**Said:** "Plus the repo limit? I think there is a max 10?"
**Reply to post:** "Noted — CodeQL default-setup batch enablement has a GitHub-imposed limit,
so rollout runs in batches. Confirming the exact cap."
**Edit:** Add to the CodeQL rollout note: *"Enabling CodeQL default setup at scale is subject
to GitHub's batch-enablement limits, so rollout proceeds in batches."* (Confirm number via **Question 4**.)

### C12 — Philippe Armando · Section 3.4 "Token-based consumption is currently small…"
**Said:** "Put the period — the number doesn't make contextual sense; next month we'll spend
$400k on Copilot. Governance already exists — talk about its shortcomings."
**Reply to post:** "Reframed — consumption is growing fast, not small; added the period and the
$400k projection; and pointed to existing governance and its shortcomings rather than proposing
new bodies."
**Edit:** Replace "currently small… while the number is still manageable" with: *"Token-based
consumption is growing rapidly and is dominated by Copilot; projected Copilot spend for [next
month] is approximately $400k. Consumption governance already exists at Pfizer — the priority
is addressing its current shortcomings, not creating new structures."* (Shortcomings from **Question 3**.)

### C13 — Philippe Armando · "What This Document Does Not Cover"
**Said:** "Internalize delivery chain, lack of release process, still credentials in code,
better secret management — several key items are missing."
**Reply to post:** "Added these to the Supply Chain section as areas the roadmap addresses."
**Edit:** In the Supply Chain Discipline section, add: *"release-process maturity (many teams
lack a defined release process), credentials still present in code, and secret-management
practices."* (Confirm framing via **Question 3**/Philippe.)

---

## Part 2 — Questions to ask (understandable, with why + what you'll do)

Send all to **Philippe** except Q5 (platform/security team). Each says why it matters so he
knows it's not busywork.

**Q1 — Monthly spend (fixes C5).**
"What's our actual monthly GitHub platform spend — total and Copilot separately — and for
which month? The figure in the draft was only a 4-day partial pull; I want to cite the real
monthly number."
→ *You'll use this to replace the wrong spend figure.*

**Q2 — Copilot token economics (fixes C4).**
"How many tokens does a Copilot seat include before usage charges start, and roughly how much
are we consuming/over-consuming? I want to show the economics of idle vs active seats."
→ *You'll add this figure to the Copilot section.*

**Q3 — Existing governance + shortcomings (fixes C12/C13).**
"You mentioned governance already exists around consumption — can you point me to it and its
main shortcomings? I want to reference the real thing, not propose new bodies."
→ *You'll describe existing governance and what to improve, instead of inventing structures.*

**Q4 — CodeQL batch limit (fixes C11).**
"What's the exact limit on CodeQL default-setup batch enablement (you mentioned ~10)? I'll
reflect it in the rollout plan."
→ *You'll state the correct batch size in the phased rollout.*

**Q5 — Priority orgs (fixes C10) — ask platform/security team.**
"Of the 14 orgs with no GHAS enabled, which are the priority candidates to enable next?"
→ *You'll name the first-wave orgs in the roadmap.*

---

## Part 3 — Appendix A (paste into the doc; also attach the CSV)

Per-organization baseline, from the GitHub API, 4 Aug 2026:

Column note (GHAS = Secret Scanning + Code Scanning + Dependabot):
- **Code Scanning enabled** = repos with the Advanced Security / code-scanning switch ON (1,411).
- **Code Scanning w/ alerts** = of those, repos currently producing code-scanning (CodeQL) alerts (987).
- **Secret scanning** and **Dependabot** are separate switches — that's why they're separate
  columns and near 100%.

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

**GHAS vs CodeQL:** GHAS = the paid licence (includes secret scanning, push protection, and
code scanning). CodeQL = the code-scanning engine inside GHAS. "GHAS 1,411" = repos licensed;
"CodeQL 987" = of those, how many actually turned scanning on. The 424 gap = paid-for-but-not-
scanning.

---

## Part 4 — Spend: use Philippe's authoritative enterprise figures (not the tool)

**Decision:** the tool's org-level billing API *undercounts* Copilot, because Copilot is billed at
the **enterprise** level, not per-org. Philippe has the real numbers, so use his — do not use a
tool-derived Copilot spend figure in the report.

**Authoritative figures from Philippe:**
- Copilot spend **July 2026 ≈ $250,000**
- Projected **≈ $400,000 by Sep/Oct 2026**
- A **discount is ending**, which is part of the increase (a real cost-driver to state).

**Edit:** wherever spend appears, replace the old $18,458 / $17,781 with these enterprise figures
and name the period. Frame it as a rising, discount-sensitive cost that needs governance now.

*(A `--billing-month` option was added to the collector so it can pull complete past months for
Actions/storage spend, but the headline Copilot number must come from enterprise billing.)*

---

## Part 5 — Philippe's second review (report needs more depth)

Philippe's verdict: **slides are good; the report needs more work.** It's light on CI/CD,
pipeline readiness, secrets management, and release process. Below is what we can answer with
real data now, and what needs his input.

### 5a. CI/CD pipeline issues — WE HAVE THIS DATA (from the audit tool)
The GHAS Workflow Audit already scanned every workflow file across all orgs. Latest results
(run 2026-06-29 — consider a fresh re-run for current numbers):

- **85,497 total findings** across **23 orgs** and **9,113 repositories**
- **51,090 real security issues**: 43,448 critical · 7,194 high · 448 medium (the rest are
  informational inventory)
- Top issue types:
  - missing workflow permissions: 17,445
  - unvetted action owner: 12,533
  - unpinned action (tag, not SHA): 12,097
  - `action_on_branch`: 1,295 · `write_all_permissions`: 1,005 · `pull_request_target`: 170 ·
    `curl_pipe_shell`: 103

**Add to report:** a "CI/CD Pipeline Security" section with these numbers. This is a strong,
data-backed answer to his ask.

### 5b. Secrets / credentials in pipelines — WE HAVE THIS
- **~4,572 hardcoded secret/key findings in workflow files**: `aws_secret` 3,210 + `app_rsa_key`
  1,362. This is the "still credentials in code" concern, quantified.
- Plus the platform secret-scanning picture (from the metrics baseline): secret scanning enabled
  on **16,989 repos (100%)**, push protection on **16,989 (100%)**, **1,809 open secret-scanning
  alerts**.

**Add to report:** a "Secrets Management" section combining pipeline hardcoded-secret findings
(4,572) + platform secret-scanning coverage (100%) + open alerts (1,809).

### 5c. Release process / pipeline readiness / JFrog — NEEDS PHILIPPE
Not visible to the GitHub API. These are architecture/process items only Philippe/the team can
frame. See Questions Q6–Q7.

### 5d. Copilot engagement — API access now ON; enterprise is the relevant level
Philippe confirmed "Copilot Metrics API access" is enabled, and that **enterprise** stats are
more relevant than pfizer-devex org stats. Our tool's token is org-scoped, so enterprise-level
metrics need enterprise access. See Question Q8.

### New questions to add
**Q6 — Release process / pipeline readiness (Philippe).**
"For the report's CI/CD section, what specific release-process and pipeline-readiness gaps do you
want called out (e.g., no standardized release process, manual promotion, missing gates)?"

**Q7 — JFrog / artifact management (Philippe).**
"You mentioned JFrog or an alternative — do you want the report to cover current artifact/binary
management (JFrog Artifactory) and its gaps? If so, what's the current state and the concern?"

**Q8 — Enterprise Copilot seats + engagement (Philippe).**
**Tested (2026-08-10):** our GitHub App CANNOT reach enterprise Copilot data — enterprise
seats and enterprise billing both return **403 "Resource not accessible by integration"**, and
enterprise metrics returns 404. So per-org seats show 0 for every org except pfizer-devex
(3,551) and pfizer-utils (9) because Copilot is enterprise-managed and our org-scoped App can't
see the enterprise level.
Ask Philippe: "Our App is org-scoped and gets a 403 on all enterprise Copilot endpoints, so we
can't pull enterprise seats/usage. Can you (or an enterprise admin) provide the enterprise-wide
Copilot seat count and engagement (active/engaged users)? That's the number that actually
matters, since seats are managed at the enterprise, not per org."
