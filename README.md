# Agents Prompt Library

[![ci](https://github.com/GabrielCpp/agent-library/actions/workflows/ci.yml/badge.svg)](https://github.com/GabrielCpp/agent-library/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

This directory is the canonical multi-repository agent toolkit. It stores source
skills, prompts, root instructions, optional workflows, and pack definitions.
The installer, [farrier](https://github.com/GabrielCpp/stablemate/tree/main/farrier)
from [stablemate](https://github.com/GabrielCpp/stablemate), renders those sources into
the adapter folders expected by Codex, Claude, and GitHub Copilot.

## Layout

- `library/skills/<namespace>/` contains source skill and instruction files.
- `library/prompts/<namespace>/` contains reusable prompts grouped by technology or purpose (no subfolders).
- `library/roots/<namespace>/` contains optional root instructions such as Copilot repository guidance.
- `scaffolds/*.yml` contains scaffold definitions — parameterized file trees applied on demand with `farrier scaffold <id>`.
- `packs/*.yml` defines installable bundles.
- `workflows/<name>/` contains workflow runner assets (YAML graph, prompts, scripts) — the single source of truth for all workflow stages.
- `library/settings/<name>.json` holds harness settings a home install merges, one top-level key per entry.
- `templates/stablemate-config.toml` is a starting stablemate home config, with every path under `$HOME`.
- `farrier` renders selected packs into a target repository.

## Home Setup On A New Machine

Your Claude home comes from this library: skills, guards, helper agents, `~/.claude/CLAUDE.md`
and the settings in `library/settings/claude.json`. MCP servers stay out of the home.
A repository that needs one declares it in its own `.mcp.json`.

1. Clone this repository and `stablemate` under `~/Documents/workspace`.
2. Install farrier and saddlebag from the checkout:

   ```bash
   pipx install -e ~/Documents/workspace/stablemate/farrier
   ```

   ```bash
   pipx install -e ~/Documents/workspace/stablemate/saddlebag
   ```

   The `saddlebag-guard` hook runs `saddlebag guard` before every tool call.
   Without saddlebag on the `PATH`, every tool call reports a hook error.

3. Copy the config template to where stablemate reads its config:

   ```bash
   mkdir -p "$(dirname "$(farrier config path)")"
   ```

   ```bash
   cp -n ~/Documents/workspace/agent-library/templates/stablemate-config.toml "$(farrier config path)"
   ```

   `farrier config path` prints the file for this platform: `~/.config/stablemate/config.toml`
   on Linux, `~/Library/Application Support/stablemate/config.toml` on macOS and
   `%APPDATA%\stablemate\config.toml` on Windows. `$STABLEMATE_CONFIG` overrides it.
   `cp -n` keeps a config you already have.

4. Read the template before you render with it. Its paths start with `$HOME`, which stablemate
   expands on each machine, so move them if your checkouts live elsewhere. Its
   `[user_library.<cli>]` tables choose the packs, hooks, helper agents and settings of each
   harness home. Its `[profiles.<cli>]` tables name the models each run and each helper agent
   uses. Delete the tables of a CLI you do not use.

   Each helper agent installs on the model its `delegates` table names.
   `e2e-web` and `e2e-mobile` start their Playwright and Maestro servers themselves.
   Leave these servers out of every `mcp` table and project config, so no other session starts them.

5. Render the home:

   ```bash
   farrier install --user
   ```

Copilot takes the same home from the template's `[user_library.copilot]` table. Its settings
come from `library/settings/copilot.json`, and its model names use dots, as in `claude-opus-5.5`.

Copilot's shell tool takes no timeout, so `require-timeout` refuses a command until each of its
pipelines starts with `timeout <seconds>` or runs only builtins such as `cd`.
It then wraps the same command in the timeout it learned.
The `clock` guard reads the request time from Copilot's session log. Copilot documents `~/.copilot/settings.json` as JSONC.
A comment written there stops the install, so keep that file plain JSON.

Codex takes its settings from `library/settings/codex.json` and its home from the template's
`[user_library.codex]` table. Farrier merges each key into `~/.codex/config.toml` and keeps your
trusted projects, providers and comments there.

Farrier owns `[features]` whole, so add no key of your own under it.

### Lean Codex and Copilot sessions

Claude starts with no MCP server, no claude.ai connector and only the library's skills.
Start Codex and Copilot the same way with these commands. Keep them as shell aliases.

```bash
S=~/.codex/skills/.system
codex \
  --disable plugins --disable apps --disable computer_use --disable browser_use \
  --disable image_generation --disable tool_suggest --disable goals --disable sleep_tool \
  --disable skill_mcp_dependency_install \
  -c mcp_servers.node_repl.enabled=false \
  -c mcp_servers.playwright.enabled=false \
  -c mcp_servers.maestro.enabled=false \
  -c "skills.config=[{path=\"$S/imagegen/SKILL.md\",enabled=false},{path=\"$S/openai-docs/SKILL.md\",enabled=false},{path=\"$S/skill-creator/SKILL.md\",enabled=false},{path=\"$S/skill-installer/SKILL.md\",enabled=false}]"
```

- The flags remove the computer-use REPL, the sleep tool, the bundled plugins, their skills
  and four system skills. Codex then starts on about 22k tokens instead of 24k.
- Codex keeps its shell, wait, user-input and subagent tools. No flag removes them.
- The fixed Codex system prompt holds about 7k tokens of the rest, and the library's skill list
  about 3k. Replacing the system prompt through `model_instructions_file` would cut it, and it
  would drop Codex's own working rules with it.
- Check a change with `codex debug prompt-input <same flags> | wc -c`. It prints what the model sees.

```bash
copilot \
  --disable-builtin-mcps \
  --disable-mcp-server playwright \
  --disable-mcp-server maestro \
  --no-ask-user \
  --excluded-tools sql
```

- `--disable-builtin-mcps` drops the GitHub MCP server. `gh` in the shell covers the same ground.
- The two `--disable-mcp-server` flags keep Playwright and Maestro out of the main session.
  The `e2e-web` and `e2e-mobile` agents start their own servers.
- `--no-ask-user` removes the question tool, as `AskUserQuestion` is denied in `claude.json`.
- Copilot prints no prompt dump. Run `/context` in a session to read the split between system
  prompt, tools and MCP tools, and add a tool name to `--excluded-tools` when it shows one you
  never use.

Farrier stops when `~/.claude/settings.json` already holds a key from `claude.json` with
another value. Delete that key and install again. Change a shared setting in
`library/settings/claude.json` and run `farrier install --user` on each machine.
A setting you change through `/config` or `/model` shows up in `farrier install --user --check`,
and the next install puts the library's value back.

## Naming Rules — Skills

- One file per skill under `library/skills/<namespace>/`.
- File name is the skill's base name without namespace prefix: `db.md`, `grpc.md`, `testing.md`.
- The installer prepends the namespace as a prefix automatically via `public_name`:
  `<repo>/db.md` → installed as `<repo>-db`.
- Exception: if the filename already starts with the namespace prefix, it passes through unchanged:
  `<repo>/<repo>-grpc.md` → installed as `<repo>-grpc` (no double prefix).
- Use technology namespaces (`go/`, `flutter/`, `pulumi/`) for stack guidance reusable across repos.
- Use a repo namespace (`<repo>/`) for product-specific rules.
- Never use dots in skill file names or pack names.

## Naming Rules — Prompts

- One file per prompt under `library/prompts/<namespace>/`.
- **No subfolders within a namespace.** All prompts for a namespace sit flat in its directory.
- Namespace is one of:
  - A technology name: `go/`, `flutter/`, `planning/`, `review/`, `testing/`, `docs/`, `misc/`
  - A purpose: `dev/`, `qa/`, `review/`
  - A product concept: `product-planning/`, `instruction-builder/`
- Do not use a `shared/` namespace — every prompt belongs to a named technology or purpose.
- File name is the prompt's base name; the installer prepends the repo prefix at install time.
- **Workflow prompts** live in `workflows/<workflow-name>/prompts/` and are the single source of truth (not in library/).

## Naming Rules — Packs

- One YAML file per pack under `packs/`.
- Pack name is the install unit name in kebab-case: `react-router`, `productivity`.
- Each pack lists `skills`/`prompts` glob patterns, `workflows` names, and/or `scaffolds` ids.
- Glob patterns match paths relative to the relevant library root
  (e.g. `qa/*` matches all files directly under `library/prompts/qa/`).
- `scaffolds` entries are literal scaffold ids from `scaffolds/*.yml` — listing one makes it
  available to `farrier scaffold` in every repo that installs the pack.

## Prompt Namespaces Reference

| Namespace              | Contents                                                            |
| ---------------------- | ------------------------------------------------------------------- |
| `planning/`            | Plan-story, implement-plan, refine-plan, write-story prompts        |
| `review/`              | Self-review, code review, PR comment, validate-code prompts         |
| `testing/`             | Test coverage expansion prompts                                     |
| `docs/`                | Documentation generation prompts                                    |
| `misc/`                | Miscellaneous utility prompts                                       |
| `product-planning/`    | MVP roadmap, epic, and story writing prompts                        |
| `instruction-builder/` | Repo exploration and instruction generation prompts                 |
| `go/`                  | Go-specific fix prompts                                             |
| `flutter/`             | Flutter-specific fix and check prompts                              |
| `qa/`                  | QA planning prompts (plan-qa, plan-qa-local)                        |

## Reusable Packs

Packs are reusable bundles only — a repo's own overlays and workflows are
selected directly in its `agents.yml` via top-level `skills:` / `workflows:`
(see `packs/AGENTS.md`).

- `flutter`, `go`, `kmp`, `pulumi`, `react-native`, `react-router`, `rust`, `python-workflow` install the reusable stack skills.
- `general` comes from stablemate's base library. It installs the language-neutral architecture, testing, UI and method skills that the stack skills build on.
- `infra` installs cloud/env tooling conventions (GCP CI/IAM, dev-stack hardening, CLI anti-hang).
- `product-planning` installs the epic/story planning skills and prompts.
- `research` installs the autonomous-researcher skills, prompts, and gate-loop workflow.
- `stablemate` comes from stablemate's base library. It installs the toolchain and library-maintenance skills.
- `shared-docs` installs the docs prompts and makes the standard `docs/` scaffold available (`farrier scaffold shared-docs`).
- `qa` installs shared QA planning prompts.

Workflows are registered per repo, e.g. `workflows: [coder]` for the unified
coder (mode=story / mode=epic) or `workflows: [author]` for the epic author.

## Repository Config

Each consuming repository should commit a `agents.yml` file:

```yaml
repo:
  name: myrepo # used as the install prefix for all skill and prompt names

agents:
  claude: true # generate .claude/ outputs
  codex: true # generate .codex/ outputs
  copilot: true # generate .github/ outputs

packs:
  - myrepo # repo-specific skills and prompts
  - qa # QA planning prompts

exclude:
  # optional: suppress specific prompts the repo does not need
  prompts:
    - planning/write-*

localInstructions:
  # writes a CLAUDE.md inside each listed directory containing the named skill
  # — Claude auto-loads it when working on files in that directory
  - skill: myrepo-db
    paths:
      - pkg/db
  - skill: myrepo-grpc
    paths:
      - cmd
```

Install into a repo:

```bash
farrier --repo /path/to/repo
```

Check generated files in CI:

```bash
farrier --repo /path/to/repo --check
```

## Generated Outputs

Claude:

- `.claude/skills/<skill-name>/SKILL.md`
- `.claude/commands/<prompt-name>.md`
- selected local `CLAUDE.md` files (from `localInstructions`)

Codex:

- `.agents/skills/<skill-name>/SKILL.md`
- `.agents/prompts/<prompt-name>.prompt.md`
- selected local `AGENTS.md` and `CODEX.md`

GitHub Copilot:

- `.github/copilot-instructions.md`
- `.github/instructions/<skill-name>.instructions.md`
- `.github/skills/<skill-name>/SKILL.md`
- `.github/prompts/<prompt-name>.prompt.md`

By default, the installer adds ignore rules only for generated GitHub adapter files and optional
workflow assets. Repositories decide for themselves whether Codex, Claude, and local
`AGENTS.md` / `CODEX.md` / `CLAUDE.md` adapter files should be tracked or ignored.

## Scaffolds

Scaffolds are YAML definitions under `scaffolds/*.yml` (a sibling of `library/`). They are **not**
rendered at install time — an agent (or human) applies one on demand when standing up a new
service or repo. A scaffold's job is to make the agent faster: it seeds structure and boilerplate,
and the agent then fills the seeded directories with real content (service code, actual docs) —
scaffold output is a starting skeleton, never the deliverable:

```bash
farrier scaffold                   # list the scaffolds available to this repo
farrier scaffold go-service --param dir=api
```

Each `scaffolds/*.yml` file maps one or more scaffold ids to a definition:

```yaml
go-service:
  description: Seed a Go service folder with a curated .gitignore.
  params:
    dir: api # default value; `~` (null) = required
  tree:
    $dir/.gitignore: | # string = inline file content
      bin/
    $dir/docs/README.md: { url: "https://raw.githubusercontent.com/..." }
    $dir/docs/specs: # empty directory
```

- `params` declares the arguments `--param key=value` may set; a `~`/null default makes the
  param required. `$param` / `${param}` placeholders substitute in tree paths (strictly — an
  unknown param errors) and inline content (leniently, so literal `$` in file bodies survives).
  Built-ins `$repo_name` (target repo directory name, kebab-cased) and `$repo_title` are always
  available.
- `tree` keys are output paths (may contain `/`, or nest as sub-mappings); values are inline
  content (string), `{url: ...}` (downloaded at scaffold time), or null/`{}` — a bare
  `some/dir:` key creates an empty directory.
- Scaffold ids share one flat namespace across all definition files — a duplicate id is a hard
  error, like a duplicate skill name.

**Placement is a param, not a library path** — service folder names are project-specific (one
repo keeps its Flutter app in `app/`, another in `mobile/`), so each scaffold takes a `dir`
param instead of baking a folder into the library.

The `scaffolds:` list in a pack or in `agents.yml` names the scaffold ids available to the
consuming repo — `farrier scaffold <id>` refuses ids outside that catalog (when the repo has no
`agents.yml` yet, every library scaffold is available, so a repo can be bootstrapped from
scratch). Current scaffolds: `go-service`, `flutter-app`, `kmp-app`, `pulumi-infra`, `react-router-web`, `rust-workspace`
(curated per-stack `.gitignore` seeds) and `shared-docs` (the standard `docs/` knowledge
hierarchy).

Every scaffolded file is a **seed**: an existing file is never overwritten, so re-running a
scaffold is safe and the repository owns every file after first write. Scaffolds are invisible
to `farrier --check` — they are repo content, not generated adapters.

## Template Values

Sources are rendered with Jinja2. Files can read repository-local values from `agents.yml` via
`{{ template.some_key }}`. Shared sources should provide defaults with the `default` filter so
they remain installable in other repositories:

```md
Use `{{ template.go_cli_name | default("appctl") }}` for CLI examples.
```

The Go QA skills start and stop local dependencies with `template.dev_stack_up` and
`template.dev_stack_down`, which default to `make -C <api_path> dev-stack-up` and
`dev-stack-down`. Set them when a repository brings its stack up another way.

Reusable prompt packs should keep product-specific nouns, example resources, local document paths,
and tool names behind `template.*` values. See `agents.example.yml` for a fuller example.

Reusable TypeScript stack skills use path templates so they can install into monorepos:

```yaml
packs:
  - react-native
  - react-router
skills:
  - stacks/typescript/typescript-backend

template:
  ts_backend_path: api
  react_native_path: app
  react_router_path: advisor-dashboard
  ts_backend_codegen_command: cd api && bun run generate
  react_native_codegen_command: cd app && npm run generate
  react_router_codegen_command: cd advisor-dashboard && CODEGEN_AUTH_TOKEN=<dev-token> npm run generate
```

The renderer exposes `repo.name`, `repo.prefix`, and `repo.root`. `vars` is accepted as an alias
for `template` for compatibility, but new configs should prefer `template`.

## Story Coder Workflow

The optional `story-coder` pack installs the unified coder workflow, which assumes the shared docs lifecycle contract under
`docs/epics/**` and `docs/specs/**`. It supports two modes via the `mode` input: `story` (single story, no queue/CI) and `epic` (multi-story queue + CI/PR gating).
Repository-specific execution details live under `agents.yml` at `workflow.epicCoder`: mode, optional epic queue path, generated prompt names, Docker image/container path, QA preflight service/CLI settings, success-gate commands, and autonomous unblock budgets.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before you open a pull request. Report a
vulnerability through [SECURITY.md](SECURITY.md), not a public issue. Everyone who takes
part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

The library is released under the [MIT License](LICENSE).
