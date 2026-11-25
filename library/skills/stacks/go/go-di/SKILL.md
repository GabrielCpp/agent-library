---
name: go-di
description: "Go dependency injection by explicit container: NewContainer in container.go, wiring order, constructor injection, consumer-side interfaces. Load when wiring a dependency into container.go, adding a constructor, or placing an interface."
applyTo: 'api/internal/app/container.go,api/internal/app/**/*.go'
tags: [go, backend, standards]
---

# Go Backend — Dependency Injection

## The Container pattern

There is no DI framework. All wiring is explicit in `internal/app/container.go`. The `Container` struct holds every named dependency; `NewContainer` constructs and wires them in order.

```go
// internal/app/container.go
type Container struct {
    Settings *Settings
    Logger   *zap.Logger
    DB       db.Conn
    Storage  *storage.ObjectStorage
    Auth     auth.TokenVerifier

    // Controllers only — repos and services are local to NewContainer
    HealthController        *controllers.HealthController
    ProfileController       *controllers.ProfileController
    // ...
    Server *Server
}
```

Only controllers (and the composed `Server`) are exported on the struct. Repositories and services are local variables inside `NewContainer` — they are not stored on `Container`.

## Wiring a new feature

Follow this order inside `NewContainer`:

1. Create the repository: `fooRepo := db.NewFooRepository(conn)`
2. Create the service: `fooService := foo.NewService(fooRepo, ...)`
3. Create the controller: `fooController := controllers.NewFooController(fooService)`
4. Add the controller to the `Container` struct field list
5. Pass the controller to `NewServer(...)` so it satisfies `api.ServerInterface`

```go
// Step 1-3 inside NewContainer
fooRepo := db.NewFooRepository(fsClient)
fooService := foo.NewService(fooRepo)
fooController := controllers.NewFooController(fooService)

// Step 5 — pass to server
server := NewServer(..., fooController)

// Return includes step 4 field
return &Container{
    ...
    FooController: fooController,
    Server:        server,
}, nil
```

## Constructor injection

All dependencies are received via constructor. No `init()` side-effects, no package-level singletons, no `sync.Once` patterns outside of `NewContainer`.

```go
// Correct
func NewFooController(service FooService) *FooController {
    return &FooController{service: service}
}

// Wrong — do not do this
var globalFooService *foo.Service
func init() { globalFooService = foo.NewService(...) }
```

## Interface segregation

Define the service interface in the **consuming** package (the controller), not in the service package. This keeps the dependency direction correct (controller depends on the interface it needs, not on a concrete type exported from `core/`).

```go
// internal/app/controllers/profile.go
type ProfileService interface {
    GetProfile(ctx context.Context, userID string) (*domain.Profile, error)
    UpdateProfile(ctx context.Context, userID string, update domain.ProfileUpdate) (*domain.Profile, error)
}
```

**Never** import a concrete service type directly into a controller — always go through an interface.

## Test substitution

In integration tests, `NewContainer` is called for real (pointing at the local database the test stack starts). There is no override mechanism for production code. If a test needs a mock, it calls the controller directly with a mock service injected via the constructor — it does not swap out `Container` fields.

## Worked examples

A worked `container.go`, constructor wiring, and interface placement. Load it only when you need the concrete shape — the rules above are the contract.

[`references/examples.md`](references/examples.md)

## Scope boundaries

This file covers `container.go` wiring, constructor injection, and interface placement. It does **not** cover the HTTP layer — see {{ skill_link("go-architecture") }}. It does **not** cover repository construction — see {{ skill_link("go-repository") }}.

