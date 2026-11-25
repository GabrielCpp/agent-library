# Modes, editions, consistency and limits

Read this when choosing a mode or edition, when the terms of one mode appear in code written for the other, or when you need a limit that the skill body does not list.

## One engine, two modes

| | Native mode | Datastore mode |
|---|---|---|
| Unit | document in a collection | entity of a kind |
| Hierarchy | `users/{uid}/orders/{orderId}`, subcollections | key path `User:uid > Order:orderId`, ancestors |
| Clients | server SDKs, mobile and web SDKs, REST, gRPC | server SDKs, REST, gRPC only |
| Realtime listeners, offline cache | yes | no |
| Security rules | yes, for mobile and web clients | no, IAM only |
| Query language | SDK builders, pipeline queries in Enterprise | SDK builders, GQL |
| Composite index file | `firestore.indexes.json` (Firebase CLI) or Terraform `google_firestore_index` | `index.yaml` (`gcloud datastore indexes create`) or Terraform |
| Exclude from index | single-field index exemption per field path | `excludeFromIndexes` per property, on every write |

Pick Native mode when a mobile or web client reads the database directly or needs listeners. Pick Datastore mode for server-only workloads that already use the Datastore API or App Engine. A project can hold several databases, each with its own mode, so one service does not force the mode of another. A database picks its mode at creation and can switch only while it is empty.

A database's location is fixed at creation: one region, or a multi-region that survives a regional outage at a higher price. Place it in or beside the region of the compute that reads it, because cross-region reads add latency and egress.

Datastore mode queries are strongly consistent, ancestor or not. The legacy entity-group limits (1 write per second per group, 25 groups per transaction) apply only to a database in `OPTIMISTIC_WITH_ENTITY_GROUPS` concurrency mode, which upgraded legacy databases carry. Switch such a database to `OPTIMISTIC` or `PESSIMISTIC` and the limits go. Code written around them (ancestor queries only for consistency, one entity group per user) is then optional design, not a requirement.

## Editions

**Standard edition** is the classic billing and indexing model. Every field gets automatic single-field indexes, every query must be served by an index, and billing counts documents.

**Enterprise edition** runs Native mode or MongoDB compatibility. Datastore mode runs on Standard edition only. Enterprise bills by size, see [cost.md](cost.md). It creates no automatic indexes, and runs a query with no index by scanning every document it visits, so add an index for each hot query. It adds pipeline queries, and MongoDB compatibility raises the document size limit to 16 MiB. Treat the edition as a cost model choice: small documents and few indexes favor Enterprise, high read counts of large documents favor whichever the pricing calculator says for the measured load.

## Consistency

- Reads and queries are strongly consistent in both modes. A query sees every write that committed before it started.
- A realtime listener delivers a local, latency-compensated snapshot first. `hasPendingWrites` and `fromCache` on the snapshot metadata tell you whether the server has confirmed it.
- Stale reads trade freshness for latency and cost nothing extra: pass a `readTime` within the last hour, or within the point-in-time recovery window when PITR is on. Use them for reports and exports that do not decide a write.
- Paging with cursors is not a snapshot. Writes between pages may appear or not. Run every page at one `readTime` when the report must be a snapshot.

## Writes and transactions

| Primitive | Atomic | Reads | Use for |
|---|---|---|---|
| `set`, `update`, `delete` on one document | yes | none | single-document changes |
| `create()` | yes, fails with already-exists | none | uniqueness by document ID |
| `update` with a `lastUpdateTime` precondition (server SDKs) | yes | the caller's earlier read | optimistic concurrency on one document |
| Field transforms: `increment`, `arrayUnion`, `arrayRemove`, `serverTimestamp` | yes | none | counters and sets without a read |
| Batched write | all or nothing | none | several writes that must land together |
| Transaction | all or nothing, serializable | reads inside it | read, decide, write |
| `BulkWriter` | per document | none | backfills and bulk deletes, not atomic |

Each database has a concurrency mode, set with `gcloud firestore databases update --concurrency-mode`. Standard edition and Datastore mode default to `PESSIMISTIC`, Enterprise to `OPTIMISTIC`. Server SDKs follow the database setting. Under pessimistic mode a transaction locks the documents it reads, so a contended document makes other writers wait or abort. Mobile and web SDKs always use optimistic concurrency: the transaction rereads and retries when a read document changed, and it fails offline. Every SDK reruns the transaction function on retry. Reads come before writes inside the function.

## Limits

| Limit | Value |
|---|---|
| Document size | 1 MiB (1,048,576 bytes) |
| Entity size (Datastore) | 1,048,572 bytes |
| Document name or key | 6 KiB |
| Subcollection depth | 100 |
| Indexed string, byte value | 1,500 bytes, longer values are truncated in the index |
| Index entry size | 7.5 KiB |
| Index entries per document (Native) | 40,000 |
| Index entries per entity (Datastore) | 20,000 |
| Composite indexes per database | 200 without billing, 1,000 with billing |
| Single-field index configurations (exemptions and TTL policies) | 200 without billing, 1,000 with billing |
| Composite index entry size per entity (Datastore) | 2 MiB in total |
| Request size (commit, batch, transaction) | 10 MiB |
| Field transforms per document per commit | 500 |
| Transaction duration | 270 seconds, expires after 60 seconds idle |
| `in`, `array-contains-any`, `OR` disjunctions | 30 after expansion to disjunctive normal form |
| `not-in` values | 10 |
| Range or inequality fields per query | 10 |
| Databases per project | 100 by default |
| Sustained writes to one document | about 1 per second, a planning figure the docs no longer state |
| Writes to a collection with a sequential indexed field | 500 per second |
| Security rule `get()` and `exists()` calls | 10 per request, 20 for a batch or transaction |
| Stale read window | 1 hour, or the PITR window (7 days) when PITR is on |

## Sources

- https://docs.cloud.google.com/firestore/docs/editions
- https://docs.cloud.google.com/firestore/quotas
- https://docs.cloud.google.com/datastore/docs/concepts/limits
- https://docs.cloud.google.com/datastore/docs/concepts/transactions
- https://docs.cloud.google.com/firestore/native/docs/transaction-data-contention
- https://docs.cloud.google.com/firestore/native/docs/pitr
- https://docs.cloud.google.com/firestore/native/docs/manage-databases
- https://docs.cloud.google.com/firestore/native/docs/best-practices
