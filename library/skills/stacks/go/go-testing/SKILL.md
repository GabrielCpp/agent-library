---
name: go-testing
description: "Go backend test rules: Test_ and TestIntegration_ naming, testify require, t.Context, injected clock, mockery mocks, AAA integration shape. Load when writing, reviewing or refactoring a _test.go file, a mock, or a failing Go test."
applyTo: 'api/**/*_test.go'
tags: [go, backend, tests]
---

# Go Backend — Testing

## Test runner and file placement

Use the standard `go test ./...` runner (no external framework). Test files are co-located with the package they test and use the `_test` package suffix (e.g. `controllers_test`).

```
internal/app/controllers/profile.go
internal/app/controllers/profile_test.go   ← same directory, package controllers_test
```

**Never** place test files in a separate `tests/` directory.

## Assertion library

Use `testify/require` for all Go test assertions.

Do not use `testify/assert` in Go tests. `require.*` fails immediately, keeps later assertions from running against invalid state, and keeps setup, preconditions, and result checks consistent.

```go
require.NoError(t, err)                    // stops the test if setup fails
require.Equal(t, http.StatusOK, resp.StatusCode)
require.Equal(t, "Alice Johnson", profile.DisplayName)
require.NotEmpty(t, profile.Id)
```

**Never** import `github.com/stretchr/testify/assert` in new or modified tests.
**Never** call `t.Fatal`, `t.Fatalf`, `t.FailNow`, `t.Error`, or `t.Errorf` in new or modified tests. Use `require.*` for both assertions and explicit failures.
**Never** use bare `if err != nil { t.Fatal(...) }` — use `require.NoError`.

```go
require.Failf(t, "unexpected request path", "path=%s", r.URL.Path)
require.NoError(t, err)
require.True(t, called, "expected callback to be called")
```

Prefer comparing whole expected values when practical:

```go
expected := domain.Profile{
    ID:          actual.ID,
    UserID:      "user-123",
    DisplayName: "Alice Johnson",
    CreatedAt:   actual.CreatedAt,
    UpdatedAt:   actual.UpdatedAt,
}
require.Equal(t, expected, actual)
```

## Test naming

Every Go test must declare its category through its top-level function name. It must also make behavior visible either in the top-level function name or, for a cohesive suite, in each subtest name.

- Use `func TestIntegration_<ThingToTest>_Should<ExpectedResult>(t *testing.T)` for tests that start the app server, exercise HTTP handlers end-to-end, use local stand-ins for the database, auth or object storage, or verify multiple production layers together.
- Use `func Test_<ThingToTest>_Should<ExpectedResult>(t *testing.T)` for isolated tests that use fakes, local `httptest` dependency boundaries, command helpers, pure functions, in-memory objects, or mocked collaborators.
- Add `_When<AlternateScenario>` when the expected result depends on a specific non-happy-path condition.
- Do not use plain `func TestBehavior(t *testing.T)`. If the test is not an integration test, keep the underscore after `Test_` so reviewers and agents can quickly tell it is isolated.

For a single-scenario top-level test, the behavior portion must have this shape:

```text
<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]
```

For a multi-scenario suite that shares setup, use a top-level suite name with `ShouldHandle<ScenarioGroup>` and put the concrete behavior in each subtest:

```text
Test_<ThingToTest>_ShouldHandle<ScenarioGroup>
TestIntegration_<ThingToTest>_ShouldHandle<ScenarioGroup>
```

Each subtest in the suite must then use:

```text
Should<ExpectedResult>[_When<AlternateScenario>]
```

This suite shape is mandatory, not optional, when tests in the same file repeat the same setup pattern for the same user-facing surface. Do not keep separate top-level tests merely because they call different endpoints, methods, command actions, or service methods if they share the same server setup, authenticated user setup, fixture shape, fake dependency setup, command runner, or cleanup flow.

Use one top-level `ShouldHandle<ScenarioGroup>` suite for a coherent feature or resource surface, then put each endpoint/action/mode in a behavior-named subtest. For example, a controller test file for one feature should prefer `TestIntegration_Assistant_ShouldHandleConversationAndSuggestionScenarios` over separate top-level tests for `GetAIConversation`, `SendAIMessage`, and `RespondToSuggestion` when they all start the same test server, use the same test user, and mutate only request path, request body, or fixture data.

Keep separate top-level tests only when the setup is genuinely different enough that sharing it would obscure the behavior under test, such as different external services, different containers, different fixture families, different command runners, or unrelated resources in the same package.

Keep each segment short, concrete, and user/operator-observable where possible. Prefer `Test_APICallRequest_ShouldHideTokenByDefault_WhenTextOutput` over `Test_APICallRequestTextOutputHidesTokenByDefault`.

Examples:

```go
func TestIntegration_GetProfile_ShouldReturnProfile_WhenProfileExists(t *testing.T) {
    // Full HTTP/server/emulator flow.
}

func Test_ParseProfileResponse_ShouldReturnProfileID(t *testing.T) {
    // Isolated parser behavior.
}

func Test_APICallRequest_ShouldHandleRequestScenarios(t *testing.T) {
    t.Run("ShouldReturnJSONResult_WhenRequestSucceeds", func(t *testing.T) {
        // Shared command setup lives in the parent test.
    })

    t.Run("ShouldRejectRemoteBackend_WhenOptInMissing", func(t *testing.T) {
        // Scenario-specific mutation and assertions live here.
    })
}
```

## Test contexts

Use `t.Context()` for contexts created by tests.

Do not use `context.Background()` in test code, test helpers, or code-under-test calls made from tests. `t.Context()` is cancelled when the test ends, which prevents leaked emulator calls, HTTP requests, goroutines, and repository operations from continuing after failure or timeout.

```go
ctx := t.Context()
profile, err := service.GetByUserID(ctx, "user-1")
require.NoError(t, err)
```

For bounded waits, derive from the test context:

```go
waitCtx, cancel := context.WithTimeout(t.Context(), 2*time.Second)
defer cancel()
require.NoError(t, waitForServer(waitCtx, settings))
```

Two cases legitimately use `context.Background()` in a `_test.go` file. Document the reason in both:

1. **Inside `t.Cleanup`** — `t.Context()` is already cancelled by the time cleanup runs, so teardown (deleting seeded rows, closing connections) must use `context.Background()` or it fails with a cancelled-context error.
2. When the test is explicitly verifying behavior with a background context.

```go
t.Cleanup(func() {
    // context.Background() is required: t.Context() is already cancelled when cleanup runs.
    _, _ = baseRepo.Execute(context.Background(), "DELETE FROM user WHERE id = ?", fix.BinID)
})
```

## Mocking generated values

Mock generated values through dependency injection. Time, UUIDs, random strings, temporary names, and similar runtime-generated values should each come from a small service dependency so tests can replace them with deterministic fakes.

Do not add package-level variables such as `var now = time.Now` or `var newID = uuid.NewString`, monkey-patch helpers, sleep until wall-clock time changes, or assert exact values produced by live generators such as `time.Now()` or `uuid.New()`.

A test never calls `time.Sleep` to wait for work. Wait on a channel, a `sync.WaitGroup` or `require.Eventually` with a deadline of 30 seconds or more. A server is ready once its listener is bound, so call `net.Listen` first and hand the listener to `Serve`.

When production behavior depends on the current time, define and inject a narrow clock dependency at the same layer as the behavior:

```go
type Clock interface {
    Now() time.Time
}

type realClock struct{}

func (realClock) Now() time.Time {
    return time.Now()
}
```

When production behavior creates IDs, define and inject a narrow ID generator dependency:

```go
type IDGenerator interface {
    NewID() string
}

type uuidGenerator struct{}

func (uuidGenerator) NewID() string {
    return uuid.NewString()
}
```

The app container or CLI container wires the real clock and real ID generator in production. Tests override those DI dependencies with deterministic fakes:

```go
type fakeClock struct {
    now time.Time
}

func (c fakeClock) Now() time.Time {
    return c.now
}

type fakeIDs struct {
    next string
}

func (g fakeIDs) NewID() string {
    return g.next
}

func Test_CreateMessage_ShouldUseInjectedGenerators(t *testing.T) {
    fixedNow := time.Date(2026, time.May, 6, 12, 0, 0, 0, time.UTC)
    service := messages.NewService(repo, fakeClock{now: fixedNow}, fakeIDs{next: "message-1"})

    message, err := service.Create(t.Context(), input)
    require.NoError(t, err)
    require.Equal(t, "message-1", message.ID)
    require.Equal(t, fixedNow, message.CreatedAt)
}
```

Keep generators separated by purpose when that makes tests simpler. A clock should produce time. An ID generator should produce IDs. Avoid broad “test utilities” objects that mix unrelated generated values.

For integration tests, override generated-value services through the test server/container setup instead of mutating global state. If the existing setup helper cannot override a dependency, add a small test-only option or constructor path that builds the container with fake generators, then keep production wiring on real generators.

For CLI tests, pass fake generated-value services through the command runner, command constructor, or CLI container. Avoid hidden package state because CLI tests often run multiple commands in the same process.

Use fixed timestamps and fixed IDs in `buildData()` for fixture data. Use injected fake generators in `callFunction(t, data)` for behavior that should stamp the current time or create a new value.

## Test fixtures

Shared test data **builders** and dependency **harnesses** are covered in full in {{ skill_link("go-testing-fixtures") }}. In short:

- Put fixtures that are shared across packages in a dedicated test-support package (e.g. `internal/testenv/builders`) in `<topic>_test_helpers.go` files — regular `.go`, **not** `_test.go` — so every package's tests can import them. Reserve `*_test.go` helpers for genuinely package-private setup.
- Build entities with a merge-with-defaults `BuildX(in X) (X, error)` helper that returns complete happy-path data; tests override only the fields a scenario cares about. Builders perform no I/O and use deterministic defaults (fixed timestamps/IDs).
- Wire the unit under test with a `NewXHarness(t, …)` helper that preloads fakes/mocks and registers `t.Cleanup`.

Feed builder output into the integration `buildData()` / `testData`, and use the harness as the suite-setup step that constructs the subject. Builders produce **data**; harnesses wire **dependencies** — keep them separate, mirroring the `buildData` vs `callFunction` split above.

## Mocks

When a test needs to stand in for a collaborator behind an **interface** —
a repository, another service, or an external seam (billing, auth, user
lookup) — use a **`mockery`-generated mock**. Do not hand-write fakes, stubs,
or function-field doubles for interfaces.

### Generating

Mocks are declared in `.mockery.yaml` at the module root and regenerated with `make generate-mocks`. The generated files are committed. Use **mockery v3** with the `testify` template, which generates the typed `EXPECT()` API by default. The config, the Makefile target and the v2 migration note are in [references/mockery-setup.md](references/mockery-setup.md). Open it when adding the first mock to a module or when `mockery` fails to parse the module.

Run `make generate-mocks` after **adding or changing any mocked interface**, and
commit the regenerated files. A stale or hand-edited mock is a bug — never edit
a generated file.

### Using

Construct the mock with `t` so expectations are asserted automatically on
cleanup, then set typed expectations with the `EXPECT()` API:

```go
import "{{ template.go_module | default("github.com/yourorg/project/api") }}/internal/core/services/mocks"

func Test_ProfileService_GetByUserID_ShouldReturnProfile_WhenProfileExists(t *testing.T) {
    logger := zaptest.NewLogger(t)
    repo := mocks.NewMockProfileRepository(t) // passing t auto-asserts on cleanup

    repo.EXPECT().
        GetProfile(mock.Anything, "user-1").
        Return(domain.Profile{ID: "123", UserID: "user-1"}, nil).
        Once()

    service := NewProfileService(repo, logger)
    got, err := service.GetByUserID(t.Context(), "user-1")

    require.NoError(t, err)
    require.Equal(t, "123", got.ID)
}
```

- Pass `t` to the constructor (`mocks.NewMockProfileRepository(t)`) — never call
  `AssertExpectations` by hand; the constructor registers it.
- Use `mock.Anything` only for arguments the test does not care about (typically
  `ctx`). Assert concrete values for arguments the behavior depends on.
- Use `.Once()` / `.Times(n)` to pin call counts when the count is part of the
  behavior under test (e.g. "does not call the repo when validation fails").
- Use `.RunAndReturn(func(...) ...)` when a return value must derive from the
  arguments; prefer plain `.Return(...)` otherwise.

### Rules

- **Never** hand-write a mock, fake, or stub for an interface — generate it.
  Replace existing hand-rolled `fakeXxx` / `MockXxx` doubles with the generated
  mock when you touch their tests.
- **Never** edit a generated mock file by hand — change the interface (or
  `.mockery.yaml`) and rerun `make generate-mocks`.
- Generated mocks live in a dedicated `mocks` package, never interleaved with
  production code; don't import a `mocks` package from non-test code.
- A small **in-memory fake** is still acceptable for a *concrete* collaborator
  that is not an interface, or when emulating real stateful behavior across many
  calls is clearer than scripting per-call expectations. Mocks are the default;
  reach for a fake only when expectation-scripting would obscure the test.

## Integration test structure

Integration tests use either `TestIntegration_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]` for one scenario or `TestIntegration_<ThingToTest>_ShouldHandle<ScenarioGroup>` for a shared-setup suite.

### The AAA shape is mandatory

Any integration test with more than one scenario — or any non-trivial arrange — **must** be expressed with the three-part Arrange-Act-Assert shape below. This is not a stylistic preference: agents and reviewers rely on it to see at a glance what is shared setup, what varies per scenario, and where behavior is asserted. A suite has exactly three named pieces plus thin subtests:

1. **Suite setup** (top of the test function) — wire the *real* dependencies once: open the datastore connection or start the emulator-backed server, build the HTTP handler, seed any always-present fixtures, and register teardown with `t.Cleanup`. This is the **only** place dependencies are constructed. A helper such as `setupTestServer(t)` may own this when the stack provides one.
2. **`testData` + `buildData()`** — a single `testData` struct holds *everything that varies per scenario*: HTTP method, path, request body, the acting user, the auth token, seed records, and the expected status/response. `buildData()` takes no parameters and returns a complete, happy-path `testData`. Use package fixtures from `test_helpers_test.go` and domain builders from `internal/testenv/builders/`.
3. **`callFunction(t, data)`** — the **one and only** function that performs Arrange (isolate + seed for this scenario) and Act (build and send the request *entirely from `data`*). It returns the response/result and contains no behavior assertions beyond `require.NoError` on arrange failures.

Each subtest is then four steps of intent and nothing else:

```go
t.Run("Should...", func(t *testing.T) {
    data := buildData()           // 1. start from the happy path
    data.email = otherUserEmail   // 2. mutate ONLY what this scenario changes
    rr := callFunction(t, data)   // 3. act
    require.Equal(t, http.StatusConflict, rr.Code) // 4. assert behavior
})
```

### Banned anti-patterns

These all defeat the AAA shape. They are exactly the deviations to refactor away when you touch an integration test:

- ❌ **Per-action call helpers** such as `callGetMe(t, token)` / `callRecordLoginEvent(t, token)`. Use ONE `callFunction(t, data)` and encode the action (method, path, body) as fields of `testData`. Multiple call helpers hide the act step and force literals at every call site.
- ❌ **Constructing handlers, servers, verifiers, or seeding rows inside a subtest** (e.g. building a second `ghostHandler` or calling a `makeUser(...)` helper from within `t.Run`). All wiring lives in suite setup; all per-scenario state flows through `data` and `callFunction`.
- ❌ **Passing scalar literals** (a bare token or email) to a call helper instead of a `testData` value.
- ❌ **Asserting behavior inside `callFunction`**. `callFunction` only arranges and acts; subtests assert.
- ❌ **A scenario that needs a different accepted token/identity rebuilding the whole handler.** Make the accepted token + identity part of suite setup and let `callFunction` send `data.authToken`; a wrong token then naturally exercises the 401 path with no new handler.

If a file has multiple `TestIntegration_` functions and each one creates the same setup, similar `testData`, similar `buildData()`, and similar `callFunction(t, data)`, refactor them into one `TestIntegration_<Feature>_ShouldHandle<ScenarioGroup>` function. The single suite owns the shared setup; subtests mutate `data` to choose the path, method, body, seeded records, expected status, and response assertions.

### Examples

Two full suites, one against an emulator-backed server with a real `http.Client` and one handler-level with `httptest`, are in [references/integration-examples.md](references/integration-examples.md). Open it when writing the first suite in a package or refactoring per-action helpers into one `callFunction`.

**Always** isolate state at the start of `callFunction` — clear the collection or delete/seed the relevant rows so each scenario starts clean. Test isolation is manual.

## Isolated test structure

Isolated tests use either `Test_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]` for one scenario or `Test_<ThingToTest>_ShouldHandle<ScenarioGroup>` for a shared-setup suite. They do not need the full integration-test shape when a smaller arrange/act/assert flow is clearer.

Use the `testData` / `buildData()` / `callFunction(t, data)` shape for isolated tests only when the test has repeated setup, multiple scenarios that mutate happy-path data, command execution setup, or dependency-boundary setup that would otherwise make the test body large.

Small isolated tests may stay direct:

```go
func Test_ParseProfileResponse_ShouldReturnProfileID(t *testing.T) {
    profile, err := parseProfileResponse([]byte(`{"id":"profile-1"}`))
    require.NoError(t, err)
    require.Equal(t, "profile-1", profile.ID)
}
```

## Authentication in tests

Use the internal auth token format to bypass the identity provider's token verification:

```go
req.Header.Set("Authorization", "Bearer internal-token-"+userID)
```

The auth middleware in `internal/app/auth/middleware.go` recognises this prefix and extracts the user ID directly. **Never** use a real identity-provider token in tests.

## Subtests

Prefer `t.Run("Should<ExpectedResult>[_When<AlternateScenario>]", func(t *testing.T) { ... })` subtests over separate top-level functions for variations of the same endpoint, command, service, or repository behavior. If scenarios share `testData`, `buildData()`, `callFunction(t, data)`, fake servers, fixture data, or command wiring, make one suite-style top-level test and keep each concrete behavior in a `Should...` subtest.

## Comments

Avoid low-value comments that narrate the obvious, such as "set up data", "call function", or "verify result". Use comments only when they explain a non-obvious test constraint, emulator behavior, fixture invariant, or production/debug boundary.

## Local test database

Integration tests run against a local instance of the project's database: an emulator or a container the dev stack starts. `setupTestServer` calls `requireDBConnected(t, container.DB)` early to fail fast with a clear message if it is not running.

Start it before running tests with the command the project overlay names.

## Commands

```bash
# Run all tests (30-second timeout)
cd api && make test          # → go test -timeout=30s ./...

# Run a single package
cd api && go test -timeout=30s ./internal/app/controllers/...

# Run lint (requires golangci-lint)
cd api && make lint          # → golangci-lint run
```

## LLM hygiene — run before finishing

After every code change to the Go API, run these two commands in order and fix any failures before considering the task complete:

```bash
cd api && make lint && make test
```

- `make lint` catches unused variables, missing error checks, import order, shadowed variables.
- `make test` fails fast on the first broken test (30-second timeout).

**Never** hand the task back to the user while `make lint` or `make test` is failing.

## Worked examples

Worked unit and integration tests, fixtures, and mock setup. Load it only when you need the concrete shape — the rules above are the contract.

[`references/examples.md`](references/examples.md)

## Scope boundaries

This file covers test file placement, assertions, package-local fixtures, mock generation, the integration test three-part pattern, authentication bypass, the local test database requirement, and the lint/test commands an LLM must run after changes. Repository entity builders are covered in {{ skill_link("go-repository") }}.

