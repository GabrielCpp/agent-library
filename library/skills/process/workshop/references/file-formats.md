# Workshop file formats

Templates for the files `/workshop research`, `thread` and `compare` write. The story template lives in `SKILL.md` under `write`.

## Finding and constraints files (`research`)

**Finding file format:**

```markdown
# <Finding Title>

## What

<What was discovered — system behavior, code path, dependency>

## Where

<File paths, services, code locations>

## Implications

<How this affects the feature being planned>
```

**Constraints file format (`research/constraints.md`):**

```markdown
# Constraints

Hard requirements that any approach must satisfy:

- <constraint 1 — e.g., "Escalation service must never fire for privacy-requested sensors">
- <constraint 2>
```

## Thread document (`thread`)

**Thread document format (`threads/<name>.md`):**

```markdown
# Thread: <Name>

## Approach

<High-level description of what this approach does — 1-2 paragraphs>

## Technical Analysis

<Detailed breakdown: what changes where, what new code is needed, how it integrates with existing systems>

### Services Affected

- <service 1>: <what changes>
- <service 2>: <what changes>

### New Components

- <new item/RPC/handler/UI>

### Integration Points

- <how this connects to existing flows>

## Tradeoffs

### Advantages

- <pro 1>
- <pro 2>

### Disadvantages

- <con 1>
- <con 2>

### Risks

- <risk 1>
- <risk 2>

## Sizing

| Layer/Team | Effort     | Notes   |
| ---------- | ---------- | ------- |
| <layer 1>  | <estimate> | <notes> |
| <layer 2>  | <estimate> | <notes> |
| **Total**  | <total>    |         |
```

## Comparison (`compare`)

**Comparison format:**

```markdown
# Comparison: <Topic>

## Dimension Table

| Dimension       | <Thread A>   | <Thread B>   | ... |
| --------------- | ------------ | ------------ | --- |
| Regression risk | <assessment> | <assessment> |     |
| Code isolation  | <assessment> | <assessment> |     |
| Effort          | <estimate>   | <estimate>   |     |
| <dimension N>   | ...          | ...          |     |

## Constraints Satisfaction

| Constraint     | <Thread A>      | <Thread B>      |
| -------------- | --------------- | --------------- |
| <constraint 1> | <how satisfied> | <how satisfied> |

## Analysis

<Tool's assessment of which thread best fits the constraints and goals — presented as input for the user's decision, not a directive>
```
