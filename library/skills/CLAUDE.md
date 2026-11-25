# Skills Library — Agent Instructions

## Layout: three categories here, prefixed names

- `stacks/<stack>/`: language, framework, IaC and cloud pattern libraries, named `<stack>-<topic>`
- `process/`: planning, writing and review workflows
- `projects/<repo>/`: repo-specific overlays, named `<repo>-<topic>`

More groups reach the merged library from **stablemate's** `base-library`, and are edited
there rather than here: the language-neutral contracts (UI, architecture, testing) and the
agent toolchain every project consumes. Globs in `packs/` resolve against them too. Copying
one back into this overlay shadows the public original with a fork that silently stops
receiving its edits.

**Naming rule:** every skill's `name:` is unique library-wide, a stack or
project skill starts with its stack's or repo's token, and the skill's
directory name equals its `name:`. Farrier resolves by name — a
duplicate name across groups is a hard install error.

## A skill is a directory: SKILL.md + references/ + scripts/

`SKILL.md` is loaded in full whenever the skill applies, so it holds **rules
only**. Anything the body should *point at* rather than state goes beside it,
and farrier installs it at the same relative path:

- `references/*.md` — worked examples, lookup tables, long snippets. Link with
  the plain relative path (`[references/examples.md](references/examples.md)`);
  that string is identical in the library and in every installed adapter.
- `scripts/*` — installed executable and byte-identical. Prefer
  "run `scripts/verify.sh`" over a fenced block of ten commands the agent will
  paraphrase differently each time.

Assets must be UTF-8 text; binaries are rejected at install. A skill consumed
through `localInstructions` is inlined into an aggregated `CLAUDE.md` and has no
directory, so it cannot rely on bundled assets.

**Never create a `<skill>-examples` sibling skill.** It burns a
library-wide-unique name on half a topic, duplicates its parent's `applyTo`, and
loads independently of the rules it illustrates. Use `references/`.

## Reuse before creating

When asked to add or update a skill, **always check whether a generic skill already covers the topic** before writing a new file.

Project-specific skill groups (`projects/<repo>/`) extend the generic ones. They must **not** duplicate rules already stated in a generic skill.

## Decision tree

```
Does a generic skill in this library already cover the topic?
│
├─ YES → Does a project-specific skill already import it?
│         ├─ YES → Add only the project-specific delta to that file.
│         └─ NO  → Create a project-specific file that imports the generic
│                  skill with {{ skill_path("<name>") }} and adds
│                  only the project-specific delta.
│
└─ NO  → Does any existing skill partially cover it?
          ├─ YES → Extend that skill file with the missing content.
          └─ NO  → Create a new generic skill file in the appropriate
                   category (stacks/<stack> or process, or, for a
                   language-neutral contract, in stablemate's
                   base-library).
                   A new top-level category needs discussion first.
```

## Rules

1. **Extend, don't duplicate.** If a stack skill defines layer boundaries, do not restate them in a project overlay. Reference the generic skill.
2. **Generic skills are the source of truth.** Changes to shared patterns belong in the generic group so all projects inherit them.
3. **Project skills add deltas only.** Module path, database engine, auth scheme, naming conventions — anything that diverges from the generic skill.
4. **Prefix project overlays with the repo name** (`<repo>-<topic>`). Shared workflow prompts cannot name a project overlay. They ask for it by tag with `find_by_tags(...)`.
5. **Keep packs in sync.** Skills are shipped by `agents/packs/*.yml` path globs; when you move or rename a skill, update the packs in the same change (see `agents/packs/CLAUDE.md`).

## Example: correct extension pattern

A project overlay imports the generic skill and adds only the repo's specifics:

```markdown
# Acme Web App

Follow the generic stack skill: `{{ skill_path("<stack>-<topic>") }}`.

Acme-specific additions:
- Auth: the token scheme and the hook that reads it
- API client: generated from the repo's OpenAPI contract
- Data fetching: the one layer allowed to call the API
```

The generic stack skill holds the full patterns shared by every project.
