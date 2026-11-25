---
name: flutter-architecture
description: "Flutter app architecture: lib/ structure (core, features), Freezed ViewState, Screen<VM, State>, AsyncScreen. Load when creating a feature or screen, writing a screen view model, or deciding if code belongs in core or a feature."
applyTo: 'app/lib/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter App — Architecture & Conventions

This is the canonical source for Flutter app architecture, screens, screen view models, and feature boundaries. `flutter.md` defines the overall Flutter hierarchy and conflict policy; within this architecture domain, follow this file and update any drifting prompt or instruction guidance.

## Folder structure

```
lib/
├── core/              # Cross-feature: services, config, shared widgets
│   ├── config/        # app_router.dart, settings.dart, theme/
│   ├── services/      # network (Dio), auth (Firebase), api providers, logging
│   └── widgets/       # skeleton, main_shell, shared UI primitives
├── features/          # One directory per bounded context
│   └── <feature>/
│       ├── providers/ # Riverpod notifiers, computed providers, state classes
│       ├── screens/   # Full-page widgets
│       └── widgets/   # Feature-local reusable sub-components
└── generated/         # Never edit manually — always regenerated
    ├── api/           # openapi-generator Dart/Dio client
    └── l10n/          # ARB codegen output
```

## Feature boundaries

- `lib/features/<feature>/` is self-contained. Feature view models may depend on providers from other features only through an explicitly documented, acyclic provider graph. Screens and widgets must not reach across feature boundaries to watch another feature's providers directly.
- `lib/core/` is for code that is used by **two or more** features. Do not put feature-specific code in `core/`.
- `lib/generated/` is never edited by hand. Regenerate with `make generate` (Riverpod, Freezed) or `make generate-api` (Dart API client).

**Never** import a feature's `screens/` or `widgets/` from another feature.
**Never** put feature-specific business logic in `lib/core/`.

## Adding a new feature

1. Create `lib/features/<feature>/providers/`, `screens/`, and `widgets/` directories.
2. Add route constants and `GoRoute` entries in `lib/core/config/app_router.dart`.
3. If the feature needs a new API endpoint, update `api/pkg/api/openapi.yaml` first and regenerate both backend and app clients.
4. Add a `widgets.dart` barrel file in the feature's `widgets/` directory that exports all public widgets.

## Screens And View Models

Every screen has exactly one screen view model. The screen view model is the only Riverpod provider the screen watches, and it owns the screen's state shape, loading/error/data mapping, actions, side-effect commands, and coordination with any other providers.

Every screen view model uses Riverpod code generation with lowercase `@riverpod`, and it must remain auto-dispose. Do not declare screen view models with manual provider constructors, and do not set `keepAlive: true` on screen view models.

Every view model state type must be a Freezed view model state. Declare `@freezed abstract class <ScreenName>ViewState with _$<ScreenName>ViewState`, include the matching `part '<file>.freezed.dart';`, and regenerate. Plain Dart classes are not allowed for view model state, even for simple states with only a few fields.

Every provider dependency inside a screen view model must be exposed through a named private getter on that view model. Do not inline `ref.read(...)`, `ref.watch(...)`, `ref.listen(...)`, or `ref.invalidate(...)` in `build()` or action methods. Use getters such as `AuthNotifier get _authNotifier => ref.read(authNotifierProvider.notifier);` and `AsyncValue<User?> get _authState => ref.watch(authNotifierProvider);`, then build state and actions from those getters.

Screens extend the shared `Screen<VM, State>` base class with their single view model and its state type as template parameters. The base screen watches that view model, receives its typed state, and calls the screen's render method with that state. Rendering must be based solely on the view model state and callbacks exposed by the view model.

The `viewModelProvider` getter is only a provider handle used by the shared base class to call Riverpod. Type it as `ProviderListenable<State>` for synchronous screens and `ProviderListenable<AsyncValue<State>>` for `AsyncScreen<VM, State>`. Do not type this getter as `Object` or use `dynamic` casts; the provider handle and rendered screen state must both remain strongly typed.

For async view models whose `build()` returns `Future<State>`, screens extend `AsyncScreen<VM, State>`. Flutter widget `build()` methods are never `async`; the async work belongs in the `@riverpod` view model, and `AsyncScreen` unwraps Riverpod's `AsyncValue<State>` into typed `buildData`, `buildLoading`, and `buildError` hooks.

### Canonical example

`lib/features/profile/providers/profile_view_model.dart`

```dart
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:{{ template.dart_api_package | default("generated_api") }}/{{ template.dart_api_package | default("generated_api") }}.dart';

import 'profile_provider.dart';

part 'profile_view_model.freezed.dart';
part 'profile_view_model.g.dart';

@freezed
abstract class ProfileViewState with _$ProfileViewState {
  const factory ProfileViewState({
    required Profile? profile,
    required ProfileViewActions actions,
  }) = _ProfileViewState;
}

class ProfileViewActions {
  const ProfileViewActions({required this.refresh});

  final Future<void> Function() refresh;
}

@riverpod
class ProfileViewModel extends _$ProfileViewModel {
  late final ProfileViewActions _actions = ProfileViewActions(
    refresh: refresh,
  );

  @override
  Future<ProfileViewState> build() async {
    return ProfileViewState(profile: await _profile, actions: _actions);
  }

  Future<Profile?> get _profile => ref.watch(profileProvider.future);

  ProfileNotifier get _profileNotifier {
    return ref.read(profileNotifierProvider.notifier);
  }

  Future<void> refresh() {
    return _profileNotifier.refresh();
  }
}
```

`lib/features/profile/screens/profile_screen.dart`

```dart
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart';

import '../../../core/widgets/screen.dart';
import '../providers/profile_view_model.dart';
import '../widgets/profile_content.dart';

class ProfileScreen extends AsyncScreen<ProfileViewModel, ProfileViewState> {
  const ProfileScreen({super.key});

  @override
  ProviderListenable<AsyncValue<ProfileViewState>> get viewModelProvider =>
      profileViewModelProvider;

  @override
  Widget buildData(BuildContext context, ProfileViewState state) {
    return ProfileContent(profile: state.profile, actions: state.actions);
  }
}
```

After adding or changing the view model above, run:

```bash
cd app && make generate
```

Then update `docs/view-model-dependency-graph.md` with the screen mapping, provider edges, getter names, and cycle-check result:

```text
profile/screens/profile_screen.dart -> profileViewModelProvider
profileViewModelProvider -> profileProvider via _profile
profileViewModelProvider -> profileNotifierProvider via _profileNotifier
Cycle check: acyclic
```

**Never** call `ref.watch()` or `ref.read()` for feature/application providers from a screen or child widget. A screen may only interact with its own view model through the shared `Screen<VM, State>` or `AsyncScreen<VM, State>` base contract.
**Never** define a view model state as a plain Dart class; every view model state is a Freezed `abstract class`.
**Never** inline provider access inside view model methods; wrap each provider access in a named private getter on the view model.
**Never** make a Flutter widget `build()` method `async`; use an async `@riverpod` view model and `AsyncScreen` instead.
**Never** call `ref.read({{ template.dart_api_provider | default("generatedApiProvider") }})` from a screen — go through a notifier.
**Never** make a screen watch multiple providers. If a screen needs data from several providers, compose that data inside the screen view model.
**Never** use `@Riverpod(keepAlive: true)` or manual provider constructors for screen view models.

## Riverpod Dependency Graph

View models must not have circular references. Before adding, deleting, or rewiring any screen view model or provider dependency, update `docs/view-model-dependency-graph.md` with:

- the screen-to-view-model mapping
- each view model's `ref.watch`, `ref.read`, `ref.listen`, and `ref.invalidate` dependencies
- the getter name used for each provider dependency
- whether the resulting directed graph is acyclic

Then check the graph manually or with a small script before finishing. Reject any change where `AViewModel -> BViewModel -> AViewModel`, or a longer cycle, can occur. Prefer moving shared state into a lower-level service, repository, or computed provider when two view models need the same information.

## Barrel files

Feature widget directories expose a `widgets.dart` barrel that exports public feature widgets. Import paths elsewhere use that barrel, for example `import '../widgets/widgets.dart'`.

## Code generation

Run after any change to a `@riverpod`-annotated file or a `@freezed` class:

```bash
cd app && make generate
```

Generated `*.g.dart` and `*.freezed.dart` files are committed. **Never** edit them by hand.

## LLM hygiene — run before finishing

After every code change to the Flutter app, run verification before handing back to the user:

```bash
cd app && make check
```

- `make format-check` → `dart format --output=none --set-exit-if-changed .` — catches unformatted Dart, including generated API files.
- `make analyze` → `flutter analyze` — catches type errors, unused imports, missing `await`, and analysis warnings.
- `make api-client-analyze` → `cd lib/generated/api && dart analyze` — verifies the generated Dart API package is valid as a package.
- `make test` → `flutter test --exclude-tags chrome --fail-fast` — runs all unit and widget tests.

`app/lib/generated/api/` is generated, but it is also the app's Dart API package. Do not exclude it from analysis to hide failures. If it breaks, fix the OpenAPI source, generator template, generated package dependencies, or regeneration flow.

If `make analyze` reports auto-fixable issues, run `make fix-analyze` to apply them:

```bash
cd app && make fix-analyze   # dart fix --apply && dart format . && flutter analyze
```

Fix every failure introduced by your change. If the repo has a known unrelated full-analyze failure, run focused `dart analyze` on the files you touched plus `make test`, then run full `make analyze` and report the unchanged known failure clearly. Do not hide or ignore a new analyzer failure introduced by your change.

## Scope boundaries

This file covers folder structure, feature boundaries, screen authoring, the screen/view-model contract, barrel files, codegen, and the analyze/test commands an LLM must run after changes. It does **not** cover Riverpod provider patterns — see {{ skill_link("flutter-state") }}. It does **not** cover navigation — see {{ skill_link("flutter-navigation") }}. It does **not** cover the API client — see {{ skill_link("flutter-api") }}.

---

## Quick Reference Checklist

When writing Dart/Flutter code:

- [ ] **Tests**: Arrange/Act/Assert pattern used? Tests co-located or in `integration_test/`?
- [ ] **Architecture**: One auto-dispose `@riverpod` ViewModel per screen? ViewModel state is Freezed? Provider access wrapped in ViewModel getters? Screen extends `Screen<VM, State>` or `AsyncScreen<VM, State>`? Screen watches only that ViewModel? Dependency graph updated and acyclic?
- [ ] **Widgets**: Pure and prop-driven? (No logic)
- [ ] **UI**: Using `context.colors`? No hardcoded strings/colors?
- [ ] **Models**: Freezed `abstract class`? Non-nullable defaults used?
- [ ] **API**: Using generated client? (No manual HTTP calls)
- [ ] **Structure**: Flat feature folders? Core isolated?
- [ ] **Hygiene**: Ran formatting? Ran `make generate` when codegen was needed?
- [ ] **Validation**: Focused analyze passes? `make test` passes? Full `make analyze` passes or has only a reported known unrelated failure?

