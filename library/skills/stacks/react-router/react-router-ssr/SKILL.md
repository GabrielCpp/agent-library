---
name: react-router-ssr
description: "React Router SSR and Emotion hydration for MUI: `ssr: false` SPA mode, HydrateFallback, Emotion cache. Load when the app renders unstyled, hydration errors #418 or #423 appear, styles flash, or `entry.client.tsx`, `entry.server.tsx` change."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/entry.*.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/app/root.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/react-router.config.*,{{ template.react_router_path | default("advisor-dashboard") }}/server.*,{{ template.react_router_path | default("advisor-dashboard") }}/Dockerfile*,{{ template.react_router_path | default("advisor-dashboard") }}/package.json'
tags: [react-router, web, standards]
---

# React Router SSR & CSS-in-JS Styling

Use this when a framework-mode React Router app uses a CSS-in-JS UI kit
(MUI/Emotion, styled-components). It covers the entry points, the document, the
**recommended SPA-mode setup** that sidesteps a whole class of hydration bugs, and
— if you must keep SSR — the Emotion critical-CSS setup. See
{{ skill_link("react-router-architecture") }} for general styling rules.

## Recommended: SPA mode + a hydration gate (read first)

Framework-mode React Router hydrates the **whole document** (`hydrateRoot(document, …)`).
That makes startup fragile in two compounding ways:

1. **CSS-in-JS mutates `<head>` during hydration.** MUI's CssBaseline `<Global>`
   re-inserts its `mui-global` styles client-side (Emotion's auto-adoption only
   matches `data-emotion^="<key> "`, never `"<key>-global "`), mutating `<head>`
   mid-hydrate.
2. **Browser extensions mutate `<html>`/`<head>`/`<body>`** before hydration.

Either trips React into **#418/#423**, and the recovery (client re-render of the
root) intermittently drops styles → an unstyled flash. The tell-tale: it is
**intermittent and only in real browsers** — headless Chrome (no extensions)
never reproduces it, and `localhost` is often clean while the deployed domain is
flaky. No Emotion tweak fully fixes it because the extension is out of your control.

The robust fix is to **stop hydrating anything non-trivial**:

1. **`react-router.config.ts`: `ssr: false`** (SPA). Routes render fresh on the
   client; only a prebuilt shell is hydrated.
2. **Export `HydrateFallback` from `root.tsx`** — this is the React-Router-native
   lever, and the only one that actually works. RR renders it (and prerenders it
   into `index.html`) during the initial hydration while route modules/clientLoaders
   resolve, so the hydrated tree is the static shell ONLY — no providers, no
   Emotion, no route `<Meta>`/`<Links>`. There is nothing to mismatch, so hydration
   cannot throw #418/#423; the real app mounts afterward, client-side.
   ```tsx
   // Returns null: the loading overlay lives in Layout and covers the screen.
   export function HydrateFallback() { return null; }
   export default function App() { return (<ThemeProvider …><CssBaseline /><Outlet /></ThemeProvider>); }
   ```
   A hand-rolled `useState(mounted)` gate that returns `null` from the default route
   export does **not** work: RR still renders the route tree (and its head tags)
   during hydration, so the mismatch — and #418 — remain. RR even logs a console
   hint pointing you to `HydrateFallback`; heed it.
3. **Branded loading overlay** in `root.tsx`'s `Layout` (plain React-owned CSS in
   `<head>` so it paints instantly; logo + animated bar), hidden via
   `html.app-ready .loader{opacity:0;visibility:hidden}`. Reveal it from an effect
   in `App` (which mounts only after hydration) — but **not** the instant it mounts:
   the active route's stylesheets (e.g. a marketing page's plain-CSS `<link>`s) load
   async, so wait for every `link[rel="stylesheet"]` to finish (`link.sheet != null`,
   plus `load`/`error` listeners) before adding `app-ready`, with a ~3s fallback.
   Revealing too early flashes an unstyled page even though hydration is clean.
   A **one-shot** check at mount is not enough: RR injects the matched route's
   `links` *after* the effect runs, so on fast loads the scan finds zero pending
   sheets, reveals, and then the route CSS arrives — an unstyled flash. Gate on a
   short **quiet period** instead: re-arm a ~120 ms settle timer whenever a
   `link[rel="stylesheet"]` finishes loading **or** a `<head>` `MutationObserver`
   sees a new stylesheet injected; reveal only once it stays quiet, with the
   hard-timeout fallback as the backstop. Also `await document.fonts.ready` before
   the final reveal: MUI/Emotion rules apply synchronously, but a late web font they
   reference repaints a momentarily mis-styled page even when no `<link>` is pending.
4. **Static server.** With `ssr: false` there is no server build; the Node server
   serves `build/client` (immutable `assets/`, the rest static) and falls back to
   `index.html` for client routes — while keeping any auth reverse-proxy and CORS.
   Point `npm start` and the container CMD at `./build/client`, never the removed
   `build/server` output. **The catch-all must not silently
   404 a misrouted `/api/*`:** that path is supposed to hit the backend via the
   Hosting rewrite (step 5), so if it reaches this static server the rewrite
   misfired — return an explicit `502` naming the rewrite, not the generic 404 the
   SPA fallback emits for non-GET (a bare `{"error":"Not Found"}` on a `POST /api/…`
   reads as an application bug and sends you debugging the wrong layer).
5. **Reach the backend same-origin — at the edge, not in the Node server.** Set the
   client's API base URL to a relative `/api` and route it to the backend with a
   **Firebase Hosting Cloud Run rewrite** (`{ "source": "/api/**", "run": { … } }`
   ordered *before* the `**` catch-all that serves the SPA). Same-origin means no
   CORS and the backend URL never reaches the browser, and it keeps the Node server
   a dumb static server — do **not** add a reverse proxy to it for this. **Gotcha:**
   a Hosting Cloud Run rewrite forwards the path **verbatim** — the `/api` prefix is
   **not** stripped — so the backend must strip a leading `/api` itself, as the
   outermost middleware (before routing/auth/CORS), and still serve its bare contract
   paths for direct callers. Mirror the rewrite in dev with a Vite `server.proxy`.
   The rewrite **forwards request headers, including `Authorization`** — do not
   assume Hosting strips the bearer. If the backend logs "missing Authorization
   header" on same-origin traffic, prove which side drops it before blaming Hosting:
   send a bogus `Authorization: Bearer x` through the Hosting `/api` path and read
   the backend log — `token verification failed` means the header arrived (look at
   the client), `missing` means it was dropped en route.

### Emotion cache in SPA mode — plain browser cache, never `compat`

MUI still needs a `CacheProvider` wrapping `HydratedRouter` in `entry.client.tsx`,
backed by a **plain** browser cache anchored at the `<head>` insertion-point meta:

```ts
// app/emotion/createEmotionCache.ts
import createCache, { type EmotionCache } from "@emotion/cache";
export const EMOTION_INSERTION_POINT = "emotion-insertion-point";
export function createEmotionCache(): EmotionCache {
  let insertionPoint: HTMLElement | undefined;
  if (typeof document !== "undefined") {
    insertionPoint =
      document.querySelector<HTMLElement>(`meta[name="${EMOTION_INSERTION_POINT}"]`) ?? undefined;
  }
  return createCache({ key: "mui", insertionPoint });
}
```

**Never set `cache.compat = true` on the client.** `compat` is Emotion's
SSR/extraction flag — it exists so `createEmotionServer` (or an inline SSR
`<style>`) can own the serialized rules instead of Emotion committing them to a
`<head>` stylesheet itself. With `ssr: false` there is no SSR HTML for routes, so
compat buys nothing here; and on the browser it is a non-standard mode that
interacts badly with the `hydrateRoot(document)` recovery path. It was implicated
in an intermittent, **real-browser-only** failure where a page renders with the
right MUI class names but **no CSS, and never recovers until a full reload**.
Beware the verification trap: headless Chrome (clean hydration, no extensions)
does **not** reproduce it, and a happy-path render styles fine *with or without*
compat — so a compat change must be confirmed in a real browser with extensions
across many reloads/navigations, never by a headless check alone. Setting compat
on the client is the single most likely cause if MUI components carry their
`Mui*`/`mui-*` classes but compute to browser-default styles.

### Production recovery: stale assets and missing Emotion rules

`Cache-Control: no-store` on `index.html` is necessary but not sufficient. It
prevents a new navigation from reusing an old shell; it cannot update an already
open tab or a document restored from the back-forward cache. After a deployment,
such a document can request a content-hashed JS/CSS asset that the new release no
longer contains. Also, a rare browser-side Emotion failure can leave correct MUI
class names with no committed rules. Both failures appear transient because a
manual reload fetches the current shell and remounts Emotion.

Build automatic, loop-safe recovery into every SPA-mode CSS-in-JS installation:

1. **Centralize one guarded reload helper** (for example,
   `app/lib/staleBundleRecovery.ts`). Store the last attempt in `sessionStorage`
   and allow at most one reload per ~60 seconds. If storage is unavailable, do
   not perform an unguarded reload. Reuse this helper for dynamic-import errors,
   stylesheet resource errors, and missing Emotion rules.
   ```ts
   const RELOAD_KEY = "app:stale-bundle-reload-at";
   const RELOAD_COOLDOWN_MS = 60_000;

   export function reloadForStaleBundle(): void {
     try {
       const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? "0");
       if (Date.now() - last < RELOAD_COOLDOWN_MS) return;
       sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
     } catch {
       return; // Never risk a reload loop when storage is blocked.
     }
     window.location.reload();
   }
   ```
2. **Catch failed stylesheet resources in capture phase.** Resource `error`
   events do not bubble and usually have no useful `event.error`/`event.message`,
   so a normal window error handler misses them. Install this before hydration in
   `entry.client.tsx`; restrict reloads to same-origin stylesheets so an optional
   third-party font outage does not reload the app.
   ```ts
   window.addEventListener("error", (event) => {
     const target = event.target;
     if (
       target instanceof HTMLLinkElement &&
       target.rel === "stylesheet" &&
       new URL(target.href, location.href).origin === location.origin
     ) {
       reloadForStaleBundle();
     }
   }, true);
   ```
3. **Do not reveal the app until Emotion has rules.** Immediately before adding
   the loader's `app-ready` class, require at least one cache-owned style sheet
   with a CSSOM rule. `CssBaseline` plus the mounted MUI route should always
   produce one. If none exists, call the guarded reload helper instead of exposing
   a permanently browser-default page.
   ```ts
   const emotionHasRules = Array.from(
     document.querySelectorAll<HTMLStyleElement>('style[data-emotion^="mui"]')
   ).some((style) => {
     try {
       return (style.sheet?.cssRules.length ?? 0) > 0;
     } catch {
       return true; // Cross-origin CSSOM access means the sheet exists.
     }
   });
   if (!emotionHasRules) {
     reloadForStaleBundle();
     return;
   }
   document.documentElement.classList.add("app-ready");
   ```
   Match the selector prefix to the Emotion cache key if it is not `mui`.
4. **Make missing hashed CSS an actual failure.** A missing `/assets/*.css`
   request must return `404`/`410` with `Cache-Control: no-store`. Never return
   `200` with an empty stylesheet: the browser reports it as loaded, the loader
   reveals an unstyled page, and no recovery handler runs. A missing hashed JS
   module may return a tiny reload module using the same cooldown key, or a real
   error that the dynamic-import handler converts into the guarded reload.

Keep immutable caching for content-hashed assets. Disabling that cache does not
solve release consistency and sacrifices the reason hashes exist; the correct
boundary is a `no-store` shell plus immutable assets plus stale-set recovery.

Result, verified across 20+ reloads in a real browser with extensions: **zero
hydration errors and zero unstyled flashes** on every route. Cost: routes are not
server-rendered (the overlay covers first paint); prerender specific routes if you
need their HTML for SEO.

## If you must keep SSR (`ssr: true`)

The rest of this file covers CSS-in-JS with SSR. Only choose it when SSR/SEO is a
hard requirement; otherwise prefer SPA mode above — it is materially more robust.

## The hydration-drops-styles failure (read first)

Framework-mode React Router hydrates the **whole document** with `hydrateRoot(document, …)`.
By default Emotion (and other CSS-in-JS runtimes) inject their `<style>` tags into
`<body>` next to each styled element during SSR. Those tags are **not part of the
React tree**, so on hydration React reconciles them away — the first paint looks
styled, then the page goes **unstyled once JS loads**. It is not a missing-CSS or a
build problem; the SSR HTML looks correct, so verify by where the styles live, not
whether they exist.

Symptom signature: server HTML contains `<style data-emotion=…>` tags, but they sit
**after `</head>`** (in `<body>`), and there are no custom `app/entry.*.tsx` files.

## The fix: shared cache + inject critical CSS into `<head>`

Provide custom entry points and a single Emotion cache shared by server and client,
keyed identically so generated class names match across SSR and hydration. Insert
client-side styles at a stable `<head>` insertion point so React never owns or drops them.

1. **Shared cache factory** (`app/emotion/createEmotionCache.ts`) — one `key` (e.g.
   `"mui"`) for both sides; on the client, anchor inserts to a `<head>` meta:
   ```ts
   import createCache from "@emotion/cache";
   export const EMOTION_INSERTION_POINT = "emotion-insertion-point";
   export function createEmotionCache() {
     let insertionPoint: HTMLElement | undefined;
     if (typeof document !== "undefined") {
       insertionPoint =
         document.querySelector<HTMLElement>(`meta[name="${EMOTION_INSERTION_POINT}"]`) ?? undefined;
     }
     return createCache({ key: "mui", insertionPoint });
   }
   ```
2. **Client entry** (`app/entry.client.tsx`) — wrap `HydratedRouter` in the cache provider:
   ```tsx
   import { CacheProvider } from "@emotion/react";
   import { startTransition, StrictMode } from "react";
   import { hydrateRoot } from "react-dom/client";
   import { HydratedRouter } from "react-router/dom";
   import { createEmotionCache } from "./emotion/createEmotionCache";
   const cache = createEmotionCache();
   startTransition(() =>
     hydrateRoot(document,
       <StrictMode><CacheProvider value={cache}><HydratedRouter /></CacheProvider></StrictMode>));
   ```
3. **Server entry** (`app/entry.server.tsx`) — **stream** the render (so hydration
   works), buffer it to completion, then extract the critical CSS and inject it into
   `<head>`. Do **not** use `renderToString` here — see the warning below.
   ```tsx
   import { PassThrough } from "node:stream";
   import createCache from "@emotion/cache";
   import { CacheProvider } from "@emotion/react";
   import createEmotionServer from "@emotion/server/create-instance";
   import { renderToPipeableStream } from "react-dom/server";
   import { ServerRouter, type EntryContext } from "react-router";
   import { EMOTION_INSERTION_POINT } from "./emotion/createEmotionCache";
   const ABORT_DELAY = 10_000;
   export default function handleRequest(
     request: Request, responseStatusCode: number,
     responseHeaders: Headers, routerContext: EntryContext): Promise<Response> {
     return new Promise((resolve, reject) => {
       const cache = createCache({ key: "mui" });
       const { extractCriticalToChunks, constructStyleTagsFromChunks } = createEmotionServer(cache);
       let didError = false;
       const { pipe, abort } = renderToPipeableStream(
         <CacheProvider value={cache}><ServerRouter context={routerContext} url={request.url} /></CacheProvider>,
         {
           // onAllReady (not onShellReady): wait for the whole tree so the buffered
           // HTML is complete for extraction AND the RR data stream is fully enqueued/closed.
           onAllReady() {
             const body = new PassThrough();
             const chunks: Buffer[] = [];
             body.on("data", (c) => chunks.push(Buffer.from(c)));
             body.on("error", reject);
             body.on("end", () => {
               const html = Buffer.concat(chunks).toString("utf-8");
               const { styles } = extractCriticalToChunks(html);
               const styleTags = constructStyleTagsFromChunks({ html, styles });
               const markup = html.replace(
                 new RegExp(`(<meta name="${EMOTION_INSERTION_POINT}"[^>]*>)`), `$1${styleTags}`);
               responseHeaders.set("Content-Type", "text/html");
               resolve(new Response(`<!DOCTYPE html>${markup}`,
                 { status: didError ? 500 : responseStatusCode, headers: responseHeaders }));
             });
             pipe(body);
           },
           onShellError: reject,
           onError(err: unknown) { didError = true; console.error(err); },
         });
       setTimeout(abort, ABORT_DELAY);
     });
   }
   ```
4. **Document** (`app/root.tsx`) — add the insertion-point meta inside the `Layout`'s `<head>`,
   before `<Meta />` / `<Links />`:
   ```tsx
   <meta name="emotion-insertion-point" content="emotion-insertion-point" />
   ```

## Rules

- Use the **same Emotion cache `key`** on server and client; mismatched keys yield
  mismatched class names and a hydration flash.
- Inject critical styles into `<head>`, not `<body>`. The insertion-point meta must
  exist in the rendered `<head>` so both the server regex and the client cache find it.
- **Never use `renderToString` in the server entry.** React Router 7 framework mode
  ships loader data and hydration through a stream the client (`HydratedRouter`)
  awaits; only a streaming render (`renderToPipeableStream` / `renderToReadableStream`)
  feeds it. `renderToString` emits the stream-setup script but never enqueues or
  closes it, so the client hydrates **forever** — the SSR HTML looks perfect and
  fully styled, but the **entire app is inert**: no event handlers, no client
  navigation, and `<form>`s fall back to native submits (a login form then reloads
  straight back to the sign-in page). Symptom signature: in the served HTML,
  `window.__reactRouterContext.stream = new ReadableStream(...)` exists but there are
  **zero** `streamController.enqueue(` and `streamController.close()` calls.
- `extractCriticalToChunks` needs the full HTML string, which streaming hands you
  piecemeal — so buffer the pipe via `onAllReady` (not `onShellReady`) and run
  extraction on the complete buffer. You trade progressive streaming for critical-CSS
  extraction, but hydration stays intact.
- Add `@emotion/cache` and `@emotion/server` as direct dependencies — do not rely on
  them only transitively.
- Keep browser-only access (`window`, `document`, Firebase/Auth singletons) guarded;
  module-level CSS-in-JS and auth init run during SSR too.

## Verify

For the recommended SPA setup:

- Build and serve `build/client`; assert `index.html`/route fallbacks return
  `Cache-Control: no-store` while existing hashed assets remain immutable.
- Request a nonexistent `/assets/missing.css`; assert a non-2xx status and
  `Cache-Control: no-store` (never a successful empty sheet).
- In a real browser, wait for `app-ready`, then assert at least one
  `style[data-emotion^="<cache-key>"]` has `sheet.cssRules.length > 0` and verify
  representative computed styles. Repeat across reloads and route navigations.
- Simulate a failed same-origin stylesheet and confirm exactly one reload occurs;
  repeat within the cooldown and confirm there is no reload loop.

For SSR mode:

- Build, serve the production bundle, and confirm every `<style data-emotion=…>` tag
  renders **before `</head>`** and the document carries the insertion-point meta —
  e.g. fetch a route and assert style offsets precede the `</head>` offset.
- **Confirm hydration actually runs**, not just that the HTML looks right: in the
  served HTML, `streamController.enqueue(` and `streamController.close()` must each
  appear (≥1). Zero means the stream is dead and nothing on the page is interactive —
  styled but inert. Cheapest end-to-end check: load the page and click something
  stateful (a menu, a locale toggle); if nothing happens, hydration is broken.
- A module that initializes a client SDK at import (e.g. Firebase with a build-time
  key) will crash SSR if the key is absent — build with the same `VITE_*`/env values
  the deployed image uses before serving locally.
