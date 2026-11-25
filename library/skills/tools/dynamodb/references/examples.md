# Worked examples: session store, e-commerce, Big Time Deals, GitHub

Read this when a new design resembles one of these apps and you want the key shapes and the techniques that combined to serve its access patterns.

## Ch 17. Notes on the examples

Key points
- Every example follows the process in modeling.md: understand the app, draw the ERD, list access patterns, design primary keys, then indexes.
- Tables list indexing attributes only. Application attributes still exist on the items.
- List access patterns first and skip trivial single-item read, write and update patterns unless they teach something.
- Reuse strategies per section of the model. No example matches an app exactly.
- Keep the entity chart (PK, SK, GSI keys) and the access pattern table in the repository. Key overloading hides intent from readers of the data layer.

## Ch 18. Building a Session Store

### Access patterns
| Access pattern | Index | Key condition / key shapes |
|---|---|---|
| Create Session | Main | PutItem, PK `SessionToken` (uuid4), `attribute_not_exists(SessionToken)` |
| Get Session | Main | Query `SessionToken = :token`, filter on TTL greater than now |
| Delete Session (time-based) | none | DynamoDB TTL on attribute `TTL` (epoch seconds) |
| Delete Sessions for User | `UserIndex` GSI, then Main | GSI PK `Username`, KEYS_ONLY; then DeleteItem by `SessionToken` |

Item attributes: `SessionToken`, `Username`, `CreatedAt` (ISO), `ExpiresAt` (ISO, now plus 7 days), `TTL` (epoch seconds, same instant).

### Techniques
- Name keys after the data (`SessionToken`, `Username`) when the table holds one entity type. Switch to generic `PK` and `SK` once a second type shares the table.
- Make the unique value the partition key and write with `attribute_not_exists(SessionToken)`. A duplicate raises `ConditionalCheckFailedException` and writes nothing. Use a UUIDv4 so collisions are unlikely and the condition so they are impossible. A GSI key cannot enforce uniqueness.
- Expire with TTL on a Number attribute in epoch seconds. Keep the ISO `ExpiresAt` beside it for debugging, since TTL ignores strings.
- Filter at read time because deletion lags expiry, typically by up to a few days. Query `#token = :token` with `FilterExpression="#ttl > :epoch"`, where `:epoch` is `{"N": str(int(time.time()))}`. An empty result means missing or expired. Treat both as unauthenticated.
- A grouping-only parent (User) needs no item. Add a GSI with simple key `Username` and `KEYS_ONLY` projection, Query it, then DeleteItem per `SessionToken`. There is no delete-by-filter. Paginate for users with many sessions.
- The GSI read is eventually consistent and can miss a just-created session. Decide ownership or expiry against the base table.
- Alternatives not chosen: lazy expiry (check `ExpiresAt` on read and delete, leaves dead items for users who never return) and pro-active expiry (extra GSI plus a scheduled job).

## Ch 19. Building an E-commerce Application

### Access patterns
| Access pattern | Index | Key condition / key shapes |
|---|---|---|
| Create Customer (unique username and email) | Main | TransactWriteItems: Customer `PK=SK=CUSTOMER#<Username>`; CustomerEmail `PK=SK=CUSTOMEREMAIL#<Email>`; both `attribute_not_exists(PK)` |
| Create/Update/Delete Address | Main | UpdateItem on `Addresses` map of the Customer item |
| View Customer and recent Orders | Main | Query `PK = CUSTOMER#<Username>`, `ScanIndexForward=False`, `Limit=11` |
| Save Order | Main | TransactWriteItems: Order `PK=CUSTOMER#<Username>`, `SK=#ORDER#<OrderId>` plus OrderItems |
| Update Order | Main | UpdateItem status |
| View Order and OrderItems | GSI1 | Query `GSI1PK = ORDER#<OrderId>`. Order: GSI1PK=GSI1SK `ORDER#<OrderId>`. OrderItem: PK=SK `ORDER#<OrderId>#ITEM#<ItemId>`, GSI1PK `ORDER#<OrderId>`, GSI1SK `ITEM#<ItemId>` |

### Techniques
- Use a composite primary key from the start because of fetch-many and parent-plus-children reads.
- Enforce multi-attribute uniqueness with one companion item per attribute (Customer, CustomerEmail) in one `TransactWriteItems`, each with `attribute_not_exists(PK)`. The email item is a bare marker. Uniqueness lives in the main table key, never a GSI.
- Denormalize bounded children into a map. Addresses sit on the Customer item, capped at 20, because no pattern fetches them by their own values. A cap is a legitimate product requirement.
- Pre-join unbounded children with the parent's partition key. Order `SK=#ORDER#<KSUID>` sorts before the Customer item, so a reverse Query with `Limit=11` returns the Customer plus the 10 newest Orders.
- Regroup a second one-to-many in a GSI. OrderItems in the Customer collection would pollute the recent-orders Query, so both Order and OrderItem carry `GSI1PK = ORDER#<OrderId>` and one GSI1 Query returns an Order with its items.
- Write an Order with its OrderItems in one `TransactWriteItems`, one Put per item. Respect the transaction limit of 100 items and 4MB.
- Use KSUIDs for OrderId to get uniqueness and chronology from the sort key.

## Ch 20. Building Big Time Deals

### Access patterns
| Access pattern | Index | Key condition / key shapes |
|---|---|---|
| Create/Fetch Deal | Main | PK=SK `DEAL#<KSUID>` |
| Latest deals overall | GSI1 | GSI1PK `DEALS#<TruncatedTimestamp>`, GSI1SK `DEAL#<DealId>`, Query descending, `SK < DEAL#<last_seen>`, Limit 25 |
| Latest deals for Brand | GSI2 | GSI2PK `BRAND#<Brand>#<TruncatedTimestamp>`, GSI2SK `DEAL#<DealId>` |
| Latest deals for Category | GSI3 | GSI3PK `CATEGORY#<Category>#<TruncatedTimestamp>`, GSI3SK `DEAL#<DealId>` |
| Cached latest deals | Main | GetItem `DEALSCACHE#<1..N>` (PK=SK) |
| Fetch Brand | Main | PK=SK `BRAND#<Brand>`, in parallel with the deals query |
| Fetch all Brands | Main | GetItem singleton PK=SK `BRANDS`, set attribute `Brands` |
| Brand Like | Main | PK=SK `BRANDLIKE#<Brand>#<Username>` plus counter `LikesCount` on Brand |
| Brand Watch | Main | PK `BRANDWATCH#<Brand>`, SK `USER#<Username>`, counter `WatchCount` |
| Category, CategoryLike, CategoryWatch | Main | `CATEGORY#<Category>` PK=SK; `CATEGORYLIKE#<Category>#<Username>` PK=SK; PK `CATEGORYWATCH#<Category>`, SK `USER#<Username>` |
| Featured deals (Category) | Main | `FeaturedDeals` complex attribute on the Category item |
| Front Page / Editor's Choice | Main | Singletons PK=SK `FRONTPAGE`, `EDITORSCHOICE` |
| Create User | Main | PK=SK `USER#<Username>`, `attribute_not_exists` for uniqueness; `UserIndex` attribute `USER#<Username>` |
| All Users | `UserIndex` GSI | Scan the sparse index (only User items carry `UserIndex`) |
| Messages for User | Main | PK `MESSAGES#<Username>`, SK `MESSAGE#<KSUID>`, `ScanIndexForward=False` |
| Unread Messages | GSI1 | GSI1PK `MESSAGES#<Username>`, GSI1SK `MESSAGE#<KSUID>`, set only while unread |
| Mark Message read | Main | UpdateItem SET Unread False, REMOVE GSI1PK, GSI1SK |
| Notify Brand/Category watchers | Main | Query `BRANDWATCH#<Brand>` / `CATEGORYWATCH#<Category>`, then create a Message per user |
| Hot New Deal to all Users | `UserIndex`, then Main | Scan the index, create a Message per User |

### Techniques
- Use KSUIDs for DealId and MessageId. Embed them in the sort key so `SK < DEAL#<last_seen>` paginates by recency.
- Shard "latest N" by time. Put a truncated timestamp (day for about 100 deals per day, hour or month by write rate) in the GSI partition key. Query one bucket descending with `Limit=25`. If fewer than 25 return, step back one bucket, capped at 5 days so sparse tables do not loop forever. Return at most 25 and carry the remaining limit into each step. Pagination logic lives in the app.
- Random-shard scatter-gather was rejected because it hits all N partitions and must re-merge. The parent Brand or Category item cannot join the sharded collection, so fetch it in a parallel request.
- Cache a hot read in N copies. A Lambda on the DynamoDB Stream queries the last two days of deals and writes N identical items `PK=SK=DEALSCACHE#<n>` with a `Deals` list. The reader picks `random.randint(1, N)` and calls GetItem. Read `resp['Item']`. Widen N to scale. Copies are eventually consistent. Redis is the alternative.
- Hold a bounded set in a singleton item. PK=SK `BRANDS` with a `Brands` set suits about 200 brands. The Front Page and Editor's Choice singletons hold featured deals written wholesale by the CMS. Reject it for unbounded data (Users) because of the 400KB limit. Copy a hot singleton across items like DealsCache.
- Copy 5 to 10 featured deals into a complex attribute on the Category item. The CMS overwrites the full list on each edit. A sparse index was rejected as overweight.
- Model Like and Watch as one item per relationship plus a counter on the parent, in one `TransactWriteItems`: Put with `attribute_not_exists(PK)` and Update `SET #likes = #likes + :incr` with `attribute_exists(PK)`. A set of likers is infeasible because it is unbounded. Watch uses PK `BRANDWATCH#<Brand>` and SK `USER#<Username>` so watchers share a collection and can be Queried.
- Fan out on write from the DynamoDB Stream. On a Deal insert, Query `BRANDWATCH#<Brand>` and create a Message per watcher. Stream handlers are at-least-once, so derive the message id deterministically from deal and user and Put with `attribute_not_exists` so redelivery is a no-op.
- Enumerate all items of one unbounded type with a sparse GSI. Add `UserIndex` only to User items and Scan the index. A static `USERS` partition would be a write hotspot. Do not reuse the index for other entities.
- Filter within a type with a sparse index. Create Message with `Unread="True"`, `GSI1PK=MESSAGES#<Username>`, `GSI1SK=MESSAGE#<KSUID>`. Mark read with `SET #unread = :false REMOVE #gsi1pk, #gsi1sk`, which drops the item from the index in the same write. The reader sets `IndexName='GSI1'` when `unread_only`. The index update propagates eventually. Rejected: read state in the partition key (doubles reads), a composite sort key (poor for optional filtering), filter expressions (overfetch).
- Enforce Create User uniqueness with `attribute_not_exists(PK)` on the main-table key.

## Ch 21. Recreating GitHub's Backend

### Access patterns
| Access pattern | Index | Key condition / key shapes |
|---|---|---|
| Get/Create Repo | Main | PK=SK `REPO#<Owner>#<RepoName>` |
| Repo plus Issues | Main | PK `REPO#<Owner>#<RepoName>`, SK `ISSUE#<ZeroPaddedIssueNumber>` (7 digits), Query `ScanIndexForward=False` |
| Repo plus Stars | Main | PK `REPO#<Owner>#<RepoName>`, SK `STAR#<UserName>`, Query `SK >= REPO#...` ascending |
| Repo plus Pull Requests | GSI1 | Repo GSI1PK=GSI1SK `REPO#<Owner>#<RepoName>`; PR PK=SK `PR#<Owner>#<RepoName>#<ZeroPaddedPRNumber>`, GSI1PK `REPO#<Owner>#<RepoName>`, GSI1SK `PR#<ZeroPaddedPRNumber>` |
| Fork Repo / Get Forks | GSI2 | Original: GSI2PK `REPO#<Owner>#<RepoName>`, GSI2SK `#REPO#<RepoName>`; Fork: GSI2PK `REPO#<OriginalOwner>#<RepoName>`, GSI2SK `FORK#<Owner>` |
| Issue/PR comments | Main | PK `ISSUECOMMENT#<Owner>#<RepoName>#<IssueNumber>` or `PRCOMMENT#...#<PRNumber>`, SK `ISSUECOMMENT#<KSUID>` / `PRCOMMENT#<KSUID>` |
| Reaction | Main | PK=SK `<TargetType>REACTION#<Owner>#<RepoName>#<TargetIdentifier>#<UserName>` (TargetType ISSUE, PR, ISSUECOMMENT, PRCOMMENT) |
| User / Organization | Main | PK=SK `ACCOUNT#<AccountName>` |
| Users in Organization | Main | Query PK `ACCOUNT#<OrgName>`, SK `MEMBERSHIP#<UserName>` |
| Organizations for User | Main | `Organizations` map on the User item (name to role) |
| Repos for Account | GSI3 | Repo GSI3PK `ACCOUNT#<AccountName>`, GSI3SK `#<UpdatedAt>`; account item GSI3PK=GSI3SK `ACCOUNT#<AccountName>` |
| Payment plan | Main | `PaymentPlan` map on the User/Org item |

### Techniques
- Share one collection between two one-to-many relations with the parent in the middle. Issue SK `ISSUE#...` sorts before `REPO#...` and Star SK `STAR#...` sorts after. Repo plus Issues: Query descending with `#sk <= :sk`. Repo plus Stars: `#sk >= :sk` ascending, where `:sk` is the Repo SK. It works only when the two relations need opposite directions. Keep the Repo key identical in every item (`REPO#<Owner>#<RepoName>`).
- Put a third relation (Pull Requests) in GSI1, which regroups Repo with PRs. Put Forks in GSI2, since a fork is itself a Repo. Original Repo GSI2SK `#REPO#<RepoName>` sorts first. Forks use the original owner's partition and SK `FORK#<Owner>`.
- Zero-pad issue and PR numbers inside string sort keys (7 digits). The width fixes the maximum count.
- Issue and PR numbers share one per-repo sequence. Run `UpdateItem SET #count = #count + :incr` on the Repo item with `ReturnValues='UPDATED_NEW'`, then Put the Issue with SK `ISSUE#<padded count>` and `attribute_not_exists(PK)`. A failed second step leaves a gap. Use a transaction when gaps matter.
- Filter Open/Closed with `attribute_not_exists(#status) OR #status = :status`, where `attribute_not_exists` keeps the Repo item. It suits two status values and small pages. The first read covers about 75 items to find 25 matches. Measure in production and move status into the key if wasteful (see migrations.md).
- Keep counts (StarCount, ForkCount, reactions) on the parent. Update in a transaction with the existence-guarded child: Put with `attribute_not_exists(PK)` and Update `SET #count = #count + :incr` with `attribute_exists(PK)`. A duplicate star cancels the transaction and the counter stays put. A counter on a very popular parent can become a write hotspot.
- Track reactions with a string set on a per-user-per-target item and a map of counts on the target. Transaction action 1: `UpdateItem ADD #reactions :reaction` (`:reaction` type SS, e.g. `["Heart"]`) with `ConditionExpression: attribute_not_exists(#reactions) OR NOT contains(#reactions, :reaction)`. Action 2: `SET #counts.#reaction = #counts.#reaction + :incr` on the target's `ReactionCounts` map. The `attribute_not_exists` branch covers the first write.
- Give comments their own collection (PK `ISSUECOMMENT#<Owner>#<RepoName>#<IssueNumber>`, SK `ISSUECOMMENT#<KSUID>`) when no pattern reads an Issue with its Comments.
- Share a namespace with one key shape. User and Organization both use PK=SK `ACCOUNT#<name>`, distinguished by a `Type` attribute, so one `attribute_not_exists` covers cross-type uniqueness. Querying by `Type` needs an index.
- Handle a mixed many-to-many by bounded-side denormalization. The User item holds an `Organizations` map (cap about 40). Membership items `ACCOUNT#<OrgName>` / `MEMBERSHIP#<UserName>` serve the unbounded side. Use a transaction when both sides change, because they can diverge.
- Embed small one-to-one data as a map (`PaymentPlan`). Split only when the data is large with different access patterns.
- Put an account and its repos ordered by update time in GSI3 (Repo GSI3SK `#<UpdatedAt>`, account GSI3SK `ACCOUNT#<name>`, query descending). Changing `UpdatedAt` rewrites the GSI entry.
