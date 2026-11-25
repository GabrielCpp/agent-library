# Uniqueness, sequential IDs, pagination, singletons, reference counts

Read this when you need a unique claim on one or more attributes, a sequential number, a page cursor, a global limit, or a maintained count.

## Ch 16. Additional strategies

Key points
- Uniqueness exists only on the full primary key. Multi-attribute uniqueness needs a transaction over marker items.
- Guard every unique Put with `ConditionExpression: attribute_not_exists(PK)`.
- A sequential id needs an atomic counter on a parent item, incremented with UpdateItem and `ReturnValues=UPDATED_NEW`, then a Put that uses the returned number.
- Paginate by passing the last seen sort key to the client and querying `<` or `>` that key with `Limit`.
- A singleton item (fixed PK and SK) holds global state, such as a capped set of running jobs.
- Maintain a reference count with a TransactWriteItems that Puts the child (conditional) and Updates the parent counter.
- A transaction accepts up to 100 items and 4MB in aggregate. It replaces multi-item edits with manual rollbacks.

### 16.1 Ensuring uniqueness on two or more attributes
- **Method:** Write one marker item per unique attribute in one transaction, each with a not-exists condition.
- **When:** Username and email must both be unique, such as signup. The same shape suits lock and claim records.
- **How:** For one attribute, put the value in both PK and SK (PK=SK=`USER#alexdebrie`) and Put with a condition. For two, do not put the email in the SK of the user item. That only makes email unique per username. Use a transaction:
```
client.transact_write_items(TransactItems=[
 {'Put': {'TableName': 'UsersTable',
   'Item': {'PK': {'S': 'USER#alexdebrie'}, 'SK': {'S': 'USER#alexdebrie'},
            'Username': {'S': 'alexdebrie'}, 'FirstName': {'S': 'Alex'}},
   'ConditionExpression': 'attribute_not_exists(PK)'}},
 {'Put': {'TableName': 'UsersTable',
   'Item': {'PK': {'S': 'USEREMAIL#alex@debrie.com'}, 'SK': {'S': 'USEREMAIL#alex@debrie.com'}},
   'ConditionExpression': 'attribute_not_exists(PK)'}}])
```
- **How:** The email item is a bare marker. Both items are created or neither. Any failed condition cancels all.
- **Pitfalls:** To read a user by email, duplicate all user data on the email item. Then every user update must be a transaction, which raises write cost and latency. Avoid that when possible.

### 16.2 Handling sequential IDs
- **Method:** Keep a counter attribute on the parent item. Increment it atomically and use the returned value as the child id.
- **When:** User-facing sequential numbers such as tickets, issues, order numbers.
- **How:**
```
resp = client.update_item(TableName='JiraTable',
  Key={'PK': {'S': 'PROJECT#my-project'}, 'SK': {'S': 'PROJECT#my-project'}},
  UpdateExpression="SET #count = #count + :incr",
  ExpressionAttributeNames={"#count": "IssueCount"},
  ExpressionAttributeValues={":incr": {"N": "1"}},
  ReturnValues='UPDATED_NEW')
current_count = resp['Attributes']['IssueCount']['N']
client.put_item(TableName='JiraTable',
  Item={'PK': {'S': 'PROJECT#my-project'}, 'SK': {'S': f"ISSUE#{current_count}"},
        'IssueTitle': {'S': '...'}},
  ConditionExpression='attribute_not_exists(PK)')
```
- **How:** The increment is atomic server-side, so concurrent callers each get a distinct value. The value also works as a fencing token or version number.
- **Pitfalls:** The create takes two requests. If the Put fails after the increment, the number is skipped, and a counter value is never reused. Put both writes in one TransactWriteItems when gaps matter. Pad the number if it forms part of a string SK (see filtering-sorting.md, zero-padding).

### 16.3 Pagination
- **Method:** Return the last seen sort key to the client (in the URL) and use it as the next Query bound.
- **When:** Paging through an item collection, such as orders per user.
- **How:** PK=`USER#<username>`, SK=`ORDER#<KSUID>`. First page: `KeyConditionExpression='#pk = :pk AND #sk < :sk'` with `:pk`=`USER#alexdebrie`, `:sk`=`ORDER$`, `ScanIndexForward=False`, `Limit=5`. The character `$` sorts just after `#`, so it bounds the end of the `ORDER#` range. Next page: URL `/users/alexdebrie/orders?before=<OrderId>` with `:sk`=`ORDER#<OrderId>`.
- **Pitfalls:** Works within one item collection only.

### 16.4 Singleton items
- **Method:** Use one item with a fixed key to track application-wide state.
- **When:** A global cap or a meta view, such as at most 100 running jobs, or a front page.
- **How:** Item PK=SK=`JOBS` holds `JobsInProgress` as a string set. Start a job with a transaction of two writes. First, update the singleton with `ADD #jobs :id` under `ConditionExpression="attribute_not_exists(#jobs) OR size(#jobs) < :max"` where `:max` is 100. The `attribute_not_exists` branch admits the first job, because `size()` of a missing attribute makes the condition false. Second, update the Job item to status `IN_PROGRESS`. The pair is a counting semaphore, and a crash cannot leave a slot held without a running job.
- **Pitfalls:** All writers hit one item, which limits throughput to the 1000 WCU per-partition ceiling.

### 16.5 Reference counts
- **Method:** In one transaction, insert the related item (conditional) and increment the counter on the parent.
- **When:** Show the count of related items (stars, retweets, likes) without counting on read.
- **How:**
```
dynamodb.transact_write_items(TransactItems=[
 {"Put": {"Item": {"PK": {"S": "REPO#alexdebrie#dynamodb-book"},
                    "SK": {"S": "STAR#danny-developer"}},
          "TableName": "GitHubModel",
          "ConditionExpression": "attribute_not_exists(PK)"}},
 {"Update": {"Key": {"PK": {"S": "REPO#alexdebrie#dynamodb-book"},
                      "SK": {"S": "REPO#alexdebrie#dynamodb-book"}},
             "TableName": "GitHubModel",
             "ConditionExpression": "attribute_exists(PK)",
             "UpdateExpression": "SET #count = #count + :incr",
             "ExpressionAttributeNames": {"#count": "StarCount"},
             "ExpressionAttributeValues": {":incr": {"N": "1"}}}}])
```
- **How:** The pair is idempotent per user. A repeat call fails the Put condition and the counter does not double count. The parent guard also fails the claim if the parent was deleted. Deletion needs the mirror transaction: Delete with `attribute_exists(PK)` and decrement.
- **Pitfalls:** Counting by query burns read capacity on thousands of items. Match the parent SK to your real key design.
