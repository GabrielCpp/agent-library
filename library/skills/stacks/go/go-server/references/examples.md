# Go Server Examples

Worked route-delegation methods. Rules live in [`../SKILL.md`](../SKILL.md); load this only when adding or reviewing delegation on the `Server` struct.

## Server Example: Route Delegation

`internal/app/server.go`:

```go
package app

import (
    "net/http"

    "github.com/yourorg/project/internal/app/controllers"
    "github.com/yourorg/project/pkg/api"
)

type Server struct {
    api.Unimplemented
    profile *controllers.ProfileController
}

func NewServer(profileCtrl *controllers.ProfileController) *Server {
    return &Server{
        profile: profileCtrl,
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

---

