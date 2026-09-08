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

import argparse
import base64
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

from db import init_db, upsert_job, load_jobs_for_export, export_to_json, get_existing_message_ids
from parsers import parse_linkedin, parse_hirist, parse_naukri

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

SOURCE_LABEL = "JobSearch"
DONE_LABEL = "delete"


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
    text/html while preserving line breaks (job listings are line-oriented).

    Some senders (e.g. Hirist) ship a text/plain part that's just a stub
    like "Please Enable HTML" for clients that don't render HTML, with all
    real content only in text/html. A plain part that short is treated as
    a placeholder and skipped in favor of the HTML part."""
    PLACEHOLDER_MAX_LEN = 60

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

    if plain_result and len(plain_result.strip()) > PLACEHOLDER_MAX_LEN:
        return plain_result
    if html_result:
        soup = BeautifulSoup(html_result, "html.parser")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        text = soup.get_text("\n")
        lines = [l.strip() for l in text.splitlines()]
        return "\n".join(l for l in lines if l)
    return plain_result or ""


# -------------------------------------------------------------- Parsing ----

PARSERS = {
    "linkedin.com": parse_linkedin,
    "hirist.tech": parse_hirist,
    "hirist.com": parse_hirist,
    "naukri.com": parse_naukri,
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
# earlier used to output a JSON object with list of jobs

# ----------------------------------------------------------------- Main ----

def main(args):
    # Handle export-only mode
    if args.export:
        export_to_json(args.export)
        print(f"Exported jobs to {args.export}")
        return

    # Initialize DB
    init_db()

    service: Any = get_service()
    source_label_id = get_or_create_label(service, SOURCE_LABEL)
    done_label_id = get_or_create_label(service, DONE_LABEL)

    done_ids = set(list_message_ids_for_label(service, done_label_id))
    unprocessed_ids = (set(list_message_ids_for_label(service, source_label_id)) - done_ids)

    print(f"Found {len(unprocessed_ids)} unprocessed JobSearch emails.")

    jobs_to_insert = []
    processed_msg_ids = []
    processed = skipped_unrecognized = skipped_no_jobs = 0

    for msg_id in unprocessed_ids:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        headers = msg["payload"]["headers"]
        from_header = get_header(headers, "From")
        date = get_header(headers, "Date")

        parser = match_parser(from_header)
        if not parser:
            skipped_unrecognized += 1
            continue

        jobs = parser(extract_body(msg["payload"]), get_header(headers, "Subject"))
        if not jobs:
            skipped_no_jobs += 1
            continue

        for job in jobs:
            record = {
                "message_id": msg_id,
                "sender": from_header,
                "date": date,
                **job,
            }
            jobs_to_insert.append(record)

        processed_msg_ids.append(msg_id)
        processed += 1

    # Debug: print records before committing
    if args.debug and jobs_to_insert:
        print("\n" + "="*70)
        print("DEBUG: Jobs extracted (before DB commit):")
        print("="*70)
        for i, job in enumerate(jobs_to_insert, 1):
            print(f"\n[{i}]")
            for key, val in job.items():
                print(f"  {key}: {val}")
        print("\n" + "="*70 + "\n")

    # Commit to DB and track new vs duplicate
    new_count = 0
    duplicate_count = 0
    for record in jobs_to_insert:
        status = upsert_job(record)
        if status == "new":
            new_count += 1
        elif status == "duplicate":
            duplicate_count += 1

    # Mark emails as done
    if processed_msg_ids:
        service.users().messages().batchModify(
            userId="me",
            body={
                "ids": processed_msg_ids,
                "addLabelIds": [done_label_id]
            }
        ).execute()

    all_jobs = load_jobs_for_export()
    total_parsed = new_count + duplicate_count
    print(f"\nProcessed: {processed} | Unrecognized sender: {skipped_unrecognized} | "
          f"No jobs parsed: {skipped_no_jobs}")
    print(f"Parsed jobs: {total_parsed} | New: {new_count} | Duplicates: {duplicate_count}")
    print(f"Total job entries in DB: {len(all_jobs)}")
    print(f"Marked {processed} emails with '{DONE_LABEL}' label.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract jobs from Gmail JobSearch emails")
    parser.add_argument("--debug", action="store_true", help="Print extracted records before committing to DB")
    parser.add_argument("--export", metavar="FILE", help="Export all jobs to JSON file (no Gmail fetch)")
    args = parser.parse_args()
    main(args)