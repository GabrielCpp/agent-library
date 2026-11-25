# Packs — Management Policy

A pack is a **reusable configuration bundle**: a named set of library items
(skills, prompts, workflows, scaffolds) that more than one consuming repo
installs together. Pack names are the **public API** of this library — external
repos reference them by name, so renaming or deleting a pack is a breaking
change for every consumer.

## The rules

1. **No project packs.** A repo's own overlay skills, one-off workflows, and
   anything only that repo uses are selected **directly in the repo's
   `agents.yml`** via the top-level `skills:` / `prompts:` / `workflows:` keys
   (they merge with pack selections):

   ```yaml
   packs:
     - go
     - react-router
     - infra
   skills:
     - projects/<repo>/* # this repo's overlays — no pack needed
   workflows:
     - coder
   ```

2. **Never a single-entry pack.** A pack wrapping one skill or one workflow is
   pure indirection — select the item directly from the consuming repo instead.
   (A glob that expands to several items is fine; one literal entry is not.)

3. **Packs mirror the library categories.** The current set: stack packs
   (`go`, `flutter`, `kmp`, `react-router`, `react-native`, `rust`, `python-workflow`,
   `pulumi`), category packs (`general`, `infra`, `product-planning`, `research`),
   toolchain (`stablemate`, `agent-library`), and shared prompt collections
   (`qa`, `shared-docs`). A new pack must fit one of these
   shapes and have at least two consumers you can name.

## Composition rules

- Prefer `includes:` to compose packs; never copy another pack's skill list.
- A pack may mix `skills:`, `prompts:`, `workflows:`, `scaffolds:`, and
  `includes:`.
- Skill/prompt entries are paths relative to `library/skills/` /
  `library/prompts/` and support globs (`stacks/go/*`, `process/**/*`).
- Scaffold entries are literal scaffold ids from `scaffolds/*.yml` (no globs);
  listing one makes the id available to `farrier scaffold <id>` in every
  consuming repo.
- Keep a pack single-category: a stack pack ships its stack, not UI or infra
  extras. Cross-category needs are expressed by the consuming repo listing both
  packs (e.g. `react-router` + `general`).

## Changing or removing a pack

1. **Check consumers first.** Grep every consuming repo's `agents.yml` (and
   this repo's `agents.yml`) for the pack name before renaming or deleting.
   Update consumers in the same change.
2. **Verify globs still resolve.** A glob pointing at a deleted/renamed library
   dir fails silently at install time. After editing, render into a scratch
   repo (`farrier --repo <scratch> --library <this>/agents` with a minimal
   `agents.yml`) and confirm the expected skills appear under
   `.claude/skills/`.
3. **Keep descriptions honest.** The `description:` is what a human reads when
   choosing packs — it must list what actually ships.

## Hygiene

- No dead entries: when a skill group moves or a prompt dir is deleted, update
  every pack that referenced it in the same commit.
- One pack file = one purpose. If a pack's description needs "and also…" for an
  unrelated concern, that concern belongs in another pack or in the consuming
  repo's own selection.
