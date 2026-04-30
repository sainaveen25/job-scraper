from automation.platforms.greenhouse import GreenhouseAdapter
from automation.platforms.lever import LeverAdapter
from automation.platforms.workday import WorkdayAdapter
from automation.runner import ApplyAutomationService


def test_platform_detection_specific_adapters():
    assert GreenhouseAdapter().detect("https://boards.greenhouse.io/acme/jobs/1")
    assert LeverAdapter().detect("https://jobs.lever.co/acme/abc")
    assert WorkdayAdapter().detect("https://acme.wd5.myworkdayjobs.com/en-US/jobs/job/1")


def test_service_falls_back_to_generic():
    service = ApplyAutomationService()
    assert service.detect_platform("https://example.com/apply").name == "generic"
