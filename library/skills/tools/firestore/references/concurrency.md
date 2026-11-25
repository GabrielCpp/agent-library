# Transactions, contention, hotspots and race-free records

Read this before writing a transaction, a counter, a uniqueness record, a lease, an idempotency record or a trigger handler, or when a write path hits contention or a hotspot.

## Pick the smallest primitive

| Need | Primitive |
|---|---|
| Increment, append to a set, stamp server time | field transform: `FieldValue.increment`, `arrayUnion`, `arrayRemove`, `serverTimestamp` |
| Create only if absent | `create()`. Already-exists is the duplicate signal. |
| Update only if unchanged since my read | `update` with a `lastUpdateTime` precondition (server SDKs) |
| Several writes land together, no reads decide them | batched write |
| A read decides a write | transaction |
| Several reads must agree, no write follows | read-only transaction, or reads at one `readTime` |

A transaction locks or validates every document it reads. Use it only when a read decides the write.

## Transaction rules

- Read every document first, then write. SDKs reject a read after a write.
- The function reruns on contention. Keep it free of side effects: no emails, no HTTP calls, no counters in memory. Return a value and act on it after the transaction commits.
- Keep it short. Under the default `PESSIMISTIC` concurrency mode of Standard edition, server SDK transactions lock what they read, so a slow body blocks other writers and can hit the 270 second cap or the 60 second idle expiry.
- Read the fewest documents that decide the write. A query inside a transaction locks every document it returns.
- Mobile and web transactions are optimistic and fail offline. Move invariants a client must not bypass into a server endpoint or a security rule.
- Map `ABORTED` after retries to a contention outcome, and `ALREADY_EXISTS` or `FAILED_PRECONDITION` to the domain outcome they signal.

## Hotspots

| Source | Ceiling | Fix |
|---|---|---|
| One document written often | about 1 write per second sustained, as a planning figure | shard it, coalesce writes, or move the state out of Firestore |
| Sequential document IDs | one key range takes all writes | auto IDs, or a hash prefix on the ID |
| Indexed field written in order (`createdAt`, a sequence) | about 500 writes per second for the collection | exempt the field from single-field indexing, or prefix it with a shard |
| A new collection or a sudden surge | splits lag behind load | ramp with 500/50/5, or pre-warm with synthetic load |

A composite index whose first field is low-cardinality equality (`tenantId`) followed by a timestamp spreads writes across tenants. A single-field index on the timestamp alone does not, so exempt it.

## Counters

- **Low rate:** `increment` on the parent.
- **High rate:** a distributed counter. `counters/{name}/shards/{0..N-1}`, each write increments a random shard, readers sum the shards (N reads) or run `sum()` on them. N equals the peak writes per second.
- **Read-heavy totals that tolerate seconds of lag:** a trigger aggregates into the summary document.
- **Exact count on demand, rarely read:** `count()` and no counter at all.
- **"At most N children":** a transaction that reads the parent counter, checks it, increments it and creates the child. A `count()` before insert is a phantom race.

## Uniqueness

- Use the unique value as the document ID: `usernames/{username}` with `create()`. Write it in the same transaction or batch as the owner.
- Changing the value is one transaction: delete the old marker after checking it belongs to the owner, create the new marker, update the owner.
- A query for "does any document have this email" cannot enforce uniqueness. Two callers both see none.
- Normalize the value (lowercase, trimmed, NFC) before building the ID.

## Leases and locks

`locks/{resource}` with `holder`, `token` (fresh per acquire) and `expiresAt`.

- Acquire: a transaction reads the lock and writes it only when it is absent or `expiresAt < now`.
- Renew and release: a transaction that checks `token` matches first.
- Guard the protected write inside the same transaction as a read of the lock, when the protected data is in Firestore. Fence external systems with a monotonic counter on the lock.
- `now` comes from the caller's clock. Leave a margin larger than the clock skew.

## Idempotency and triggers

- Cloud Functions and Eventarc deliver Firestore events at least once and in no guaranteed order.
- Key every effect by the event ID: `create()` `processedEvents/{eventId}` in the same transaction as the effect. Already-exists means done.
- A trigger that writes to the document that fired it fires again. Guard with a field comparison or write elsewhere.
- Compare `before` and `after` in update triggers. Act only on the fields you care about.
- Order-sensitive consumers compare a version or `updateTime` on the target and drop older events.

## TTL and expiry

- A TTL policy deletes a document some time after its timestamp field passes, typically within 24 hours. The document stays readable until then.
- Filter `expiresAt > now` in queries and compare it in rules and transactions.
- The TTL field must hold a timestamp. A document without it, or with another type, is never deleted.
- Exempt the TTL field from indexing unless you query it. Expiry timestamps written in order are a sequential index.
- TTL deletes do not cascade to subcollections.
- TTL deletes fire listeners and triggers like any delete. A delete trigger that must tell expiry from a user action checks `expiresAt` on the deleted snapshot.
- A collection group takes one TTL field.

## Checklist before shipping a write path

- [ ] Each read that decides a write is inside the same transaction, or the invariant is a `create()` or a precondition.
- [ ] The transaction body has no side effects and reads before it writes.
- [ ] No document takes more than one write per second at peak, and no sequential indexed field nears 500 writes per second.
- [ ] Every trigger handler is idempotent by event ID and tolerates reordering.
- [ ] Expiry is compared in code, not left to TTL.
- [ ] A test runs the contenders concurrently against the emulator. A sequential test cannot show a race.

## Sources

- https://docs.cloud.google.com/firestore/native/docs/transaction-data-contention
- https://docs.cloud.google.com/firestore/native/docs/best-practices
- https://docs.cloud.google.com/firestore/native/docs/understand-reads-writes-scale
- https://docs.cloud.google.com/firestore/native/docs/extend-with-functions-2nd-gen
- https://docs.cloud.google.com/firestore/native/docs/ttl
