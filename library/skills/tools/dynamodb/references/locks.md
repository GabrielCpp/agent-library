# Lock records, leases, claims and dedup items

Read this before writing any item whose job is to exclude a concurrent writer: a mutex or lease, a "one active X per Y" slot, a semaphore, an idempotency or dedup record, or a one-time claim. Every rule here comes from one fact: DynamoDB has no server-side locks and no held connection. A lock is a row, and the only atomic primitives are a condition on one item and a transaction across up to 100 items.

## Item shape

| Attribute | Type | Purpose |
|---|---|---|
| `PK` | S | `LOCK#<resource>`. Build it from values every contender already holds. A key that needs a read to compute is a race. |
| `SK` | S | A fixed constant such as `#ITEM` or `LOCK`. |
| `LockToken` | S | A fresh random ID (ULID, KSUID, UUID) minted on every acquire. It identifies one acquisition, not one user. |
| `Owner` | S | Who holds it, for display and for the error detail. Never the identity check. |
| `ExpiresAt` | N | Lease end in epoch seconds. Every acquire condition compares it. |
| `ttl` | N | Table TTL attribute, set to `ExpiresAt` plus a grace window. Garbage collection only. |
| `Fence` | N | Optional. A monotonic counter incremented on every acquire, for fencing downstream writes. |

The table's TTL attribute must be a Number holding epoch seconds. A String or an ISO date is silently ignored.

## Operations

| Operation | API | Condition | On ConditionalCheckFailed |
|---|---|---|---|
| Acquire | `PutItem` | `attribute_not_exists(PK) OR #exp < :now` | The lock is held. Return the holder from `ReturnValuesOnConditionCheckFailure=ALL_OLD`, so no second read is needed. |
| Re-acquire by the same holder | `PutItem` | `attribute_not_exists(PK) OR #exp < :now OR #tok = :myToken` | Same as acquire. |
| Renew (heartbeat) | `UpdateItem SET #exp = :newExp, #ttl = :newTtl` | `#tok = :myToken` | The lease is lost. Stop the work. |
| Release | `DeleteItem` | `#tok = :myToken` | The lease was lost before release. Report it, because the work ran unprotected for some window. |
| Admin override | `PutItem` with a new token | none | Not applicable. The old holder's next renew or release fails, and that is the signal. |
| Fenced acquire | `UpdateItem SET #tok = :new, #exp = :exp ADD #fence :one`, `ReturnValues=UPDATED_NEW` | the acquire condition | The lock is held. |

UpdateItem upserts. Every UpdateItem on a lock item carries a condition. An unconditioned `SET #ttl = :x` on a lock that was just released recreates a bare lock with no token or owner. That lock blocks every contender until it expires.

Delete with no condition frees whatever is there, including a lock a newer holder took after yours expired. Release conditions on the token, or on the owning entity's ID for a slot.

## Expiry is a comparison, TTL is cleanup

DynamoDB deletes expired items "typically within a few days". An expired item stays readable and still makes `attribute_not_exists(PK)` false. Every acquire therefore includes `OR #exp < :now`, and every read that decides "is it held" compares `ExpiresAt` to now.

- `:now` comes from the writer's clock. Hosts skew. Make the lease length a multiple of the worst skew you tolerate, and renew at no more than a third of the lease.
- Compare numbers, epoch seconds. A lexical compare on RFC3339 strings works only when every writer uses UTC with the same precision and format.
- Size the lease to the work. A lease tied to a user session or a day-long TTL holds the resource for that long after a crash. A short lease with heartbeats frees it within one lease of the crash.

## Doing work under the lock

A lease can expire while the holder still runs: a GC pause, a slow downstream call, a network partition. "I acquired it" does not mean "I still hold it" at write time.

First check whether the holder can outlive its lease. Find the holder's own deadline: an SQS handler's visibility timeout without heartbeats, a request timeout, a job's context deadline. When that deadline always ends before the lease does, the holder dies first and the lease cannot expire under it. Write no renew loop and no abort-on-lost-lease context in that case, because no input reaches them. Keep the lease longer than the deadline, and keep that relation true when either value changes.

When the holder can outlive the lease, pick one of these, in order of strength:

1. **Guard the write with a transaction.** Put a `ConditionCheck` on the lock item (`#tok = :myToken AND #exp > :now`) in the same `TransactWriteItems` as the protected write. The write lands only if the lock is still yours at commit. This is the only form that holds when the protected data is in DynamoDB.
2. **Fence downstream systems.** Pass the `Fence` value with every downstream write, and have the downstream reject a fence lower than the highest it has seen. Use this when the protected resource is outside DynamoDB (an external API, a file).
3. **Renew and abort.** Heartbeat, and stop at the first failed renew. This narrows the window but does not close it.

A save that reads the lock, checks the holder in memory, then writes unconditionally is check-then-act across two keys. A concurrent override or a second save lands between the read and the write. Move the check into the write's condition or into a `ConditionCheck`.

## Variants

**Lock created with its entity.** When the lock exists to stop a duplicate entity (one open alert per room), write the lock `Put` and the entity `Put` in one `TransactWriteItems`. Release the lock in the same transaction that moves the entity to its terminal state. `CancellationReasons[i].Code == "ConditionalCheckFailed"` at the lock's index means a duplicate.

**One-active-X slot.** `PK=SLOT#<scope>`, no expiry, holding the owning entity's ID. Acquire with `attribute_not_exists(PK)` in the entity's create transaction. Release with `#owner = :entityId`, so a late terminal write from an older entity cannot free a newer entity's slot. A slot with no TTL needs a recovery path for an owner that never reaches a terminal state.

**Counting semaphore.** A singleton item holding a string set of holder IDs. Acquire: `ADD #holders :idSet`, condition `attribute_not_exists(#holders) OR size(#holders) < :max OR contains(#holders, :id)`. Release: `DELETE #holders :idSet`. Use `<`, not `<=`, or the set reaches max plus one. The first acquire needs the `attribute_not_exists` branch, because `size()` of a missing attribute makes the condition false. Set ADD is idempotent, so a retried acquire is safe. Holders that crash leak a slot, so pair the set with per-holder expiry items or a reaper.

**Idempotency or dedup record.** `PK=<operation>#<request or event id>`, written with `attribute_not_exists(PK) OR #ttl < :now` in the same transaction as the effect. `ttl` is the dedup window. Derive the ID from the input (event ID, a hash of the payload without timestamps), so that a redelivery produces the same key. ConditionalCheckFailed means already done. Return success and skip the side effect.

**One-time claim.** A use-once token (ticket, ack, invite): `UpdateItem SET #usedAt = :now REMOVE #secret`, condition `attribute_exists(PK) AND attribute_not_exists(#usedAt) AND #exp > :now`, `ReturnValues=ALL_OLD`. The read and the claim are one operation, so two redeemers cannot both succeed.

**Uniqueness marker.** `PK=SK=<TYPE>#<value>` with no other attributes, put with `attribute_not_exists(PK)` in the same transaction as the owning item. Changing the value is one transaction: delete the old marker (conditioned on owner), put the new marker, update the owner. A GSI query can never enforce uniqueness, because GSIs are eventually consistent.

## Errors and observability

- Map ConditionalCheckFailed on acquire to "already exists" or "held", and attach the holder as structured detail. Do not serialize it into the message.
- Map a failed renew or release to "lost". Count it in a metric. A silent nil on a lost release hides the case where the work ran without the lock.
- In a transaction, read `TransactionCanceledException.CancellationReasons` by index to know which item failed. `TransactionConflict` means a concurrent transaction touched the same item. Retry it with backoff.
- Pass `ClientRequestToken` on `TransactWriteItems`, so an SDK retry after a timeout within 10 minutes does not double-apply.

## Hot locks

One lock item lives on one partition: at most 1000 WCU/s and 3000 RCU/s. A single global lock for a busy workload hits that ceiling. Lock per resource, not per type.

## Checklist before shipping a lock

- [ ] The key is computable by every contender without a read.
- [ ] Acquire compares expiry in the condition, not only through TTL.
- [ ] Every UpdateItem and DeleteItem on the lock carries a token or owner condition.
- [ ] The protected write is guarded by a `ConditionCheck` or a fence, or the gap is accepted and documented.
- [ ] The lease length covers the slowest normal run. A heartbeat exists only when the holder's own deadline can outlast the lease.
- [ ] ConditionalCheckFailed on acquire, renew and release each maps to a distinct, observable outcome.
- [ ] A crash at every step leaves a state the next contender can recover from within one lease.
