---
name: react-router
description: "Entry point for React Router framework-mode web apps with authenticated client-side data: route registry, generated GraphQL hooks, service context, Apollo, theme tokens, codegen. Load when starting any task in a React Router web app."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/react-router.config.*,{{ template.react_router_path | default("advisor-dashboard") }}/package.json'
tags: [react-router, web, standards, entrypoint]
---

# React Router Web App

Use this as the root instruction for TypeScript React Router web applications, especially framework-mode apps with authenticated client-side data.

## Next-Level Instructions

- Application architecture, routes, services, GraphQL, and styling: {{ skill_link("react-router-architecture") }}
- Component and screen tests in jsdom: {{ skill_link("react-router-testing") }}
- Authentication and protected routes: {{ skill_link("react-router-auth") }}
- SSR entry points and CSS-in-JS (MUI/Emotion) hydration setup: {{ skill_link("react-router-ssr") }}
- Accessibility — ARIA roles, accessible names, keyboard operability, focus management: {{ skill_link("react-router-a11y") }}

## Stack Shape

- Web root: `{{ template.react_router_path | default("advisor-dashboard") }}`
- App root: `{{ template.react_router_app_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app") }}`
- Route registry: `{{ template.react_router_routes_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/routes.ts") }}`
- Route modules: `{{ template.react_router_route_modules_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/routes") }}`
- Services root: `{{ template.react_router_services_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/services") }}`
- GraphQL generated output: `{{ template.react_router_graphql_generated_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/lib/generated/graphql.tsx") }}`

## Core Rules

- Register routes only in the route registry file.
- Keep route modules focused on one route. Route modules usually default-export the route component.
- Wrap authenticated pages in the repository's protected route and layout components.
- Use typed generated GraphQL hooks for API data.
- Model services as classes or interfaces, create them in the app-level service builder, and consume them through the app service context/hook rather than importing mutable singletons into components.
- Use Apollo local state for app-wide client state. Keep component-only state local.
- Use the established UI kit and theme, commonly MUI with `sx` and theme tokens. Stay faithful to the design system: every color, spacing, border, and radius is a theme token — never an inline hex or one-off pixel literal. If a token is missing, extend the central theme rather than hardcoding the value (see {{ skill_link("react-router-architecture") }} styling rules).
- Do not edit generated GraphQL files.
- Run web codegen after operation changes: `{{ template.react_router_codegen_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && CODEGEN_AUTH_TOKEN=<dev-token> npm run generate") }}`.

## Verification

- Prefer repository scripts:
  - `{{ template.react_router_typecheck_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && npm run typecheck") }}`
  - `{{ template.react_router_test_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && npm test") }}`
  - `{{ template.react_router_build_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && npm run build") }}`
- If a script is absent, report it and run the closest available package script.

