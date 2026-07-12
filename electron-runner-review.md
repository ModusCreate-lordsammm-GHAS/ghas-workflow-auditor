# Pfizer Electron / Bolt Self-Hosted Runner — Best-Practices Review

**Reviewer's note.** This review is based only on what is visible in the three repos below at the commit SHAs recorded in the "Sources & References" section. Anything not visible in source (Terraform state backend config, tfvars, deploy tooling in `pfizer/tf-ga-helper`, GitHub App scope, actual pool sizes) is called out as an open question rather than a finding.

**Scope covers BOTH Linux and Windows runner templates.** `data/bolt-ubuntu/` (Linux) and `data/bolt-windows/` (Windows PowerShell) bootstraps and their corresponding `runner-configs/ub-x86.yaml` and `runner-configs/win-x86.yaml` philips-labs configs. Where a finding applies to only one OS, it is labelled `(Linux only)` or `(Windows only)`; otherwise it applies to both.

## Repos reviewed

| Repo | Authoritative branch reviewed | Also spot-checked | Notes |
|---|---|---|---|
| `pfizer/mi-electron-github-runner-ubuntu` (AMI) | `main` (protected) | `deploy` (unprotected) | Packer + Ansible AMI build |
| `pfizer/terraform-aws-electron-github-runners-config` (orchestration) | `deploy` (protected) | `2.x` (protected) | Terraform root module — no `main` branch exists |
| `pfizer/terraform-aws-electron-github-runner` (runner module + bootstrap) | `deploy` (**unprotected**) | `2.x` (protected) | Wrapped by config repo above; no `main` branch exists |

**Volume assumed:** 14,000 workflow runs/month (current baseline per Pfizer). Cost figures below use that baseline; treat them as order-of-magnitude, based on public c6i.xlarge pricing (~$0.17/hr on-demand, ~$0.06/hr spot). Each cost line also gives a **per-1K-jobs** unit so the numbers scale cleanly if volume changes.

---

## Summary

The setup is **solid overall for Linux**, and **more concerning for Windows**. Ephemerality, autoupdate-off, IMDSv2, encrypted EBS, permissions boundary, and the ECR pull-through cache are all right on the Linux side. The **Windows template is not configured as ephemeral** (see H0), which changes the security and cost story materially for that OS. Aside from that, the setup is clearly built by people who know what they're doing.

The concerns cluster in four areas, ordered by real impact at 14K jobs/month:

1. **Windows runners are non-ephemeral** — the biggest single deviation from the "one job, one instance" model. Reused runners inherit state, credentials, and caches from previous jobs. Combined with UAC-disabled and `ghrunner` being a full local Administrator, the Windows security posture is materially weaker than Linux (see H0, H7). Impact is by scale × exposure, not by dollars.
2. **Logging** — the AMI installs the CloudWatch agent but the Ubuntu Ansible task never configures or starts it; the philips-labs module wires it at runtime via SSM. Windows explicitly enables the agent at runtime (`amazon-cloudwatch-agent-ctl.ps1 -a fetch-config`), Linux does not. Two layers touch log shipping on Linux with no single owner — the most likely explanation for reports of missing logs.
3. **Supply chain / change control** — the runner module is pinned to a mutable branch (`pfizer-main`), the config repo pins the runner module by mutable branch (`deploy`), and that `deploy` branch is **not protected**. Two unreviewed mutable refs sit between commit and production.
4. **Cost efficiency** — `minimum_running_time_in_minutes: 15` (Linux) / **30** (Windows), the `sleep 10` in every post-job hook, and the spot/on-demand default are meaningful at any scale but modest in absolute dollars at 14K/mo (roughly **$100–500/month** across the three levers). If volume grows toward the 200K/mo target sometimes discussed, these become **$1K–7K/mo** — worth acting on now while the fix is cheap.

Nothing here is a fire. The Windows-ephemeral and logging items are the ones worth doing this quarter regardless of volume.

---

## What's Done Well

- **Ephemeral, single-use runners (Linux only).** `enable_ephemeral_runners: true` in `runner-configs/ub-x86.yaml`; deregistration is handled by the philips-labs module on ephemeral exit — no ghost-runner accumulation observed in the Linux code path. **Windows is not configured this way — see H0.**
- **Runner autoupdate disabled on both OSes** (`disable_runner_autoupdate: true`). Correct for a controlled environment where agent version is pinned at image-build time.
- **Non-root service account on Linux.** `runner_run_as: ghrunner`. The `ghrunner` user has passwordless sudo and is in the docker group, but that is a deliberate design decision for ephemeral hosts and is documented in the Ansible comments. **On Windows, `ghrunner` is also added to the local `Administrators` group — see H7.**
- **IMDSv2 required on both OSes** with `http_put_response_hop_limit: 1` — SSRF-hardened, protects the instance role from being stolen via a workflow request.
- **EBS boot volume encrypted** in both the Packer build (16 GB) and the runtime launch template (Linux 40 GB gp3, Windows 100 GB gp3, both 750 MB/s throughput).
- **Session Manager for SSH** on builders (no port 22 open, no key management).
- **IAM policies mostly least-privilege** — `ec2:CreateTags` is conditioned on tag; `ssm:GetParameter` is enumerated to specific parameter ARNs; ECR pull-through is scoped to the two cache repos.
- **Role permissions boundary applied.** Defence-in-depth against role privilege escalation.
- **Corporate root CAs** installed in the AMI. TLS-inspection proxies work out of the box.
- **CrowdStrike Falcon + Nessus agents** present in the AMI — endpoint protection meets enterprise policy.
- **ECR pull-through cache for Docker Hub and ghcr.io (Linux)**, plus a docker wrapper in `user-data.sh` that rewrites `docker pull ghcr.io/foo` to the ECR URL. Reduces external egress, avoids Docker Hub rate limits, keeps images inside the VPC.
- **Toolcache pre-populated** with Python 3.9–3.14. Fast boot-to-ready for common toolchains.
- **KMS customer-managed keys** for parameter encryption; instances get an explicit `kms:Decrypt` policy scoped to the right key alias.
- **Runner registration uses SSM Parameter Store**, not launch-template plaintext, for both the GitHub App credentials and the enterprise PAT.
- **Multi-region** (us-east-1 + eu-west-1) with separated proxy tiers managed by ASG.
- **CloudWatch agent explicitly enabled on Windows at runtime** via `amazon-cloudwatch-agent-ctl.ps1 -a fetch-config` in `data/bolt-windows/runner_setup.tftpl`. Good — but see H3 for the Linux gap.
- **`bolt-windows/` has no drift between `deploy` and `2.x`** (identical SHA). Positive contrast with the Linux bootstrap drift (see L2).
- **Windows JIT SSM parameter is deleted after use** in `runner_setup.tftpl` (`aws ssm delete-parameter --name "$token_path/$InstanceId"`). Good hygiene — no orphaned config tokens in SSM.

---

## Findings & Recommendations

### HIGH

#### H0 — Windows runners are NOT configured as ephemeral (Windows only)
- **What:** The Windows philips-labs config does not set `enable_ephemeral_runners`. It also has no `ACTIONS_RUNNER_HOOK_JOB_COMPLETED` wiring in the visible source. This means Windows runners **stay registered and reuse the same instance across multiple jobs** (default philips-labs behaviour when `enable_ephemeral_runners` is absent or false).
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`runner-configs/win-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml) (no `enable_ephemeral_runners` key, compare with [`ub-x86.yaml` L8](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L8) which has it).
- **Risk:** Reused Windows runners inherit state from previous jobs — cached credentials in `%USERPROFILE%\.docker\config.json`, cached NuGet/npm/pip artefacts, `C:\actions-runner\_work\` contents, environment variables leaked into the runner service, temp files, Chocolatey state. A malicious or negligent job can leave secrets or workspace files for the next unrelated tenant to pick up. Combined with H7 (Windows `ghrunner` = local Administrator) and the "no cleanup between jobs" story, this is the biggest single deviation from the "ephemeral runner" model the rest of the design assumes.
- **Recommendation:** The direct fix is to set `enable_ephemeral_runners: true` in `win-x86.yaml`, matching Linux. This requires validating that the Windows AMI can register cleanly in ephemeral mode (start-up time may be 3–5 min so scale-up latency needs tuning). If ephemeral is not feasible short-term, the mitigation stack is: (a) wire a `runner_hook_job_completed` PowerShell script that wipes `C:\actions-runner\_work\`, `%TEMP%`, `%USERPROFILE%\.docker`, `%APPDATA%\npm-cache`, and equivalents; (b) enforce max-lifetime recycle (kill runners after N jobs or T minutes); (c) treat Windows runners as security-tier lower and label them explicitly so callers know.
- **Priority:** HIGH.
- **Cost impact:** None direct — the fix may slightly increase cost (more instances started) but is offset by lower `minimum_running_time_in_minutes` (see H1).

#### H1 — `minimum_running_time_in_minutes: 15` (Linux) / **30** (Windows) on runners
- **What:** philips-labs config sets a minimum billed lifetime per runner instance.
- **Where:**
  - Linux: `terraform-aws-electron-github-runner` @ `deploy` — [`runner-configs/ub-x86.yaml` L36](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L36) (`minimum_running_time_in_minutes: 15`)
  - Windows: [`runner-configs/win-x86.yaml` L28](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml#L28) (`minimum_running_time_in_minutes: 30`)
- **Risk:** Every Linux runner is billed for ≥15 min, Windows for ≥30 min, even if the job took 45 seconds. This is the largest per-job cost multiplier in the stack — dollar magnitude is modest at 14K/mo but scales linearly with volume. Windows is 2× the Linux impact per job. Note also: Windows runners are non-ephemeral (H0), so this parameter drives idle-runner life rather than per-job billing — same cost effect either way, but the reasoning changes.
- **Recommendation:** Instrument the actual job-duration distribution per OS (median, p90). If most Linux jobs finish in <5 min, drop Linux to 5 (the philips-labs floor). If Windows jobs are shorter than 30 min mean, drop Windows to something between 10 and 15. The value exists to smooth scale-down thrash; it should be tuned to the observed distribution, not left at the module default.
- **Priority:** HIGH.
- **Cost impact (at 14K jobs/month, Linux only illustration):** if Linux median is 4 min and 60% of Linux jobs are <15 min, dropping 15 → 5 saves ~10 min × ~8,400 jobs = **~1,400 instance-hours/month**. c6i.xlarge spot ($0.06) ≈ **~$85/mo**; on-demand ≈ **~$240/mo**. **Per-1K jobs: ~$6 spot / ~$17 on-demand.** Windows dropping 30 → 15 could roughly double this on the Windows share. Highest-$-value finding in the review, and scales linearly — at 200K/mo it would be $1.2K–3.4K/mo.

#### H2 — Blocking `sleep 10` + synchronous Lambda invoke on every job teardown
- **What:** `post-job-hook.tftpl` runs `sleep 10` then a synchronous `aws lambda invoke` to the proxy-log-searcher on every job completion.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`data/bolt-ubuntu/post-job-hook.tftpl` around line 73 (`sleep 10`) and line 87 (`aws lambda invoke`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl#L73-L92)
- **Risk:** 14K × 10s = 140,000 CPU-seconds ≈ **~39 CPU-hours/month** wasted in pure sleep, plus average Lambda cold-start on top. Small in dollars but user-visible — every Linux job takes ~10 s longer to release its runner than it needs to. Also directly extends billed instance-hours (the 15-min minimum masks it for short jobs but pushes borderline jobs into the next billing increment).
- **Recommendation:** Make the Lambda call async (`--invocation-type Event` — fire and forget). Delete the sleep, or, if it exists to allow logs to flush before termination, replace with a specific flush (`systemctl stop amazon-cloudwatch-agent`).
- **Priority:** HIGH.
- **Cost impact (at 14K jobs/month):** ~**$2–7/month** in wasted instance-hours (spot vs on-demand). **Per-1K jobs: ~$0.17 spot / ~$0.47 on-demand.** Cost is trivial; the reason to fix it is p95 latency and code hygiene (a one-line change that removes a sleep in the critical path). At 200K/mo the cost becomes $30–100/mo.

#### H3 — CloudWatch agent installed but not configured or enabled in the AMI (Linux only)
- **What:** The Ubuntu Ansible task downloads and dpkg-installs `amazon-cloudwatch-agent.deb`, then deletes the .deb. There is no config file drop, no `fetch-config` from SSM, no `systemctl enable/start`. **Windows does this correctly** — `data/bolt-windows/runner_setup.tftpl` explicitly runs `amazon-cloudwatch-agent-ctl.ps1 -a fetch-config -m ec2 -s -c "ssm:.../cloudwatch_agent_config_runner"` at boot. The Linux boot has no equivalent step.
- **Where:** `mi-electron-github-runner-ubuntu` @ `main` — [`ansible/tasks/cloudwatch-agent.yaml`](https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/cloudwatch-agent.yaml). Contrast with [`data/bolt-windows/runner_setup.tftpl` (the `Enabling CloudWatch Agent` block)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/runner_setup.tftpl).
- **Note:** The philips-labs module DOES wire `runner_log_files` (syslog, user-data.log, `_diag/*`) via SSM at boot time — see [`runner-configs/ub-x86.yaml` L38–L52](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml#L38-L52). But nothing in the Linux user-data script actually starts the agent with that config.
- **Risk:** Ambiguous ownership of log shipping on Linux. If SSM ever fails or the instance starts a job before SSM has settled, logs are lost silently for that instance. **This is the most likely explanation for the "logs disappear" reports** — the AMI leaves the agent installed-but-idle, so any diagnostic looking at the image assumes it's doing the shipping when nothing actually is. The fact that Windows explicitly enables the agent and Linux doesn't strongly suggests the Linux config was simply forgotten.
- **Recommendation:** Mirror what Windows does. Either (a) add an equivalent step to the Ubuntu user-data script (fetch config from SSM, enable, start), or (b) drop a functional `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json` in the image via the Ansible task and `systemctl enable amazon-cloudwatch-agent` so logs ship from t=0. Then document, in the AMI README, which layer owns log shipping.
- **Priority:** HIGH.
- **Cost impact (at 14K jobs/month):** CW Logs ingestion at 14K × ~5 MB/job ≈ **~70 GB/month × $0.50/GB = ~$35/mo ingestion** once fully functional (plus storage). **Per-1K jobs: ~$2.50 ingestion.** Apply metric filters to drop noisy syslog lines. At 200K/mo this is ~$500/mo.

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

#### H7 — Windows security cluster: `ghrunner` is local Administrator, UAC disabled, local-account password in runner service config (Windows only)
- **What:** Three related issues in `data/bolt-windows/runner_setup.tftpl` that compound on non-ephemeral Windows runners (H0):
  1. `ghrunner` is added to the local `Administrators` group (not just `docker-users`).
  2. UAC is disabled: `Set-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System -Name ConsentPromptBehaviorAdmin -Value 0 -Force` — with an unresolved `TODO investigate if this is needed or if its overkill` comment referencing philips-labs issue #1505.
  3. Local-account password is fetched from SSM (`/runners/windows-user-password`) and passed to `.\config.cmd --windowslogonaccount ghrunner --windowslogonpassword $password`. That password becomes part of the runner Windows service configuration on a persistent (non-ephemeral) box.
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`data/bolt-windows/runner_setup.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/runner_setup.tftpl) (Administrators around L95, UAC-disable around L102, `configCmd` around L118)
- **Risk:** On a reused runner, any workflow that executes as `ghrunner` (i.e. every workflow) inherits full local Administrator, no UAC prompts, and can potentially recover the service-account password from the Windows service configuration or LSA secrets. Combined with H0 (no wipe between jobs), a malicious or over-privileged job can plant persistence (scheduled task, service, DLL sideload) that survives into every subsequent job on that host. This is the highest-severity item on Windows.
- **Recommendation (in order of effort):** (a) Fix H0 first — ephemeral runners collapse most of the blast radius here. (b) If Windows must stay non-ephemeral: rotate the shared `ghrunner` password on every runner-service-config event (unique per instance from SSM), audit LSA-secret access, add a per-job cleanup hook that resets known persistence points (Scheduled Tasks, Services, Startup, autorun registry keys) and clears `%USERPROFILE%\.docker\config.json` and other credential caches. (c) Resolve the UAC-disabled TODO — either document why it must stay off (and mitigate) or turn it back on and fix whatever needed it off. (d) Investigate whether `runner_run_as` on Windows can be a lower-privileged user with docker-users but not Administrators (may require refactoring how docker-desktop-for-Windows is installed).
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
- **Risk:** At 14K jobs/month, even a 1 % spot-interruption rate = **~140 failed jobs/month for infra reasons**, not code reasons. Developers see flaky CI and lose trust in the platform. If volume grows, this scales linearly.
- **Recommendation:** Mixed strategy — spot for jobs known to be idempotent/retriable (opt-in via a label like `spot-ok`), on-demand for release/prod-critical jobs. Instrument actual spot-interruption rate before deciding the split.
- **Priority:** MEDIUM.
- **Cost impact (at 14K jobs/month):** Spot vs on-demand at c6i.xlarge = $0.06 vs $0.17. On 14K jobs × ~30 min mean billed time = 7,000 instance-hours/mo → **~$420/mo spot vs ~$1,190/mo on-demand** (delta ~$770/mo). **Per-1K jobs: ~$30 spot / ~$85 on-demand delta.** A 70/30 hybrid is a reasonable starting point. At 200K/mo this delta becomes ~$11K/mo.

---

### LOW

#### L1 — `set +u` disabled immediately before `${start_runner}` template expansion
- **Where:** `terraform-aws-electron-github-runner` @ `deploy` — [`data/bolt-ubuntu/user-data.sh` (last lines — search for `set +u`)](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh)
- **Risk:** Bash strict mode disabled at the most critical bootstrap step. If the templated block references an unset variable, it silently continues with an empty value instead of failing loudly. Historically the cause of "runner boots but never registers" incidents.
- **Recommendation:** Remove the `set +u`; ensure the templated block sets defaults for every variable it uses (`: "${RUNNER_NAME:=}"`).
- **Priority:** LOW.

#### L2 — Drift between `deploy` and `2.x` branches of the Linux bootstrap (Linux only)
- **Where:** `terraform-aws-electron-github-runner` — [`data/bolt-ubuntu/user-data.sh` on `deploy`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh) is 12,782 bytes; [same file on `2.x`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/72b7c2d8cf7eca9edeb44e7884704f4ec86c7e7a/data/bolt-ubuntu/user-data.sh) is 7,909 bytes. Only `deploy` has the ECR-pull-through docker wrapper. **Positive:** `data/bolt-windows/` has the same SHA on both branches — Windows has no drift.
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

- **Linux and Windows are not the same product.** Linux is ephemeral, config-driven, and mostly follows the "one job, one instance" story the design assumes. Windows is non-ephemeral, admin-privileged, and reuses runners across jobs. Findings, priorities, and cost math should be tracked per OS. If Windows job volume is a small fraction of total (as often the case), H0/H7 are less broadly impactful but still worth fixing because when Windows *is* used it tends to be for higher-trust workflows (release signing, .NET builds).
- **The logging bug is almost certainly the Ubuntu AMI/module ownership split (H3).** Windows explicitly enables the CloudWatch agent at runtime; Linux does not. The Windows implementation is the model to copy.
- **The two mutable-branch pins (H4 + H5) compound.** If either the philips-labs fork's `pfizer-main` or this repo's `deploy` moves without review, the fleet takes the change silently. Pin both to immutable refs and the change-control story becomes coherent.
- **Cost levers stack, but are modest at current scale.** H1 (min runtime, Linux 15 + Windows 30), H2 (sleep 10, Linux only), M9 (spot vs on-demand) are all in the "instance-hours" bucket. At 14K jobs/month the combined saving is on the order of $100–500/month — worth doing for code hygiene and to remove drag before volume grows, but not the headline reason to fix these repos. Do H1 and H2 first (pure wins, no reliability tradeoff), then decide M9 based on measured spot-interruption rate.
- **What if volume grows.** The brief mentioned both 14K/mo (current) and 200K/mo (referenced as a target). All cost figures scale linearly. Pinning H1/H2 fixes now is cheap; deferring them until volume grows means paying the tax at growth-time when everyone is busy.

---

## Open Questions (not answerable from source alone)

- **Terraform state backend encryption / lock status.** Not visible in `versions.tf`. Presumed handled by `pfizer/tf-ga-helper`, but must be verified out-of-band. (See M1.)
- **Actual pool sizes / scaling settings.** Not in the repos reviewed — presumably in a private tfvars file. Impacts the cost sizing above but not the direction of the findings.
- **Whether the `pfizer-main` branch of the philips-labs fork (`pfizer/terraform-aws-github-runner`) is itself branch-protected.** Should be, given H4.
- **Median / p90 job duration.** Needed to size H1 precisely. Can be pulled from `github.rest.actions.listWorkflowRunsForRepo` or from runner CloudWatch logs once H3 is fixed.
- **Which branch the production AMI is built from** — `main` (protected) or `deploy` (unprotected). The `deploy` branch exists on the AMI repo but is unprotected; if the AMI pipeline ever builds from `deploy`, that is a supply-chain concern equivalent to H5.
- **Whether a separate Windows AMI repo exists** — the Windows `runner_setup.tftpl` mentions `mi-electron-github-runner-windows` as the source of the pre-configured `ghrunner` user. That repo was **not** reviewed here; H7 and H0 should be re-verified against it before acting.
- **What Windows share of the 14K/mo job volume actually is** — sizes the impact of H0/H1 (Windows leg)/H7. If Windows is <5% of jobs, prioritise Linux fixes first; if it's larger, H0/H7 move up.
- **Whether the 14K/mo baseline or a higher target (200K/mo was also referenced in the brief) is the correct planning horizon** — findings and priorities don't change, but the dollar values in the cost table do (14× difference).

---

## Quick Wins (this week, minimal effort)

1. **Set `enable_ephemeral_runners: true` on Windows (H0).** One-line change in `runner-configs/win-x86.yaml`, matches Linux. Needs a smoke-test of Windows scale-up, but collapses most of H7's blast radius in the process. Highest-security-value quick win.
2. **Make the post-job Lambda invoke async and delete the sleep (H2).** One-line change in `post-job-hook.tftpl`. Saves ~$100–270/mo and ~10 s off every Linux job's teardown. Zero reliability risk.
3. **Enable branch protection on the runner-module `deploy` branch (H5).** Two clicks in GitHub settings. Closes an entire supply-chain hole without changing any code.
4. **Add the Linux CloudWatch-agent enable step (H3).** Copy the pattern from `data/bolt-windows/runner_setup.tftpl` into the Ubuntu user-data. One block of code. Fixes the missing-logs symptom.

## Longer-Term Recommendations

- **Consolidate the Windows security posture** (H0 + H7) — make Windows ephemeral, remove `ghrunner` from Administrators, re-enable UAC or document why not, and add a per-job cleanup hook. Treat Windows and Linux as one runner story again rather than two.
- **Tune `minimum_running_time_in_minutes`** (H1) — measure job-duration distribution per OS first, then drop Linux 15 → 5 and Windows 30 → 15 as data permits. Modest saving at 14K/mo (~$85–240/mo Linux); scales to $1K–4K/mo at 200K/mo. Do after H2 for cleaner data.
- **Pin the philips-labs module to an immutable ref** (H4) — semver tag or SHA. Set up a scheduled `terraform plan` that catches drift on upstream commits not yet adopted.
- **Formalise Terraform state hygiene** (M1) — either inline the backend block or document its config, encryption, and access control. Add a smoke test in CI.
- **Move the deploy pipeline off self-hosted** (M8) — GitHub-hosted or a small management pool. Removes the circular dependency for disaster recovery.
- **Investigate JIT registration** (L3) — one-line change but requires a rollout window; do it after any pending agent-version cycle.
- **Retire the AMI-baked Docker Hub credentials and the `get.docker.com` install** (M2 + M3) — pin the apt version and drop the login. Reduces both build non-determinism and credential blast-radius.
- **Consolidate Linux bootstrap branches** (L2) — retire either `2.x` or `deploy` on the runner-module repo. Two divergent long-lived branches accumulate technical debt fast.

---

## Cost Summary (order-of-magnitude, per month)

Numbers are illustrative — actual figures depend on instance mix, region pricing, spot availability, and job-duration distribution. The **per-1K-jobs** column is the honest unit: multiply by your true monthly job count.

| Item | At 14K/mo (current) | At 200K/mo (aspirational) | Per-1K jobs |
|---|---|---|---|
| **H1** — save from tuning `min_running_time` 15 → 5 (Linux only) | ~$85–240/mo | ~$1.2K–3.4K/mo | ~$6–17 saved |
| **H2** — save from removing `sleep 10` in post-job hook | ~$2–7/mo | ~$30–100/mo | ~$0.17–0.47 saved |
| **H3** — CW Logs ingestion once logging is fixed | +~$35/mo | +~$500/mo | +~$2.50 ingested |
| **M9** — spot-vs-on-demand delta on the current fleet | ~$770/mo (spot saves this) | ~$11K/mo | ~$55 delta |

**Bottom line at 14K jobs/month:** the cost findings are worth doing (they are easy wins and remove technical debt), but the absolute dollar impact is modest — roughly **$100–500/mo** across the three main levers. The dominant reasons to act are **security (H0/H7), logging (H3), and change-control (H4/H5)** — not the cost figures alone.

**If volume grows** toward the 200K/mo figure that appeared in the brief, cost findings become materially larger ($1.5K–4K/mo range) — worth pinning them in the backlog now while the fixes are cheap.

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
- [`runner-configs/ub-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml) (H1 Linux, L3; H3 `runner_log_files` block)
- [`runner-configs/win-x86.yaml`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml) (H0, H1 Windows leg)
- [`data/bolt-ubuntu/post-job-hook.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl) (H2)
- [`data/bolt-ubuntu/user-data.sh`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/user-data.sh) (L1)
- [`data/bolt-windows/user-data.ps1`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/user-data.ps1) (Windows entry point, Chocolatey install)
- [`data/bolt-windows/proxy_setup.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/proxy_setup.tftpl) (Windows proxy configuration)
- [`data/bolt-windows/runner_setup.tftpl`](https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/runner_setup.tftpl) (H3 contrast, H7)

**External dependency (mentioned, not reviewed in depth):**
- `pfizer/terraform-aws-github-runner` — the Pfizer fork of philips-labs multi-runner, sourced by the runner module at branch `pfizer-main` (H4). Recommend reviewing this fork's branch-protection status and its divergence from upstream `philips-labs/terraform-aws-github-runner` as a separate follow-up.

### Line-number caveat

GitHub line anchors above (`#Ln-Lm`) were counted against the SHAs listed. Line numbers are stable per SHA; if you view HEAD instead of the pinned SHA, they may drift by a line or two. The permalink form (`/blob/<SHA>/path#Ln`) is immutable — use those if quoting to stakeholders.
