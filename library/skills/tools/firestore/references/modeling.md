# Hierarchy, document shape and relationships

Read this when starting a model, deciding where a child entity lives, choosing IDs, or sizing a document.

## Process

1. List entities and relationships.
2. List access patterns as a table: pattern, inputs, query, index, documents read per call, calls per day.
3. Place each entity: root collection, subcollection, map field, array field, or inside its parent.
4. Write the query for each pattern and the composite index it needs.
5. Multiply documents read by calls per day. Restructure the patterns that dominate.

A pattern whose cost row reads "N documents per page view" with N unbounded is the first to restructure.

## Where a child lives

| Place | Query scope | Read cost to load with parent | Size bound | Choose when |
|---|---|---|---|---|
| Field in the parent (map, array) | none, it is the parent | 0 extra | parent's 1 MiB | the set is small, bounded, always read with the parent, rarely written |
| Subcollection `parents/{id}/children` | one parent, or all parents with a collection group query | 1 per child | none | children are unbounded or written independently, and most reads are per parent |
| Root collection `children` with `parentId` | any filter | 1 per child | none | children are queried across parents as often as within one, or have several parents |
| Datastore ancestor key `Parent:id > Child:id` | ancestor query | 1 per child | none | the same cases as a subcollection, in Datastore mode |

Hierarchy notes:

- A subcollection and a root collection with a `parentId` field cost the same per read. Choose by query scope and by security rules. Rules on `users/{uid}/...` match the owner from the path, with no extra read.
- The parent document can be absent while its subcollection holds documents. The console shows it in italics, and a parent query never returns it.
- Deleting a parent deletes nothing below it. Delete subcollections explicitly, see [migrations.md](migrations.md).
- A collection group query reads every collection with that ID at any depth. Give unrelated collections distinct IDs, or a collection group query and its index will mix them.
- In Datastore mode, an ancestor path is fixed at creation. Moving an entity to another parent is a new key: copy, then delete. Choose ancestors only for a parent the child never leaves.
- Depth costs nothing per level, but every level is a value every reader must hold to build the path. Keep paths to what callers know.

## Document shape

- **One document per screen** is the cheapest read. A profile page that shows a user, their last five orders and their stats reads one document when a writer keeps a `profileView` summary current.
- **Bucket small records.** Many tiny records read together (hourly readings, chat messages of one day) cost one read each. One document per bucket holding a map or array of them costs one read. Keep buckets under about 1 MiB and below the 1 write per second per document rate, so pick the bucket size from the write rate.
- **Maps for keyed sets.** `members.{uid}: true` supports `where('members.uid1', '==', true)` and per-member updates with a field path. It costs two index entries per key, ascending and descending, so exempt the map when it grows large and you do not query it.
- **Arrays for small value sets.** `array-contains` and `array-contains-any` query them. Arrays of objects match only on the whole object, so store the queried scalar in its own array (`tagIds` beside `tags`).
- **Large blobs elsewhere.** Put files in Cloud Storage and keep the path. Put long text you do not query in an exempted field.
- **Explicit defaults.** Write every field a query filters or orders on, on every document. A missing field and a `null` field are different: `null` is indexed, missing is not.

## IDs

- Use the auto-generated ID (`doc()` with no argument, or `allocateIds` in Datastore mode) when nothing natural identifies the entity. It spreads writes across the key range.
- Use a natural ID (`usernames/{username}`, `orders/{externalOrderId}`) when callers hold it. A get by ID is the cheapest read and `create()` makes it unique.
- Keep IDs spread across the key range. A sequential or timestamp ID sends every write to one tablet and caps throughput. Prefix a time-ordered ID with a hash or random shard when order matters.
- Keep IDs path-safe. `/` cannot appear in an ID, and `.` or `..` alone are invalid. IDs matching `__.*__` are reserved.

## Relationships

**One-to-many.** Children as a subcollection when reads are per parent. Duplicate the parent fields a child list shows (name, avatar) into each child, and give one writer (a trigger or the service that updates the parent) the job of fanning out changes. When the fan-out is large, accept staleness and update in the background with `BulkWriter`.

**Many-to-many.** Pick per direction:
- Small and bounded on one side (a user in at most 50 groups): an array of IDs on that side, queried with `array-contains`.
- Large on both sides: a membership collection `memberships/{groupId}_{uid}` with both IDs and the duplicated display fields of each side. The composed ID makes membership unique and lets either side check it with a get.
- Need the list from both sides with display data: two subcollections, `groups/{g}/members/{uid}` and `users/{uid}/groups/{g}`, written in one batch.

**Reference fields.** A `DocumentReference` field is a pointer, not a join. Reading it is another get. Store the fields you display beside the reference.

## Tenants

| Placement | Choose when |
|---|---|
| `tenantId` field on root collections | many small tenants, cross-tenant queries for operators |
| `tenants/{t}/...` path | rules must match the tenant from the path with no read |
| One database per tenant | tenants need separate backups, locations or deletion, and there are fewer than 100 per project |
| Datastore namespace per tenant | Datastore mode, see below |

Put `tenantId` first in every composite index a tenant query uses. It spreads timestamp writes across tenants.

## Datastore mode specifics

- A kind has no schema. Entities of one kind can carry different properties. The same field-presence rule applies: a missing property drops the entity from queries on it.
- Mark properties you never filter on with `excludeFromIndexes` in the write. Long text and blobs must be excluded or the write fails past 1,500 bytes.
- Embedded entities index their subproperties by default. Exclude the embedded entity when you never query inside it.
- Namespaces partition a database for multi-tenant data. Every query runs in one namespace. Indexes are shared across namespaces.

## Sources

- https://docs.cloud.google.com/firestore/native/docs/data-model
- https://docs.cloud.google.com/firestore/native/docs/best-practices
- https://docs.cloud.google.com/datastore/docs/concepts/entities
