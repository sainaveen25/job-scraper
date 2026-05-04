from job_scraper.extractors import extract_keywords, is_job_like, tag_category


def test_extract_keywords_finds_expected_terms():
    data = extract_keywords(
        "We need Java, Spring Boot, AWS, Docker, Kubernetes, SQL, REST APIs, Terraform and CI/CD experience."
    )
    assert "Java" in data["required_skills"]
    assert "Spring Boot" in data["required_skills"]
    assert "AWS" in data["required_skills"]
    assert "Docker" in data["required_skills"]
    assert "Kubernetes" in data["required_skills"]
    assert "SQL" in data["required_skills"]
    assert "REST APIs" in data["required_skills"]
    assert "Terraform" in data["required_skills"]
    assert "CI/CD" in data["required_skills"]


def test_tag_category():
    category = tag_category("Senior DevOps Engineer", "Terraform AWS Kubernetes CI/CD")
    assert category == "devops"


def test_extract_keywords_finds_broad_engineering_terms():
    data = extract_keywords("Relay design for substations, PLC controls, CAD, RF, firmware, and validation testing.")
    assert "Relay Protection" in data["required_skills"]
    assert "PLC" in data["required_skills"]
    assert "CAD" in data["required_skills"]
    assert "RF" in data["required_skills"]
    assert "Firmware" in data["required_skills"]
    assert "Validation" in data["required_skills"]


def test_tag_category_keeps_non_software_engineering_distinctions():
    assert tag_category("Relay Designer", "Protection relay and substation design") == "power_systems"
    assert tag_category("Controls Engineer", "PLC and SCADA automation") == "controls_automation"
    assert tag_category("Mechanical Engineer", "CAD product design") == "mechanical_engineering"


def test_is_job_like_keeps_stem_and_filters_obvious_non_stem():
    assert is_job_like("Electrical Engineer", "Substation and circuit design")
    assert is_job_like("Hardware Validation Engineer", "Test FPGA boards")
    assert is_job_like("Controls Technician", "PLC and SCADA troubleshooting")
    assert not is_job_like("Retail Sales Associate", "Customer-facing store role")
    assert not is_job_like("Non-Technical Recruiter", "Hire software engineers")
    assert not is_job_like("Warehouse Specialist I", "Inventory and fulfillment for a technology company")
    assert not is_job_like("Lease Accounting Specialist", "Accounting for data center leases")
    assert not is_job_like("Director, Global Affairs", "Policy role at a software company")
    assert not is_job_like("Graphic Designer", "Create marketing assets")
    assert not is_job_like("Industry Product Manager", "Product roadmap and customer discovery")
    assert not is_job_like("Director of Industrial", "Industrial client relationships")
    assert not is_job_like("Investment Banking Analyst", "Finance and valuation modeling")
    assert not is_job_like("Data Entry Clerk", "Enter customer records into spreadsheets")
    assert is_job_like("Relay Designer", "Protection relay and substation design")
