# Async work must not outlive its context

A response may only write to state that belongs to the context its request was sent for. The
kind of request decides how that is enforced:

| Kind | Enforcement | Why |
|---|---|---|
| Read | Latest wins (1.1) | Reads are cheap to discard. Locking the UI for a read makes the screen feel stuck. |
| Write session | Lock the context for the whole session (1.2) | A write cannot be undone silently. Guarding responses one at a time leaves gaps. |
| One-off write | Capture every input at confirm (1.3) | The user confirmed specific values. The write must use exactly those. |

## 1.1 Latest read wins

**Trigger.** A response handler assigns state, and nothing checks that the request is still the
latest one for the current context.

**Fix.** Use one of two tools:

- A **generation counter**. Increment it when the request starts, capture the value, and assign
  only if the captured value still equals the counter when the response arrives.
- An **abort signal**. Abort the previous request when a new one starts. Treat the abort error
  as a normal outcome, not a failure.

Keep the UI interactive during the read.

**Counter-case.** The context cannot change during the request's life, such as a config load
before the first screen renders.

## 1.2 Lock the write session

**Trigger.** A control that changes the context stays enabled while the user has unsaved edits
or a save is in flight.

**Fix.** Lock every context control from the first request of the session until the final write
is confirmed. Show a pending state on the control that ends the session, such as a spinner on
Save. Unlock on success and on failure.

**Counter-case.** Drafts are stored per context, keyed by the context's id. Switching context
then parks the draft instead of corrupting it.

## 1.3 Capture at confirm

**Trigger.** A dialog's confirm handler reads page state after its first await. The usual shape
is a handler that awaits a validation call, then reads the selected record.

**Fix.** Read every input when the user confirms. Pass them to the write as arguments. The write
function takes no input from shared state.

## 1.4 Capture before await

**Trigger.** Inside an async function, a read of mutable or reactive state appears after the
first await. A second shape: work is queued, and the queued function reads state when it runs
instead of when it was queued.

**Fix.** Copy every value the function needs into locals before the first await. After the
await, use only the locals. A queued job receives its inputs as arguments at enqueue time.

**Counter-case.** The read after the await is the point, such as re-checking a cancellation flag.
Name it as a cancellation check so a reviewer sees the intent.

## 1.5 One flag per lock

**Trigger.** Two or more controls decide "disabled" from different combinations of booleans. One
checks `saving`, another checks `saving || editing`.

**Fix.** Expose the lock as one derived boolean, for example
`contextLocked = savePending || editMode`. Every context control reads that one value.

## 1.6 Name the race in a test

**Trigger.** A guard from 1.1 to 1.5 exists, and no test proves it.

**Fix.** Write one test per guard:

1. Mock the request with a deferred handler that only responds when the test releases it.
2. Start the request.
3. Change the context, or try to.
4. Release the response.
5. Assert the state belongs to the right context, or that the control was locked.

Name the race in the test's title. Watch the test fail with the guard removed before trusting
it. Put tests that drive a widget known to flake in their own file, so a flake there does not
hide a race regression elsewhere.
