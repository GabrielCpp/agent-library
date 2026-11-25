# Go Repository Examples

A worked entity, mapper, repository, and repository-backed fixture. Rules live in [`../SKILL.md`](../SKILL.md); load this only when adding or reviewing persistence.

## Repository Example: Entity, Mapper, Repository

### Entity Definition

`internal/io/db/entities.go`:

```go
package db

import "time"

type ProfileEntity struct {
    UserID      string    `db:"user_id"`
    DisplayName string    `db:"display_name"`
    Bio         string    `db:"bio"`
    Age         int       `db:"age"`
    CreatedAt   time.Time `db:"created_at"`
    UpdatedAt   time.Time `db:"updated_at"`
}
```

### Mappers

`internal/io/db/mappings.go`:

```go
package db

import (
    "github.com/yourorg/project/internal/core/domain"
)

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

### Repository Instance

`internal/io/db/profile_repository.go`:

```go
package db

import (
    "context"

    "github.com/yourorg/project/internal/core/domain"
)

type ProfileRepository struct {
    *Repository[domain.Profile, ProfileEntity]
}

func NewProfileRepository(conn Conn) *ProfileRepository {
    return &ProfileRepository{NewRepository[domain.Profile, ProfileEntity](
        conn,
        "profiles",
        ProfileToDomain,
        ProfileToEntity,
    )}
}

func (r *ProfileRepository) FindByUserID(ctx context.Context, userID string) (*domain.Profile, error) {
    return r.FindOneBy(ctx, Where("user_id", userID))
}
```

---

