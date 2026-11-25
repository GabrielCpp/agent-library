---
name: plan-qa
description: Plan manual QA
---

## Before you start

Read the repo's QA instructions **before generating anything**: the QA instruction file or skill
its CLAUDE.md names. They hold the exact command patterns, field-name conventions, fixed
test-context IDs and the pitfalls learned from real debugging sessions.

Use the repo's own QA helper tools when they directly support the story under test: discovery
helpers that look up test data, and evidence collectors that tail published events or stream
records.

When a step depends on one device's or one session's state, capture that device's own identifier
from the connected device and query by it. Never query by a shared test user or infer the state
from a wide scan.

---

Create a **MANUAL QA PLAN Markdown file** for the story, against the **DEV environment only**.

Your output must look like the repo's existing QA manuals: concise title, fixed context, numbered
steps, optional verification and cleanup.

## Primary objective

Generate a single Markdown document, saved as `<story-folder>/manual-qa.md`.

Write the plan content into that file in the workspace.
Do NOT return the full plan content in chat.

The document must be strict, minimal, practical, human readable.

## Inputs policy

- Do not use placeholders unless absolutely required.
- If any placeholders are required, include exactly one section at top: **Inputs Needed**.
- Keep Inputs Needed short and explicit.

## Plan requirements

- Do NOT use Markdown tables anywhere in the runbook.
- Do NOT include a shell script block.
- Do NOT search logs to verify published events. Use the repo's event and stream collectors
  instead, and include a prerequisite step that starts them in separate terminals before
  triggering.
- Keep commands step-scoped and copy-paste runnable.
- Include explicit per-step evidence files and verdict rules.
- Include clear execution order that continues after non-critical failures.
- Include explicit cleanup and manifest expectations.

## Evidence requirements

Every piece of evidence must be written to disk under `<story-folder>/qa/`.

- Define `QA_DIR="<story-folder>/qa"` near the top and `mkdir -p` all subdirectories
  before the first step that writes evidence.
- Organize evidence by acceptance criterion: one subdirectory per AC
  (e.g. `qa/ac1-<slug>/`, `qa/ac2-<slug>/`).
- Each step's "Save evidence" block must redirect output into `$QA_DIR/acN-<slug>/<file>`.
- The final section must be an **Evidence manifest** listing every file path and what it proves,
  grouped by AC.

## Style requirements

- Keep commands concrete and copy-paste runnable.
- Prefer a discovery helper for setup when it makes the runbook shorter, but keep the explicit
  command for a lifecycle step that needs its own evidence.
- Include collector setup and query steps when published events or stream records are part of
  the acceptance criteria.
- Use numbered steps (`## 1) ...`, `## 2) ...`) similar to the existing QA manuals.
- Keep language operational, not explanatory.
- Avoid extra features not needed for manual QA in DEV.

## Delivery requirements

- Do not print the runbook body in chat.
- In chat, return only a short confirmation including the saved file path.
