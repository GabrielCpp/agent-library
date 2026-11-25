---
name: pulumi-qa
description: "Pulumi infrastructure smoke QA: pulumi preview of an infra change, success signal (no unintended replace or delete on live infra), saved proof. Load when QA-ing an infrastructure story, or judging whether a preview output is safe."
applyTo: 'Only when running local-run / smoke QA for the Pulumi infrastructure layer'
tags: [pulumi, infra, qa]
---

# Pulumi infrastructure — local-run / smoke QA

Infrastructure has no app to boot; the smoke check is a **`pulumi preview`** that proves the change
resolves the way the story intends. **Do not run `pulumi up` locally** — applies go through the Cloud
Build CI (see {{ skill_link("pulumi") }} and
{{ skill_link("pulumi-ci-docker") }}); a local
apply leaves a lock + pending operations that poison the next run.

Bound every command with a wall-clock `timeout`.

## Preview the change

Use the project's state backend + (empty) passphrase preamble, then preview the target stack:

```bash
export PULUMI_CONFIG_PASSPHRASE=""
timeout 120 pulumi login gs://<project>-pulumi-state
cd {{ template.pulumi_path | default("pulumi") }} && timeout 600 pulumi preview --refresh --stack <stack>
```

The exact bucket/stack come from `{{ template.pulumi_path | default("pulumi") }}/Pulumi.<stack>.yaml`
and the plan's **Local run (smoke)** section — prefer those.

## Success signal — what "it runs" means

- `pulumi preview` **resolves cleanly** and the summary shows the **intended** operations:
  `create`/`update`/`unchanged` for what the story changes.
- It does **not** show an unintended **`replace`/`delete`** on live infra (VPC connectors, egress IPs,
  populated secrets, data stores). `~ urn …` alias renames are benign; a `replace`/`delete` of live
  state is a **defect to FIX now** (usually a changed logical name → add an alias).

If preview needs credentials only an operator can provide, report `blocked` naming what was missing —
never `done`.

## Capture proof

Save the `pulumi preview` summary (the resource op counts and any replace/delete lines) beside the
story.
