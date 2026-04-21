from __future__ import annotations

import re
from typing import Any


TECH_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("Java", r"\bjava\b"),
    ("Spring Boot", r"\bspring\s+boot\b"),
    ("Python", r"\bpython\b"),
    ("JavaScript", r"\bjavascript\b"),
    ("TypeScript", r"\btypescript\b"),
    ("React", r"\breact\b"),
    ("Angular", r"\bangular\b"),
    ("Node.js", r"\bnode(?:\.js)?\b"),
    ("AWS", r"\baws\b|\bamazon web services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle cloud\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("Terraform", r"\bterraform\b"),
    ("SQL", r"\bsql\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("MongoDB", r"\bmongodb\b"),
    ("REST APIs", r"\brest(?:ful)?\s+apis?\b|\brest api\b"),
    ("GraphQL", r"\bgraphql\b"),
    ("microservices", r"\bmicroservices?\b"),
    ("CI/CD", r"\bci/cd\b|\bcontinuous integration\b|\bcontinuous delivery\b"),
    ("Jenkins", r"\bjenkins\b"),
    ("Git", r"\bgit\b"),
    ("Jira", r"\bjira\b"),
    ("Linux", r"\blinux\b"),
    ("Tableau", r"\btableau\b"),
    ("Power BI", r"\bpower bi\b"),
    ("Excel", r"\bexcel\b"),
    ("ETL", r"\betl\b"),
    ("Spark", r"\bspark\b"),
    ("Kafka", r"\bkafka\b"),
    ("Snowflake", r"\bsnowflake\b"),
    ("Databricks", r"\bdatabricks\b"),
    ("Salesforce", r"\bsalesforce\b"),
    ("Workday", r"\bworkday\b"),
    ("ServiceNow", r"\bservicenow\b"),
    ("Selenium", r"\bselenium\b"),
    ("Playwright", r"\bplaywright\b"),
    ("Cypress", r"\bcypress\b"),
    ("Machine Learning", r"\bmachine learning\b"),
    ("AI", r"\bartificial intelligence\b|\bai\b"),
    ("LLM", r"\bllm\b|\blarge language model"),
    ("Cybersecurity", r"\bcybersecurity\b|\bsecurity\b"),
)

CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("devops", ("devops", "ci/cd", "jenkins", "kubernetes", "terraform")),
    ("software_engineering", ("software", "backend", "frontend", "full stack", "developer", "engineer")),
    ("data", ("data", "analytics", "bi", "etl", "sql", "tableau", "power bi")),
    ("business", ("business analyst", "business analysis", "operations")),
    ("cloud", ("cloud", "aws", "azure", "gcp", "terraform")),
    ("qa", ("qa", "quality assurance", "selenium", "playwright", "cypress", "test automation")),
    ("security", ("security", "cybersecurity", "iam", "soc")),
    ("product", ("product manager", "product management")),
    ("project", ("project manager", "project management", "scrum")),
    ("salesforce", ("salesforce",)),
    ("workday", ("workday", "hcm")),
    ("it_support", ("it support", "help desk", "systems administrator", "sysadmin")),
)

JOB_HINTS = ("job", "career", "position", "role", "responsibilities", "requirements", "apply")
RESPONSIBILITY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (r"\bbuild\b", r"\bdesign\b", r"\bdevelop\b", r"\bmaintain\b", r"\bcollaborate\b", r"\blead\b")
)
WORK_MODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Remote", re.compile(r"\bremote\b", re.IGNORECASE)),
    ("Hybrid", re.compile(r"\bhybrid\b", re.IGNORECASE)),
    ("On-site", re.compile(r"\bon[- ]?site\b|\bin office\b", re.IGNORECASE)),
)
EMPLOYMENT_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Full-time", re.compile(r"\bfull[- ]?time\b", re.IGNORECASE)),
    ("Part-time", re.compile(r"\bpart[- ]?time\b", re.IGNORECASE)),
    ("Contract", re.compile(r"\bcontract\b", re.IGNORECASE)),
    ("Internship", re.compile(r"\bintern(ship)?\b", re.IGNORECASE)),
    ("Temporary", re.compile(r"\btemporary\b", re.IGNORECASE)),
)
SALARY_PATTERN = re.compile(
    r"(\$[\d,]+(?:\.\d+)?(?:\s*-\s*\$[\d,]+(?:\.\d+)?)?(?:\s*(?:per year|yearly|annually|/hr|per hour))?)",
    re.IGNORECASE,
)
PREFERRED_PATTERN = re.compile(r"\bpreferred\b|\bnice to have\b|\bbonus\b", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_keywords(description: str | None) -> dict[str, Any]:
    text = normalize_text(description)
    lowered = text.lower()

    found_skills: list[str] = []
    for label, pattern in TECH_KEYWORDS:
        if re.search(pattern, lowered, re.IGNORECASE):
            found_skills.append(label)

    preferred_skills = found_skills if PREFERRED_PATTERN.search(text) else []
    ats_keywords = found_skills.copy()

    responsibilities = []
    for pattern in RESPONSIBILITY_PATTERNS:
        if pattern.search(text):
            responsibilities.append(pattern.pattern.replace(r"\b", "").replace("\\", ""))

    work_mode = next((label for label, pattern in WORK_MODE_PATTERNS if pattern.search(text)), None)
    employment_type = next((label for label, pattern in EMPLOYMENT_TYPE_PATTERNS if pattern.search(text)), None)
    salary_match = SALARY_PATTERN.search(text)
    salary_text = salary_match.group(1).strip() if salary_match else None

    domain_terms = [label for label, tokens in CATEGORY_PATTERNS if any(token in lowered for token in tokens)]

    return {
        "required_skills": found_skills,
        "preferred_skills": preferred_skills,
        "ats_keywords": ats_keywords,
        "domain_terms": domain_terms,
        "responsibilities": responsibilities,
        "work_mode": work_mode,
        "employment_type": employment_type,
        "salary_text": salary_text,
    }


def tag_category(title: str | None, description: str | None) -> str:
    haystack = f"{normalize_text(title)} {normalize_text(description)}".lower()
    for category, tokens in CATEGORY_PATTERNS:
        if any(token in haystack for token in tokens):
            return category
    return "unknown"


def is_job_like(title: str | None, description: str | None) -> bool:
    title_text = normalize_text(title).lower()
    description_text = normalize_text(description).lower()
    if len(title_text.split()) < 2:
        return False
    if any(hint in title_text for hint in ("job", "engineer", "developer", "analyst", "manager", "specialist", "administrator")):
        return True
    return any(hint in description_text for hint in JOB_HINTS)
