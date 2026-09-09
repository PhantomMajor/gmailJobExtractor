# 📧 Gmail Job Extractor

I was overwhelmed by the number of job board notification emails coming in my inbox. Too many unheard of companies (startups, etc.) and too many senders (LinkedIn, Hireist, Naurki, etc.).

My biggest pain was that I did not know which of these companies was I interested in, and should network with more. Now that I write this, I realise that an easier workflow would be laissez-faire, where I just go through my email (with the label= JobSearch), individually read about companies, and start 1) applying, 2) networking with people in them.

However, considering the large amount of noise in these emails, I decided to just write this basic scrapper in python.

## ✨ What it does

```
┌─────────────────┐
│   Gmail Inbox   │  (With JobSearch label)
└────────┬────────┘
         │
         ↓
┌──────────────────────────┐
│  gmail_job_extractor.py  │  Identifies sender & extracts jobs
└────────┬─────────────────┘
         │
         ├─→ Finds: Role, Company, Location, Experience
         │
         ↓
    ┌────────────────────────────────────┐
    │  Database (DB_TYPE env var)        │
    ├────────────────────────────────────┤
    │  ├─ jobs.db (SQLite) — local       │
    │  └─ Turso cloud — production       │
    └────────────────────────────────────┘
         ↑
         │
         └─ Emails auto-labeled "delete"
```

### Supported senders (for now)
- ✅ LinkedIn Job Alerts
- ✅ Hirist
- ✅ Naukri

### Edge cases:
- Unknown sender? Skipped, label stays clean (you'll spot it manually)
- Parser didn't match anything? Skipped, label untouched (template may have changed—time to adjust)

## 📸 See it in action

|**Before**|**After**|
|---|---|
|54 emails in my inbox waiting to be processed ![Gmail inbox with 54 job emails](screenshots/gmail_processed.jpeg)|Structured job data in `jobs.db`, ready to use. ![Extracted jobs in VSCode](screenshots/extracted_jobs_output.jpeg)|


## 🚀 Quick Start

### Prerequisites
Before you start, make sure you have:
- **Python 3.7+** installed. Check by opening Terminal and running `python3 --version`. If you don't have it, [install Python here](https://www.python.org/downloads/).
- **Git** installed (to download this repo). Check with `git --version`. If you don't have it, [install Git here](https://git-scm.com/downloads).
- A **Gmail account** with job notification emails you want to organize.

### 1. Download this repo
Open Terminal and run:
```bash
git clone https://github.com/PhantomMajor/gmailJobExtractor.git
cd gmailJobExtractor
```

**Don't have git?** Download the ZIP instead: go to https://github.com/PhantomMajor/gmailJobExtractor → click the green "Code" button → "Download ZIP" → extract it → open Terminal in that folder.

### 2. Create a virtual environment (optional but recommended)
This keeps your Python setup clean and separate from your system:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
You'll see `(.venv)` appear in Terminal, meaning you're in the isolated environment. Run `source .venv/bin/activate` this every time you open a new Terminal window to work on this project.

example- ![venv terminal](screenshots/image.png)

### 3. Install dependencies
This downloads and installs the Python libraries this script needs:
```bash
pip install -r requirements.txt
```

### 4. (ONE TIME) Set up Gmail API access
This is a one-time setup so the script can securely read your Gmail.

**Step A:** Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with your Gmail account.

**Step B:** Create a new project (top-left dropdown → "New Project" → pick a name like "JobExtractor").

**Step C:** Enable the Gmail API:
   - Left sidebar → "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click it, then click "Enable"

**Step D:** Create credentials (this is how the script proves it's allowed to access Gmail):
   - Left sidebar → "APIs & Services" → "Credentials"
   - Click "+ Create Credentials" → "OAuth client ID"
   - If it asks to configure the consent screen first, click "Configure consent screen"
     - Choose "External"
     - Fill in the app name (`JobExtractor`)
     - Add your Gmail as a test user
     - Save and continue (you don't need a review)
   - Back to creating credentials: Choose "Desktop app" as the application type
   - Click "Create"
   - A popup appears → Click "Download" and save the JSON file

**Step E:** Save the credentials file:
   - Rename the downloaded file to `credentials.json`
   - Move it into your `gmailJobExtractor` folder (the one you cloned in Step 1)

### 5. Run the script
```bash
python src/gmailJobExtractor.py
```
First run will open your browser asking you to approve access—sign in with your Gmail. After approval, the script:
- Creates `token.json` (so you won't need to log in again)
- Reads emails labeled `JobSearch` from your Gmail
- Extracts job info and saves it to `jobs.db` (a database file)
- Labels those emails as `delete` so you can review & delete them in bulk

Don't have a `JobSearch` label yet? Create one in Gmail (left sidebar → "Create new label" → type "JobSearch"). Then move your job notification emails there.

### 6. Optional: Use flags for more control

#### Available Flags

| Flag | Purpose | Example |
|------|---------|---------|
| `--debug` | Print extracted job records before saving to DB | `python src/gmailJobExtractor.py --debug` |
| `--export FILE` | Export all jobs from DB to JSON (skips Gmail fetch) | `python src/gmailJobExtractor.py --export jobs.json` |
| `--db TYPE` | Override `DB_TYPE` env var (useful for one-off runs) | `python src/gmailJobExtractor.py --db turso` |

#### Examples

**Debug mode** — see exactly what was extracted before it's saved:
```bash
python src/gmailJobExtractor.py --debug
```
Output shows all parsed jobs with their fields (role, company, location, experience) before they hit the database.

**Export to JSON** — dump all jobs from the database to a file (no Gmail fetch):
```bash
python src/gmailJobExtractor.py --export jobs.json
```
Useful for backups, sharing, or data analysis. Creates a JSON file with all extracted jobs.

**Override database backend** — use Turso for a single run even if `DB_TYPE=sqlite`:
```bash
python src/gmailJobExtractor.py --db turso
```
Helpful for testing Turso without permanently changing `DB_TYPE` env var.

**Combine flags** — extract with Turso and show debug output:
```bash
python src/gmailJobExtractor.py --db turso --debug
```

---

## 🗄️ Database Configuration

By default, jobs are stored in a local SQLite database (`jobs.db`). You can also use Turso cloud for production deployments.

### Local SQLite (Default)
**Best for:** Local development, single-user setup

No extra setup needed. Jobs are stored in `jobs.db`:
```bash
python src/gmailJobExtractor.py
python run.py
```

### Turso Cloud Database
**Best for:** Production, multi-device access, cloud deployments (e.g., Vercel)

#### Prerequisites
1. Sign up for [Turso](https://turso.tech) (free tier available)
2. Create a database and get your credentials:
   - `TURSO_DATABASE_URL` — your database URL
   - `TURSO_AUTH_TOKEN` — your auth token

#### Using Turso
**Local development:**
```bash
export DB_TYPE=turso
export TURSO_DATABASE_URL=<your-url>
export TURSO_AUTH_TOKEN=<your-token>

python src/gmailJobExtractor.py
python run.py
```

**Vercel deployment:**
Add these to your environment variables in Vercel project settings:
```
DB_TYPE=turso
TURSO_DATABASE_URL=<your-url>
TURSO_AUTH_TOKEN=<your-token>
```

---

## 💼 Job Dashboard - Web Interface

Once you have jobs extracted, you can browse them in an interactive web dashboard. The dashboard works with both SQLite and Turso backends (no code changes needed).

### Running the Dashboard

#### 1. Start the Flask server

**Local SQLite (default):**
```bash
python run.py
```

**With Turso (using flag):**
```bash
export TURSO_DATABASE_URL=<your-url>
export TURSO_AUTH_TOKEN=<your-token>
python run.py --db turso
```

**With Turso (using env var):**
```bash
export DB_TYPE=turso
export TURSO_DATABASE_URL=<your-url>
export TURSO_AUTH_TOKEN=<your-token>
python run.py
```

The server will start on `http://localhost:5000`. Open your browser and navigate there to see the dashboard.

#### 2. Stop the server
Press `Ctrl+C` in the terminal

### Features

- **View all jobs** extracted from Gmail in a searchable table
- **Filter by company** with live search (debounced)
- **Three-state job evaluation:**
  - **? Not Evaluated** (gray) — initial state, untouched by user
  - **✓ Interested** (green) — you're interested in this job
  - **✗ Not Interested** (red) — you explicitly rejected this job
  - *Once you click, the job cycles between interested/not interested (never returns to unevaluated)*
- **View statistics** (total jobs, unique companies, marked interested)
- **Responsive design** that works on desktop and mobile

### How it works

- **Server**: Flask (Python) web server
- **Database**: SQLite (local) or Turso (cloud) — configured via `DB_TYPE` env var
- **Frontend**: Vanilla HTML + JavaScript (zero dependencies, no build step)
- **API**: Simple REST endpoints (GET jobs, GET stats, POST to toggle interested)

### Troubleshooting

**Port 5000 already in use?**
```bash
# Kill the process using port 5000
lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

**Database locked?**
SQLite uses file-level locking. Make sure only one Flask server is running.

**No jobs showing?**
Run the extractor first:
```bash
python src/gmailJobExtractor.py
```

---

## ☁️ Deploying to Vercel (Cloud Hosting)

Once you've set up Turso (above), you can deploy the dashboard as a single, always-on Vercel Python Function — it serves the API, the HTML page, and the static JS all from `src/app.py`, so there's no separate frontend hosting step and no CORS to configure.

### 1. Install the Vercel CLI and log in
```bash
npx vercel login
```

### 2. Link this folder to a Vercel project
```bash
npx vercel link
```
Answer the prompts (scope, project name, directory = `./`). This creates a local `.vercel/` folder (gitignored) and a new project on vercel.com — no deploy happens yet.

### 3. Add your Turso credentials as Production environment variables
```bash
npx vercel env add DB_TYPE production        # Plain Text — value: turso
npx vercel env add TURSO_DATABASE_URL production   # Secret — paste from your .env
npx vercel env add TURSO_AUTH_TOKEN production     # Secret — paste from your .env
```
Never put these values in `vercel.json` or any committed file — `vercel.json` is public (it's in this repo), so secrets belong only in Vercel's encrypted env var store.

### 4. Deploy
```bash
npx vercel --prod
```
Vercel auto-detects `src/app.py` as the Flask entrypoint and routes every request to it — no `rewrites` or routing config needed in `vercel.json`.

### 5. Verify
Open the printed production URL — the dashboard should load with your real Turso data. Toggle a job's interested state and refresh to confirm it persisted.

### Access control
By default, new Vercel projects created under a team may have **Deployment Protection (SSO)** enabled — only people logged into that Vercel team can load the URL at all. Since the dashboard itself has no login of its own, this is worth keeping on for a personal deployment (otherwise anyone with the link could view/toggle your jobs). If you want it fully public instead, disable Deployment Protection in Project Settings — just know that removes all access control.

---

## 🗺 Roadmap (v1.* planned)

Detailed roadmap present [here](docs/ROADMAP.md).

## 🤝 Contributing
This is v1, and there's a lot of room to grow. Here's how you can help:

### Ideas
- Add support for new job email senders (Indeed, Wellfound, etc.)
- Improve parsing accuracy or add new fields (e.g., salary, job type)
- Test edge cases and report bugs
- Share your roadmap ideas

### Code contributions
1. **Fork & branch** (`feature/new-sender`, `fix/parser-bug`, etc.)
2. **Test your changes** (run the script, verify `extracted_jobs.json`)
3. **Open a PR** with a description of what you changed and why

No experience needed—if you're fixing something that bothered you, that's a great PR.

## 📝 License

MIT License - See [LICENSE](LICENSE) for details. Yours to use, modify, and share. Build on it!

**Questions?** [Open an issue](../../issues). **Found a bug?** Same place.  

**Built something cool with this?** Let me know—I'd love to see it!
