# Story quality bars

The bars every `story.md` must pass in `/workshop write` and `/workshop refine`.

## Context

the same drift that hits ACs hits Context even harder, because Context
is prose and prose has room to keep narrating. A Context section that walks through every
branch trigger, guard condition, and job name is a diff description wearing a paragraph's
clothes. Before it's done, Context should pass:

- **The verbal test.** Could you say this paragraph out loud to a PM without naming a single
  file, job, or line number? If a sentence only makes sense to someone reading the workflow
  YAML alongside it, it's Technical Notes.
- **WHAT/WHY only.** What does this story deliver, and why does it matter (what breaks today,
  what it unblocks)? Not which step in which file does it today — that's the engineer's
  homework, captured in Technical Notes for when they get there.

Worked contrast — same story, before and after:

**Before (implementation dump):**

> The API service's `ci.yaml` `build` job is generic branch CI, not a `dev`-scoped job — it runs on
> every `pull_request` and on every `push` to `develop`, `develop-plus`, `release/*`,
> `hotfix/*`, and `dev-slot*` branches, plus every tag push. Inside that job, unconditionally,
> a `Terraform ECR` step runs `terraform apply --auto-approve` against the
> `tf/environments/dev/ecr` state, with no guard and no state lock table...

**After (high-level, WHAT/WHY):**

> The API service's dev ECR terraform is currently applied from branch CI instead of a real deploy
> trigger, with no guard against concurrent runs — the active cause of the terraform state
> corruption described in the epic goal. This story moves that apply into the dev deploy
> workflow, matching how test and prod already gate their own ECR terraform.

The exact job names, trigger branch list, and guard condition from the "before" version don't
disappear — they move to Technical Notes, where an implementer who needs them still finds them.

## Acceptance Criteria

a vague AC ("cases are filtered properly", "Slack gets more detail on failure") passes review and then gets implemented as whatever was easiest. Push every AC through these six checks before it's considered done:

1. **Name the exact trigger and every variant.** Enumerate the cases instead of leaving them implicit: "A failed deploy of the API service (dev, test, or prod)" beats "when a deploy fails". If an AC would read differently for each environment/role/input variant, that's a sign it needs to name them or split into one AC per variant.
2. **State the observable output, not internal state.** Something a reviewer can check from outside the system — a message field, a response, a UI label — never "the system tracks/handles/supports X".
3. **Rule out the plausible-but-wrong shortcut.** If a lazier implementation would technically satisfy a looser wording, say so explicitly: "resolves to the exact run whose failure triggered the notification, not a generic Actions tab or workflow list". Rule it out with an outcome the shortcut cannot produce, not with where the fix must go. "A user who resizes the window while the page loads gets the phone layout" rules out a test-only workaround. "The fix is in the app, not the test" names a location a reviewer cannot observe. The "do not do X" instruction itself belongs in Technical Notes.
4. **Make preservation explicit when the story adds to existing behavior.** "Existing failure message content is preserved alongside the new link — the fix adds information, it doesn't remove any." Without this, additive stories get implemented as rewrites that silently drop fields.
5. **Name cross-site consistency explicitly when the same behavior lands in more than one place.** "The link format is identical between the API service's and the web app's notification steps" — don't assume two implementations converge just because each independently satisfies the same AC.
6. **One checkable fact per bullet.** If stating it needs "and", it's two ACs.

**Keep the AC list short: the story's outcome, plus only the ACs that rule out a plausible wrong path.** The six checks sharpen each AC. They are not a reason to add ACs. A typical story has one to three. Before an AC stays, it must say something true of *this* story that its outcome AC does not already cover. Move the rest out:

- **A rule that holds for every story in the epic** (no hardcoded timeouts, accessible locators only, a repeat count that proves a flake fix) goes once in `goal.md` under `## Definition of Done`, which is pasted into the Jira epic's description. Do not repeat it in each story. When `write` finds the same AC forming in a second story, move it to `goal.md` instead.
- **How the fix is proven or built** (forcing a race, adding a component test, the repeat command, which locator to use) goes in Technical Notes. It is the implementer's method, not a criterion the reviewer approves.
- **Non functional ACs** follow the same bar. Keep one only when a plausible change in this story could break it.

Worked contrast, for a story fixing an intermittent "mobile nav button" test:

> ❌ Six ACs: the race forced and the old test failing; a component test for the store; 10 repeats with retries off; the button located by role and name; every other locator accessible; missing accessible names added. Four non functional ACs: no timeouts, no `networkidle`, what the test verifies unchanged, the app bar unchanged.
>
> ✅ Two ACs: "'Mobile nav button is clickable' no longer fails because a resize during page load leaves the app in its desktop layout." and "A user who resizes or rotates the window while the page is loading gets the phone layout." One non functional AC: "At every viewport width, the app bar and navigation drawer look and behave as they do today."

The four epic-wide rules moved to `goal.md`. The proof and the locator moved to Technical Notes. The second AC stayed because a test-only workaround would pass the first one.

**A human reviewer is the primary consumer, so ACs stay prose, not a spec.** Every check above is about the *behavior* an AC pins down, not about how many identifiers it names. A reviewer reading the AC list top to bottom should be able to say yes/no to each line without decoding a file path first. Exact file names, line numbers, job/step names, and env var names go in `## Technical Notes`, keyed loosely to the ACs above them — the AC says what's true in plain language, Technical Notes says exactly where. An AC that reads like a diff (backticked paths, `matrix.region ==` conditionals, line numbers) has smuggled implementation into the criterion; move the identifiers down and leave the behavior in the bullet.

Worked example — a real set of ACs for "deploy failures should link to the failing run in Slack":

**Acceptance Criteria:**

- A failed deploy of the API service or the web app (dev, test, or prod) posts a Slack message with a clickable link to the exact GitHub Actions run that failed, not a generic Actions tab or workflow list.
- Existing failure message content is preserved alongside the new link — the fix adds information, it doesn't remove any.
- The link format is identical between the API service's and the web app's notification steps.
- The failed step's label shown in the message is overridable, not tied to GitHub Actions' raw step name.
- The message includes the latest commit's author.

**Technical Notes:**

- Interpolate `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` into the existing failure message text at all 6 call sites: the API service's and the web app's `deploy_dev`/`deploy_test`/`deploy_prod` workflows.
- "Existing failure message content" = environment name, region, version.

Contrast with the AC these replace — "Deploy failures notify Slack with more detail" — which fails checks 1, 2, 3, and 4 in one sentence: no named environments, no observable field, no ruled-out shortcut, and no statement that old fields survive. Also contrast with an over-corrected version that inlines every path and line number into the bullets themselves — technically passes the six checks but fails the reviewer, who now has to parse workflow YAML to approve a sentence about user-visible behavior.

## Technical Notes

**Every bullet must change what the implementer does.** Technical Notes are
not a research digest, a findings summary, or a place to park observations that were interesting to
discover. Research lives in `research/`; the story quotes only the part that lands in the diff. Before a
bullet stays, it must answer at least one of:

- **Where** — the file, function, line range, job, env var, or resource the implementer edits or reads.
- **What to do or not do** — the mechanism to use, the shortcut that would be wrong, the ordering that
  matters, the status code / field / name that must be exact.
- **What is already true** — behaviour that exists, so the implementer builds less (and knows what they
  must not break).

**Delete on sight:**

- "Worth recording, not fixing here" / "latent risk" / "out of scope but noted" — if it is not being done
  in this story, it belongs in `research/` or its own story, never in Technical Notes. A note that
  explicitly says it is not actionable is the clearest possible failure of this bar.
- Supersession narrative — "this replaces the earlier framing", "an earlier draft assumed X", "finding `09`
  said Y but". The story states what is true now. Version history lives in the research files.
- Verification receipts that no longer change a decision — "verified on dev 2026-08-25 by grepping Z". If
  the conclusion is load-bearing, state the conclusion; cite the check only when the implementer would
  otherwise doubt it or needs to re-run it.
- Restated ACs and restated Context, in more words and with backticks.
- **Estimates and story points, in any form.** Not the number, not the calibration against a past ticket,
  not the per-repo breakdown. The team sets points at grooming, and a number in the ticket either anchors
  that conversation or contradicts its outcome. Planning-time effort belongs in the thread's Sizing table,
  which is where the split was argued and which no one syncs to Jira.
- **Advice the implementer would follow anyway** — "follow the existing convention", "match the
  surrounding code", "add tests", "the file to change is the obviously-named one". A bullet that states a
  default spends the reader's attention and dilutes the bullets carrying real constraints. It earns its
  place only when it *reverses* a default — and then it must say which one, because that is the whole
  content: "the enumeration AC does not mean 29 separate resources — copy `x.tf:157-186`" is a note; "follow
  the existing convention in `x.tf`" is not.
- **Ruled-out risks that were never tempting.** "The resource server's scope blocks are not restructured"
  reads like a guardrail, but if nothing in the story invites restructuring them, it guards nothing. A
  do-not-do bullet needs a plausible wrong path, not a hypothetical one.
- **Ordering advice for changes that are order-independent.** Sequencing is worth a bullet only when the
  wrong order breaks something — a token asserting one tenant against a record saying another, a command
  that cannot run until a permission exists. The tell is that the bullet refutes itself in its own
  subordinate clause: "land the Terraform first — the role is inert until a group grants it" says, in the
  same breath, that either order works.
- **Workshop-relative paths** — `research/07-…`, `constraints.md`, "see finding `02`". `story.md` is the
  only file pushed to Jira, so these resolve to nothing for the person reading the ticket. State the
  conclusion the finding reached; the finding itself stays discoverable in the workshop.
- **Diagnosis bullets that only set up the bullet after them.** A bullet with no imperative, whose content
  exists to explain why the next bullet is right, is half a note — merge the load-bearing pointers into that
  next bullet and delete the rest. This one hides well, because each half looks defensible alone: the
  diagnosis is true and cites real code, and the instruction reads fine. The test is whether the bullet
  survives on its own. If the implementer would act identically having never read it, it is prose.

Two bullets, same story, to calibrate:

> ❌ **Latent risk worth recording, not fixing here.** The mobile client is still configured for refresh
> tokens with `infinite_token_lifetime = true`, which is permissive of something the app does not do. If
> `offline_access` is ever added, the window silently becomes unbounded again.

> ✅ **Return `Unauthenticated`, never `PermissionDenied`.** The client funnels 401 into its single logout
> path (`lib/providers/api_provider.dart:119-120`); a 403 throws a snackbar error and the session keeps
> running (`:121-128`). The wrong status ships this story as a broken app instead of a logout.

The first is true, was expensive to learn, and is genuinely worth keeping — in `research/`. It tells the
implementer to do nothing. The second changes a line of code.

A third shape, harder to catch, is a true and well-cited bullet that still tells the implementer nothing:

> ❌ **The nine refusal strings in the login handler cannot reach mobile today.** The Action sets the claim
> on the ID token and continues the login (`triggers.tf:47-49`); only the web path converts it into a
> refusal (`process_callback.go:28-31`). Mobile's only gate is client-side.
>
> ✅ **Deliver the reason as an access-token claim: the Action sets it on the ID token only, so this is an
> add, not a read.** Put `api.accessToken.setCustomClaim(...)` beside the existing ID-token line
> (`triggers.tf:47-49`) and read it where the client already decodes that token
> (`auth_provider.dart:139-165`).

Same facts, same citations. The first states a gap; the second closes it, and carries the one fact from the
diagnosis that changes the work — the claim is on the wrong token, so the fix adds rather than reads.
