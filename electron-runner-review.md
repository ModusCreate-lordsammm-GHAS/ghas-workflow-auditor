# Pfizer Electron / Bolt Self-Hosted Runner — Best-Practices Review

**Reviewer's note.** This review is based only on what is visible in the three repos below at the commit SHAs recorded in the "Sources & References" section. Anything not visible in source (Terraform state backend config, tfvars, deploy tooling in `pfizer/tf-ga-helper`, GitHub App scope, actual pool sizes) is called out as an open question rather than a finding.

## Repos reviewed

| Repo | Authoritative branch reviewed | Also spot-checked | Notes |
|---|---|---|---|
| `pfizer/mi-electron-github-runner-ubuntu` (AMI) | `main` (protected) | `deploy` (unprotected) | Packer + Ansible AMI build |
| `pfizer/terraform-aws-electron-github-runners-config` (orchestration) | `deploy` (protected) | `2.x` (protected) | Terraform root module — no `main` branch exists |
| `pfizer/terraform-aws-electron-github-runner` (runner module + bootstrap) | `deploy` (**unprotected**) | `2.x` (protected) | Wrapped by config repo above; no `main` branch exists |

**Volume assumed:** 200,000+ workflow runs/month. Cost figures below use that baseline; treat them as order-of-magnitude, based on public c6i.xlarge pricing (~$0.17/hr on-demand, ~$0.06/hr spot).

---

## Summary

The setup is **solid overall**, clearly built by people who know what they're doing. Ephemeral runners are correctly configured (`enable_ephemeral_runners: true`), autoupdate is off (`disable_runner_autoupdate: true`), IMDSv2 is required with hop-limit 1, EBS is encrypted, IAM has a permissions boundary, and the ECR pull-through cache is a clever egress optimisation. Security posture is defensible.

The concerns cluster in three areas, ordered by real impact at 200K jobs/month:

1. **Cost efficiency** — `minimum_running_time_in_minutes: 15` and the `sleep 10` in every post-job hook together are the biggest levers in the stack. Tuning them is worth **~$1K–4K/month**.
2. **Logging** — the AMI installs the CloudWatch agent but never configures or starts it; the philips-labs module wires it at runtime via SSM. Two layers touch log shipping with no single owner — the most likely explanation for reports of missing logs.
3. **Supply chain / change control** — the runner module is pinned to a mutable branch (`pfizer-main`), the config repo pins the runner module by mutable branch (`deploy`), and that `deploy` branch is **not protected**. Two unreviewed mutable refs sit between commit and production.

Nothing here is a fire. The logging and cost items are the ones worth doing this quarter.

---

## What's Done Well

- **Ephemeral, single-use runners.** `enable_ephemeral_runners: true` in the philips-labs config; deregistration is handled by the philips-labs module on ephemeral exit — no ghost-runner accumulation observed in the code path.
- **Runner autoupdate disabled** (`disable_runner_autoupdate: true`). Correct for a controlled environment where agent version is pinned at image-build time.
- **Non-root service account.** `runner_run_as: ghrunner`. The `ghrunner` user has passwordless sudo and is in the docker group, but that is a deliberate design decision for ephemeral hosts and is documented in the Ansible comments.
- **IMDSv2 required** with `http_put_response_hop_limit: 1` — SSRF-hardened, protects the instance role from being stolen via a workflow request.
- **EBS boot volume encrypted** in both the Packer build (16 GB) and the runtime launch template (40 GB gp3, 750 MB/s).
- **Session Manager for SSH** on builders (no port 22 open, no key management).
- **IAM policies mostly least-privilege** — `ec2:CreateTags` is conditioned on tag; `ssm:GetParameter` is enumerated to specific parameter ARNs; ECR pull-through is scoped to the two cache repos.
- **Role permissions boundary applied.** Defence-in-depth against role privilege escalation.
- **Corporate root CAs** installed in the AMI. TLS-inspection proxies work out of the box.
- **CrowdStrike Falcon + Nessus agents** present in the AMI — endpoint protection meets enterprise policy.
- **ECR pull-through cache for Docker Hub and ghcr.io**, plus a docker wrapper in `user-data.sh` that rewrites `docker pull ghcr.io/foo` to the ECR URL. Reduces external egress, avoids Docker Hub rate limits, keeps images inside the VPC.
- **Toolcache pre-populated** with Python 3.9–3.14. Fast boot-to-ready for common toolchains.
- **KMS customer-managed keys** for parameter encryption; instances get an explicit `kms:Decrypt` policy scoped to the right key alias.
- **Runner registration uses SSM Parameter Store**, not launch-template plaintext, for both the GitHub App credentials and the enterprise PAT.
- **Multi-region** (us-east-1 + eu-west-1) with separated proxy tiers managed by ASG.

---

## Findings & Recommendations

### HIGH

#### H1 — `minimum_running_time_in_minutes: 15` on ephemeral runners
- **What:** philips-labs config sets a 15-minute minimum billed lifetime per runner instance.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`runner-configs/ub-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L36)
- **Risk:** Every ephemeral runner is billed for at least 15 minutes even if the job took 45 seconds. At 200K jobs/month this is the single largest cost multiplier in the stack.
- **Recommendation:** Instrument the actual job-duration distribution (median, p90). If most jobs finish in <5 min, drop this to 5 (the philips-labs floor). If most are <10, drop to 10. The value exists to smooth scale-down thrash; it should be tuned to the observed distribution, not left at the module default.
- **Priority:** HIGH.
- **Cost impact:** Illustrative — if median job is 4 min and 60 % of jobs are <15 min, dropping 15 → 5 saves ~10 min × ~120K jobs = **~20,000 instance-hours/month**. c6i.xlarge spot ($0.06) ≈ **~$1,200/mo**; on-demand ≈ **~$3,400/mo**. Likely the highest-$-value finding in the review.

#### H2 — Blocking `sleep 10` + synchronous Lambda invoke on every job teardown
- **What:** `post-job-hook.tftpl` runs `sleep 10` then a synchronous `aws lambda invoke` to the proxy-log-searcher on every job completion.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`data/bolt-ubuntu/post-job-hook.tftpl` around line 73 (`sleep 10`) and line 87 (`aws lambda invoke`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl#L73-L92)
- **Risk:** 200K × 10s = 2,000,000 CPU-seconds ≈ **~23 CPU-days/month** wasted in pure sleep, plus average Lambda cold-start on top. Directly extends billed instance-hours (the 15-min minimum masks it for short jobs but pushes borderline jobs into the next billing increment).
- **Recommendation:** Make the Lambda call async (`--invocation-type Event` — fire and forget). Delete the sleep, or, if it exists to allow logs to flush before termination, replace with a specific flush (`systemctl stop amazon-cloudwatch-agent`).
- **Priority:** HIGH.
- **Cost impact:** ~**$95–270/month** in wasted instance-hours (spot vs on-demand). Also cuts ~10 s off p95 job-completion latency — user-visible.

#### H3 — CloudWatch agent installed but not configured or enabled in the AMI
- **What:** The Ansible task downloads and dpkg-installs `amazon-cloudwatch-agent.deb`, then deletes the .deb. There is no config file drop, no `fetch-config` from SSM, no `systemctl enable/start`.
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`ansible/tasks/cloudwatch-agent.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/cloudwatch-agent.yaml)
- **Note:** The philips-labs module DOES wire `runner_log_files` (syslog, user-data.log, `_diag/*`) via SSM at boot time — see [`runner-configs/ub-x86.yaml` L38–L52](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L38-L52) — so logs generally do ship. But there is no single owner.
- **Risk:** Ambiguous ownership of log shipping. If SSM ever fails or the instance starts a job before SSM has settled, logs are lost silently for that instance. **This is the most likely explanation for the "logs disappear" reports** — the AMI leaves the agent installed-but-idle, so any diagnostic looking at the image assumes it's doing the shipping when the philips-labs runtime step is the actual owner.
- **Recommendation:** Pick one owner. Either (a) **delete the pre-bake install** entirely and let philips-labs own it at runtime (simplest — one layer, one story), or (b) drop a functional `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json` in the image and `systemctl enable amazon-cloudwatch-agent` so logs ship from t=0. Then document, in the AMI README, which layer owns log shipping.
- **Priority:** HIGH.
- **Cost impact:** CW Logs ingestion at 200K jobs × ~5 MB/job ≈ **~1 TB/month × $0.50/GB = ~$500/mo ingestion** once fully functional. Apply metric filters to drop noisy syslog lines.

#### H4 — Runner module pinned to a mutable branch (`pfizer-main`), not a version tag
- **What:** `runner.tf` sources the philips-labs fork as `git::ssh://git@github.com/pfizer/terraform-aws-github-runner//modules/multi-runner?ref=pfizer-main`. This is a moving branch, not a semver tag or SHA.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`runner.tf` L2](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner.tf#L2)
- **Risk:** Any commit pushed to `pfizer-main` on the fork is picked up on next `terraform apply` with no PR-level review of what changed. Supply-chain vector: anyone with push rights to the fork effectively deploys to production.
- **Recommendation:** Pin to an immutable ref — a semver tag (e.g. `?ref=v7.3.0-pfizer.1`) or a full commit SHA. If tracking a branch is required, add a scheduled `terraform plan` job that alerts on drift.
- **Priority:** HIGH.
- **Cost impact:** None direct. High blast-radius if abused.

#### H5 — Runner-module `deploy` branch is unprotected but is the deployment target
- **What:** The config repo pins the runner module to `?ref=deploy` — and that `deploy` branch on `pfizer/terraform-aws-electron-github-runner` is **not** branch-protected (verified via GitHub API — `protected: false`).
- **Where:**
  - Consumer pins it: `terraform-aws-electron-github-runners-config` @ `deploy` — [`runners.tf` L2](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/runners.tf#L2)
  - Target of the pin: `terraform-aws-electron-github-runner` — [`deploy` branch settings](https://github.com/pfizer/terraform-aws-electron-github-runner/settings/branches)
- **Risk:** A single unreviewed push (or force-push) to `deploy` reaches production on the next apply of the config repo. Combined with H4, there are two unprotected mutable refs between commit and prod. Either one is enough for an accident or an insider action to hit the whole fleet.
- **Recommendation:** Enable branch protection on `deploy` (require PR review, require status checks, disallow force-push, disallow deletion). Better still: pin `runners.tf` L2 to a tag or commit SHA and use `deploy` only as a promotion label, not a live ref.
- **Priority:** HIGH.
- **Cost impact:** None direct.
- **Note on the config repo:** The config repo's own `deploy` branch **is** protected. This finding is specifically about the *runner-module* repo's `deploy` branch.

#### H6 — GitHub App private key / ID / webhook secret pulled by `.value` into Terraform state
- **What:** `runner.tf` reads `github_app_key`, `github_app_id`, and `webhook_secret` via `data.aws_ssm_parameter.*.value` and passes them into the module. Terraform stores these values in the state file in plaintext on every apply.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`runner.tf` L22–L27](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner.tf#L22-L27)
- **Risk:** Whoever reads the state file has the enterprise-runner-registration credentials. If the state backend is not encrypted (see M1), or if state is ever downloaded locally for troubleshooting and left on disk, the secrets leak.
- **Recommendation:** Where possible, pass only parameter *names* to the module and have the module resolve them at runtime (philips-labs supports `github_app.key_base64_ssm` etc.). At minimum: verify the S3 backend uses SSE-KMS with a customer-managed key + DynamoDB locking + tight IAM read scope on the state bucket, and have a documented rotation runbook.
- **Priority:** HIGH.
- **Cost impact:** None direct.

---

### MEDIUM

#### M1 — No backend block visible in source; state config lives outside these repos
- **Where:** `terraform-aws-electron-github-runners-config` @ `deploy` — [`versions.tf`](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/versions.tf) (only 10 lines; no `terraform { backend "s3" { ... } }` block).
- **Risk:** Backend is presumably injected by the `pfizer/tf-ga-helper` shared workflow. From these repos alone, encryption / locking / access control of state cannot be verified. State configuration divorced from source is harder to audit; if the shared helper regresses, downstream regresses silently.
- **Recommendation:** Either declare the backend inline in `versions.tf` (with `key` templated per environment), or document — in the repo README — where state lives, how it is encrypted, who has read access, and how the lock table is configured. Add a `terraform state list` step in CI as a smoke test.
- **Priority:** MEDIUM.

#### M2 — Docker installed via `curl https://get.docker.com | sh` at image-build time
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`ansible/tasks/docker-install.yaml` L10–L14](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/docker-install.yaml#L10-L14)
- **Risk:** Whatever `get.docker.com` serves at build time gets baked into the image, with no checksum or signature verification. Non-reproducible and supply-chain-vulnerable.
- **Recommendation:** Use the official Docker apt repo with a pinned version (`apt-get install -y docker-ce=5:24.0.7-1~ubuntu.22.04~jammy` etc.), gpg-verified via the docker.com apt key. Bump the pin deliberately.
- **Priority:** MEDIUM.

#### M3 — Docker Hub credentials baked into image via `docker login`
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`ansible/tasks/docker-install.yaml` around L42–L46 (task "Docker Login")](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/docker-install.yaml#L42-L46)
- **Risk:** `docker_login` writes base64-encoded credentials to `~/.docker/config.json`, which becomes part of the AMI. Every runner ships with usable Docker Hub credentials on disk that a workflow can trivially read.
- **Recommendation:** Remove the `docker login` from image build. Rely on the ECR pull-through cache (already configured) for the images the org actually needs. If direct Docker Hub pulls are still required, inject short-lived credentials at job start via the pre-job hook and unset them in the post-job hook.
- **Priority:** MEDIUM.

#### M4 — Sensitive tokens passed to Ansible via `--extra-vars` on the CLI
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`main.pkr.hcl` L20–L30](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/main.pkr.hcl#L20-L30)
- **Risk:** Packer invokes Ansible with `--extra-vars "docker_token=... github_token=..."`. These appear in `ps auxf` on the builder while Ansible runs. Any co-tenant on the Packer builder can capture them; also lands in shell history / build logs if `set -x` is ever enabled.
- **Recommendation:** Pass via `--extra-vars @secrets.yaml` (file chmod 600, deleted via `trap`), Ansible Vault, or fetch directly from SSM/Secrets Manager inside the playbook so they never touch a CLI arg.
- **Priority:** MEDIUM.

#### M5 — Hardcoded Artifactory IP `162.48.120.68/32` in security group
- **Where:** `terraform-aws-electron-github-runners-config` @ `deploy` — [`security_groups.tf` L51–L58 (`aws_security_group_rule.egress_runner_to_artifactory`)](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/security_groups.tf#L51-L58)
- **Risk:** IP-based allow rules break silently when the target moves. One IP change at Artifactory and every runner fails to fetch dependencies at once — a fleet-wide outage from a change outside your team's control.
- **Recommendation:** Resolve at plan time via a DNS data source (`data "external"`), or run a Lambda that periodically syncs the SG from a DNS name; better still, use a Pfizer-internal PrivateLink endpoint for Artifactory and allow the endpoint SG.
- **Priority:** MEDIUM.

#### M6 — Hardcoded VPC ID default in runner module
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`variables.tf` around L96 (`variable "vpc_id" { default = "vpc-0aedf14e7c9f0c024" }`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/variables.tf#L94-L98)
- **Risk:** A consumer who does not override the default gets a subtly-wrong deployment or a plan failure referencing a resource they cannot see.
- **Recommendation:** Remove the default — require the caller to specify. Or move Pfizer-specific defaults to a wrapper module and keep the reusable module clean.
- **Priority:** MEDIUM.

#### M7 — Hardcoded KMS multi-region key default (`ami_kms_key_id`); README documents a different key
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`variables.tf` L7–L11 (`ami_kms_key_id`, default `mrk-c4229f61e0284f89a53e9e876d3230b3`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/variables.tf#L7-L11). The README documents a different default (`mrk-57c12f2f22f049f8a7543555044dda4b`).
- **Risk:** Consumers trusting the README pick a KMS key that doesn't exist in their account, or a stale one. Encrypted resources become unreadable or plans fail obscurely.
- **Recommendation:** Pick one source of truth. Prefer no default (require caller to pass) and update the README to match.
- **Priority:** MEDIUM.

#### M8 — Deployment workflow runs on the fleet it deploys (circular dependency)
- **Where:** `terraform-aws-electron-github-runners-config` @ `deploy` — [`.github/workflows/package.yml` L11 (`runs-on: [ self-hosted, bolt-ubuntu ]`)](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/.github/workflows/package.yml#L11)
- **Risk:** If the bolt fleet is down, the workflow that would fix it cannot run. Recovery from a bad deploy requires the very fleet the bad deploy broke.
- **Recommendation:** Run the deploy pipeline on GitHub-hosted runners, or on a separately-managed "management" self-hosted pool. Keep application/CI workflows on `bolt-ubuntu`.
- **Priority:** MEDIUM.

#### M9 — `instance_target_capacity_type` defaults to `spot`
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`variables.tf` L53 (`instance_target_capacity_type = optional(string, "spot")`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/variables.tf#L50-L54)
- **Risk:** At 200K jobs/month, even a 1 % spot-interruption rate = **~2,000 failed jobs/month for infra reasons**, not code reasons. Developers see flaky CI and lose trust in the platform.
- **Recommendation:** Mixed strategy — spot for jobs known to be idempotent/retriable (opt-in via a label like `spot-ok`), on-demand for release/prod-critical jobs. Instrument actual spot-interruption rate before deciding the split.
- **Priority:** MEDIUM.
- **Cost impact:** Big lever either way. Spot vs on-demand at c6i.xlarge = $0.06 vs $0.17. On 200K jobs × ~30 min mean billed time = 100K instance-hours/mo → **~$6K spot vs ~$17K on-demand**. A 70/30 hybrid is a reasonable starting point.

---

### LOW

#### L1 — `set +u` disabled immediately before `${start_runner}` template expansion
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`data/bolt-ubuntu/user-data.sh` (last lines — search for `set +u`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh)
- **Risk:** Bash strict mode disabled at the most critical bootstrap step. If the templated block references an unset variable, it silently continues with an empty value instead of failing loudly. Historically the cause of "runner boots but never registers" incidents.
- **Recommendation:** Remove the `set +u`; ensure the templated block sets defaults for every variable it uses (`: "${RUNNER_NAME:=}"`).
- **Priority:** LOW.

#### L2 — Drift between `deploy` and `2.x` branches of the bootstrap
- **Where:** `terraform-aws-electron-github-runner` — [`data/bolt-ubuntu/user-data.sh` on `deploy`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh) is 12,782 bytes; [same file on `2.x`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/72b7c2d8cf7eca9edeb44e7884704f4ec86c7e7a/data/bolt-ubuntu/user-data.sh) is 7,909 bytes. Only `deploy` has the ECR-pull-through docker wrapper.
- **Risk:** Confusing for anyone reading `2.x` expecting production behavior. Merge/rebase conflicts multiply over time.
- **Recommendation:** Consolidate. Either fold `deploy` back into `2.x` (or a new `main`) and cut a release tag, or officially deprecate `2.x`. Do not maintain two divergent long-lived branches of a bootstrap script.
- **Priority:** LOW.

#### L3 — `enable_jit_config: false` — using the older token flow
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`runner-configs/ub-x86.yaml` L10](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L10)
- **Risk:** The older flow uses a broader-scoped registration token with a longer TTL. Smaller blast-radius reduction than JIT.
- **Recommendation:** Set `enable_jit_config: true`. Requires runner agent v2.298+ (already the case).
- **Priority:** LOW.

#### L4 — Runner agent version pulled from `releases/latest` at build time
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`ansible/tasks/actions-runner.yaml` L10–L22](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/actions-runner.yaml#L10-L22)
- **Risk:** Two consecutive AMI builds a week apart can ship different agent versions with no changelog entry. Runtime autoupdate is correctly disabled, so this is a build-time-only concern.
- **Recommendation:** Pin the agent version as a Packer variable, verify the release checksum, bump deliberately.
- **Priority:** LOW.

#### L5 — No explicit metric/alarm for ghost-runner accumulation
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — no such alarm exists in the module.
- **Risk:** philips-labs handles deregistration on ephemeral runners, but there is no visible alarm on the case where deregistration silently fails and offline runners stack up at the GitHub Enterprise level.
- **Recommendation:** Weekly scheduled Lambda that lists runners via the GitHub Enterprise API and alarms if `offline` count exceeds a threshold (e.g., 50) or any runner has been offline > 1 h. Cheap insurance against a silent regression.
- **Priority:** LOW.

---

## Cross-Cutting Observations

- **The logging bug is almost certainly the AMI/module ownership split (H3).** Two layers touch CloudWatch, neither is authoritative in source, and there's no README section explaining which one owns log shipping. Fix H3 and document the ownership; the reported symptom should either go away or become reproducible enough to root-cause the residual case.
- **The two mutable-branch pins (H4 + H5) compound.** If either the philips-labs fork's `pfizer-main` or this repo's `deploy` moves without review, the fleet takes the change silently. Pin both to immutable refs and the change-control story becomes coherent.
- **Cost levers stack.** H1 (min runtime), H2 (sleep 10), M9 (spot vs on-demand) are all in the "instance-hours" bucket. Together they represent the majority of the compute bill. Do H1 and H2 first (pure wins, no reliability tradeoff), then decide M9 based on measured spot-interruption rate.

---

## Open Questions (not answerable from source alone)

- **Terraform state backend encryption / lock status.** Not visible in `versions.tf`. Presumed handled by `pfizer/tf-ga-helper`, but must be verified out-of-band. (See M1.)
- **Actual pool sizes / scaling settings.** Not in the repos reviewed — presumably in a private tfvars file. Impacts the cost sizing above but not the direction of the findings.
- **Whether the `pfizer-main` branch of the philips-labs fork (`pfizer/terraform-aws-github-runner`) is itself branch-protected.** Should be, given H4.
- **Median / p90 job duration.** Needed to size H1 precisely. Can be pulled from `github.rest.actions.listWorkflowRunsForRepo` or from runner CloudWatch logs once H3 is fixed.
- **Which branch the production AMI is built from** — `main` (protected) or `deploy` (unprotected). The `deploy` branch exists on the AMI repo but is unprotected; if the AMI pipeline ever builds from `deploy`, that is a supply-chain concern equivalent to H5.

---

## Quick Wins (this week, minimal effort)

1. **Make the post-job Lambda invoke async and delete the sleep (H2).** One-line change in `post-job-hook.tftpl`. Saves ~$100–270/mo and ~10 s off every job's teardown. Zero reliability risk.
2. **Enable branch protection on the runner-module `deploy` branch (H5).** Two clicks in GitHub settings. Closes an entire supply-chain hole without changing any code.
3. **Pick a CloudWatch-agent owner and document it (H3).** Either delete the pre-bake or make it functional. Publish a one-paragraph README section in the AMI repo naming the authoritative layer. Immediately makes the "missing logs" symptom either fixed or reproducible.

## Longer-Term Recommendations

- **Tune `minimum_running_time_in_minutes`** (H1) — measure job-duration distribution first, then drop from 15 to something between 5 and 10. Likely $1K–4K/month recurring saving. Do this after H2 for cleaner data.
- **Pin the philips-labs module to an immutable ref** (H4) — semver tag or SHA. Set up a scheduled `terraform plan` that catches drift on upstream commits not yet adopted.
- **Formalise Terraform state hygiene** (M1) — either inline the backend block or document its config, encryption, and access control. Add a smoke test in CI.
- **Move the deploy pipeline off self-hosted** (M8) — GitHub-hosted or a small management pool. Removes the circular dependency for disaster recovery.
- **Investigate JIT registration** (L3) — one-line change but requires a rollout window; do it after any pending agent-version cycle.
- **Retire the AMI-baked Docker Hub credentials and the `get.docker.com` install** (M2 + M3) — pin the apt version and drop the login. Reduces both build non-determinism and credential blast-radius.
- **Consolidate branches** (L2) — retire either `2.x` or `deploy` on the runner-module repo. Two divergent long-lived branches of a bootstrap script accumulate technical debt fast.

---

## Cost Summary (order-of-magnitude, per month, at 200K jobs)

| Item | Current | After fix | Delta |
|---|---|---|---|
| Instance-hours if H1 tuned 15 → 5 | ~$17K (on-dem) / ~$6K (spot) | ~$13.6K / ~$4.8K | **–$1.2K to –$3.4K** |
| Wasted sleep-10 across 200K jobs (H2) | ~$95–270 | ~$0 | **–$95 to –$270** |
| CloudWatch Logs ingestion once H3 fixed | ~$0 (broken) | ~$500 | +$500 (but you get logs) |
| Spot vs on-demand at status quo (M9) | see above | policy choice | ~$11K delta either way |

Numbers depend on the actual instance mix, region pricing, and log verbosity — but the *relative* size of the levers is stable.

---

## Sources & References

All findings above are pinned to specific commits so they can be verified. If any of these SHAs change, re-verify before relying on the finding.

### Commit SHAs reviewed

| Repo | Branch | Commit SHA | Protected? |
|---|---|---|---|
| `pfizer/mi-electron-github-runner-ubuntu` | `main` | `d90fc873976ed6adee62d68dc8daedeb667e8c02` | ✅ Yes |
| `pfizer/mi-electron-github-runner-ubuntu` | `deploy` | `8fc1dcd47159cf308a5f1f3c15785e6ae18aa32a` | ❌ No |
| `pfizer/terraform-aws-electron-github-runners-config` | `deploy` | `0e978e2222da70f3da7eb547846433bdf4c7e6ef` | ✅ Yes |
| `pfizer/terraform-aws-electron-github-runners-config` | `2.x` | `7a9945a3df086e6cf0a3582dbc7bdc48f448bd21` | ✅ Yes |
| `pfizer/terraform-aws-electron-github-runner` | `deploy` | `da8660467d353b490d80356dd7149246c6a49893` | ❌ **No — see H5** |
| `pfizer/terraform-aws-electron-github-runner` | `2.x` | `72b7c2d8cf7eca9edeb44e7884704f4ec86c7e7a` | ✅ Yes |

### Files cited (permalinks, immutable via SHA)

**AMI repo — `pfizer/mi-electron-github-runner-ubuntu` @ `main`:**
- [`main.pkr.hcl`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/main.pkr.hcl) (M4)
- [`ansible/tasks/cloudwatch-agent.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/cloudwatch-agent.yaml) (H3)
- [`ansible/tasks/docker-install.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/docker-install.yaml) (M2, M3)
- [`ansible/tasks/actions-runner.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/actions-runner.yaml) (L4)

**Config repo — `pfizer/terraform-aws-electron-github-runners-config` @ `deploy`:**
- [`runners.tf`](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/runners.tf) (H5)
- [`versions.tf`](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/versions.tf) (M1)
- [`security_groups.tf`](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/security_groups.tf) (M5)
- [`.github/workflows/package.yml`](https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/.github/workflows/package.yml) (M8)

**Runner module + bootstrap — `pfizer/terraform-aws-electron-github-runner` @ `deploy`:**
- [`runner.tf`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner.tf) (H4, H5, H6)
- [`variables.tf`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/variables.tf) (M6, M7, M9)
- [`runner-configs/ub-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml) (H1, L3; and H3 for `runner_log_files` block)
- [`data/bolt-ubuntu/post-job-hook.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl) (H2)
- [`data/bolt-ubuntu/user-data.sh`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh) (L1)

**External dependency (mentioned, not reviewed in depth):**
- `pfizer/terraform-aws-github-runner` — the Pfizer fork of philips-labs multi-runner, sourced by the runner module at branch `pfizer-main` (H4). Recommend reviewing this fork's branch-protection status and its divergence from upstream `philips-labs/terraform-aws-github-runner` as a separate follow-up.

### Line-number caveat

GitHub line anchors above (`#Ln-Lm`) were counted against the SHAs listed. Line numbers are stable per SHA; if you view HEAD instead of the pinned SHA, they may drift by a line or two. The permalink form (`/blob/<SHA>/path#Ln`) is immutable — use those if quoting to stakeholders.
