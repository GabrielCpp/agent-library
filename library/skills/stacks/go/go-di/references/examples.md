# Go Dependency Injection Examples

Worked container wiring. Rules live in [`../SKILL.md`](../SKILL.md); load this only when wiring dependencies in the app container.

## Wiring Example: Dependency Injection

`internal/app/container.go`:

```go
package app

import (
    "context"

    "go.uber.org/zap"

    "github.com/yourorg/project/internal/app/controllers"
    "github.com/yourorg/project/internal/core/services/profile"
    "github.com/yourorg/project/internal/io/db"
)

type Container struct {
    Settings *Settings
    Logger   *zap.Logger
    DB       db.Conn
    Server   *Server
}

func NewContainer(ctx context.Context, settings *Settings) (*Container, error) {
    // Logger
    logger, err := zap.NewProduction()
    if err != nil {
        return nil, err
    }

    // Database connection
    conn, err := db.Connect(ctx, settings.DatabaseURL)
    if err != nil {
        return nil, err
    }

    // Repository
    profileRepo := db.NewProfileRepository(conn)

    // Service
    profileService := profile.NewService(profileRepo, logger)

    // Controller
    profileController := controllers.NewProfileController(profileService)

    // Server
    server := NewServer(profileController)

    return &Container{
        Settings: settings,
        Logger:   logger,
        DB:       conn,
        Server:   server,
    }, nil
}

func (c *Container) Close() error {
    c.Logger.Sync()
    if c.DB != nil {
        return c.DB.Close()
    }
    return nil
}
```

---

