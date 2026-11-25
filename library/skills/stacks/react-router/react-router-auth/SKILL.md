---
name: react-router-auth
description: "React Router web auth: `useAuth()`, auth service, `ProtectedRoute`, `Layout`, public routes, sign-in flow. Load when adding a protected page, changing sign-in or auth context, debugging a login redirect loop, or placing public routes."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.tsx'
tags: [react-router, web, standards]
---

# React Router Auth

Use this for authenticated React Router routes, auth context changes, sign-in flows, and protected layout behavior.

## Auth Context

- Keep a single auth provider mounted near the root.
- Read auth state through `{{ template.react_router_auth_hook | default("useAuth()") }}` or the repository's equivalent.
- Do not duplicate Firebase/Auth0/custom-provider listeners inside route modules when the context already owns them.
- Keep auth service integration behind `{{ template.react_router_auth_service_name | default("AuthService") }}` or the repository's service abstraction.

## Protected Routes

- Wrap authenticated routes in the shared protected route component, commonly `{{ template.react_router_protected_route_component | default("ProtectedRoute") }}`.
- Wrap application pages in the shared layout component, commonly `{{ template.react_router_layout_component | default("Layout") }}`.
- Keep public routes such as login, callback, health, and error pages outside the protected app shell unless the repo says otherwise.
- Register new protected pages in `{{ template.react_router_routes_path | default((template.react_router_path | default("advisor-dashboard")) ~ "/app/routes.ts") }}` with the same guard pattern as existing protected pages.

## Sign-In Flow

- Preserve the repository's current sign-in provider and post-login verification query.
- After sign-in, navigate to the configured authenticated landing route, commonly `{{ template.react_router_authenticated_landing_path | default("/clients") }}`.
- Keep auth loading, failed login, missing user, and permission-denied states separate so users do not see a blank page.
- Do not store tokens in code, generated files, logs, or committed config.

## Data Access Under Auth

- Authenticated route components should wait for auth readiness before running user-scoped operations when the repo requires it.
- Use generated GraphQL hooks and service methods that already attach auth state.
- Do not manually attach auth headers in every component if the Apollo/service layer already does it.
- Keep redirects and permission decisions centralized in guards, layout, or auth service helpers.

