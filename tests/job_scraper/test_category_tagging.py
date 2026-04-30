"""Tests for infer_category covering all taxonomy categories."""
from __future__ import annotations

import pytest

from job_scraper.normalization import infer_category


@pytest.mark.parametrize("title,description,expected", [
    # salesforce (highest priority — must match before backend)
    ("Salesforce Developer", "Apex, Lightning, and SOQL", "salesforce"),
    ("Salesforce Admin", "Configure and customize Salesforce", "salesforce"),

    # workday
    ("Workday Analyst", "HCM business processes and integrations", "workday"),
    ("Workday Consultant", "Workday HCM implementation", "workday"),

    # cybersecurity
    ("Security Engineer", "Cybersecurity, IAM, and SOC", "cybersecurity"),
    ("Cybersecurity Analyst", "Vulnerability assessment", "cybersecurity"),

    # devops
    ("DevOps Engineer", "Kubernetes, Terraform, CI/CD pipelines", "devops"),
    ("Site Reliability Engineer", "SRE platform engineering", "devops"),
    ("Platform Engineer", "Kubernetes and platform engineering", "devops"),

    # cloud
    ("Cloud Architect", "AWS and Azure infrastructure", "cloud"),
    ("Cloud Engineer", "GCP, AWS cloud design", "cloud"),

    # qa
    ("QA Automation Engineer", "Selenium and Playwright tests", "qa"),
    ("Test Automation Engineer", "Cypress test automation", "qa"),

    # data_engineering
    ("Senior Data Engineer", "Build Spark ETL pipelines with Databricks", "data_engineering"),
    ("ETL Developer", "Data pipeline with Kafka", "data_engineering"),

    # data_analytics
    ("Data Analyst", "SQL, Tableau, Power BI reporting", "data_analytics"),
    ("BI Developer", "Analytics and reporting with Tableau", "data_analytics"),

    # business_analysis
    ("Business Analyst", "Requirements gathering and analysis", "business_analysis"),
    ("Business Systems Analyst", "Business process analysis", "business_analysis"),

    # frontend
    ("Frontend Developer", "React and TypeScript applications", "frontend"),
    ("UI Engineer", "Angular front-end development", "frontend"),

    # full_stack
    ("Full Stack Developer", "Full stack web development", "full_stack"),
    ("Fullstack Engineer", "Fullstack Java and React", "full_stack"),

    # ai_ml
    ("Machine Learning Engineer", "LLM fine-tuning and inference", "ai_ml"),
    ("AI Engineer", "Artificial intelligence and neural networks", "ai_ml"),

    # product
    ("Product Manager", "Roadmap planning and product delivery", "product"),
    ("Product Owner", "Agile product ownership", "product"),

    # support
    ("Support Engineer", "Technical support and help desk", "support"),
    ("Help Desk Technician", "Desktop support IT help desk", "support"),

    # software_engineering (catch-all for software/backend)
    ("Software Engineer", "Application developer backend systems", "software_engineering"),
    ("Application Developer", "Software developer backend APIs", "software_engineering"),

    # backend
    ("Backend Engineer", "API engineer Java Python backend", "backend"),
    ("Python Developer", "Python backend REST APIs", "backend"),
])
def test_infer_category(title, description, expected):
    result = infer_category(title, description)
    assert result == expected, f"For title={title!r}: expected {expected!r}, got {result!r}"


def test_unknown_category_for_unrecognised_title():
    result = infer_category("Office Manager", "Scheduling and administration")
    assert result == "unknown"


def test_category_uses_keywords_list():
    result = infer_category(
        "Technical Consultant",
        "ERP implementation",
        keywords=["salesforce", "apex"],
    )
    assert result == "salesforce"
