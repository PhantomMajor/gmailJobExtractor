"""
Format-specific job parsers for LinkedIn, Hirist, and Naukri emails.
Each parser handles its distinct email structure and extraction logic.
"""

import re
from html.parser import HTMLParser
from typing import List, Dict, Tuple

EXPERIENCE_RE = re.compile(r"\d+\s*[-–to]+\s*\d+\s*\+?\s*(?:yrs?|years?)", re.I)
DURATION_RE = re.compile(r"^\d+[\s\-]*(?:to|–|-)\s*\d+\s*(?:months?|weeks?|days?)", re.I)
RATING_RE = re.compile(r"^\d+\.\d+$")

MAX_FIELD_LEN = 80


def _looks_like_noise(s: str) -> bool:
    """Check if a string is noise (URLs, boilerplate, etc.)"""
    s_lower = s.lower()
    noise_patterns = [
        "http://", "https://",
        "unsubscribe", "manage your job alert", "help", "view job", "see all jobs",
        "your job alert", "new jobs match", "preferences",
        "©", "linkedin corporation", "registered trademark",
        "2026 linkedin", "1zwnj",  # LinkedIn copyright/legal footer
        "view job:", "apply", "learn more",
        "pro tip", "note:", "info:", "tip:",  # Common metadata labels
    ]
    return (
        len(s) > MAX_FIELD_LEN
        or any(pattern in s_lower for pattern in noise_patterns)
        or s.endswith(":")  # Reject labels like "Pro Tip:"
    )


def _looks_like_role(s: str) -> bool:
    """Validate that a string looks like a job role, not metadata/skill list."""
    if not s or len(s) < 3:
        return False
    # Reject if it looks like a comma-separated skill list
    # (more than 2 commas usually means it's a list, not a role title)
    comma_count = s.count(",")
    if comma_count > 2:
        return False
    return True


def _is_valid_location(s: str) -> bool:
    """Validate that a string is actually a location, not a rating/duration/boilerplate."""
    if not s or RATING_RE.match(s) or DURATION_RE.match(s):
        return False
    s_lower = s.lower()
    invalid_keywords = [
        "get app", "not interested", "hi ", "hello ", "dear ",
        "unsubscribe", "manage preferences", "privacy", "copyright",
        "linkedin corporation", "actively hiring", "4 connections",
        "view job", "apply now", "save job", "report", "similar",
    ]
    if any(keyword in s_lower for keyword in invalid_keywords):
        return False
    # Location should have at least 2 chars
    if len(s) < 2:
        return False
    return True


# ======================== LINKEDIN PARSER ========================

def parse_linkedin(text: str, subject: str) -> List[Dict[str, str]]:
    """
    Parse LinkedIn job alerts. Plain text format with newline-separated fields:

    Role
    Company
    Location
    [optional metadata: "4 connections", "actively hiring", etc.]
    View job link
    ---------[separator line]
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    jobs = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip separator lines and boilerplate
        if line.startswith("---") or _looks_like_noise(line) or "See all jobs" in line:
            i += 1
            continue

        # Skip lines with "View job:" URLs
        if "view job:" in line.lower():
            i += 1
            continue

        # Skip if line looks like a role/company but is too short (likely junk)
        if len(line) < 3:
            i += 1
            continue

        # Look for pattern: Role → Company → Location
        role = line
        company = ""
        location = ""

        # Next non-empty line should be company
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1

        if i < len(lines):
            company = lines[i].strip()
            if _looks_like_noise(company) or company.startswith("---") or len(company) < 2:
                i += 1
                continue

        # Next line should be location (may have metadata like "4 connections")
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1

        if i < len(lines):
            potential_location = lines[i].strip()
            # Location line might have metadata after it
            if not (potential_location.startswith("---") or _looks_like_noise(potential_location)):
                location = potential_location

        # Add job only if we have role and company, they look valid, and role contains "Product"
        if (role and company and
            not _looks_like_noise(role) and
            not _looks_like_noise(company) and
            _looks_like_role(role) and
            len(company) > 2 and
            "product" in role.lower()):
            jobs.append({
                "role": role,
                "company": company,
                "location": location,
                "experience": ""
            })

        i += 1

    # Fallback: try subject line if no jobs found
    if not jobs and " at " in subject:
        role, company = subject.split(" at ", 1)
        jobs = [{"role": role.strip(), "company": company.strip(), "location": "", "experience": ""}]

    return jobs


# ======================== HIRIST PARSER ========================

def parse_hirist(text: str, subject: str) -> List[Dict[str, str]]:
    """
    Parse Hirist job alerts from HTML. Job cards have metadata line:
    "Company · Experience · Location"

    The HTML extraction gives us lines like:
    Role
    Company · Experience · Location
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    jobs = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip boilerplate
        if not line or _looks_like_noise(line) or line.lower() == "please enable html":
            i += 1
            continue

        # Look for metadata line containing · separator (Company · Experience · Location)
        if "·" in line:
            # This is a metadata line following a role
            parts = [p.strip() for p in line.split("·") if p.strip()]

            if len(parts) >= 2 and not any(_looks_like_noise(p) for p in parts):
                # Previous line should be the role
                role = ""
                if i > 0:
                    role = lines[i - 1].strip()
                    if "·" in role or _looks_like_noise(role):
                        role = ""

                # Parse metadata: Company · Experience · Location
                company = parts[0]
                experience = ""
                location = ""

                if len(parts) >= 3:
                    # Assume: Company · Experience · Location
                    experience = parts[1]
                    location = parts[2]
                elif len(parts) == 2:
                    # Assume: Company · Location
                    location = parts[1]

                # Validate location
                if not _is_valid_location(location):
                    location = ""

                if (role and company and
                    not _looks_like_noise(company) and
                    _looks_like_role(role) and
                    "product" in role.lower()):
                    jobs.append({
                        "role": role,
                        "company": company,
                        "location": location,
                        "experience": experience
                    })

        i += 1

    return jobs


# ======================== NAUKRI PARSER ========================

class NaukriJobCardExtractor(HTMLParser):
    """HTML parser to extract job data from Naukri's nested table structure."""

    def __init__(self):
        super().__init__()
        self.jobs = []
        self.current_job = {}
        self.in_job_card = False
        self.in_role = False
        self.in_company = False
        self.in_location = False
        self.in_rating = False
        self.last_text = ""

    def handle_starttag(self, tag: str, attrs: Dict):
        attrs_dict = dict(attrs)

        # Detect job card container
        if tag == "table" and "job-card-dark" in attrs_dict.get("class", ""):
            self.in_job_card = True
            self.current_job = {}

    def handle_endtag(self, tag: str):
        if tag == "table" and self.in_job_card:
            # End of job card
            if self.current_job.get("role") and self.current_job.get("company"):
                self.jobs.append(self.current_job)
            self.in_job_card = False
            self.current_job = {}

    def handle_data(self, data: str):
        text = data.strip()
        if not text or not self.in_job_card:
            return

        text = text.replace("&nbsp;", " ").strip()
        if not text:
            return

        # Try to identify field type by content patterns
        if not self.current_job.get("role") and len(text) < 100 and "product" in text.lower():
            self.current_job["role"] = text
        elif not self.current_job.get("company") and len(text) < 100 and self.current_job.get("role"):
            self.current_job["company"] = text
        elif not self.current_job.get("location") and len(text) < 80 and _is_valid_location(text):
            self.current_job["location"] = text
        elif RATING_RE.match(text) and "rating" not in self.current_job:
            # Skip ratings
            pass


def parse_naukri(text: str, subject: str) -> List[Dict[str, str]]:
    """
    Parse Naukri job alerts from HTML. Job data is in structured tables:
    - Role (contains "product")
    - Company name
    - Rating (skipped)
    - Location
    - Interactive form for "Not Interested"
    """

    # Try HTML parsing first
    parser = NaukriJobCardExtractor()
    try:
        parser.feed(text)
        if parser.jobs:
            for job in parser.jobs:
                job.setdefault("experience", "")
                job.setdefault("location", "")
            return parser.jobs
    except Exception:
        pass

    # Fallback: Line-by-line parsing for plain text extraction
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    jobs = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for role (contains "product")
        if "product" not in line.lower():
            i += 1
            continue

        role = line
        company = ""
        location = ""

        # Next line should be company
        if i + 1 < len(lines):
            company = lines[i + 1].strip()

        # Skip rating line (i+2) and get location (i+3)
        if i + 3 < len(lines):
            loc_line = lines[i + 3].strip()
            if _is_valid_location(loc_line):
                location = loc_line
        elif i + 2 < len(lines):
            # Fallback if i+3 doesn't exist
            potential_loc = lines[i + 2].strip()
            if _is_valid_location(potential_loc):
                location = potential_loc

        # Only add if we have valid role and company, and role contains "Product"
        if (role and company and
            not _looks_like_noise(company) and
            _looks_like_role(role) and
            "product" in role.lower()):
            jobs.append({
                "role": role,
                "company": company,
                "location": location,
                "experience": ""
            })

        i += 1

    return jobs
