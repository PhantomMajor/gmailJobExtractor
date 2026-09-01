# Project Roadmap

## Overview
This roadmap shows the evolution of the job extractor from a CLI tool to a discoverable, personal job dashboard.

### Overall Project Success
- Job discovery workflow improved (easier to find/review jobs)
- Interested jobs tracked and revisited


## ✅ Completed

### v1.0 — Gmail Job Extraction CLI
- [x] Extract job postings from Gmail (Naukri, LinkedIn, Indeed)
- [x] Parse job details (role, company, location, experience)
- [x] Store in JSON file
- [x] Deduplication by message ID

### v1.1 — Database Migration
- [x] Replace JSON file storage with SQLite
- [x] Atomic writes + transactions
- [x] Upsert on message_id to prevent duplicates
- [x] Add indexes for common queries (company, interested flag)
- [x] Export-to-JSON for portability
- [x] Schema versioning for future evolution


## 🔄 In Progress / Next

### v1.2 — Local Web Interface (Phase 1)
**Goal:** See and interact with your extracted jobs locally  
**Effort:** 4–6 hours  
**Status:** Design complete; ready to build

#### Phase 1a: Backend API
- [ ] Flask server + SQLite query layer
- [ ] `GET /api/jobs` with filters (company, interested)
- [ ] `GET /api/stats` for aggregate data
- [ ] `POST /api/jobs/<id>/interested` with validation & error handling
- [ ] CSRF-ready design (decorator pattern for Phase 2)

#### Phase 1b: Frontend UI
- [ ] HTML template (responsive table layout)
- [ ] Vanilla JavaScript client (`fetch()` API)
- [ ] Search/filter by company (with debounce)
- [ ] Mark-as-interested toggle (optimistic UI updates)
- [ ] Stats display (total jobs, unique companies)
- [ ] Error handling & network resilience

#### Success Criteria
- Flask server runs on `localhost:5000`
- All jobs visible and filterable
- Interested toggles work and persist
- Load time <2s for 5k jobs

## 📋 Planned

### v1.3 — Cloud Deployment (Phase 2)
**Goal:** Access your job dashboard from anywhere, always-on  
**Effort:** 3–4 hours  
**Prerequisites:** Phase 1 complete and validated

#### Phase 2a: Infrastructure
- [ ] Create Turso database (SQLite-as-a-service)
- [ ] Export local `jobs.db` to Turso (one-time migration)
- [ ] Set up `.env` for Turso credentials
- [ ] Test API against cloud DB

#### Phase 2b: Deployment
- [ ] Convert Flask app to Vercel Serverless Functions
- [ ] Deploy frontend to Vercel (static hosting)
- [ ] Configure CORS for cloud-to-cloud calls
- [ ] Test end-to-end from public URL

#### Phase 2c: Sync & Fallback
- [ ] Decide: Extractor writes to Turso directly OR local DB + cron sync
- [ ] Document sync strategy
- [ ] Keep local DB as offline fallback

#### Success Criteria
- Public URL works from any device
- Same features as Phase 1 (filter, toggle, stats)
- No manual intervention after initial setup

## 🚀 Future Enhancements

### v1.4 — CSRF & Security Hardening
- Add CSRF token validation (Phase 2 architecture ready)
- Rate limiting on API endpoints
- Audit logging for interested toggles
- Schema migration tools for breaking changes


## Design Documents

| Doc | Purpose |
|-----|---------|
| [WEBAPP_ARCHITECTURE.md](./WEBAPP_ARCHITECTURE.md) | Server contract, validation, security design, Phase 1 & 2 comparison |
| [FRONTEND_API_CLIENT.md](./FRONTEND_API_CLIENT.md) | Frontend implementation patterns, fetch() examples, error handling |
| [prd.md](./prd.md) | Product vision, tradeoffs, risks for database + webapp |



## Key Decisions & Tradeoffs

### Why Two Phases?
- **Phase 1 validates usefulness** — Is a web interface actually useful? Does it change how you find jobs?
- **Fast feedback loop** — 4–6 hours to working local app vs. 7–10 hours for full cloud setup
- **Phase 2 is optional** — If local satisfies you, skip cloud deployment entirely

### Why Vanilla JS (no htmx)?
- Zero dependencies → smaller, faster, easier to debug
- `fetch()` API is modern standard → no learning curve
- Complexity is low → JS suffices without frameworks

### Why Validated Mutations?
- Prevents bugs (orphaned updates, race conditions)
- Secure by structure (validation before mutation)
- Phase 2 auth added as decorator → no logic refactoring

### Why SQLite → Turso (not PostgreSQL)?
- SQLite is portable → works locally and in cloud
- Turso free tier sufficient for personal use
- Zero operations overhead (managed service)
- Costs scale only if you actually need it

---

## Open Questions / Decisions Pending

1. **Phase 2 sync strategy:** Extractor → Turso directly, or local DB + cron?
   - Decision deferred to Phase 2 spike
   
2. **Pagination threshold:** Add pagination at 5k jobs? 10k? Never?
   - Decision deferred until dataset grows or performance degrades

3. **Authentication in Phase 2:** OAuth2 or simple API key?
   - Depends on sharing needs; currently not planned

---

## Metrics for Success

### Phase 1 MVP Success
- App launches without errors
- Can see all extracted jobs
- Can toggle interested flag
- Stats display correctly
- < 2 second load time for current dataset

### Phase 2 Success
- Same features accessible from public URL
- Works across devices (phone, laptop, etc.)
- Data stays in sync between local extractor and cloud DB
- No manual sync intervention needed
