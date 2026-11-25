---
name: go-cli-qa
description: "Go CLI local-run smoke QA: dev stack and emulators, go run of a touched command against local fixtures, success signal, saved proof. Load when QA-ing or smoke-running a story that changed a Go CLI command."
applyTo: 'Only when running local-run / smoke QA for the Go CLI layer'
tags: [go, cli, qa]
---

# Go CLI — local-run / smoke QA

Use this to **actually run the `{{ template.go_cli_name | default("appctl") }}` command a story touched**
against the local stack — proof the command builds, parses its flags, and does what the story says, not
just that unit tests pass.

Bound every command with a wall-clock `timeout`
so a hung command fails fast.

## Bring up local dependencies

If the command talks to the DB / emulators, start the same local stack the API uses (see
{{ skill_link("go-qa") }} and the repo's
{{ find_by_tags("runbook") | default("this repo's own developer runbook", true) }}):

{% set api = template.api_path | default("api") -%}
```bash
# Generous timeout: first run pulls Docker images (cold cache takes minutes) — let it
# download rather than failing/escalating; warm runs return in seconds.
timeout 1800 {{ template.dev_stack_up | default("make -C " ~ api ~ " dev-stack-up") }}
# ... run the command (below) ...
timeout 60 {{ template.dev_stack_down | default("make -C " ~ api ~ " dev-stack-down") }}
```

## Run the touched command

Run it the way the story intends, against **local fixtures / the emulator only** — never a real/prod
backend. Use the exact invocation from the plan's **Local run (smoke)** section and
{{ skill_link("go-cli-commands") }}.

```bash
# Example — adjust to the story's command + flags:
( cd {{ template.api_path | default("api") }} && STAGE=local timeout 300 go run ./cmd/{{ template.go_cli_name | default("appctl") }} <command> <flags> )
```

## Success signal — what "it runs" means

- The command **builds and runs** with no panic and exits 0 on the happy path (or the documented
  non-zero for an error case).
- It produces the **observable effect the story describes** — the row written/updated in the local DB,
  the file emitted, the fixture reset — verified out-of-band (e.g. query the local DB).
- Emulator-only safeguards hold: the command refuses to run against a non-local target.

A panic, a build failure, or a no-op where the story expects an effect is a **defect to FIX now**. If
the command can only run against an operator-provided environment, report `blocked` naming what was
missing — never `done`.

## Capture proof

Save the command, its output, and the verified effect (e.g. the changed DB row) beside the story.
