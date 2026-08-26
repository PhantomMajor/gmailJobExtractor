#!/usr/bin/env python3
import json
import sys
from gmailJobExtractor import get_service, list_message_ids_for_label, SOURCE_LABEL

def debug_explore_message(msg):
    """
    Temporary debug function to output the structure of raw headers,
    subject, and date objects from the Gmail API response.
    """
    headers = msg.get("payload", {}).get("headers", [])
    print("\n" + "="*80)
    print("DEBUG: EXPLORING RAW GMAIL MESSAGE OBJECTS")
    print("="*80)
    
    # 1. Structure of msg['payload']['headers']
    print(f"\n1. msg['payload']['headers'] is a {type(headers).__name__} of length {len(headers)}.")
    print("Here is a sample of the first 3 header objects:")
    print(json.dumps(headers[:3], indent=2))
    
    # 2. Finding specific headers (From, Subject, Date)
    print("\n2. Specific header objects (From, Subject, Date) as stored in the headers list:")
    for h in headers:
        name_lower = h.get("name", "").lower()
        if name_lower in ("from", "subject", "date"):
            print(f"\nHeader: {h.get('name')}")
            print(json.dumps(h, indent=2))
            
    print("="*80 + "\n")

def main():
    try:
        service = get_service()
    except Exception as e:
        sys.exit(f"Failed to authenticate or initialize Gmail API service: {e}\n"
                 f"Please ensure credentials.json is present and valid.")
        
    print(f"Listing message IDs for label: {SOURCE_LABEL}")
    source_label_id = None
    try:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        for l in labels:
            if l["name"].lower() == SOURCE_LABEL.lower():
                source_label_id = l["id"]
                break
    except Exception as e:
        sys.exit(f"Failed to query Gmail labels: {e}")
        
    if not source_label_id:
        sys.exit(f"Label '{SOURCE_LABEL}' not found in your Gmail account. Please create it first.")
        
    message_ids = list_message_ids_for_label(service, source_label_id)
    if not message_ids:
        sys.exit(f"No messages found with label '{SOURCE_LABEL}'.")
        
    msg_id = list(message_ids)[0]
    print(f"Fetching raw details for message ID: {msg_id}")
    try:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        debug_explore_message(msg)
    except Exception as e:
        sys.exit(f"Failed to fetch message details: {e}")

if __name__ == "__main__":
    main()
