# Go REST Examples

A worked OpenAPI contract and the HTTP controller that implements it. Rules live in [`../SKILL.md`](../SKILL.md); load this only when implementing or reviewing REST contracts and controllers.

## REST Contract Example: OpenAPI Specification

`pkg/api/openapi.yaml`:

```yaml
openapi: 3.0.0
info:
  title: {{ template.api_title | default("Project API") }}
  version: 1.0.0

paths:
  /v1/profile:
    get:
      operationId: getProfile
      summary: Get current user's profile
      tags: [Profile]
      security:
        - BearerAuth: []
      responses:
        "200":
          description: Profile found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Profile"
        "404":
          description: Profile not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"

    put:
      operationId: updateProfile
      summary: Update current user's profile
      tags: [Profile]
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/UpdateProfileRequest"
      responses:
        "200":
          description: Profile updated
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Profile"
        "400":
          description: Invalid input
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"

components:
  schemas:
    Profile:
      type: object
      required:
        - id
        - userId
      properties:
        id:
          type: string
        userId:
          type: string
        displayName:
          type: string
        bio:
          type: string
        age:
          type: integer
        createdAt:
          type: string
          format: date-time
        updatedAt:
          type: string
          format: date-time

    UpdateProfileRequest:
      type: object
      properties:
        displayName:
          type: string
          minLength: 2
          maxLength: 50
        bio:
          type: string
          maxLength: 500
        age:
          type: integer
          minimum: 18
          maximum: 150

    Error:
      type: object
      properties:
        error:
          type: string

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```

After editing, run: `make generate`

---

## REST Controller Example: Profile Handlers

`internal/app/controllers/profile.go`:

```go
package controllers

import (
    "encoding/json"
    "errors"
    "net/http"

    "github.com/yourorg/project/internal/app/auth"
    "github.com/yourorg/project/internal/app/exceptions"
    "github.com/yourorg/project/internal/app/httputil"
    "github.com/yourorg/project/internal/core/services/profile"
    "github.com/yourorg/project/pkg/api"
)

type ProfileController struct {
    service *profile.Service
}

func NewProfileController(service *profile.Service) *ProfileController {
    return &ProfileController{service: service}
}

func (c *ProfileController) GetProfile(w http.ResponseWriter, r *http.Request) {
    if err := c.getProfile(w, r); err != nil {
        exceptions.WriteError(w, err)
        return
    }
}

func (c *ProfileController) getProfile(w http.ResponseWriter, r *http.Request) error {
    userID, err := auth.GetUserID(r.Context())
    if err != nil {
        return exceptions.ErrUnauthorized
    }

    profile, err := c.service.GetByUserID(r.Context(), userID)
    if err != nil {
        if errors.Is(err, profile.ErrNotFound) {
            return exceptions.NotFound("profile")
        }
        return exceptions.ErrInternal.Wrap(err)
    }

    resp := domainToAPIProfile(profile)
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}

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

    var req api.UpdateProfileRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        return exceptions.BadRequest("invalid JSON")
    }

    input := apiToUpdateInput(&req)

    profile, err := c.service.Update(r.Context(), userID, input)
    if err != nil {
        if errors.Is(err, profile.ErrNotFound) {
            return exceptions.NotFound("profile")
        }
        if errors.Is(err, profile.ErrValidation) {
            return exceptions.BadRequest(err.Error())
        }
        return exceptions.ErrInternal.Wrap(err)
    }

    resp := domainToAPIProfile(profile)
    httputil.WriteJSON(w, http.StatusOK, resp)
    return nil
}

// Convert domain model to API response
func domainToAPIProfile(p *domain.Profile) *api.Profile {
    resp := &api.Profile{
        Id:     p.ID,
        UserId: p.UserID,
    }

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

// Convert API request to domain input
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

---

