# Bolt Runner Review — 1-page Readout

**Companion to** `electron-runner-review.md` (full document, 22 findings with permalinks). This page is the version for the meeting.

## TL;DR

The setup is **solid overall on Linux**. Ephemerality, autoupdate-off, IMDSv2, encrypted EBS, permissions boundary, ECR pull-through cache — all right. **Windows tells a different story.**

Concerns cluster in four areas:

1. **Windows runners are non-ephemeral** — they reuse the same instance across jobs, with `ghrunner` as local Administrator and UAC disabled. Very different security model from Linux.
2. **Logging** — the CloudWatch agent is installed in the Ubuntu AMI but never started. Windows does start it. Fixing this on Linux almost certainly resolves the "logs disappear" symptom you've been seeing.
3. **Change control** — the runner module is pinned to a mutable branch (`pfizer-main`) and the config repo pins it to a second mutable branch (`deploy`) that is not branch-protected. Two unreviewed refs between commit and production.
4. **Cost efficiency** — real but modest at current 14K jobs/mo (~$100–500/mo across three levers). Scales to $1–7K/mo at 200K/mo.

**Nothing here is a fire.** Windows and logging are the two items worth doing this quarter.

## Top 3 asks (each 1–4 hours of work)

| # | Ask | Owner | Effort | Value |
|---|---|---|---|---|
| 1 | **Set `enable_ephemeral_runners: true` on Windows** (H0). Requires a scale-up smoke test. | Platform team | ~1 day (test + rollout) | Highest security win — collapses most of H7's blast radius. |
| 2 | **Enable the CloudWatch agent on Ubuntu** (H3). Copy the pattern from `data/bolt-windows/runner_setup.tftpl`. | Platform team | ~2 hours | Almost certainly fixes the missing-logs bug. |
| 3 | **Enable branch protection on the runner-module `deploy` branch** (H5). Two clicks. | Repo admin | 5 minutes | Closes a supply-chain hole with no code change. |

## What's done well (credit before critique)

- Linux runners **are ephemeral** — `enable_ephemeral_runners: true`.
- Runner autoupdate **is disabled** on both OSes.
- **IMDSv2 required** with hop-limit 1 on both — SSRF-hardened.
- **EBS encrypted** at build and runtime.
- **IAM has a permissions boundary** and mostly-scoped policies.
- **ECR pull-through cache** for Docker Hub and ghcr.io — clever, reduces egress and rate-limit exposure.
- **Windows runtime CloudWatch enablement** works correctly — Linux should copy that pattern (see ask #2).

## HIGH findings at a glance (8 total)

Grouped by cluster. Full detail + permalinks in the long doc.

**Windows security (Windows only)**
- **H0** — Windows runners are not ephemeral: [`runner-configs/win-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml)
- **H7** — Windows `ghrunner` is local Administrator, UAC disabled (with unresolved TODO), local-account password in runner service config: [`data/bolt-windows/runner_setup.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/runner_setup.tftpl)

**Logging (Linux only)**
- **H3** — CloudWatch agent installed by Ansible but never started; Windows starts it, Linux does not: [`ansible/tasks/cloudwatch-agent.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/cloudwatch-agent.yaml)

**Change control**
- **H4** — Runner module pinned to mutable branch `pfizer-main` (not a version tag): [`runner.tf` L2](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner.tf#L2)
- **H5** — Config repo pins to unprotected `deploy` branch: [`runners.tf` L2](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/runners.tf#L2)
- **H6** — GitHub App secrets pulled by `.value` into Terraform state: [`runner.tf` L22–27](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner.tf#L22-L27)

**Cost efficiency**
- **H1** — `minimum_running_time_in_minutes: 15` Linux / 30 Windows: [`ub-x86.yaml` L36](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L36), [`win-x86.yaml` L28](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml#L28)
- **H2** — Blocking `sleep 10` + sync Lambda invoke on every job teardown: [`post-job-hook.tftpl` L73](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl#L73)

*(9 MEDIUM and 5 LOW findings in the long doc — none urgent.)*

## Cost, one line

At **14K jobs/mo**: fixing H1 + H2 + choosing spot/on-demand deliberately (M9) is worth roughly **$100–500/mo** in AWS spend. At **200K jobs/mo** it becomes **$1.5K–4K/mo**. Per-1K jobs the total lever is ~$10–40. Not the headline reason to act — logging (H3) and Windows (H0/H7) are — but easy wins to bundle in.

## What we couldn't answer from source (out-of-band checks needed)

- Terraform state backend encryption / lock config — not in the repos; presumably handled by `pfizer/tf-ga-helper`. Should be verified.
- Whether the philips-labs fork's `pfizer-main` branch is itself protected.
- Whether the AMI pipeline builds from `main` (protected) or `deploy` (unprotected) on the AMI repo.
- What fraction of jobs run on Windows (sizes H0/H7 impact).
- Whether 14K/mo or a higher target (200K/mo referenced in the brief) is the correct planning horizon for cost decisions.
