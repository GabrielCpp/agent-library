# Conversion Templates

**Copy-paste code snippets for common conversions.**

---

## API Request → Domain Input

### Simple Conversion (Pointers → Zero Values)

```go
// Given API request type (generated from OpenAPI)
type UpdateProfileRequest struct {
    DisplayName *string `json:"displayName,omitempty"`
    Bio         *string `json:"bio,omitempty"`
    Age         *int    `json:"age,omitempty"`
}

// Domain input type (zero values)
type UpdateInput struct {
    DisplayName string
    Bio         string
    Age         int
}

// Conversion function
func apiToUpdateInput(req *api.UpdateProfileRequest) UpdateInput {
    input := UpdateInput{}

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

### With Time Fields

```go
type CreateInput struct {
    Name      string
    StartDate time.Time
    EndDate   time.Time
}

func apiToCreateInput(req *api.CreateRequest) CreateInput {
    input := CreateInput{}

    if req.Name != nil {
        input.Name = *req.Name
    }
    if req.StartDate != nil {
        input.StartDate = *req.StartDate
    }
    if req.EndDate != nil {
        input.EndDate = *req.EndDate
    }

    return input
}
```

### With Nested Objects

```go
type Address struct {
    Street  string
    City    string
    ZipCode string
}

type CreateProfileInput struct {
    Name    string
    Address Address
}

func apiToCreateInput(req *api.CreateProfileRequest) CreateProfileInput {
    input := CreateProfileInput{}

    if req.Name != nil {
        input.Name = *req.Name
    }

    if req.Address != nil {
        if req.Address.Street != nil {
            input.Address.Street = *req.Address.Street
        }
        if req.Address.City != nil {
            input.Address.City = *req.Address.City
        }
        if req.Address.ZipCode != nil {
            input.Address.ZipCode = *req.Address.ZipCode
        }
    }

    return input
}
```

---

## Domain Model → API Response

### Simple Conversion (Zero Values → Pointers)

```go
// Domain model (zero values)
type Profile struct {
    ID          string
    UserID      string
    DisplayName string
    Bio         string
    Age         int
    CreatedAt   time.Time
    UpdatedAt   time.Time
}

// API response type (generated, uses pointers)
type ProfileResponse struct {
    ID          string     `json:"id"`
    UserID      string     `json:"userId"`
    DisplayName *string    `json:"displayName,omitempty"`
    Bio         *string    `json:"bio,omitempty"`
    Age         *int       `json:"age,omitempty"`
    CreatedAt   *time.Time `json:"createdAt,omitempty"`
    UpdatedAt   *time.Time `json:"updatedAt,omitempty"`
}

// Conversion function
func domainToAPIProfile(p *domain.Profile) *api.ProfileResponse {
    resp := &api.ProfileResponse{
        ID:     p.ID,
        UserID: p.UserID,
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
```

### With Float Fields

```go
type Product struct {
    ID    string
    Name  string
    Price float64
}

func domainToAPIProduct(p *domain.Product) *api.ProductResponse {
    resp := &api.ProductResponse{
        ID:   p.ID,
        Name: p.Name,
    }

    if p.Price > 0 {
        resp.Price = &p.Price
    }

    return resp
}
```

### With Arrays/Slices

```go
type Profile struct {
    ID     string
    Photos []string
    Tags   []string
}

func domainToAPIProfile(p *domain.Profile) *api.ProfileResponse {
    resp := &api.ProfileResponse{
        ID: p.ID,
    }

    if len(p.Photos) > 0 {
        resp.Photos = &p.Photos
    }
    if len(p.Tags) > 0 {
        resp.Tags = &p.Tags
    }

    return resp
}
```

### List Conversion

```go
// Convert slice of domain models to slice of API responses
func domainProfilesToAPI(profiles []domain.Profile) []api.ProfileResponse {
    responses := make([]api.ProfileResponse, len(profiles))
    for i, profile := range profiles {
        responses[i] = *domainToAPIProfile(&profile)
    }
    return responses
}

// Or with pointers
func domainProfilesToAPIPointers(profiles []domain.Profile) []*api.ProfileResponse {
    responses := make([]*api.ProfileResponse, len(profiles))
    for i, profile := range profiles {
        responses[i] = domainToAPIProfile(&profile)
    }
    return responses
}
```

---

## Domain Model ↔ Persisted Entity

### Domain → Entity (for persistence)

```go
// Domain model
type Profile struct {
    ID          string
    UserID      string
    DisplayName string
    Bio         string
    Age         int
    CreatedAt   time.Time
    UpdatedAt   time.Time
}

// Persisted entity
type ProfileEntity struct {
    UserID      string    `db:"user_id"`
    DisplayName string    `db:"display_name"`
    Bio         string    `db:"bio"`
    Age         int       `db:"age"`
    CreatedAt   time.Time `db:"created_at"`
    UpdatedAt   time.Time `db:"updated_at"`
}

// Conversion: Domain → Entity (returns doc ID and entity)
func ProfileToEntity(profile domain.Profile) (string, *ProfileEntity, error) {
    return profile.ID, &ProfileEntity{
        UserID:      profile.UserID,
        DisplayName: profile.DisplayName,
        Bio:         profile.Bio,
        Age:         profile.Age,
        CreatedAt:   profile.CreatedAt,
        UpdatedAt:   profile.UpdatedAt,
    }, nil
}
```

### Entity → Domain (from the database)

```go
// Conversion: Entity → Domain (receives doc ID)
func ProfileToDomain(id string, entity *ProfileEntity) (domain.Profile, error) {
    return domain.Profile{
        ID:          id,
        UserID:      entity.UserID,
        DisplayName: entity.DisplayName,
        Bio:         entity.Bio,
        Age:         entity.Age,
        CreatedAt:   entity.CreatedAt,
        UpdatedAt:   entity.UpdatedAt,
    }, nil
}
```

### With Optional Fields

```go
type Profile struct {
    ID         string
    ArchivedAt time.Time  // Zero value = not archived
}

type ProfileEntity struct {
    ArchivedAt time.Time `db:"archived_at,omitempty"`
}

func ProfileToEntity(profile domain.Profile) (string, *ProfileEntity, error) {
    return profile.ID, &ProfileEntity{
        ArchivedAt: profile.ArchivedAt,  // Zero value stored as-is
    }, nil
}

func ProfileToDomain(id string, entity *ProfileEntity) (domain.Profile, error) {
    return domain.Profile{
        ID:         id,
        ArchivedAt: entity.ArchivedAt,  // Zero value if not set
    }, nil
}
```

### With Nested Structs

```go
type Location struct {
    Latitude  float64
    Longitude float64
}

type Profile struct {
    ID       string
    Location Location
}

type LocationEntity struct {
    Latitude  float64 `db:"latitude"`
    Longitude float64 `db:"longitude"`
}

type ProfileEntity struct {
    Location LocationEntity `db:"location"`
}

func ProfileToEntity(profile domain.Profile) (string, *ProfileEntity, error) {
    return profile.ID, &ProfileEntity{
        Location: LocationEntity{
            Latitude:  profile.Location.Latitude,
            Longitude: profile.Location.Longitude,
        },
    }, nil
}

func ProfileToDomain(id string, entity *ProfileEntity) (domain.Profile, error) {
    return domain.Profile{
        ID: id,
        Location: Location{
            Latitude:  entity.Location.Latitude,
            Longitude: entity.Location.Longitude,
        },
    }, nil
}
```

---

## Complete Flow Example

### Request → Service → Response

```go
// 1. API Request (controller receives this)
var req api.UpdateProfileRequest
json.NewDecoder(r.Body).Decode(&req)

// 2. Convert to domain input
input := profile.UpdateInput{}
if req.DisplayName != nil {
    input.DisplayName = *req.DisplayName
}
if req.Bio != nil {
    input.Bio = *req.Bio
}

// 3. Call service (returns domain model)
profile, err := service.Update(ctx, userID, input)

// 4. Convert domain model to API response
resp := &api.ProfileResponse{
    ID:     profile.ID,
    UserID: profile.UserID,
}
if profile.DisplayName != "" {
    resp.DisplayName = &profile.DisplayName
}
if profile.Bio != "" {
    resp.Bio = &profile.Bio
}

// 5. Return response
httputil.WriteJSON(w, http.StatusOK, resp)
```

---

## Helper Functions for Common Patterns

### Pointer Helpers (use sparingly)

```go
// Convert string to *string (only if not empty)
func stringPtr(s string) *string {
    if s == "" {
        return nil
    }
    return &s
}

// Convert *string to string (with default)
func stringValue(ptr *string) string {
    if ptr == nil {
        return ""
    }
    return *ptr
}

// Convert int to *int (only if > 0)
func intPtr(i int) *int {
    if i <= 0 {
        return nil
    }
    return &i
}

// Convert time.Time to *time.Time (only if not zero)
func timePtr(t time.Time) *time.Time {
    if t.IsZero() {
        return nil
    }
    return &t
}
```

**Usage**:

```go
// Simplified API response conversion
func domainToAPIProfile(p *domain.Profile) *api.ProfileResponse {
    return &api.ProfileResponse{
        ID:          p.ID,
        UserID:      p.UserID,
        DisplayName: stringPtr(p.DisplayName),
        Bio:         stringPtr(p.Bio),
        Age:         intPtr(p.Age),
        CreatedAt:   timePtr(p.CreatedAt),
        UpdatedAt:   timePtr(p.UpdatedAt),
    }
}
```

**Note**: Only use helpers if you have many conversions. For 1-2 fields, inline conversion is clearer.

---

## Quick Reference Table

| From         | To           | Check         | Convert |
| ------------ | ------------ | ------------- | ------- |
| `*string`    | `string`     | `!= nil`      | `*ptr`  |
| `string`     | `*string`    | `!= ""`       | `&val`  |
| `*int`       | `int`        | `!= nil`      | `*ptr`  |
| `int`        | `*int`       | `> 0`         | `&val`  |
| `*time.Time` | `time.Time`  | `!= nil`      | `*ptr`  |
| `time.Time`  | `*time.Time` | `!t.IsZero()` | `&val`  |
| `*[]T`       | `[]T`        | `!= nil`      | `*ptr`  |
| `[]T`        | `*[]T`       | `len(s) > 0`  | `&val`  |

