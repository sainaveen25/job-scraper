import pytest

from automation.models import Field, FieldType, JobContext, PageProgress, UserProfile
from automation.platforms.base import PlatformAdapter
from automation.platforms.greenhouse import GreenhouseAdapter
from automation.platforms.workday import WorkdayAdapter
from automation.progress import progress_to_dict
from automation.resume_upload import upload_resume


class FakeLocator:
    def __init__(self, *, count=1, enabled=True):
        self._count = count
        self._enabled = enabled
        self.filled = None
        self.checked = False
        self.clicked = False
        self.uploaded = None
        self.selected = None

    @property
    def first(self):
        return self

    async def count(self):
        return self._count

    async def is_enabled(self):
        return self._enabled

    async def fill(self, value):
        self.filled = value

    async def check(self):
        self.checked = True

    async def uncheck(self):
        self.checked = False

    async def click(self):
        self.clicked = True

    async def set_input_files(self, value):
        self.uploaded = value

    async def select_option(self, **kwargs):
        self.selected = kwargs


class FakePage:
    def __init__(self):
        self.locators = {}
        self.url = "https://example.com/apply"

    def locator(self, selector):
        return self.locators.setdefault(selector, FakeLocator(count=0))

    async def title(self):
        return "Application"


class FixtureAdapter(PlatformAdapter):
    name = "fixture"

    async def scan_fields(self, page):
        return [
            Field("Email", FieldType.TEXT, selector="#email", required=True),
            Field("First Name", FieldType.TEXT, selector="#first"),
        ]


@pytest.mark.asyncio
async def test_adapter_reports_page_progress_and_next_readiness():
    page = FakePage()
    page.locators["#email"] = FakeLocator()
    page.locators["#first"] = FakeLocator()
    page.locators["button:has-text('Next')"] = FakeLocator()

    result = await FixtureAdapter().fill_fields(
        page,
        UserProfile(email="ada@example.com", first_name="Ada"),
        [],
        JobContext(url="https://example.com", metadata={"step": 2}),
        None,
    )

    assert result.progress is not None
    assert result.progress.step == 2
    assert result.progress.current_url == "https://example.com/apply"
    assert result.progress.page_title == "Application"
    assert result.progress.ready_for_next
    assert not result.progress.unresolved_fields
    assert result.logs
    assert result.logs[0].event == "fields_detected"
    assert page.locators["#email"].filled == "ada@example.com"


def test_progress_payload_includes_screenshot_and_rich_aliases():
    field = Field("Email", FieldType.TEXT, selector="#email")
    progress = PageProgress(
        page_detected="fixture",
        current_url="https://example.com/apply",
        page_title="Application",
        screenshot_path="artifacts/apply_runs/run/step-1.png",
        fields_found=[field],
        screenshots=["artifacts/apply_runs/run/step-1.png"],
    )

    payload = progress_to_dict(progress)

    assert payload["current_url"] == "https://example.com/apply"
    assert payload["page_title"] == "Application"
    assert payload["screenshot_path"].endswith("step-1.png")
    assert payload["fields_detected"][0]["label"] == "Email"


@pytest.mark.asyncio
async def test_adapter_does_not_mark_ready_when_required_unknown():
    page = FakePage()
    page.locators["#email"] = FakeLocator()
    page.locators["button:has-text('Next')"] = FakeLocator()

    result = await FixtureAdapter().fill_fields(
        page,
        UserProfile(first_name="Ada"),
        [],
        JobContext(url="https://example.com"),
        None,
    )

    assert result.progress is not None
    assert not result.progress.ready_for_next
    assert result.progress.required_missing[0].label == "Email"


@pytest.mark.asyncio
async def test_continue_button_clicks_first_enabled_control():
    page = FakePage()
    page.locators["button:has-text('Continue')"] = FakeLocator()

    moved = await PlatformAdapter().continue_to_next(page)

    assert moved
    assert page.locators["button:has-text('Continue')"].clicked


@pytest.mark.asyncio
async def test_greenhouse_adapter_specific_progression_selector():
    page = FakePage()
    page.locators["#submit_app"] = FakeLocator()

    moved = await GreenhouseAdapter().continue_to_next(page)

    assert moved
    assert page.locators["#submit_app"].clicked


@pytest.mark.asyncio
async def test_workday_adapter_specific_progression_selector():
    page = FakePage()
    selector = "button[data-automation-id='bottom-navigation-next-button']"
    page.locators[selector] = FakeLocator()

    moved = await WorkdayAdapter().continue_to_next(page)

    assert moved
    assert page.locators[selector].clicked


@pytest.mark.asyncio
async def test_resume_upload_sets_supported_file(tmp_path):
    resume = tmp_path / "tailored.pdf"
    resume.write_bytes(b"%PDF-1.4")
    page = FakePage()
    selector = "input[type='file'][name*='cv' i], input[type='file'][id*='cv' i]"
    page.locators[selector] = FakeLocator()

    uploaded = await upload_resume(page, str(resume))

    assert uploaded
    assert page.locators[selector].uploaded == str(resume)
