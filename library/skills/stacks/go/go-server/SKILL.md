---
name: go-server
description: "Go server composition: Server struct embedding api.Unimplemented, NewServer, ServerInterface check, feature checklist. Load when adding a controller or endpoint to server.go, fixing a ServerInterface compile error, or planning a feature."
applyTo: 'api/internal/app/server.go,api/internal/app/container.go'
tags: [go, backend, standards]
---

# Go Backend — Server Composition & New Feature Wiring

## Server struct

`internal/app/server.go` defines the `Server` struct that implements the generated `api.ServerInterface`. It embeds `api.Unimplemented` (which returns 501 for any endpoint not yet implemented) and holds one field per controller.

```go
type Server struct {
    api.Unimplemented
    health        *controllers.HealthController
    profile       *controllers.ProfileController
    ai            *controllers.AIController
    matches       *controllers.MatchesController
    conversations *controllers.ConversationsController
}
```

## NewServer constructor

`NewServer` receives all controllers as positional arguments:

```go
func NewServer(
    health *controllers.HealthController,
    profile *controllers.ProfileController,
    ai *controllers.AIController,
    matches *controllers.MatchesController,
    conversations *controllers.ConversationsController,
) *Server {
    return &Server{
        health:        health,
        profile:       profile,
        ai:            ai,
        matches:       matches,
        conversations: conversations,
    }
}
```

## Delegation methods

Each generated interface method on `Server` delegates to the matching controller method. One line per delegation — no logic:

```go
func (s *Server) GetProfile(w http.ResponseWriter, r *http.Request) {
    s.profile.GetProfile(w, r)
}
```

For methods with path parameters or query params, forward them:

```go
func (s *Server) ConfirmPhotoUpload(w http.ResponseWriter, r *http.Request, photoId string) {
    s.profile.ConfirmPhotoUpload(w, r, photoId)
}

func (s *Server) GetMatches(w http.ResponseWriter, r *http.Request, params api.GetMatchesParams) {
    s.matches.GetMatches(w, r)
}
```

**Never** put logic in a delegation method — it must be a one-line call to the controller.

## Compile-time interface check

This line ensures the Go compiler verifies that `Server` satisfies `api.ServerInterface`:

```go
var _ api.ServerInterface = (*Server)(nil)
```

If you add a new endpoint to `openapi.yaml` and run `make generate`, this line will cause a compile error until you add the delegation method.

## Adding a new controller to Server (step-by-step)

### 1. Add the field to `Server`

```go
type Server struct {
    api.Unimplemented
    // ... existing fields ...
    listings *controllers.ListingsController  // ← new
}
```

### 2. Add the parameter to `NewServer`

```go
func NewServer(
    // ... existing params ...
    listings *controllers.ListingsController,   // ← new
) *Server {
    return &Server{
        // ... existing assignments ...
        listings: listings,                      // ← new
    }
}
```

### 3. Add delegation methods for each endpoint

After running `make generate`, the compiler tells you which methods are missing. Add one delegation method per operation:

```go
func (s *Server) CreateListing(w http.ResponseWriter, r *http.Request) {
    s.listings.CreateListing(w, r)
}

func (s *Server) GetListing(w http.ResponseWriter, r *http.Request, listingId string) {
    s.listings.GetListing(w, r, listingId)
}
```

### 4. Wire in container.go

In `NewContainer`, create the repository → service → controller chain and pass the controller to `NewServer`:

```go
// internal/app/container.go — inside NewContainer

// Listings feature
listingsRepo := db.NewListingRepository(fsClient)
listingsService := listing.NewService(listingsRepo, storageClient)
listingsController := controllers.NewListingsController(listingsService)

// Pass to server (update the NewServer call)
server := NewServer(
    healthController,
    profileController,
    aiController,
    matchesController,
    conversationsController,
    listingsController, // ← new
)
```

### 5. Add controller to Container struct (if needed for tests)

```go
type Container struct {
    // ...
    ListingsController *controllers.ListingsController
    // ...
}
```

Only expose the controller on `Container` if integration tests need direct access. Repositories and services remain local variables inside `NewContainer`.

## Full checklist for adding a new feature

| Step | File | Action |
|---|---|---|
| 1 | `pkg/api/openapi.yaml` | Add paths, schemas, operationIds |
| 2 | Terminal | `cd api && make generate` |
| 3 | `internal/core/domain/` | Add domain model structs (if new entity) |
| 4 | `internal/io/db/entities.go` | Add entity with `snake_case` storage tags |
| 5 | `internal/io/db/mappings.go` | Add `toDomain` / `toEntity` mapper functions |
| 6 | `internal/io/db/` | Add `NewXxxRepository(conn)` named constructor |
| 7 | `internal/core/services/<feature>/` | Create service with `Repository` interface, errors, business logic |
| 8 | `internal/app/controllers/` | Create controller with public/private method pattern |
| 9 | `internal/app/server.go` | Add field, constructor param, delegation methods |
| 10 | `internal/app/container.go` | Wire repo → service → controller → `NewServer(...)` |
| 11 | `internal/testenv/builders/` | Add test builder for the new entity |
| 12 | `internal/app/controllers/` | Write integration tests |
| 13 | Generated clients | Regenerate every client built from the spec (see go-openapi) |

## Worked examples

Worked route-delegation methods on the `Server` struct. Load it only when you need the concrete shape — the rules above are the contract.

[`references/examples.md`](references/examples.md)

## Scope boundaries

This file covers the `Server` struct, `NewServer` constructor, delegation methods, and the full wiring checklist for adding a new feature. It does **not** cover the controller pattern — see {{ skill_link("go-controller") }}. It does **not** cover DI principles — see {{ skill_link("go-di") }}.

