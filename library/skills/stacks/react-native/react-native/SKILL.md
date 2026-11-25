---
name: react-native
description: "React Native TypeScript app entry point: Paper, generated GraphQL hooks, Apollo local state, i18n, Formik/Yup, typed navigation, codegen. Load when starting any task in a React Native app, before the matching sibling skill."
applyTo: '{{ template.react_native_path | default("app") }}/src/**/*.ts,{{ template.react_native_path | default("app") }}/src/**/*.tsx,{{ template.react_native_path | default("app") }}/App.tsx,{{ template.react_native_path | default("app") }}/package.json'
tags: [react-native, mobile, standards, entrypoint]
---

# React Native App

Use this as the root instruction for TypeScript React Native applications.

## Next-Level Instructions

- Architecture and service boundaries: {{ skill_link("react-native-architecture") }}
- GraphQL operations and generated hooks: {{ skill_link("react-native-graphql") }}
- Navigation: {{ skill_link("react-native-navigation") }}
- Styling and design system: {{ skill_link("react-native-styling") }}

## Stack Shape

- App root: `{{ template.react_native_path | default("app") }}`
- Source root: `{{ template.react_native_src_path | default((template.react_native_path | default("app")) ~ "/src") }}`
- Screen root: `{{ template.react_native_screens_path | default((template.react_native_path | default("app")) ~ "/src/app/screens") }}`
- Services root: `{{ template.react_native_services_path | default((template.react_native_path | default("app")) ~ "/src/services") }}`
- GraphQL root: `{{ template.react_native_graphql_path | default((template.react_native_path | default("app")) ~ "/src/graphql") }}`

## Core Rules

- Build UI with React Native and the repository's component system, commonly React Native Paper or a local design system.
- Keep screens, reusable components, hooks, services, and GraphQL operations in their established folders.
- Use typed generated GraphQL hooks. Do not call raw `fetch` or untyped Apollo hooks for API operations when generated hooks exist.
- Model services as classes or interfaces, create them in the app-level service builder, and consume them through the app service context/hook rather than importing mutable singletons into components.
- Use Apollo local state for app-wide client state. Keep component-only state local.
- Keep user-facing strings in the repository's i18n system.
- Use Formik/Yup or the repository's established form stack for non-trivial forms.
- Follow the repo's navigation registry and typed route parameter list.
- Run codegen after GraphQL operation changes: `{{ template.react_native_codegen_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm run generate") }}`.

## Verification

- Prefer the repository scripts:
  - `{{ template.react_native_typecheck_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm run typecheck") }}`
  - `{{ template.react_native_test_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm test") }}`
  - `{{ template.react_native_lint_command | default("cd " ~ (template.react_native_path | default("app")) ~ " && npm run lint") }}`
- If a script is absent, report that clearly and run the closest available package script.

