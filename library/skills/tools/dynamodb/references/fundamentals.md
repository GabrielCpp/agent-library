# Fundamentals: concepts, limits, API actions, request options

Read this before designing any table, choosing an API action, or sizing a request against DynamoDB limits.

## Ch 2. Core Concepts in DynamoDB (includes Ch 1)

Key points
- DynamoDB is a key-value and wide-column store. Each partition key maps to a B-tree of items ordered by sort key.
- Know the access patterns before designing the table. The model can evolve, mostly by adding patterns.
- DynamoDB has no database-level schema. Enforce the schema in application code.
- Requests go over HTTP with IAM auth. There is no connection pool and no persistent connection.
- Scans and a single hot partition key do not scale. That is misuse, not a tool flaw.
- Pricing is provisioned (RCU/WCU) or on-demand. Start on-demand, switch to provisioned once traffic is known.
- 1 RCU is one strongly consistent read per second, or two eventually consistent reads, up to 4KB. 1 WCU is one write per second up to 1KB.
- IAM can allow or deny per action and per key or attribute. Define tables and indexes in Terraform or CloudFormation.
- A table holds items. An item holds typed attributes. Items in one table need not share attributes.
- Every item must include the full primary key. Writing an existing key overwrites the item unless the write carries a condition.
- The primary key is simple (partition key only) or composite (partition key plus sort key). Only composite keys support Query.
- Items with the same partition key form an item collection, stored together on one node.
- Prefer a global secondary index (GSI). Create a local secondary index (LSI) only with the table, and only if you need strongly consistent reads on an alternate sort key.
- GSIs are eventually consistent only. LSIs allow strongly consistent reads.
- Primary key design is the most important modeling decision.

### 2.1 Basic vocabulary
- **Method:** Put multiple entity types in one table to avoid joins. Enforce the schema in code.
- **When:** Always.
- **How:** Attribute types fall in three groups. Scalars: string, number, binary, boolean, null. Complex: list, map. Sets: string set, number set, binary set (one element type, unique elements).
- **How:** The type decides the allowed operations. Updates add or subtract numbers. Sets support membership checks and add or remove of members.
- **Pitfalls:** A write without the full primary key is rejected. A write with an existing key silently overwrites.

### 2.2 Primary keys and secondary indexes
- **Method:** Use a simple key for one-to-one lookups. Use a composite key for "fetch many" and relations.
- **How:** A composite key allows `Query` on a partition key with a sort key condition.
- **Method:** Use a GSI to add an access pattern with a different key shape.
- **How:** A GSI takes any attributes as partition and sort key. AWS copies items into the reshaped index. A GSI has its own throughput and can be added or dropped after table creation. The default limit is 20 GSIs per table.
- **Method:** Use an LSI only for strong consistency on an alternate sort key.
- **How:** An LSI shares the table partition key, differs in sort key, uses table throughput, and must exist at table creation. The limit is 5 LSIs per table.
- **Pitfalls:** GSI replication is asynchronous, so a GSI read can miss the latest write. Never read a uniqueness marker or ownership state through a GSI. A strongly consistent LSI read costs more throughput.

### 2.3 Item collections
- **Method:** Give items you read together the same partition key.
- **When:** Any multi-item access pattern.
- **How:** An item collection is all items with one partition key in the base table or in an index. A collection of one item is still a collection. Example: PK=Actor, SK=Movie puts two Tom Hanks rows in one collection.
- **Pitfalls:** All items of a collection live on one node, so a hot partition key limits throughput.

## Ch 3. Advanced Concepts

Key points
- Item max is 400KB. Query and Scan read at most 1MB per call, applied before filters.
- A single partition caps at 3000 RCU or 1000 WCU per second.
- With an LSI, an item collection (base table plus LSI items for one partition key) caps at 10GB. Writes are rejected past it. GSIs have no such cap.
- Reads are eventually consistent by default. `ConsistentRead=True` gives strong consistency on the base table and on LSIs, never on GSIs.
- Eventually consistent reads cost half the read capacity of strongly consistent reads.
- Overload generic `PK` and `SK` attribute names and prefix values by type so one table holds many entity types.

### 3.1 DynamoDB Streams
- **Method:** Enable Streams and process records to react to writes.
- **When:** Work queues, fan-out to other services, derived data, event-driven reactions.
- **How:** Each put, update or delete produces a stream record. Process with Lambda. A stream is an immutable sequence with multiple independent consumers. A TTL deletion produces a REMOVE record.
- **Pitfalls:** Consumers can see a record more than once. Make handlers idempotent.

### 3.2 Time-to-live (TTL)
- **Method:** Use TTL to expire short-lived items instead of a cleanup job.
- **When:** Sessions, temporary tokens, locks, anything with a lifespan. Mixed tables are fine.
- **How:** Name a TTL attribute on the table. Store a Unix timestamp in epoch seconds as a Number. DynamoDB deletes items whose value is in the past. Items without the attribute never expire. An ISO string attribute is ignored, so store a separate epoch copy.
- **Pitfalls:** AWS deletes expired items typically within a few days, not at the TTL time (the book says 48 hours). Do not rely on TTL for correctness. Check expiry in the application on read, or with a filter expression (see expressions.md).

### 3.3 Partitions
- **Method:** Reason about partitions to understand item collections and limits.
- **How:** The request router hashes the partition key to pick the node. Adaptive capacity moves throughput to hot items.
- **Pitfalls:** Per-partition throughput limits and the LSI collection limit still apply.

### 3.4 Consistency
- **Method:** Choose consistency per read.
- **How:** Each partition has one primary and two secondary nodes. A write commits on the primary and one secondary, then replicates to the third. An eventually consistent read can hit a lagging secondary. `ConsistentRead=True` reads the primary. The base table and LSIs let you choose. GSIs are eventual only.
- **Pitfalls:** Read the current state of a lock or counter with `ConsistentRead=True` on the base table. A stale read can show an old holder or a missing item.

### 3.5 DynamoDB limits
- **Item size:** The maximum is 400KB. Do not store unbounded related items on the parent. Split into smaller items and do targeted operations.
- **Query and Scan size:** Each call reads at most 1MB before any filter. Paginate for more.
- **Partition throughput:** 3000 RCU or 1000 WCU per second per partition, not per table. A single hot item hits this ceiling. Shard the key per resource or shard reads and writes.
- **Item collection:** With an LSI, a collection is capped at 10GB and further writes are rejected. GSI collections split across partitions automatically.
- **Transactions:** TransactWriteItems and TransactGetItems accept up to 100 items and 4MB in aggregate.

### 3.6 Overloading keys and indexes
- **Method:** Name keys generically (`PK`, `SK`, `GSI1PK`, `GSI1SK`) and encode entity type in the value with a prefix.
- **When:** Multiple entity types in one table.
- **How:** Org item: PK=`ORG#<OrgName>`, SK=`ORG#<OrgName>`. User item: PK=`ORG#<OrgName>`, SK=`USER#<UserName>`. Do the same on index keys.
- **Pitfalls:** Without prefixes, different types collide on the same key and overwrite each other. A company and a user both named "Keller Williams" are one example.

## Ch 4. The Three API Action Types

Key points
- Three categories: item-based actions (specific items), Query (one item collection), Scan (whole table).
- Item-based actions need the full primary key, run on the base table only, and are the only way to write.
- No write targets "all items with partition key Y". Query, then write each item by full key.
- Batch actions succeed or fail per item. Transaction actions succeed or fail together.
- Query requires the partition key and at most one sort key condition. Operators: `=`, `<`, `<=`, `>`, `>=`, `begins_with`, `BETWEEN`. There is no `contains` or `ends_with`.
- Query and Scan return at most 1MB per call. Page with `LastEvaluatedKey`.

### 4.1 Item-based actions
- **Method:** Use GetItem, PutItem, UpdateItem, DeleteItem for single-item work.
- **When:** You know the full primary key.
- **How:** PutItem overwrites a same-key item. UpdateItem edits attributes and creates the item if missing, so an acquire can be one conditional UpdateItem instead of read then write. BatchGetItem and BatchWriteItem save round trips. TransactWriteItems and TransactGetItems are atomic.
- **Pitfalls:** Every write is item-based and on the base table, never on an index. Batch writes are not atomic. Use a transaction when two writes must succeed together.

### 4.2 Query
- **Method:** Use Query to read an item collection on a table or index.
- **When:** One-to-many, many-to-many, "all X for Y".
- **How:** `KeyConditionExpression='#actor = :actor'`. Add `AND #movie BETWEEN :a AND :m` for a sort key condition. Add `IndexName='MoviesIndex'` to query a GSI, for example PK=Movie, SK=Actor to flip the pattern.
- **Pitfalls:** The partition key is mandatory. Key conditions work only on primary key attributes.

### 4.3 Scan
- **Method:** Avoid Scan in latency-sensitive paths.
- **When:** Very small tables, full export to another system, or an intentionally designed sparse index.
- **How:** Scan returns pages of up to 1MB plus a pagination key. Call again with it.

### 4.4 How DynamoDB enforces efficiency
- **Method:** Design access so each call is an O(1) partition lookup, an O(log n) sort key seek, then a sequential read of at most 1MB.
- **How:** The partition key hash picks the node. The sort key seek is a B-tree search inside one collection. Collections are ordered, so only contiguous ranges are readable.
- **Pitfalls:** Anything beyond 1MB needs explicit serial paging, which makes unscalable patterns visible.

## Ch 5. Using the DynamoDB API

Key points
- Always use `ExpressionAttributeNames` (`#name`) and `ExpressionAttributeValues` (`:value`). Names are required for reserved words (for example Name, Count, Month, Timestamp, Bucket, By) and for names containing a period.
- Values are typed (`{"S": ...}`, `{"N": "1"}`). The string "1565954664" does not equal the number 1565954664.
- Use the bare SDK or a thin helper (Document Client, Boto3 Table resource, DynamoDB Toolbox). Do not use an ORM or ODM.
- `ConsistentRead`, `ScanIndexForward`, `ReturnValues`, `ReturnConsumedCapacity` and `ReturnItemCollectionMetrics` change what a call returns.
- Model first in a spreadsheet or NoSQL Workbench, then write the calls.

### 5.1 Expression names and values
- **Method:** Use placeholders for every attribute name and value.
- **When:** Every expression in production code.
- **How:** `KeyConditionExpression='#actor = :actor AND #movie BETWEEN :a AND :m'` with `ExpressionAttributeNames={'#actor':'Actor','#movie':'Movie'}` and `ExpressionAttributeValues={':actor':{'S':'Tom Hanks'},':a':{'S':'A'},':m':{'S':'M'}}`.
- **Pitfalls:** A dot in an unaliased name reads as nested access. An unaliased reserved word fails the request.

### 5.2 Don't use an ORM
- **Method:** Use the plain SDK plus type-inference wrappers.
- **How:** Document Client and the Boto3 Table resource infer types (`'Actor': 'Tom Hanks'` instead of `{'S': ...}`). DynamoDB Toolbox maps entities and is not an ORM.
- **Pitfalls:** ODMs push single-entity-per-table thinking. Helper libraries do not model data for you.

### 5.3.1 ConsistentRead
- **Method:** Set `ConsistentRead=True` when the read must reflect all prior writes.
- **When:** Read-after-write, reading a lock or counter.
- **How:** Valid on GetItem, BatchGetItem, Query and Scan. Allowed on LSIs, not GSIs.
- **Pitfalls:** A strongly consistent read of up to 4KB costs 1 RCU. An eventually consistent read costs 0.5.

### 5.3.2 ScanIndexForward
- **Method:** Set `ScanIndexForward=False` on Query to read newest first.
- **When:** "Most recent N", reverse alphabetical, parent-first layouts.
- **How:** PK=`SensorId`, SK=`Timestamp`, `ScanIndexForward=False`, `Limit=20`. Without it, 1440 daily readings must be paged to reach the last 20.
- **Pitfalls:** Query only.

### 5.3.3 ReturnValues
- **Method:** Set `ReturnValues` to receive item state from a write without an extra read.
- **When:** Counter after increment, the old item on delete, the conflicting item on a failed condition.
- **How:** Values are `NONE` (default), `ALL_OLD`, `UPDATED_OLD`, `ALL_NEW`, `UPDATED_NEW`. Available on PutItem, UpdateItem, DeleteItem. Transactions use `ReturnValuesOnConditionCheckFailure`, which returns the item that failed its condition.

### 5.3.4 ReturnConsumedCapacity
- **Method:** Request `INDEXES` (per table and index) or `TOTAL` to measure capacity.
- **When:** Prototyping and load testing a design, or billing customers per usage.
- **How:** The response carries `ConsumedCapacity` with `CapacityUnits`, `ReadCapacityUnits`, `WriteCapacityUnits` and a `GlobalSecondaryIndexes` map.
- **Pitfalls:** Cost depends on item size, consistency mode and transactional requests.

### 5.3.5 ReturnItemCollectionMetrics
- **Method:** Request it on writes to watch collection size when the table has an LSI.
- **How:** The response has `ItemCollectionMetrics.ItemCollectionKey` and `SizeEstimateRangeGB`. Alert at about 7 to 8GB.
- **Pitfalls:** Without an LSI there is no collection limit and the metrics do not matter.
