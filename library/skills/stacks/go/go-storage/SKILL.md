---
name: go-storage
description: "Go object storage: ObjectStorage adapter, StorageClient interfaces, SignedURLOptions, object paths, signed upload URL then confirm-upload flow. Load when adding file upload or download, signed URLs, photo handling, or a storage dependency."
applyTo: 'api/internal/io/storage/**/*.go,api/internal/core/services/**/service.go'
tags: [go, backend, standards]
---

# Go Backend — Object Storage

## Architecture

File storage goes to an object store that issues signed URLs. The adapter lives in `internal/io/storage/objects.go` as the `ObjectStorage` type. The project overlay names the provider and its SDK. Services access storage through a `StorageClient` interface defined in the consuming service package — never the concrete `ObjectStorage` type.

```
internal/io/storage/objects.go           ← concrete implementation
internal/core/services/profile/service.go ← defines StorageClient interface
internal/app/container.go                ← wires storageClient → service
```

**Never** import `internal/io/storage` from `internal/core/`. The service defines its own interface.

## StorageClient interface

Each service that needs storage defines a minimal interface in its own package:

```go
// internal/core/services/profile/service.go
type StorageClient interface {
    GetSignedURL(ctx context.Context, objectPath string, opts storage.SignedURLOptions) (*storage.SignedURLResult, error)
    Exists(ctx context.Context, objectPath string) (exists bool, size int64, contentType string, err error)
    Delete(ctx context.Context, objectPath string) error
}
```

The interface references `storage.SignedURLOptions` and `storage.SignedURLResult` — these are plain value structs in `internal/io/storage/` and are the only types imported from that package.

**Never** define a monolithic `StorageClient` interface in a shared package. Each service declares only the methods it uses.

## Value types

```go
// internal/io/storage/objects.go

type SignedURLOptions struct {
    Method      string // "PUT" for upload, "GET" for download
    ContentType string // MIME type for uploads (e.g. "image/jpeg")
    MaxSize     int64  // Max content length in bytes (0 = no limit)
}

type SignedURLResult struct {
    URL       string    // The signed URL to use
    Method    string    // HTTP method the client must use for this URL
    ExpiresAt time.Time // When the URL expires
}
```

The `Method` field in `SignedURLResult` can differ from the requested method. A local stand-in for the store may accept `POST` where production takes `PUT`. The client must read this field and use the method it names.

## Object path convention

Storage paths follow this pattern:

```
users/{userID}/photos/{photoID}
```

Paths are stored in the database as **object paths** (not full URLs). Signed URLs are generated on-demand when serving responses.

## Signed URL generation pattern (service layer)

The three-step upload flow is orchestrated by the service:

### Step 1: Generate signed upload URL

```go
func (s *Service) GetPhotoUploadURL(ctx context.Context, userID string, input *GetPhotoUploadURLInput) (*GetPhotoUploadURLResult, error) {
    // 1. Business validation (e.g. max 9 photos)
    // 2. Generate unique ID
    photoID := uuid.New().String()
    objectPath := fmt.Sprintf("users/%s/photos/%s", userID, photoID)

    // 3. Request signed URL from storage
    result, err := s.storage.GetSignedURL(ctx, objectPath, storage.SignedURLOptions{
        Method:      "PUT",
        ContentType: input.ContentType,
        MaxSize:     3 * 1024 * 1024, // 3 MB
    })
    if err != nil {
        return nil, fmt.Errorf("failed to get signed URL: %w", err)
    }

    return &GetPhotoUploadURLResult{
        PhotoID:      photoID,
        ObjectName:   objectPath,
        UploadURL:    result.URL,
        UploadMethod: result.Method,
        ExpiresAt:    result.ExpiresAt,
    }, nil
}
```

### Step 2: Client uploads directly to the object store (not handled by backend)

### Step 3: Confirm upload

```go
func (s *Service) ConfirmPhotoUpload(ctx context.Context, userID string, input *ConfirmPhotoUploadInput) (*domain.Photo, error) {
    objectPath := fmt.Sprintf("users/%s/photos/%s", userID, input.PhotoID)

    // 1. Verify file exists in storage
    exists, size, contentType, err := s.storage.Exists(ctx, objectPath)
    if err != nil || !exists {
        return nil, ErrFileNotUploaded
    }

    // 2. Validate size and content type
    if size > 3*1024*1024 {
        return nil, ErrFileTooLarge
    }
    if !isAllowedContentType(contentType) {
        return nil, ErrValidation
    }

    // 3. Create domain model and persist
    photo := domain.Photo{
        ID:               input.PhotoID,
        URL:              objectPath,
        ContentType:      contentType,
        Size:             size,
        DisplayOrder:     input.DisplayOrder,
        ModerationStatus: "pending",
    }

    // 4. Update profile with new photo
    // ...

    return &photo, nil
}
```

## Adding storage to a new service

1. **Define the interface** in your service package, declaring only the methods you need:

```go
// internal/core/services/listing/service.go
type StorageClient interface {
    GetSignedURL(ctx context.Context, objectPath string, opts storage.SignedURLOptions) (*storage.SignedURLResult, error)
    Delete(ctx context.Context, objectPath string) error
}
```

2. **Accept it via constructor**:

```go
func NewService(repo Repository, storage StorageClient) *Service {
    return &Service{repo: repo, storage: storage}
}
```

3. **Wire in container.go** — the same `storageClient` instance is passed to all services that need it:

```go
// internal/app/container.go — inside NewContainer
storageClient, err := storage.NewObjectStorage(ctx, settings.StorageBucket, logger)
// ...
listingService := listing.NewService(listingRepo, storageClient)
```

`storageClient` satisfies any service-local `StorageClient` interface because `*storage.ObjectStorage` implements all three methods (`GetSignedURL`, `Exists`, `Delete`).

## Local stand-in

Local runs and integration tests point `ObjectStorage` at a local stand-in for the store (an emulator or a compatible server). The adapter reads the stand-in's address from settings, never from a service. In local mode:
- Signed URLs point at the stand-in's host and are plain HTTP.
- No real signing happens.
- The upload method may differ from production. The adapter sets `SignedURLResult.Method` to the method the stand-in accepts.

The client reads `UploadMethod` from the API response to handle both cases.

## ObjectStorage methods reference

| Method | Signature | Use when |
|---|---|---|
| `GetSignedURL` | `(ctx, objectPath, SignedURLOptions) → (*SignedURLResult, error)` | Generating upload or download URLs |
| `Exists` | `(ctx, objectPath) → (exists bool, size int64, contentType string, err error)` | Confirming an upload succeeded |
| `Delete` | `(ctx, objectPath) → error` | Removing a file (e.g. photo deletion) |

## Scope boundaries

This file covers the `ObjectStorage` adapter, the `StorageClient` interface pattern, object paths, signed URL generation, the three-step upload flow, the local stand-in, and how to wire storage into a new service. It does **not** cover the client-side upload flow. The client stack's skill covers it. It does **not** cover one provider's SDK or signing setup. The project overlay names the provider. It does **not** cover the controller layer for upload endpoints — see {{ skill_link("go-controller") }}.

