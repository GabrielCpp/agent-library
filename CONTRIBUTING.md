# Contributing to agent-library

Thanks for looking. This library holds the skills, prompts, hooks, helper agents and packs
that [farrier](https://github.com/GabrielCpp/stablemate/tree/main/farrier) renders into a
repository or a home folder for Claude Code, Codex and Copilot. A change here changes what
an agent reads, so the bar is the bar for code.

## Setting up

```bash
git clone https://github.com/GabrielCpp/agent-library.git
git clone https://github.com/GabrielCpp/stablemate.git
pipx install -e stablemate/farrier
```

The [README](README.md) walks through a full home setup. To try a change, render it into
a scratch repository with `farrier install --repo <path>` and read what came out.

## Where a change belongs

- A language, framework or cloud pattern goes under `library/skills/stacks/<stack>/`.
- A planning, writing or review method goes under `library/skills/process/`.
- A language-neutral contract (UI, architecture, testing) and the stablemate toolchain
  skills live in stablemate's `base-library`. Edit them there, not here. A copy in this
  library shadows the original and stops receiving its edits.
- Repository-specific overlays never land here. They belong in the consuming repository.

[`library/skills/AGENTS.md`](library/skills/AGENTS.md) and [`packs/AGENTS.md`](packs/AGENTS.md)
hold the naming and layout rules. The README's naming sections repeat the short version.

## Writing a skill

- A skill is a directory named after its `name:`. The name is unique across the library and
  starts with its stack token.
- `SKILL.md` holds rules only, because an agent loads it whole. Examples and lookup tables go
  in `references/`. Commands an agent should run verbatim go in `scripts/`.
- The `description:` decides when an agent loads the skill. Write the situations that should
  trigger it, not a summary of its body.
- Keep product nouns behind `{{ template.* | default("...") }}` values so the skill installs
  in any repository.

## Keep it public

This repository is public. No client or employer name, private hostname, credential or
personal path may enter a tracked file or a commit message. Use neutral placeholders:
`acme` or `globex` for a client, `api-service` or `web-app` for a repository, `example.com`
for a host.

## Tests

The hooks and policies carry pytest suites. Run them from the repository root before you
open a pull request:

```bash
uvx pytest library
```

CI runs the same command on every pull request.

## Commit messages

Subjects follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <lowercase imperative description>
```

- `type` is `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `ci` or `chore`.
- `scope` names the area you touched, such as `hooks`, `settings`, `go` or `react-router`.
  Omit it for a change across the library.
- Keep one concern per commit and the subject under 72 characters.

## Opening a pull request

- Branch from `main` and keep the pull request to one concern.
- Say why in the description. The diff already says what.
- A new hook or policy behaviour needs a test that fails without it.
- Renaming or deleting a pack breaks every repository that selects it. Call it out.

## Reporting a vulnerability

See [SECURITY.md](SECURITY.md). Please do not open a public issue for one.

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
