---
name: dynamodb
description: "DynamoDB data modeling and access design (single-table, GSI, race-free writes). Load when designing or reviewing a table, key, GSI or query; writing a lock, lease, idempotency or uniqueness record; using a transaction or TTL; migrating."
tags: [backend, architecture, design]
---

# DynamoDB

Design from access patterns, enforce every invariant inside a write, and treat every other read as a hint.

## Rules every design follows

1. **Access patterns first.** List every read and write pattern with its inputs before choosing a key. A pattern whose inputs cannot build the key needs a different key or an index.
2. **The caller must know the full key.** A key containing a value the caller has to look up first (a timestamp, a generated ID) is a race or a second request.
3. **Prefix keys by entity type**: `USER#<id>`, `ORDER#<ksuid>`. Prefixes keep types from colliding in one table and keep `begins_with` queries precise.
4. **Indexing attributes are separate from application attributes.** `PK`, `SK`, `GSI1PK`, `GSI1SK` hold keys. The entity keeps its own fields (`Username`, `Status`) as data, and every item carries a `Type` attribute.
5. **One module owns key construction.** Callers pass domain values, never `PK` strings.
6. **Query and GetItem serve the hot paths. Scan is for migrations and admin jobs.**
7. **Invariants live in a `ConditionExpression` or a transaction `ConditionCheck`.** An `if` in application code after a read is check-then-act, and it races.
8. **A GSI is eventually consistent, has non-unique keys, and joins no transaction.** Uniqueness, locks and "is it free" decisions go through base-table keys.
9. **TTL is cleanup, not expiry.** Store `ExpiresAt` as epoch seconds, compare it in conditions and filters, and set the TTL attribute (a Number) for garbage collection.
10. **Bounded growth per item.** 400 KB per item. A list that grows without bound becomes its own item collection.
11. **Spread write load across partition keys.** One partition key serves at most 1000 WCU/s and 3000 RCU/s. Shard a hot key (`DEALS#<date>#<shard>`).
12. **A request path makes a bounded number of queries.** A loop that queries once per id is N+1. Key the data so one query answers it, by the parent or with a sparse index that holds only the items the reader wants. Gate a feature's reads on its flag before the query runs. A filter, in code or in a `FilterExpression`, does not cut the read cost. Multiply every query on a polled endpoint by its request rate.

## Limits worth remembering

400 KB item. 1 MB per Query or Scan page, applied before the filter. 100 items and 4 MB per transaction, two capacity units per item. 25 items per BatchWriteItem, 100 per BatchGetItem, neither atomic. 20 GSIs by default, 5 LSIs, 10 GB per item collection with an LSI. TTL deletes typically within a few days. `ClientRequestToken` covers 10 minutes. Stream records live 24 hours.

## Where to read next

Read the reference that matches the branch you are on. Each one is self-contained.

| You are | Read |
|---|---|
| Writing a lock, lease, heartbeat, "one active X" slot, semaphore, idempotency or dedup record, one-time claim, or uniqueness marker | [references/locks.md](references/locks.md) |
| Reading one key and writing another, reading through a GSI, paginating, reading several items as one view, retrying, using streams or global tables | [references/concurrency.md](references/concurrency.md) |
| Unsure about item collections, partitions, consistency, Streams, TTL, the three action types, `ReturnValues`, `ConsistentRead`, or why not to use an ORM | [references/fundamentals.md](references/fundamentals.md) |
| Writing a key condition, filter, projection, condition or update expression | [references/expressions.md](references/expressions.md) |
| Starting a model: ERD, access-pattern list, entity chart, single-table versus multi-table, implementation hygiene | [references/modeling.md](references/modeling.md) |
| Modeling one-to-many or many-to-many: complex attribute, duplication, item collection, GSI, hierarchical sort key, adjacency list, materialized graph | [references/relationships.md](references/relationships.md) |
| Filtering by partition, sort key, composite sort key, sparse index or filter expression; sorting, sorting on a changing attribute, newest-first, zero-padding | [references/filtering-sorting.md](references/filtering-sorting.md) |
| Enforcing uniqueness on several attributes, sequential IDs, pagination tokens, singleton items, reference counts | [references/additional-strategies.md](references/additional-strategies.md) |
| Adding an attribute, entity or index to a live table, backfilling with a Scan, parallel scans | [references/migrations.md](references/migrations.md) |
| Looking for a precedent: session store, e-commerce, a deals site with hot keys and caches, a GitHub-like backend | [references/examples.md](references/examples.md) |

## Done when

- Every access pattern maps to one GetItem, Query, or transaction on a named index with its key condition written out.
- No request path runs a query inside a loop over ids.
- Every invariant (uniqueness, single holder, max count, valid state transition, version) is a condition on a write, and the item it is evaluated on is named.
- Every read that feeds a write decision is a strongly consistent base-table read, a `ConditionCheck`, or is accepted as a hint in writing.
- Each `ConditionalCheckFailed` and `TransactionCanceled` path maps to a distinct, observable outcome.
