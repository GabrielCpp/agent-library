# Expressions: key condition, filter, projection, condition, update

Read this when writing any Query, filter, conditional write, or UpdateItem expression.

## Ch 6. Expressions

Key points
- Five expressions. Read: key condition, filter, projection. Write: condition (all writes) and update (UpdateItem).
- Every expression may use name placeholders. All but projection need value placeholders.
- A key condition applies only to primary key attributes. The partition key must use `=`. The sort key may use `=`, `<`, `<=`, `>`, `>=`, `BETWEEN`, `begins_with`. Every sort key condition can be written as BETWEEN.
- Filter and projection run after the 1MB read limit. They cut payload, not read cost. Pagination can return empty pages.
- A condition expression asserts state before a write and cancels the write when false. It evaluates atomically with the write on the same item. It replaces read-then-write and avoids races.
- A failed condition raises `ConditionalCheckFailedException`. A failed condition inside a transaction cancels every action with `TransactionCanceledException`.
- Update verbs are `SET`, `REMOVE`, `ADD`, `DELETE`. UpdateItem changes only the named attributes. PutItem replaces the whole item.
- Most PutItem calls should carry `attribute_not_exists` on the key.

### 6.1 Key Condition Expressions
- **Method:** Use the key condition in every Query to pick the partition and a sort key range.
- **When:** Every Query.
- **How:** `#c = :c AND #ot BETWEEN :start AND :end` with a customer id and OrderTime as an ISO-8601 string. `#a = :a AND #m < :title` for comparisons. Strings sort by UTF-8 bytes, so uppercase precedes lowercase. Numbers sort numerically.
- **Pitfalls:** Non-key attributes are not allowed. ISO-8601 timestamps sort correctly as strings.

### 6.2 Filter Expressions
- **Method:** Use FilterExpression to trim a response, never to implement an access pattern.
- **When:** Reduce payload, simplify client filtering, hide items past their TTL that DynamoDB has not yet deleted.
- **How:** `KeyConditionExpression="#actor = :actor", FilterExpression="#genre = :genre"`. A filter works on any attribute in Query and Scan.
- **Pitfalls:** The order is read (up to 1MB), then filter, then return. A 1GB table with 100KB of matches needs about 1000 requests, mostly empty. Build the pattern into the key or an index instead.

### 6.3 Projection Expressions
- **Method:** Use ProjectionExpression to return only needed attributes.
- **When:** Items carry large attributes, for example a 350KB cover image.
- **How:** `ProjectionExpression="#actor, #movie, #role, #year, #genre"`. It supports nested paths in lists and maps and applies to all reads.
- **Pitfalls:** It runs after the read, so 1MB paging remains. If large attributes force paging, create a GSI that projects only the needed attributes.

### 6.4 Condition Expressions
- **Method:** Add ConditionExpression to PutItem, UpdateItem, DeleteItem and their batch or transactional forms to assert item state first.
- **When:** Avoid overwrites, enforce invariants, check ownership, limit concurrency.
- **How:** Operators: `>`, `<`, `=`, `BETWEEN`. Functions: `attribute_exists()`, `attribute_not_exists()`, `attribute_type()`, `begins_with()`, `contains()` (substring or set membership), `size()` (string length, binary bytes, or element count of a list, map or set). A condition may reference any attribute of the targeted item.
- **Pitfalls:** The key parameter addresses the item, so conditions cover non-key attributes freely.

### 6.4.1 Preventing overwrites or checking for uniqueness
- **Method:** Put with `attribute_not_exists(#pk)` to create only if absent.
- **When:** Unique usernames or ids, idempotent create, taking a free lock, claiming an idempotency key.
- **How:** `put_item(TableName='Users', Item={Username, Name, CreatedAt}, ConditionExpression="attribute_not_exists(#username)", ExpressionAttributeNames={"#username":"Username"})`. A `ConditionalCheckFailedException` means another writer already holds or processed the key.
- **Pitfalls:** Uniqueness holds only on the full primary key of the base table. A GSI key cannot enforce it. Uniqueness on another attribute needs a separate item keyed by that value, written in a transaction (see additional-strategies.md).

### 6.4.2 Limiting in-progress items
- **Method:** Guard a tracking item's set with a `size()` condition to cap concurrent work.
- **When:** Limit jobs per state or group size.
- **How:** Item PK=`Tracker` holds a string set `InProgress`. Use `ConditionExpression="size(#inprogress) < :max"`, `UpdateExpression="ADD #inprogress :id"`, with `:id` = `{"SS":[<jobId>]}` and `:max` = `{"N":"10"}`. The set add is atomic and idempotent for the same id, so this is a counting semaphore.
- **Pitfalls:** `size(x) <= 10` passes at 10 members and lets the set reach 11. Use `< 10` to cap at 10.

### 6.4.3 Asserting user permissions on an item
- **Method:** Use `contains(set, :user)` in the condition to authorize an update.
- **When:** Only owners or admins may change an item.
- **How:** `ConditionExpression="contains(#a, :user)"`, `UpdateExpression="SET #st = :type"`, with Admins a string set on the item. The same shape works for an owner check: `#owner = :me`.

### 6.4.4 Checks across multiple items
- **Method:** Use TransactWriteItems with a `ConditionCheck` on one item and the write on another.
- **When:** The authorization or precondition lives on a different item than the one you write.
- **How:** `TransactItems=[{"ConditionCheck": {Key: PK=`Admins#<orgId>`, ConditionExpression: "contains(#a, :user)", ...}}, {"Delete": {Key: PK=`Billing#<orgId>`, TableName}}]`. All operations succeed or fail together. The checked item is not modified.
- **Pitfalls:** A transaction accepts up to 100 items and 4MB in aggregate.

### 6.5 Update Expressions
- **Method:** Use UpdateItem with SET, REMOVE, ADD, DELETE to change attributes in place.
- **When:** Partial updates, counters, set edits.
- **How:** `SET` sets or overwrites and does arithmetic. `REMOVE` deletes an attribute or nested element. `ADD` adds to a number or inserts into a set. `DELETE` removes members from a set. State each verb once with comma-separated clauses: `SET Name = :name, UpdatedAt = :updatedAt REMOVE InProgress`.
- **Pitfalls:** Unnamed attributes stay untouched. Use PutItem to replace the whole item.

### 6.5.1 Updating or setting an attribute
- **How:** `UpdateExpression="SET #picture = :url"`. It works whether or not the attribute exists. Guard it with an owner condition to renew a lease with `SET #expiresAt = :newExpiry`.

### 6.5.2 Deleting an attribute
- **How:** `UpdateExpression="REMOVE #picture"`.
- **When:** Also removes an item from a sparse GSI by dropping the index key attribute, and releases a lease without deleting the item.

### 6.5.3 Incrementing a numeric value
- **How:** `UpdateExpression="SET #views = #views + :inc"` with `:inc` = `{"N":"1"}`. It needs no prior read and has no race between concurrent increments.
- **When:** For optimistic concurrency, add `ConditionExpression="#v = :expected"` to a version increment. The condition rejects stale writers.

### 6.5.4 Adding a nested property
- **How:** `UpdateExpression="SET #phone.#mobile = :cell"` with `#phone` = `PhoneNumbers` and `#mobile` = `MobileNumber`. It updates one map key with no read.
- **Pitfalls:** The parent map must exist, or the update fails.

### 6.5.5 Adding and removing from a set
- **How:** `UpdateExpression="ADD #a :user"` with `:user` = `{"SS":["an_admin_user","another_user"]}`. Adding an existing member is not an error. To remove members, use `DELETE #a :user`.
- **Pitfalls:** `REMOVE` deletes whole attributes or list and map elements, not set members.
