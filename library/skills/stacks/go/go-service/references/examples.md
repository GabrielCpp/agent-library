# Go Service Examples

A worked service. Rules live in [`../SKILL.md`](../SKILL.md); load this only when adding or reviewing service-layer business logic.

## Service Example: Profile Business Logic

`internal/core/services/profile/service.go`:

```go
package profile

import (
    "context"
    "errors"
    "fmt"
    "time"

    "go.uber.org/zap"

    "github.com/yourorg/project/internal/core/domain"
)

var (
    ErrNotFound   = errors.New("profile not found")
    ErrValidation = errors.New("validation failed")
)

type Repository interface {
    Get(ctx context.Context, id string) (*domain.Profile, error)
    Set(ctx context.Context, profile domain.Profile) error
    FindByUserID(ctx context.Context, userID string) (*domain.Profile, error)
}

type Service struct {
    repo   Repository
    logger *zap.Logger
}

func NewService(repo Repository, logger *zap.Logger) *Service {
    return &Service{
        repo:   repo,
        logger: logger,
    }
}

func (s *Service) GetByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    s.logger.Info("getting profile", zap.String("userID", userID))

    if userID == "" {
        return nil, ErrValidation
    }

    profile, err := s.repo.FindByUserID(ctx, userID)
    if err != nil {
        s.logger.Error("failed to get profile",
            zap.String("userID", userID),
            zap.Error(err),
        )
        return nil, ErrNotFound
    }

    return profile, nil
}

type UpdateInput struct {
    DisplayName string
    Bio         string
    Age         int
}

func (s *Service) Update(ctx context.Context, userID string, input UpdateInput) (*domain.Profile, error) {
    s.logger.Info("updating profile",
        zap.String("userID", userID),
    )

    // Get existing profile
    profile, err := s.GetByUserID(ctx, userID)
    if err != nil {
        return nil, err
    }

    // Validate input
    if err := s.validateUpdateInput(input); err != nil {
        return nil, fmt.Errorf("%w: %s", ErrValidation, err.Error())
    }

    // Apply updates (only non-zero values)
    if input.DisplayName != "" {
        profile.DisplayName = input.DisplayName
    }
    if input.Bio != "" {
        profile.Bio = input.Bio
    }
    if input.Age > 0 {
        profile.Age = input.Age
    }

    profile.UpdatedAt = time.Now()

    // Persist
    if err := s.repo.Set(ctx, *profile); err != nil {
        s.logger.Error("failed to update profile",
            zap.String("profileID", profile.ID),
            zap.Error(err),
        )
        return nil, err
    }

    s.logger.Info("profile updated",
        zap.String("profileID", profile.ID),
    )

    return profile, nil
}

func (s *Service) validateUpdateInput(input UpdateInput) error {
    if input.DisplayName != "" {
        if len(input.DisplayName) < 2 {
            return errors.New("displayName must be at least 2 characters")
        }
        if len(input.DisplayName) > 50 {
            return errors.New("displayName must be at most 50 characters")
        }
    }

    if input.Bio != "" && len(input.Bio) > 500 {
        return errors.New("bio must be at most 500 characters")
    }

    if input.Age > 0 {
        if input.Age < 18 {
            return errors.New("age must be at least 18")
        }
        if input.Age > 150 {
            return errors.New("age must be at most 150")
        }
    }

    return nil
}
```

---

