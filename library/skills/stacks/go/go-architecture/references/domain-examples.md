# Go Domain Examples

Worked domain model shapes. Rules live in [`../SKILL.md`](../SKILL.md); load this only when adding or reviewing types under `internal/core/domain`.

## Domain Example: Profile Model

`internal/core/domain/models.go`:

```go
package domain

import "time"

type Profile struct {
    ID          string
    UserID      string
    DisplayName string
    Bio         string
    Age         int
    CreatedAt   time.Time
    UpdatedAt   time.Time
}
```

---

