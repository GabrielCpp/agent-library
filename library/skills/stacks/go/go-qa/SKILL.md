---
name: go-qa
description: "Go API local-run smoke QA: dev stack, server with STAGE=local, curl with an emulator token, success signal, saved proof. Load when QA-ing or smoke-running a story that changed a Go backend endpoint."
applyTo: 'Only when running local-run / smoke QA for the Go API layer'
tags: [go, backend, qa]
---

# Go API — local-run / smoke QA

Use this to **run the backend locally and exercise the endpoint a story touched** — the proof that the
code actually boots and serves, not just that unit tests pass. The tool is **`curl`** (or any HTTP
client) against the locally-running server.

Bound every command with a wall-clock `timeout`
so a hung boot or request fails fast instead of stalling QA.

## Bring the API up locally

Use the project's documented local-stack runbook — do **not** invent commands. Typical shape:

{% set api = template.api_path | default("api") -%}
```bash
# Local dependencies (DB + auth/storage emulators), if the project has a dev stack.
# Generous timeout: the FIRST run pulls Docker images, which on a cold cache legitimately
# takes minutes — let the download finish rather than treating it as a failure/operator block.
# Warm runs return in seconds.
timeout 1800 {{ template.dev_stack_up | default("make -C " ~ api ~ " dev-stack-up") }}

# The API server (reads the local config, STAGE=local):
( cd {{ template.api_path | default("api") }} && STAGE=local timeout 1800 go run ./cmd/server & )

# Teardown when done:
timeout 60 {{ template.dev_stack_down | default("make -C " ~ api ~ " dev-stack-down") }}
```

The exact targets/flags live in the repo's {{ find_by_tags("runbook") | default("this repo's own developer runbook", true) }} and the
`{{ template.api_path | default("api") }}/Makefile`; the boot command also appears in the plan's
**Local run (smoke)** section. Prefer those over the template above.

## Exercise the touched path

`curl` the endpoint(s) the story added or changed, with a real (emulator/seeded) auth token where the
route requires it. Walk the actual request the story enables, the way the client will.

```bash
# Example — adjust path/method/auth to the story:
timeout 30 curl -sS -i http://localhost:8080/<touched-endpoint>
```

## Success signal — what "it runs" means

- The server **boots with no panic** (watch the boot log).
- The touched endpoint returns a **genuine status** — its real 2xx/4xx for the input, **not**
  connection-refused (server never came up) and **not** a boot-time 500 (it crashed on first request).
- For a CLI-style/background path, the operation completes against local fixtures and produces the
  effect the story describes.

A panic, a connection-refused, or an unexpected 500 on the touched path is a **defect to FIX now** —
not something to discover in QA or hand off. If the local stack genuinely cannot be brought up here
(no Docker, an operator-only dependency), report `blocked` naming exactly what was missing — never
`done`.

## Capture proof

Save a short artifact beside the story (its `qa/` or spec dir): the server boot log line plus the
endpoint's response (status + body). Do not assert "it runs" without evidence.
