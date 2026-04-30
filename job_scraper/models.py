from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BroadQuery:
    category: str
    location: str
    query: str


@dataclass
class JobPosting:
    title: str = ""
    normalized_title: str | None = None
    company: str | None = None
    location: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    source: str = ""
    source_mode: str = "direct_http"
    source_status: str = "ok"
    source_external_id: str | None = None
    source_url: str = ""
    job_url: str = ""
    description: str | None = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    ats_keywords: list[str] = field(default_factory=list)
    domain_terms: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    work_mode: str | None = None
    employment_type: str | None = None
    salary_text: str | None = None
    posted_at: str | None = None
    posted_at_raw: str | None = None
    posted_at_source: str | None = None
    scraped_at: str | None = None
    category: str | None = None
    search_terms: list[str] = field(default_factory=list)
    autocomplete_terms: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "normalized_title": self.normalized_title,
            "company": self.company,
            "location": self.location,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "source": self.source,
            "source_mode": self.source_mode,
            "source_status": self.source_status,
            "source_external_id": self.source_external_id,
            "source_url": self.source_url,
            "job_url": self.job_url,
            "description": self.description,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "ats_keywords": self.ats_keywords,
            "domain_terms": self.domain_terms,
            "responsibilities": self.responsibilities,
            "work_mode": self.work_mode,
            "employment_type": self.employment_type,
            "salary_text": self.salary_text,
            "posted_at": self.posted_at,
            "posted_at_raw": self.posted_at_raw,
            "posted_at_source": self.posted_at_source,
            "scraped_at": self.scraped_at,
            "category": self.category,
            "search_terms": self.search_terms,
            "autocomplete_terms": self.autocomplete_terms,
            "raw_payload": self.raw_payload,
        }
