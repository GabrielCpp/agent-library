---
name: test-coverage-analysis
description: "Deriving the test cases for a type, function or API before writing tests: classes, boundaries, pairwise, invariants; a decision table for a story. Load when asked what to test, whether cases are missing, or to plan tests."
argument-hint: 'paste or reference the type/function/API to analyze, or a story folder path for story mode'
tags: [tests, qa, planning]
---

# Test Coverage Analysis

Derives *what* to test from the shape and usage of a type or function, before writing any test code. Language-agnostic — works for a Go struct, a Dart class, a TypeScript interface, a Python function, or an HTTP endpoint.

## When to Use
- User asks "what should I test here", "what am I missing", "is this covered".
- Planning test cases for a new type, function, or endpoint before implementation.
- Reviewing an existing test file for coverage gaps.
- Any time someone hands you a bare data shape (struct/class/interface) and asks how to test around it.
- A story has many states and use cases (warnings, statuses, eligibility rules) and the grilling session is done. Use story mode below.

Not for: writing the actual test code/assertions (hand off to the repo's test-writing skill, e.g. `<repo>-test`) or measuring code-coverage tool output — this skill is about *designing* the test space, not running coverage tools.

## Procedure

Work through each category that applies. Not every category applies to every shape — skip what's irrelevant (e.g. concurrency doesn't apply to a plain data struct).

### 1. Per-field / per-parameter equivalence classes
For every field or parameter, partition its domain into classes and pick one representative per class — don't enumerate every value.

| Type | Classes to consider |
|---|---|
| Integer | zero, positive, negative, min/max (overflow-adjacent), known sentinels (-1, id=0) |
| Float | zero, positive, negative, NaN/Inf if applicable, precision edge cases |
| String | empty, whitespace-only, normal, very long, unicode/multi-byte, chars special to a downstream sink (SQL/HTML/JSON/shell) |
| Bool | true, false (trivial, no further partitioning) |
| Enum | each valid value, plus an invalid/unknown value if the type isn't closed |
| Collection (slice/list/map) | nil/absent, empty, single element, many elements, duplicates, nested empty |
| Pointer / nullable / optional | nil/None/null, present |
| Time/date | zero value, past, future, boundary (epoch, DST transition, leap day) if relevant |

### 2. Zero-value / default state
Always include the fully-default instance (`Foo{}`, `{}`, unset struct). This is often a real path — missing fields after deserialization, uninitialized struct in a map, etc.

### 3. Combinatorics — pairwise over brute force
Don't test the full cartesian product of every field's classes; it explodes fast. Default to **pairwise coverage** (every pair of classes across two fields appears in at least one case). Only escalate to full combinations for fields with a *known* interaction (see invariants below).

### 4. Usage-based paths (requires looking at callers, not just the shape)
A bare type/struct doesn't reveal these — check constructors, callers, and serialization code:
- **Round-trip**: marshal → unmarshal (JSON/proto/DB row) → equal to original.
- **Validation**: does a `Validate()`/constructor reject invalid states? Test the rejections, not just the happy path.
- **Mutation/aliasing**: passed by pointer/reference? Test that mutations don't leak unexpectedly, and vice versa.
- **Equality/comparison**: if compared with `==`/`DeepEqual`/custom `Equals`, test edge cases (nil vs empty, differently-ordered collections).

### 5. Cross-field invariants
Look for rules that only make sense across fields (e.g. "Bar is only valid when Beep is true"). These aren't visible in the type definition — find them in constructors, validation code, or domain docs. Once found, they become full-combination candidates from step 3, not pairwise.

### 6. Function/behavior-specific (skip for pure data shapes)
- Partition inputs by branch/decision point in the implementation, not just by type.
- Error paths: every distinct error return/throw needs at least one test driving it.
- Side effects: what changes in the world (DB write, event published, file written) — assert on that, not just the return value.
- Idempotency: does calling twice with the same input behave correctly?

### 7. Concurrency-specific (skip unless the type/function is shared across goroutines/threads or async tasks)
- Concurrent read/write races on shared state.
- Ordering guarantees (or lack of) under concurrent calls.
- Cancellation/timeout mid-operation.

### 8. Assemble the output
Produce a checklist grouped by category (not a flat list), e.g.:

```
Foo{Boo int, Bar string, Beep bool}
- Zero value: Foo{}
- Boo: zero, negative, MaxInt
- Bar: empty, unicode, very long
- Beep: true, false
- Pairwise: {Boo=negative, Bar=empty}, {Boo=MaxInt, Bar=unicode}, ...
- Round-trip: JSON marshal/unmarshal preserves all fields
- Invariant (if found in constructor): Bar required non-empty when Beep=true
```

## Story Mode

Use when the input is a story folder (a `story.md` with acceptance criteria) whose behavior depends on many combined states. The model derives cases from a fixed structure. It does not recall them.

Run it after the grilling session, so the answers from that session are in the conversation or in the story. Read `story.md` and any grilling notes in the folder first.

### S1. Name the axes
List every input that changes the outcome, each with its values. Use the equivalence classes from step 1 for each axis. Include axes the AC never mentions but the system has, such as position (first, last), count (0, 1, 2+), and entity state (active, disabled, deleted).

### S2. Build the decision table
Write rows as combinations of axis values. Write columns as the outputs: which outcomes fire (warnings, errors, events) and their exact text. Collapse rows that behave the same. Cite the rule that justifies each collapse.

### S3. Surface undecided cells
List every cell the AC and the grilling answers do not decide. Mark each one `OPEN`. Ask the user to resolve them in one numbered round, each with a recommendation. Do not guess a cell. Update the table with the answers before continuing.

### S4. Check the table mechanically
- Gaps: every combination of axis values maps to exactly one output set.
- Conflicts: no two rows claim the same combination with different outputs.
- Co-firing: list every pair of outcomes that can fire on the same input.
- Suppression: for each outcome, list the inputs that make it not fire.

### S5. Derive the test list
Pick the minimal rows that cover each axis value at least once and each pairwise interaction. Add full combinations for axes with a known interaction. Add the zero-value row and one row per distinct error path.

### S6. Write the files
Write `test-matrix.md` next to `story.md` with these sections: Axes, Decision table, Co-firing and suppression, Test list. Add one line under the story's Description that links to it. Do not write test code.

If the user runs the skill again, update `test-matrix.md` in place and keep resolved decisions.

## Completion Check
Before handing off to test writing, confirm:
- [ ] Zero-value case included
- [ ] Every field/parameter has at least its boundary classes covered
- [ ] Combinatorics handled via pairwise (not brute-forced) unless an invariant demands full combos
- [ ] Usage-based paths checked against actual callers/constructors, not assumed
- [ ] Error paths and side effects covered for functions/behavior (not just data shapes)
- [ ] Story mode: no `OPEN` cells remain, the gap and conflict checks pass, and `test-matrix.md` is linked from `story.md`
