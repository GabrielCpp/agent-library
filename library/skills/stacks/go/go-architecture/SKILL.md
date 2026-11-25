---
name: go-architecture
description: "Go backend layering (hexagonal): cmd, internal/app, internal/core, internal/io, pkg/api, port purity, domain types. Load when deciding which package code belongs in, reviewing a cross-layer import, or checking core for infra leaks."
applyTo: 'api/**/*.go'
tags: [go, backend, standards]
---

# Go Backend — Architecture & Conventions

This skill is the **Go mechanics** for the ports-and-adapters contract. Read
{{ skill_link("hexagonal-architecture") }}
first — it defines the invariants (dependency direction, domain purity, port purity, generic-engine-
vs-port, testability). This file says how each is spelled in Go; the *why* and the cross-language
rules live there.

## Layer boundaries

The backend maps the contract's three rings onto a strict four-layer clean architecture. Respect the
boundaries at all times:

- `cmd/server/` — entry point only; reads env, builds the container, starts the HTTP server.
- `internal/app/` — HTTP layer: controllers, auth middleware, exception handling. No business logic.
- `internal/core/` — Domain logic: services and domain types. No I/O.
- `internal/io/` — Infrastructure adapters: database repositories, object storage, external API clients.
- `pkg/api/` — oapi-codegen output: generated types and `ServerInterface`. Never edit by hand.

**Never** call the database driver or any `internal/io/` adapter directly from `internal/core/`.
**Never** put business logic in `internal/app/controllers/`.
**Never** import `internal/app/` from `internal/core/` or `internal/io/`.

## Controllers

Controllers are plain structs with one exported method per route. The exported method catches all errors and writes the response; a private method named with the same verb does the actual work and returns `error`.

```go
// internal/app/controllers/profile.go
type ProfileController struct {
    service ProfileService
}

func NewProfileController(service ProfileService) *ProfileController {
    return &ProfileController{service: service}
}

func (c *ProfileController) GetProfile(w http.ResponseWriter, r *http.Request) {
    if err := c.getProfile(w, r); err != nil {
        exceptions.WriteError(w, err)
    }
}

func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    userID := auth.UserIDFromContext(r.Context())
    profile, err := c.service.GetProfile(r.Context(), userID)
    if err != nil {
        return err
    }
    return writeJSON(w, http.StatusOK, profile)
}
```

**Never** call `exceptions.WriteError` from the inner private method.
**Never** place business logic (validation, rules, calculations) in a controller method.

## Route registration

Routes are registered exclusively via oapi-codegen. The `Server` struct in `internal/app/server.go` implements the generated `api.ServerInterface`. Adding a new endpoint means:

1. Add the operation to `pkg/api/openapi.yaml`
2. Run `make generate` to regenerate `pkg/api/server.gen.go`
3. Implement the new method on `Server` in `internal/app/server.go`

**Never** hand-register chi routes for API endpoints.
**Never** edit files inside `pkg/api/` directly.

## Services and domain types

Services live in `internal/core/services/<feature>/`. They depend on repository interfaces defined in the same package, not on concrete `internal/io/` types.

Domain types are pure Go structs in `internal/core/domain/`. They have no storage tags, no HTTP tags, and no external dependencies.

```go
// internal/core/services/profile/service.go
type ProfileRepository interface {
    Get(ctx context.Context, userID string) (*domain.Profile, error)
    Set(ctx context.Context, profile domain.Profile) error
}

type Service struct {
    repo    ProfileRepository
    storage StorageClient
}

func NewService(repo ProfileRepository, storage StorageClient) *Service {
    return &Service{repo: repo, storage: storage}
}
```

### Port purity — no infrastructure type in a core interface

This is obligation 3 of the contract, spelled in Go: a repository/port interface declared under
`internal/core/` must name **only** domain types and stdlib primitives in its method signatures. The
`internal/io/` adapter that implements it may import the database driver freely. The port may
not.

```go
// ✗ LEAK — the port names the driver's query type, so the core, its tests, and every
//   fake are now coupled to that database. A driver import in an internal/core file
//   is the tell.
type TodoRepository interface {
    Filter(ctx context.Context, q driver.Query) ([]domain.Todo, error)
    DeleteBy(ctx context.Context, q driver.Query) error
}

// ✓ CLEAN — criteria cross as domain vocabulary; the adapter turns ownerID into a
//   concrete driver query on its side of the boundary.
type TodoRepository interface {
    ListByOwner(ctx context.Context, ownerID string) ([]domain.Todo, error)
    DeleteByOwner(ctx context.Context, ownerID string) error
}
```

If a query is genuinely open-ended, pass a domain **specification** struct (a plain value describing
what to match), never a driver query or a function that builds one. The generic CRUD engine that backs the adapter
(`Repository[T, E]`) is fine and encouraged — bind it to the entity in a thin `internal/io/db`
constructor and expose it *as* the domain-shaped port above; the service depends on the port, never
on `Repository[T, E]` directly.

**Checkable form:** no driver, `http.`, or other `internal/io`/SDK symbol may appear in an
interface declared under `internal/core/`. Grep tell: a database driver or cloud SDK import (or
any `internal/io` import) in a file under `internal/core/`.

## Settings

All env vars are declared in `internal/app/settings.go` using `os.Getenv` (or a similar helper). Never read `os.Getenv` inside a service or controller.

## Worked examples

Worked domain model shapes for `internal/core/domain`. Load it only when you need the concrete shape — the rules above are the contract.

[`references/domain-examples.md`](references/domain-examples.md)

## Scope boundaries

This file covers layering, controller structure, route registration, services, domain types, and settings. It does **not** cover DI wiring — see {{ skill_link("go-di") }}. It does **not** cover error types — see {{ skill_link("go-errors") }}. It does **not** cover the repository pattern — see {{ skill_link("go-repository") }}.

