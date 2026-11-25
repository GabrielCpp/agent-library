# Concurrency and visibility across keys

Read this when an access pattern reads one key and writes another, reads through an index, reads several items as if they were one view, or relies on a retry, TTL, a stream or a clock. DynamoDB guarantees atomicity and serializability on one item. Across items it guarantees only what a transaction or a strongly consistent base-table read gives you. Every race below comes from assuming more.

## What each read sees

Two separate axes apply: isolation against concurrent writes, and consistency (whether the read reflects every prior successful write).

| Read | Isolation vs Put/Update/Delete | Isolation vs TransactWriteItems | Strong read available |
|---|---|---|---|
| GetItem | serializable | serializable | yes, `ConsistentRead=true` |
| TransactGetItems | serializable | serializable, fails on conflict | always |
| BatchGetItem | serializable per item | read-committed as a unit | yes, per table |
| Query, Scan on table or LSI | read-committed | read-committed | yes |
| Query, Scan on GSI | read-committed | read-committed | **never** |

- Every read is eventually consistent unless you set `ConsistentRead=true`.
- Read-committed means no dirty reads. It does not stop the item changing the moment after you read it.
- Two GetItem calls on two items of one in-flight transaction can return one new and one old. Use TransactGetItems (up to 100 items, 4 MB) for a consistent multi-item view.
- After a transaction returns success, an eventually consistent read may still return the old state. Read your own write with `ConsistentRead=true` on the base key, or use `ReturnValues` from the write itself.

## Pagination is not a snapshot

- Each 1 MB page is a separate request. Writes between pages may or may not appear.
- A Query can see part of a concurrent transaction: some items new, some old.
- Do not rely on one page being a point-in-time snapshot either. AWS does not document it.
- A FilterExpression runs after the 1 MB cap. A page can be empty and still carry `LastEvaluatedKey`. Only a missing `LastEvaluatedKey` ends the iteration.

## Indexes

- GSIs update asynchronously, "within a fraction of a second" normally, longer in failure scenarios.
- A GSI cannot be read with `ConsistentRead`, cannot be used in a transaction, and its keys are not unique.
- Changing a GSI key attribute is a delete plus a put in the index. A reader can briefly see the old entry, the new one, neither, or both.
- A transaction's changes reach each GSI gradually, not as a unit.
- A GSI short on write capacity throttles writes to the base table.
- LSIs update with the base table and support strong reads. They cap each item collection at 10 GB and exist only from table creation.

Treat every GSI read as a hint. It can choose what to try, but never decide whether a write is allowed.

## What is atomic

- One PutItem, UpdateItem or DeleteItem is atomic. Its condition is evaluated against the latest version of that item, in the same step as the write.
- Writes to one item apply in the order received.
- TransactWriteItems is all-or-nothing over up to 100 distinct items and 4 MB, in one account and Region. `ConditionCheck` asserts on an item the transaction does not write.
- One transaction cannot touch the same item twice. A ConditionCheck and an Update on one item is rejected. Fold the condition into the Update.
- BatchWriteItem (25 puts or deletes, no updates) and BatchGetItem (100 items) are not atomic. Each item succeeds or fails alone, and readers can see half a batch. Retry `UnprocessedItems` and `UnprocessedKeys`.
- Transactions cost two units per item (prepare and commit), even when canceled. A failed conditional write still consumes write capacity.

## Errors that signal contention

| Error | Meaning | Response |
|---|---|---|
| `ConditionalCheckFailedException` | Your condition was false on the latest item. | Domain outcome: held, duplicate, stale version. Use `ReturnValuesOnConditionCheckFailure=ALL_OLD` to see the current item without a read. |
| `TransactionCanceledException` | One action failed. `CancellationReasons` is ordered like `TransactItems`. | Inspect by index. SDKs do not retry it. |
| `TransactionConflictException` | A plain write hit an item inside an in-flight transaction. | Retry with backoff. |
| `IdempotentParameterMismatchException` | Same `ClientRequestToken`, different parameters, within 10 minutes. | A bug: the token was reused for a different intent. |
| `ReplicatedWriteConflictException` | MRSC global table: a racing write in another Region. | Retry. |

A GetItem concurrent with a transaction does not conflict. Both succeed.

## Streams

- Each record appears once, and records for one primary key arrive in modification order.
- There is no order across items or item collections.
- The records of one transaction can arrive at different times and interleave with other transactions. A consumer cannot reconstruct transaction atomicity.
- Records expire after 24 hours. A write that changes nothing emits nothing. TTL deletes appear as service deletes.
- Lambda consumers retry, so handlers must be idempotent. Key the effect by the source event ID with `attribute_not_exists`.

## Global tables

- MREC (default): replication is async, usually under a second, last writer wins per item. Conditions, transactions and `ConsistentRead` are Region-local. A version check cannot protect an invariant across Regions. Pin each item's writes to one Region.
- MRSC: exactly three Regions. Writes and strong reads are consistent across Regions. Transactions, TTL and LSIs are not supported.

## Race catalogue

Each entry: the pattern that races, then the pattern that holds.

1. **Read then write one item.** GetItem, compute, PutItem loses a concurrent update. Use an update expression (`SET n = n + :d`) or a condition on the attribute you read (`#v = :v`, then `SET #v = :v + 1`).
2. **Check key A, write key B (write skew).** GetItem A, then PutItem B lets A change in between. Use TransactWriteItems with a `ConditionCheck` on A and the Put on B. Better still, move the invariant into one item so a single conditional write enforces it.
3. **Uniqueness by GSI query.** Query the GSI for the email, then Put if empty. Two callers both see empty. Put a marker item `PK=EMAIL#<email>` with `attribute_not_exists(PK)` in the same transaction as the owner.
4. **Count a collection, then insert ("at most N children").** A concurrent insert is a phantom your Query never saw. Keep a count on the parent. In one transaction, run `SET #c = #c + :one` with `#c < :max` on the parent and Put the child with `attribute_not_exists(PK)`.
5. **Child and parent counter as two calls.** A crash between them leaves the counter wrong. Write both in one transaction.
6. **Read-after-write through a GSI.** PutItem, then Query the GSI, misses the item. Read by base key with `ConsistentRead`, or use the write's `ReturnValues`.
7. **BatchWriteItem as a unit.** Parent and children in one batch can half-apply. Use TransactWriteItems when they must agree.
8. **Retrying a non-idempotent update after a timeout.** `ADD #n :one` retried double-counts. Pass a `ClientRequestToken` on a transaction, or condition on the value you expect, or write a request-ID item with `attribute_not_exists` in the same transaction.
9. **TTL as expiry.** An expired item stays readable for days. Store `ExpiresAt`, compare it in the condition, and filter it on read. TTL is cleanup. See [locks.md](locks.md).
10. **Wall-clock comparisons from many hosts.** `:now` comes from each client and DynamoDB has no server-time function in expressions. Add a margin larger than the skew, and fence the protected write with a token or version.
11. **Filter expression as a guard.** A filter shapes the result set. It protects no write. Put the guard in the write's `ConditionExpression` or a `ConditionCheck`.
12. **Delete then recreate.** After a delete, `attribute_not_exists` passes again. Use a tombstone or a surviving version when a key must never be reused.
13. **Hot transactional item.** Transactions on one item cancel each other. Back off instead of retrying in a tight loop. Split transactions that do not need atomicity, and keep attributes that are always updated together in one item.

## Checklist: a path reads key A and writes key B

1. Can the invariant live in one item, enforced by one conditional write? Prefer that: it is cheaper and cannot conflict with a transaction.
2. Otherwise, is A in the same TransactWriteItems as B, as a `ConditionCheck`?
3. Does any read that decides the write go through a GSI, an eventually consistent read, a filter, or a multi-page Query? Each is a hint, not a guard.
4. Does the decision depend on absence or a count? Replace it with a marker item or a counter attribute.
5. What does a concurrent reader see between two non-transactional writes? What does a crash between them leave?
6. Is every write idempotent under an SDK retry after a timeout?
7. Does any step trust TTL, a client clock, or stream order across items?
8. Is the table global? Then conditions hold per Region only.
9. Does each contention error map to a defined outcome?
10. Does a test run the contenders concurrently? A sequential test cannot show any race in this file.

## Sources

AWS DynamoDB Developer Guide, `https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/`: `transaction-apis.html` (isolation levels, limits, errors), `HowItWorks.ReadConsistency.html`, `GSI.html`, `LSI.html`, `Streams.html`, `V2globaltables_HowItWorks.html`, `WorkingWithItems.html` (conditional writes, atomic counters), `TTL.html`, `Query.Pagination.html`, `Query.FilterExpression.html`.
