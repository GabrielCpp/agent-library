# Integration suite examples

Two full suites in the mandatory Arrange-Act-Assert shape. The shape's rules live in [`../SKILL.md`](../SKILL.md).

The Act/seed mechanics differ by stack — a server backed by a local database is exercised with a real `http.Client`; a handler-level test is exercised with `httptest`. The *shape* is identical either way.

## Server on a local database with a real http.Client

```go
func TestIntegration_GetProfile_ShouldReturnProfile_WhenProfileExists(t *testing.T) {
    ts := setupTestServer(t)

    type testData struct {
        userID    string
        profile   domain.Profile
        authToken string
    }

    buildData := func() testData {
        return testData{
            userID:    "user-123",
            profile:   builders.AProfile().WithUserID("user-123").Build(),
            authToken: "internal-token-user-123",
        }
    }

    callFunction := func(t *testing.T, data testData) (*http.Response, error) {
        ctx := t.Context()
        require.NoError(t, testenv.ResetTable(ctx, ts.Container.DB, "profiles"))
        require.NoError(t, ts.Container.ProfileRepo.Set(ctx, data.profile))

        url := fmt.Sprintf("http://%s:%d/v1/profile", ts.Settings.HTTPHost, ts.Settings.HTTPPort)
        req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
        req.Header.Set("Authorization", "Bearer "+data.authToken)
        return (&http.Client{}).Do(req)
    }

    t.Run("ShouldReturnProfile_WhenProfileExists", func(t *testing.T) {
        data := buildData()
        resp, err := callFunction(t, data)
        require.NoError(t, err)
        defer resp.Body.Close()
        require.Equal(t, http.StatusOK, resp.StatusCode)
        // ...
    })
}
```

## Handler-level with httptest

For handler-level tests (real DB or in-process handler exercised with `httptest`), the same shape applies — a single `callFunction(t, data)` driven entirely by `testData`, with the action data-driven instead of split across per-endpoint helpers:

```go
func TestIntegration_ProfileEndpoints_ShouldHandleProfileScenarios(t *testing.T) {
    // --- suite setup: real deps wired ONCE ---
    sqlxDB := mustConnectTestDB(t)                              // t.Cleanup closes it
    handler := buildHandler(t, sqlxDB, acceptedToken, identity) // accepted token/identity fixed here

    type testData struct {
        method     string
        path       string
        body       any
        authToken  string
        seedEmail  string
        expectCode int
    }

    buildData := func() testData {
        return testData{
            method:     http.MethodPut,
            path:       "/profile",
            authToken:  acceptedToken,
            seedEmail:  "alice@test.example",
            expectCode: http.StatusOK,
        }
    }

    callFunction := func(t *testing.T, data testData) *httptest.ResponseRecorder {
        t.Helper()
        // Arrange: isolate + seed for this scenario.
        seedUser(t, sqlxDB, data.seedEmail)
        // Act: build the request ENTIRELY from data — no per-endpoint helper.
        var bodyReader io.Reader
        if data.body != nil {
            raw, _ := json.Marshal(data.body)
            bodyReader = bytes.NewReader(raw)
        }
        req := httptest.NewRequest(data.method, data.path, bodyReader)
        req.Header.Set("Authorization", "Bearer "+data.authToken)
        rr := httptest.NewRecorder()
        handler.ServeHTTP(rr, req)
        return rr
    }

    t.Run("ShouldReturn409_WhenEmailChangedToDuplicate", func(t *testing.T) {
        data := buildData()
        data.body = map[string]string{"email": existingOtherEmail}
        data.expectCode = http.StatusConflict
        rr := callFunction(t, data)
        require.Equal(t, data.expectCode, rr.Code)
    })

    t.Run("ShouldReturn401_WhenTokenIsNotAccepted", func(t *testing.T) {
        data := buildData()
        data.authToken = "wrong-token" // no new handler — the accepted token lives in setup
        rr := callFunction(t, data)
        require.Equal(t, http.StatusUnauthorized, rr.Code)
    })
}
```
