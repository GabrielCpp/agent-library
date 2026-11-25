---
name: presentation-content
description: "Talk content as local files: single-file HTML deck, word-for-word script and speaker notes. Load when asked to plan, build, revise or script a presentation, a deck, slides or a talk, including retiming a script after a dry run."
tags: [presentation, writing]
---

# Presentation content

A talk exists to make the audience do one thing afterwards. Every slide, line and diagram
either moves them toward that **ask** or comes out.

The deliverable is three local files in the folder the user names: `deck.html`, `script.md`
and `notes.md`. Write them with the Write tool. Show the deck by serving it and taking a
screenshot.

## Steps

### 1. Pin the brief

Write down, in the user's words:

- **Slot:** minutes, audience, date, and who introduces the speaker.
- **Ask:** the one action the audience takes afterwards ("run `/grill` on your next story").
- **Level:** what the audience already knows. A talk pitched past it loses the room, so when
  the last talk was "too advanced", pitch this one at the newest person in the room.
- **Trigger:** the event that prompted the talk.

Done when the ask fits in one sentence and names something the audience can do this week.

### 2. Find the audience's questions

List the questions the audience will ask about the thing you present. For a tool these are
the mechanism questions: how it decides, when it acts, when it reads what it wrote, how to
get it. The talk answers each one on a slide or in the script.

Done when every question maps to a slide, a script line, or a Q&A entry in `notes.md`.

### 3. Separate mechanism from anecdote

Sort every candidate point into one of two piles:

- **Mechanism:** what the thing does every time, which an audience member will see when they
  try it.
- **Anecdote:** what happened once, on one project, for reasons unrelated to the thing.

Mechanism carries the slides. An anecdote earns a slide only as a worked example of the
mechanism. When the sort is unclear, run {{ skill_link("isolating-causes") }} on the claim.

Done when every slide has a mechanism it shows.

### 4. Size the deck to the slot

Budget about 130 spoken words a minute and one to one and a half minutes a slide. A
10-minute slot takes 5 to 7 slides and a script that stops about two minutes early for
questions. The usual shape:

1. Title: the problem in one line, plus the trigger.
2. How it works: the mechanism, answering the questions from step 2.
3. Before and after: a diagram of what changed.
4. One worked example up close.
5. Improvements and caveats.
6. How to get it: the commands, pointing at what the audience can install today.
7. Thanks and questions.

Done when the slide count times the per-slide budget fits inside the slot with time left for
questions.

### 5. Verify every claim

Each claim on a slide or in the script traces to a source: a file, a commit, a ticket, or
the user's own statement. Record each one in a **claims table** in `notes.md` with its
source. Mark a claim the user reports from experience as "experience, unmeasured" and phrase
it that way aloud ("I won't put a number on it").

Keep the user's claims at the size they gave them. A caveat the user stated stays that
caveat. Adding a reason or an example to it is a new claim, and it goes to the user for a
yes before it reaches a slide.

Done when every row in the claims table names its source.

### 6. Write for a stranger

Read every label as someone outside the team would:

- Name things by what they do. "The story that sends flagged falls to the review queue", not
  the team's nickname for it.
- Explain each domain term in one sentence the first time it appears.
- Use the accurate word. A record of an earlier choice is a "past decision", whatever skill
  produced it.

Done when no label on a slide needs the speaker to translate it.

### 7. Write the script and notes

`script.md` is word for word, one section per slide, with the start time on each heading and
cues in **[brackets]** ("[Point at BEFORE.]"). Retime after every edit: count the words per
section and move the start times to match.

`notes.md` holds the brief, the claims table, the timing with a fallback for running long
(which slide to skip), and Q&A prep for the questions from step 2 that no slide answers.

Done when the start times in `script.md` match its word counts at 130 words a minute.

### 8. Render and check

Serve the folder and screenshot each slide at 1920x1080 and 1280x720. Read every screenshot
for overflow, clipped text and arrows whose direction is ambiguous. The deck mechanics and the
screenshot commands are in [references/deck-mechanics.md](references/deck-mechanics.md). Read
it before writing `deck.html` for the first time, and before any diagram.

Done when every slide renders clean at both sizes.

## Revising after a dry run or review

Before writing, diff the target folder against what you last wrote. The user edits the deck
by hand between rounds. Carry those edits into the new version word for word, and keep
their phrasing even where you would word it differently. Mention grammar slips in chat.

Feedback after a dry run usually asks for one of three slides: a before and after visual, an
improvements and caveats slide, or a thanks and questions slide. The step 4 shape already
holds all three.

When a reviewer's points pull against each other, satisfy the intent behind both, then
say in chat which wording you kept and why. A request to reverse an arrow while also writing
a label that reads in the current direction is usually a request to make the direction
obvious: add a start dot and a larger arrowhead.

A question the reviewer repeats ("what does the queue story mean?") means a label failed step 6. Rename it on every slide and in the script.

## When to reach for the neighbours

- **A claim's cause is unclear**, or a point mixes mechanism with anecdote: {{ skill_link("isolating-causes") }}.
- **The deck needs a chart:** load `dataviz` before drawing it.
