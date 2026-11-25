# Queries and indexes

Read this when writing a query, adding a composite index or an exemption, or paginating.

Every Standard edition query is served by an index, and the work it does is proportional to the result set, not the collection. A query that needs an index you did not declare fails with `FAILED_PRECONDITION` and a link that creates it. Copy that index into the checked-in file, not into the console only.

## Index types

| Index | Created | Serves |
|---|---|---|
| Single-field, ascending and descending | automatically, per field, collection scope | equality and range on one field, `orderBy` on one field |
| Single-field `array-contains` | automatically, per array field | `array-contains`, `array-contains-any` |
| Composite | by you, per collection or collection group | several filters, or a filter plus an `orderBy` on another field |
| Collection group scope | by you, single-field or composite | queries over every collection with one ID |
| Vector | by you | `findNearest` on an embedding field |
| Datastore built-in | automatically per property | single-property queries, ancestor plus equality |
| Datastore composite | `index.yaml` | everything else, including projections and ancestor plus sort |

Equality-only queries on several fields can often run on single-field indexes alone, through a merge join. Add a composite index when the planner asks for one or when the merge is slow on a large collection.

## Composite index field order

Order fields so the index is one contiguous range for the query:

1. Equality fields (`==`, `in`, `array-contains`) first.
2. Then range or inequality fields (`<`, `>`, `!=`, `not-in`), most selective first.
3. Then any `orderBy` field that carries no range filter.

Write the query's `orderBy` in the same sequence, with the most selective range field first. Firestore appends range fields you leave out of `orderBy` to the ordering implicitly. A query may filter by range on up to 10 fields. Each extra range field scans index entries it does not return, so latency grows with the entries scanned. Standard edition bills returned documents, and a query with range filters on two or more fields also bills one read per 1,000 index entries scanned. Convert a low-cardinality range into an equality (`status in [...]` instead of `status < 3`).

## Query capabilities

- `in` and `array-contains-any` take up to 30 values. `OR` filters expand to disjunctive normal form and allow up to 30 disjunctions. Each disjunction may need its own index.
- `not-in` takes up to 10 values. `!=` and `not-in` exclude documents where the field is missing. Both are range filters for index purposes.
- One `array-contains` or `array-contains-any` per disjunction.
- `orderBy` on a field drops documents that lack it.
- Collection group queries need a collection-group-scoped index, and security rules must allow the `{path=**}` match.
- `select()` projections cut network bytes. In Standard edition they still bill one read per document. In Datastore mode a projection query on indexed properties is a small operation, see [cost.md](cost.md).
- Aggregations (`count()`, `sum()`, `avg()`) run on the index and return one number. Use them for totals instead of fetching documents.
- Text search by prefix: `where('name', '>=', p).where('name', '<', p + '\uf8ff')`. Anything richer (contains, fuzzy, ranking) belongs in a search index such as Typesense, Algolia or Vertex AI Search, fed by a trigger. Enterprise edition adds built-in text and geospatial search, in Preview at the time of writing.
- Security rules are not filters. A client query fails whole when it could return a document the rules deny, so the query carries the same constraint the rule checks (`where('ownerId', '==', uid)`).
- Vector search: store embeddings in a vector field, create a vector index with the dimension and distance measure, and query with `findNearest` plus a `limit`. Prefilter with equality filters that the vector index includes.

## Pagination

- Page with `orderBy` plus `startAfter(lastSnapshot)` or `startAfter(...values)`. Add a unique tiebreaker such as the document ID to the `orderBy` so ties do not repeat or skip.
- Skip ahead with cursors only. An `offset` bills every skipped document as a read and adds latency.
- Return an opaque cursor to API clients: the encoded `orderBy` values of the last document, or a Datastore `endCursor`.
- Total counts for a paged UI come from `count()`, run once per filter change, not per page.

## Exemptions and exploding indexes

Every indexed field adds index entries on every write: storage cost and write latency. Exempt a field from single-field indexing when:

- it holds a large string, map or array you never query,
- it is a timestamp or sequential value written at high rate and you never filter on it alone, because writes in order all land on one index range and hotspot,
- it is the TTL field.

A composite index on several array or map fields indexes the cross product of their values. Two arrays of 100 values make 10,000 entries per document, close to the 40,000 cap (20,000 in Datastore mode). Avoid composite indexes over more than one multi-valued field. In Datastore mode, exclude list properties from the built-in indexes when you only need them in one composite.

Exemptions take a field path and apply per collection or collection group. Keep them in the index file next to the composite indexes, so a fresh environment matches production.

## Index lifecycle

- Building a composite index on a large collection takes minutes to hours. Deploy indexes before the code that queries them.
- Removing an index the code still uses breaks that query at once. Remove indexes after the code.
- Enterprise edition has no automatic single-field indexes. Declare an index for each filtered or sorted field the hot queries use, and use query explain to confirm the plan reads an index rather than scanning.
- Use `explain()` (query explain) to see index entries scanned versus documents returned. A ratio far above one means a better index or a more selective first field.

## Datastore mode query notes

- GQL and the SDK builders compile to the same queries and need the same indexes.
- Ancestor queries scope to one subtree and need a composite index when combined with sort or inequality.
- Keys-only queries return keys without entities. Pair with a batched lookup when you need only some of them.
- `DISTINCT ON` projections need a composite index and are billed as entity reads.

## Sources

- https://docs.cloud.google.com/firestore/native/docs/query-data/queries
- https://docs.cloud.google.com/firestore/native/docs/query-data/multiple-range-fields
- https://docs.cloud.google.com/firestore/native/docs/storage-size
- https://docs.cloud.google.com/firestore/native/docs/vector-search
- https://docs.cloud.google.com/datastore/docs/concepts/queries
