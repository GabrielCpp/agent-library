---
name: flutter-state
description: "Flutter Riverpod state: AsyncNotifier, Notifier, Provider, optimistic updates, keepAlive, codegen. Load when writing or debugging a notifier or provider, choosing a provider variant, or fixing stale or disposed state."
applyTo: 'app/lib/features/**/providers/**/*.dart,app/lib/core/services/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter App — State Management (Riverpod)

## Provider variants

| Variant | Use when |
|---|---|
| `AsyncNotifier<T>` | Async data that can be mutated (fetch + write) |
| `Notifier<T>` | Synchronous state that is mutated by the UI (e.g. form state) |
| `Provider<T>` | Derived/computed values from other providers — no async calls |

**Never** put async calls inside a synchronous `Provider<T>`.

## AsyncNotifier — fetch + mutate pattern

`build()` loads initial state. Mutation methods update `state` directly. The private-getter rule below applies to screen view models; lower-level providers and feature notifiers may use direct `ref.read`/`ref.watch` when they are not screen view models.

```dart
class ProfileNotifier extends AsyncNotifier<Profile?> {
  @override
  Future<Profile?> build() async {
    final profileApi = ref.read(profileApiProvider);
    final response = await profileApi.getProfile();
    return response.data;
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final profileApi = ref.read(profileApiProvider);
      final response = await profileApi.getProfile();
      return response.data;
    });
  }

  Future<void> updateProfile(ProfileUpdate update) async {
    final profileApi = ref.read(profileApiProvider);
    final previous = state;
    try {
      final response = await profileApi.updateProfile(profileUpdate: update);
      state = AsyncValue.data(response.data);
    } catch (e, st) {
      state = previous;           // rollback
      state = AsyncValue.error(e, st);
    }
  }
}

final profileNotifierProvider =
    AsyncNotifierProvider<ProfileNotifier, Profile?>(() => ProfileNotifier());
```

Always roll back to `previous` state before setting an error state, so the UI can still read the last known data during error display.

## Optimistic updates

For mutations that should feel instant:

1. Save `final previous = state`
2. Apply the optimistic update immediately
3. Await the API call
4. On failure: restore `state = previous`, then set error

## Computed providers

Use `Provider<T>` with `ref.watch` for derived values. These re-evaluate automatically when their dependencies change.

```dart
final currentProfileProvider = Provider<Profile?>((ref) {
  return ref.watch(profileNotifierProvider).asData?.value;
});

final isProfileCompleteProvider = Provider<bool>((ref) {
  final profile = ref.watch(currentProfileProvider);
  if (profile == null) return false;
  return profile.displayName.isNotEmpty &&
      profile.photos.isNotEmpty &&
      profile.completenessScore >= 50;
});
```

**Never** call `ref.read` inside `build()` for dependencies that should trigger rebuilds — use `ref.watch`.
**Never** put `await` inside a synchronous `Provider`.

## View model dependency graph

Provider dependencies are a directed graph. Every time you add, remove, rename, or rewire a Riverpod view model/provider dependency, update `docs/view-model-dependency-graph.md` before finishing.

Record every edge introduced by:

- `ref.watch(xProvider)`
- `ref.read(xProvider)`
- `ref.listen(xProvider, ...)`
- `ref.invalidate(xProvider)`

View models must not depend on each other circularly, directly or indirectly. If `AViewModel` needs `BViewModel` and `BViewModel` also needs `AViewModel`, extract the shared state or action into a lower-level provider, repository, or service and make both view models depend on that instead.

Screen view models are allowed to compose lower-level providers and other acyclic dependencies, but screens must only watch their own screen view model through the shared `Screen<VM, State>` or `AsyncScreen<VM, State>` base class.

Async screen view models return `Future<State>` from `build()`. The screen uses `AsyncScreen<VM, State>`, not an `async` Flutter widget `build()` method.

Every view model state type must be a Freezed state class. Use `@freezed abstract class <Name>ViewState with _$<Name>ViewState` plus the matching `.freezed.dart` part file for sync and async view models alike. Do not use plain Dart classes for view model state, even when the state only contains scalar fields or an actions object.

Every provider access inside a screen view model must go through a named private getter on that view model. Avoid inline calls such as `ref.read(authNotifierProvider.notifier)` or `ref.watch(profileProvider)` in `build()` and action methods. Instead, define getters near `build()`:

```dart
AsyncValue<User?> get _authState => ref.watch(authNotifierProvider);
AuthNotifier get _authNotifier => ref.read(authNotifierProvider.notifier);
```

Use `watch` getters only for dependencies that should rebuild the view model state. Use `read`/snapshot getters for action methods and one-off commands.

## keepAlive vs auto-dispose

- `keepAlive: true` (or `AsyncNotifierProvider` without code-gen auto-dispose) for global singletons: auth state, settings, API clients.
- Screen view models use lowercase `@riverpod` and must auto-dispose. Do not set `keepAlive: true` for a screen view model.
- Feature-level notifiers should auto-dispose unless they represent a deliberate feature-wide cache with a documented lifecycle reason.
- Prefer generated `@riverpod` notifiers/functions over manual provider constructors for view models.

## Notifier for form state

Use a synchronous `Notifier<T>` with a Freezed state class for edit forms:

```dart
class ProfileEditNotifier extends Notifier<ProfileEditState> {
  @override
  ProfileEditState build() {
    final profile = ref.watch(currentProfileProvider);
    return profile != null
        ? ProfileEditState.fromProfile(profile)
        : const ProfileEditState();
  }

  void updateDisplayName(String value) {
    state = state.copyWith(displayName: value, hasChanges: true);
  }
}
```

## Code generation

After adding or modifying a notifier or Freezed class, run:

```bash
cd app && make generate
```

Generated `*.g.dart` files are committed. **Never** edit them.

## Scope boundaries

This file covers `AsyncNotifier`, `Notifier`, `Provider`, optimistic updates, computed providers, the view model dependency graph, keepAlive, and codegen. It does **not** cover how providers are consumed in screens — see {{ skill_link("flutter-architecture") }}. It does **not** cover the API client providers that notifiers call — see {{ skill_link("flutter-api") }}.

