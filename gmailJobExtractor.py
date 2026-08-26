#!/usr/bin/env python3
"""
Gmail JobSearch Extractor
--------------------------
Extracts structured job data (Role, Company, Location, Experience) from
JobSearch-labeled emails (LinkedIn Job Alerts, Hirist.tech) and marks
successfully-processed emails with a "delete" Gmail label.

Setup:
1. In Google Cloud Console: create/select a project, enable the "Gmail API",
   create an OAuth Client ID of type "Desktop app", download the JSON and
   save it next to this script as credentials.json.
2. pip install -r requirements.txt
3. python gmail_job_extractor.py
   First run opens a browser for OAuth consent; token.json is cached after
   that, so subsequent runs don't need a browser.

Idempotency: emails that already carry the delete label are excluded
from the next run's query, so it's safe to re-run this repeatedly (e.g. as a
cron job or later as a Claude routine) without re-processing or duplicating
JSON entries.

Behavior on edge cases (see README for rationale):
- Sender not recognized (not LinkedIn / Hirist)  -> skipped, label untouched.
- Sender recognized but nothing could be parsed  -> skipped, label untouched,
  so you can review it manually instead of silently losing data.
"""

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

SOURCE_LABEL = "JobSearch"
DONE_LABEL = "delete"

OUTPUT_FILE = "extracted_jobs.json"

EXPERIENCE_RE = re.compile(r"\d+\s*[-–to]+\s*\d+\s*\+?\s*(?:yrs?|years?)", re.I)


# ---------------------------------------------------------------- Auth ----

def get_service():
    '''
    Authenticates and initializes a "Google Gmail API service client"
    (i.e., a specific Python object to talk directly to Gmail's servers)
    '''
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                sys.exit(f"Missing {CREDENTIALS_FILE}. See README for setup.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_or_create_label(service: Any, name):
    '''
    retrieves the ID of an existing Gmail label with the given "name" (case-insensitive);
    if the label does not exist, it creates a new label with that name and returns its ID
    '''
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for l in labels:
        if l["name"].lower() == name.lower():
            return l["id"]
    label = service.users().labels().create(
        userId="me",
        body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return label["id"]


# ------------------------------------------------------------- Fetching ----

def list_message_ids_for_label(service: Any, label_id):
    ids, page_token = set(), None
    while True:
        resp = service.users().messages().list(
            userId="me", labelIds=[label_id], pageToken=page_token
        ).execute()
        ids.update(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def list_unprocessed_messages(service: Any, source_label_id, done_label_id):
    to_process = list_message_ids_for_label(service, source_label_id)
    already_done = list_message_ids_for_label(service, done_label_id)
    return to_process - already_done


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def decode_part(data):
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")


def extract_body(payload):
    """Best-effort plain text body: prefer text/plain, else strip tags from
    text/html while preserving line breaks (job listings are line-oriented)."""
    plain_result, html_result = None, None
    stack = [payload]
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        if mime == "text/plain" and body.get("data") and not plain_result:
            plain_result = decode_part(body["data"])
        elif mime == "text/html" and body.get("data") and not html_result:
            html_result = decode_part(body["data"])
        stack.extend(part.get("parts", []))

    if plain_result:
        return plain_result
    if html_result:
        soup = BeautifulSoup(html_result, "html.parser")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        text = soup.get_text("\n")
        lines = [l.strip() for l in text.splitlines()]
        return "\n".join(l for l in lines if l)
    return ""


# -------------------------------------------------------------- Parsing ----

MAX_FIELD_LEN = 80  # real role/company/location text is short; URLs and
                     # footer boilerplate ("Manage your job alerts: https://...")
                     # are not, so this doubles as a noise filter.


def _looks_like_noise(s):
    s_lower = s.lower()
    return (
        "http://" in s_lower
        or "https://" in s_lower
        or len(s) > MAX_FIELD_LEN
        or s_lower.startswith(("unsubscribe", "manage your job alert", "help", "view job", "see all jobs"))
    )


def parse_job_blocks(text):
    """Scans lines for a 'Company · [Experience ·] Location' detail line
    (the '·' separated pattern seen in both LinkedIn and Hirist bodies) and
    takes the preceding non-empty line as the Role.

    LinkedIn's own footer ("Manage your job alerts · Unsubscribe · Help")
    uses the same '·' separator, so every candidate line/part is screened
    with _looks_like_noise() to reject links and boilerplate before being
    accepted as a job."""

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    jobs = []
    for i, line in enumerate(lines):
        if "·" not in line or _looks_like_noise(line):
            continue
        parts = [p.strip() for p in line.split("·") if p.strip()]
        if not (2 <= len(parts) <= 3) or any(_looks_like_noise(p) for p in parts):
            continue
        role = lines[i - 1] if i > 0 else ""
        if not role or "·" in role or _looks_like_noise(role):
            continue
        company = parts[0]
        experience, location = "", ""
        for p in parts[1:]:
            if EXPERIENCE_RE.search(p):
                experience = p
            else:
                location = p
        jobs.append({"role": role, "company": company, "location": location, "experience": experience})
    return jobs


def parse_linkedin(text, subject):
    jobs = parse_job_blocks(text)
    if not jobs and " at " in subject:
        role, company = subject.split(" at ", 1)
        jobs = [{"role": role.strip(), "company": company.strip(), "location": "", "experience": ""}]
    return jobs


def parse_hirist(text, subject):
    return parse_job_blocks(text)


PARSERS = {
    "linkedin.com": parse_linkedin,
    "hirist.tech": parse_hirist,
    "hirist.com": parse_hirist,
}


def sender_domain(from_header):
    m = re.search(r"@([\w.-]+)", from_header)
    return m.group(1).lower() if m else ""


def match_parser(from_header):
    domain = sender_domain(from_header)
    for key, fn in PARSERS.items():
        if key in domain:
            return fn
    return None


# --------------------------------------------------------------- Output ----

def load_existing_output():
    if os.path.exists(OUTPUT_FILE):
        try:
            return json.loads(Path(OUTPUT_FILE).read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_output(records):
    tmp = OUTPUT_FILE + ".tmp"
    Path(tmp).write_text(json.dumps(records, indent=2, ensure_ascii=False))
    os.replace(tmp, OUTPUT_FILE)  # atomic swap, avoids a half-written file on crash


# ----------------------------------------------------------------- Main ----

def main():
    service: Any = get_service()
    source_label_id = get_or_create_label(service, SOURCE_LABEL)
    done_label_id = get_or_create_label(service, DONE_LABEL)

    message_ids = list_unprocessed_messages(service, source_label_id, done_label_id)
    print(f"Found {len(message_ids)} unprocessed JobSearch emails.")

    records = load_existing_output()
    processed = skipped_unrecognized = skipped_no_jobs = 0

    for msg_id in message_ids:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        
        headers = msg["payload"]["headers"]
        from_header = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date = get_header(headers, "Date")

        parser = match_parser(from_header)
        if not parser:
            skipped_unrecognized += 1
            continue  # unrecognized sender: leave label untouched, per spec

        jobs = parser(extract_body(msg["payload"]), subject)
        if not jobs:
            skipped_no_jobs += 1
            continue  # recognized sender but parse failed: leave for manual review

        # Drop any stale entries for this message before adding fresh ones,
        # so re-running after a label reset never leaves old/bad data
        # sitting alongside the corrected extraction.
        records = [r for r in records if r.get("message_id") != msg_id]

        for job in jobs:
            records.append({
                "message_id": msg_id,
                "sender": from_header,
                "date": date,
                "subject": subject,
                **job,
            })

        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [done_label_id]}
        ).execute()
        processed += 1

    save_output(records)
    print(f"Processed: {processed} | Unrecognized sender: {skipped_unrecognized} | "
          f"No jobs parsed: {skipped_no_jobs}")
    print(f"Extracted {len(records)} total job entries -> {OUTPUT_FILE}")
    print(f"Marked {processed} emails with '{DONE_LABEL}' label.")


if __name__ == "__main__":
    main()