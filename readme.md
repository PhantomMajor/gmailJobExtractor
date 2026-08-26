# Gmail JobSearch Extractor

## Setup

1. **Google Cloud project**
   - Go to console.cloud.google.com, create (or pick) a project.
   - Enable the **Gmail API** (APIs & Services -> Library).
   - Configure the OAuth consent screen as "External" + "Testing", add your
     own Gmail address as a test user (no Google review needed for personal use).
   - Create credentials -> OAuth client ID -> Application type: **Desktop app**.
   - Download the JSON, save it as `credentials.json` next to the script.

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Run**
   ```
   python gmail_job_extractor.py
   ```
   First run opens a browser to approve access; approve with the same
   account that has the `JobSearch` label. This creates `token.json`, which
   is reused (and auto-refreshed) on later runs — no repeated browser login.

## What it does

- Finds all emails with the Gmail label `JobSearch` that don't yet have the
  `ReadyToDelete` label.
- Identifies the sender (LinkedIn Job Alerts / Hirist) and extracts every
  job listing in the email body: Role, Company, and (if present) Location
  and Years of Experience — all as strings.
- Appends results to `extracted_jobs.json`.
- Adds the `ReadyToDelete` label to any email it successfully extracted
  from. **Nothing is deleted** — that's a manual/phase-2 step.

## Edge case behavior

- Sender not LinkedIn/Hirist -> skipped, label untouched.
- Sender recognized but nothing matched the parsing pattern (e.g. the
  template changed) -> skipped, label untouched, so you can spot it in your
  `JobSearch` label and adjust the parser or review manually.

## Extending to a new sender

Add a `parse_<sender>(text, subject)` function returning a list of
`{"role", "company", "location", "experience"}` dicts, and register its
sender domain in the `PARSERS` dict.