---
name: go-errors
description: "Go backend errors: RFC 9457 HTTPError, exceptions package, controller error mapping, opaque responses with detailed logs. Load when mapping an error to an HTTP response, logging at an error boundary, or debugging a 401 or 500 with no cause."
applyTo: 'api/internal/**/*.go'
tags: [go, backend, standards]
---

# Go Backend — Error Handling

All HTTP-layer errors are `*exceptions.HTTPError` (`internal/app/exceptions/errors.go`),
an RFC 9457 Problem Details type serialised by `exceptions.WriteError`. See that file
for the struct fields, sentinels, factories, and `ProblemType*` URI constants.

## Rules

- **Never** construct `&exceptions.HTTPError{...}` inline, call `http.Error` directly,
  hardcode a problem-type URI, or return raw infrastructure errors (e.g. a database driver error) from
  a controller. Use a sentinel or factory + `exceptions.WriteError`.
- **Never** both log and re-return the same error — pick one.
- Services/repositories return plain or domain errors; only **controllers** map them to
  `HTTPError`.

## Sentinels & factories

Sentinels (add context with `.WithDetail(...)`): `ErrBadRequest`, `ErrValidation`,
`ErrUnauthorized`, `ErrForbidden`, `ErrNotFound`, `ErrConflict`, `ErrInternal`,
`ErrServiceUnavailable`.

Factories (preferred for common cases):

```go
exceptions.NotFound("profile")              // 404 "profile not found"
exceptions.BadRequest("invalid photo ID")   // 400
exceptions.Conflict("match already exists")  // 409
exceptions.ValidationError("invalid input", map[string]string{
    "displayName": "must be at least 2 characters",
})
```

## Controller flow

Exported method catches and writes; private method does the work and maps errors:

```go
func (c *ProfileController) GetProfile(w http.ResponseWriter, r *http.Request) {
    if err := c.getProfile(w, r); err != nil {
        exceptions.WriteError(w, err)
    }
}

func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    profile, err := c.service.GetProfile(r.Context(), auth.UserIDFromContext(r.Context()))
    if err != nil {
        if errors.Is(err, db.ErrNotFound) {
            return exceptions.NotFound("profile")
        }
        return exceptions.ErrInternal.Wrap(err) // Detail stays generic; original preserved for errors.Is/logging
    }
    return writeJSON(w, http.StatusOK, profile)
}
```

Use `.Wrap(err)` to keep the original (for `errors.Is`/`errors.As`) without leaking it to
the client; `.WithDetail("...")` to add a client-facing message.

## Surfacing errors in logs (opaque to client, detailed in logs)

The RFC 9457 body returned to the client is deliberately generic — a bare `401
Unauthorized`, a `500 "An unexpected error occurred"`. That is correct for the
client and **useless for operators**: in the hosted log viewer the access log
shows only `method`, `path`, `status` (and `request_id`), so a failing request
gives you a status code and no reason. The rule:

> **Opaque to the client, detailed in the logs.** Every place that maps an error to
> an `HTTPError` (or discards a cause to return a sentinel) must emit one
> structured server-side log line carrying the real cause and the `request_id`
> *before* writing the response.

Without this, `.Wrap(err)` only preserves the cause for `errors.Is`/`errors.As` —
nothing ever prints it, so a wrapped 500 or a generic 401 is undebuggable.

### `WriteError` as a catch-all sink (injected `*zap.Logger`)

`exceptions` must **not** import the `logging` package (`logging` → `middleware` →
`exceptions` is an import cycle), but that only bars the `logging` *package* — not
logging itself. Give `exceptions` a package-level `*zap.Logger` set once at startup
and have `WriteError` log the cause of every **5xx** through it:

```go
var pkgLogger *zap.Logger
func SetLogger(l *zap.Logger) { pkgLogger = l } // call once in container wiring

func WriteError(w http.ResponseWriter, err error) {
    httpErr := asHTTPError(err) // wraps a non-HTTPError in ErrInternal
    if pkgLogger != nil && httpErr.Status >= 500 {
        pkgLogger.Error("request failed with server error",
            zap.Int("status", httpErr.Status), zap.Error(httpErr.cause))
    }
    // …write the opaque problem+json body…
}
```

This is the **global safety net**: a controller that returns a bare
`ErrInternal.Wrap(err)` *without* its own log line still gets its cause recorded, so
no 5xx is ever a silent "unknown reason". It carries no `request_id` (no context),
but the access-log line for the same request lands at the same timestamp. Pair it
with the richer **boundary** logs below, which add `request_id` and intent — do not
treat the catch-all as a reason to skip them:

- **Controllers** (can import `logging`): log via `logging.FromContext(ctx)` — it
  attaches `request_id` automatically — at the point you map a cause to an
  `HTTPError`. Log the *cause*, not the sanitized `HTTPError`.
  ```go
  func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
      profile, err := c.service.GetProfile(r.Context(), userID)
      if err != nil {
          if errors.Is(err, db.ErrNotFound) {
              return exceptions.NotFound("profile") // expected; no log needed
          }
          // Unexpected: record the real cause before returning a generic 500.
          logging.FromContext(r.Context()).Error("get profile failed", zap.Error(err))
          return exceptions.ErrInternal.Wrap(err)
      }
      return writeJSON(w, http.StatusOK, profile)
  }
  ```
- **Middleware** (must **not** import `logging` — same cycle): take an injected
  `*zap.Logger` (like `AccessLogMiddleware` does) and pair it with
  `RequestIDFromContext(ctx)`. Auth middleware that collapses every verifier error
  into one opaque 401 is the worst offender — log the discarded cause at `Warn`:
  ```go
  identity, err := verifier.VerifyToken(r.Context(), token)
  if err != nil {
      logger.Warn("token verification failed",
          zap.String("request_id", RequestIDFromContext(r.Context())),
          zap.Error(err)) // the real reason: expired, audience mismatch, bad signature…
      exceptions.WriteError(w, exceptions.ErrUnauthorized) // client still sees a bare 401
      return
  }
  ```

### Level by status class

- `5xx` → `Error` (a bug or a downstream outage — must page-able/alertable).
- `401/403` → `Warn` (auth/permission failure — log the cause; never the bearer token
  or password).
- other `4xx` → `Info`/`Debug` (client mistakes; noisy, keep low).
- **Never** log secrets — tokens, passwords, full Authorization headers. Log the
  *reason string* the SDK returns, not the credential.

### Reading them back

The `request_id` ties the access line to its error line. Query the log backend for
non-2xx lines with their reason, newest first. Then pivot on one `request_id` to see the
access line and its cause together. The project overlay holds the exact query for its
log backend.

If a 401/500 shows no companion log line with a cause, the boundary is swallowing
the error — that is the bug to fix, before chasing the symptom.

## Scope

Covers `HTTPError`, sentinels, factories, controller error flow, and the
log-the-cause-at-the-boundary convention. Broader controller structure:
{{ skill_link("go-architecture") }}.
Access-log middleware and logger injection:
{{ skill_link("go-server") }}.

