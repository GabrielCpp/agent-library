# Go Testing Examples

Worked tests, fixtures, and mock setup. Rules live in [`../SKILL.md`](../SKILL.md); load this only when adding or reviewing Go tests.

## Test Naming

- Use `TestIntegration_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]` for single-scenario tests that start the app server, hit HTTP handlers end-to-end, use local stand-ins for the database, auth or object storage, or verify multiple production layers together.
- Use `Test_<ThingToTest>_Should<ExpectedResult>[_When<AlternateScenario>]` for single-scenario isolated tests that use fakes, local `httptest` dependency boundaries, command helpers, pure functions, in-memory objects, or mocked collaborators.
- Use `TestIntegration_<ThingToTest>_ShouldHandle<ScenarioGroup>` or `Test_<ThingToTest>_ShouldHandle<ScenarioGroup>` when multiple scenarios share setup. In that shape, each `t.Run` name must use `Should<ExpectedResult>[_When<AlternateScenario>]`.
- Do not use plain `TestBehavior` or names that omit `Should`; choose either `TestIntegration_` or `Test_` and keep behavior visible from the top-level test or its subtests.

## Test Example: Controller Integration Tests

`internal/app/controllers/test_helpers_test.go`:

```go
package controllers

import (
    "time"

    "github.com/yourorg/project/internal/core/domain"
    "github.com/yourorg/project/internal/testenv/builders"
)

type profileFixture struct {
    userID    string
    authToken string
    profile   domain.Profile
}

type profileFixtureBuilder struct {
    fixture profileFixture
}

func aProfileFixture() profileFixtureBuilder {
    now := time.Date(2026, time.May, 6, 12, 0, 0, 0, time.UTC)
    profile := builders.AProfile().
        WithID("profile-123").
        WithUserID("user-123").
        WithDisplayName("Alice Johnson").
        WithCreatedAt(now).
        WithUpdatedAt(now).
        Build()

    return profileFixtureBuilder{
        fixture: profileFixture{
            userID:    "user-123",
            authToken: "internal-token-user-123",
            profile:   profile,
        },
    }
}

func (b profileFixtureBuilder) WithUserID(userID string) profileFixtureBuilder {
    b.fixture.userID = userID
    b.fixture.authToken = "internal-token-" + userID
    b.fixture.profile.UserID = userID
    return b
}

func (b profileFixtureBuilder) WithMissingProfile() profileFixtureBuilder {
    b.fixture.profile = domain.Profile{}
    return b
}

func (b profileFixtureBuilder) Build() profileFixture {
    return b.fixture
}
```

`internal/app/controllers/profile_test.go`:

```go
package controllers

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "testing"
    "time"

    "github.com/joho/godotenv"
    "github.com/stretchr/testify/require"

    "github.com/yourorg/project/internal/app"
    "github.com/yourorg/project/internal/core/domain"
    "github.com/yourorg/project/internal/testenv"
    "github.com/yourorg/project/pkg/api"
)

func TestIntegration_GetProfile_ShouldReturnProfile_WhenProfileExists(t *testing.T) {
    _ = godotenv.Load("../../../.env")

    settings, err := app.LoadSettings()
    require.NoError(t, err)

    ctx := t.Context()
    container, err := app.NewContainer(ctx, settings)
    require.NoError(t, err)
    defer container.Close()

    server := app.CreateHTTPServer(container)
    listener, err := net.Listen("tcp", server.Addr)
    require.NoError(t, err)
    go server.Serve(listener)
    defer server.Shutdown(ctx)

    type testData struct {
        userID     string
        profile    domain.Profile
        authToken  string
    }

    buildData := func() testData {
        fixture := aProfileFixture().Build()
        return testData{
            userID:    fixture.userID,
            profile:   fixture.profile,
            authToken: fixture.authToken,
        }
    }

    callFunction := func(t *testing.T, data testData) (*http.Response, error) {
        require.NoError(t, testenv.ResetTable(ctx, container.DB, "profiles"))

        if data.profile.ID != "" {
            require.NoError(t, container.ProfileRepo.Set(ctx, data.profile))
        }

        url := fmt.Sprintf("http://%s:%d/v1/profile", settings.HTTPHost, settings.HTTPPort)
        req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
        require.NoError(t, err)
        req.Header.Set("Authorization", "Bearer "+data.authToken)

        client := &http.Client{}
        return client.Do(req)
    }

    t.Run("ShouldReturnProfile_WhenProfileExists", func(t *testing.T) {
        data := buildData()
        resp, err := callFunction(t, data)
        require.NoError(t, err)
        defer resp.Body.Close()

        require.Equal(t, http.StatusOK, resp.StatusCode)

        var profile api.Profile
        require.NoError(t, json.NewDecoder(resp.Body).Decode(&profile))
        require.Equal(t, "Alice Johnson", *profile.DisplayName)
        require.Equal(t, 28, *profile.Age)
    })

    t.Run("ShouldReturnNotFound_WhenProfileIsMissing", func(t *testing.T) {
        fixture := aProfileFixture().WithMissingProfile().Build()
        data := buildData()
        data.profile = fixture.profile

        resp, err := callFunction(t, data)
        require.NoError(t, err)
        defer resp.Body.Close()

        require.Equal(t, http.StatusNotFound, resp.StatusCode)
    })
}

func TestIntegration_UpdateProfile_ShouldUpdateProfile_WhenInputIsValid(t *testing.T) {
    _ = godotenv.Load("../../../.env")

    settings, err := app.LoadSettings()
    require.NoError(t, err)

    ctx := t.Context()
    container, err := app.NewContainer(ctx, settings)
    require.NoError(t, err)
    defer container.Close()

    server := app.CreateHTTPServer(container)
    listener, err := net.Listen("tcp", server.Addr)
    require.NoError(t, err)
    go server.Serve(listener)
    defer server.Shutdown(ctx)

    type testData struct {
        userID      string
        profile     domain.Profile
        requestBody api.UpdateProfileRequest
        authToken   string
    }

    buildData := func() testData {
        now := time.Now()
        newName := "Updated Name"
        newBio := "Updated bio"

        return testData{
            userID: "user-123",
            profile: domain.Profile{
                ID:          "profile-123",
                UserID:      "user-123",
                DisplayName: "Old Name",
                CreatedAt:   now,
            },
            requestBody: api.UpdateProfileRequest{
                DisplayName: &newName,
                Bio:         &newBio,
            },
            authToken: "internal-token-user-123",
        }
    }

    callFunction := func(t *testing.T, data testData) (*http.Response, error) {
        require.NoError(t, testenv.ResetTable(ctx, container.DB, "profiles"))

        if data.profile.ID != "" {
            require.NoError(t, container.ProfileRepo.Set(ctx, data.profile))
        }

        body, _ := json.Marshal(data.requestBody)
        url := fmt.Sprintf("http://%s:%d/v1/profile", settings.HTTPHost, settings.HTTPPort)
        req, err := http.NewRequestWithContext(ctx, http.MethodPut, url, bytes.NewReader(body))
        require.NoError(t, err)
        req.Header.Set("Authorization", "Bearer "+data.authToken)
        req.Header.Set("Content-Type", "application/json")

        client := &http.Client{}
        return client.Do(req)
    }

    t.Run("ShouldUpdateProfile_WhenInputIsValid", func(t *testing.T) {
        data := buildData()
        resp, err := callFunction(t, data)
        require.NoError(t, err)
        defer resp.Body.Close()

        require.Equal(t, http.StatusOK, resp.StatusCode)

        var profile api.Profile
        require.NoError(t, json.NewDecoder(resp.Body).Decode(&profile))
        require.Equal(t, "Updated Name", *profile.DisplayName)
        require.Equal(t, "Updated bio", *profile.Bio)
    })

    t.Run("ShouldReturnBadRequest_WhenAgeIsInvalid", func(t *testing.T) {
        data := buildData()
        invalidAge := 10
        data.requestBody.Age = &invalidAge

        resp, err := callFunction(t, data)
        require.NoError(t, err)
        defer resp.Body.Close()

        require.Equal(t, http.StatusBadRequest, resp.StatusCode)
    })
}
```

---

