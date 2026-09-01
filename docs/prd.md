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

---

# v1.2 Web Interface for Job Discovery

## Vision
Build a searchable web interface to explore extracted jobs locally, with an option to scale to cloud (Vercel + Turso) for always-on access.

For detailed architecture, validation, and security design, see [WEBAPP_ARCHITECTURE.md](./WEBAPP_ARCHITECTURE.md) and [FRONTEND_API_CLIENT.md](./FRONTEND_API_CLIENT.md).

## Phase 1: Local Webapp (MVP)

### Goals
- Display all extracted jobs in a browsable, filterable table
- Mark jobs as "interested" (save preference to DB)
- View aggregate stats (total jobs, unique companies, etc.)
- Run locally on `localhost:5000` (personal use, no auth needed)

### Tech Stack
- **Backend:** Flask (Python) — minimal overhead, same language as extractor
- **Frontend:** HTML + vanilla JavaScript — no build step, zero framework dependencies
- **API:** REST endpoints with validation; JSON responses
- **Data:** Query existing SQLite DB directly

### Key Design Decisions
1. **Webapp is read-mostly** — Only toggling the `interested` flag requires writes. All job data comes from the extractor (CLI).
2. **Vanilla fetch API** — Plain JavaScript, no htmx or SPA framework; simpler to maintain.
3. **Validated mutations** — All UPDATE endpoints validate job ID, verify existence before mutation, support CSRF in Phase 2 without refactoring.
4. **No pagination initially** — Assume <5k jobs fit in memory. Add if dataset grows beyond 10k.
5. **No auth in Phase 1** — Local-only (localhost:5000). Phase 2 can add CSRF + auth if needed.

### Success Criteria
- [ ] Flask server runs on `localhost:5000`
- [ ] Homepage displays all jobs in a filterable table
- [ ] Can filter by company (search/dropdown)
- [ ] Can mark/unmark jobs as interested
- [ ] Stats endpoint shows job totals and company breakdown
- [ ] Load time <2s for 5k jobs
- [ ] Optimistic UI updates (toggle shows immediately, reverts on error)

---

## Phase 2: Cloud Deployment (Stretch Goal)

### Goals
- Share job discoveries with a public or semi-public URL
- Webapp always accessible (not tied to local machine)
- Automated sync from local extractor to cloud DB

### Tech Stack
- **Frontend Hosting:** Vercel (free tier)
- **Backend:** Vercel Serverless Functions (Node.js or Python)
- **Database:** Turso (SQLite-as-a-service, free tier)

### Turso Free Tier Analysis
- **Storage:** 5 GB
- **Rows:** 1M
- **Realistic capacity:** 5k–50k jobs (assuming ~50 bytes per record + metadata)
- **Verdict:** ✅ Sufficient for personal use; upgrade only if >50k jobs across multiple years

### Migration Strategy
1. Export schema and data from local `jobs.db` to Turso
2. Deploy Flask app to Vercel as serverless functions (API endpoints)
3. Deploy frontend HTML/JS to Vercel static hosting
4. Update extractor to write to Turso (optional; can keep local DB + cron sync)
5. Keep local DB as offline fallback

### Effort Estimate
- **Phase 1:** 4–6 hours (Flask + basic UI)
- **Phase 2:** 3–4 hours (migration + deployment)
- **Total:** 7–10 hours from concept to cloud-hosted

---

## Tradeoffs

| Aspect | Phase 1 (Local) | Phase 2 (Cloud) |
|--------|-----------------|-----------------|
| **Setup time** | ~1 hour | +3 hours total |
| **Accessibility** | Local only (`localhost:5000`) | Public URL anywhere |
| **Uptime** | Only when machine is on | 99.9% (Vercel) |
| **Data ownership** | Local file (full control) | Turso cloud (encrypted at rest) |
| **Cost** | $0 | $0–$10/mo if scaling past free tier |
| **Complexity** | Simple (Flask + SQLite) | More moving parts (FaaS, cloud DB, sync) |

## Risks & Mitigation

| Risk | Phase | Likelihood | Mitigation |
|------|-------|-----------|------------|
| Turso free tier exhausted | 2 | Low | Monitor usage; keep local DB as fallback |
| Sync issues (local ↔ cloud) | 2 | Medium | Test data migration carefully; document sync strategy |
| Performance on large datasets | 1 | Low | Pagination if >10k jobs; indexes already in place |
| Schema evolution | Both | Medium | Treat schema as stable; breaking changes require migration scripts |

---

## Out of Scope (v1.2)
- User authentication (no login needed for personal tool)
- Sharing individual job links
- Advanced search (NLP, semantic search)
- Bulk actions (delete, export to CSV)
- Notifications or reminders

These can be added in future versions if valuable.