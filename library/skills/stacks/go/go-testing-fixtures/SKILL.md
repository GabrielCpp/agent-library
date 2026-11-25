---
name: go-testing-fixtures
description: "Go shared test fixtures: internal/testenv, topic_test_helpers.go, BuildX builders with mergo, MustBuild, NewXHarness with t.Cleanup. Load when creating or reusing test data builders or harnesses shared across packages, or placing a helper."
applyTo: 'api/**/*_test_helpers.go,api/internal/testenv/**'
tags: [go, backend, tests]
---

# Go Backend — Test Fixtures & Harnesses

Shared test setup has two distinct jobs: **building data** (builders) and **wiring dependencies** (harnesses). Keep the two separate, and make both reusable from every package's tests rather than re-deriving them in each `_test.go`.

## Where fixtures live

Put shared fixtures and harnesses in **dedicated test-support packages** under `internal/testenv/` — for example `internal/testenv/builders` (data) and `internal/testenv/harness` (wiring) — in files named **`<topic>_test_helpers.go`** (e.g. `user_test_helpers.go`).

The filename ends in `_test_helpers.go`, **not** `_test.go`. That distinction is the whole point:

- A `*_test.go` file is compiled only while testing *its own* package, so its symbols are invisible to every other package. Fixtures placed there cannot be shared across modules or packages.
- A `*_test_helpers.go` file is an ordinary compiled source file. Its exported symbols (`BuildUser`, `NewServiceHarness`, …) are importable from **every** package's `_test.go` files. That is what makes one fixture usable everywhere.

Because these support packages are imported **only from test files**, Go's linker drops them from production binaries via dead-code elimination — so cross-package sharing costs nothing at runtime, and pulling in test-only dependencies like `mergo` never bloats the shipped binary.

Rules:

- **Never** put fixture/harness helpers in a production package's compiled files (e.g. a `service_test_helpers.go` sitting in `package services` next to production code). That ships test code and its dependencies into production and forces every importer to compile them. Keep them in `internal/testenv/...`.
- **Never** use `*_test.go` (including `test_helpers_test.go`) for fixtures that must be shared across packages — those are visible only to the single package under test. Reserve `*_test.go` helpers for genuinely package-private setup.
- It is expected and correct for these support packages to import `testing` from non-`_test.go` files (a harness takes `*testing.T`). That is safe precisely because the package is only ever imported by tests; a linter that flags `testing` imports outside `_test.go` should be suppressed for the `internal/testenv/...` packages.

## Builders — building data

Provide one exported `BuildX(in X) (X, error)` per entity. It returns a complete, valid, **happy-path** default, with any field set in `in` overriding the default. Tests then set only the fields the scenario cares about:

```go
user, err := BuildUser(User{Email: "duplicate@example.com"})
```

Implement the merge with [`dario.cat/mergo`](https://pkg.go.dev/dario.cat/mergo) (`go get dario.cat/mergo`; the older import path `github.com/imdario/mergo` is the same package):

```go
type User struct {
	ID        int
	Username  string
	Email     string
	Active    *bool  // pointer so nil means "not provided"
	Age       *int
	CreatedAt time.Time
	Tags      []string
}

// BuildUser returns a User with defaults merged with the partial 'in'.
// Fields set (non-nil or non-zero) in 'in' overwrite defaults.
func BuildUser(in User) (User, error) {
	defaultAge := 25
	defaultActive := true
	def := User{
		ID:        0,
		Username:  "testuser",
		Email:     "test@example.com",
		Active:    &defaultActive,
		Age:       &defaultAge,
		CreatedAt: time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		Tags:      []string{"trial"},
	}

	// mergo.WithOverride copies non-zero/non-nil fields from src ('in') over dst ('def').
	if err := mergo.Merge(&def, in, mergo.WithOverride); err != nil {
		return User{}, err
	}
	return def, nil
}
```

Conventions:

- **Optional fields use pointers** (`*bool`, `*int`, `*string`) so `nil` means "not provided" and is distinguishable from the zero value. `mergo.WithOverride` then copies non-nil/non-zero fields from `in` over the defaults; a `nil` pointer in `in` leaves the default intact.
- **Deterministic defaults only.** Use fixed timestamps and fixed IDs (`time.Date(2024, 1, 1, …)`, a constant UUID). Never call `time.Now()` / `uuid.New()` inside a builder — non-deterministic fixtures make tests flaky and un-diffable. When production must stamp a real time/ID, inject a fake generator instead (see "Mock generated values" in {{ skill_link("go-testing") }}).
- **No I/O.** Builders only assemble in-memory data — never a DB write, server start, env read, or network call. Persistence and request firing belong in the harness or the integration `callFunction(t, data)`.
- **Be explicit about slice/map semantics.** `mergo.WithOverride` replaces a slice only when the incoming slice is non-nil, so `nil` keeps the default `Tags` and a non-nil slice replaces it. Document the chosen behaviour where it matters.
- **Ergonomic must-wrapper.** The only failure is a malformed fixture (a programming error), so a `MustBuildX` wrapper that fails the test keeps call sites clean:

  ```go
  func MustBuildUser(t *testing.T, in User) User {
  	t.Helper()
  	u, err := BuildUser(in)
  	require.NoError(t, err)
  	return u
  }
  ```

A legacy fluent form (`AUser().WithEmail(...).Build()`) exists in some packages and remains acceptable, but new fixtures should use the `BuildX` merge form — less boilerplate and a single obvious override path.

## Harnesses — wiring dependencies

For dependency injection, provide a `NewXHarness(t *testing.T, …) (*X, deps…)` helper. It constructs the unit under test with its collaborators (mocks/fakes) preloaded, registers teardown with `t.Cleanup`, and returns the subject plus the handles the test needs to drive or inspect:

```go
// NewServiceHarness creates a Service backed by a fakeStore preloaded with users.
func NewServiceHarness(t *testing.T, preload []User) (*Service, *fakeStore) {
	t.Helper()
	fs := newFakeStore()
	for _, u := range preload {
		fs.users[u.ID] = u
	}
	svc := NewService(fs)
	t.Cleanup(func() {
		// teardown if needed (close connections, stop goroutines, …)
	})
	return svc, fs
}
```

Conventions:

- **Always take `t` and always register `t.Cleanup`**, even when teardown is currently empty — it gives cleanup a home and prevents leaks once the harness later acquires real resources.
- **Preload through builders**, not inline literals: `NewServiceHarness(t, []User{ MustBuildUser(t, User{ID: 1}) })`.
- **Use generated mocks for interface ports** (repositories, external seams) so the harness composes across packages — see the mockery rules in {{ skill_link("go-testing") }}. A small in-memory **fake** (like `fakeStore`) is right for a concrete, stateful collaborator where scripting per-call expectations would obscure the test.
- **Return the dependency handles** (the `*fakeStore`, the mocks) so a test can seed extra state or assert interactions without reaching into the subject's internals.
- A harness that must wire **package-private** types cannot live in a shared package; keep that one in its package's own test files. Prefer exported ports + generated mocks so the harness can live in `internal/testenv/harness` and be reused.

## Builders vs harnesses

Keep the two separate — builders produce **data**, harnesses wire **dependencies**. This mirrors the integration split in {{ skill_link("go-testing") }}: builder output feeds `buildData()` / `testData`, while a harness is the suite-setup step that constructs the subject and registers cleanup. A test reads cleanly when the data it varies and the wiring it shares are obviously distinct.

## Scope boundaries

This file covers where shared fixtures live, the `BuildX` merge-with-defaults builder convention, and the `NewXHarness` dependency-wiring convention. Test naming, the AAA `buildData`/`callFunction` structure, assertions, mock generation, and the integration three-part pattern are in {{ skill_link("go-testing") }}. Domain repository entity builders used for DB seeding are in {{ skill_link("go-repository") }}.

