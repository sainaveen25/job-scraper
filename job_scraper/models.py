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
    title: str
    company: str | None
    location: str | None
    state: str | None
    country: str
    source: str
    source_external_id: str | None
    source_url: str
    job_url: str
    description: str | None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    ats_keywords: list[str] = field(default_factory=list)
    domain_terms: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    work_mode: str | None = None
    employment_type: str | None = None
    salary_text: str | None = None
    posted_at: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "state": self.state,
            "country": self.country,
            "source": self.source,
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
            "raw_payload": self.raw_payload,
        }

