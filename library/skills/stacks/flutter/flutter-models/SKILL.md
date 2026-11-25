---
name: flutter-models
description: "Flutter generated API types vs local models: AsyncNotifier data, Freezed UI state, form state. Load when tempted to create a model class that mirrors an API type, or when choosing what a provider's state should hold."
applyTo: 'app/lib/features/**/models/**/*.dart,app/lib/features/**/providers/**/*.dart'
tags: [flutter, mobile, standards, codegen]
---

# Flutter App — Generated Types vs Local Models

## Decision rule

Use generated API types from the `{{ template.dart_api_package | default("generated_api") }}` package **directly** for data that flows from the API. Create local Freezed models **only** for UI state that does not exist in the API. Every view model state is UI state and must be declared as a Freezed view model state, never as a plain Dart class.

```
┌──────────────────────────────────────────────────────────┐
│  Generated type ({{ template.dart_api_package | default("generated_api") }})                              │
│  Profile, Photo, AIConversation, Match, ...              │
│  → Use directly in AsyncNotifier<T> and computed         │
│    providers. Never duplicate these.                     │
├──────────────────────────────────────────────────────────┤
│  Local Freezed state (features/*/providers/)             │
│  ProfileEditState, AssistantState, ...                     │
│  → Wraps generated types + adds UI flags                 │
│    (isLoading, isSending, validationErrors, hasChanges)  │
└──────────────────────────────────────────────────────────┘
```

## Pattern 1: Data provider — use generated type directly

For read-only data fetched from the API, the `AsyncNotifier` returns the generated type:

```dart
class ProfileNotifier extends AsyncNotifier<Profile?> {
  @override
  Future<Profile?> build() async {
    final profileApi = ref.read(profileApiProvider);
    final response = await profileApi.getProfile();
    return response.data; // generated Profile type
  }
}
```

**Never** create a local `ProfileModel` class that mirrors the generated `Profile`. Use `Profile` from `{{ template.dart_api_package | default("generated_api") }}` everywhere.

## Pattern 2: UI state — Freezed class wrapping generated types

When you need UI-only state alongside API data, create a Freezed class that **holds** the generated type (not duplicates it):

```dart
@freezed
abstract class AssistantState with _$AssistantState {
  const factory AssistantState({
    AIConversation? conversation,  // generated type
    @Default(false) bool isLoading,
    @Default(false) bool isSending,
    @Default('') String error,
  }) = _AssistantState;
}
```

The generated `AIConversation` is a field on the state, not spread into individual fields.

Screen view model state follows the same rule. A state such as `OnboardingViewState`, `ProfileViewState`, or `SettingsViewState` must be `@freezed abstract class ... with _$...` with a generated `.freezed.dart` part file, even if it only contains a few scalar fields and an actions object.

## Pattern 3: Form state — extract scalar fields

For editable forms, extract the editable fields as plain scalars. The form state is NOT a wrapper around the generated type — it is a flat structure optimised for field-level binding:

```dart
@freezed
abstract class ProfileEditState with _$ProfileEditState {
  const factory ProfileEditState({
    @Default('') String displayName,
    @Default('') String bio,
    @Default({}) Map<String, String> validationErrors,
    @Default(false) bool hasChanges,
    @Default(false) bool isSubmitting,
  }) = _ProfileEditState;

  factory ProfileEditState.fromProfile(Profile profile) {
    return ProfileEditState(
      displayName: profile.displayName ?? '',
      bio: profile.bio ?? '',
    );
  }
}
```

The `.fromProfile()` factory hydrates from the generated type. The `submit()` method maps back to the generated request type.

## Decision matrix

| Scenario | Approach |
|---|---|
| Displaying API data (list, detail screen) | `AsyncNotifier<GeneratedType>` — use generated type directly |
| Mutating API data (edit form) | `Notifier<FormState>` — Freezed state with scalar fields + `.fromEntity()` factory |
| UI state + API data (chat, complex screens) | `Notifier<ScreenState>` — Freezed state holding generated type as a field + UI flags |
| Derived/computed value | `Provider<T>` — derive from existing providers, no new model |
| Local caching (offline) | Create a local model with Hive/Isar adapters (rare in this app) |

## Mapping back to generated request types

On form submission, map the local state to the generated request type in the notifier:

```dart
Future<void> submit() async {
  final profileApi = ref.read(profileApiProvider);
  await profileApi.updateProfile(
    updateProfileRequest: UpdateProfileRequest(
      displayName: state.displayName,
      bio: state.bio,
    ),
  );
}
```

**Never** create an intermediate DTO between the form state and the generated request type. Map directly.

## Scope boundaries

This file covers when to use generated API types vs. local Freezed models, the three patterns (data, UI state, form), and the mapping approach. It does **not** cover how to generate the API client — see {{ skill_link("flutter-api") }}. It does **not** cover Freezed syntax — see {{ skill_link("flutter-data") }}.

