---
name: go
description: "Entry point for Go API work: core rules, decision trees, lint and test gate, map of sibling go skills (architecture, controllers, services, repositories, DI, errors, OpenAPI, storage, CLI, testing). Load first when starting any Go API task."
applyTo: 'api/**/*.go'
tags: [go, backend, standards, entrypoint]
---

# Go API — Core Principles

**Read this FIRST. Keep these rules in mind for EVERY task.**

---

## Next-Level Instructions

- Backend architecture and layer boundaries: {{ skill_link("go-architecture") }}
- Controller pattern: {{ skill_link("go-controller") }}
- Service pattern: {{ skill_link("go-service") }}
- Repository and persistence: {{ skill_link("go-repository") }}
- Dependency injection: {{ skill_link("go-di") }}
- Error handling: {{ skill_link("go-errors") }}
- Server composition: {{ skill_link("go-server") }}
- OpenAPI and generated contracts: {{ skill_link("go-openapi") }}
- Storage: {{ skill_link("go-storage") }}
- Go CLI: {{ skill_link("go-cli") }}
- Conversion snippets: [`references/conversion-snippets.md`](references/conversion-snippets.md)
- Testing: {{ skill_link("go-testing") }}
- Test fixtures & harnesses: {{ skill_link("go-testing-fixtures") }}

## Level-3 Subtopics And Examples

- CLI commands: {{ skill_link("go-cli-commands") }}

Worked examples ship inside the skill they illustrate, under its `references/`. Open the
skill for the surface you are touching and follow its examples link: domain shapes live in
`go-architecture`, REST contracts and controllers in `go-controller`, and the rest in
`go-service`, `go-repository`, `go-di`, `go-server`, and `go-testing`.

---

## Architecture Overview

```
HTTP Request → Controller → Service → Repository → Database
     ↓            ↓           ↓            ↓
  Routing    HTTP→Domain  Business    Domain→Entity
             Errors       Logic       Mapping
```

**Golden Rule**: Each layer has ONE job. Never skip layers or mix responsibilities.

---

## The 10 Commandments

### 1. OpenAPI is Source of Truth

- **Before writing code**: Update `pkg/api/openapi.yaml`
- **Generate types**: Run `make generate` (creates `types.gen.go`, `server.gen.go`)
- **Never edit**: `pkg/api/*.gen.go` files

### 2. Dependency Injection Only

- **All wiring**: Happens in `internal/app/container.go`
- **No globals**: No singletons, no package-level variables
- **Pattern**: `Infrastructure → Repository → Service → Controller → Server`

### 3. Layer Boundaries Are Sacred

| Layer              | Responsibility                       | Returns                       | Depends On            |
| ------------------ | ------------------------------------ | ----------------------------- | --------------------- |
| **Controller**     | HTTP concerns (parse, serialize)     | `error` (from exceptions pkg) | Service interfaces    |
| **Service**        | Business logic, validation           | Domain models, domain errors  | Repository interfaces |
| **Repository**     | Persistence CRUD only                | Domain models                 | Database driver       |
| **Infrastructure** | Generic I/O (storage, external APIs) | Generic types                 | External clients      |

**Never**:

- Controllers with business logic
- Services with HTTP status codes
- Repositories with business rules
- Infrastructure with domain knowledge

### 4. Domain Models Are Pure

- **Location**: `internal/core/domain/models.go`
- **Contents**: Plain Go structs, zero values (NOT pointers)
- **No dependencies**: No storage tags, no HTTP concerns
- **Conversion**: Controllers convert API types ↔ Domain types

### 5. Error Handling Pattern

**Services return domain errors**:

```go
var ErrNotFound = errors.New("profile not found")
return nil, ErrNotFound
```

**Controllers map to HTTP errors**:

```go
if errors.Is(err, profile.ErrNotFound) {
    return exceptions.NotFound("profile")
}
return exceptions.ErrInternal.Wrap(err)
```

**Exception types**: `ErrBadRequest`, `ErrUnauthorized`, `ErrForbidden`, `ErrNotFound`, `ErrConflict`, `ErrInternal`

### 6. Zero Values, Not Pointers

**Domain models**:

```go
type Profile struct {
    DisplayName string    // "" means empty
    Age         int       // 0 means not set
    CreatedAt   time.Time // time.Zero() means not set
}
```

**Check emptiness**: `name != ""`, `age > 0`, `!createdAt.IsZero()`

**OpenAPI**: Make fields optional (not in `required` array), NOT `nullable: true`

### 7. Server Uses Delegation, Not Embedding

```go
type Server struct {
    api.Unimplemented  // Provides 501 for unimplemented endpoints
    profile *controllers.ProfileController
}

// Explicit delegation (NOT embedding)
func (s *Server) GetProfile(w http.ResponseWriter, r *http.Request) {
    s.profile.GetProfile(w, r)
}
```

**Why**: Embedding causes "ambiguous selector" errors with `Unimplemented`.

### 8. Tests Are Co-Located

- **File naming**: `profile.go` → `profile_test.go` (same directory)
- **Integration tests**: `func TestIntegration_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>](t *testing.T)` for one server, emulator, HTTP, storage, or cross-layer behavior; use `TestIntegration_<ThingToTest>_ShouldHandle<ScenarioGroup>` when behavior-named subtests share setup
- **Unit/isolated tests**: `func Test_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>](t *testing.T)` for one fake, local helper, pure function, command helper, or in-memory behavior; use `Test_<ThingToTest>_ShouldHandle<ScenarioGroup>` when behavior-named subtests share setup
- **Shared fixtures & harnesses**: reusable test data and dependency wiring belong in `<topic>_test_helpers.go` files under shared support packages (e.g. `internal/testenv/...`), **not** `*_test.go` — `BuildX(in X) (X, error)` merge-with-defaults builders for data and `NewXHarness(t, …)` helpers for wiring. See {{ skill_link("go-testing-fixtures") }}
- **Never**: `func TestFunctionName(t *testing.T)` without either `TestIntegration_` or `Test_`
- **Never**: Separate `test/` or `tests/` directories
- **Before writing or updating Go tests**: load and follow `{{ skill_path("go-testing") }}`. Treat it as the canonical Go test instruction set, including explicit category plus `Should` behavior naming in either top-level tests or suite subtests, `require`-only assertions, the mandatory AAA `buildData`/`callFunction(t, data)` shape, mockery-generated mocks, and integration-test shape rules. For shared fixtures, builders, and DI harnesses, also load `{{ skill_path("go-testing-fixtures") }}`.

### 9. Context First, Logger Via DI

- **Services**: First param is always `context.Context`
- **Logging**: Inject `*zap.Logger` via constructor
- **No globals**: Pass logger through dependency injection

### 10. Persisted Field Naming

- **Entities**: Tag every field with the key your database driver reads, in `snake_case` (`db:"display_name"`)
- **Test data**: Match entity field names exactly (snake_case)
- **Tables and collections**: Lowercase names (`"profiles"`, not `"Profiles"`)

---

## File Organization Quick Map

```
api/
├── pkg/api/
│   ├── openapi.yaml          # SOURCE OF TRUTH (edit this)
│   ├── types.gen.go          # Generated (never edit)
│   └── server.gen.go         # Generated (never edit)
│
├── internal/app/             # HTTP layer
│   ├── container.go          # DI wiring (ALL dependencies here)
│   ├── server.go             # Composite server (delegates to controllers)
│   ├── controllers/          # HTTP handlers (thin, delegate to services)
│   ├── exceptions/           # HTTP error types
│   └── auth/                 # Auth middleware (verifies the identity provider token)
│
├── internal/core/            # Business logic
│   ├── domain/models.go      # Pure domain models
│   └── services/             # Business logic (services here)
│
└── internal/io/              # Infrastructure
    ├── db/                   # Repositories (database adapter)
    │   ├── repository.go     # Generic Repository[T, E]
    │   ├── entities.go       # Persisted entities
    │   └── mappings.go       # Domain ↔ Entity converters
    └── storage/              # Object storage and other external clients
```

---

## Decision Trees

### Adding a New Endpoint

```
1. Define in openapi.yaml
   └─→ Add path, operationId, request/response schemas
2. Run make generate
   └─→ Creates ServerInterface method signature
3. Implement controller method
   └─→ Parse request → Call service → Map errors → Return response
4. Create or update service
   └─→ Business logic, return domain models
5. Wire in container.go
   └─→ Add to DI container if new controller/service
6. Write integration test
   └─→ Use test template from Level 2
```

### Handling Errors

```
Service layer:
  └─→ Return domain error (errors.New("not found"))

Controller layer:
  └─→ Map domain error to HTTP error:
      if errors.Is(err, ErrNotFound) {
          return exceptions.NotFound("resource")
      }
      return exceptions.ErrInternal.Wrap(err)

Response:
  └─→ exceptions.WriteError(w, err)
```

### Working with Optional Fields

```
OpenAPI:
  └─→ Don't include in required array (NOT nullable: true)

Generated API type:
  └─→ Field becomes *string, *int, *time.Time

Convert to domain:
  └─→ if apiModel.Field != nil { domain.Field = *apiModel.Field }

Convert to API:
  └─→ if domain.Field != "" { apiModel.Field = &domain.Field }
```

---

## LLM hygiene — run before finishing

After every code change, run these commands and fix all failures before handing back to the user:

```bash
cd api && make lint && make test
```

- `make lint` → `golangci-lint run` — catches unused vars, missing error checks, import order.
- `make test` → `go test -timeout=30s ./...` — fails fast on the first broken test.

**Never** hand the task back while either command is failing.

## Validation Checklist (Run After Code Generation)

Before committing, verify:

- [ ] Updated `openapi.yaml` BEFORE writing code
- [ ] Ran `make generate` to update generated types
- [ ] Controller method signature matches `ServerInterface`
- [ ] Service accepts `context.Context` as first parameter
- [ ] Domain models use zero values (not pointers for scalars)
- [ ] Errors use `exceptions` package (not raw HTTP codes)
- [ ] Test file is co-located (`*_test.go` in same directory)
- [ ] Every Go test starts with either `TestIntegration_` or `Test_` and uses `<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]`, or uses `<ThingToTest>_ShouldHandle<ScenarioGroup>` with behavior-named subtests
- [ ] Any Go test changes follow `{{ skill_path("go-testing") }}` (AAA `buildData`/`callFunction` shape, mockery-generated mocks)
- [ ] Shared fixtures/harnesses follow `{{ skill_path("go-testing-fixtures") }}` (`<topic>_test_helpers.go`, `BuildX` merge builders, `NewXHarness`)
- [ ] Entity fields use `snake_case` storage tags
- [ ] All dependencies wired in `container.go`
- [ ] `make lint && make test` passes

---

## When to Reference Level 2/3

**Level 2 (Detailed Patterns)**: Reference when implementing:

- Repository pattern with generic Repository[T, E]
- Auth middleware and context extraction
- Test templates (integration, unit)
- Infrastructure layer (storage, external APIs)

**Level 3 (Surface-Specific Examples)**: Reference when:

- Building your first endpoint, but load only the relevant example files for the surfaces you are touching
- Stuck on error handling flow in a controller (`{{ skill_path("go-controller") }}`)
- Need to see working test patterns (`{{ skill_path("go-testing") }}`)
- Implementing complex business logic (`{{ skill_path("go-service") }}`)

---

## Common Pitfalls

❌ **Editing generated files** (`pkg/api/*.gen.go`)
✅ Update `openapi.yaml` and regenerate

❌ **Business logic in controllers**
✅ Controllers parse → delegate to service → serialize

❌ **Services returning HTTP status codes**
✅ Services return domain errors, controllers map to HTTP

❌ **Using pointers for optional fields in domain models**
✅ Use zero values (`""`, `0`, `time.Zero()`)

❌ **Embedding controllers in Server struct**
✅ Use explicit delegation methods

❌ **Tests in separate directories**
✅ Co-locate tests with source files

❌ **Writing Go tests from memory or generic Go habits**
✅ Load `{{ skill_path("go-testing") }}` first and follow its category plus `Should` behavior naming for top-level tests or suite subtests, `require`-only, context, and integration-test shape rules

❌ **Global loggers or singletons**
✅ Pass via dependency injection

---

**Next Steps**:

- For detailed implementation patterns
  - {{ skill_path("go-controller") }}
  - {{ skill_path("go-repository") }}
  - {{ skill_path("go-service") }}
  - {{ skill_path("go-testing") }}
  - {{ skill_path("go-testing-fixtures") }}
- For working code examples → Load the level-3 `.examples.md` file for the specific surface you are changing
- For specific questions → Ask which pattern to reference

