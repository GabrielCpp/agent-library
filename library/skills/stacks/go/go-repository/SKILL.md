---
name: go-repository
description: "Go persistence: generic db.Repository, entities.go storage tags, named constructors, Criteria, Get, Set, Update, Filter, Transaction, schema evolution, test builders. Load when writing or changing a repository, entity, query or field."
applyTo: 'api/internal/io/db/**/*.go'
tags: [go, backend, standards]
---

# Go Backend — Repository & Persistence

This skill holds for any database. `Conn` below stands for the handle the project's driver
provides (a connection pool or a client). The project overlay names the engine and its driver.

## Generic Repository

All database access goes through `db.Repository[T, E]` in `internal/io/db/repository.go`. `T` is the domain type (from `internal/core/domain/`); `E` is the entity struct (from `internal/io/db/entities.go`).

```go
// internal/io/db/repository.go
type Repository[T any, E any] struct {
    conn     Conn
    table    string           // table, collection or key prefix
    toDomain ToDomain[T, E]   // func(id string, src *E) (T, error)
    toEntity ToEntity[T, E]   // func(obj T) (id string, entity *E, err error)
}
```

**Never** call the database driver directly from `internal/core/`. **Never** bypass `Repository` to write ad-hoc queries from a service.

## Entity structs

Entity structs live in `internal/io/db/entities.go`. They carry the storage tags the driver reads, in `snake_case`, and are the only types that touch the stored format. Domain types have no such tags. The examples use the `db` tag key. Use the key your driver reads.

```go
// internal/io/db/entities.go
type MatchEntity struct {
    UserIDs    []string  `db:"user_ids"`
    Status     string    `db:"status"`
    CreatedAt  time.Time `db:"created_at"`
    ArchivedAt time.Time `db:"archived_at,omitempty"`
}
```

**Never** put storage tags on domain types in `internal/core/domain/`.
**Never** put business fields directly on a domain type that belong to the persistence representation.

## Named constructors

Each domain entity has a named constructor that wraps `db.NewRepository` with its mapping functions and exposes the domain-shaped finders the service's port declares. The constructor is the only public surface for that repository.

```go
// internal/io/db/profile_repository.go
type ProfileRepository struct {
    *Repository[domain.Profile, ProfileEntity]
}

func NewProfileRepository(conn Conn) *ProfileRepository {
    return &ProfileRepository{NewRepository(conn, "profiles", profileToDomain, profileToEntity)}
}

func (r *ProfileRepository) FindByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    return r.FindOneBy(ctx, Where("user_id", userID))
}
```

**Never** call `db.NewRepository` directly from `container.go` or any other file. Always go through the named constructor.

## Criteria stay in the adapter

`Criteria` (built with `Where`, `OrderBy`, `Limit`) is the engine's own type in `internal/io/db`. The engine translates it into the driver's query. A named repository builds criteria inside a domain-shaped method such as `FindByUserID`. **Never** let `Criteria` or a driver query appear in an interface under `internal/core/`. See {{ skill_link("go-architecture") }} for port purity.

## Key operations

| Method | Use when |
|---|---|
| `Get(ctx, id)` | Fetch by ID; returns `db.ErrNotFound` if missing |
| `TryGet(ctx, id)` | Fetch by ID; returns `nil, nil` if missing |
| `Set(ctx, entity)` | Create or overwrite by ID |
| `Update(ctx, id, fields)` | Partial field update |
| `FindOneBy(ctx, criteria)` | First match of a query |
| `TryFindOneBy(ctx, criteria)` | First match or nil |
| `Filter(ctx, criteria, opts)` | Paginated query with cursor |
| `DeleteBy(ctx, criteria)` | Batch-delete matching records |
| `Transaction(ctx, fn)` | Atomic multi-record operation |

The engine maps the driver's own not-found error to `db.ErrNotFound`. Always check `errors.Is(err, db.ErrNotFound)` when handling not-found cases from `Get` and `FindOneBy`.

## Schema evolution

Records written before a change stay in the database. Adding a new field:
- Add it to the entity struct so a record without the field still reads, as the zero value. A schema-less store needs `omitempty` on the tag. A relational store needs a migration that adds the column with a default before the code that writes it ships.
- Add it to the domain type.
- Update `toDomain` and `toEntity`.
- **Never** delete or rename a stored field without confirming all existing records have been migrated.

## Test fixtures — Builder pattern

Integration tests must not write untyped maps or raw driver calls to the database. Use a typed builder instead.

Each domain entity that appears in tests has a builder in `internal/testenv/builders/`. Builders follow the fluent pattern: each `With*` method returns `*Self`, `Build()` returns the domain type, and there is a package-level factory function.

```go
// internal/testenv/builders/profile_builder.go
package builders

import (
    "time"
    "{{ template.go_module | default("github.com/yourorg/project/api") }}/internal/core/domain"
)

type ProfileBuilder struct {
    data domain.Profile
}

func AProfile() *ProfileBuilder {
    return &ProfileBuilder{
        data: domain.Profile{
            UserID:      "user-test-" + randSuffix(),
            DisplayName: "Test User",
            CreatedAt:   time.Now(),
            UpdatedAt:   time.Now(),
        },
    }
}

func (b *ProfileBuilder) WithUserID(id string) *ProfileBuilder {
    b.data.UserID = id
    return b
}

func (b *ProfileBuilder) WithDisplayName(name string) *ProfileBuilder {
    b.data.DisplayName = name
    return b
}

func (b *ProfileBuilder) WithPhotos(photos []domain.Photo) *ProfileBuilder {
    b.data.Photos = photos
    return b
}

func (b *ProfileBuilder) Build() domain.Profile {
    return b.data
}

func (b *ProfileBuilder) Clone() *ProfileBuilder {
    copy := *b
    return &copy
}
```

Persist a builder result via the repository in the test, not via raw driver writes:

```go
// in a test
profile := builders.AProfile().WithUserID("user-123").Build()
require.NoError(t, ts.Container.ProfileRepo.Set(ts.Context, profile))
```

**Never** write a record through the driver handle on the container (`ts.Container.DB`) in new tests.
**Never** build test data with a mix of raw maps and builders.

## Worked examples

A worked repository, entity struct, named constructors, and query operations. Load it only when you need the concrete shape — the rules above are the contract.

[`references/examples.md`](references/examples.md)

## Scope boundaries

This file covers the Repository generic, entity structs, named constructors, criteria, query operations, schema evolution, and the test builder convention. It does **not** cover wiring repositories into services — see {{ skill_link("go-di") }}. It does **not** cover one engine's data modeling, indexes or cost. The project overlay names the engine and points at its skill.
