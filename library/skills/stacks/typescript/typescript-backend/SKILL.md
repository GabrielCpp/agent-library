---
name: typescript-backend
description: "Entry point for TypeScript backends serving HTTP and GraphQL: app -> core -> io layers, DI container, repositories, schema and codegen, typed errors, ESM `.mts`. Load when starting any TypeScript backend task such as an endpoint or service."
applyTo: '{{ template.ts_backend_path | default("api") }}/src/**/*.ts,{{ template.ts_backend_path | default("api") }}/src/**/*.mts,{{ template.ts_backend_path | default("api") }}/src/**/*.tsx,{{ template.ts_backend_path | default("api") }}/package.json,{{ template.ts_backend_path | default("api") }}/vitest.config.*'
tags: [typescript, backend, standards, entrypoint]
---

# TypeScript Backend

Use this for TypeScript backends that expose HTTP and GraphQL APIs, keep business logic isolated from I/O, and generate typed API contracts.

## Stack Shape

- Backend root: `{{ template.ts_backend_path | default("api") }}`
- Source root: `{{ template.ts_backend_src_path | default((template.ts_backend_path | default("api")) ~ "/src") }}`
- App layer: `{{ template.ts_backend_app_path | default((template.ts_backend_path | default("api")) ~ "/src/app") }}`
- Core layer: `{{ template.ts_backend_core_path | default((template.ts_backend_path | default("api")) ~ "/src/core") }}`
- I/O layer: `{{ template.ts_backend_io_path | default((template.ts_backend_path | default("api")) ~ "/src/io") }}`
- GraphQL schemas: `{{ template.ts_backend_graphql_schema_path | default((template.ts_backend_path | default("api")) ~ "/src/app/schemas") }}`
- Generated GraphQL output: `{{ template.ts_backend_graphql_generated_path | default((template.ts_backend_path | default("api")) ~ "/src/app/graphql/generated.mts") }}`
- Codegen command: `{{ template.ts_backend_codegen_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun run generate") }}`

## Layer Rules

- Keep the dependency direction one-way: `app -> core -> io`.
- Put protocol concerns in the app layer: HTTP routes, GraphQL resolvers, auth wrappers, request parsing, response serialization, and controller registration.
- Put business rules in the core layer: domain models, domain services, typed errors, validation, policy decisions, and interfaces that describe required I/O.
- Put external systems in the I/O layer: database repositories, SDK clients, payment providers, storage providers, email providers, and other adapters.
- Do not import database SDKs, Fastify, GraphQL server types, or provider SDKs into core services or domain models.
- Do not put business decisions in controllers or repositories. Controllers translate transport details; repositories persist and retrieve data.

## Controllers And Routes

- Keep controllers thin. They should parse inputs, call services, and return transport-shaped responses.
- Register every new controller or resolver in the repository's controller index and application composition file.
- Prefer framework-native route registration and resolver registration helpers already present in the repo over ad hoc bootstrap code.
- Services should throw or return typed domain errors. Controllers should not swallow errors; let the shared error mapping layer translate them.
- Keep authorization declarative when the repo has decorators or route metadata. Use scope patterns already established by the backend, such as `resource:permission:$paramName`.

## Dependency Injection

- Wire dependencies in the central container module: `{{ template.ts_backend_container_path | default((template.ts_backend_path | default("api")) ~ "/src/app/modules.mts") }}`.
- Constructor parameters should describe interfaces where possible, not concrete provider implementations.
- Register new repositories, clients, services, controllers, clocks, loggers, and config readers once in the container.
- Use test-only container overrides in test helpers. Do not override production dependencies from feature code.
- Avoid process-wide singletons except for intentionally shared framework bootstrap objects already used by the repo.

## Data Access

- Access persistent storage through repository abstractions in the I/O layer.
- Keep storage entities separate from domain models when the persistence format differs from the business model.
- Put mapping code at the repository boundary or in dedicated mapper helpers.
- Do not query persistence directly from controllers or services when a repository pattern already exists.
- Keep collection/table names, indexes, and provider-specific options near the adapter, not scattered through core logic.

## GraphQL And Codegen

- Treat schema files under `{{ template.ts_backend_graphql_schema_path | default((template.ts_backend_path | default("api")) ~ "/src/app/schemas") }}` as the source of truth.
- Keep root schema files minimal. Domain schema files should extend `Query` and `Mutation` instead of redefining roots.
- Use one domain schema file per bounded area unless the repo already has a finer convention.
- Define enums and custom scalars once at the schema level; do not duplicate them in feature files.
- After schema or operation changes, run `{{ template.ts_backend_codegen_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun run generate") }}`.
- Never edit generated files, including `{{ template.ts_backend_graphql_generated_path | default((template.ts_backend_path | default("api")) ~ "/src/app/graphql/generated.mts") }}`.
- If frontend clients consume the schema, run their codegen commands too:
  - React Native: `{{ template.react_native_codegen_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm run generate") }}`
  - React Router web: `{{ template.react_router_codegen_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && CODEGEN_AUTH_TOKEN=<dev-token> npm run generate") }}`

## Settings, Logging, And Errors

- Read environment variables only through the repository's settings/config module, usually `{{ template.ts_backend_settings_path | default((template.ts_backend_path | default("api")) ~ "/src/settings.mts") }}`.
- Use required/optional helpers from that settings module; do not read `process.env` throughout the codebase.
- Use the injected logger abstraction. Do not use `console.*` in application code unless the repo explicitly reserves it for startup scripts.
- Log stable identifiers and outcome context, not secrets, tokens, raw PII, or whole request bodies.
- Throw typed application errors from the existing exception module. If the repo has names such as `ValidationError`, `ForbiddenError`, `ResourceMissing`, `ExternalApiError`, `QuotaExceededError`, or `InternalError`, reuse them instead of adding local throwaway error classes.

## TypeScript And Modules

- Follow the repo's module mode. For ESM `.mts` projects, source files should use `.mts` and imports should use `.mjs` specifiers.
- Do not change package module type, transpilation target, or test runner threading to make one feature easier.
- Prefer explicit return types at service and public boundary methods.
- Keep generated types at the boundary. Convert them to domain types before business logic when the generated shape does not match the domain.

## Tests

- Co-locate unit tests with the source file unless the repo has a dedicated cross-layer integration test area.
- Use the established test runner command: `{{ template.ts_backend_test_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun test") }}`.
- Integration tests should build the real app/test server through repository helpers, inject requests through the framework, and reset persistent repositories between cases.
- Use existing builders and fake clocks when they exist. Add or extend builders instead of duplicating raw object literals across tests.
- Keep the backend test runner single-threaded if the repo configured it that way for shared emulators or Datastore state.

## Verification

- For type and build checks, prefer the repo's scripts:
  - `{{ template.ts_backend_typecheck_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun run type:check") }}`
  - `{{ template.ts_backend_test_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun test") }}`
  - `{{ template.ts_backend_build_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun run build") }}`
- Run codegen before type checks whenever schemas, operations, generated contracts, or resolver signatures changed.

