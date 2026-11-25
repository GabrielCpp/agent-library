---
name: react-native-graphql
description: "React Native GraphQL with Apollo: operations, fragments, generated hooks like `useSomeQuery`, cache updates, codegen. Load when adding or changing a query, mutation or fragment, replacing raw `useQuery`, or running codegen."
applyTo: '{{ template.react_native_path | default("app") }}/src/graphql/**/*.ts,{{ template.react_native_path | default("app") }}/src/graphql/**/*.tsx,{{ template.react_native_path | default("app") }}/src/**/*.ts,{{ template.react_native_path | default("app") }}/src/**/*.tsx'
tags: [react-native, mobile, standards, codegen]
---

# React Native GraphQL

Use this for GraphQL operations, fragments, Apollo usage, and generated types in React Native.

## Files

- Queries: `{{ template.react_native_queries_path | default((template.react_native_path | default("app")) ~ "/src/graphql/queries.ts") }}`
- Mutations: `{{ template.react_native_mutations_path | default((template.react_native_path | default("app")) ~ "/src/graphql/mutations.ts") }}`
- Fragments: `{{ template.react_native_fragments_path | default((template.react_native_path | default("app")) ~ "/src/graphql/fragments.ts") }}`
- Local state: `{{ template.react_native_local_state_path | default((template.react_native_path | default("app")) ~ "/src/graphql/local-state.ts") }}`
- Generated output: `{{ template.react_native_graphql_generated_path | default((template.react_native_path | default("app")) ~ "/src/graphql/generated/graphql.ts") }}`

## Operation Rules

- Define operations in the appropriate GraphQL source file. Do not inline `gql` documents inside screens.
- Keep fragments in the fragment file, then interpolate fragments into queries and mutations from there.
- Use generated typed hooks from the generated GraphQL output.
- Do not edit generated files.
- Run `{{ template.react_native_codegen_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm run generate") }}` after adding or changing operations.
- If the backend schema changed, run backend codegen first: `{{ template.ts_backend_codegen_command | default("cd " ~ (template.ts_backend_path | default("api")) ~ " && bun run generate") }}`.

## Apollo Usage

- Prefer generated hooks such as `useSomeQuery` and `useSomeMutation`.
- Do not use raw `useQuery`, `useMutation`, or `client.query` unless the repo has no generated hook for that operation and you are adding codegen in the same change.
- Keep cache updates close to the mutation or in existing cache helper modules.
- Use the repository's Apollo service/provider. Do not create a new client inside a screen.

## Local State

- Use Apollo local state as the app-wide client store.
- Put Apollo reactive variables, client-only fields, and field policies only in the dedicated local state or Apollo setup module.
- Use local component state for UI-only toggles, selections, and drafts that do not need cache visibility.
- Do not introduce Redux, Zustand, or another global store for new app state unless the repository already standardizes on it.
- Do not represent server truth in both React state and Apollo cache unless the screen is explicitly editing a draft.

