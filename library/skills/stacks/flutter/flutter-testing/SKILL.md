---
name: flutter-testing
description: "Flutter tests: testWidgets, ProviderScope overrides, mocktail, notifier tests, Maestro flows, make test, make analyze, make fix-analyze. Load when writing or fixing a widget, notifier or Maestro test, or verifying Flutter code."
applyTo: 'app/test/**/*.dart,app/maestro_flows/**/*.yaml'
tags: [flutter, mobile, tests]
---

# Flutter App — Testing

## Test directories

- `test/` — unit tests and widget tests. Run with `make test` (`flutter test --exclude-tags chrome --fail-fast`).
- `maestro_flows/` — end-to-end emulator flows. Run with `make test-e2e` or `maestro test --device <device> maestro_flows/`.

**Never** add Patrol tests. **Never** put widget tests inside `maestro_flows/`.

## Widget tests

Use `testWidgets` + `WidgetTester`. Wrap the widget under test in `ProviderScope` with `overrides` to inject test state. For concrete widget-test and provider-override examples, see [`references/examples.md`](references/examples.md).

Always test the three async states for screens that consume async providers: `loading`, `data`, and `error`.

A test never waits on real time. After an event, call `await tester.pump()`. Advance the fake clock with `tester.pump(duration)`. Keep `Future.delayed` and `sleep` out of tests. A Maestro flow waits with `extendedWaitUntil` on a visible element, never a fixed pause.

## Mocking with mocktail

Use `mocktail` for mocking Dart interfaces. **Never** use `mockito`.
For concrete mocktail examples, see [`references/examples.md`](references/examples.md).

## Maestro E2E flows

Maestro flows drive the installed app like a user on an emulator or simulator. Use YAML flows under `app/maestro_flows/`.

Prefer stable visible text, accessibility labels, or test identifiers that map to user-visible controls. Keep flows small and deterministic.
For a concrete Maestro flow example, see [`references/examples.md`](references/examples.md).

## What to test

| Test type | What to cover |
|---|---|
| Widget test | Loading state, data state, error state, key user interactions |
| Notifier unit test | State transitions, optimistic update rollback, error propagation |
| E2E (Maestro) | Full user flows: login → onboarding, profile edit, conversation navigation |

## Commands

```bash
# Unit + widget tests
cd app && make test          # flutter test --exclude-tags chrome --fail-fast

# Static analysis
cd app && make analyze       # flutter analyze

# Analysis + auto-fix + format (use when analyzer reports fixable issues)
cd app && make fix-analyze   # dart fix --apply && dart format . && flutter analyze

# E2E on a connected device/emulator (not required after every change)
cd app && maestro test --device emulator-5554 maestro_flows/
```

## LLM hygiene — run before finishing

After every code change to the Flutter app, run verification before considering the task complete:

```bash
cd app && make analyze && make test
```

- `make analyze` catches type errors, unused imports, missing `await`, deprecated API usage.
- `make test` runs all unit and widget tests with fail-fast.
- **Formatting**: use the repository formatting command; keep generated files up to date.

Fix every failure introduced by your change. If the repo has a known unrelated full-analyze failure, run focused `dart analyze` on the files you touched plus `make test`, then run full `make analyze` and report the unchanged known failure clearly. Do not hide or ignore a new analyzer failure introduced by your change.

## Scope boundaries

This file covers `test/` vs. `maestro_flows/` placement, widget test structure, Riverpod overrides, mocktail, Maestro E2E patterns, what to test, and the analyze/test commands an LLM must run after changes. Examples live in [`references/examples.md`](references/examples.md). It does **not** cover how providers are written — see {{ skill_link("flutter-state") }}.

