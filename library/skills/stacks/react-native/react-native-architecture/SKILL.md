---
name: react-native-architecture
description: "React Native app structure: screens, components, hooks, `buildServices()`, `useServices()`, Apollo local state, Formik/Yup, i18n. Load when adding a screen, component, hook or service, wiring bootstrap, or placing feature logic."
applyTo: '{{ template.react_native_path | default("app") }}/src/**/*.ts,{{ template.react_native_path | default("app") }}/src/**/*.tsx'
tags: [react-native, mobile, standards]
---

# React Native Architecture

Use this for React Native screens, components, hooks, services, app bootstrap, and feature structure.

## Folder Boundaries

- Screens live under `{{ template.react_native_screens_path | default((template.react_native_path | default("app")) ~ "/src/app/screens") }}`.
- Reusable components live under `{{ template.react_native_components_path | default((template.react_native_path | default("app")) ~ "/src/components") }}`, grouped by domain when the repo does that.
- Hooks live under `{{ template.react_native_hooks_path | default((template.react_native_path | default("app")) ~ "/src/hooks") }}` or the feature-local hook folder already used nearby.
- Services live under `{{ template.react_native_services_path | default((template.react_native_path | default("app")) ~ "/src/services") }}` and are exposed through the service provider.
- GraphQL operations live under `{{ template.react_native_graphql_path | default((template.react_native_path | default("app")) ~ "/src/graphql") }}`.

## Component And Screen Rules

- Keep route-level orchestration in screens and reusable behavior in components/hooks.
- Export new screens from the screen index if the repo uses one.
- When adding a component domain folder, add or update the domain barrel only if the repo already uses that pattern.
- Keep components named by responsibility. Avoid dumping unrelated feature logic into generic files such as `helpers.ts`.
- Use loading, empty, error, and success states that match existing screens. Do not invent a new app-wide state pattern for one feature.

## Services

- Model services as classes or interfaces. A service should expose behavior, not act as an untyped object bag.
- Add services to the app service builder/provider, commonly `buildServices()`.
- `buildServices()` should create the service graph in one place, wire constructor dependencies, run async initialization, and return the typed `Services` object.
- Components and hooks should consume services through `useServices()` or the local equivalent.
- Keep service constructors small and explicit. Inject dependencies such as Apollo clients, auth providers, loggers, storage, telemetry, and loaders.
- Use module singletons only for services the repo already treats as singleton platform boundaries, such as auth or logging.
- Keep telemetry and logging behind service abstractions. Do not scatter direct analytics calls across screens.

## Data Flow

- Use generated GraphQL hooks for server data.
- Use local React state for transient UI state.
- Use Apollo local state for app-wide client state.
- Define Apollo reactive variables, client-only fields, and field policies only in the repo's dedicated local state or Apollo setup module.
- Keep API and persistence details out of presentational components.
- Prefer small feature hooks when a screen coordinates multiple queries, mutations, and UI transitions.

## Forms And Text

- Use the repository's form stack, commonly Formik with Yup schemas.
- Keep validation schemas near the form screen or feature.
- Put user-visible text through i18n, usually via `useTranslation()`.
- Avoid hardcoded strings in components except stable technical IDs, test IDs, and non-user-visible constants.

