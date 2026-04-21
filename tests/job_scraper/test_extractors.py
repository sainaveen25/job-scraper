from job_scraper.extractors import extract_keywords, tag_category


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
