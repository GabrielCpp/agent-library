---
name: go-controller
description: "Go HTTP controller pattern: thin handlers, exceptions.WriteError, request parsing, API-to-domain conversion, error-to-HTTP table. Load when writing or reviewing an endpoint handler, request parsing, response mapping or status codes."
applyTo: 'api/**/*.go'
tags: [go, backend, standards]
---

# Level 2: Controller Pattern

**Reference this when implementing HTTP endpoints.**

---

## Controller Responsibilities

A controller is a **thin HTTP adapter** that:

1. Extracts data from HTTP request
2. Calls service (business logic)
3. Maps errors to HTTP responses
4. Serializes success responses

**Controllers do NOT**:

- Contain business logic
- Access repositories directly
- Make external API calls
- Perform validation (beyond basic parsing)

---

## Anatomy of a Controller

```go
package controllers

import (
    "net/http"
    "github.com/yourorg/project/internal/app/exceptions"
    "github.com/yourorg/project/internal/app/httputil"
    "github.com/yourorg/project/internal/app/auth"
    "github.com/yourorg/project/internal/core/services/profile"
)

type ProfileController struct {
    service profile.Service  // Interface, not concrete type
}

func NewProfileController(service profile.Service) *ProfileController {
    return &ProfileController{service: service}
}

// Public method: matches ServerInterface signature
// Handles error conversion using exceptions pattern
func (c *ProfileController) GetProfile(w http.ResponseWriter, r *http.Request) {
    if err := c.getProfile(w, r); err != nil {
        exceptions.WriteError(w, err)  // Converts error to HTTP response
        return
    }
}

// Private method: returns errors instead of writing responses
// This pattern enables cleaner error handling
func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    // 1. Extract auth context (added by middleware)
    userID, err := auth.GetUserID(r.Context())
    if err != nil {
        return exceptions.ErrUnauthorized
    }

    // 2. Call service (business logic)
    profile, err := c.service.GetByUserID(r.Context(), userID)
    if err != nil {
        // Map service errors to HTTP errors
        if errors.Is(err, profile.ErrNotFound) {
            return exceptions.NotFound("profile")
        }
        // Wrap unexpected errors (logs original, returns 500)
        return exceptions.ErrInternal.Wrap(err)
    }

    // 3. Convert domain model to API response type
    resp := domainToAPIProfile(profile)

    // 4. Serialize and send response
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}
```

---

## Pattern Variations

### POST/PUT Endpoints (with request body)

```go
func (c *ProfileController) UpdateProfile(w http.ResponseWriter, r *http.Request) {
    if err := c.updateProfile(w, r); err != nil {
        exceptions.WriteError(w, err)
        return
    }
}

func (c *ProfileController) updateProfile(w http.ResponseWriter, r *http.Request) error {
    userID, err := auth.GetUserID(r.Context())
    if err != nil {
        return exceptions.ErrUnauthorized
    }

    // 1. Decode request body (generated API type)
    var req api.UpdateProfileRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        return exceptions.BadRequest("invalid JSON")
    }

    // 2. Convert API type to domain input
    input := apiToUpdateInput(&req)

    // 3. Call service
    profile, err := c.service.Update(r.Context(), userID, input)
    if err != nil {
        if errors.Is(err, profile.ErrValidation) {
            return exceptions.BadRequest(err.Error())
        }
        return exceptions.ErrInternal.Wrap(err)
    }

    // 4. Return response
    resp := domainToAPIProfile(profile)
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}
```

### Path Parameters

```go
func (c *MatchesController) GetMatch(w http.ResponseWriter, r *http.Request, matchID string) {
    if err := c.getMatch(w, r, matchID); err != nil {
        exceptions.WriteError(w, err)
        return
    }
}

func (c *MatchesController) getMatch(w http.ResponseWriter, r *http.Request, matchID string) error {
    userID, err := auth.GetUserID(r.Context())
    if err != nil {
        return exceptions.ErrUnauthorized
    }

    // Validate path parameter
    if matchID == "" {
        return exceptions.BadRequest("matchID is required")
    }

    match, err := c.service.GetMatch(r.Context(), userID, matchID)
    if err != nil {
        if errors.Is(err, matches.ErrNotFound) {
            return exceptions.NotFound("match")
        }
        if errors.Is(err, matches.ErrForbidden) {
            return exceptions.ErrForbidden
        }
        return exceptions.ErrInternal.Wrap(err)
    }

    resp := domainToAPIMatch(match)
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}
```

### Query Parameters

```go
func (c *MatchesController) ListMatches(w http.ResponseWriter, r *http.Request, params api.ListMatchesParams) {
    if err := c.listMatches(w, r, params); err != nil {
        exceptions.WriteError(w, err)
        return
    }
}

func (c *MatchesController) listMatches(w http.ResponseWriter, r *http.Request, params api.ListMatchesParams) error {
    userID, err := auth.GetUserID(r.Context())
    if err != nil {
        return exceptions.ErrUnauthorized
    }

    // Extract query params (oapi-codegen provides typed params)
    limit := 20
    if params.Limit != nil {
        limit = *params.Limit
    }

    matches, err := c.service.ListMatches(r.Context(), userID, limit)
    if err != nil {
        return exceptions.ErrInternal.Wrap(err)
    }

    resp := domainToAPIMatches(matches)
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}
```

---

## Domain ↔ API Type Conversion

### Converting API Request → Domain Input

```go
// API type (generated from OpenAPI, uses pointers for optional fields)
type UpdateProfileRequest struct {
    DisplayName *string `json:"displayName,omitempty"`
    Bio         *string `json:"bio,omitempty"`
    Age         *int    `json:"age,omitempty"`
}

// Domain input (service layer contract, uses zero values)
type UpdateInput struct {
    DisplayName string
    Bio         string
    Age         int
}

// Conversion helper
func apiToUpdateInput(req *api.UpdateProfileRequest) profile.UpdateInput {
    input := profile.UpdateInput{}

    if req.DisplayName != nil {
        input.DisplayName = *req.DisplayName
    }
    if req.Bio != nil {
        input.Bio = *req.Bio
    }
    if req.Age != nil {
        input.Age = *req.Age
    }

    return input
}
```

### Converting Domain Model → API Response

```go
// Domain model (zero values for optional fields)
type Profile struct {
    ID          string
    UserID      string
    DisplayName string
    Bio         string
    Age         int
    CreatedAt   time.Time
    UpdatedAt   time.Time
}

// API response (generated, uses pointers)
type ProfileResponse struct {
    ID          string     `json:"id"`
    UserID      string     `json:"userId"`
    DisplayName *string    `json:"displayName,omitempty"`
    Bio         *string    `json:"bio,omitempty"`
    Age         *int       `json:"age,omitempty"`
    CreatedAt   *time.Time `json:"createdAt,omitempty"`
    UpdatedAt   *time.Time `json:"updatedAt,omitempty"`
}

// Conversion helper
func domainToAPIProfile(p *domain.Profile) *api.ProfileResponse {
    resp := &api.ProfileResponse{
        ID:     p.ID,
        UserID: p.UserID,
    }

    // Only include non-zero values
    if p.DisplayName != "" {
        resp.DisplayName = &p.DisplayName
    }
    if p.Bio != "" {
        resp.Bio = &p.Bio
    }
    if p.Age > 0 {
        resp.Age = &p.Age
    }
    if !p.CreatedAt.IsZero() {
        resp.CreatedAt = &p.CreatedAt
    }
    if !p.UpdatedAt.IsZero() {
        resp.UpdatedAt = &p.UpdatedAt
    }

    return resp
}
```

---

## Error Mapping Reference

| Service Error      | HTTP Error                           | Status Code |
| ------------------ | ------------------------------------ | ----------- |
| `ErrNotFound`      | `exceptions.NotFound("resource")`    | 404         |
| `ErrValidation`    | `exceptions.BadRequest(err.Error())` | 400         |
| `ErrAlreadyExists` | `exceptions.Conflict("resource")`    | 409         |
| `ErrUnauthorized`  | `exceptions.ErrUnauthorized`         | 401         |
| `ErrForbidden`     | `exceptions.ErrForbidden`            | 403         |
| Any other error    | `exceptions.ErrInternal.Wrap(err)`   | 500         |

**Pattern**:

```go
if err != nil {
    if errors.Is(err, service.ErrSpecific) {
        return exceptions.HTTPError  // Map to specific HTTP error
    }
    return exceptions.ErrInternal.Wrap(err)  // Default to 500
}
```

---

## Common Mistakes

### ❌ Business Logic in Controller

```go
// WRONG: Validation logic in controller
func (c *ProfileController) updateProfile(w http.ResponseWriter, r *http.Request) error {
    var req api.UpdateProfileRequest
    json.NewDecoder(r.Body).Decode(&req)

    // DON'T DO THIS - validation belongs in service
    if req.Age != nil && *req.Age < 18 {
        return exceptions.BadRequest("must be 18+")
    }

    // ...
}

// CORRECT: Delegate to service
func (c *ProfileController) updateProfile(w http.ResponseWriter, r *http.Request) error {
    var req api.UpdateProfileRequest
    json.NewDecoder(r.Body).Decode(&req)

    input := apiToUpdateInput(&req)
    profile, err := c.service.Update(r.Context(), userID, input)
    // Service handles validation, returns ErrValidation if invalid
    if err != nil {
        if errors.Is(err, profile.ErrValidation) {
            return exceptions.BadRequest(err.Error())
        }
        return exceptions.ErrInternal.Wrap(err)
    }
    // ...
}
```

### ❌ Mixing Error Patterns

```go
// WRONG: Mixing response writing with error returns
func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    profile, err := c.service.GetByUserID(r.Context(), userID)
    if err != nil {
        httputil.WriteError(w, http.StatusNotFound, "not found")  // Writing response
        return err  // Also returning error (will be written again!)
    }
    return nil
}

// CORRECT: Return errors, let WriteError handle responses
func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    profile, err := c.service.GetByUserID(r.Context(), userID)
    if err != nil {
        if errors.Is(err, profile.ErrNotFound) {
            return exceptions.NotFound("profile")  // Return error only
        }
        return exceptions.ErrInternal.Wrap(err)
    }
    httputil.WriteJSON(w, http.StatusOK, profile)
    return nil
}
```

### ❌ Not Using Generated Types

```go
// WRONG: Defining custom request types
type CustomUpdateRequest struct {
    Name string `json:"name"`
}

// CORRECT: Use generated types from openapi.yaml
var req api.UpdateProfileRequest  // Generated by oapi-codegen
```

---

## Wiring Controllers in Server

Controllers are composed in `internal/app/server.go`:

```go
type Server struct {
    api.Unimplemented
    profile *controllers.ProfileController
    matches *controllers.MatchesController
}

func NewServer(
    profileCtrl *controllers.ProfileController,
    matchesCtrl *controllers.MatchesController,
) *Server {
    return &Server{
        profile: profileCtrl,
        matches: matchesCtrl,
    }
}

// Explicit delegation (required because of Unimplemented)
func (s *Server) GetProfile(w http.ResponseWriter, r *http.Request) {
    s.profile.GetProfile(w, r)
}

func (s *Server) UpdateProfile(w http.ResponseWriter, r *http.Request) {
    s.profile.UpdateProfile(w, r)
}
```

**Why explicit delegation?**: Embedding causes "ambiguous selector" errors when `api.Unimplemented` and controller both define the same method.

---

## Testing Controllers

See **Level 2: Test Patterns** for integration test templates.

## Worked examples

A worked OpenAPI contract and the HTTP controller that implements it. Load it only when you need the concrete shape — the rules above are the contract.

[`references/rest-examples.md`](references/rest-examples.md)
