# v1.1 migration from JSON to database
## tradeoffs

|Aspect|JSON|Database (SQLite)|
|---|---|---|
|Startup cost|~0ms (file load)|~5-50ms (connection)|
|Append performance|O(n) memory, must rewrite entire file|O(1), single INSERT|
|Query speed|O(n) full scan|O(1-log n) with indexes|
|Concurrent access|❌ Risky (race conditions)|✅ Safe with transactions|
|Operational complexity|Simple (just a file)|More setup, schema management|
|Backups & recovery|Copy a file|Requires DB backup strategy|

## key challenges
1. Schema evolution — JSON is schemaless; a DB needs schema. What happens if you add new fields (salary, job_type) later? => Mitigation: Use SQLite migrations (alembic or simple versioning). Plan the schema to be slightly forward-compatible.
2. Local file sync complexity — If you later want to sync data across devices or back up, JSON is trivial; DB requires deliberate sync. => Mitigation: For now, SQLite is local-only (fine for a personal tool). Later, you could add export-to-cloud or cron-based backup.
3. Testing & debugging — Harder to inspect intermediate state without DB tools. => Mitigation: Add a --debug flag to print extracted records before committing, or export to JSON for review.

## implementation steps
1. Start with SQLite — not PostgreSQL/MySQL. Zero setup overhead, file-based (portable).
2. Keep the atomic write pattern — use transactions:
```py
conn.execute("BEGIN TRANSACTION")
# ... INSERT records ...
conn.commit()  # atomic, same safety as JSON's tmp-file swap
```
3. Upsert on message_id — prevents duplicates cleanly:
```sql
INSERT INTO jobs (message_id, sender, date, subject, role, company, location, experience)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(message_id) DO UPDATE SET ...
```
4. Add an export-to-JSON command — for portability:
```bash
python gmailJobExtractor.py --export extracted_jobs.json
```
5. Version your schema — even for a simple tool:
```sql
CREATE TABLE schema_version (version INTEGER);
INSERT INTO schema_version VALUES (1);  -- on init, check this before queries
```
6. Keep the same CLI output — users shouldn't notice the storage layer changed.