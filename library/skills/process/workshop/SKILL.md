---
name: workshop
description: "Interactive story-writing via `/workshop` subcommands (init, research, thread, compare, decide, split, write, refine, status). Load when a complex feature needs research and tradeoffs before stories exist, on /workshop, or to refine stories"
tags: [process, planning, research]
---

# Interactive Story Workshop

Use this for complex features where you need to:

- Gather research about how systems work and interact
- Explore multiple alternative approaches (threads) and weigh tradeoffs
- Commit to one approach, then decompose into properly-scoped stories
- Refine stories interactively before promoting them

## Command: `/workshop <subcommand> [args]`

| Subcommand            | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| `init <dir>`          | Initialize a workshop in a project directory          |
| `research [topic]`    | Explore codebase, gather findings on a specific topic |
| `thread <name>`       | Create or develop an alternative approach             |
| `compare`             | Generate/refresh side-by-side comparison table        |
| `decide <thread>`     | Commit to a thread, reject others                     |
| `split`               | Propose story breakdown from the chosen thread        |
| `write [story-slug]`  | Write story files (one or all)                        |
| `refine [story-slug]` | Iterate on stories with user feedback                 |
| `status`              | Show current workshop state                           |

There is no `promote` subcommand — promotion means creating the Jira issues from `stories/` (see "Promotion" below). Stories stay in the workshop's `stories/` directory; that's their permanent location.

---

## Subcommand Behaviors

### `init <dir>`

Create workshop structure in the specified directory. Does NOT touch existing files.

**Steps:**

1. Read the directory to identify existing files (preserve them)
2. Ask the user for the topic/goal (1-2 sentence problem statement)
3. Ask the user for the Jira epic key this project will sync under, if known (e.g. `PROJ-123`) — optional, can be filled in later by editing `workshop.json` directly
4. Create:
   - `workshop.json` (state file)
   - `goal.md` (problem statement + desired outcome, and an empty `## Definition of Done` section for rules every story in the epic must meet)
   - `research/` directory
   - `threads/` directory
   - `stories/` directory
5. Set `phase: "research"` in `workshop.json`

**workshop.json schema:**

```json
{
  "topic": "<short-name>",
  "goal": "<one-line problem statement>",
  "phase": "research",
  "createdAt": "<YYYY-MM-DD>",
  "epicKey": null,
  "chosenThread": null,
  "threads": [],
  "stories": []
}
```

---

### `research [topic]`

Investigate a specific aspect of the system. Each invocation focuses on one topic.

**Steps:**

1. Read `workshop.json` to understand context
2. Read `goal.md` and existing findings in `research/` to avoid duplication
3. Launch Explore agent(s) to investigate the topic (code paths, existing behavior, dependencies)
4. Write findings to `research/NN-<slug>.md` (numbered sequentially)
5. If hard constraints are discovered, append to `research/constraints.md`
6. Update `research/sources.md` with code paths and docs referenced

Write each finding in the **finding file format**, and append hard constraints in the **constraints file format**, both in [references/file-formats.md](references/file-formats.md).

**Rules:**

- Number findings sequentially (01, 02, 03...)
- One finding per file — keep them focused
- Reference existing files in the directory if relevant (e.g., "See also: `technical_analysis.md`")
- A scope bullet from a handoff or planning doc is a suggestion. Before researching how to build it, check it against `goal.md`. If the goal does not need it, say so in the summary and ask the user whether to research it
- After writing findings, present a brief summary to the user and ask if they want to explore further

---

### `thread <name>`

Create or develop an alternative approach document.

**Steps:**

1. Read `workshop.json`, `goal.md`, all `research/` findings, and `research/constraints.md`
2. If thread file doesn't exist (`threads/<name>.md`), create it
3. If thread file exists, read it and ask the user what to develop further
4. Write/update the thread document with sections below
5. Update `workshop.json` threads array (add if new, set `status: "exploring"`)

Write the thread in the **thread document format** in [references/file-formats.md](references/file-formats.md).

**Rules:**

- Use Explore agents to investigate the technical feasibility of the approach
- Reference research findings when relevant
- Be concrete — name specific files, services, and RPCs
- If the approach requires checking whether something is feasible, do the investigation and report
- After writing, present the key points to the user and ask for feedback

---

### `compare`

Generate a structured side-by-side comparison of all threads.

**Steps:**

1. Read all thread documents in `threads/`
2. Read `research/constraints.md`
3. Generate `comparison.md` at the workshop root

Write `comparison.md` in the **comparison format** in [references/file-formats.md](references/file-formats.md).

**Rules:**

- Dimensions should emerge from the threads' own tradeoff sections
- Always include: regression risk, effort, code isolation, and constraint satisfaction
- The Analysis section is advisory — present reasoning but defer to the user
- After generating, present the comparison and ask the user for their decision

---

### `decide <thread>`

Commit to a thread. This is a checkpoint — records the decision for future reference.

**Steps:**

1. Read comparison and thread documents
2. Write `decision.md`:

   ```markdown
   # Decision: <Chosen Thread Name>

   **Date:** <YYYY-MM-DD>
   **Chosen:** <thread slug>
   **Rationale:** <user's stated reason>

   ## Rejected Alternatives

   - **<thread B>**: <why not — 1 sentence>
   ```

3. Update `workshop.json`:
   - Set `chosenThread: "<slug>"`
   - Mark chosen thread `status: "chosen"`, others `status: "rejected"`
   - Set `phase: "writing"`
4. Confirm to the user: "Committed to <thread>. Ready for `/workshop split` to break this into stories."

---

### `split`

Propose a story breakdown from the chosen thread's analysis.

**Steps:**

1. Read the chosen thread document (`threads/<chosenThread>.md`)
2. Read `research/constraints.md`
3. Identify discrete deliverables from the Technical Analysis section
4. Test each deliverable against `goal.md`: name what fails if the epic ships without it, and check it against the goal's outcome and invariants. Drop a deliverable that changes behavior the goal promised to leave alone, such as a new check that makes a call fail which succeeds today. List each dropped or doubtful one for the user as "from the handoff, not required by the goal", with the reason
5. Group by deployment independence (one story should not require coordinated deployment of unrelated services)
6. Identify dependencies between stories
7. Present the proposed split to the user as a numbered list:
   ```
   Proposed stories:
   1. <title> — <1-line scope>
   2. <title> — <1-line scope>  (depends on: 1)
   3. <title> — <1-line scope>
   ```
8. Wait for user approval/adjustment (merge, split, reorder, rename)
9. After approval, update `workshop.json` stories array with just `slug`, `title`, and `status` per story — nothing else. The dependency graph itself is not stored separately — it's written directly into each story's `## Blocked By` section in `write`, and that markdown is the sole source of truth from then on. Do not add a `dependencies` (or `caseId`) field to these entries; that would just relocate the same duplication a `dependencies.json` sidecar would have caused.

**Splitting principles:**

- Prefer more, sharper stories over coarse ones
- Each story should be independently deployable and testable
- Data model before API, API before UI, proto before codegen
- No "pure verify" stories — verification folds into the builder story's ACs

---

### `write [story-slug]`

Write story files. If `story-slug` provided, write just that one. Otherwise write all stories from the split.

**Steps:**

1. Read the chosen thread document, research findings, and constraints
2. For each story to write:
   - Create `stories/<slug>/story.md`
   - Derive Context from the thread's technical analysis (scoped to this story)
   - Derive ACs from constraints + thread analysis + the story's specific scope
3. Update `workshop.json` stories status to `"draft"`

**Story format (MANDATORY):**

```markdown
Date: <YYYY-MM-DD>

# [<TICKET-ID>] <Title>

## Context

<2-4 sentences, high-level: what this story delivers, why it matters, and how it fits the
broader feature. A reader unfamiliar with the code should follow it end to end. No file
paths, job/step names, line numbers, or blow-by-blow "here's what the code currently does"
narrative — that's Technical Notes.>

## Acceptance Criteria

- <Observable, testable criterion on code this story modifies, introduces, or removes, in plain language a human reviewer reads in one pass>
- <Observable, testable criterion on code this story modifies, introduces, or removes, in plain language a human reviewer reads in one pass>
- ...

## Non functional Acceptance Criteria

- <Observable, testable criterion that remains true and unchanged, in plain language a human reviewer reads in one pass>
- <Observable, testable criterion that remains true and unchanged, in plain language a human reviewer reads in one pass>
- ...


## Technical Notes

<Optional. Exact file paths, line numbers, job/step names, env vars, current-code behavior,
and other implementation detail that anchors the Context/ACs to the actual code. Omit the
section entirely if there's nothing beyond what Context/ACs already say.>

## Blocked By

- <slug of a sibling story in stories/, or a real TICKET-ID>
- ...
```

**Rules:**

- If the user hasn't assigned TICKET-IDs yet, use `[TBD]` as placeholder and ask
- Every AC must clear the **AC quality bar** in references/story-quality-bars.md
- A human reviewer is the primary consumer of both Context and ACs — Context is a high-level
  summary of WHAT and WHY, not an implementation narrative of HOW. If a Context sentence names
  a specific file, job, line number, or describes today's code path in detail, that sentence
  belongs in Technical Notes, not Context
- Always write `## Blocked By`, even for a story with no dependencies — write `(none)` instead of a bullet list rather than omitting the section
- Populate `## Blocked By` from the dependency list agreed on in `split`, one entry per line, using the dependency's slug (its `stories/<slug>/` folder name) — TICKET-IDs aren't known yet at this point. This mirrors Jira's own "is blocked by" language for a "Blocks" link, so the section name and the Jira relationship it creates read the same way. This section is the only record of the dependency graph — there is no separate dependencies.json to keep in sync, and it should not be copied into `workshop.json` either (see `split`).
- Once a real TICKET-ID is assigned, it belongs in the story's own `# [TICKET-ID] Title` heading, not as a duplicate `caseId` field in `workshop.json`
- After writing, present each story's title + Context + ACs to the user for review

**Quality bars:** before a story is done, its Context, every AC and every Technical Note must pass the
bars in [references/story-quality-bars.md](references/story-quality-bars.md). Read that file before
writing or refining any story. It covers the Context bar, the AC bar with its rule to keep the AC list
short, and the Technical Notes bar, each with worked contrasts.

---

### `refine [story-slug]`

Iterate on stories based on user feedback.

**Steps:**

1. If slug provided, read that story. Otherwise list all stories with their current ACs.
2. Ask the user what to change (or accept their stated feedback)
3. Apply changes
4. Validate:
   - All required sections present (Context, ACs)
   - Context clears the Context quality bar (see references/story-quality-bars.md) — high-level WHAT/WHY, no
     file/job/line-level narrative
   - Every AC clears the AC quality bar (see references/story-quality-bars.md)
   - The AC list is short (see "Keep the AC list short" in references/story-quality-bars.md): an AC that repeats an epic-wide rule moves to `goal.md`'s `## Definition of Done`, and an AC that describes how the fix is proven or built moves to Technical Notes
   - Every Technical Note clears the Technical Notes quality bar (see references/story-quality-bars.md) — each bullet gives an
     actionable pointer; delete anything that says "noted but not fixed here", narrates superseded
     drafts, or restates an AC
   - Cross-story consistency (terms, field names, entity references match)
   - No overlapping scope between stories
   - Dependencies still make sense
5. Report any issues found during validation
6. Update story status to `"reviewed"` in `workshop.json` when user approves

**Refinement types:**

- AC rewording ("make this more specific")
- Scope adjustment ("move this criterion to another story")
- Story splitting ("this is too big, break it into two")
- Story merging ("combine these, they're too small alone")
- Dependency correction ("these can actually be parallel")

---

### `status`

Show the current state of the workshop.

**Output format:**

```
Workshop: <topic>
Phase: <phase>
Directory: <path>

Research: <N> findings, constraints: <yes/no>
Threads: <list with status>
  - <name> [exploring|explored|chosen|rejected]
Decision: <chosen thread or "not yet">
Stories: <list with status>
  - <slug>: <title> [draft|reviewed]
```

---

## State Awareness

Every subcommand MUST:

1. Read `workshop.json` before doing anything
2. Load context from existing files (don't ask the user to repeat what's already written)
3. Present a soft warning if the subcommand is unusual for the current phase (but don't block)

**Phase progression (typical, not enforced):**

```
research → threads → writing → refining
```

The user can jump phases. If they run `/workshop write` without having decided on a thread, warn: "No thread has been chosen yet. Which thread should I write stories from?" — then proceed.

---

## Cross-Session Resumability

This workflow survives session boundaries because all state is in files:

- `workshop.json` tracks phase and progress
- Research findings persist as markdown files
- Thread documents persist as markdown files
- Stories persist in `stories/`

On any invocation, read the workshop directory to reconstruct context. Never assume the user remembers what happened in a previous session — briefly state where things stand before asking what to do next.

---

## Integration with Existing Patterns

- **Dependency graph ground truth** is each story's `## Blocked By` section in `story.md` — nothing else. There is no `dependencies.json` sidecar, and `workshop.json`'s own `stories` array must not carry a `dependencies` field either — that's the same duplication just moved to a different file. Any tool that needs the dependency graph should parse `## Blocked By` directly out of the story markdown files. Likewise, the real TICKET-ID lives only in each story's `# [TICKET-ID] Title` heading — `workshop.json` tracks a story by `slug`/`title`/`status` only.
- **Existing project files** (notes.md, technical_analysis.md, etc.) are preserved and can be referenced from structured findings
- **Promotion is Jira creation, not a file copy** — create one Jira Story per `stories/<slug>/story.md` still marked `[TBD]`, under the epic recorded in `workshop.json`'s `epicKey` field. Write the assigned TICKET-ID back into each story's heading, and link `## Blocked By` entries as Jira "Blocks" relationships. Stories remain in `stories/` permanently; there's no separate canonical location to copy them to.
