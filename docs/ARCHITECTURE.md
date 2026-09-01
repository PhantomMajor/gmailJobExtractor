# Architecture & Design Decisions

## System Overview

```
Gmail Inbox (JobSearch label)
           ↓
    [Extractor CLI]
           ↓
      jobs.db (SQLite)
           ↑                    ↓
    [Backend API]          [Web Frontend]
    (Flask, REST)          (HTML + Vanilla JS)
```

**Data flow:**
1. **Extractor** reads emails from Gmail → extracts job details → writes to SQLite
2. **Backend API** queries SQLite → returns JSON
3. **Frontend** fetches JSON via API → renders interactive UI with three-state toggle

---

## Phase 1: Local Web Interface

### Architecture Decisions

#### 1. **Three-State Interested Field**
- **null** = Not Evaluated (untouched by user)
- **1** = Interested
- **0** = Not Interested
- **Cycle:** null → 1 ⇄ 0 (once touched, never returns to null)

**Why?** Distinguishes between "not yet decided" and "explicitly rejected". Allows user to evaluate jobs in stages (explore → decide).

#### 2. **Vanilla JavaScript (no framework)**
- No build step, no dependencies
- Simple `fetch()` API for HTTP calls
- DOM manipulation with vanilla JS

**Why?** Minimal complexity for UI that's just a table + filters. A framework (React/Vue) would be overkill and slow to develop.

**Tradeoff:** Write more JS code ourselves, but we own the stack entirely.

#### 3. **Flask Backend (Python)**
- Already using Python for the extractor
- Minimal overhead, synchronous is fine for this scale
- SQLite queries directly in `src/db.py`

**Why?** Zero context switch. Can reuse existing DB layer.

#### 4. **No Pagination (Phase 1)**
- Assume <5k jobs fit in memory
- Add pagination only if dataset grows >10k

**Why?** Faster to ship. JavaScript array operations are fast enough for 5k rows. Revisit if performance degrades.

#### 5. **Stateless API (no sessions)**
- Every request is independent
- No user accounts, no auth (localhost-only)

**Why?** Personal tool running locally. Auth adds complexity we don't need yet. Phase 2 can add CSRF/OAuth if sharing URL.

#### 6. **Optimistic UI Updates**
- Button state changes immediately on click
- Server confirms or reverts
- Feels responsive to user

**Why?** Better UX. Network latency doesn't block the UI.

---

## API Endpoints

### `GET /api/jobs`
- Returns jobs in descending extraction order
- Optional filters: `?company=X` (partial match), `?interested=1` (show interested only)
- Response: `{ "jobs": [...] }`

### `GET /api/stats`
- Returns: `{ "total_jobs": int, "unique_companies": int, "interested_count": int, "top_companies": [...] }`

### `POST /api/jobs/<id>/interested`
- Cycles interested state: null → 1 → 0 → 1 → 0 ...
- Validates: ID must be integer and exist in DB
- Response: `{ "id": int, "interested": 1 | 0 | null }`
- Error: 400 (bad format), 404 (not found)

---

## Phase 2: Cloud Deployment

### Architecture Change

```
Extractor (local) ↔ Turso (SQLite cloud) ← Vercel Functions (API) ← Vercel Hosting (Frontend)
                        ↑
                   Replicated DB
```

### Technology Choices

| Layer | Phase 1 | Phase 2 | Why |
|-------|---------|---------|-----|
| Database | SQLite (local file) | Turso (cloud) | Zero code changes; portable; free tier sufficient |
| Frontend | Flask serves HTML | Vercel static hosting | Always-on; CDN; no server cost |
| Backend | Flask (local) | Vercel Serverless Functions | Same API contract; scales automatically |

### Turso Free Tier

- **5 GB storage** + **1M rows**
- **Realistic capacity:** 5k–50k jobs (~50 bytes per record)
- **Verdict:** ✅ Sufficient for personal use

### Sync Strategy (Phase 2 Decision Point)

**Option A: Direct-to-Turso (recommended)**
- Extractor writes directly to Turso (connection string change)
- Single source of truth; no sync complexity
- **Con:** Requires Turso API key in local `.env`

**Option B: Local-first + cron sync**
- Extractor writes to local DB (as today)
- Nightly cron exports local → Turso
- **Pro:** Works offline; keeps local backup
- **Con:** Eventual consistency; more moving parts

**Recommendation:** Option A. Simpler, faster.

---

## Security & Validation

### Phase 1 Validation
Every mutation validates:
1. **ID format check** — must be integer (400 error if not)
2. **ID existence check** — must exist in DB (404 error if not)
3. **Atomic update** — single SQL statement, no race conditions

### Phase 2 Extension (no code changes needed)
- Add `@require_csrf_token` decorator to `/api/jobs/<id>/interested`
- Validation logic stays identical
- CSRF token validated as middleware

---

## Tradeoffs & Risks

### Phase 1 Tradeoffs
| Decision | Benefit | Cost |
|----------|---------|------|
| Vanilla JS | No dependencies, small bundle | More JS code to write |
| Local-only | Simple, no auth overhead | Not shareable online |
| No pagination | Faster to ship | Need pagination if >10k jobs |
| Optimistic updates | Feels fast to user | Must revert on error |

### Phase 2 Risks
| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Turso free tier exhausted | Low | Monitor usage; keep local DB fallback |
| Sync bugs (local ↔ cloud) | Medium | Test migration carefully; document strategy |
| CORS issues | Medium | Configure Vercel + Turso CORS settings |

---

## Data Model

### Interested Column
```sql
interested INTEGER  -- NULL (not evaluated), 1 (interested), 0 (not interested)
```

**Indexes:**
- `idx_company` — fast company filtering
- `idx_interested` — fast interested-only queries

**Constraints:**
- Unique on `(message_id, role, company)` — prevents duplicate jobs
- Foreign keys enabled on connections

---

## File Structure

```
├── docs/
│   ├── ARCHITECTURE.md    (this file—decisions & rationale)
│   ├── ROADMAP.md         (phases, timeline, future work)
│   └── prd.md             (product vision, scope)
├── src/
│   ├── app.py             (Flask server, API endpoints)
│   ├── db.py              (SQLite query layer)
│   └── gmailJobExtractor.py (CLI extractor—unchanged)
├── templates/
│   └── index.html         (homepage UI)
├── static/
│   └── app.js             (client-side logic)
├── run.py                 (entry point)
├── jobs.db                (SQLite database)
└── requirements.txt       (Flask dependency)
```

---

## Next Steps

**Phase 1 validation:**
- ✅ API endpoints working
- ✅ Frontend renders and filters
- ✅ Three-state toggle persists to DB
- ✅ Stats display correct

**Before Phase 2:**
1. Decide: Option A (direct-to-Turso) or Option B (cron sync)?
2. Create Turso account and test migration
3. Set up Vercel project (free tier)
4. Deploy frontend + serverless functions
5. Test end-to-end from public URL

See [ROADMAP.md](./ROADMAP.md) for full timeline.
