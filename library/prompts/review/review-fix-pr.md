Review a pull request, then fix what the review finds. Input: $ARGUMENTS (PR URL or number, defaults to the current branch's PR).

## 1. Review

Invoke the `code-review` skill on the PR with the Skill tool and args `high <pr>`. Always pass the level, because without one the skill reuses the last level typed. Keep the findings it returns as the work list. Do not post comments.

Open threads. List the unresolved review threads on the PR with `gh api graphql` (`reviewThreads`, `isResolved: false`). Add each human reviewer's comment to the work list with its author. A thread follows the same rules as any other finding.

Then run four passes yourself, after loading the skills the repo's CLAUDE.md names for the touched paths (for example `/<repo>-events` for event handlers, `/<repo>-db` for the data layer, `/<repo>-grpc` for RPC handlers). The rules in those skills are the checklist.

Trust-boundary pass. List every read or write the diff adds or changes that is keyed by a request field (an id, a tenant, a facility, a sensor). For each one, name the check that ties the field to the caller: the interceptor, a tenant-scoped key, or an explicit comparison with the caller's tenant and facility. A sibling path in the same handler that performs a check this one lacks counts as evidence. Every key without a named check is a correctness finding. Its test sends a value that belongs to another facility or tenant. A named check still fails the pass in two cases. The first is a check that runs after the read it guards, so the read already happened for a caller who is denied. The second is error codes that differ between "the item does not exist" and "the item exists but is not yours", which tells the caller which ids exist. Its test sends an id from another facility and an id that does not exist, and asserts the same code for both.

Authorization-completeness pass. List every handler the diff adds or changes that checks a permission or capability. For each one, answer three questions. Does every branch of a switch, oneof or type field run a check, and does the default deny? Is the check as narrow as the action, or does an any-of check let a caller who holds the permission for one type act on another type? Does the check at the edge (a gateway, a router, a UI guard) match the check the downstream service runs for the same action? A branch with no check, a default that allows, or an edge check wider than the downstream check is a correctness finding. Its test calls the handler as a caller who holds only the permission for a different type.

Cross-repo pass. List every finding or review thread whose verdict depends on state in another repo: a role or permission definition, a shared config, a client that consumes the API. Name the repo and the file you read to settle it. A claim you could not settle from a file goes under the decisions for the user in step 7, with the repo named.

Delivery pass. List every event, stream or queue handler the diff adds or changes. For each write it makes to a datastore (a database of any kind, a cache, a file or object store, an external API), name the guard that makes a second delivery harmless: a uniqueness constraint, a conditional write or compare-and-set, a version check, an upsert on a key derived from the event, or a processed-event record in the same transaction. An unconditional insert, overwrite or increment with no guard is a finding when the handler can run twice. Then ask what a second delivery does when state changed in between: a feature flag flipped, a field already set by a later event, a result already stored, a row already updated by another writer. Any decision derived from live state on each delivery, and not read back from the stored item, is a finding. Its test delivers the same event twice with the state change between them.

## 2. Gather the goal

Read what the PR is meant to achieve before judging any finding:

- The PR title, description and linked story or epic (Jira key in the title or branch, `story.md` beside the plan if one exists).
- The repo's CLAUDE.md and the skills it names for the touched paths. Load those skills.

Write the goal in two sentences. Every later judgement compares against it.

The goal is the behavior the story asks for. The plan is not the goal. A finding that contradicts a plan line is still a finding: the plan may have prescribed the defect. A finding that the story or the PR description already defers to a named follow-up story is out of scope. Record it as skipped and name that story.

## 3. Isolate the work

Work on the PR's own head branch. Never create a new branch. Read its name with `gh pr view <pr> --json headRefName -q .headRefName`, then `git fetch origin <branch>`.

Create a worktree of that branch outside the user's checkout with `git worktree add <path> <branch>`. If the user's checkout already has the branch, use `git worktree add --detach <path> origin/<branch>` instead. Never edit the user's working tree. Run every later step in the worktree.

## 4. Correctness findings that a test can reproduce

A finding that describes behavior a user or a caller observes (a flash, a stale value, state that sticks between visits, a leak, a wrong result) belongs here, whatever class the review gave it. Structure and naming findings go to step 5.

For each finding that claims wrong behavior:

1. Write the smallest test that fails because of the finding. Follow the repo's test skill.
2. Run it. If it passes, discard the finding and record "not reproduced".
3. If the test needs infrastructure you cannot run here (a local database, a queue emulator, a cloud emulator), record the finding as "unproven", keep it in the report and treat it as a judged finding in step 5. Never discard a finding because its test could not run.
4. If it fails, fix the code until the test passes. Keep the test.

Never fix a correctness finding without a failing test first.

## 5. Every other finding

Covers simplification, efficiency, structure and any correctness claim a test cannot reproduce. A finding that breaks a written rule in the repo's CLAUDE.md or a skill it names (dead code, an unreachable guard, a deprecated call) is fixed unless the story defers it. So is a comment that states behavior the code does not have. Quote the rule or the contradicting line. For each other finding, load `whole-first`, `isolating-causes` and `root-cause`, then decide:

- `whole-first`: does the finding serve the goal from step 2, or does it only improve a piece in isolation?
- `isolating-causes`: what is the origin of the problem, backed by evidence from the code or logs?
- `root-cause`: does the proposed change reach that origin, or does it patch a symptom?

Every skip reason cites evidence: a file and line, a test result, or a line of the story. These never count as a reason:

- The existing code does the same thing. A pattern shows what is common and does not show what is correct.
- An assumption about runtime ("it loads once", "nobody does that") with no line of code behind it.
- An argument against a design the finding did not propose.

An open comment from a human reviewer is never skipped by you alone. Fix it, or list it under the decisions for the user with your reasoning.

Your judgement is the gate. Fix the finding only when all three answers hold and the change aligns with the goal and the repo's skills. Otherwise skip it and give the reason in one sentence. A skipped finding is a valid outcome.

## 6. Verify and commit

- Run the repo's formatter, analyzer and the tests you touched. Fix what you broke.
- Make one commit per fixed finding, following the repo's commit style and attribution rules.
- Do not push. Ask the user first. Once they approve, push the commits to the PR's head branch with `git push origin HEAD:<branch>`. Never force-push. If the push is rejected, rebase on `origin/<branch>`, rerun the tests and push again.

## 7. Report

One table, one row per finding: finding, class (reproduced, judged, skipped), outcome, and a reason of at most one sentence. Then list anything that needs a decision from the user. No other summary.

## 8. Record skipped findings in the PR description

Later reviewers read the description before they re-raise a settled finding. Record every finding with outcome skipped or "not reproduced".

1. Read the current body with `gh pr view <pr> --json body -q .body`.
2. Build a section delimited by `<!-- review-fix-pr:start -->` and `<!-- review-fix-pr:end -->`:

```
## Review findings not fixed

| Finding | Reason |
|---|---|
| <finding in one line, with file:line> | <reason in one sentence> |
```

3. If the markers exist, replace everything between them. Otherwise append the section to the end of the body. Leave the rest of the body unchanged.
4. If no finding was skipped, remove the section when it exists and write nothing otherwise.
5. Apply with `gh pr edit <pr> --body-file <file>`.

Rows already in the section are claims, not settled facts. Before you keep one, check its reason against the code and the rules above. Remove or fix a row whose reason cites no evidence or no longer holds.

The reason states why the finding does not apply to the goal or what test showed it does not reproduce. Do not paste the review's wording.
