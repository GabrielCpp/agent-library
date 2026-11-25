# One-to-many and many-to-many strategies

Read this when an access pattern joins two entity types and you must choose how to store the relationship.

## Ch 11. Strategies for one-to-many relationships (includes Ch 10)

Key points
- Relational modeling has one correct answer per problem. DynamoDB modeling has several strategies and needs judgment.
- Apply a strategy per access pattern. One table commonly combines several.
- The core problem: fetch parent information when retrieving related entities, without joins.
- Five strategies: complex attribute, duplicated data, composite primary key plus Query (most common), secondary index plus Query, composite sort key.
- A complex attribute needs a bounded size and no access by its values. The item limit is 400KB.
- Duplicate data only when it is immutable, or rarely changes and few copies exist.
- Put parent and children in one item collection. `PK = ORG#<OrgName>` returns both. Add `begins_with(SK, "USER#")` for children only.
- Use a GSI when the base table keys are reserved for another purpose such as uniqueness, or when the hierarchy has many levels. Keep the uniqueness item on the base key and serve reads from the GSI.
- Direct-lookup keys such as PK=SK=`TICKET#<TicketId>` support GetItem by exact id.
- Use `ScanIndexForward=False` to read newest first. Put the parent item last in the collection when children sort by timestamp.
- Never put unbounded growth into one item. The 400KB limit is a hard failure.

### 11.1 Denormalization by using a complex attribute
- **Method:** Store the children as a list or map attribute on the parent item.
- **When:** No access pattern queries by the nested values, and the nested count is bounded.
- **How:** A Customer item holds a MailingAddresses map, capped at 20 by the application. This violates first normal form on purpose.
- **Pitfalls:** A complex attribute cannot be part of a primary key or index. Unbounded data breaks the 400KB limit. Keep Order Items separate from Orders because items per order are unbounded.

### 11.2 Denormalization by duplicating data
- **Method:** Copy parent data onto each child item.
- **When:** The copied data is immutable, or changes rarely and few items hold copies.
- **How:** Book items carry the Author's name and birth year, so a read needs one item.
- **Pitfalls:** Ask whether the data is immutable, how often it changes and how many items contain it. Thousands of copies make updates costly and risk inconsistency.

### 11.3 Composite primary key plus the Query API action
- **Method:** Share the partition key between parent and children and Query the item collection.
- **When:** Most one-to-many cases, especially with several access patterns on parent and children.
- **How:**
  - Organization: PK=`ORG#<OrgName>`, SK=`METADATA#<OrgName>`.
  - User: PK=`ORG#<OrgName>`, SK=`USER#<UserName>`.
  - Get Organization: GetItem with PK and SK.
  - Organization plus all Users: Query `PK = ORG#<OrgName>`.
  - Users only: Query `PK = ORG#<OrgName> AND begins_with(SK, "USER#")`.
  - One User: GetItem PK=`ORG#<OrgName>`, SK=`USER#<Username>`.
- **Pitfalls:** A large third type (Tickets) in the same collection bloats the Organization-plus-Users query and forces pagination.

### 11.4 Secondary index plus the Query API action
- **Method:** Build the item collection in a GSI instead of the base table.
- **When:** Base keys are reserved for another purpose, or the hierarchy has several levels.
- **How:**
  - Ticket: PK=SK=`TICKET#<TicketId>`, its own collection. TicketId is a timestamp plus random hash suffix.
  - User and Ticket both get GSI1PK=`ORG#<OrgName>#USER#<UserName>`.
  - User GSI1SK=`USER#<UserName>`. Ticket GSI1SK=`TICKET#<TicketId>`.
  - Query GSI1 with `ScanIndexForward=False` to get the User last and the newest Tickets first.
- **Pitfalls:** GSI reads are eventually consistent and GSIs cost extra writes. Sort order decides which items come back first.

### 11.5 Composite sort keys with hierarchical data
- **Method:** Concatenate hierarchy levels into the sort key and query with `begins_with`.
- **When:** More than two levels, patterns at every level, and each level returns all descendants.
- **How:** PK=`<Country>`, SK=`<State>#<City>#<ZipCode>`. Country: `PK = <Country>`. State: `begins_with(SK, '<State>#')`. City: `begins_with(SK, '<State>#<City>')`. Zip: `begins_with(SK, '<State>#<City>#<ZipCode>')`.
- **Pitfalls:** A poor fit when a level should exclude deeper items, such as Users without Tickets. The query returns extraneous items.

## Ch 12. Strategies for many-to-many relationships

Key points
- Many-to-many is the hardest relationship because both sides must be queryable.
- Four strategies: shallow duplication, adjacency list, materialized graph, normalization plus multiple requests.
- Shallow duplication needs a bounded count (400KB limit) and immutable copied values. It handles one side only.
- An adjacency list stores top-level entity items plus relationship items. Invert the key with a GSI (PK and SK swapped) to read the other side.
- Keep mutable data on entity items and immutable relationship data on edge items, so updates touch few items.
- An edge item has a natural unique key per pair. A conditional put on that key prevents a duplicate link.
- When relationship data is highly mutable and heavily duplicated, use normalization and multiple requests (Query, then BatchGetItem).
- Do not fan out writes to thousands or millions of copies.
- Treat copied values as hints. A shopping cart copies the price at add time and revalidates against the authoritative item at checkout.

### 12.1 Shallow duplication
- **Method:** Copy a small, immutable subset of the related entity into a list attribute on the other.
- **When:** A parent view needs minimal child info (name or id), the count is bounded, and the values do not change.
- **How:** A Class item has a Students list of student names. One GetItem returns the class and its students.
- **Pitfalls:** Only one side is solved. Handle the other side with a one-to-many strategy. Mutable data such as GPA makes updates expensive and risks inconsistency.

### 12.2 Adjacency list
- **Method:** Store entities and the relationship as separate items, then read the other side through an inverted index.
- **When:** Relationship data is immutable or rarely changes.
- **How:**
  - Movie: PK=SK=`MOVIE#<MovieName>`.
  - Actor: PK=SK=`ACTOR#<ActorName>`.
  - Role: PK=`MOVIE#<MovieName>`, SK=`ACTOR#<ActorName>`.
  - Query `PK = MOVIE#<MovieName>` returns the Movie plus its Roles.
  - A GSI with partition key SK and sort key PK returns the Actor plus Roles.
  - Prefer `GSI1PK` and `GSI1SK` carrying flipped values on just these items if other entities should not be flipped.
- **Pitfalls:** Works best when the relationship data is immutable.

### 12.3 Materialized graph
- **Method:** Break each node into multiple items in the base table, then regroup them by relationship with a secondary index.
- **When:** Highly connected data with many relationship types.
- **How:** Split a Person node into items per facet (marriage date, job). A GSI groups edges, for example one partition per date or `JOB|Attorney`. Items carry the node id, so a query on the base table rebuilds the parent.
- **Pitfalls:** Niche.

### 12.4 Normalization and multiple requests
- **Method:** Store sparse relationship items and fetch authoritative data in a second request.
- **When:** Relationship data is highly mutable and duplicated widely, such as social follows with thousands or millions of followers.
- **How:**
  - User: PK=SK=`USER#<Username>`.
  - Following: PK=`USER#<Username>`, SK=`FOLLOWING#<Username>`.
  - Step 1: Query the user's collection for the User and Following items.
  - Step 2: BatchGetItem the followed User items for display name and profile.
- **Pitfalls:** Two requests are unavoidable. Updating all copies would cause heavy write traffic.
