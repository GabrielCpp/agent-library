---
name: react-native-styling
description: "React Native styling: `StyleSheet.create`, `useStyles(theme)`, Paper `useTheme()`, design tokens, safe areas, keyboard overlap. Load when writing or reviewing screen layout, theme usage or styles, or replacing inline styles and hex colors."
applyTo: '{{ template.react_native_path | default("app") }}/src/**/*.ts,{{ template.react_native_path | default("app") }}/src/**/*.tsx'
tags: [react-native, mobile, standards]
---

# React Native Styling

Use this for React Native layout, theme usage, design tokens, and component styling.

## Styling Rules

- Use `StyleSheet.create` for styles.
- Avoid inline style object literals in JSX except tiny dynamic arrays that combine named styles with conditional values already defined in a stylesheet.
- Prefer theme-aware styles via a `useStyles(theme)` helper or the repository's established equivalent.
- Use static stylesheet constants only when a style never depends on theme, color mode, density, or responsive state.
- Do not introduce NativeWind, styled-components, Tamagui, or another styling framework unless the repo already uses it.

## Design System

- Use tokens from `{{ template.react_native_design_system_path | default((template.react_native_path | default("app")) ~ "/src/design-system.ts") }}` when present.
- Use the active theme, commonly from React Native Paper's `useTheme()`, for colors and typography.
- Prefer app component primitives over raw React Native primitives when an equivalent exists in the design system.
- Keep spacing, radius, typography, and elevation consistent with nearby screens.
- Do not hardcode one-off hex colors when a semantic theme color exists.

## Layout

- Build mobile-first layouts that handle small screens, keyboard overlap, loading states, long names, and translated strings.
- Use safe-area handling consistently with the app shell.
- Keep touch targets comfortable and use platform conventions for destructive actions, disabled states, and progress.
- Preserve scroll behavior for forms and dense content.

## Accessibility

- Add accessibility labels for icon-only buttons and controls where visible text is absent.
- Keep disabled states, loading states, and error states perceivable.
- Do not use color alone to communicate important status.

