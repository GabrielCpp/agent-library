Review a pull request, keep only the correctness findings a test proves, and post each as a PR comment with its failing test. Input: $ARGUMENTS (PR URL or number, defaults to the current branch's PR).

## 1. Review

Load the skills the repo's CLAUDE.md names for the touched paths. Invoke the `code-review` skill on the PR with the Skill tool and args `high <pr>`. Always pass the level, because without one the skill reuses the last level typed. Do not pass `--comment` or `--fix`. Keep the findings it returns as the work list.

Open threads. List the unresolved review threads on the PR with `gh api graphql` (`reviewThreads`, `isResolved: false`). Add each human reviewer's comment to the work list with its author. A thread follows the same rules as any other finding.

Then run four passes yourself and add their findings to the list.

Trust-boundary pass. List every read or write the diff adds or changes that is keyed by a request field (an id, a tenant, a facility, a sensor). For each one, name the check that ties the field to the caller. A key without a named check is a correctness finding. Its test sends a value that belongs to another facility or tenant. A named check still fails the pass in two cases. The first is a check that runs after the read it guards, so the read already happened for a caller who is denied. The second is error codes that differ between "the item does not exist" and "the item exists but is not yours", which tells the caller which ids exist. Its test sends an id from another facility and an id that does not exist, and asserts the same code for both.

Authorization-completeness pass. List every handler the diff adds or changes that checks a permission or capability. For each one, answer three questions. Does every branch of a switch, oneof or type field run a check, and does the default deny? Is the check as narrow as the action, or does an any-of check let a caller who holds the permission for one type act on another type? Does the check at the edge (a gateway, a router, a UI guard) match the check the downstream service runs for the same action? A branch with no check, a default that allows, or an edge check wider than the downstream check is a correctness finding. Its test calls the handler as a caller who holds only the permission for a different type.

Cross-repo pass. List every finding or review thread whose verdict depends on state in another repo: a role or permission definition, a shared config, a client that consumes the API. Name the repo and the file you read to settle it. A claim you could not settle from a file stays on the list as "needs human check", with the repo named.

Delivery pass. List every event, stream or queue handler the diff adds or changes. For each write it makes to a datastore (a database of any kind, a cache, a file or object store, an external API), name the guard that makes a second delivery harmless: a uniqueness constraint, a conditional write or compare-and-set, a version check, an upsert on a key derived from the event, or a processed-event record in the same transaction. An unconditional insert, overwrite or increment with no guard is a finding when the handler can run twice. A decision derived from live state on each delivery, and not read back from the stored item, is a finding. Its test delivers the same event twice with the state change between them.

## 2. Filter

Split the findings into three groups:

- Correctness: the finding claims wrong behavior for a concrete input or state. A finding that describes behavior a user or a caller observes (a flash, a stale value, state that sticks between visits, a leak, a wrong logout or error reason) is correctness, whatever class the review gave it.
- Rule breaks: the finding breaks a written rule in the repo's CLAUDE.md or a skill it names, such as dead code, an unreachable guard or a deprecated call. A comment or doc that states behavior the code does not have also belongs here. Quote the rule or the contradicting line.
- Other: simplification, efficiency, structure, naming, missing tests, with no written rule behind them.

Drop the third group. Do not post it, fix it or mention it in comments. Count the dropped findings for the report. Rule breaks skip step 4 and go straight to step 5.

## 3. Isolate the work

Create a worktree of the PR branch outside the user's checkout. Never edit the user's working tree. Run every later step in the worktree. Load the repo's CLAUDE.md and the test skill it names for the touched paths.

## 4. Prove each correctness finding with a test

For each correctness finding:

1. Write the smallest test that fails because of the finding. Follow the repo's test skill and naming rules.
2. Run it. Record the command and the failure message.
3. If the test passes, discard the finding and record "not reproduced" with the test name and the passing run. Post nothing for it. A test that cannot reach the defect (a setup that resets the state under test) proves nothing, so fix the test first.
4. If the test needs infrastructure you cannot run here (a local database, a queue emulator, a cloud emulator), record "unproven". Post it as a comment with the reasoning and the test you would run, without a failing-output line. Never discard it for that reason.
5. If the test fails, keep the finding. Do not fix the code.

Put the test in the file that sits beside the code under test. Leave the tests uncommitted in the worktree.

## 5. Post the comments

Post one review on the PR with one inline comment per reproduced finding and per rule break. Anchor each comment on the finding's `file:line`.

Each comment has this shape:

````
<one sentence: the defect>

<one sentence: the input or state that reaches it and the wrong result>

<details><summary>Failing test</summary>

```<lang>
<the full test function>
```

Run: `<command>`
Fails with: `<first failing line of the output>`

</details>
````

A rule break uses the same shape with the details block replaced by the quoted rule and the file it comes from. For a dead branch, name the input that would reach it and show that no caller sends it.

Rules:

- Embed the complete test, not a link to it. The author must be able to paste it into the repo.
- Use `gh api repos/{owner}/{repo}/pulls/{pr}/reviews` with `event=COMMENT` and a `comments` array. Use the PR head SHA as `commit_id`.
- If a line is outside the diff, post that finding as a regular PR comment with `gh pr comment` and name the `file:line` in the first sentence.
- Follow the user's prose style. No em dashes, no en dashes, no summary paragraph.
- A finding the PR description lists as settled is a claim. Check its reason against the code. If the reason cites no evidence, or your test fails, post the finding.

If no finding was reproduced, post nothing.

## 6. Report

One table, one row per correctness finding and rule break: finding, outcome (posted, unproven, not reproduced), and the test name or the quoted rule. Then the "needs human check" claims from the cross-repo pass, each with its repo. Then one line with the number of findings dropped in step 2. Then the worktree path, so the user can inspect or keep the tests. Remove the worktree only when the user asks.
