---
name: flutter
description: "Flutter app work under app/: sibling skill hierarchy, make generate, make test, make analyze. Load when starting any Flutter task, before the sibling that matches the files you touch."
applyTo: 'app/**'
tags: [flutter, mobile, standards, entrypoint]
---

# Flutter App — Flutter Root

This is the root Flutter instruction. Load this first for any work under `app/`, then load the next-level instruction files that match the files you will touch.

## Next-Level Instructions

- Architecture and screen/view-model contract: {{ skill_link("flutter-architecture") }}
- Riverpod state management: {{ skill_link("flutter-state") }}
- API client and network layer: {{ skill_link("flutter-api") }}
- Data and Freezed syntax: {{ skill_link("flutter-data") }}
- Generated API types vs local models: {{ skill_link("flutter-models") }}
- Forms and validation: {{ skill_link("flutter-forms") }}
- Navigation and routes: {{ skill_link("flutter-navigation") }}
- Theme and design tokens: {{ skill_link("flutter-theme") }}
- UI components and design system: {{ skill_link("flutter-ui") }}
- Testing: {{ skill_link("flutter-testing") }}

## Level-3 Examples


## Core Rules

- Follow the dash-only skill hierarchy from the central agents library. Do not introduce dotted skill IDs; generated skill names must remain valid kebab-case.
- `flutter.md` defines the Flutter hierarchy and conflict policy. `flutter-architecture.md` is canonical for screens, screen view models, Freezed `*ViewState`, Riverpod annotations, private provider getters, `Screen<VM, State>`, `AsyncScreen<VM, State>`, code generation, and view-model dependency graph updates.
- When a rule appears to conflict, the more specific skill file wins within its domain. If a prompt conflicts with an instruction file, update the prompt or follow the instruction file.
- Run `cd app && make generate` after Riverpod or Freezed changes.
- Run focused analysis on touched files, `cd app && make test`, and full `cd app && make analyze`; report known unrelated full-analyze failures instead of hiding them.

