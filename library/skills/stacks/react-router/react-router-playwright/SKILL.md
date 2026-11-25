---
name: react-router-playwright
description: "Playwright specs for the React Router web app: auto-waiting expect, getByRole, StrictMode double fetch, mocked `*-qa.spec.ts` vs live `*.journey.spec.ts`. Load when writing, reviewing or debugging a spec under `e2e/`, or a flaky spec"
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/e2e/**/*.ts'
tags: [react-router, web, tests]
---

# React Router web — writing Playwright specs

This skill is the Playwright mechanics for the generic E2E contract in
{{ skill_link("testing-e2e") }} — read that for
*why* each rule exists; this file is *how* it's done in this stack. It is the writing-side
companion to {{ skill_link("react-router-qa") }}:
that skill is the **run** workflow (boot the stack, walk the journey, capture evidence); this one
is what makes the `*.journey.spec.ts` / `*-qa.spec.ts` specs that workflow drives resilient enough
to trust.

## Waits: auto-retrying `expect(locator)` only

Playwright's `expect(locator)` assertions (`toBeVisible`, `toHaveText`, `toHaveCount`, …)
auto-retry until the condition holds or the timeout expires — they *are* the wait mechanism.
`page.waitForTimeout()` and any hand-rolled sleep are **banned** in committed specs, for the
reasons in e2e-testing's wait-strategy section: a sleep is simultaneously too short and too long,
and it hides the race instead of naming it.

```ts
// wrong: guesses a duration
await page.waitForTimeout(5000);
await expect(page.getByRole("status")).toBeVisible();

// right: states the condition; Playwright polls it
await expect(page.getByRole("status")).toBeVisible();

// right, when a longer deadline is deliberate (see cold start below):
// first navigation after dev-server boot — StrictMode double-fetch + on-demand compile
await expect(page.getByRole("status")).toBeVisible({ timeout: 60_000 });
```

`waitForURL` after a submit/sign-in and `waitForLoadState` at entry are fine — they state
conditions too. An extended `timeout:` is allowed only with a comment naming the slow thing.

## Locators: `getByRole` with a partial-name regex

Prefer `getByRole` with `{ name: /stable-token/ }` over `getByText` with a full literal string —
this is e2e-testing's locator rule expressed in Playwright's API, and the roles/names it queries
are the ones {{ skill_link("react-router-a11y") }}
requires the components to carry. A `getByRole` that finds nothing is frequently reporting a real
accessibility gap in the component — check that before rewriting the locator as CSS.

When the copy is server-rendered, localized, or interpolated — a full French sentence, a value
baked into an aria-label — do **not** put the whole string in the locator's `name`. Match a fixed
fragment, and if the story requires the exact wording, assert it separately after presence is
established:

```ts
// wrong: one assertion couples "is it there yet?" to a 90-char localized sentence
await expect(
  page.getByRole("status", { name: "La traduction française est obsolète depuis la modification du 3 mars" })
).toBeVisible();

// right: presence by role + stable fragment; exact copy as its own step if the AC demands it
const staleBadge = page.getByRole("status", { name: /obsolète/ });
await expect(staleBadge).toBeVisible();
await expect(staleBadge).toHaveText(/depuis la modification/);
```

## The StrictMode cold-start double-fetch, concretely

React 18 `StrictMode` (on in this app's dev builds) **mounts every component twice** on first
render: mount → unmount → remount. Any `useEffect`-driven fetch — including the page-content
loading hooks this app uses — therefore fires, is **aborted**, and fires again on a scenario's
first navigation. Against a freshly-booted dev server this stacks with on-demand route compilation,
so the first assertion of the first scenario can face tens of seconds of legitimate emptiness —
and a 30s default timeout expires while the failure screenshot shows the finished page.

You'll recognize it exactly as e2e-testing's cold-start section describes: an aborted+reissued
request pair for the same resource in the network log, the expected element already present in the
failure's aria snapshot, and a failure exclusive to first navigation. The spec shape that survives
it:

```ts
// first assertion after the scenario's entry navigation:
// role + fragment (never the full sentence), extended deadline for
// cold dev-server boot + StrictMode abort/refetch on first mount
await expect(page.getByRole("status", { name: /obsolète/ })).toBeVisible({ timeout: 60_000 });
```

Extend only that entry assertion — once the first paint has settled, subsequent assertions in the
scenario keep the default timeout, so a genuinely broken interaction still fails fast. Do not
solve this with `test.retry()` or a global timeout raise: both blunt every real failure to
absorb one named race.

## Mocked suite vs. live suite

{{ skill_link("react-router-qa") }} defines
the two surfaces and when each runs — don't re-litigate that split here. A screen's state matrix
belongs in {{ skill_link("react-router-testing") }}, and the mocked suite holds what jsdom cannot
see. The Playwright mechanics for each:

- **`*-qa.spec.ts` (mocked story suite)** — dev server only, no backend. Stub auth and every
  `/api/*` call with `page.route()` **before** the navigation that triggers the fetch, and fulfill
  with fixture JSON:

  ```ts
  await page.route("**/api/pages/*", (route) =>
    route.fulfill({ json: pageContentFixture({ translationStale: true }) })
  );
  await page.goto("/sign-in"); // then drive the UI to the route under test
  ```

  Because StrictMode's abort/refetch (above) means a route handler can be hit more than once per
  mount, handlers must be **stateless and idempotent** — never `route.fulfill` a different payload
  on "the second call", which races the double-invoke. To exercise a state *change* (stale →
  republished), drive it through the UI action that causes it and swap the handler with
  `page.unroute()` + a new `page.route()` at that step boundary.
- **`*.journey.spec.ts` (live regression suite)** — real API + auth emulator, **no `page.route()`
  mocking of `/api/*` at all**; the point of the suite is catching the backend 5xx the mocked
  suite cannot. Navigate once to the journey's entry point and reach everything else by driving
  the UI — deep-linking past the entry is react-router-qa's rule and applies verbatim to the
  committed spec.

## Review checklist for a new or changed spec

- [ ] No `page.waitForTimeout()` / sleeps; every wait is an auto-retrying assertion.
- [ ] No visible-assertion carries a full literal sentence — role + stable fragment, exact copy
      asserted separately only where the AC is about the wording.
- [ ] The scenario's first post-navigation assertion has the cold-start-tolerant shape (role
      first, extended deadline with a comment); later assertions keep the default.
- [ ] One `page.goto()` to the journey's entry point; every other page reached through the UI
      (react-router-qa's deep-linking rule).
- [ ] One scenario = one isolated state: own fixtures, own sign-in, `page.route()` handlers
      stateless; nothing depends on another scenario having run.
- [ ] Mocked and live concerns not mixed: `page.route("**/api/**")` appears in `*-qa.spec.ts`
      only, never in `*.journey.spec.ts`.
- [ ] Failure artifacts on (`trace`/`screenshot` in the Playwright config) so a red run is
      diagnosable without a re-run.
