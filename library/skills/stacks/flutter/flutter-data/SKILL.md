---
name: flutter-data
description: "Flutter data layer: Dio client from openapi.yaml, Freezed models, part files, json_serializable, default values. Load when writing or fixing a Freezed class, a part directive or build_runner error, or nullable vs defaulted fields."
applyTo: 'app/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter Data & Models Instructions

**CRITICAL: LLM Contract for Writing Dart/Flutter Code**

Apply these rules strictly related to API generation, Models, and Data handling.

---

## Rule 1: Generating Dio API Client from OpenAPI

**CRITICAL:** The Dio API client is generated from the backend's OpenAPI specification. NEVER hand-edit generated files.

### Generation Process:

**Step 1: Update Backend OpenAPI Spec** (`api/pkg/api/openapi.yaml`)
**Step 2: Generate Dart Dio Client** (`make generate-api` from app folder)
**Step 3: Run Flutter Pub Get** (`flutter pub get`)

**ENFORCE:**

- Regenerate client after ANY OpenAPI spec changes
- Use provided script (`make generate-api`)
- NEVER edit files in `lib/generated/api/`

---

## Rule 2: Using Generated API Types

**CRITICAL:** Prefer using generated API types directly instead of creating duplicate local models.

### Correct Pattern:

```dart
// Provider uses generated API directly
class ConversationsNotifier extends StateNotifier<ConversationsListState> {
  Future<void> loadConversations() async {
      // Uses generated ConversationsResponse type directly
      final response = await _conversationsApi.getConversations();
      state = state.copyWith(conversations: response.data?.conversations.toList() ?? []);
  }
}
```

**ENFORCE:**

- Use generated types from `{{ template.dart_api_package | default("generated_api") }}` package directly in state classes
- State classes (`@freezed`) reference generated types, not duplicates
- Only create local models when caching (Hive/SQLite) or offline support is required

**REJECT:**

- Creating duplicate model classes that mirror generated types
- Custom `fromJson`/`toJson` when generated types handle serialization

---

## Rule 3: Freezed Models Configuration

**ENFORCE:** All Freezed models must use `abstract class` to satisfy analyzer requirements when using mixins.

**ENFORCE:** Every view model state is a Freezed model. A `*ViewState` used by a Riverpod view model must never be a plain Dart class; declare it with `@freezed abstract class *ViewState with _$*ViewState` and regenerate.

### Correct Freezed Pattern:

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'user.freezed.dart';
part 'user.g.dart'; // Only if using json_serializable

@freezed
abstract class User with _$User {
  // Abstract class required for mixin validation
  const factory User({
    required String id,
    @Default('') String name,
  }) = _User;

  const User._();
  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}
```

**ENFORCE:**

- Use `abstract class Name with _$Name`
- Use `const factory` constructor
- Use `@Default` for optional fields
- Run `cd app && make generate` after modifying annotated classes

---

## Rule 4: Non-Nullable Types with Default Values

**CRITICAL:** Prefer non-nullable types with default values (`@Default('')`, `@Default(0)`) instead of nullable types (`String?`, `int?`).

**GUIDELINES:**

- `String` -> `@Default('')`
- `int` -> `@Default(0)`
- `bool` -> `@Default(false)`
- `List<T>` -> `@Default([])`

**REJECT:**

- Nullable collections (`List<T>?`)
- Nullable strings/primitives when default is semantically valid

