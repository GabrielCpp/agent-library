# Service operation patterns

One worked shape per kind of service method. Rules live in [`../SKILL.md`](../SKILL.md). Open the section for the operation you are writing.

## Common Service Patterns

### Create Operation

```go
type CreateInput struct {
    UserID      string
    DisplayName string
    Age         int
}

func (s *Service) Create(ctx context.Context, input CreateInput) (*domain.Profile, error) {
    // 1. Validate input (domain rules)
    if input.UserID == "" {
        return nil, ErrValidation
    }
    if input.Age < 18 {
        return nil, errors.New("must be 18 or older")
    }
    if len(input.DisplayName) < 2 {
        return nil, errors.New("display name too short")
    }

    // 2. Check for existing profile
    existing, err := s.repo.FindByUserID(ctx, input.UserID)
    if err == nil && existing != nil {
        return nil, ErrAlreadyExists
    }

    // 3. Create domain model
    now := time.Now()
    profile := domain.Profile{
        ID:          generateID(),  // Business ID generation
        UserID:      input.UserID,
        DisplayName: input.DisplayName,
        Age:         input.Age,
        CreatedAt:   now,
        UpdatedAt:   now,
    }

    // 4. Persist
    if err := s.repo.Set(ctx, profile); err != nil {
        s.logger.Error("failed to create profile",
            zap.String("userID", input.UserID),
            zap.Error(err),
        )
        return nil, err
    }

    s.logger.Info("profile created",
        zap.String("profileID", profile.ID),
        zap.String("userID", input.UserID),
    )

    return &profile, nil
}
```

### Update Operation

```go
type UpdateInput struct {
    DisplayName string
    Bio         string
    Age         int
}

func (s *Service) Update(ctx context.Context, userID string, input UpdateInput) (*domain.Profile, error) {
    // 1. Get existing profile
    profile, err := s.GetByUserID(ctx, userID)
    if err != nil {
        return nil, err
    }

    // 2. Validate changes
    if input.Age > 0 && input.Age < 18 {
        return nil, errors.New("must be 18 or older")
    }

    // 3. Apply changes (only update non-zero values)
    if input.DisplayName != "" {
        profile.DisplayName = input.DisplayName
    }
    if input.Bio != "" {
        profile.Bio = input.Bio
    }
    if input.Age > 0 {
        profile.Age = input.Age
    }

    // 4. Update timestamp
    profile.UpdatedAt = time.Now()

    // 5. Persist
    if err := s.repo.Set(ctx, *profile); err != nil {
        s.logger.Error("failed to update profile",
            zap.String("profileID", profile.ID),
            zap.Error(err),
        )
        return nil, err
    }

    return profile, nil
}
```

### Delete/Archive Operation

```go
func (s *Service) Archive(ctx context.Context, userID string) error {
    profile, err := s.GetByUserID(ctx, userID)
    if err != nil {
        return err
    }

    // Business rule: Can't archive incomplete profiles
    if !s.isComplete(profile) {
        return errors.New("cannot archive incomplete profile")
    }

    profile.ArchivedAt = time.Now()
    profile.UpdatedAt = time.Now()

    if err := s.repo.Set(ctx, *profile); err != nil {
        s.logger.Error("failed to archive profile",
            zap.String("profileID", profile.ID),
            zap.Error(err),
        )
        return err
    }

    return nil
}
```

### List/Query Operations

```go
type ListOptions struct {
    Limit int
    Status string
}

func (s *Service) ListMatches(ctx context.Context, userID string, opts ListOptions) ([]domain.Match, error) {
    if userID == "" {
        return nil, ErrValidation
    }

    // Default limit
    if opts.Limit <= 0 {
        opts.Limit = 20
    }

    matches, err := s.repo.ListMatches(ctx, domain.MatchQuery{
        UserID: userID,
        Status: opts.Status,
        Limit:  opts.Limit,
    })
    if err != nil {
        s.logger.Error("failed to list matches",
            zap.String("userID", userID),
            zap.Error(err),
        )
        return nil, err
    }

    return matches, nil
}
```

## Service Composition (Orchestration)

Services can depend on other services for complex workflows:

```go
type MatchesService struct {
    repo           Repository
    profileService ProfileService  // Depends on another service
    logger         *zap.Logger
}

func (s *MatchesService) CreateMatch(ctx context.Context, userID, targetUserID string) (*domain.Match, error) {
    // 1. Verify both users exist (orchestrating profile service)
    user1, err := s.profileService.GetByUserID(ctx, userID)
    if err != nil {
        return nil, errors.New("user not found")
    }

    user2, err := s.profileService.GetByUserID(ctx, targetUserID)
    if err != nil {
        return nil, errors.New("target user not found")
    }

    // 2. Business rule: Can't match with yourself
    if userID == targetUserID {
        return nil, errors.New("cannot match with yourself")
    }

    // 3. Business rule: Both users must be active
    if user1.ArchivedAt != time.Time{} || user2.ArchivedAt != time.Time{} {
        return nil, errors.New("cannot match with archived user")
    }

    // 4. Create match
    match := domain.Match{
        ID:        generateID(),
        UserIDs:   []string{userID, targetUserID},
        Status:    "pending",
        CreatedAt: time.Now(),
    }

    if err := s.repo.Set(ctx, match); err != nil {
        return nil, err
    }

    return &match, nil
}
```

## Infrastructure Dependencies (Storage, External APIs)

Services can depend on infrastructure interfaces for I/O operations:

```go
// Storage interface (infrastructure provides implementation)
type StorageClient interface {
    GetSignedURL(ctx context.Context, objectPath string, opts SignedURLOptions) (*SignedURLResult, error)
    Delete(ctx context.Context, objectPath string) error
}

type Service struct {
    repo    Repository
    storage StorageClient  // Infrastructure dependency
    logger  *zap.Logger
}

// Service handles domain logic (path construction, ID generation)
func (s *Service) GetPhotoUploadURL(ctx context.Context, userID, contentType string) (*UploadURLResult, error) {
    // 1. Validate
    if userID == "" {
        return nil, ErrValidation
    }

    // 2. Generate business ID (domain logic)
    photoID := uuid.New().String()

    // 3. Construct domain path (domain logic)
    objectPath := fmt.Sprintf("users/%s/photos/%s", userID, photoID)

    // 4. Apply business rules (domain logic)
    maxSize := 3 * 1024 * 1024 // 3MB limit

    // 5. Call infrastructure with complete path
    result, err := s.storage.GetSignedURL(ctx, objectPath, SignedURLOptions{
        Method:      "PUT",
        ContentType: contentType,
        MaxSize:     maxSize,
        ExpiresIn:   15 * time.Minute,
    })
    if err != nil {
        return nil, err
    }

    return &UploadURLResult{
        PhotoID:   photoID,
        UploadURL: result.URL,
        ExpiresAt: result.ExpiresAt,
    }, nil
}
```

## Validation Patterns

### Input Validation

```go
func (s *Service) validateCreateInput(input CreateInput) error {
    if input.UserID == "" {
        return errors.New("userID is required")
    }
    if input.DisplayName == "" {
        return errors.New("displayName is required")
    }
    if len(input.DisplayName) < 2 {
        return errors.New("displayName must be at least 2 characters")
    }
    if input.Age < 18 {
        return errors.New("must be 18 or older")
    }
    if input.Age > 150 {
        return errors.New("invalid age")
    }
    return nil
}

func (s *Service) Create(ctx context.Context, input CreateInput) (*domain.Profile, error) {
    if err := s.validateCreateInput(input); err != nil {
        return nil, fmt.Errorf("%w: %s", ErrValidation, err.Error())
    }
    // ... rest of creation logic
}
```

### Domain Rules Validation

```go
func (s *Service) canSendMessage(from, to *domain.Profile) error {
    // Business rule: Both users must be active
    if from.ArchivedAt != time.Time{} {
        return errors.New("your profile is archived")
    }
    if to.ArchivedAt != time.Time{} {
        return errors.New("recipient profile is archived")
    }

    // Business rule: Both must have completed profiles
    if !s.isComplete(from) {
        return errors.New("complete your profile first")
    }
    if !s.isComplete(to) {
        return errors.New("recipient has incomplete profile")
    }

    return nil
}
```
