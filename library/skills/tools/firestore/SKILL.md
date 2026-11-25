---
name: firestore
description: "Firestore and Datastore modeling, queries, indexes and cost. Load when designing or reviewing a collection, kind, document, key, query or index; transactions, listeners, counts, pagination, hot writes; cutting a Firestore bill; backfilling."
tags: [backend, architecture, design]
---

# Firestore and Datastore

Design each screen or endpoint as one bounded query on an index you declared, and pay for every document you touch.

Firestore has two modes on one engine. Native mode speaks collections, documents and subcollections, with realtime listeners and mobile and web SDKs. Datastore mode speaks kinds, entities and ancestor keys, for server code only. The rules below hold for both modes. Rules 2 and 6 describe Standard edition, the only edition Datastore mode runs on. Enterprise edition bills and indexes differently, see [references/fundamentals.md](references/fundamentals.md). Mode-specific terms sit in the references.

## Rules every design follows

1. **Access patterns first.** List every read and write with its inputs, its result size and its rate before choosing a path or an index. A pattern with no index that serves it is a pattern you cannot run.
2. **Billing counts documents, not bytes or queries.** Standard edition bills one read per document returned, one write per document written, one delete per document deleted. Shape data so the hot read returns few documents.
3. **Shape documents for the read.** Denormalize into the document a screen loads. Storage is cheap and reads are not. Every copy needs one named writer that keeps it in sync.
4. **Bound every query.** Every list query carries `limit()` and pages with a cursor (`startAfter` or a Datastore cursor). An offset still bills each skipped document.
5. **A path is a key, not a join.** A subcollection groups children under a parent for scoped queries and rules. It does not make the parent load its children, and deleting the parent leaves them behind.
6. **Index on purpose.** Single-field indexes are automatic in Standard edition. Composite indexes live in a checked-in file (`firestore.indexes.json` or `index.yaml`). Exempt every field you never filter or sort on when it is large, a timestamp written in order, or a TTL field.
7. **A document missing a field drops out of any query that filters or orders on that field.** Write every queried field on every document, with an explicit default.
8. **Invariants live in a transaction, a `create()` or a precondition.** A read followed by an unconditioned write is check-then-act, and it races. Transaction bodies rerun on contention, so they hold no side effects.
9. **Spread writes.** Plan for about one sustained write per second per document. A field indexed in order (a timestamp, a sequential ID) sends every write to one index range, which caps that collection at about 500 writes per second. Shard the counter, randomize the ID, or exempt the field.
10. **Count with aggregation, not with reads.** `count()`, `sum()` and `avg()` bill one read per 1000 index entries. A maintained counter costs a write per change. Pick by read and write rates.
11. **TTL is cleanup, not expiry.** Expired documents linger before the policy deletes them. Compare an `expiresAt` field in queries and rules.

## Limits worth remembering

1 MiB per document or entity. 1,500 bytes per indexed string value. 40,000 index entries per document in Native mode, 20,000 per entity in Datastore mode. 100 levels of subcollection depth. 30 disjunctions per `in`, `array-contains-any` or `OR`, 10 values per `not-in`, 10 range or inequality fields per query. 270 seconds per transaction, 60 seconds idle.

## Where to read next

Read the reference that matches the branch you are on. Each one is self-contained.

| You are | Read |
|---|---|
| Choosing Native or Datastore mode, Standard or Enterprise edition, or a location, unsure about consistency, transactions per SDK or document versus entity terms, or looking up the full limits table | [references/fundamentals.md](references/fundamentals.md) |
| Deciding hierarchy (root collection, subcollection, map, array, ancestor key or entity group), placing tenants or namespaces, choosing IDs, modeling one-to-many or many-to-many, sizing a document | [references/modeling.md](references/modeling.md) |
| Writing a query, a composite index or an exemption, using `OR`, `in`, range filters on several fields, collection group queries, projections, text or vector search, paginating | [references/queries-indexes.md](references/queries-indexes.md) |
| Estimating or cutting the bill: reads per screen, listeners, security-rule reads, aggregation, caching, bundles, index storage, deletes, free tier, Enterprise units, Datastore small operations | [references/cost.md](references/cost.md) |
| Writing a transaction, a counter, a uniqueness record, a lease, an idempotency record, a trigger handler or a TTL policy, hitting contention or a hotspot | [references/concurrency.md](references/concurrency.md) |
| Adding a field, an index or a collection to live data, backfilling, moving or deleting a collection, exporting, importing or restoring, setting up the emulator or per-environment databases | [references/migrations.md](references/migrations.md) |

## Done when

- Every access pattern maps to one document get, one batched get, or one bounded query, and the composite index it needs is in the index file.
- Every screen's read cost is written as documents per load, and no list grows without `limit()`.
- Every invariant (uniqueness, single holder, max count, valid transition) is a transaction, a `create()` or a precondition, and its contention or already-exists error maps to an observable outcome.
- Every field written in sequence at a rate near 500 writes per second is exempted from indexing or prefixed to spread it.
