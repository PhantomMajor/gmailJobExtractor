# Useful SQLite Queries for Job Extraction DB

Quick reference for exploring and managing your job database.

## Connection

```bash
# Connect to database
sqlite3 jobs.db

# Pretty formatting inside sqlite3
.headers on
.mode column
```

---

## Exploration Queries

### View Schema
```sql
-- Show all tables
.tables

-- Show jobs table structure
.schema jobs

-- Show indexes
.schema jobs --indent
```

### Count & Overview
```sql
-- Total jobs in database
SELECT COUNT(*) as total_jobs FROM jobs;

-- Total jobs by sender
SELECT sender, COUNT(*) as count FROM jobs GROUP BY sender ORDER BY count DESC;

-- Total jobs by company
SELECT company, COUNT(*) as count FROM jobs GROUP BY company ORDER BY count DESC;

-- Jobs by location
SELECT location, COUNT(*) as count FROM jobs WHERE location != '' GROUP BY location ORDER BY count DESC;
```

### View All Jobs
```sql
-- Show all jobs (basic columns)
SELECT role, company, location FROM jobs;

-- Show all jobs (detailed)
SELECT id, role, company, location, sender, date FROM jobs ORDER BY extracted_at DESC;

-- Show with interested status
SELECT role, company, interested FROM jobs;
```

---

## Filtering Queries

### By Interest Status
```sql
-- Jobs you marked as interested (1 = yes)
SELECT role, company, location FROM jobs WHERE interested = 1;

-- Jobs you marked as not interested (0 = no)
SELECT role, company, location FROM jobs WHERE interested = 0;

-- Jobs you haven't decided on yet (NULL = not reviewed)
SELECT role, company, location FROM jobs WHERE interested IS NULL;
```

### By Company
```sql
-- Find jobs at a specific company
SELECT role FROM jobs WHERE company LIKE '%Microsoft%';

-- Find all jobs from a specific sender
SELECT role, company FROM jobs WHERE sender LIKE '%linkedin%';
```

### By Role Keywords
```sql
-- Find all manager roles
SELECT role, company FROM jobs WHERE role LIKE '%Manager%';

-- Find all senior roles
SELECT role, company FROM jobs WHERE role LIKE '%Senior%';

-- Find all roles containing a keyword (case-insensitive)
SELECT role, company FROM jobs WHERE LOWER(role) LIKE '%product%';
```

### By Date
```sql
-- Jobs extracted in the last 7 days
SELECT role, company, extracted_at FROM jobs 
WHERE extracted_at >= datetime('now', '-7 days')
ORDER BY extracted_at DESC;

-- Jobs from a specific email date
SELECT role, company, date FROM jobs WHERE date LIKE '%Aug 2026%';
```

---

## Update Queries

### Mark Interest
```sql
-- Mark specific job as interested
UPDATE jobs SET interested = 1 WHERE id = 1;

-- Mark multiple jobs as interested (by company)
UPDATE jobs SET interested = 1 WHERE company = 'Google';

-- Mark job as not interested
UPDATE jobs SET interested = 0 WHERE id = 2;

-- Reset a job to "not reviewed" (NULL)
UPDATE jobs SET interested = NULL WHERE id = 3;
```

### Update Other Fields
```sql
-- Add metadata (JSON) to a job
UPDATE jobs SET metadata = '{"salary": "100-120k", "job_type": "full-time"}' 
WHERE id = 1;

-- Update a job's location
UPDATE jobs SET location = 'San Francisco, CA' WHERE id = 5;
```

---

## Delete Queries

### Remove Jobs
```sql
-- Delete a specific job by ID
DELETE FROM jobs WHERE id = 1;

-- Delete all jobs from a company
DELETE FROM jobs WHERE company = 'OldCompany';

-- Delete jobs you marked as not interested
DELETE FROM jobs WHERE interested = 0;

-- Delete all jobs (WARNING: no undo!)
DELETE FROM jobs;
```

### Cleanup Malformed Data
```sql
-- ===== OPTION 1: Clear malformed location fields (SAFE - RECOMMENDED) =====

-- Clear ratings (e.g., "3.8", "4.1", "5.0") from location field
UPDATE jobs
SET location = ''
WHERE location REGEXP '^\d+\.\d+$';

-- Clear durations (e.g., "6-7 Months") from location field
UPDATE jobs
SET location = ''
WHERE location REGEXP '^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)' COLLATE NOCASE;

-- Clear boilerplate text (e.g., "Hi Udayaditya,", "Get App") from location field
UPDATE jobs
SET location = ''
WHERE LOWER(location) IN ('hi udayaditya,', 'get app', 'not interested')
   OR LOWER(location) LIKE 'hi %'
   OR LOWER(location) LIKE 'hello %'
   OR LOWER(location) LIKE 'dear %';

-- ===== OPTION 2: Delete entire malformed job entries (DESTRUCTIVE) =====

-- View jobs that would be deleted (preview before deleting)
SELECT id, role, company, location, sender
FROM jobs
WHERE location REGEXP '^\d+\.\d+$'
   OR location REGEXP '^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)'
   OR LOWER(location) IN ('hi udayaditya,', 'get app');

-- Delete entire job records with malformed locations
DELETE FROM jobs
WHERE location REGEXP '^\d+\.\d+$'
   OR location REGEXP '^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)'
   OR LOWER(location) IN ('hi udayaditya,', 'get app', 'not interested')
   OR LOWER(location) LIKE 'hi %'
   OR LOWER(location) LIKE 'hello %'
   OR LOWER(location) LIKE 'dear %';

-- ===== Remove duplicate entries (if any) =====
DELETE FROM jobs WHERE id NOT IN (
  SELECT MIN(id) FROM jobs GROUP BY message_id
);
```

### Analyze Data Quality
```sql
-- Find all malformed locations
SELECT location, COUNT(*) as count
FROM jobs
WHERE location IS NOT NULL
  AND location != ''
  AND (location REGEXP '^\d+\.\d+$'
       OR location REGEXP '^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)'
       OR LOWER(location) IN ('hi udayaditya,', 'get app', 'not interested'))
GROUP BY location
ORDER BY count DESC;

-- Malformed entries by source (Naukri, Hirist, LinkedIn, etc.)
SELECT sender, COUNT(*) as malformed_count
FROM jobs
WHERE location IS NOT NULL
  AND location != ''
  AND (location REGEXP '^\d+\.\d+$'
       OR location REGEXP '^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)')
GROUP BY sender
ORDER BY malformed_count DESC;

-- Data quality report
SELECT
  COUNT(*) as total_jobs,
  COUNT(CASE WHEN location = '' OR location IS NULL THEN 1 END) as empty_locations,
  COUNT(CASE WHEN location != '' THEN 1 END) as filled_locations,
  ROUND(COUNT(CASE WHEN location != '' THEN 1 END) * 100.0 / COUNT(*), 1) as fill_rate
FROM jobs;
```

---

## Export & Backup

### CSV Export
```bash
# Export to CSV
sqlite3 jobs.db << 'EOF'
.mode csv
.output jobs_export.csv
SELECT role, company, location, interested FROM jobs;
.output stdout
EOF
```

### Backup & Restore
```bash
# Backup database
cp jobs.db jobs.db.backup

# Backup with timestamp
cp jobs.db "jobs.db.backup.$(date +%Y%m%d_%H%M%S)"

# List all backups
ls -lh jobs.db.backup*

# Restore from backup (WARNING: overwrites current database!)
cp jobs.db.backup jobs.db
```

### SQL Backup (Create & Restore)
```sql
-- CREATE backup table before cleanup
CREATE TABLE jobs_backup AS SELECT * FROM jobs;

-- Verify backup was created
SELECT COUNT(*) as backup_count FROM jobs_backup;

-- RESTORE from backup (delete current, copy back)
DELETE FROM jobs;
INSERT INTO jobs SELECT * FROM jobs_backup;

-- Clean up backup table when done
DROP TABLE jobs_backup;
```

### Use Python Export
```bash
# Export to JSON using the built-in function
python src/gmailJobExtractor.py --export jobs.json
```

---

## Statistics & Insights

### Count by Status
```sql
-- Jobs by interest status (with counts)
SELECT 
  CASE 
    WHEN interested = 1 THEN 'Interested'
    WHEN interested = 0 THEN 'Not Interested'
    ELSE 'Not Reviewed'
  END as status,
  COUNT(*) as count
FROM jobs
GROUP BY interested
ORDER BY count DESC;
```

### Most Common Companies
```sql
-- Top companies with most job postings
SELECT company, COUNT(*) as job_count FROM jobs 
GROUP BY company 
ORDER BY job_count DESC 
LIMIT 10;
```

### Senders Distribution
```sql
-- Jobs by sender
SELECT sender, COUNT(*) as count FROM jobs 
GROUP BY sender 
ORDER BY count DESC;
```

### Jobs Without Location
```sql
-- Find jobs missing location info
SELECT id, role, company FROM jobs WHERE location = '' OR location IS NULL;
```

---

## One-Liners

```bash
# Count total jobs
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs;"

# See column names
sqlite3 jobs.db "PRAGMA table_info(jobs);"

# Check if database exists and is readable
sqlite3 jobs.db ".tables"

# Quick interested count
sqlite3 jobs.db "SELECT interested, COUNT(*) FROM jobs GROUP BY interested;"

# Find oldest/newest jobs
sqlite3 jobs.db "SELECT role, extracted_at FROM jobs ORDER BY extracted_at DESC LIMIT 1;"
sqlite3 jobs.db "SELECT role, extracted_at FROM jobs ORDER BY extracted_at ASC LIMIT 1;"
```

---

## Tips

1. **Always backup before bulk changes:**
   ```bash
   cp jobs.db jobs.db.backup
   ```

2. **Use .headers and .mode for readability:**
   ```bash
   sqlite3 jobs.db -header -column "SELECT * FROM jobs LIMIT 5;"
   ```

3. **Test with LIMIT first:**
   ```sql
   -- Test before updating all
   SELECT * FROM jobs WHERE interested IS NULL LIMIT 5;
   -- Then update
   UPDATE jobs SET interested = 1 WHERE interested IS NULL;
   ```

4. **View transaction history:**
   ```sql
   -- See when each job was added/updated
   SELECT role, extracted_at, updated_at FROM jobs ORDER BY updated_at DESC;
   ```

5. **Use LIKE for partial matches:**
   ```sql
   -- Case-insensitive search
   SELECT * FROM jobs WHERE LOWER(role) LIKE '%manager%';
   ```
