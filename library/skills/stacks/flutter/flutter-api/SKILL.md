---
name: flutter-api
description: "Flutter API client: generated Dart/Dio client, OpenAPI Generator, api make generate, bearer token via ref.listen, api_providers.dart. Load when adding a backend endpoint to the app, regenerating the client, or editing api_providers.dart."
applyTo: 'app/lib/core/services/api/**/*.dart,app/lib/features/**/providers/**/*.dart,app/lib/generated/api/**'
tags: [flutter, mobile, standards, codegen]
---

# Flutter App — API Client & Network Layer

## Three-tier abstraction

```
lib/generated/api/          ← auto-generated Dart/Dio client (never edit)
lib/core/services/api/      ← Riverpod providers that vend the generated client
lib/features/*/providers/   ← notifiers that call the API providers
```

**Never** import the generated client directly into screens or widgets.
**Never** instantiate the generated API client outside `lib/core/services/api/`.

## Generated API client

`lib/generated/api/` is produced by the **OpenAPI Generator — `@openapitools/openapi-generator-cli`**, run via `npx` with the **`dart-dio`** generator (`-g dart-dio`) against `api/pkg/api/openapi.yaml`, using the custom templates under `app/.openapi-generator-templates/` (e.g. `pubspec.mustache`). Regenerate with `cd app && make generate-api`. The output uses `built_value` for immutable types and `json_serializable` for serialisation. Do not commit manual changes to this directory — they will be overwritten, and do not swap the generator (`dart-dio`) without updating the templates and the Riverpod provider wiring below.

## Code generation commands (three distinct commands)

These three commands are different — do not confuse them:

| Command | Run from | Regenerates |
|---|---|---|
| `make generate` | `api/` | Go types + `ServerInterface` from `openapi.yaml` |
| `make generate-api` | `app/` | Dart/Dio HTTP client from `openapi.yaml` |
| `make generate` | `app/` | Riverpod `.g.dart` + Freezed `.freezed.dart` files |

When you add a new backend endpoint, the required sequence is:

```bash
# 1. Regenerate Go types (after editing openapi.yaml)
cd api && make generate

# 2. Regenerate Dart HTTP client
cd app && make generate-api

# 3. Regenerate Riverpod/Freezed (if you added a new notifier or Freezed class)
cd app && make generate
```

**Never** run `cd app && make generate` as a substitute for `make generate-api` — they produce completely different output.

## Riverpod API providers

The generated client is vended as a Riverpod provider in `lib/core/services/api/api_providers.dart`. The bearer token is injected centrally via `ref.listen`:

```dart
final {{ template.dart_api_provider | default("generatedApiProvider") }} = Provider<{{ template.dart_api_client | default("GeneratedApi") }}>((ref) {
  final dioClient = ref.read(dioClientProvider);
  final settings = ref.watch(settingsProvider);

  final api = {{ template.dart_api_client | default("GeneratedApi") }}(
    dio: dioClient.dio,
    basePathOverride: settings.backendUrl,
  );

  ref.listen<String?>(tokenProvider, (previous, next) {
    api.setBearerAuth('bearer', next ?? '');
  });

  return api;
});
```

Feature notifiers obtain the appropriate sub-client via a scoped provider (e.g. `profileApiProvider`, `matchesApiProvider`) that calls `ref.read({{ template.dart_api_provider | default("generatedApiProvider") }}).<subApi>`.

**Never** set bearer tokens in a notifier or screen.
**Never** read `tokenProvider` outside `api_providers.dart`.

## Adding a sub-API provider for a new endpoint

When codegen produces a new `XxxApi` class (because you added a new `tags:` group in `openapi.yaml`), you **must** add a scoped provider in `lib/core/services/api/api_providers.dart` before any notifier can use it.

```dart
// lib/core/services/api/api_providers.dart

/// Provider for Listings API  ← add one per new tag group
final listingsApiProvider = Provider<ListingsApi>((ref) {
  final api = ref.read({{ template.dart_api_provider | default("generatedApiProvider") }});
  return api.getListingsApi();
});
```

Then reference it in a notifier via `ref.read`:

```dart
// lib/features/listings/providers/listings_notifier.dart
class ListingsNotifier extends AsyncNotifier<List<Listing>> {
  @override
  Future<List<Listing>> build() async {
    final listingsApi = ref.read(listingsApiProvider);
    final response = await listingsApi.getListings();
    return response.data ?? [];
  }
}
```

**Never** call `ref.read({{ template.dart_api_provider | default("generatedApiProvider") }}).getListingsApi()` inside a notifier directly — always go through the scoped provider.
**Never** instantiate `ListingsApi(dio: ...)` by hand — the scoped provider handles wiring.

## DioClient

`lib/core/services/network/dio_client.dart` configures Dio with:
- Logging interceptor (debug only)
- Auth interceptor (injects bearer token)
- 401 refresh interceptor (calls Firebase to get a new token, retries the request once)

**Never** handle 401 retry logic in a notifier — DioClient already does it.
**Never** add interceptors in a notifier or screen.

## Photo upload (three-step pattern)

The upload flow is: get signed URL → PUT/POST to GCS → confirm with backend. Follow the pattern in `profile_notifier.dart`:

```dart
// Step 1: get signed upload URL
final urlResp = await profileApi.getPhotoUploadUrl(
  photoUploadUrlRequest: PhotoUploadUrlRequest(
    contentType: contentType,
    displayOrder: displayOrder,
  ),
);

// Step 2: upload bytes directly to GCS using the signed URL
final uploadResponse = uploadMethod == POST
    ? await http.post(uri, headers: {'Content-Type': mimeType}, body: bytes)
    : await http.put(uri, headers: {'Content-Type': mimeType}, body: bytes);

// Step 3: confirm with backend
await profileApi.confirmPhotoUpload(
  photoId: photoId,
  confirmPhotoUploadRequest: ConfirmPhotoUploadRequest(displayOrder: displayOrder),
);
```

Use `timeout(const Duration(seconds: 30))` on backend calls and `timeout(const Duration(seconds: 60))` on the GCS upload step.

## Error handling in notifiers

Let errors propagate as `AsyncValue.error` — do not swallow them silently. Rollback state before setting the error so the UI retains the last valid data:

```dart
final previous = state;
try {
  state = AsyncValue.data(await doWork());
} catch (e, st) {
  state = previous;
  state = AsyncValue.error(e, st);
}
```

## Scope boundaries

This file covers the generated client, codegen commands, Riverpod API providers, adding sub-API providers for new endpoints, token injection, DioClient, the photo upload pattern, and error propagation. It does **not** cover the backend OpenAPI spec — see `go-openapi`. It does **not** cover notifier patterns generally — see {{ skill_link("flutter-state") }}.

