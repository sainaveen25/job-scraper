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
    ("MATLAB", r"\bmatlab\b"),
    ("Simulink", r"\bsimulink\b"),
    ("CAD", r"\bcad\b|\bsolidworks\b|\bautocad\b|\bcreo\b|\bcatia\b"),
    ("PLC", r"\bplc\b|\bprogrammable logic controller\b"),
    ("SCADA", r"\bscada\b"),
    ("Controls", r"\bcontrols?\b|\bcontrol systems?\b"),
    ("Power Systems", r"\bpower systems?\b|\bsubstation\b|\btransmission\b|\bdistribution\b"),
    ("Relay Protection", r"\brelay\b|\bprotection and control\b|\bprotective relaying\b"),
    ("Circuit Design", r"\bcircuit design\b|\bpcb\b|\bschematic\b"),
    ("Embedded Systems", r"\bembedded\b|\bmicrocontroller\b|\brtos\b"),
    ("Firmware", r"\bfirmware\b"),
    ("RF", r"\brf\b|\bradio frequency\b|\bantenna\b"),
    ("Signal Processing", r"\bsignal processing\b|\bdsp\b"),
    ("Hardware", r"\bhardware\b|\bfpga\b|\basic\b"),
    ("Validation", r"\bvalidation\b|\bverification\b|\btest engineer\b"),
    ("Manufacturing", r"\bmanufacturing\b|\bprocess engineering\b|\blean\b|\bsix sigma\b"),
    ("Robotics", r"\brobotics?\b|\bmechatronics\b"),
    ("Civil Engineering", r"\bcivil\b|\bstructural\b|\btransportation\b|\binfrastructure\b"),
    ("Environmental Engineering", r"\benvironmental\b|\bwater resources\b"),
    ("Energy", r"\brenewable energy\b|\benergy systems?\b|\bsolar\b|\bwind\b|\bbattery\b"),
    ("Biomedical", r"\bbiomedical\b|\bmedical device\b"),
    ("Lab Automation", r"\blab automation\b|\blaboratory automation\b"),
)

CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("devops", ("devops", "ci/cd", "jenkins", "kubernetes", "terraform")),
    ("backend", ("backend", "back end", "api engineer", "java developer", "python developer")),
    ("frontend", ("frontend", "front end", "ui engineer", "react developer", "angular developer")),
    ("full_stack", ("full stack", "fullstack")),
    ("software_engineering", ("software", "application developer", "software developer")),
    ("data_engineering", ("data engineer", "etl", "pipeline", "spark", "databricks")),
    ("data_analytics", ("data analyst", "analytics", "bi", "sql", "tableau", "power bi", "reporting")),
    ("business_analysis", ("business analyst", "business analysis", "business systems analyst")),
    ("cloud", ("cloud", "aws", "azure", "gcp", "terraform")),
    ("qa", ("qa", "quality assurance", "selenium", "playwright", "cypress", "test automation")),
    ("cybersecurity", ("security", "cybersecurity", "iam", "soc")),
    ("salesforce", ("salesforce",)),
    ("workday", ("workday", "hcm")),
    ("electrical_engineering", ("electrical engineer", "electrical engineering")),
    ("electronics_engineering", ("electronics engineer", "electronics engineering")),
    ("telecom_engineering", ("telecom", "communication engineer", "communication systems", "rf engineer", "signal processing")),
    ("power_systems", ("power systems", "substation", "relay", "protection and control", "transmission")),
    ("controls_automation", ("controls engineer", "control systems", "automation engineer", "plc", "scada")),
    ("hardware_engineering", ("hardware engineer", "circuit design", "pcb", "fpga", "asic")),
    ("validation_testing", ("validation engineer", "test engineer", "verification engineer")),
    ("embedded_firmware", ("embedded", "firmware", "rtos", "microcontroller")),
    ("mechanical_engineering", ("mechanical engineer", "mechanical engineering", "cad", "solidworks")),
    ("manufacturing_engineering", ("manufacturing engineer", "process engineer", "manufacturing")),
    ("industrial_engineering", ("industrial engineer", "lean", "six sigma")),
    ("robotics_mechatronics", ("robotics", "mechatronics")),
    ("civil_engineering", ("civil engineer", "civil engineering", "transportation engineer")),
    ("structural_engineering", ("structural engineer", "structural engineering")),
    ("environmental_engineering", ("environmental engineer", "water resources")),
    ("energy_engineering", ("energy systems", "renewable energy", "solar", "wind", "battery")),
    ("biomedical_engineering", ("biomedical engineer", "medical device")),
    ("research_engineering", ("research engineer", "r&d engineer")),
    ("systems_engineering", ("systems engineer", "systems engineering", "systems analyst", "technical program manager")),
    ("technical_support", ("support engineer", "technical support", "field engineer", "help desk", "systems administrator", "sysadmin")),
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
NON_STEM_TITLE_RE = re.compile(
    r"\b("
    r"cashier|sales associate|retail associate|restaurant|waiter|waitress|server|bartender|barista|"
    r"recruiter|talent acquisition|office assistant|administrative assistant|admin assistant|"
    r"customer service representative|customer support representative|beauty|salon|hair stylist|"
    r"account executive|accounting specialist|lease accounting|revenue accounting|marketing manager|"
    r"legal assistant|paralegal|bookkeeper|loan officer|warehouse specialist|warehouse associate|"
    r"global affairs|operating partner|school success|graphic designer|product manager|product owner|"
    r"director of industrial|investment banking analyst|financial analyst|finance analyst|accounting analyst|"
    r"data entry|data entry clerk"
    r")\b",
    re.IGNORECASE,
)
STEM_SIGNAL_RE = re.compile(
    r"\b("
    r"engineer|engineering|developer|architect|analyst|scientist|technician|technologist|"
    r"technical|systems?|software|data|analytics?|ai|machine learning|llm|cloud|devops|security|qa|"
    r"electrical|electronics?|relay|relay designer|controls?|power systems?|substation|embedded|hardware|firmware|"
    r"rf|communication systems?|signal processing|mechanical|manufacturing|process|industrial|"
    r"automation|robotics?|mechatronics|civil|structural|transportation|environmental|energy|"
    r"renewable|biomedical|research|validation|testing|laboratory|lab"
    r")\b",
    re.IGNORECASE,
)


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
    if NON_STEM_TITLE_RE.search(title_text):
        return False
    if STEM_SIGNAL_RE.search(f"{title_text} {description_text}"):
        return True
    return any(hint in description_text for hint in JOB_HINTS) and not NON_STEM_TITLE_RE.search(title_text)
