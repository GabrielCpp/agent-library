---
name: go-openapi
description: "Go OpenAPI contract and codegen: openapi.yaml, oapi-codegen v2, make generate, operationId and schema naming. Load when editing openapi.yaml, debugging make generate, or adding or renaming an operation, schema or parameter."
applyTo: 'api/pkg/api/openapi.yaml,api/pkg/api/*.gen.go,api/Makefile'
tags: [go, backend, codegen]
---

# Go Backend — OpenAPI Spec & Codegen

## Authoritative spec location

`api/pkg/api/openapi.yaml` is the single source of truth for all API routes, request shapes, and response shapes. Any copy elsewhere (e.g. `specs/`) is a historical document and must not be used as the working spec.

## Codegen workflow

After any change to `openapi.yaml`:

```bash
cd api && make generate
```

**Generator: `oapi-codegen` v2** (`github.com/oapi-codegen/oapi-codegen/v2`). The Makefile invokes it with **`go run`** (not the npm package) — e.g. `go run github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@v2.5.1`, with the version pinned in `api/Makefile` (so no global install is required). It regenerates two files from `openapi.yaml`:
- `-generate types` → `pkg/api/types.gen.go` — all request/response types.
- `-generate chi-server` → `pkg/api/server.gen.go` — the `ServerInterface` (a **chi**-router server) that `internal/app/server.go` must satisfy.

The generated code depends on the `github.com/oapi-codegen/runtime` package. Do not switch to a different OpenAPI generator or server flavor (keep `chi-server`) without coordinating the server composition in `internal/app/server.go`.

**Never** edit `pkg/api/types.gen.go`, `pkg/api/server.gen.go`, or any other `*.gen.go` file by hand.
**Always** commit the regenerated files together with the spec change.

## Adding a new endpoint

1. Add the operation to `api/pkg/api/openapi.yaml` with a `operationId`, request body schema, and response schema.
2. Run `make generate`.
3. Implement the new method on the `Server` struct in `internal/app/server.go` — the Go compiler will fail if the interface is not satisfied.
4. Create or extend the relevant controller in `internal/app/controllers/`.
5. Wire the controller in `internal/app/container.go` if it is new.

## Naming conventions in the spec

- `operationId` values are used by oapi-codegen to name the generated interface methods — use `PascalCase` verbs (`GetProfile`, `UpdateProfile`, `ConfirmPhotoUpload`).
- Response schema `$ref` names become generated Go type names — use `PascalCase` nouns (`Profile`, `Match`, `PhotoUploadUrlResponse`).
- Path parameters use `camelCase` (e.g. `photoId`, not `photo_id`).

## Client codegen

Any client generated from `api/pkg/api/openapi.yaml` (a web, mobile or service client) breaks when the spec does. A breaking change (removing a field, changing a type, renaming an operation) requires regenerating every such client. The project overlay names each client and its generate command. Coordinate spec changes with whoever owns each client.

**Never** remove or rename a field in the spec without updating every generated client in the same PR.

## Scope boundaries

This file covers the spec location, codegen workflow, adding endpoints, naming conventions, and client coordination. It does **not** cover how the generated types are consumed in controllers — see {{ skill_link("go-architecture") }}. It does **not** cover the client side of the API. The client stack's skill covers it.

