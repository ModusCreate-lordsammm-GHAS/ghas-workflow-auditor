# Electron Runner — Logging & Configuration Feedback

**Scope:** Technical feedback on internal GitHub Actions runners built from custom images (Electron). Focus is the current logging gap and configuration bugs on the custom images — not a full platform audit.

**Repos reviewed (pinned commits — every snippet below is quoted from these SHAs):**

| Repo | Ref | Commit |
|---|---|---|
| `pfizer/mi-electron-github-runner-ubuntu` | `main` | `d90fc873976ed6adee62d68dc8daedeb667e8c02` |
| `pfizer/terraform-aws-electron-github-runner` | `2.x` (`deploy`) | `da8660467d353b490d80356dd7149246c6a49893` |
| `pfizer/terraform-aws-electron-github-runners-config` | `deploy` | `0e978e2222da70f3da7eb547846433bdf4c7e6ef` |

Both **Ubuntu** and **Windows** bootstrap paths were reviewed.

---

## Summary

The Electron stack is well-structured overall — the Ubuntu path is genuinely ephemeral, IMDSv2 is enforced, EBS volumes are encrypted with a customer KMS key, runner auto-update is disabled (correct for a pinned-image environment), and the design cleanly wraps the philips-labs terraform-aws-github-runner module rather than reinventing it.

Against that solid baseline there are **five concrete issues** on the custom-image / bootstrap surface. One of them is the root cause of the current logging problem, and importantly the Windows path already implements the correct pattern for it — so the fix has an in-repo reference.

---

## Positive Findings

Worth calling out because these are non-trivial to get right and the team has already gotten them right:

- **Runner auto-update is disabled on both OS images.** `runner-configs/ub-x86.yaml` and `win-x86.yaml` both set `disable_runner_autoupdate: true`. This is correct for a controlled-image environment where the runner agent version should be part of the image build, not a moving target.
- **Linux runners are truly ephemeral.** `runner-configs/ub-x86.yaml` sets `enable_ephemeral_runners: true`, so each Linux instance handles a single job and is destroyed. This eliminates the entire class of "residue from previous job" risks on Linux.
- **IMDSv2 is enforced.** Both runner configs set `http_tokens: required` on `runner_metadata_options`. Removes IMDSv1 credential-theft vectors.
- **EBS volumes are encrypted.** Both configs set `encrypted: true` on the root volume with a customer KMS key (`kms_key_arn = "${kms_key_id}"`).
- **CloudWatch agent is correctly configured on Windows.** `data/bolt-windows/runner_setup.tftpl` calls `amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c "ssm:$ssm_config_path/cloudwatch_agent_config_runner"` at boot. Logs ship from Windows runners as intended. This is the reference pattern for the Linux fix below.
- **Post-job hook has proper structured logging and metadata handling.** `data/bolt-ubuntu/post-job-hook.tftpl` uses IMDSv2 with token retrieval, error-checks each metadata call, and writes timestamped logs to `github-runner-hooks.log` and syslog.
- **The design wraps philips-labs terraform-aws-github-runner rather than forking it.** This means upstream security fixes flow through cleanly.

---

## Findings

### Finding 1 — CloudWatch agent installed on Ubuntu but never started (logging root cause)

**Severity:** High. This is the most likely single explanation for the missing/lost logs on Linux runners.

**Where:** `pfizer/mi-electron-github-runner-ubuntu`, file `ansible/tasks/cloudwatch-agent.yaml`.

**Snippet — the entire Ansible task file:**

```yaml
---
- name: Download amazon-cloudwatch-agent.deb binary
  ansible.builtin.get_url:
    url: https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
    dest: /tmp/amazon-cloudwatch-agent.deb

- name: Install amazon-cloudwatch-agent.deb package
  become: true
  ansible.builtin.apt:
    deb: /tmp/amazon-cloudwatch-agent.deb

- name: Remove temporary amazon-cloudwatch-agent.deb
  ansible.builtin.file:
    path: /tmp/amazon-cloudwatch-agent.deb
    state: absent
```

That is the whole file. The agent gets downloaded, installed, and the installer removed. There is:

- no CloudWatch agent config file written to `/opt/aws/amazon-cloudwatch-agent/etc/`
- no `systemctl enable amazon-cloudwatch-agent`
- no `amazon-cloudwatch-agent-ctl -a fetch-config` call
- no SSM parameter reference for a Linux CW-agent config

The agent is on disk and idle.

**Contrast — the Windows bootstrap does it correctly.** `pfizer/terraform-aws-electron-github-runner`, file `data/bolt-windows/runner_setup.tftpl`:

```powershell
& 'C:\Program Files\Amazon\AmazonCloudWatchAgent\amazon-cloudwatch-agent-ctl.ps1' `
    -a fetch-config -m ec2 -s `
    -c "ssm:$ssm_config_path/cloudwatch_agent_config_runner"
```

The `$ssm_config_path` is discovered from an instance tag (`ghr:ssm_config_path`) and the CW-agent JSON config lives at the SSM parameter.

**Additional evidence — the runner config *declares* log groups that never get populated on Linux.** `pfizer/terraform-aws-electron-github-runner`, `runner-configs/ub-x86.yaml`:

```yaml
runner_log_files:
  - log_group_name: syslog
    prefix_log_group: true
    file_path: /var/log/syslog
    log_stream_name: "{instance_id}"
  - log_group_name: user_data
    prefix_log_group: true
    file_path: /var/log/user-data.log
    log_stream_name: "{instance_id}/user_data"
  - log_group_name: runner
    prefix_log_group: true
    file_path: /opt/actions-runner/_diag/Runner_**.log
    log_stream_name: "{instance_id}/runner"
```

These paths are what the team *expects* to be shipped. They will not be shipped as long as the agent that ships them is never started.

**Why this matters:** ephemeral instances are destroyed after a single job. Any logs on local disk when the instance terminates are gone — OS logs, runner agent `_diag/*.log`, troubleshooting output. Across the Linux job volume this leaves the team blind when investigating runner-side failures.

**Recommendation:**

1. In `data/bolt-ubuntu/user-data.sh`, after SSM is available and before the runner is started, add the equivalent of the Windows call:

   ```bash
   /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
       -a fetch-config -m ec2 -s \
       -c "ssm:${ssm_config_path}/cloudwatch_agent_config_runner"
   ```

   `ssm_config_path` is already available via the `ghr:ssm_config_path` instance tag (same source Windows uses).

2. Create a Linux CloudWatch agent config JSON in SSM at the matching parameter path. Use the existing Windows CW-agent config as the reference and adapt paths for Linux (`/var/log/syslog`, `/var/log/user-data.log`, `/opt/actions-runner/_diag/Runner_**.log`).

Either step alone is insufficient; both are required.

**Open question:** the philips-labs terraform-aws-github-runner module can, in some configurations, inject a systemd unit for the CW agent via SSM. Worth confirming whether that path is active here — if it is, the fix may reduce to correcting the SSM parameter rather than editing `user-data.sh`. Either way, current behaviour on Linux is: agent installed, agent never runs.

---

### Finding 2 — Windows runners are not configured as ephemeral

**Severity:** High. This is a configuration difference between the two custom images with material security and cleanliness implications.

**Where:** `pfizer/terraform-aws-electron-github-runner`, file `runner-configs/win-x86.yaml`.

**Snippet — Windows config (relevant lines):**

```yaml
runner_config:
  # ...
  disable_runner_autoupdate: true
  runner_os: windows
  runner_architecture: x64
  runner_name_prefix: bolt-windows_
  # ...
  delay_webhook_event: 5
  runner_registration_level: org
  enable_runner_binaries_syncer: false
  enable_ssm_on_runners: true
  runner_run_as: ghrunner
  create_service_linked_role_spot: true
  runner_boot_time_in_minutes: 10
  minimum_running_time_in_minutes: 30
```

Note what is *not* present: there is no `enable_ephemeral_runners: true`.

**Contrast — Linux does set it.** `runner-configs/ub-x86.yaml`:

```yaml
runner_config:
  # ...
  disable_runner_autoupdate: true
  enable_ephemeral_runners: true
  enable_jit_config: false
  runner_os: linux
```

**Why this matters:** on Linux, each instance picks up one job and is destroyed — no state leaks between jobs, no persistent attack surface. On Windows, absent `enable_ephemeral_runners`, the module's default is to keep instances alive to service multiple jobs. So Linux runs on a "one instance = one job" model while Windows does not. Combined with the fact that the Windows service runs as a local administrator, this is a materially different threat model between the two OSs.

**Recommendation:** decide explicitly whether Windows should be ephemeral. If yes, add `enable_ephemeral_runners: true` to `win-x86.yaml` and validate that job durations fit within the philips-labs single-use lifecycle. If no, document *why* Windows deliberately differs from Linux so future maintainers do not assume it's an oversight.

---

### Finding 3 — Runner module pinned to a mutable branch, not a version tag

**Severity:** High. This is the deployment-config bug that lets any commit to a shared branch reach production without a version bump.

**Where:** `pfizer/terraform-aws-electron-github-runners-config`, file `runners.tf`.

**Snippet — the module source line:**

```hcl
module "bolt" {
  source = "git::ssh://git@github.com/pfizer/terraform-aws-electron-github-runner?ref=deploy"

  additional_iam_policies = length(local.bolt_ssh_lambda_arns_list) > 0 ? {
    bolt_ssh_lambda_invoke = data.aws_iam_policy_document.bolt_ssh_lambda_invoke[0].json
  } : {}
  # ...
}
```

`?ref=deploy` is a branch, not a tag. Whatever the tip of that branch is at `terraform apply` time is what gets deployed.

**Why this matters:** every `terraform apply` implicitly picks up whatever landed on the runner-module's `deploy` branch since the last apply — even if the config repo itself has not changed. There is no version pin, so there is no atomic mapping from "state of the config repo at commit X" to "actual infrastructure deployed." A change to the runner module cannot be rolled back by reverting the config repo; the config repo never referenced a specific version to begin with.

**Recommendation:** pin the module to a git tag or commit SHA:

```hcl
source = "git::ssh://git@github.com/pfizer/terraform-aws-electron-github-runner?ref=v2.4.1"
```

or

```hcl
source = "git::ssh://git@github.com/pfizer/terraform-aws-electron-github-runner?ref=da86604..."
```

Version bumps then become intentional PRs against the config repo. This also enables proper diff review — the config-repo PR shows exactly which module version is being adopted, and reviewers can inspect the tag range's changes.

---

### Finding 4 — `deploy` branch on the runner module is unprotected

**Severity:** Medium. Related to Finding 3 but distinct — this is the *governance* half of the deployment-config gap.

**Where:** `pfizer/terraform-aws-electron-github-runner`, branch `deploy` (equivalent to `2.x` at the pinned commit).

**Evidence:** the runner-module `deploy` branch has no branch-protection rule — no required reviewers, no required status checks, direct pushes permitted. This is in contrast to the config repo's own `deploy` branch, which *is* protected.

There is no code snippet for this because the absence-of-configuration is the finding. It can be verified in GitHub Settings → Branches on `terraform-aws-electron-github-runner`.

**Why this matters:** Finding 3 says the config repo pins to a mutable ref. Finding 4 says that mutable ref itself has no gate. Together this means any authorised committer can push a single commit on the runner module's `deploy` branch and — because the config repo tracks that branch — reach production on the next `terraform apply`, with no PR, no review, no CI check, no approval trail.

**Recommendation:** enable branch protection on `terraform-aws-electron-github-runner`'s `deploy` branch. Match the settings already in place on the config repo's `deploy` branch: require pull request, require at least one review, require status checks to pass.

Fixing Finding 3 alone (pin to a version tag) reduces the blast radius; fixing Finding 4 alone (protect the branch) closes the accidental-push path. Doing both is inexpensive and appropriate.

---

### Finding 5 — Hard-coded `sleep 10` in Linux post-job hook

**Severity:** Medium. Configuration bug on the custom-image bootstrap path with a small but real runtime cost.

**Where:** `pfizer/terraform-aws-electron-github-runner`, file `data/bolt-ubuntu/post-job-hook.tftpl`.

**Snippet — the relevant block:**

```bash
# ── Proxy blocked-domain summary ─────────────────────────────────────────────
sleep 10
LAMBDA_ARN="${proxy_log_searcher_lambda_arn}"


RUNNER_IP=$(hostname -I | awk '{print $1}')
END_MS=$(date +%s%3N)

if [ -n "$START_EPOCH" ]; then
    START_MS=$(( START_EPOCH * 1000 ))
else
    START_MS=$(( END_MS - 1800000 ))   # fall back to last 30 min
fi

log "Invoking proxy log searcher lambda — ip: $RUNNER_IP"

LAMBDA_PAYLOAD=$(printf '{"runner_ip":"%s","start_time":%d,"end_time":%d}' "$RUNNER_IP" "$START_MS" "$END_MS")

aws lambda invoke \
    --region "$AWS_REGION" \
    --function-name "$LAMBDA_ARN" \
    --payload "$LAMBDA_PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /tmp/lambda-response.json 2>/tmp/lambda-invoke.err || true
```

The `sleep 10` sits between "job finished" and "invoke Lambda to query proxy logs." It is a hedge — waiting for the proxy's request logs to reach whatever backing store the Lambda queries — before running the search.

**Why this matters:** every Linux job pays a 10-second teardown tax. It is a magic number: not tied to observed ingestion latency, not adaptive, and not commented. It also blocks the instance from terminating for those 10 seconds, so it is 10 seconds of paid compute per job with no work being done.

**Why this is subtle:** the Lambda's response *is* consumed synchronously — the script parses it with `jq` to write blocked domains to the workflow's job summary. So the naive fix ("make the Lambda call async") would break the feature. The right question is whether the 10s hedge is actually necessary, and if so, whether a bounded retry would be better than a fixed sleep.

**Recommendation (in order of preference):**

1. Measure the actual proxy-log ingestion latency. If it is under a second or two in practice, reduce or remove the sleep.
2. If some hedge is genuinely required, replace the fixed `sleep 10` with a bounded retry: invoke the Lambda, and if it reports "no data yet" retry with backoff up to a cap. This preserves correctness while removing the tax on the common case.
3. If neither of the above is feasible, at minimum add a comment explaining *why* 10 seconds, and move the value into a Terraform variable so it can be tuned without editing template code.

---

## Also worth mentioning (shorter, on the same surface)

Not required to resolve the logging/setup task, but on the same image/bootstrap surface and cheap to fix while the team is in the code:

- **Ubuntu `user-data.sh` disables strict-unset checking (`set +u`) immediately before starting the runner.** If the runner expects an env var and it's unset, the failure will be silent rather than loud. Low severity; one-line fix.
- **Runner agent version pulled from `releases/latest`** in `ansible/tasks/actions-runner.yaml` (Ubuntu AMI). Two image builds a week apart may bake different runner-agent versions. Pin the version explicitly.
- **Windows service runs as local `Administrator` with UAC disabled**, with an unresolved `TODO` in `data/bolt-windows/runner_setup.tftpl` about tightening it. Combined with Finding 2 (Windows non-ephemeral), this is a decision the team should make explicitly rather than let drift.

---

## What I did not review

Boundaries stated up-front so nothing is implied:

- **Consumer workflows across Pfizer's 23 GitHub orgs.** Findings above are grounded in the platform-side source only; they do not depend on how any given team consumes the runners.
- **`pfizer/tf-ga-helper`** (Terraform backend / state configuration).
- **`mi-electron-github-runner-windows`** (Windows AMI source). Only the *bootstrap* side of the Windows path was inspected via the runner-module repo.
- **Live telemetry.** No access to CloudWatch metrics, cost reports, or job-duration distributions. The Finding 5 impact estimate is a rough extrapolation from monthly job volume, not measured.

---

## References

- Ubuntu AMI @ `d90fc87`: https://github.com/pfizer/mi-electron-github-runner-ubuntu/tree/d90fc873976ed6adee62d68dc8daedeb667e8c02
  - CloudWatch task file: https://github.com/pfizer/mi-electron-github-runner-ubuntu/blob/d90fc873976ed6adee62d68dc8daedeb667e8c02/ansible/tasks/cloudwatch-agent.yaml
- Runner module @ `da86604` (`2.x`/`deploy`): https://github.com/pfizer/terraform-aws-electron-github-runner/tree/da8660467d353b490d80356dd7149246c6a49893
  - Windows CW-agent start: https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-windows/runner_setup.tftpl
  - Ubuntu post-job hook: https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/data/bolt-ubuntu/post-job-hook.tftpl
  - Linux runner config: https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/ub-x86.yaml
  - Windows runner config: https://github.com/pfizer/terraform-aws-electron-github-runner/blob/da8660467d353b490d80356dd7149246c6a49893/runner-configs/win-x86.yaml
- Runners config @ `0e978e2` (`deploy`): https://github.com/pfizer/terraform-aws-electron-github-runners-config/tree/0e978e2222da70f3da7eb547846433bdf4c7e6ef
  - Module source pin: https://github.com/pfizer/terraform-aws-electron-github-runners-config/blob/0e978e2222da70f3da7eb547846433bdf4c7e6ef/runners.tf
