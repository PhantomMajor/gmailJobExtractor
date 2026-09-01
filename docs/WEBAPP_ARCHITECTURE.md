# Webapp Architecture & Roadmap

## Vision
Display extracted jobs in a searchable web interface to enable discovery, filtering, and marking interested or not. Two-phase rollout: local-first for rapid iteration, cloud migration for accessibility.

## Phase 1: Local Webapp (MVP)

### High-Level Architecture
```
Extractor (CLI)  →  SQLite (jobs.db)  ←  Web Backend (Flask)  ←→  Frontend (HTML/JS)
   ↑                                             ↓
   └─ Already exists                    Query + JSON response
```

### Tech Stack Rationale
| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | Flask (Python) | Already using Python; minimal overhead; synchronous is fine for this scale |
| **Frontend** | HTML + vanilla JS | No build step; fast iteration; zero framework dependencies; modern fetch API |
| **Database** | SQLite (local file) | Already in use; zero ops; queries via Python sqlite3 driver |

### Design Decisions

#### 1. **API Design (Stateless, simple REST)**
- `GET /api/jobs` — list all jobs (sorted by date DESC)
- `GET /api/jobs?company=X` — filter by company (case-insensitive partial match)
- `GET /api/jobs?interested=1` — show only marked-interested jobs
- `GET /api/stats` — aggregate stats (total jobs, unique companies, etc.)
- `POST /api/jobs/<id>/interested` — toggle job's `interested` flag in DB

**Validation & Security (Phase 1 → Phase 2 ready):**

Phase 1 implements core validation; Phase 2 layers on CSRF/auth without changing the mutation logic:

```python
# Phase 1: Validate & perform mutation
@app.post('/api/jobs/<job_id>/interested')
def toggle_interested(job_id):
    # 1. Validate job_id is a valid integer
    try:
        job_id = int(job_id)
    except ValueError:
        return {"error": "Invalid job ID format"}, 400
    
    # 2. Verify job exists in DB before mutating (prevents orphaned updates)
    conn = get_connection()
    cursor = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
    if not cursor.fetchone():
        return {"error": "Job not found"}, 404
    
    # 3. Atomic update: toggle interested flag (NULL ↔ 1)
    conn.execute("""
        UPDATE jobs 
        SET interested = CASE WHEN interested IS NULL THEN 1 ELSE NULL END
        WHERE id = ?
    """, (job_id,))
    conn.commit()
    
    # 4. Return updated state to client
    cursor = conn.execute("SELECT interested FROM jobs WHERE id = ?", (job_id,))
    updated = cursor.fetchone()[0]
    conn.close()
    return {"id": job_id, "interested": bool(updated)}, 200

# Phase 2: Add CSRF protection without changing mutation logic
@app.post('/api/jobs/<job_id>/interested')
@require_csrf_token  # Decorator validates X-CSRF-Token header or body field
def toggle_interested(job_id):
    # ... identical validation + update logic above ...
    pass
```

**Design principles:**
- **Validate early:** Type-check ID format, verify existence before any mutation
- **Atomic mutations:** Single UPDATE with CASE expression (serializable under SQLite)
- **Idempotent:** Toggling twice returns to original state (safe for network retries)
- **Phase 2 ready:** CSRF/auth layer added as decorator; core logic unchanged
- **Error codes:** 400 (bad format), 404 (not found), 200 (success)
- **Request format (stays same in Phase 2):** `POST /api/jobs/5/interested` with optional `X-CSRF-Token` header

**Trade-off:** No pagination initially (assume <5k jobs fit in memory). Add if dataset grows beyond 10k.

#### 2. **Frontend First-Pass**
- Single-page app (vanilla JS, no SPA framework yet)
- Table view of jobs (role, company, location, date)
- Inline filters (dropdown or search box for company)
- Click to expand for full metadata (experience, sender, original date)
- Mark-as-interested button per row
- Search/filter via vanilla `fetch()` API (see [FRONTEND_API_CLIENT.md](./FRONTEND_API_CLIENT.md) for implementation patterns)

**Trade-off:** No framework dependencies (smaller, faster to load). Plain JavaScript is sufficient for this complexity level.

#### 3. **Data Ownership & Mutation**
- Only the extractor (CLI) writes to DB (via `gmailJobExtractor.py`)
- Webapp only *reads* + toggles the `interested` flag
- This keeps data flow simple: CLI is source of truth for job data; webapp is display + light interaction layer
- `interested` flag is scoped to the webapp; extractor ignores it

**Trade-off:** No full CRUD; constraints prevent accidental deletions or overwrites. Clean separation of concerns.

#### 4. **No Auth in Phase 1**
- Webapp runs on `localhost:5000` only
- Intended for personal use (you, on your machine)
- No user management, no login

**Trade-off:** Not shareable online yet (accept for MVP). Phase 2 can add auth if needed.



## Phase 2: Cloud Migration (Stretch)

### Architecture Shift
```
Extractor (local)  ←→  Turso (SQLite cloud)  ←  Vercel Functions (API)  ←→  Vercel Hosting (Frontend)
                             ↑
                        Replicated DB
```

### Tech Stack Changes
| Layer | Change | Impact |
|-------|--------|--------|
| **Database** | SQLite (local) → Turso (cloud) | Zero code changes to queries; just change connection string |
| **Backend** | Flask (local) → Vercel Serverless Functions (Node.js or Python) | Replaces Flask; same API contract |
| **Frontend** | Flask-served HTML → Vercel-hosted static + serverless calls | Same HTML/JS; CORS handling needed |
| **Hosting** | Local machine → Vercel (free tier) | Frontend is always up; backend scales automatically |

### Turso Free Tier Evaluation
**Is 5GB + 1M rows enough?**
- **Assumptions:** ~50 bytes per job record (metadata stored as JSON string)
- **Math:** 5GB ÷ 50 bytes = ~100M records possible
- **Reality:** With indexes, metadata, timestamps: expect ~5k–50k jobs comfortably before approaching limits
- **Verdict:** ✅ **Sufficient for personal use**. Scale only if you extract >50k jobs across multiple years

### Data Sync Strategy (Phase 2 Problem)
**Challenge:** Extractor runs locally; DB now in cloud. How do we keep them in sync?

**Option A: Extractor writes directly to Turso**
- Change connection string from local `jobs.db` to Turso remote
- Extractor still works the same way
- **Pro:** Single source of truth; no sync overhead
- **Con:** Requires Turso API key in local environment (security consideration)

**Option B: Extractor → local DB → periodic sync to Turso**
- Extractor writes to local SQLite as today
- Nightly cron job exports local DB → Turso (or vice versa)
- **Pro:** Local-first resilience; can work offline
- **Con:** Eventual consistency; more moving parts

**Recommendation:** **Option A** (direct-to-Turso) once Phase 2 is committed. Simpler, faster, single source of truth. Store API key in `.env`, never commit it.

### Migration Path (Phase 1 → Phase 2)
1. Create Turso workspace and database
2. Run `sqlite3 jobs.db .schema > schema.sql` on local DB
3. Recreate schema in Turso
4. Export jobs from local DB: `sqlite3 jobs.db "SELECT * FROM jobs"` → CSV → bulk insert to Turso
5. Test Phase 2 API against Turso
6. Deploy frontend to Vercel
7. Update extractor to use Turso (connection string change + `.env`)
8. Keep local `jobs.db` as backup

**Estimated effort:** 2–4 hours total (mostly waiting for Turso connection, testing).



## Tradeoffs & Decisions at a Glance

### Why Two Phases?
| Phase | Scope | Time | Benefit | Blocker |
|-------|-------|------|---------|---------|
| **1: Local** | Flask + HTML | 4–6 hrs | See your data; validate usefulness | None—start now |
| **2: Cloud** | Vercel + Turso | 3–4 hrs | Share URL; always-on; scale | Requires Turso account |

### Risk & Mitigation
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Turso free tier exhausted | Low | Can't query live data | Monitor usage; upgrade if needed; keep local DB as fallback |
| Sync bugs between local & cloud | Medium (Phase 2) | Data mismatch | Test Option A carefully; consider Option B if issues arise |
| Performance (5k+ jobs) | Low initially | UI sluggish | Add pagination in Phase 1 if >10k jobs |
| Auth needed later | Low | Security gap | Plug in OAuth2 (GitHub) in Vercel; stateless via JWT |

### Technical Debt Awareness
- **No error handling in Phase 1:** Assume local SQLite is always available
- **No caching:** Every request hits DB; fine for <1 min query time on small dataset
- **No audit logging:** Who marked what as interested? Not tracked (fine for solo user)
- **No schema versioning on webapp:** Unlike the extractor (which has schema_version), webapp assumes fixed schema; mirror extractor's pattern if DB evolves



## Success Criteria

### Phase 1
- [ ] Flask server starts, listens on `localhost:5000`
- [ ] Homepage shows all jobs in a table
- [ ] Filter by company works
- [ ] Mark-as-interested toggle saves to DB
- [ ] Stats endpoint shows totals

### Phase 2
- [ ] Frontend deployed to Vercel
- [ ] API deployed to Vercel Functions
- [ ] Public URL works from any device
- [ ] Data syncs from local extractor to Turso
- [ ] No manual intervention needed after initial setup

---

## File Structure (Phase 1)

```
gmailJobExtractor/
├── src/
│   ├── db.py              (existing—add query methods)
│   ├── app.py             (NEW—Flask server)
│   └── gmailJobExtractor.py (existing—no changes needed)
├── templates/
│   └── index.html         (NEW—homepage & UI)
├── static/
│   └── app.js             (NEW—client-side logic)
├── jobs.db                (existing)
└── requirements.txt       (update with Flask)
```

---

## Next Steps
1. Implement Phase 1 locally
2. Validate feature usefulness + gather UX feedback
3. If valuable, plan Phase 2 migration
4. Once Phase 2 done, consider: auth, sharing links, saved searches, etc.