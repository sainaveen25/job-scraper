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
    ("Junior Front-End Developer", "React and TypeScript applications", "frontend"),
    ("UI Engineer", "Angular front-end development", "frontend"),

    # full_stack
    ("Full Stack Developer", "Full stack web development", "full_stack"),
    ("Fullstack Engineer", "Fullstack Java and React", "full_stack"),

    # ai_ml
    ("Machine Learning Engineer", "LLM fine-tuning and inference", "ai_ml"),
    ("AI Engineer", "Artificial intelligence and neural networks", "ai_ml"),

    # data titles should not get stolen by incidental security words
    ("Senior Data Scientist", "Consumer app fraud and security analytics", "data_analytics"),

    # electrical / electronics / telecom / power
    ("Electrical Engineer", "Circuit design and electrical systems", "electrical_engineering"),
    ("Electronics Engineer", "PCB schematic capture and circuit design", "electronics_engineering"),
    ("Communication Engineer", "RF communication systems and signal processing", "telecom_engineering"),
    ("Relay Designer", "Protection relay and substation design", "power_systems"),
    ("RF Engineer", "Antenna and radio frequency systems", "telecom_engineering"),

    # controls / embedded / hardware / validation
    ("Controls Engineer", "PLC, SCADA, and control systems", "controls_automation"),
    ("Embedded Systems Engineer", "RTOS firmware on microcontrollers", "embedded_firmware"),
    ("Firmware Engineer", "Embedded C and microcontroller firmware", "embedded_firmware"),
    ("Hardware Engineer", "FPGA board design and validation", "hardware_engineering"),
    ("Hardware Validation Engineer", "Validation and verification test plans", "validation_testing"),

    # mechanical / manufacturing / industrial / robotics
    ("Mechanical Engineer", "CAD and product design", "mechanical_engineering"),
    ("Manufacturing Engineer", "Lean manufacturing processes", "manufacturing_engineering"),
    ("Process Engineer", "Production process engineering", "manufacturing_engineering"),
    ("Industrial Engineer", "Six sigma process improvement", "industrial_engineering"),
    ("Robotics Engineer", "Robotics and mechatronics automation", "robotics_mechatronics"),

    # civil / energy / other STEM
    ("Civil Engineer", "Transportation infrastructure", "civil_engineering"),
    ("Structural Engineer", "Structural steel design", "structural_engineering"),
    ("Environmental Engineer", "Water resources compliance", "environmental_engineering"),
    ("Renewable Energy Engineer", "Solar battery energy systems", "energy_engineering"),
    ("Biomedical Engineer", "Medical device development", "biomedical_engineering"),
    ("Research Engineer", "R&D prototype testing", "research_engineering"),
    ("Systems Engineer", "Systems engineering requirements", "systems_engineering"),
    ("Systems Analyst", "Technical systems analysis", "systems_engineering"),

    # support
    ("Support Engineer", "Technical support and help desk", "technical_support"),
    ("Field Engineer", "Technical field support for lab systems", "technical_support"),

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
