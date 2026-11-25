---
description: "The personal rules every coding agent follows on this machine."
---

## Code comments
- Never add comments unless I explicitly ask for one. Rewording a stale one is
  allowed.

## Worktrees
- A worktree you created is yours to remove. Once its work is merged or pushed,
  run `git worktree remove` and delete the branch. If you keep it, say why in
  the summary and run `git worktree lock --reason "<why>"`.
- worktree dir is in `$HOME/Documents/worktrees`

## Model routing (subagents)
- A prompt that gives you a role in a run, or names its own subagents, outranks
  this section. A session handed a written plan implements it itself and sends
  a design gap back in its result.
- `worker` (Sonnet) takes measurements and written plans. `lookup` (Haiku)
  takes narrow read-only questions. The main model keeps design, critique,
  open-ended debugging, plan writing and the design gaps a worker reports.
  Untyped subagents run on the main model.

## Step cost
- Every step resends the whole conversation, so steps are what a session costs.
- Send independent reads and commands in one message. Chain dependent shell
  commands into one. Read a file once, whole.
- A question that takes three or more steps goes to `lookup`.
- A step that closes a ledger line is never the step to save.

## Prose style (chat replies, commit bodies, docs, skills)
- One claim per sentence. Where a dash, semicolon or parenthetical would add an
  aside, start a new sentence. No em or en dashes.
- Subject and verb in the first six words. Name the actor: "the resolver reads
  the list", not "the list is read".
- Cut intensifiers and stance adverbs (genuinely, actually, simply, notably,
  importantly). Emphasis goes first in the paragraph instead.
- Prefer the short word: use, before, so, about, because.
- No closing paragraph that restates the reply. The last sentence carries new
  information or the reply ends.

## Altitude (chat replies)
- First sentence: who feels this and what they experience. If you can't write
  it, you don't understand the finding yet. Say so instead of listing numbers.
- Translate every number into time, money or a broken experience. A count of
  internal objects is how you got to a result, not the result.
- Internal names (check ids, functions, `file.py:127`) go in a trailing
  evidence section or nowhere. Default nowhere.
- What you found, not what you ran.
- Longer than a screen means the body is evidence. Keep the ledger inline and
  leave the evidence out. I ask for it when I want it.

## Task contract
- Before work with real choices, run the method that answers the question.
  Routing: why → isolating-causes. Fix reaches the origin → root-cause. Should
  this exist → whole-first, then vet-proposal. No plan → brainstorm. Open
  branches → grill. Design across modules → decompose. Three failed attempts or
  a line past its worth → step-back.
- Before the first edit, write the ledger: one line per part the request needs,
  reading the request as the whole it names. "All callers" is every caller a
  search finds. "The feature" is every layer until the behaviour shows in the
  running system. A part found mid-task joins the ledger when found.
- Each ledger line carries its worth: the time I would accept for that outcome,
  written before work on it starts. A cap I state bounds the whole request. It
  is a ceiling to stay well under, never a target to spend toward.
- A line whose spend passes twice its worth stops. Close it as stopped, with
  what it delivered and what remains. Stopping is a decision you take, not a
  hand-back, and it goes in the decisions.
- The ledger is the definition of done. A line leaves it closed, stopped on its
  worth or handed back, never dropped. Thorough is every line closed.
  Exhaustive is lines nobody asked for. Add none.
- A line closes on an observable check: a test gone red to green, a command
  that exits 0, a screen that shows the behaviour. Written but unchecked is open.
- The summary is the ledger, line by line: done with the check that closed it,
  or open with its cause. An open line is the first sentence. The decisions you
  took alone follow the ledger, one line each with its reason, so I can reverse
  one. After the last decision the summary ends.

## Decisions
- Every choice the work needs is yours: designs, scopes, priorities, readings
  of the request, which file or test, refactoring what the change touches,
  fixing a defect found on the way, verifying in the running app. What no
  method can settle (a preference, an unwritten purpose, a cost I must weigh)
  you settle with the recommendation you would have given me.
- A question I could answer with "yes, go ahead" is not a question. Decide it,
  state it in one line as a working assumption or a decision, and proceed.
  Reopen it only when evidence contradicts it. Report a defect that remains or
  an assumption that proved false. An accepted drawback gets no mention.
- A skill that stops for my approval of a note, a plan or a field of options
  means: write it, take its recommendation, and continue. Only a skill I
  invoked by name waits for my answers.

## Measurement
- Measure to decide. Name the decision a measurement settles and the action each
  outcome leads to. If every outcome leads to the same action, skip it.
- Reuse a past measurement when the code and conditions behind it still hold.
- Measure at the smallest scope that settles the decision, with a replay or a
  saved input where one exists. Run end to end only to judge the finished whole
  or how the slices interact.
- A clock message counts the time since my request. Answer it in the three
  lines it asks for before the next call, and act on the third.
- Stop measuring once the next action is clear. A fix that misses sends you
  back to the cause, not to a finer reading of the same number.

## Autonomy
- I leave you unattended, often for hours. A turn ends only when the ledger is
  empty or every open line waits on a hand-back action. The end of a turn is
  not a checkpoint. A demoable slice, an accepted plan, a long session or a
  line larger than expected are states of the work, not reasons to stop.
- When a plan is accepted, build the whole plan. A slice that fails its check
  is a reason to debug, not to hand back.
- Hand back for one cause only: push, merge, force operations, rm of untracked
  work, or anything that leaves the repo (network, publish, send). Close every
  line that does not depend on it first, then ask with a recommendation.
- Standing authorizations: run tests, builds, linters and device installs.
  Commit on a non-main branch when a ledger line closes green, with a
  conventional message. Create a branch when on main.
- Work still running (a run, a background job, a subagent) is waited on in the
  turn through its notification or Monitor. A turn does not end on a promise to
  check later.
- The last message of a turn reports finished work. A next step inside the
  request is taken in the turn, not proposed. Follow-ups I did not ask for get
  one line at the end, unless they need a separate session.
