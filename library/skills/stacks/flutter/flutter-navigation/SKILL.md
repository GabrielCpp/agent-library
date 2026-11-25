---
name: flutter-navigation
description: "Flutter navigation with go_router: AppRouter, GoRoute, StatefulShellRoute, context.go vs context.push, redirect. Load when adding or changing a route, editing app_router.dart, or debugging a redirect or missing bottom bar."
applyTo: 'app/lib/core/config/app_router.dart,app/lib/features/**/screens/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter App — Navigation

## Route constants

All route path strings are `static const String` on the `AppRouter` class. Never hardcode path strings anywhere else.

```dart
class AppRouter {
  static const String login          = '/login';
  static const String onboarding     = '/onboarding';
  static const String home           = '/';
  static const String assistant        = '/assistant';
  static const String conversations  = '/conversations';
  static const String conversationDetail = '/conversations/:id';
  static const String profile        = '/profile';
  static const String profileEdit    = '/profile/edit';
  static const String settings       = '/settings';
}
```

**Never** write path strings like `'/profile'` directly in a `context.go(...)` call — always use the `AppRouter` constant.

## Adding a new route

1. Add a `static const String` to `AppRouter`.
2. Add a `GoRoute` entry in `AppRouter.router` in `app_router.dart`.
3. Decide whether the route belongs inside or outside the `StatefulShellRoute` (see below).

## Shell vs. full-screen routes

The `StatefulShellRoute.indexedStack` wraps the three bottom-nav tabs (Assistant, Conversations, Profile). Routes that should show the bottom nav bar are declared as branches inside the shell. Routes that are full-screen (no bottom nav) are declared outside the shell, at the top level.

```dart
routes: [
  GoRoute(path: login, ...),          // full-screen — outside shell
  GoRoute(path: profileEdit, ...),    // full-screen — outside shell
  StatefulShellRoute.indexedStack(
    builder: (context, state, shell) => MainShell(navigationShell: shell),
    branches: [
      StatefulShellBranch(routes: [GoRoute(path: assistant, ...)]),
      StatefulShellBranch(routes: [GoRoute(path: conversations, ...)]),
      StatefulShellBranch(routes: [GoRoute(path: profile, ...)]),
    ],
  ),
]
```

**Never** add a route that needs the bottom nav bar outside the shell.
**Never** add a full-screen route inside a shell branch.

## Navigation calls

Use Go Router's `context.go(...)` for top-level navigation (replaces the current stack) and `context.push(...)` for pushing onto the current branch stack.

```dart
// Navigate to profile edit (full-screen push)
context.push(AppRouter.profileEdit);

// Navigate to a conversation detail (parameterised)
context.push('/conversations/$conversationId');

// Replace current route (e.g. after login)
context.go(AppRouter.assistant);
```

**Never** use `Navigator.push` or `Navigator.of(context).pushNamed` — always use Go Router.

## Global redirect

`AppRouter.router` has a global `redirect` callback that handles:
- Unauthenticated users → `/login`
- Authenticated users on `/login` → `/onboarding` (if not completed) or `/assistant`

Do not add per-screen auth guards (e.g. checking `FirebaseAuth.instance.currentUser` in a screen's `build`). The global redirect handles all auth gating.

The `decideRedirect` static helper extracts the redirect logic so it can be unit-tested without a real `GoRouter`.

## Session expiration

`AppRouter.init()` subscribes to `SessionManager.instance.onSessionExpired` and calls `router.go(AppRouter.login)`. Call `AppRouter.init()` once at app startup and `AppRouter.dispose()` when the app is torn down.

## Parameterised routes

For resource routes, use path parameters:

```dart
GoRoute(
  path: conversations,   // '/conversations'
  routes: [
    GoRoute(
      path: ':id',       // matches '/conversations/:id'
      builder: (context, state) {
        final id = state.pathParameters['id']!;
        return ConversationDetailScreen(conversationId: id);
      },
    ),
  ],
),
```

Declare the constant for the full path with the parameter token: `static const String conversationDetail = '/conversations/:id'`.

## Scope boundaries

This file covers route constants, adding routes, shell vs. full-screen placement, navigation calls, the global redirect, session expiration, and parameterised routes. It does **not** cover the `MainShell` bottom nav widget — see {{ skill_link("flutter-architecture") }}.

