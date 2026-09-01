# Frontend API Client Contract

This document defines how the frontend (`static/app.js`) consumes the backend API. See [WEBAPP_ARCHITECTURE.md](./WEBAPP_ARCHITECTURE.md) for server-side contract and validation logic.

---

## API Endpoints Summary

| Method | Endpoint | Purpose | Response |
|--------|----------|---------|----------|
| GET | `/api/jobs` | Fetch all jobs | `{ jobs: [...] }` |
| GET | `/api/jobs?company=X` | Filter by company | `{ jobs: [...] }` |
| GET | `/api/jobs?interested=1` | Show interested only | `{ jobs: [...] }` |
| GET | `/api/stats` | Aggregate stats | `{ total_jobs: int, unique_companies: int, ... }` |
| POST | `/api/jobs/<id>/interested` | Toggle interested flag | `{ id: int, interested: bool }` |

---

## Client Patterns

### 1. **Fetching Jobs List**

```javascript
async function loadJobs(filters = {}) {
  try {
    const params = new URLSearchParams(filters); // e.g., { company: 'Google', interested: 1 }
    const response = await fetch(`/api/jobs?${params}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    renderJobsTable(data.jobs);
  } catch (error) {
    showError('Failed to load jobs');
    console.error(error);
  }
}

// Usage:
loadJobs(); // Load all
loadJobs({ company: 'Amazon' }); // Filter by company
loadJobs({ interested: 1 }); // Only interested jobs
```

### 2. **Toggling Interested Flag (with optimistic update)**

```javascript
async function toggleInterested(jobId) {
  const jobRow = document.querySelector(`[data-job-id="${jobId}"]`);
  const button = jobRow.querySelector('.interested-btn');
  const currentState = button.classList.contains('interested');
  
  // Optimistic update: toggle UI immediately
  button.classList.toggle('interested');
  button.textContent = currentState ? 'Mark Interested' : 'Unmark';
  button.disabled = true;
  
  try {
    const response = await fetch(`/api/jobs/${jobId}/interested`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
      // Phase 2: Add CSRF token header here
      // 'X-CSRF-Token': getCsrfToken()
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    // Confirm server state matches optimistic update
    button.classList.toggle('interested', data.interested);
    button.textContent = data.interested ? 'Unmark' : 'Mark Interested';
    
  } catch (error) {
    // Revert optimistic update on error
    button.classList.toggle('interested');
    button.textContent = currentState ? 'Unmark' : 'Mark Interested';
    showError(`Failed to update job ${jobId}`);
    console.error(error);
  } finally {
    button.disabled = false;
  }
}
```

### 3. **Loading Stats**

```javascript
async function loadStats() {
  try {
    const response = await fetch('/api/stats');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const stats = await response.json();
    document.getElementById('total-jobs').textContent = stats.total_jobs;
    document.getElementById('unique-companies').textContent = stats.unique_companies;
    // ... update other stat displays
  } catch (error) {
    console.error('Failed to load stats', error);
  }
}
```

### 4. **Filtering with Search Box**

```javascript
const searchInput = document.querySelector('#company-filter');
let filterTimeout;

searchInput.addEventListener('input', (e) => {
  clearTimeout(filterTimeout);
  filterTimeout = setTimeout(() => {
    const company = e.target.value.trim();
    if (company.length === 0) {
      loadJobs(); // Reset to all jobs
    } else {
      loadJobs({ company });
    }
  }, 300); // Debounce: wait 300ms after user stops typing
});
```

---

## Error Handling

All fetch calls should handle:
- **Network errors:** No connection, timeout
- **HTTP errors:** 400 (bad ID format), 404 (job not found), 500 (server error)
- **JSON parse errors:** Invalid response format

```javascript
async function safeApiCall(url, options = {}) {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      // Server returned error status
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(error.error || `HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    // Distinguish network errors from API errors
    if (error instanceof TypeError) {
      console.error('Network error:', error.message);
      showError('Network connection failed');
    } else {
      console.error('API error:', error.message);
      showError(`Error: ${error.message}`);
    }
    throw error;
  }
}
```

---

## State Management (Phase 1)

**Keep it simple—no external state library needed:**
- **Jobs list:** Stored in DOM (render from API response each time)
- **Filters:** Stored in query params or input values
- **Interested toggles:** Immediate DOM update + server confirmation

If the dataset grows >5k jobs and performance degrades, consider:
- Caching the jobs list in memory
- Debouncing filter requests
- Pagination (server-side: add `?limit=50&offset=0`)

---

## Phase 2: CSRF Protection

When deployed to cloud (Vercel + Turso), add CSRF token validation:

```javascript
// Get CSRF token from <meta> tag or cookie
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content 
    || document.cookie.split('; ').find(row => row.startsWith('csrf_token='))?.split('=')[1];
}

// Add to all POST requests
const response = await fetch(`/api/jobs/${jobId}/interested`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCsrfToken()
  }
});
```

---

## Response Format Reference

### `GET /api/jobs` / `GET /api/jobs?...`
```json
{
  "jobs": [
    {
      "id": 1,
      "message_id": "msg_abc123",
      "sender": "naukri@naukri.com",
      "date": "2026-08-15",
      "role": "Senior Software Engineer",
      "company": "Google",
      "location": "Remote",
      "experience": "5+ years",
      "interested": null
    },
    ...
  ]
}
```

### `GET /api/stats`
```json
{
  "total_jobs": 342,
  "unique_companies": 24,
  "interested_count": 12,
  "top_companies": ["Google", "Amazon", "Microsoft"]
}
```

### `POST /api/jobs/<id>/interested`
```json
{
  "id": 1,
  "interested": true
}
```

### Error Response (all endpoints)
```json
{
  "error": "Job not found"
}
```

---

## Testing Checklist

- [ ] Load jobs without filters
- [ ] Filter by company (partial match works)
- [ ] Toggle interested flag (optimistic update, then confirm)
- [ ] Revert toggle on network error
- [ ] Display stats after page load
- [ ] Debounce search box (no request spam)
- [ ] Handle 404 when toggling non-existent job
- [ ] Handle network timeout gracefully
