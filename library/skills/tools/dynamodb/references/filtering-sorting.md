# Filtering and sorting strategies

Read this when an access pattern needs to narrow results or return them in a specific order.

## Ch 13. Strategies for filtering

Key points
- Filtering is almost exclusively about primary keys, on the base table and on every secondary index.
- Every API except Scan requires the partition key, so put items read together under one partition key.
- A partition key lookup is O(1) and narrows the data to one node of at most 10GB.
- A filter expression runs after the read. You pay for filtered-out items, and the 1MB limit applies before the filter.
- Do not rely on a filter expression to rescue a bad model.
- A sparse index omits items that lack the index key attributes. Use it as a deliberate filter.
- A composite sort key (`<ENUM>#<HIGH_CARDINALITY>`) filters on two attributes in one Query.
- TTL deletion lags expiry, typically by up to a few days. Add a filter expression that drops items whose TTL is already past.

### 13.1 Filtering with the partition key
- **Method:** Use the partition key as the first and coarsest filter.
- **When:** Always.
- **How:** With PK=Actor, one Query returns one actor's movies. A GSI with PK=Movie returns all actors in a movie.
- **Pitfalls:** Scan is the only operation without a partition key, and it is costly.

### 13.2.1 Filtering with the sort key: simple filters
- **Method:** Put a meaningful value (date, score) in the sort key and use a range condition.
- **When:** A clear item collection grouped by a parent entity.
- **How:** PK=`CustomerId`, SK=`OrderTime` (ISO string). `KeyConditionExpression="#c = :c AND #ot BETWEEN :start AND :end"`.
- **Pitfalls:** Needs a composite primary key.

### 13.2.2 Assembling different collections of items
- **Method:** Place the parent item at a chosen point in the sort order and use `<=` or `>=` on the sort key to pick one side.
- **When:** A parent plus one of several child types share a partition, such as a Repo with Issues and Stars, to save secondary indexes.
- **How:** PK=`REPO#<owner>#<repo>`. Issues SK=`ISSUE#<n>`, Repo SK=`REPO#<owner>#<repo>`, Stars SK=`STAR#<user>`. Repo plus Issues: `#pk = :pk AND #sk <= :sk` with `:sk` equal to the Repo SK and `ScanIndexForward=False`, which reads backward from the Repo item. Repo plus Stars: `#sk >= :sk`, read forward.
- **Pitfalls:** The sort key encodes your arrangement and has no inherent meaning.

### 13.3 Composite sort key
- **Method:** Combine two attributes into one sort key value, enum first.
- **When:** A pattern always filters on two or more attributes and one is enum-like.
- **How:** Attribute `OrderStatusDate` = `<STATUS>#<ISO date>`. GSI PK=`CustomerId`, SK=`OrderStatusDate`. Query `#osd BETWEEN :start AND :end` with `CANCELLED#2019-07-01T00:00:00.000000` and `CANCELLED#2019-10-01T00:00:00.000000`.
- **Pitfalls:** Order matters. `<Date>#<Status>` is useless because the high-cardinality date interleaves statuses.

### 13.4.1 Sparse index: global filter on an item type
- **Method:** Set the GSI key attributes only on items that should appear in the index.
- **When:** A rare condition within an entity type, such as admins in an organization.
- **How:** Org and User items get GSI1PK=`ORG#<OrgName>`. Write GSI1SK=`Admin` only on admin Users. Non-admins lack GSI1SK and stay out of the index. The index can stay overloaded for other entities.
- **Pitfalls:** Removing the attribute removes the item from the index. Reading all users and filtering wastes read capacity.

### 13.4.2 Sparse index: project a single entity type
- **Method:** Give only one entity type a dedicated index key attribute.
- **When:** You must enumerate all items of one type, such as all Customers for a marketing email.
- **How:** Add `CustomerIndexId` to Customer items. Create index `CustomerIndex` with that attribute as PK. Scan the index.
- **Pitfalls:** It does not work with an overloaded index. Use a dedicated index.

### 13.5 Filter expressions
- **Method:** Use filter expressions only as a minor optimization on an already good model.
- **When:** Reducing response payload, easier app-side filtering, guarding TTL expiry.
- **How:** Accept a filter if the hit rate is at least 30 to 40 percent, or the pre-filter result is small (under 1MB, likely under about 100KB). Exclude TTL-expired items with `#ttl > :now`.
- **Pitfalls:** You pay for filtered-out reads. Returning exactly N items is hard because `Limit` applies before the filter. A composite sort key lets `Limit=10` return exactly 10.

### 13.6 Client-side filtering
- **Method:** Fetch a small dataset and filter or sort in the client.
- **When:** Filtering is hard to model (calendar gap finding) or the data is under 1MB (table views with many column filters).
- **How:** Narrow to one customer or parent first, then ship everything to the client.
- **Pitfalls:** Fails for large catalogs.

## Ch 14. Strategies for sorting

Key points
- Sorting needs a composite primary key and happens only on the sort key within one item collection.
- Sort keys are number, string or binary. Strings and binary sort by UTF-8 bytes.
- Uppercase sorts before lowercase and symbols count. Normalize sort key text to one case.
- Use sortable timestamps (epoch or ISO-8601), never display formats.
- Primary key attributes cannot be updated. Put a changing sort value in a GSI sort key.
- Place the parent item in the sort order according to the direction you will read children.
- Zero-pad numbers inside string sort keys.

### 14.1.1 Lexicographical sorting
- **Method:** Standardize sort key text to all upper or all lower case.
- **When:** Names or free text in the sort key.
- **How:** Store `DEAN`, `DEBRIE`, `DERN`. Keep the properly cased value in another attribute.
- **Pitfalls:** Unnormalized, `DeBrie` sorts before `Dean`. Characters like `#` and `$` take part in ordering.

### 14.1.2 Sorting with timestamps
- **Method:** Use epoch numbers or ISO-8601 strings such as `2020-03-06T15:14:15`.
- **How:** Prefer ISO for readability in the console.
- **Pitfalls:** "May 26, 1988" does not sort.

### 14.1.3 Unique, sortable IDs
- **Method:** Use KSUIDs (K-Sortable Unique IDs).
- **When:** You need URL-friendly unique ids that also sort chronologically, such as request ids, idempotency keys, lock tokens.
- **How:** A KSUID is a 27-character string with a timestamp prefix plus a random payload, for example `1YnlHOfSSk3DhX4BR6lMAceAo1V`. It is more unique than UUIDv4. Segment's CLI shows it with `ksuid -f inspect`.
- **Pitfalls:** Ordering is rough at the timestamp resolution.

### 14.2 Sorting on changing attributes
- **Method:** Keep the base table key immutable and put the changing value in a GSI sort key.
- **When:** Most recently updated, leaderboards.
- **How:** Base table PK=`OrgName`, SK=`TicketId`. GSI PK=`OrgName`, SK=`UpdatedAt`. Query the GSI.
- **Pitfalls:** A key containing `UpdatedAt` forces delete plus create on every update, with data-loss risk. A GSI does that replication for you.

### 14.3 Ascending vs. descending
- **Method:** Set the read direction with `ScanIndexForward` (default true). Set false for newest first. Position the parent item to suit.
- **When:** A parent plus the most recent N children in one collection.
- **How:** Device SK=`DEVICE#<id>`, Readings SK=`READING#<ts>`. `DEVICE` sorts before `READING`, so a forward read returns the oldest readings. Prefix readings with `#` so they sort ahead of the Device, then read with `ScanIndexForward=False` and `Limit`.
- **Pitfalls:** The wrong parent position means paginating through old items.

### 14.4 Two relational access patterns in a single item collection
- **Method:** Put the parent between two child types and read one direction for each.
- **When:** An Org with Users and Teams, to save a secondary index.
- **How:** PK=`ORG#<OrgName>`. Teams SK=`#TEAM#<TeamName>`, Org SK=`ORG#<OrgName>`, Users SK=`USER#<UserName>`. Org plus Teams: `#sk <= :sk` with `:sk`=`ORG#MCDONALDS` and `ScanIndexForward=False`. Org plus Users: `#sk >= :sk`, forward.
- **Pitfalls:** One side's order is fixed by the other. Use it when order does not matter for one side or the directions differ.

### 14.5 Zero-padding with numbers
- **Method:** Left-pad numbers with `0` to a fixed width in string sort keys.
- **When:** A sort key like `<ItemType>#<Number>`.
- **How:** `10` becomes `00010`, `2` becomes `00002`. Width 5 allows up to 99999. Pick the maximum you can imagine plus 2 or 3 digits.
- **Pitfalls:** Unpadded, `10` sorts before `2`. Alert when a count reaches about 30 percent of the maximum.

### 14.6 Faking ascending order
- **Method:** Store a zero-padded difference (max minus value) so a forward read yields descending order.
- **When:** A parent has two one-to-many relations that both need newest-first reads in the same collection.
- **How:** Width 5, max 99999, id 157 becomes `99842`. The Device item sits at the top, and a forward read returns the latest readings.
- **Pitfalls:** Exotic. Pick a maximum you cannot exceed.
