# Keeping the bill small

Read this when estimating cost, reviewing a design for cost, or tracing a bill spike. Reads dominate almost every Firestore bill, so start there.

## What is billed

**Standard edition, both modes.**

| Charge | Unit | Notes |
|---|---|---|
| Read | one per document returned or fetched | a query with no result bills one read, and each offset-skipped document bills one read |
| Aggregation | one read per batch of up to 1,000 index entries matched | `count()`, `sum()`, `avg()` |
| Index scan | one read per batch of up to 1,000 index entries scanned | queries with range filters on two or more fields |
| Write | one per document written | `set`, `update`, `create`, a field transform, each document in a batch or transaction |
| Delete | one per document deleted | includes TTL deletes and recursive deletes |
| Storage | GiB-month of documents plus index entries | each index entry carries the document name and the indexed values |
| Network egress | GiB | free to compute in the same region |
| PITR, backups | GiB-month | PITR roughly doubles retained storage |

Batching, transactions and `getAll` reduce round trips, not billed operations. A batch of 100 writes bills 100 writes.

The Standard edition free tier gives 50,000 reads, 20,000 writes and 20,000 deletes per day, and 1 GiB stored. It applies to one database per project: the first one created. Extra databases, staging included, bill from the first operation.

**Datastore mode** bills entity reads, writes and deletes the same way. Small operations are free: keys-only queries and projection queries without `DISTINCT ON` return results that do not bill per entity, and `allocateIds` is free. The query itself bills one entity read.

**Enterprise edition** bills one read unit per 4 KiB read and one write unit per 1 KiB written. Index entries consume write units, and deletes bill as write units. Small documents and few indexes make it cheaper. A query with no index scans and bills every document it visits. Its free tier gives 50,000 read units and 40,000 write units per day, with deletes counted as write units.

## Estimate before you build

For each access pattern: documents read per call times calls per day. Sum per screen, then per daily active user. A feed that loads 50 documents per open, opened 20 times a day by 10,000 users, reads 10 million documents a day. Compare that row against the price per 100,000 reads in the current pricing page before shipping.

## Read patterns that cut cost

1. **Summary documents.** Keep a `views/{screen}` or a parent-level summary that a writer updates. One read replaces N. Pay with one extra write per change, which wins whenever the screen is read more often than the data changes.
2. **Bucket small records** into one document per time window or parent. One read returns hundreds of records. See [modeling.md](modeling.md).
3. **Limit and page every list.** `limit(20)` with a cursor, as [queries-indexes.md](queries-indexes.md) describes.
4. **Count with `count()`**, not by fetching. Keep a maintained counter only when the count is read far more often than its 1,000-entry batches would cost.
5. **Cache on the client.** Mobile and web SDKs keep an offline cache. Read with `source: 'cache'` for data that changes rarely, and let listeners serve repeat views.
6. **Bundles for shared data.** A data bundle built server-side and served from a CDN gives every client the same query result for the price of one build. Use it for catalogs, config and leaderboards.
7. **Cache in the server.** A process-level cache with a short TTL in front of hot, shared documents (feature flags, settings) turns millions of reads into a few.
8. **Datastore keys-only first.** Run a keys-only query, filter keys you already hold in a cache, then look up only the missing entities.
9. **Stale reads for reports.** They cost the same per document but run on less contended replicas. Export to BigQuery for analytics instead of scanning collections from code.

## Listener patterns

- A listener bills one read per document in the initial result, then one read per document added or changed, and one per document that leaves the result because it changed. A document deleted from the result costs no read.
- A listener that reconnects after more than 30 minutes offline bills the full result again. With offline persistence off, every reconnect bills the full result again.
- Scope every listener with filters and `limit()`. A listener on a whole collection bills every write anyone makes to it.
- Detach listeners when the screen goes away. A leaked listener in a single-page app bills forever.
- Prefer one listener on a summary document over many listeners on detail documents.

## Security rules

- Each document a rule reads with `get()` or `exists()` bills one read per request, once even when the rule reads it several times. A rule that reads a user document bills that read on every request the user makes.
- Put roles and tenant IDs in custom auth claims (`request.auth.token.role`) instead of reading a user document in every rule.
- Match ownership from the path (`users/{uid}/...`) so the rule compares strings and reads nothing.

## Write and storage patterns

1. **Exempt unused fields from indexing.** Index entries bill as storage and slow writes. Large maps, long strings and arrays you never query are the biggest wins.
2. **Write only what changed.** `update` with field paths bills the same one write as a full `set`, but it avoids rewriting large values and their index entries.
3. **Coalesce frequent updates.** A document updated every second for a progress bar bills 86,400 writes a day. Update every few seconds from the client, or keep fast-changing state in memory or Realtime Database.
4. **TTL for disposable data.** A TTL policy deletes expired sessions, logs and caches without code. Each deletion bills as a delete, with no free tier. TTL behaviour sits in [concurrency.md](concurrency.md).
5. **Size the retention.** PITR and scheduled backups bill storage. Turn them on for production, not for every scratch database.

## Tracing a bill spike

1. Open the usage tab or Cloud Monitoring `document/read_count` broken down by database.
2. Turn on query insights or audit logs to find the query and caller.
3. Look first for: a listener without `limit`, a list using `offset`, a rule doing `get()` on every request, a job scanning a collection on a schedule, a retry loop rereading on every failure.

## Sources

- https://cloud.google.com/firestore/pricing
- https://cloud.google.com/datastore/pricing
- https://firebase.google.com/docs/firestore/enterprise/pricing
- https://docs.cloud.google.com/firestore/native/docs/storage-size
- https://docs.cloud.google.com/firestore/native/docs/ttl
