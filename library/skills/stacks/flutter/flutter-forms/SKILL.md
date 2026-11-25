---
name: flutter-forms
description: "Flutter forms and validation: Freezed form state, validationErrors, isSubmitting, TextFormField, dirty tracking. Load when building or reviewing an edit or create form, field validation, or a submit button's loading and error behaviour."
applyTo: 'app/lib/features/**/screens/**/*.dart,app/lib/features/**/widgets/**/*.dart,app/lib/features/**/providers/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter App — Forms, Validation & Submission

## Two-tier architecture

Forms follow a split between **state** (in a Riverpod `Notifier`) and **presentation** (in widgets). The notifier owns validation logic and submission; widgets are dumb renderers.

```
Notifier<FormState>          ← owns fields, validation, dirty tracking, submit
  ↑ watched by Screen<VM, State> ← base screen reads the one screen view model
Screen extends Screen<VM, State> ← renders state and calls view model actions
  └─ TextFormField widgets   ← pure, receive values + callbacks via props
```

**Never** put validation logic in a widget `build()` method.
**Never** call the API directly from a screen — go through the notifier.
**Never** make a form screen watch a form notifier plus other providers directly. Compose everything the form needs in the form screen view model.

## Form state pattern (Freezed)

Create a Freezed state class per form. Include field values, validation errors, dirty flag, and submission status:

```dart
@freezed
abstract class ProfileEditState with _$ProfileEditState {
  const factory ProfileEditState({
    @Default('') String displayName,
    @Default('') String bio,
    @Default('') String tagline,
    @Default({}) Map<String, String> validationErrors,
    @Default(false) bool hasChanges,
    @Default(false) bool isSubmitting,
  }) = _ProfileEditState;

  /// Hydrate from the current profile (generated API type).
  factory ProfileEditState.fromProfile(Profile profile) {
    return ProfileEditState(
      displayName: profile.displayName ?? '',
      bio: profile.bio ?? '',
      tagline: profile.tagline ?? '',
    );
  }
}
```

**Rules**:
- Use `@Default('')` for string fields, `@Default(false)` for booleans, `@Default({})` for error maps.
- Include a `.fromProfile()`/`.fromEntity()` factory to hydrate from the generated API type.
- `hasChanges` is `true` when any field diverges from the initial data.
- `isSubmitting` guards the submit button and disables inputs.

## Notifier for editable forms

Use a synchronous `Notifier<T>` (not `AsyncNotifier`) for form state. Load initial data from another provider:

```dart
@riverpod
class ProfileEditNotifier extends _$ProfileEditNotifier {
  @override
  ProfileEditState build() {
    final profile = ref.watch(currentProfileProvider);
    return profile != null
        ? ProfileEditState.fromProfile(profile)
        : const ProfileEditState();
  }

  void updateDisplayName(String value) {
    state = state.copyWith(displayName: value, hasChanges: true);
    _validate();
  }

  void updateBio(String value) {
    state = state.copyWith(bio: value, hasChanges: true);
    _validate();
  }

  void _validate() {
    final errors = <String, String>{};

    if (state.displayName.isNotEmpty && state.displayName.length < 2) {
      errors['displayName'] = 'Must be at least 2 characters';
    }
    if (state.bio.length > 500) {
      errors['bio'] = 'Must be 500 characters or less';
    }

    state = state.copyWith(validationErrors: errors);
  }

  bool get isValid => state.validationErrors.isEmpty && state.hasChanges;

  Future<void> submit() async {
    _validate();
    if (!isValid) return;

    state = state.copyWith(isSubmitting: true);
    try {
      final profileApi = ref.read(profileApiProvider);
      await profileApi.updateProfile(
        updateProfileRequest: UpdateProfileRequest(
          displayName: state.displayName,
          bio: state.bio,
        ),
      );
      // Refresh the source-of-truth provider
      ref.invalidate(profileNotifierProvider);
      state = state.copyWith(isSubmitting: false, hasChanges: false);
    } catch (e) {
      state = state.copyWith(isSubmitting: false);
      rethrow; // Let the screen catch and show a SnackBar
    }
  }
}
```

**Rules**:
- `_validate()` is called after every field update and before `submit()`.
- Validation rules live in the notifier, never in widget validators.
- After a successful submit, `ref.invalidate()` the source-of-truth async provider so dependent screens refresh.
- On failure, reset `isSubmitting` and rethrow so the screen can display the error.

## Validation rules

Validation is state-driven. The `validationErrors` map uses field names as keys and user-facing messages as values.

```dart
void _validate() {
  final errors = <String, String>{};

  // Required field
  if (state.displayName.isEmpty) {
    errors['displayName'] = 'Name is required';
  } else if (state.displayName.length < 2) {
    errors['displayName'] = 'Must be at least 2 characters';
  }

  // Optional field — only validate if non-empty
  if (state.bio.isNotEmpty && state.bio.length > 500) {
    errors['bio'] = 'Must be 500 characters or less';
  }

  state = state.copyWith(validationErrors: errors);
}
```

**Never** use Flutter's `Form` widget + `GlobalKey<FormState>` for validation. Use the notifier-driven pattern above.
**Never** show validation errors before the user has interacted with a field (check `hasChanges` or field-level dirty tracking).

## Screen binding

Screens extend `Screen<VM, State>`. If the form view model hydrates asynchronously, screens extend `AsyncScreen<VM, State>` instead. The shared base class watches the screen view model. The `viewModelProvider` getter is only the provider handle and must be typed as `ProviderListenable<State>` for synchronous screens or `ProviderListenable<AsyncValue<State>>` for async screens; the rendered form state remains the typed `State` template parameter. The concrete screen renders from the typed state and wires callbacks exposed by that view model:

```dart
class ProfileEditScreen extends Screen<ProfileEditViewModel, ProfileEditState> {
  const ProfileEditScreen({super.key});

  @override
  ProviderListenable<ProfileEditState> get viewModelProvider =>
      profileEditViewModelProvider;

  @override
  Widget buildScreen(BuildContext context, ProfileEditState state) {
    return Scaffold(
      appBar: AppBar(
        title: Text(context.l10n.editProfile),
        actions: [
          TextButton(
            onPressed: state.canSubmit ? state.actions.submit : null,
            child: state.isSubmitting
                ? const SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(context.l10n.save),
          ),
        ],
      ),
      body: ListView(
        padding: EdgeInsets.all(AppSpacing.md),
        children: [
          TextFormField(
            initialValue: state.displayName,
            decoration: InputDecoration(
              labelText: context.l10n.displayName,
              errorText: state.validationErrors['displayName'],
              border: OutlineInputBorder(borderRadius: AppRadius.inputRadius),
            ),
            onChanged: state.actions.updateDisplayName,
          ),
          Gap(AppSpacing.md),
          TextFormField(
            initialValue: state.bio,
            decoration: InputDecoration(
              labelText: context.l10n.bio,
              errorText: state.validationErrors['bio'],
              border: OutlineInputBorder(borderRadius: AppRadius.inputRadius),
            ),
            maxLines: 4,
            onChanged: state.actions.updateBio,
          ),
        ],
      ),
    );
  }
}
```

**Rules**:
- Disable the save button when `isSubmitting` or `!isValid`.
- Show a `CircularProgressIndicator` inside the button while submitting.
- On success: `context.pop()` (or navigate away).
- On error: show a `SnackBar` with the error message.
- Bind `errorText` on `InputDecoration` to `state.validationErrors['fieldName']`.
- Use `initialValue` (not `controller`) when the notifier owns the value. Use `TextEditingController` only when you need programmatic cursor control.

## TextFormField conventions

All text inputs follow Material 3 outlined style:

```dart
TextFormField(
  decoration: InputDecoration(
    labelText: context.l10n.fieldLabel,
    errorText: state.validationErrors['fieldName'],
    border: OutlineInputBorder(borderRadius: AppRadius.inputRadius),
    filled: false, // Never use filled text fields (look disabled)
  ),
  onChanged: notifier.updateFieldName,
)
```

**Never** use `filled: true` on text fields.
**Always** use `OutlineInputBorder` — never `UnderlineInputBorder`.

## Dirty tracking

`hasChanges` is set to `true` on the first field mutation. For forms that need field-level dirty tracking (e.g. to highlight changed fields), compare against the initial values:

```dart
bool get hasChanges {
  final initial = _initialState;
  return state.displayName != initial.displayName ||
      state.bio != initial.bio;
}
```

Store the initial state in a late field set once during `build()`.

## Submission UX summary

| State | Button | Inputs | Feedback |
|---|---|---|---|
| Idle, no changes | Disabled (grayed out) | Enabled | — |
| Idle, has changes, valid | Enabled | Enabled | — |
| Idle, has changes, invalid | Disabled | Enabled | Error text on fields |
| Submitting | Disabled, shows spinner | Disabled or dimmed | Optional SnackBar "Saving…" |
| Success | — | — | `context.pop()` or success SnackBar |
| Failure | Re-enabled | Re-enabled | Error SnackBar |

## Scope boundaries

This file covers form state architecture, validation patterns, screen binding, TextFormField conventions, dirty tracking, and submission UX. It does **not** cover photo upload flows — see {{ skill_link("flutter-api") }}. It does **not** cover how notifiers work generally — see {{ skill_link("flutter-state") }}.

