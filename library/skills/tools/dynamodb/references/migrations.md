# Migrations: strategies and the GitHub worked example

Read this before adding an attribute, entity or index to a live table, or writing a backfill job.

## Ch 15. Strategies for Migrations

Key points
- First ask whether the change is purely additive or must edit existing items.
- Only indexing attributes force a migration. Application attributes never do.
- Handle new application attributes lazily in the read mapper with defaults.
- A new entity in a new or unused item collection is additive.
- A new relational pattern with no free collection needs a new or existing GSI plus a backfill job.
- A backfill is a Scan, a filter on type, then an UpdateItem per item that SETs the new key attributes.
- Use UpdateItem with SET, not Put, so concurrent writers are not overwritten. Add `attribute_exists(PK)` if items may be deleted mid-scan.
- Speed up the backfill with Scan `TotalSegments` and `Segment`.

### 15.1 Adding new attributes to an existing entity
- **Method:** Add the attribute in application code and default it on read.
- **When:** A new application attribute such as Birthdate.
- **How:** `item.get('Birthdate', {}).get('S')` when mapping the item to a domain object. It works for denormalized relationships stored as attributes.
- **Pitfalls:** Keep DynamoDB access at the application boundary so the default lives in one place.

### 15.2 Adding a new entity type without relations
- **Method:** Write the new items into a new item collection.
- **When:** No access pattern needs the parent fetched together with the new type.
- **How:** Give Projects under an Organization a new shared PK, for example `ORG#<Org>#PROJECTS`, distinct from the existing collection. No existing item changes.

### 15.3 Adding a new entity type into an existing item collection
- **Method:** Model the new item to share the parent's existing partition key.
- **When:** A relational pattern is needed and the parent's collection is unused.
- **How:** Likes: PK=`POST#<PostId>`, SK=`LIKE#<Username>`. Post items already live at PK=`POST#<PostId>`.
- **Pitfalls:** Works only if the collection is not already serving another relationship.

### 15.4 Adding a new entity type into a new item collection
- **Method:** Create a GSI collection, backfill the parent's GSI keys, write children with those keys.
- **When:** The parent collection is taken, such as Post plus Comments.
- **How:** Post gets GSI1PK=GSI1SK=`POST#<PostId>`. Comment: PK=SK=`COMMENT#<CommentId>`, GSI1PK=`POST#<PostId>`, GSI1SK=`COMMENT#<Timestamp>`. Backfill by looping Scan with `FilterExpression="#type = :type"`, then per item `UpdateExpression="SET #gsi1pk = :gsi1pk, #gsi1sk = :gsi1sk"`:
```
kwargs = {}
while True:
    results = client.scan(TableName=TABLE, FilterExpression="#type = :type",
                          ExpressionAttributeNames={"#type": "Type"},
                          ExpressionAttributeValues={":type": {"S": "Post"}}, **kwargs)
    for item in results["Items"]:
        client.update_item(...)
    last_key = results.get("LastEvaluatedKey")
    if not last_key:
        break
    kwargs["ExclusiveStartKey"] = last_key
```
- **Pitfalls:** This is the hard part of a migration. Test thoroughly and monitor. Add parallel scans, error handling and BatchWriteItem for production.

### 15.5 Joining existing items into a new item collection
- **Method:** Design a new collection in a new or existing GSI and backfill key attributes.
- **When:** A new filter, sort or join on existing types.
- **How:** Run the same Scan plus UpdateItem job as 15.4.
- **Pitfalls:** Parameterize which items and which attributes.

### 15.6 Using parallel scans
- **Method:** Pass `TotalSegments` and `Segment` to Scan.
- **When:** Speeding up an ETL scan.
- **How:** `"TotalSegments": 10, "Segment": 0` for worker 0 of 10. Workers 1 to 9 take the other segments. DynamoDB manages the state. Wrap values in type descriptors: `":type": {"S": "Post"}`.

## Ch 22. Handling Migrations in the GitHub example

Key points
- Rank migrations by difficulty: new attribute, new unrelated entity, new entity in an existing collection, new entity in a new collection, migrate an existing pattern.
- Optional attributes and new entities that reuse existing collections need no backfill. Add them lazily from application code.
- Adding GSI keys to existing items needs a one-time Scan plus UpdateItem ETL.
- A many-to-many relation uses an adjacency-list item that sits in both parents' collections (base table and a GSI).
- Replace a filter expression with a key: composite sort key `ISSUE#<Status>#<Number>`, using `99999999 - number` for descending order in an ascending scan.
- The alternative to the odd key math is one extra GSI per pattern, which costs more.
- Do the easy changes first and run ETL only for the hard ones. A new index needs its backfill before the new query path ships.

### Access patterns added
| Access pattern | Index | Key condition / key shapes |
|---|---|---|
| Add Code of Conduct | Main | `CodeOfConduct` map on Repo item (name, url), no keys |
| Create Gist, View Gists for User | Main | Gist PK `ACCOUNT#<Username>`, SK `#GIST#<KSUID>`; Query PK descending returns User plus latest Gists |
| Account plus GitHub Apps | GSI1 | App PK=SK `APP#<AccountName>#<AppName>`, GSI1PK `ACCOUNT#<AccountName>`, GSI1SK `APP#<AppName>`; User/Org gain GSI1PK=GSI1SK `ACCOUNT#<AccountName>` |
| App plus its installations | Main | AppInstallation PK `APP#<AccountName>#<AppName>`, SK `REPO#<RepoOwner>#<RepoName>` |
| Repo plus installed apps | GSI1 | AppInstallation GSI1PK `REPO#<RepoOwner>#<RepoName>`, GSI1SK `REPOAPP#<AppOwner>#<AppName>`; Repo GSI1PK `REPO#<RepoOwner>#<RepoName>` |
| Repo plus open/closed Issues | GSI4 | Repo GSI4PK `REPO#<RepoOwner>#<RepoName>`, GSI4SK `#REPO#<RepoOwner>#<RepoName>`; Issue GSI4PK `REPO#<RepoOwner>#<RepoName>`, Closed GSI4SK `#ISSUE#CLOSED#<IssueNumber>`, Open GSI4SK `ISSUE#OPEN#<IssueNumberDifference>` |
| Repo plus open/closed PRs | GSI5 | Same shape with `#PR#CLOSED#<PRNumber>` and `PR#OPEN#<PRNumberDifference>` |

IssueNumberDifference is 99999999 minus the issue number, zero padded to 8 digits. Open issue 15 gives `ISSUE#OPEN#99999984`. Closed issue 15 gives `ISSUE#CLOSED#00000015`. The Issue and Repo items must carry the same GSI4PK value.

### Lazy attribute addition (one-to-one)
- **Method:** Add a new optional attribute only when the feature is used.
- **When:** Code of Conduct on Repo, not indexed.
- **How:** UpdateItem sets the `CodeOfConduct` map on demand. Readers treat absence as none.
- **Pitfalls:** Valid only for attributes not used in keys or indexes.

### Reuse an existing item collection for a new entity
- **Method:** Place a new child in a base-table collection that has free sort key space.
- **When:** Gists with Users, since the User collection holds only the User item.
- **How:** Gist SK `#GIST#<KSUID>` sorts before `ACCOUNT#...`, so a descending Query returns the User then the newest Gists. The Gist URL `gist.github.com/<username>/<gistId>` contains both key parts, so Get works by key.
- **Pitfalls:** The `#` prefix is required for ordering. Organization collections hold Membership after the Org item (ascending), so the same trick would conflict there. That is why Apps use a GSI.

### New collection in a GSI via backfill ETL
- **Method:** Decorate existing items with new GSI keys through a Scan plus UpdateItem job.
- **When:** Account plus Apps needs GSI1 keys on all existing User and Org items.
- **How:** Loop Scan with `FilterExpression: #type IN (:user, :org)` and `ExclusiveStartKey` from `.get('LastEvaluatedKey')`. For each hit, `update_item SET #gsi1pk = :gsi1pk, #gsi1sk = :gsi1sk` with values copied from the item's own PK and SK. The lazy alternative adds keys only when an account first creates an App.
- **Pitfalls:** The scan reads the whole table and costs capacity. The update is unconditional, so it is safe only because it touches just the new attributes. Add `ConditionExpression: attribute_not_exists(GSI1PK)` or a version check if a writer might set them concurrently.

### Adjacency list for many-to-many
- **Method:** Create an association item that appears in both parents' collections.
- **When:** Apps install into repos, repos hold many apps, both unbounded.
- **How:** AppInstallation PK `APP#...`, SK `REPO#...` puts it in the App collection in the base table. GSI1PK `REPO#...`, GSI1SK `REPOAPP#...` puts it in the Repo's GSI1 collection. The key includes both sides, so an app installs into a repo once. Add `attribute_not_exists(PK)` to reject a repeat.
- **Pitfalls:** The base-table side needs a free collection. No existing items change.

### Composite sort key for a double filter (status plus order)
- **Method:** Encode status and sequence in the sort key: `ISSUE#<STATUS>#<Number>`.
- **When:** A filter expression over-fetches, for example repos with mostly Open issues need 75-item first reads and follow-up queries.
- **How:** Query one status by key prefix. Ascending order gives Closed, Open, Repo. Fix it by prefixing Closed issues and the Repo with `#` so the Repo sits between Closed and Open. Then Open issues read oldest first. Fix that with `99999999 - number` for Open, so ascending key order is newest first.
- **How:** A status change is a key change. Update the GSI key attributes in the same UpdateItem, with `ConditionExpression: #status = :expected` so concurrent transitions fail.
- **Pitfalls:** The keys are meaningless outside DynamoDB. The pattern needs two new GSIs (GSI4 for Issues, GSI5 for PRs) because GSI1 to GSI3 are used. The alternative is one GSI per pattern: four indexes (open and closed Issues, open and closed PRs), at higher cost and with no shared capacity.
