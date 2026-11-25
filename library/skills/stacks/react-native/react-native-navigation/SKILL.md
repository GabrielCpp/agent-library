---
name: react-native-navigation
description: "React Navigation in React Native: `RootParamList`, route params, tabs, drawer, app bars, navigation ref. Load when adding or renaming a screen or route, typing route params, changing tabs or drawer, or handling deep links and back behavior."
applyTo: '{{ template.react_native_path | default("app") }}/src/app/**/*.ts,{{ template.react_native_path | default("app") }}/src/app/**/*.tsx,{{ template.react_native_path | default("app") }}/src/**/*navigation*.ts,{{ template.react_native_path | default("app") }}/src/**/*navigation*.tsx,{{ template.react_native_path | default("app") }}/src/**/*routes*.ts,{{ template.react_native_path | default("app") }}/src/**/*routes*.tsx'
tags: [react-native, mobile, standards]
---

# React Native Navigation

Use this for React Navigation route definitions, screen registration, app bars, drawers, tabs, and service-driven navigation.

## Route Registry

- Register screens in the typed route parameter list, commonly `{{ template.react_native_routes_path | default((template.react_native_path | default("app")) ~ "/src/app/routes.tsx") }}`.
- Register screen configuration in the app shell, commonly `{{ template.react_native_screen_config_path | default((template.react_native_path | default("app")) ~ "/src/app/index.tsx") }}`.
- Export screens from the screen index when the repo has one.
- Keep route names stable and centralized. Do not build route names from strings in components.

## Typed Navigation

- Use the repository's `RootParamList` and typed navigation helpers.
- Pass route params through typed route definitions. Do not read arbitrary params from untyped objects.
- Use typed navigation props or `useNavigation<NavigationProp<RootParamList>>()` when the repo uses React Navigation directly.
- Keep tab param lists explicit, with `undefined` for routes that take no params.

## App Shell

- Respect existing safe-area wrappers, app bars, drawers, and tab containers.
- Put screen-level header or drawer content in the existing slot/configuration system.
- Do not add a second bottom-tab implementation if the app already owns tab behavior in its app shell.
- Use the existing navigation ref for service-triggered navigation, deep links, auth redirects, and notification flows.

## Flow Changes

- When adding a screen, update route types, screen exports, navigation config, and any auth/onboarding guard that controls access.
- Keep back behavior and empty route params intentional.
- Verify both direct route entry and in-app navigation paths when possible.

