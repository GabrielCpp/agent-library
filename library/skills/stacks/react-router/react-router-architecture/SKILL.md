---
name: react-router-architecture
description: "React Router web app structure: route registry, components, hooks, `useServices()`, GraphQL operations, Apollo local state, MUI `sx` tokens, `useT()`. Load when adding or changing a route, component, hook, service or GraphQL operation."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.tsx'
tags: [react-router, web, standards]
---

# React Router Architecture

Use this for React Router routes, components, hooks, services, GraphQL operations, and styling.

## Routes

- Register routes in `{{ template.react_router_routes_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/routes.ts") }}`.
- Put route modules under `{{ template.react_router_route_modules_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/routes") }}`.
- Route modules should default-export their page component unless the repo uses a different React Router convention.
- Do not add loaders or actions just because React Router supports them. If the app currently fetches client-side through Apollo and auth context, keep that model unless the story explicitly changes the data strategy.
- If SSR is enabled, keep browser-only APIs behind effects, guards, or client-only services. With a CSS-in-JS UI kit, also set up the Emotion/MUI SSR cache so styles survive hydration — see {{ skill_link("react-router-ssr") }}.

## Components And Hooks

- Shared components live under `{{ template.react_router_components_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/components") }}`.
- Hooks live under `{{ template.react_router_hooks_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/hooks") }}` or feature-local hook folders.
- Components should use named exports. Route modules may use default exports.
- Do not add broad component barrels if the repo intentionally imports components directly.
- Keep page orchestration in route modules and reusable UI in components.
- Give every interactive element a real role and an accessible name, and manage focus
  deliberately on modal open/close, route change, and async completion — see
  {{ skill_link("react-router-a11y") }}.
- **No hardcoded user-facing strings.** Every label, placeholder, button text,
  helper text, default value, and message goes through the translation catalog
  (`useT()` / a message key) — never a literal string in JSX or component state.
  A "default" value a form opens with (e.g. a default project name) is a
  translation key, not a hardcoded word.
- **Default to client/local generation.** Unless a skill or contract says a value
  comes from the server, generate it **locally** in the component (e.g. a default
  name from the catalog, a random number, a generated id) rather than assuming the
  API supplies it. Do not add an API call for something the legacy app produced
  client-side.
- A translation hook (`useT`) must return a **referentially-stable** function —
  memoize it per-locale with `useCallback([locale])`. Components put `t` in
  `useEffect`/`useCallback` dependency arrays; a fresh function each render re-fires
  data-loading effects every render (stuck loading / re-render loops).
- Make the translator hook **provider-optional**: fall back to the default locale
  when there is no locale context, so a component renders bare in a unit test
  (which mounts it without the provider) instead of throwing. Keep the *locale
  switcher* hook (the one exposing `setLocale`) strict — it genuinely needs the
  provider. Keep catalog `en` values byte-identical to the original hardcoded
  strings so existing tests that assert English still pass.

## Services

- Services live under `{{ template.react_router_services_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/services") }}`.
- Model services as classes or interfaces. A service should expose behavior, not act as an untyped object bag.
- Create services through an app-level builder, commonly `buildServices()`, and export a typed `Services` interface.
- The service builder should create the service graph in one place, wire constructor dependencies, and return the typed `Services` object consumed by the provider.
- Consume services through `useServices()` or the repository's service context.
- Keep service constructors explicit and testable.
- Use module singletons only for services the repo already treats as singleton platform boundaries, such as auth or logging.
- Do not import mutable service instances directly into route modules or components.

## GraphQL

- Put queries and mutations in the app GraphQL source files, commonly:
  - `{{ template.react_router_queries_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/lib/queries.ts") }}`
  - `{{ template.react_router_mutations_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/lib/mutations.ts") }}`
- Use generated typed Apollo hooks from `{{ template.react_router_graphql_generated_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/lib/generated/graphql.tsx") }}`.
- Do not inline raw `gql` documents inside route components when the repo has operation files.
- Run `{{ template.react_router_codegen_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && CODEGEN_AUTH_TOKEN=<dev-token> npm run generate") }}` after operation or schema changes.
- Do not commit real auth tokens used for codegen.

## Apollo Local State

- Use Apollo local state as the app-wide client store.
- Keep reactive variables, client-only fields, and field policies in a dedicated local state or Apollo setup module, commonly `{{ template.react_router_local_state_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/lib/local-state.ts") }}` or `{{ template.react_router_apollo_service_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/services/apollo.service.ts") }}`.
- Keep component-only state in React component state or feature hooks.
- Do not introduce Redux, Zustand, or another global store for new app state unless the repository already standardizes on it.
- Do not represent server truth in both React state and Apollo cache unless the route is explicitly editing a draft.

## Styling

- Use the repository UI kit, commonly MUI.
- **Stay faithful to the design system — never inline a magic value.** Color,
  spacing, radius, shadow, border, and typography all come from the **central
  theme** (the app's `createTheme`, commonly in `root.tsx` or a dedicated theme
  module) and are referenced as tokens in `sx`/`styled`. A reviewer reading a
  component must see token references (`bgcolor: "background.paper"`,
  `borderColor: "neutral.border"`, `p: 2`, `borderRadius: 1`,
  `color: "text.secondary"`), **never** a raw literal like `bgcolor: "#f8f8f8"`,
  `border: "1px solid #e7e7e7"`, or `py: "10px"`. Inline hex, rgb/rgba, and
  one-off pixel strings for any property the theme governs are a defect, not a
  shortcut — they fork the design system one component at a time.
- **If the token you need does not exist yet, create it — extend the theme, don't
  inline.** When the design system has no token for a value (a new neutral
  surface, a border grey, a spacing step, a custom palette role), **add it to the
  central theme** and reference the new token. For custom palette keys, use MUI
  module augmentation (the repo's theme-augmentation `.d.ts`, e.g. the existing
  `neutral`/`footer` palette groups) so the token is typed. Adding one shared
  token is the correct fix; scattering the same literal across components is not.
  The only acceptable inline literal is a genuinely one-off, non-reusable value,
  and it must carry a short comment saying why it isn't a token.
- **Spacing goes through the theme scale, not pixel strings.** Use the numeric
  spacing API (`p`, `py`, `px`, `m`, `gap`, `rowGap` taking theme units like `1`,
  `2`, `2.5`) so spacing stays on the 8px grid; reserve raw `"10px"`-style strings
  for the rare value the scale genuinely can't express, with a comment.
- **Borders, dividers, and radii are tokens too.** Use `divider`/palette tokens
  (`borderColor: "divider"`) or a `<Divider>` rather than `"1px solid #e7e7e7"`,
  and `borderRadius`/`theme.shape` rather than a hardcoded pixel radius.
- When a story asks you to match a legacy/reference design, capture each value as
  a **named theme token traced to its source** (as the existing palette tokens
  are annotated to their legacy origin) instead of transcribing the hex/px inline
  into the component. Faithfulness to the design means faithfulness to the
  design *system*.
- Do not introduce Tailwind or another styling framework unless the app already uses it for that surface.
- **No central theme yet, or one components keep bypassing?** Don't keep adding
  inline literals — stand up (or consolidate) the design system first. See
  {{ skill_link("react-router-design-system") }}
  for what a design system is in MUI terms (the `createTheme` structure, typed
  custom palette keys via module augmentation, central component overrides).
- Keep route-level layouts scan-friendly and compatible with long translated strings.
- **Responsive by default — mobile-first.** Every route must be usable from narrow
  phone widths up through wide desktop. Drive layout with MUI responsive primitives,
  not fixed widths: `sx` breakpoint objects (`{ xs, sm, md }`), `Stack`/`Grid` with
  responsive `direction`/`spacing`/`columns`, and `theme.breakpoints` (or
  `useMediaQuery`) for branching. Never assume a desktop viewport; the page must not
  overflow or force horizontal scroll on small screens, and tap targets/controls must
  stay reachable on touch. Verify the layout at a phone width, not just full-screen.
- **Center page content in a constrained column.** Do not let content stretch
  edge-to-edge on wide displays. Wrap each route's content in a horizontally centered,
  max-width container — MUI `Container` (with `maxWidth`), or a `Box` with
  `mx: "auto"`, a `maxWidth`, and responsive horizontal padding — so it reads as a
  centered column with comfortable gutters on large screens while still filling narrow
  ones. For short, empty, error, or auth/form pages, also center vertically: a
  full-height flex wrapper (`minHeight: "100dvh"`, `display: "flex"`,
  `alignItems`/`justifyContent: "center"`) so the card/content sits in the middle of
  the viewport rather than pinned to the top-left.
- With SSR + a CSS-in-JS kit (MUI/Emotion), styles must be injected into `<head>` via a shared cache or they are dropped on document hydration and the app renders unstyled — see {{ skill_link("react-router-ssr") }}.

## Data States

- Use the app's established loading, error, and empty components.
- Preserve the three-state shape for authenticated data routes: loading, error/permission problem, and data.
- Keep redirect and auth-loading logic in shared route guards rather than duplicating it in every page.

