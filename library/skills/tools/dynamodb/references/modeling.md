# Modeling process, single-table design, implementation hygiene

Read this when starting a new table or entity, deciding between one table and several, or writing the data access layer.

## Ch 7. How to approach data modeling in DynamoDB

Key points
- Do not model DynamoDB like a relational database. The result is worse than using the relational database.
- There are no joins. Preassemble data in the shape a read needs. Do not fake joins with serial requests in application code.
- Denormalize. Storage is cheap. Integrity of duplicated data becomes an application concern.
- Put multiple entity types in one table. Use generic key names `PK` and `SK`, and `GSI1PK` and `GSI1SK` on indexes.
- Filtering is built into key design. Primary keys and secondary indexes decide how you retrieve data. There is no arbitrary WHERE.
- Access patterns drive the model. List all of them before designing keys.
- Process: understand the app, draw an ERD, list access patterns, design the primary key, then add secondary indexes and streams for what remains.
- Solve as much as possible with the primary key. It costs no extra throughput and is strongly consistent, unlike a GSI.
- Satisfy uniqueness first, then fetch-many patterns.
- The client must know the full primary key at read and update time. Build keys from values the caller already holds.

### 7.1 Differences with relational databases
- **Method:** Replace joins, normalization, per-entity tables and ad hoc filtering with pre-joined, denormalized, single-table, key-driven access.
- **When:** Any time a relational habit appears in a DynamoDB design.
- **How:** Joins do not exist. Pre-join by storing related items under one partition key. Do not fetch a record, then query its related records in a second call.
- **How:** Normalization existed to save storage and keep data consistent. Only consistency still applies. Decide where and when duplicated data is updated and how the copies are found.
- **How:** Multiple entity types per table are required to fetch a Customer and its Orders in one request. Name key attributes `PK` and `SK` because their meaning varies by entity. Hide this in the data access layer.
- **How:** There is no WHERE clause. Requests are precise key lookups, which keeps latency under 10 ms at 1GB or 1TB.
- **Pitfalls:** Console browsing and analytics export are harder with mixed entity types. The database does not enforce integrity of copies.

### 7.2 Steps for modeling
- **Method:** Follow five steps in order: understand the app, ERD, access patterns, primary key, secondary indexes and streams.
- **When:** Every new table or new entity.
- **Pitfalls:** You cannot model generically for future flexibility. Skipping steps leads to a stuck data model. Expect several iterations.

### 7.2.1 Create an entity-relationship diagram
- **Method:** Draw entities (nouns) with attributes and the relationships between them, for example one-to-many.
- **When:** Always. Large models still fit one table: the GitHub example has 8 entities and 14 relationships.
- **How:** Boxes for entities, lines for relationships. Keep the diagram as an artifact for new engineers.

### 7.2.2 Define your access patterns
- **Method:** List every access pattern before designing keys.
- **When:** After the ERD.
- **How:** API-centric: list each endpoint and its response shape. UI-centric: list each screen and the data it needs. Track them in a chart with columns Entity, Access Pattern, Index, Parameters, Notes. Fill the API call, index and parameters as you design. Ask product managers and stakeholders for every need.
- **Pitfalls:** The most common failure is missing patterns up front and getting stuck once the model has solidified.

### 7.2.3 Model your primary key structure
- **Method:** Build an entity chart, choose a simple or composite key, then design a key template per entity.
- **When:** After the access patterns are listed.
- **How:** The entity chart has columns Entity, PK, SK. Start from the ERD entities. Remove entities stored as list or map attributes. Add item types for many-to-many relationships and for uniqueness.
- **How:** Use a composite key if any pattern fetches multiple entities (all Orders for a User) or multiple entity types (a Sensor and its recent SensorReadings).
- **How:** Prefix keys by entity type. Customer: PK=`CUSTOMER#<CustomerId>`, SK=`METADATA#<CustomerId>`. CustomerOrder: PK=`ORDER#<OrderId>`, SK=`METADATA#<OrderId>`.
- **How:** Use values the client knows at read time. A username in a `/users/alexdebrie` URL is safe.
- **Pitfalls:** Do not put `CreatedAt` in the primary key to get uniqueness when the timestamp is unavailable at read or update time. Add an item type solely to enforce uniqueness when needed.

### 7.2.4 Handle additional access patterns with secondary indexes and streams
- **Method:** Use overloaded GSIs for patterns the primary key cannot serve.
- **When:** After the primary key design.
- **How:** Name keys `GSI1PK` and `GSI1SK`. Serve several access patterns from one index.
- **Pitfalls:** One index per read pattern costs more. GSIs add cost and eventual consistency.

## Ch 8. The What, Why, and When of Single-Table Design

Key points
- Use as few tables as possible, ideally one per application or microservice.
- The reason is one request for heterogeneous items. An item collection is the pre-join mechanism.
- Multiple tables force serial, waterfall requests. Network I/O dominates latency and the cost grows with scale.
- Side benefits are marginal: fewer alarms and metrics, and shared provisioned capacity. On-demand pricing gives no savings.
- Downsides: a steep learning curve, new access patterns that may need an ETL over every item, and hard analytics.
- Exceptions: new apps that value agility over latency (multiple tables, roughly 100 ms acceptable) and GraphQL.

### 8.1 What is single-table design
- **Method:** Pre-join related entities into one item collection so one Query returns them.
- **When:** Any pattern that reads a parent plus related items, or several entity types together.
- **How:** Actors table: PK=actor name, SK=movie name, so Tom Hanks has Cast Away and Toy Story in one collection. Put Order items in the User item's collection, and one Query returns the User and Orders.
- **Pitfalls:** Multi-table designs built on relational thinking cause waterfall requests that slow as the app scales.

### 8.2 Downsides of a single-table design
- **Method:** Accept and plan for three costs: learning curve, inflexible new patterns, analytics difficulty.
- **How:** The table is tailored to known patterns. A change may need an ETL that scans every item to add attributes (see migrations.md). DynamoDB is for OLTP, so export to Redshift or S3 plus Athena and re-normalize. Plan the pipeline early.
- **Pitfalls:** An overloaded table is hard to read and export. Evolving patterns mean item rewrites.

### 8.3 When not to use single-table design
- **Method:** Use multiple tables only when query flexibility and analytics matter more than latency.
- **When:** Greenfield apps where agility beats performance, and GraphQL backends.
- **How:** Faux-SQL normalizes across tables and accepts serial calls, such as GetItem User then Query Orders. It suits workloads where 100 ms is acceptable instead of under 30 ms. GraphQL resolvers fetch each type independently, so single-table gives no benefit. One table per entity is fine.
- **Pitfalls:** Still follow denormalization and NoSQL principles.

## Ch 9. From modeling to implementation

Key points
- Keep indexing attributes (`PK`, `SK`, `GSI1PK`, `GSI1SK`) separate from application attributes. Never drop an application attribute because a key encodes it.
- Confine all DynamoDB code to a data module at the application boundary. The core uses plain application objects.
- Give every GSI its own generic attributes `GSI<N>PK` and `GSI<N>SK`. Do not reuse `SK` as a GSI sort key.
- Write a Type attribute on every item.
- Write a small CLI script per access pattern to debug.
- Shorten attribute names only for the largest tables.
- Most of the work happens in planning before code.

### 9.1 Separate application attributes from indexing attributes
- **Method:** Store both the indexing attributes and the application attributes they derive from.
- **When:** Every item write.
- **How:** PK=`USER#alexdebrie`, SK=`USER#alexdebrie`, GSI1PK=`ORG#facebook`, GSI1SK=`USER#alexdebrie`, plus Username, FirstName, LastName, OrganizationName. Conditions and later migrations need the real attribute as data.
- **Pitfalls:** Removing Username because it is in PK adds complexity and risks data loss if keys change. The cost is slightly larger items.

### 9.2 Implement the data model at the boundary of the application
- **Method:** Wrap all DynamoDB calls in a data module that returns application objects.
- **When:** Always.
- **How:** `get_user(username)` builds Key `{'PK': {'S': f'USER#{username}'}}`, calls GetItem, then maps `resp['Item']['Username']['S']` and the rest into a User object. The module alone owns type descriptors, key templates and indexing attributes. Callers never see `PK` or `SK`.
- **Pitfalls:** Leaking DynamoDB shapes into business logic forces nested property access and type conversion everywhere.

### 9.3 Don't reuse attributes across indexes
- **Method:** Give each GSI dedicated `GSI<N>PK` and `GSI<N>SK` attributes.
- **When:** Even when `GSI1SK` equals `SK`.
- **Pitfalls:** Reuse saves storage but makes multi-entity modeling and later migrations harder.

### 9.4 Add a Type attribute to every item
- **Method:** Write `'Type': {'S': 'User'}` on every item in the data layer.
- **How:** It orients you in the console, drives filter expressions in ETL scans during migrations, and lets you re-normalize entities into separate tables after export.

### 9.5 Write scripts to debug access patterns
- **Method:** Write one CLI script per access pattern that takes its parameters and prints results through the data module.
- **How:** `scripts/get_user.py --username alexdebrie` calls `data.get_user`. It helps most for GSI queries with sort key conditions.
- **Pitfalls:** The console is poor for single-table items, indexed attributes and shortened names.

### 9.6 Shorten attribute names to save storage
- **Method:** Abbreviate stored names (Username to `u`, FirstName to `fn`) and rehydrate on read.
- **When:** Only for tables with billions to trillions of items.
- **Pitfalls:** The gain is marginal for normal apps and it hurts debugging. Keep the mapping inside the data module.
