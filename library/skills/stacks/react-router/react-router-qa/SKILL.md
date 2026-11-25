---
name: react-router-qa
description: "Local smoke QA for the React Router web app: dev server against the emulator, Playwright through the UI, screenshot and video proof, `ostler vet`. Load when smoke-running or QA-ing a web story to prove the page renders the feature."
applyTo: 'Only when running local-run / smoke QA for the React Router web layer'
tags: [react-router, web, qa]
---

# React Router web — local-run / smoke QA

Use this to **run the web app locally and drive the touched route in a real browser** — proof the page
actually renders the feature, not just that the build/typecheck pass. The tool is **Playwright**
(headless, or via the Playwright MCP server for a live walkthrough).

Judge from **rendered pixels in a browser running the branch's code**, never from `.tsx` source. Bound
every command with a wall-clock `timeout`
so a hung `networkidle`/login fails fast.

## Bring the web app up locally

Use the project's documented local-stack runbook — do **not** invent commands. Typical shape:

```bash
# Dev server (proxies the API and points auth at the local emulator):
( cd {{ template.react_router_path | default("advisor-dashboard") }} && timeout 1800 npm run dev & )
```

If the route needs real data, also bring up the API + emulators per
{{ skill_link("go-qa") }} and the repo's
{{ find_by_tags("runbook") | default("this repo's own developer runbook", true) }}. The exact commands also appear in the plan's **Local run
(smoke)** section — prefer those.

## Drive the touched route

Two distinct surfaces — keep them separate:

1. **Mocked Playwright spec (no backend).** Run with just the dev server; use `page.route()` to stub
   auth and `/api/*` so you can assert the touched route renders the feature (including states a seeded
   user can't reach). Sign in (fill email/password, submit, `waitForURL` off the sign-in route), then
   assert the feature's elements render.
2. **Live walkthrough (real/deployed stack) via the Playwright MCP server.** When QA must exercise the
   real backend or a deployed URL, drive a real browser through the MCP tools (navigate / click / fill /
   screenshot) against the stack you brought up — do **not** bake a real backend into a committed test.

### Reach pages by driving the UI — NOT by deep-linking a URL

For the live walkthrough, **use `browser_navigate` exactly once: to the app entry point** (sign-in page
or app root). Reach every other page **by clicking through the real UI** the way a user does — sign in →
open the picker / parent list → select the record → click into the feature. Do **not** `browser_navigate`
to a deep link with an ID or a route segment past the entry point (`/projects/<id>/...`, `/.../stages`).

Follow the documented journey. The book of the web service you are testing documents each journey
as a flow page under `docs/services/<book>/flows/`. Read the matching flow and walk it step by step.
If no flow covers the journey, say so in the QA notes and record the click path you took, so the
book can gain the flow.

A repo may also keep a **committed real-stack regression spec** per journey: a Playwright spec that
drives the **live** backend and auth (no `/api` mocking) and **fails on any 5xx or error page** during
the walk. It is distinct from a mocked story spec, which stubs `/api/*` and so cannot catch a backend
500. The plan's local-run section or the repo's runbook names where these specs live and how to run
them. When you add or change a journey in such a repo, add or update its spec so the regression suite
covers it. How to *write* those specs — locators, waits, the cold-start-tolerant first
assertion, the mocked-vs-live `page.route()` split — is
{{ skill_link("react-router-playwright") }};
this skill is only the run workflow.

Why: a typed deep link skips the very navigation the story must make work, and can land in a state no
real user reaches — exactly how a `/projects/<id>/stages` deep link 500s while the same project _reached
through the picker_ is fine. The only navigation that proves the journey is the journey. **Sole
exception:** a story whose explicit, written subject _is_ direct-URL entry (e.g. "a shared `/projects/:id`
link must restore the page") — then deep-linking IS the test; say so in the notes.

### An error on ANY step is a `failed` — never screenshot past it

If a step produces a **500 / error page / error overlay / error toast / blank feature**, that step has
**failed**. Stop there and report it as the defect — the failing URL, the status, and the console/network
error. **Never** continue past the error, navigate to something that does render, and screenshot _that_
as if the run passed: a green screenshot of a page you weren't testing is a fake pass, not evidence. The
proof screenshot must be the **target feature reached through the journey** — if you couldn't reach it,
the result is `failed`.

**A server error on the page under test fails the story even if the widget you came to check rendered.**
Your story's ACs are a _minimum_, not the _only_ thing that can fail. A page that returns a 500 (or shows
an error body, a broken data region, a console/network 5xx) is a **broken page** — you cannot pass ANY AC
on it, no matter how narrow. The classic miss: checking a navbar/header variant on `/projects/<id>/stages`,
seeing the chrome render fine on top of a 500 page body, noting the 500 as an aside, and passing because
"the navbar was my target." That is a **`failed`** — the navbar rendering on a broken page does not make
the page work. If the page the AC lives on errors, the result is `failed`; report the 500, do not file it
as a neutral "note."

## Success signal — what "it runs" means

- The dev server serves the touched route and it **renders the feature in a real browser** — not a
  blank screen, an error overlay, a perpetual loading indicator, or a redirect/fallback away from the
  page.
- The interaction the story adds works (form submits, list loads, navigation lands).

A blank/error page, a stuck loading state, or a route that bounces to a fallback is a **defect to FIX
now**. Reserve `blocked` for what only an operator can provide (a real deployed build, a live payment
path) — never for an app bug on the path.

## Capture proof

Save a **screenshot** of the rendered route (Playwright/MCP) into the story's `qa/` dir. Do not assert
"it renders" without a screenshot.

Write the screenshot to an **absolute** path resolved to that `qa/` directory — build it with
`path.resolve(...)` / `fileURLToPath(import.meta.url)` in a script, or pass the MCP
`browser_take_screenshot` `filename` as an absolute path. A bare filename or cwd-relative path is
resolved against the working directory (the repo root) and dumps screenshots there instead — not
acceptable.

### Enhanced evidence: real video + real DevTools (opt-in, not default)

Only when the user explicitly asks for evidence more convincing than screenshots/text (e.g. "I want to
see the dev tools", "can I get a video") — or the story is a security-sensitive / adversarial-audit
re-QA. Not the default for every run; standard `browser_take_screenshot` + console/network text capture
remains the default.

- **Video without real DevTools chrome**: `page.context().tracing.start({ screenshots: true, snapshots:
true })` before the interaction, `tracing.stop({ path: 'ac1-trace.zip' })` after. Gives a scrubbable
  trace (`npx playwright show-trace ac1-trace.zip`) with real Console/Network tabs; screenshot those
  tabs, or extract the embedded screencast JPEGs and stitch them into an mp4 with `ffmpeg -f concat`
  (per-frame `duration` = real delta between the frames' embedded epoch-ms timestamps).
- **Video with DevTools visibly open in the frame itself**: launch a real, separate Chrome
  (`open -na "Google Chrome" --args --remote-debugging-port=9222 --auto-open-devtools-for-tabs
--user-data-dir=/tmp/<scratch>-profile --window-size=1500,950 <url>`), drive it with
  `playwright-core`'s `chromium.connectOverCDP('http://127.0.0.1:9222')` (no browser download needed).
  `--auto-open-devtools-for-tabs` does **not** land on the Network tab by default — force it: fetch
  `http://127.0.0.1:<port>/json/list`, find the `devtools://` target, open a raw WebSocket to its
  `webSocketDebuggerUrl` (Node 22+ has a global `WebSocket`), and `Runtime.evaluate` an expression that
  recurses into every element's `shadowRoot` (the tab strip lives in shadow DOM — a plain
  `querySelector` finds nothing) to find the `[role="tab"]` labeled `Network` and click it, **before**
  starting the capture loop — the panel selection then persists for the whole session. Also **start the
  capture loop before login**, not just before the interaction under test — launch to the app's base
  URL, switch the panel, start capturing, _then_ drive the real sign-in, navigation, and interaction all
  in one recording; a clip that starts already-logged-in is far less convincing.
  **Never full-screen/full-display capture** (`screencapture -x` / `ffmpeg -f avfoundation` against the
  whole screen) to record it — full-screen capture depends on window z-order/focus at the exact moment
  and can leak an unrelated frontmost window (this happened for real: an unrelated Slack DM ended up in
  a recording). Capture **only** that Chrome window by its CGWindowID instead: enumerate windows with
  `pyobjc-framework-Quartz`'s `CGWindowListCopyWindowInfo` (filter `kCGWindowOwnerName == "Google
Chrome"`), then loop `screencapture -x -o -l <windowNumber> -t png frame_$(epoch-ms).png` for the
  interaction's duration and assemble with `ffmpeg -f concat` as above — this is compositor window
  capture and cannot contain any other window's pixels regardless of focus. Requires macOS Screen
  Recording permission granted to the actual app hosting the terminal (check with
  `ps -o pid,ppid,comm -p $PPID`), which requires a full quit+relaunch of that app after granting.
  **Always `view_image` a sample frame before trusting the recording as evidence.** **Clean up
  afterward and verify it** — close the temp Chrome window/profile, remove scratch npm/venv dirs, and
  delete every intermediate frame-staging directory, including any staged directly under the story's
  `qa/` evidence dir; `ls -la qa/` at the end and confirm only the final named artifacts remain (no
  leftover hidden dot-directories) — this was missed more than once before being caught, so treat the
  final listing check as mandatory, not optional.

## Deterministic visual-fidelity check (`ostler vet`)

A screenshot proves _you_ looked; it doesn't prove the page still renders the elements you're
claiming a pass on if someone re-runs the story tomorrow. Close that gap with `ostler vet` — a
deterministic CLI that scans the live DOM over the same CDP session your browser tooling already
has open and diffs it against a manifest you write.

- While you verify an AC in the browser (per the live-walkthrough flow above), note the
  selector, role, and bounding box of the story-relevant element(s) you just confirmed. Accumulate
  these into a bare JSON list at `<qa_dir>/vet-manifest-<state>.json`, one file per distinct UI
  state you check (e.g. `vet-manifest-default.json`, `vet-manifest-empty.json`):
  ```json
  [
    {
      "selector": "table tbody tr:has-text('gabriel-test')",
      "role": "row",
      "bbox": { "x": 214, "y": 768, "width": 852, "height": 44 },
      "visible": true
    }
  ]
  ```
  Scope this to what _this story_ touched — not a full-page inventory. A screenshot of the same
  state is required (see Capture proof above); `ostler vet` diffs against it.
- Run it against the open CDP port:
  ```bash
  ostler vet <screenshot.png> --manifest <qa_dir>/vet-manifest-<state>.json \
    --cdp-url <cdp-port> --slug <story-slug> --state <state> --json --write
  ```
- **A nonzero exit code does not mean the command failed.** `ostler vet` exits `1` whenever its
  scan finds _any_ disagreement — including elements the manifest never mentioned. Read the JSON
  report; the only bucket that means "the story broke something" is `missing` (a manifested
  element that did not render). `unexpected` and `unlabeled` are expected noise on a real page —
  see {{ skill_link("react-router-a11y") }}
  for why role-less native elements (a plain `<table>`/`<tr>`) land in `unlabeled` even when
  nothing is wrong.
- Record the outcome per state in `qa-evidence.json`'s `visual_fidelity` array (state, manifest
  path, report path). This is a claim like the rest of that file — the deterministic QA-evidence
  gate re-checks it and downgrades the pass only when a report's `missingCount > 0`.
