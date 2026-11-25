# Skills Library

This directory contains reusable skill files that are installed into project repositories as agent instruction sets.

## Structure

The tree has three top-level categories. Each leaf directory is one skill
(`<skill-name>/SKILL.md`), and skill names are unique library-wide.

```
skills/
  stacks/             # language, framework, IaC and cloud pattern libraries, one directory per stack
  process/            # planning, writing and review workflows
  projects/           # repo-specific overlays, one directory per repo, deltas only
```

The merged library an install sees also carries the groups owned by **stablemate's**
`base-library`, edited there: the language-neutral contracts (UI, architecture, testing) and
the agent toolchain every project consumes. Never copy one of them into this overlay. An
overlay copy shadows the public original, so the fork keeps installing while the edits land
upstream and never arrive.

Two rules the tree encodes:

1. **Directory = category, name prefix = unique domain token.** A skill under
   `stacks/` starts with its stack's token (`<stack>-<topic>`), and a skill
   under `projects/` starts with its repo's name (`<repo>-<topic>`). Farrier
   resolves skills by name; duplicate names across groups are a hard install
   error.
2. **Generic vs project is visible in the tree.** Anything under `projects/`
   is a delta over a generic skill and must not duplicate it. Everything else
   must work in any repo.

Shared workflow prompts cannot name a project overlay. They ask for it by tag
with `find_by_tags(...)`.

## Skill anatomy

A skill is a directory, not a file. Beside its `SKILL.md` it may bundle two
directories, which farrier installs alongside the generated skill at the same
relative path:

```
<skill-name>/
  SKILL.md                  # the rules, always loaded when the skill applies
  references/
    examples.md             # long-form material the body points at
  scripts/
    verify.sh               # installed executable; the body calls it
```

- **`references/`** holds what a body should *link to* rather than inline:
  worked examples, lookup tables, long snippets. `SKILL.md` is loaded in full
  whenever the skill applies, so every line in it costs context on every task;
  a reference costs nothing until the agent opens it. Link with the plain
  relative path (`references/examples.md`). It is identical in the library and
  in every installed adapter.
- **`scripts/`** holds commands a procedure would otherwise ask the agent to
  retype from a fenced block. They arrive byte-identical and executable, so the
  body can say "run `scripts/verify.sh`" instead of spelling out ten commands
  the agent will paraphrase differently each time.

Two constraints: assets must be UTF-8 text (binaries are rejected at install;
fetch or generate them at run time), and a skill consumed through
`localInstructions` is inlined into an aggregated `CLAUDE.md` with no directory
of its own, so it cannot rely on bundled assets.

Do **not** express a reference as a sibling skill. A `<skill>-examples` skill
burns a library-wide-unique name on half a topic, duplicates its parent's
`applyTo`, and loads independently of the rules it illustrates.

## Authoring Policy

### 1. Reuse before creating

Before writing a new skill file, check whether a **generic skill** already covers the topic:

| Topic | Look here first |
|---|---|
| Language, framework, IaC or cloud patterns | `stacks/<stack>/` |
| Planning, writing and review workflows | `process/` |
| UI, architecture and testing contracts | stablemate's `base-library` |

If a generic skill covers 80 %+ of the need, **extend it** in the
project-specific skill group (`projects/<repo>/`) rather than duplicating it.
Reference the generic skill from the project-specific one using
`{{ skill_path("<name>") }}` template placeholders.

### 2. Extend, don't duplicate

Project-specific skill files should:

- Import and defer to the matching generic skill for shared patterns.
- Add only what is **project-specific**: module paths, database choices, auth schemes, naming conventions.
- Use `{{ skill_path("<name>") }}` to cross-link sibling or parent skills.
- Be named `<repo>-<topic>` so they never collide with another project's overlay.

**Bad**: copying a stack's architecture rules into `projects/<repo>/<repo>-<topic>/SKILL.md`:

```markdown
# Acme API

Controllers must call services. Services must not import repositories directly...
(duplicated from the stack's architecture skill)
```

**Good**: referencing the generic skill and adding only the delta:

```markdown
# Acme API

Follow the generic stack skill: `{{ skill_path("<stack>-<topic>") }}`.

Acme-specific additions:
- Module: `github.com/example-org/acme/api`
- Database: the engine this repo uses, and the repository skill that covers it
- Auth: the token scheme this repo uses
```

### 3. Generic skills are the source of truth

Changes to shared patterns (error handling, DI conventions, test structure) belong in the **generic skill group** (`stacks/<stack>/`), not in project copies. Project skills inherit the update automatically.

### 4. New skill groups

Only create a new top-level category when the domain is orthogonal to the
existing ones. A new stack goes under `stacks/`, a new repo under
`projects/`. Discuss before adding.
