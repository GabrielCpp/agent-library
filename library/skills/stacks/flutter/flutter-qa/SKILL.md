---
name: flutter-qa
description: "Flutter local-run smoke QA: emulator, Maestro flow, screenshot proof. Load when smoke-running or QA-ing a mobile story on an emulator after the widget tests pass."
applyTo: 'Only when running local-run / smoke QA for the Flutter app layer'
tags: [flutter, mobile, qa]
---

# Flutter app — local-run / smoke QA

Use this to **run the app on an emulator and reach the screen a story touched** — proof the app boots,
navigates, and the interaction works, not just that widget tests pass. The tool is **Maestro** for the
end-to-end flow.

This is the run/exercise companion to {{ skill_link("flutter-testing") }},
which holds the canonical Maestro + `make` commands — use those, don't duplicate them. Bound every
command with a wall-clock `timeout`.

## Bring the app up

Run the app on a connected emulator/simulator. If the screen needs backend data, bring up the API +
emulators per {{ skill_link("go-qa") }} and the repo's
{{ find_by_tags("runbook") | default("this repo's own developer runbook", true) }}. The plan's **Local run (smoke)** section gives the exact device
+ launch command — prefer it.

## Drive the touched screen

Use a small, deterministic **Maestro** flow that walks the actual user path to the touched screen
(e.g. sign in → reach the feature → exercise it), per
{{ skill_link("flutter-testing") }}:

```bash
cd {{ template.app_path | default("app") }} && timeout 600 maestro test --device emulator-5554 maestro_flows/
```

Prefer stable visible text / accessibility labels for selectors.

**Walk the real user path — never deep-link.** Reach the screen by launching the app and tapping
through the UI (sign in → tab/menu → into the feature), as a user does — not via a deep link / route /
screen arg straight to it (a forced deep link skips the navigation the story must make work and can hit a
state no real user reaches). The sole exception is a story whose explicit subject *is* deep-link entry.
A crash, error, or blank screen on any step is a **fail** — report that step; never tap on to a screen
that works and screenshot *that* as a pass.

Follow the documented journey. The book of the mobile service you are testing documents each journey
as a flow page under `docs/services/<book>/flows/`. Read the matching flow and walk it step by step.
If no flow covers the journey, say so in the QA notes and record the tap path you took, so the book
can gain the flow.

## Success signal — what "it runs" means

- The app **runs on the emulator** with no crash on launch.
- You **sign in, reach the touched screen, and the interaction works** — the feature renders and
  responds, not a blank/error screen or a stuck loading spinner.

A crash, a screen that never loads, or a broken interaction on the touched path is a **defect to FIX
now**. If no emulator/device is available here, report `blocked` naming what was missing — never
`done`.

## Capture proof

Save a **screenshot** of the reached screen (Maestro can capture one) into the story's `qa/` dir.
