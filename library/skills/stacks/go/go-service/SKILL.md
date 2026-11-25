---
name: go-service
description: "Go service layer: pure business logic, domain errors, repository interfaces, context first, zap logger, mockery tests. Load when writing or reviewing business rules, validation or orchestration in internal/core/services, or a service test."
applyTo: 'api/**/*.go'
tags: [go, backend, standards]
---

# Level 2: Service Pattern

**Reference this when implementing business logic.**

---

## Service Responsibilities

A service contains **pure business logic**:

- Domain rules and validation
- Orchestration of repositories
- State transformations
- Authorization checks (based on domain rules)

**Services do NOT**:

- Parse HTTP requests
- Return HTTP status codes
- Directly access the database (use repositories)
- Know about HTTP concerns (headers, cookies, etc.)

---

## Anatomy of a Service

```go
package profile

import (
    "context"
    "errors"
    "time"
    "go.uber.org/zap"
    "github.com/yourorg/project/internal/core/domain"
)

// Domain errors (not HTTP errors)
var (
    ErrNotFound      = errors.New("profile not found")
    ErrAlreadyExists = errors.New("profile already exists")
    ErrValidation    = errors.New("validation failed")
)

// Repository interface (service depends on abstraction, not concrete impl)
type Repository interface {
    Get(ctx context.Context, id string) (*domain.Profile, error)
    Set(ctx context.Context, profile domain.Profile) error
    FindByUserID(ctx context.Context, userID string) (*domain.Profile, error)
}

// Service struct
type Service struct {
    repo   Repository
    logger *zap.Logger
}

// Constructor (receives dependencies via DI)
func NewService(repo Repository, logger *zap.Logger) *Service {
    return &Service{
        repo:   repo,
        logger: logger,
    }
}

// Business logic method
// ALWAYS: context.Context as first parameter
// RETURNS: Domain models and domain errors
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    s.logger.Info("getting profile",
        zap.String("userID", userID),
    )

    // 1. Input validation
    if userID == "" {
        return nil, ErrValidation
    }

    // 2. Repository query
    profile, err := s.repo.FindByUserID(ctx, userID)
    if err != nil {
        s.logger.Error("failed to get profile",
            zap.String("userID", userID),
            zap.Error(err),
        )
        return nil, ErrNotFound
    }

    // 3. Business logic (if needed)
    // Example: Enrich profile with computed fields
    // profile.IsComplete = s.checkCompletion(profile)

    return profile, nil
}
```

---

## Operation patterns

Services can depend on other services for orchestration, and on infrastructure interfaces for I/O.

**KEY PRINCIPLE**: Infrastructure provides **generic I/O operations**. Services provide **domain-specific logic** (paths, IDs, rules).

Create, update, archive, list/query, service composition, infrastructure dependencies and validation helpers each have a worked shape in [references/patterns.md](references/patterns.md). Open the section for the operation you are writing.

---

## Error Handling Guidelines

### Return Domain Errors

```go
var (
    ErrNotFound      = errors.New("profile not found")
    ErrAlreadyExists = errors.New("profile already exists")
    ErrValidation    = errors.New("validation failed")
    ErrForbidden     = errors.New("access denied")
)
```

### Wrap Errors with Context

```go
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    profile, err := s.repo.FindByUserID(ctx, userID)
    if err != nil {
        // Wrap repository error with service context
        return nil, fmt.Errorf("failed to get profile for user %s: %w", userID, err)
    }
    return profile, nil
}
```

### Log Errors Before Returning

```go
func (s *Service) Update(ctx context.Context, userID string, input UpdateInput) (*domain.Profile, error) {
    if err := s.repo.Set(ctx, *profile); err != nil {
        s.logger.Error("failed to update profile",
            zap.String("userID", userID),
            zap.String("profileID", profile.ID),
            zap.Error(err),
        )
        return nil, err  // Return error after logging
    }
    return profile, nil
}
```

---

## Common Mistakes

### ❌ Returning HTTP Status Codes

```go
// WRONG: Service returns HTTP concerns
func (s *Service) GetByUserID(ctx context.Context, userID string) (int, *domain.Profile, error) {
    profile, err := s.repo.FindByUserID(ctx, userID)
    if err != nil {
        return 404, nil, err  // HTTP status code in service
    }
    return 200, profile, nil
}

// CORRECT: Return domain error, let controller map to HTTP
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    profile, err := s.repo.FindByUserID(ctx, userID)
    if err != nil {
        return nil, ErrNotFound  // Domain error
    }
    return profile, nil
}
```

### ❌ Direct Database Access

```go
// WRONG: Service calling the database driver directly
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    row, err := s.dbConn.QueryProfile(ctx, userID)
    // ...
}

// CORRECT: Use repository interface
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    profile, err := s.repo.FindByUserID(ctx, userID)
    // ...
}
```

### ❌ Missing Context Parameter

```go
// WRONG: No context parameter
func (s *Service) GetByUserID(userID string) (*domain.Profile, error) {
    // How do we handle timeouts/cancellation?
}

// CORRECT: Context as first parameter
func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    // Can handle timeouts, cancellation, deadlines
}
```

---

## Testing Services

Services are easy to test with `mockery`-generated repository mocks. Generate
the mock (`make generate-mocks`) and script expectations with the typed
`EXPECT()` API — never hand-write a repository double. See the **Mocks** section
of the Go testing guide for setup and rules.

```go
func Test_Service_GetByUserID_ShouldHandleLookup(t *testing.T) {
    logger := zaptest.NewLogger(t)

    t.Run("ShouldReturnProfile_WhenFound", func(t *testing.T) {
        repo := mocks.NewMockRepository(t)
        repo.EXPECT().
            FindByUserID(mock.Anything, "user-1").
            Return(&domain.Profile{ID: "123", UserID: "user-1"}, nil).
            Once()

        profile, err := NewService(repo, logger).GetByUserID(t.Context(), "user-1")
        require.NoError(t, err)
        require.Equal(t, "123", profile.ID)
    })

    t.Run("ShouldReturnErrNotFound_WhenMissing", func(t *testing.T) {
        repo := mocks.NewMockRepository(t)
        repo.EXPECT().
            FindByUserID(mock.Anything, "user-1").
            Return(nil, ErrNotFound).
            Once()

        profile, err := NewService(repo, logger).GetByUserID(t.Context(), "user-1")
        require.ErrorIs(t, err, ErrNotFound)
        require.Nil(t, profile)
    })
}
```

Construct the mock with `t` so expectations are asserted automatically on
cleanup. See **Level 2: Test Patterns** for more examples.

## Worked examples

A worked service: business logic, orchestration, and error mapping end to end. Load it only when you need the concrete shape — the rules above are the contract.

[`references/examples.md`](references/examples.md)
