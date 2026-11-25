---
name: go-cli-commands
description: "Go Cobra command authoring: flags, container.go, root.go, main.go, envconfig config, RunE, dry-run, output and errors, command tests. Load when writing or changing a Cobra command, its flags, output or tests inside a CLI."
applyTo: 'api/cmd/**/*.go'
tags: [go, cli, standards]
---

# Go CLI — Command Authoring Patterns

See {{ skill_link("go-cli") }} for repo layout, module rules, and directory structure.

When authoring or changing CLI tests under `api/cmd/**`, also load `{{ skill_path("go-testing") }}`. The CLI command guidance does not replace the canonical Go test guidance.

---

## Command naming conventions

| Pattern | Rule | Example |
|---|---|---|
| Resource group | Plural noun | `profiles`, `matches`, `moderation` |
| Action | Verb | `create`, `list`, `delete`, `backfill`, `seed` |
| Full command | `<group> <verb>` | `{{ template.go_cli_name | default("appctl") }} profiles create` |
| Dev helpers | Under `dev` group | `{{ template.go_cli_name | default("appctl") }} dev seed` |
| Flags | `--kebab-case` | `--user-id`, `--dry-run`, `--output` |
| Positional args | Zero or one, named in `Use` | `approve <photo-id>` |

**Never** use underscores in flag/command names.
**Never** create top-level verb commands (`{{ template.go_cli_name | default("appctl") }} create-profile`) — group by resource first.

---

## container.go — CLI-specific DI

The CLI container is **completely independent** from `api/internal/app/container.go`. It holds only what the CLI commands need — no HTTP stack, no controllers, no WebSocket.

Wire it from `api/pkg/db/` (repositories) only. Commands call repository methods directly, without a service layer, unless a service is promoted to `api/pkg/`.

```go
// api/cmd/{{ template.go_cli_name | default("appctl") }}/container.go
package main

import (
    "context"
    "fmt"

    "go.uber.org/zap"
    pkgdb "{{ template.go_module | default("github.com/yourorg/project/api") }}/pkg/db"
)

type Container struct {
    Logger      *zap.Logger
    DB          pkgdb.Conn
    ProfileRepo *pkgdb.ProfileRepository
    MatchRepo   *pkgdb.MatchRepository
}

type contextKey struct{}

func newContainer(ctx context.Context, cfg *Settings) (*Container, error) {
    logger, _ := zap.NewDevelopment()

    conn, err := pkgdb.Connect(ctx, cfg.DatabaseURL)
    if err != nil {
        return nil, fmt.Errorf("database: %w", err)
    }

    return &Container{
        Logger:      logger,
        DB:          conn,
        ProfileRepo: pkgdb.NewProfileRepository(conn),
        MatchRepo:   pkgdb.NewMatchRepository(conn),
    }, nil
}

func withContainer(ctx context.Context, c *Container) context.Context {
    return context.WithValue(ctx, contextKey{}, c)
}

func containerFromContext(ctx context.Context) (*Container, error) {
    c, ok := ctx.Value(contextKey{}).(*Container)
    if !ok || c == nil {
        return nil, fmt.Errorf("container not initialised — was PersistentPreRunE called?")
    }
    return c, nil
}

func (c *Container) close() {
    if c.DB != nil     { c.DB.Close() }
    if c.Logger != nil    { _ = c.Logger.Sync() }
}
```

**Never** call `newContainer` inside a command's `RunE` — build it once in `PersistentPreRunE`.
**Never** import or reuse the main app's `container.go` — the CLI wires only what it needs.

---

## root.go

```go
// api/cmd/{{ template.go_cli_name | default("appctl") }}/root.go
package main

var (
    cfgFile string
    dryRun  bool
    verbose bool
)

func newRootCmd(metadata binaryMetadata) *cobra.Command {
    root := &cobra.Command{
        Use:           "{{ template.go_cli_name | default("appctl") }}",
        Short:         "Platform operator CLI",
        SilenceUsage:  true,  // don't dump usage on every error
        SilenceErrors: true,  // main.go is the single error printer
    }

    root.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default ~/.{{ template.go_cli_name | default("appctl") }}/config.yaml)")
    root.PersistentFlags().BoolVar(&dryRun, "dry-run", false, "print what would happen without making changes")
    root.PersistentFlags().BoolVar(&verbose, "verbose", false, "enable verbose output")

    root.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
        cfg, err := loadConfig(cfgFile)
        if err != nil {
            return err
        }
        c, err := newContainer(cmd.Context(), cfg)
        if err != nil {
            return err
        }
        cmd.SetContext(withContainer(cmd.Context(), c))
        return nil
    }

    root.AddCommand(newProfilesCmd())
    root.AddCommand(newMatchesCmd())
    root.AddCommand(newModerationCmd())
    root.AddCommand(newDevCmd())
    return root
}
```

---

## main.go

```go
// api/cmd/{{ template.go_cli_name | default("appctl") }}/main.go
package main

import (
    "context"
    "fmt"
    "os"
    "runtime/debug"
)

type binaryMetadata struct {
    Version string
    Commit  string
}

func main() {
    if err := newRootCmd(readBinaryMetadata()).ExecuteContext(context.Background()); err != nil {
        fmt.Fprintf(os.Stderr, "error: %v\n", err)
        os.Exit(1)
    }
}

func readBinaryMetadata() binaryMetadata {
    info, ok := debug.ReadBuildInfo()
    if !ok {
        return binaryMetadata{Version: "dev", Commit: "unknown"}
    }

    metadata := binaryMetadata{Version: "dev", Commit: "unknown"}
    if info.Main.Version != "" && info.Main.Version != "(devel)" {
        metadata.Version = info.Main.Version
    }
    for _, setting := range info.Settings {
        if setting.Key == "vcs.revision" && setting.Value != "" {
            metadata.Commit = setting.Value
        }
    }
    return metadata
}
```

**Always** use `ExecuteContext` — never `Execute`.
**Never** use package-level `version` or `commit` variables populated through `-ldflags`. CLI version metadata should come from the Go binary's embedded build info via `runtime/debug.ReadBuildInfo()`, with deterministic metadata injection only in tests.

---

## config.go

```go
// api/cmd/{{ template.go_cli_name | default("appctl") }}/config.go
package main

import (
    "os"
    "path/filepath"

    "github.com/joho/godotenv"
    "github.com/kelseyhightower/envconfig"
)

type Settings struct {
    DatabaseURL   string `envconfig:"DATABASE_URL" required:"true"`
    StorageBucket string `envconfig:"STORAGE_BUCKET" required:"true"`
}

// loadConfig: env vars win over config file, which wins over .env
func loadConfig(cfgFile string) (*Settings, error) {
    _ = godotenv.Load()
    if cfgFile == "" {
        home, _ := os.UserHomeDir()
        cfgFile = filepath.Join(home, ".{{ template.go_cli_name | default("appctl") }}", "config.yaml")
    }
    _ = godotenv.Overload(cfgFile) // OK if missing

    var s Settings
    return &s, envconfig.Process("", &s)
}
```

**Never** store credentials in the config file. The driver reads them from the environment, or from a key file whose path the environment names.

---

## commands/<group>.go — anatomy

Each file in `commands/` declares one group command and all its subcommands. All belong to `package main`.

```go
// api/cmd/{{ template.go_cli_name | default("appctl") }}/commands/profiles.go
package main

import (
    "fmt"
    "github.com/spf13/cobra"
)

// Group — no RunE; running `{{ template.go_cli_name | default("appctl") }} profiles` prints help automatically
func newProfilesCmd() *cobra.Command {
    cmd := &cobra.Command{Use: "profiles", Short: "Manage user profiles"}
    cmd.AddCommand(newProfilesCreateCmd())
    cmd.AddCommand(newProfilesListCmd())
    return cmd
}

// Subcommand flags in a private struct — never package-level vars
type profilesCreateFlags struct {
    userID      string
    displayName string
}

func newProfilesCreateCmd() *cobra.Command {
    f := &profilesCreateFlags{}
    cmd := &cobra.Command{
        Use:   "create",
        Short: "Create a profile for an existing identity-provider user",
        Args:  cobra.NoArgs,
        RunE:  func(cmd *cobra.Command, _ []string) error { return runProfilesCreate(cmd, f) },
    }
    cmd.Flags().StringVar(&f.userID, "user-id", "", "Identity-provider user ID (required)")
    cmd.Flags().StringVar(&f.displayName, "display-name", "", "Display name (required)")
    _ = cmd.MarkFlagRequired("user-id")
    _ = cmd.MarkFlagRequired("display-name")
    return cmd
}

func runProfilesCreate(cmd *cobra.Command, f *profilesCreateFlags) error {
    c, err := containerFromContext(cmd.Context())
    if err != nil {
        return err
    }

    if dryRun {
        fmt.Fprintf(cmd.OutOrStdout(), "[dry-run] would create profile for %s\n", f.userID)
        return nil
    }

    profile, err := c.ProfileRepo.Create(cmd.Context(), f.userID, f.displayName)
    if err != nil {
        return fmt.Errorf("create profile: %w", err)
    }

    fmt.Fprintf(cmd.OutOrStdout(), "created profile %s\n", profile.ID)
    return nil
}
```

**Rules:**
- `RunE` is a one-liner delegating to `runXxx(cmd, flags)`.
- Output → `cmd.OutOrStdout()`. Errors → `return fmt.Errorf("context: %w", err)`.
- Never `os.Exit`, `log.Fatal`, or print + return the same error.
- Check `dryRun` before any mutation.

---

## Output conventions

| Situation | Format |
|---|---|
| Data result | One line per record; `--output json` for scripting |
| Progress | Plain present tense: `"seeding 50 profiles..."` |
| Dry-run | Prefix every line with `[dry-run]` |
| Errors | Lowercase, no trailing period, wrapped with context |

```go
// --output json support on list commands
if outputJSON {
    return json.NewEncoder(cmd.OutOrStdout()).Encode(results)
}
```

---

## Error handling

```go
// ✅ correct — root prints it once
return fmt.Errorf("list profiles: %w", err)

// ❌ double-prints
fmt.Fprintf(os.Stderr, "error: %v\n", err)
return err
```

---

## Testability and dependencies

Prefer explicit interfaces over package-level function variables.

Use small interfaces for external effects such as:

- calling another Cobra command
- issuing backend HTTP requests
- creating users in the local identity provider
- running `maestro`, `adb`, Docker, or other processes
- reading or writing files outside a temporary test directory

Good pattern:

```go
type smokeExternalCommands interface {
    DevHealthCheck(cmd *cobra.Command, cfg *configFlags, flags *devHealthFlags) error
    FixtureSeed(cmd *cobra.Command, flags *fixtureFlags, cfg *configFlags) error
    Maestro(ctx context.Context, flowPath, screenshotDir string) error
}

type defaultSmokeExternalCommands struct{}

func (defaultSmokeExternalCommands) DevHealthCheck(cmd *cobra.Command, cfg *configFlags, flags *devHealthFlags) error {
    return runDevHealthCheck(cmd, cfg, flags)
}
```

Tests pass a fake implementation:

```go
runner := smokeRunner{commands: fakeSmokeCommands{seed: seedFunc}}
```

Avoid this pattern except for rare process-wide constants:

```go
var runThingForTest = runThing
```

It makes production code harder to read, spreads hidden mutable state across tests, and becomes fragile under parallel tests. If a command needs multiple replaceable behaviors, define one narrow interface that names the dependency and pass it through a runner, constructor, or context.

Keep `RunE` small. It should construct flags, retrieve or create the runner/dependencies, and delegate to a named function or method.

---

## Testing commands

```go
func TestProfilesCreate(t *testing.T) {
    c := &Container{ProfileRepo: &mockProfileRepo{}}
    ctx := withContainer(t.Context(), c)

    root := newRootCmd("test")
    buf := &bytes.Buffer{}
    root.SetOut(buf)
    root.SetArgs([]string{"profiles", "create", "--user-id", "u-1", "--display-name", "Alice"})

    require.NoError(t, root.ExecuteContext(ctx))
    require.Contains(t, buf.String(), "u-1")
}
```

**Never** test via `os.Exec`. **Never** hit a real database in unit tests — mock the repositories.

