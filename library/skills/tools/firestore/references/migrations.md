# Migrations, backfills, deletes and recovery

Read this when changing live data: adding a field, an index or a collection, renaming or reshaping documents, deleting a collection, or restoring.

Firestore has no schema, so every migration is code that reads and rewrites documents, and every rewrite bills a read and a write. Size it first: documents times two operations, at the price per 100,000.

## Add a field that queries depend on

A document without the field drops out of every query that filters or orders on it. Ship in this order:

1. Deploy writers that always set the field.
2. Backfill existing documents with the default.
3. Deploy the composite index if one is needed, and wait for it to finish building.
4. Deploy readers that filter or order on the field.

Readers that ship before step 2 finishes silently miss old documents.

## Rename or reshape a field

1. Writers write both the old and the new shape.
2. Backfill the new shape.
3. Readers switch to the new shape.
4. Writers stop writing the old shape. A cleanup pass deletes it with `FieldValue.delete()`.

Migrate on read when most documents are cold and a full backfill costs more than it saves. Readers accept both shapes, every write saves the new shape, and a `schemaVersion` field tells them apart. A query on the new shape still misses the cold documents, so backfill before any reader filters or orders on it.

## Move a collection

A path is a key, so a move is a copy.

1. Writers write to both paths.
2. Copy existing documents with `BulkWriter`.
3. Readers read the new path, and fall back to the old one until the copy finishes.
4. Delete the old path.

## Running a backfill

- Use `BulkWriter` in server SDKs. It batches, retries and applies the 500/50/5 ramp.
- Page through the collection by document ID (`orderBy(FieldPath.documentId())` with `startAfter`).
- Make each document's rewrite idempotent. A rerun after a crash must produce the same result.
- Skip documents already migrated with a `schemaVersion` field, so a rerun bills reads but not writes.
- Use a collection group query to reach every subcollection with one ID.
- For a collection too large for one worker, run Dataflow over a managed export, or partition with `partitionQuery` across workers.
- Read at one `readTime` when the backfill must see a snapshot.

## Indexes

- Deploy new composite indexes before the code that needs them. Builds on large collections take hours.
- Delete indexes after the code that used them is gone.
- Adding an exemption removes existing index entries in the background. It lowers storage and write cost once it completes.
- Datastore mode: `gcloud datastore indexes create index.yaml`, then `gcloud datastore indexes cleanup index.yaml` to drop indexes no longer listed.

## Delete a collection or a subtree

- Deleting a document leaves its subcollections. Use `recursiveDelete` in server SDKs, `firebase firestore:delete --recursive`, or a TTL policy for gradual cleanup.
- `gcloud firestore bulk-delete --collection-ids=...` runs a managed delete. It bills one delete per document plus one read per 1,000 index entries, and it removes only the listed collection IDs, so list the child collection IDs too.
- Every deleted document bills one delete. A large collection costs as much to delete as to write.
- Delete in the background with `BulkWriter`. A tight delete loop on sequential IDs builds a hotspot of tombstones that slows queries for a while.

## Export, import and recovery

| Tool | Use for | Cost |
|---|---|---|
| Managed export to Cloud Storage | migrations to another project, BigQuery loads, cold backups | one read per document exported |
| Managed import | seeding or restoring a database | one write per document |
| Scheduled backups | daily or weekly restore points, restored into a new database | storage |
| Point-in-time recovery | read or export the state at any minute of the last 7 days | storage |

- A restore always creates a new database. Verify it, then switch the application's database ID.
- An import writes into an existing database and overwrites every document that shares an ID.
- Reapply TTL policies and security rules to a restored database.
- Scheduled backups keep at most 14 weeks.
- BigQuery analytics: stream changes with the Firestore to BigQuery extension or Datastream, instead of scheduled queries over the live database.

## Environments

- Run tests against the emulator. It does not bill, and it enforces indexes only partially, so deploy the index file to a staging database before trusting a new query.
- Give each environment its own database or project. The free tier applies to one database per project.
- Keep `firestore.indexes.json`, `firestore.rules` or `index.yaml` in the repository and deploy them from CI with the code that needs them.

## Sources

- https://docs.cloud.google.com/firestore/native/docs/manage-data/delete-data
- https://docs.cloud.google.com/firestore/native/docs/understand-reads-writes-scale
- https://docs.cloud.google.com/firestore/native/docs/pitr
- https://docs.cloud.google.com/firestore/native/docs/backups
