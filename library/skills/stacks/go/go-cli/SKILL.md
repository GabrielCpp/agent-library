---
name: go-cli
description: "Go CLI structure under api/cmd/<name>: self-contained CLI dirs, shared api/go.mod, api/pkg imports, CLI-owned container, Makefile targets. Load when creating a CLI, deciding where CLI code or a shared helper lives, or what a CLI may import."
applyTo: 'api/cmd/**/*.go'
tags: [go, cli, standards, entrypoint]
---

# Go CLI — Architecture & Conventions

## Purpose

The CLI provides operator and developer tooling for the platform: data seeding, user management, migrations, moderation, and local development helpers.

Each CLI is **self-contained** inside its own `api/cmd/<name>/` subdirectory. It is part of the API Go module (`{{ template.go_module | default("github.com/yourorg/project/api") }}`) and may import from `api/pkg/` but **not** from `api/internal/` (convention — CLIs depend on the public contract only).

See {{ skill_link("go-cli-commands") }} for command authoring patterns, container setup, and testing.

---

## Repo layout — where CLIs live

CLIs live in `api/cmd/`, sharing the same `go.mod` as the HTTP server:

```
(repo root)
├── api/                         ← Go module: {{ template.go_module | default("github.com/yourorg/project/api") }}
│   ├── cmd/
│   │   ├── server/              ← HTTP API server (existing)
│   │   │   └── main.go
│   │   ├── {{ template.go_cli_name | default("appctl") }}/              ← operator/admin CLI
│   │   │   ├── main.go
│   │   │   ├── root.go
│   │   │   ├── config.go
│   │   │   ├── container.go
│   │   │   └── commands/
│   │   │       ├── profiles.go
│   │   │       ├── matches.go
│   │   │       ├── moderation.go
│   │   │       └── dev.go
│   │   └── <another-cli>/       ← future CLIs follow the same pattern
│   │
│   ├── pkg/                     ← PUBLIC — the only packages CLIs may import
│   │   ├── api/                 ← generated HTTP types
│   │   └── db/                  ← exported repo constructors (add when CLI needs the database)
│   │
│   └── internal/                ← PRIVATE by convention for CLI code
│
└── <client>/                    ← other apps in the repo (web, mobile), if any
```

**All files for one CLI live inside `api/cmd/<name>/`** — no code outside that directory belongs to it.
**Never** share a helper between two CLIs via `internal/` — promote it to `api/pkg/` instead.

---

## Module and dependency rules

- CLIs share `api/go.mod` — there is **no separate `go.mod`** per CLI.
- Add CLI-only dependencies (e.g. Cobra) to `api/go.mod`.
- **Only import from `api/pkg/`** — e.g. `{{ template.go_module | default("github.com/yourorg/project/api") }}/pkg/db`.
- **Do not import `api/internal/`** — the Go toolchain allows it (same module) but it violates the separation of concerns CLIs are meant to maintain.

---

## What belongs in `api/pkg/`

Add to `api/pkg/` only when a CLI needs it. The implementation stays in `api/internal/` — `api/pkg/` re-exports constructors only.

| Package | Contents | Add when |
|---|---|---|
| `api/pkg/api/` | Generated HTTP types, `ServerInterface` | Already exists |
| `api/pkg/db/` | Database connection + repository constructors | CLI needs direct database access |

Example re-export in `api/pkg/db/repositories.go`:

```go
package db

import (
    "context"

    internaldb "{{ template.go_module | default("github.com/yourorg/project/api") }}/internal/io/db"
)

type Conn = internaldb.Conn

func Connect(ctx context.Context, databaseURL string) (Conn, error) {
    return internaldb.Connect(ctx, databaseURL)
}

func NewProfileRepository(conn Conn) *internaldb.ProfileRepository {
    return internaldb.NewProfileRepository(conn)
}
```

**Never** copy internal code into a CLI — promote it to `api/pkg/` instead.
**Never** put business logic in `api/pkg/` — only constructors and generated types.

---

## CLI DI is independent from the main app

The main app's DI lives in `api/internal/app/container.go` and wires the full HTTP stack (controllers, services, repos, WebSocket). **CLIs have their own lean `container.go`** inside `api/cmd/<name>/` — no controllers, no HTTP, no WebSocket. Each CLI wires only what its commands need.

**Never** import or call the main app's container from a CLI.

---

## Directory layout of one CLI

Prefer folder organization when a CLI grows beyond a handful of commands. In Go, a folder is a package boundary, so do not move files into subdirectories casually just to make the tree look tidy. Choose one of these shapes deliberately:

Command-family package layout:

```
api/cmd/<cli-name>/
├── main.go
├── root.go
├── shared/
│   └── config.go
├── auth/
│   ├── auth.go
│   └── users.go
├── dev/
│   └── health.go
├── fixture/
│   └── fixture.go
└── smoke/
    ├── smoke.go
    └── helpers.go
```

For CLIs with several coherent command families, keep `main.go`, `root.go`, and top-level command composition directly under `api/cmd/<cli-name>/`. Put command families directly under `api/cmd/<cli-name>/<family>/`, for example `api/cmd/yin/auth/`, `api/cmd/yin/dev/`, `api/cmd/yin/fixture/`, and `api/cmd/yin/smoke/`. Use `api/cmd/<cli-name>/shared/` only for narrow shared CLI settings and helpers. Do not hide subcommands under an `internal/commands` bucket when the command family can be represented as a clear package.

Larger CLI:

```
api/cmd/{{ template.go_cli_name | default("appctl") }}/
├── main.go       ← entry point: newRootCmd + ExecuteContext
├── root.go       ← root cobra.Command, global flags, PersistentPreRunE
├── config.go     ← Settings struct + loadConfig()
├── container.go  ← CLI-specific DI (repos from api/pkg/db/ only)
└── commands/     ← one file per resource group, all package main
    ├── profiles.go
    ├── matches.go
    ├── moderation.go
    └── dev.go
```

When using subfolders, each subfolder is a real package. Keep shared CLI config and narrow interfaces in a small root package or a `shared`/`internal` package owned by the CLI. Do not create circular command dependencies. Do not use package globals to avoid designing the package boundary.

Within one folder, group command files by user-facing command family. Use names like `auth_command.go`, `auth_users_command.go`, `fixture_command.go`, `smoke_command.go`, `smoke_backend.go`, and `smoke_mobile.go`; avoid a single large `helpers.go` that mixes unrelated command behavior.

---

## Makefile

Add build targets to `api/Makefile`. Tests and lint already run `./...` so they cover `cmd/` automatically.

```makefile
# api/Makefile (additions)
build-{{ template.go_cli_name | default("appctl") }}:
    go build -o bin/{{ template.go_cli_name | default("appctl") }} ./cmd/{{ template.go_cli_name | default("appctl") }}
```

---

## LLM hygiene — run before finishing

Before writing or updating CLI tests under `api/cmd/**`, load and follow `{{ skill_path("go-testing") }}` in addition to the CLI instructions. CLI tests use the same Go test standard: explicit `TestIntegration_` or `Test_` category plus behavior naming, `require` only, no `assert`, and the `testData` / `buildData()` / `callFunction(t, data)` shape when command setup or repeated scenarios would otherwise make the test body large. Use a single suite such as `Test_APICallRequest_ShouldHandleRequestScenarios` when scenarios share command setup, and name each subtest `Should<ExpectedResult>[_When<AlternateScenario>]`.

```bash
cd api && make lint && make test
```

**Never** hand the task back while `make lint` or `make test` is failing.

