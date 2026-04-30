from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Any

from job_scraper.extractors import normalize_text


_MINUTES_AGO_RE = re.compile(r"(\d+)\s*(minute|minutes|min|mins)\s+ago", re.IGNORECASE)
_HOURS_AGO_RE = re.compile(r"(\d+)\s*(hour|hours|hr|hrs)\s+ago", re.IGNORECASE)
_DAYS_AGO_RE = re.compile(r"(\d+)\s*(day|days)\s+ago", re.IGNORECASE)
_JUST_POSTED_RE = re.compile(r"\b(just posted|just now|posted today|today)\b", re.IGNORECASE)
_REMOTE_RE = re.compile(r"\bremote\b", re.IGNORECASE)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
_ONSITE_RE = re.compile(r"\bon[- ]?site\b|\bin[- ]office\b|\bon site\b", re.IGNORECASE)

US_STATES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}
STATE_NAME_TO_CODE = {name.casefold(): code for code, name in US_STATES.items()}
CANADA_PROVINCES = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}
PROVINCE_NAME_TO_CODE = {name.casefold(): code for code, name in CANADA_PROVINCES.items()}
COUNTRY_ALIASES = {
    "usa": "United States",
    "u.s.a": "United States",
    "us": "United States",
    "united states": "United States",
    "canada": "Canada",
    "india": "India",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "england": "United Kingdom",
    "germany": "Germany",
    "france": "France",
    "spain": "Spain",
    "italy": "Italy",
    "netherlands": "Netherlands",
    "poland": "Poland",
    "ireland": "Ireland",
    "singapore": "Singapore",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "philippines": "Philippines",
    "pakistan": "Pakistan",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
}

TITLE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsr\.?\b", re.IGNORECASE), "senior"),
    (re.compile(r"\bjr\.?\b", re.IGNORECASE), "junior"),
    (re.compile(r"\beng\b", re.IGNORECASE), "engineer"),
    (re.compile(r"\bdev\b", re.IGNORECASE), "developer"),
)

ROLE_SYNONYMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("software engineer", ("software engineer", "software developer")),
    ("java developer", ("java developer", "backend java developer", "java engineer")),
    ("full stack java developer", ("full stack java developer", "java full stack developer")),
    ("data analyst", ("data analyst", "reporting analyst", "sql analyst")),
    ("data engineer", ("data engineer", "etl developer", "pipeline engineer", "data pipeline engineer")),
    ("business analyst", ("business analyst", "business systems analyst")),
    ("salesforce developer", ("salesforce developer", "salesforce engineer", "apex developer", "lightning developer")),
    ("workday analyst", ("workday analyst", "workday consultant", "workday hcm analyst")),
)

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("salesforce", ("salesforce",)),
    ("workday", ("workday", "hcm")),
    ("cybersecurity", ("cybersecurity", "security engineer", "soc analyst", "iam", "application security")),
    ("devops", ("devops", "site reliability", "sre", "kubernetes", "terraform", "platform engineer")),
    ("cloud", ("cloud engineer", "aws", "azure", "gcp", "cloud architect")),
    ("qa", ("qa engineer", "quality assurance", "test automation", "selenium", "playwright", "cypress")),
    ("data_engineering", ("data engineer", "etl", "pipeline", "spark", "databricks")),
    ("data_analytics", ("data analyst", "analytics", "bi developer", "tableau", "power bi", "reporting analyst")),
    ("business_analysis", ("business analyst", "business analysis", "business systems analyst")),
    ("frontend", ("frontend", "front end", "ui engineer", "react developer", "angular developer")),
    ("full_stack", ("full stack", "fullstack")),
    ("ai_ml", ("machine learning", "ml engineer", "ai engineer", "llm", "artificial intelligence")),
    ("product", ("product manager", "product owner")),
    ("project_management", ("project manager", "project management", "program manager", "scrum master")),
    ("support", ("support engineer", "help desk", "technical support", "desktop support")),
    ("software_engineering", ("software engineer", "software developer", "application developer")),
    ("backend", ("backend engineer", "back end engineer", "api engineer", "java developer", "python developer")),
)


def parse_posted_at(value: Any, now: datetime | None = None) -> tuple[str | None, str | None]:
    timestamp = _parse_datetime(value, now=now)
    text = normalize_text(value) or None
    if timestamp is None:
        return None, text
    return timestamp.isoformat(), text


def _parse_datetime(value: Any, now: datetime | None = None) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None

    current = now or datetime.now(timezone.utc)

    if text.isdigit():
        number = int(text)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)

    lowered = text.casefold()
    if _JUST_POSTED_RE.search(lowered):
        return current
    if lowered == "yesterday":
        return current - timedelta(days=1)

    for regex, delta_builder in (
        (_MINUTES_AGO_RE, lambda amount: timedelta(minutes=amount)),
        (_HOURS_AGO_RE, lambda amount: timedelta(hours=amount)),
        (_DAYS_AGO_RE, lambda amount: timedelta(days=amount)),
    ):
        match = regex.search(lowered)
        if match:
            return current - delta_builder(int(match.group(1)))

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def choose_posted_at(
    raw_value: Any,
    *,
    scraped_at: datetime | None = None,
) -> dict[str, str | None]:
    current = scraped_at or datetime.now(timezone.utc)
    posted_at, posted_at_raw = parse_posted_at(raw_value, now=current)
    if posted_at:
        return {
            "posted_at": posted_at,
            "posted_at_raw": posted_at_raw,
            "posted_at_source": "source",
            "scraped_at": current.isoformat(),
        }
    return {
        "posted_at": current.isoformat(),
        "posted_at_raw": posted_at_raw,
        "posted_at_source": "fallback",
        "scraped_at": current.isoformat(),
    }


def normalize_location(
    location: Any,
    *,
    state: Any = None,
    country: Any = None,
    work_mode: Any = None,
) -> dict[str, str | None]:
    location_text = normalize_text(location) or None
    state_text = normalize_text(state) or None
    country_text = normalize_country(country)
    work_mode_text = normalize_work_mode(work_mode, location_text)
    city = None

    if location_text:
        # Strip parenthetical suffixes BEFORE splitting so "CA (On-site)" stays intact
        pre_cleaned = re.sub(r"\s*\([^)]*\)", "", location_text).strip()
        cleaned = re.sub(r"\s*[-|/]\s*", ", ", pre_cleaned)
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        # Identify work-mode tokens to skip when assigning city
        _work_mode_words = {"remote", "hybrid", "on-site", "onsite", "on site"}
        if parts:
            # Pick the first part that is not a work-mode keyword as the city
            for candidate in parts:
                if candidate.casefold() not in _work_mode_words:
                    # Don't assign known country names as city
                    if normalize_country(candidate) is None:
                        city = candidate if candidate.casefold() != "remote" else None
                    break
        for part in reversed(parts):
            normalized_country = normalize_country(part)
            if normalized_country and not country_text:
                country_text = normalized_country
                continue
            normalized_state = normalize_state(part)
            if normalized_state and not state_text:
                state_text = normalized_state

    if state_text and not country_text:
        if state_text in US_STATES:
            country_text = "United States"
        elif state_text in CANADA_PROVINCES:
            country_text = "Canada"

    return {
        "location": location_text,
        "city": city,
        "state": state_text,
        "country": country_text,
        "work_mode": work_mode_text,
    }


def normalize_state(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    upper = text.upper()
    if upper in US_STATES or upper in CANADA_PROVINCES:
        return upper
    if text.casefold() in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[text.casefold()]
    if text.casefold() in PROVINCE_NAME_TO_CODE:
        return PROVINCE_NAME_TO_CODE[text.casefold()]
    return None


def normalize_country(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    alias = COUNTRY_ALIASES.get(text.casefold())
    if alias:
        return alias
    return None


def normalize_work_mode(work_mode: Any, location: Any = None) -> str | None:
    for candidate in (normalize_text(work_mode), normalize_text(location)):
        if not candidate:
            continue
        if _REMOTE_RE.search(candidate):
            return "Remote"
        if _HYBRID_RE.search(candidate):
            return "Hybrid"
        if _ONSITE_RE.search(candidate):
            return "On-site"
    return None


def normalize_title(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    normalized = text.casefold()
    for pattern, replacement in TITLE_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"[^a-z0-9+/ ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def infer_category(
    title: Any,
    description: Any = None,
    keywords: list[str] | None = None,
) -> str:
    haystack = " ".join(
        part for part in (normalize_text(title), normalize_text(description), " ".join(keywords or [])) if part
    ).casefold()
    for category, tokens in CATEGORY_RULES:
        if any(token in haystack for token in tokens):
            return category
    return "unknown"


def generate_search_terms(
    *,
    title: Any,
    normalized_title: Any,
    category: str,
    required_skills: list[str] | None,
    ats_keywords: list[str] | None,
) -> tuple[list[str], list[str]]:
    ordered_terms: list[str] = []
    for candidate in (normalize_text(title), normalize_text(normalized_title)):
        if candidate:
            ordered_terms.append(candidate.casefold())

    title_text = normalize_text(title).casefold()
    normalized = normalize_text(normalized_title).casefold()

    if "java" in normalized and "javascript" not in normalized:
        ordered_terms.extend(
            [
                "java",
                "java developer",
                "java engineer",
                "backend java",
                "backend java developer",
            ]
        )
        if "full stack" in normalized or "fullstack" in normalized:
            ordered_terms.extend(["full stack java", "full stack java developer"])

    if "data analyst" in normalized:
        ordered_terms.extend(["data", "analyst", "data analyst", "reporting analyst", "sql analyst"])

    if "data engineer" in normalized:
        ordered_terms.extend(["data", "data engineer", "etl", "etl developer", "pipeline engineer"])

    if "business analyst" in normalized:
        ordered_terms.extend(["analyst", "business analyst", "business systems analyst"])

    if "salesforce" in normalized:
        ordered_terms.extend(["salesforce", "salesforce developer", "apex", "lightning", "crm"])

    if "workday" in normalized:
        ordered_terms.extend(["workday", "workday analyst", "hcm", "workday hcm", "workday consultant"])

    if category == "software_engineering":
        ordered_terms.append("software engineer")

    for label, synonyms in ROLE_SYNONYMS:
        if any(term in normalized or term in title_text for term in synonyms):
            ordered_terms.extend((label, *synonyms))

    for skill in (required_skills or []) + (ats_keywords or []):
        skill_text = normalize_text(skill).casefold()
        if skill_text and skill_text not in {"javascript", "typescript"}:
            ordered_terms.append(skill_text)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in ordered_terms:
        cleaned = re.sub(r"\s+", " ", term).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)

    autocomplete_terms = [term for term in deduped if len(term) >= 3]
    return deduped, autocomplete_terms
