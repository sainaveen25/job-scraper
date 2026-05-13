"""
tests/job_scraper/test_jd_cleaner.py
=====================================
Unit tests for job_scraper.description_cleaner.clean_description.
These cover every HTML construct that can pollute job descriptions.
"""
from __future__ import annotations

import pytest

from job_scraper.description_cleaner import DescriptionBundle, clean_description


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(raw: str | None) -> str | None:
    return clean_description(raw).description_text


def _preview(raw: str | None) -> str | None:
    return clean_description(raw).description_preview


def _html_safe(raw: str | None) -> str | None:
    return clean_description(raw).description_html_safe


# ---------------------------------------------------------------------------
# Basic structural tests
# ---------------------------------------------------------------------------

def test_none_input_returns_all_none():
    bundle = clean_description(None)
    assert bundle.raw_description is None
    assert bundle.description_text is None
    assert bundle.description_html_safe is None
    assert bundle.description_preview is None


def test_empty_string_returns_all_none():
    bundle = clean_description("   ")
    assert bundle.description_text is None
    assert bundle.description_preview is None


def test_plain_text_passes_through():
    text = _text("We are looking for a backend engineer.")
    assert text == "We are looking for a backend engineer."


def test_raw_description_is_preserved():
    raw = "<p>Hello &amp; World</p>"
    bundle = clean_description(raw)
    assert bundle.raw_description == raw


# ---------------------------------------------------------------------------
# HTML conversion tests
# ---------------------------------------------------------------------------

def test_br_converted_to_newline():
    text = _text("Line one<br>Line two<br/>Line three")
    assert "Line one" in text
    assert "Line two" in text
    assert "Line three" in text
    assert "\n" in text


def test_p_tags_produce_paragraph_separation():
    text = _text("<p>First paragraph.</p><p>Second paragraph.</p>")
    assert "First paragraph." in text
    assert "Second paragraph." in text
    # There should be at least one blank line between them.
    assert "\n\n" in text or text.index("Second") > text.index("First") + 5


def test_ul_li_produces_bullets():
    raw = "<ul><li>Python</li><li>SQL</li><li>Spark</li></ul>"
    text = _text(raw)
    assert "Python" in text
    assert "SQL" in text
    assert "Spark" in text
    assert "•" in text


def test_ol_li_produces_bullets():
    raw = "<ol><li>First step</li><li>Second step</li></ol>"
    text = _text(raw)
    assert "First step" in text
    assert "Second step" in text
    assert "•" in text


# ---------------------------------------------------------------------------
# Entity decoding tests
# ---------------------------------------------------------------------------

def test_html_entities_decoded():
    text = _text("Java &amp; Python &lt;developers&gt; needed &ndash; now")
    assert "&amp;" not in text
    assert "&lt;" not in text
    assert "&gt;" not in text
    assert "Java" in text
    assert "Python" in text


def test_nbsp_converted_to_space():
    text = _text("Remote&nbsp;position in&nbsp;Austin")
    # &nbsp; should become a regular space (not a non-breaking space entity).
    assert "&nbsp;" not in text
    assert "Remote" in text
    assert "Austin" in text


def test_escaped_html_in_plain_text():
    """Escaped angle brackets inside a non-HTML string (already encoded)."""
    text = _text("Requirements: &lt;5 years experience, &gt;BS degree")
    assert "&lt;" not in text
    assert "&gt;" not in text


# ---------------------------------------------------------------------------
# Security / sanitisation tests
# ---------------------------------------------------------------------------

def test_script_tag_content_stripped():
    raw = "<p>Apply today!</p><script>alert('xss')</script><p>Benefits included.</p>"
    text = _text(raw)
    safe_html = _html_safe(raw)

    assert "Apply today!" in text
    assert "alert" not in text
    assert "xss" not in text

    assert "<script>" not in (safe_html or "")
    assert "alert" not in (safe_html or "")


def test_style_tag_stripped():
    raw = "<style>body { color: red; }</style><p>Job details here.</p>"
    text = _text(raw)
    assert "color" not in text
    assert "Job details here." in text


def test_event_attributes_stripped_from_safe_html():
    raw = '<p onclick="evil()">Click me</p><a href="https://example.com" onmouseover="evil()">Link</a>'
    safe = _html_safe(raw) or ""
    assert "onclick" not in safe
    assert "onmouseover" not in safe
    assert "Click me" in safe
    assert "https://example.com" in safe


def test_javascript_href_stripped():
    raw = '<a href="javascript:alert(1)">Click</a>'
    safe = _html_safe(raw) or ""
    assert "javascript:" not in safe


def test_inline_style_attribute_stripped():
    raw = '<p style="color:red;font-size:20px;">Description text.</p>'
    safe = _html_safe(raw) or ""
    assert 'style=' not in safe
    assert "Description text." in safe


# ---------------------------------------------------------------------------
# Whitespace / collapsing tests
# ---------------------------------------------------------------------------

def test_excessive_whitespace_collapsed():
    text = _text("We   need    a   developer.")
    assert "  " not in text
    assert "We need a developer." == text or "We need a developer" in text


def test_excessive_blank_lines_collapsed():
    raw = "<p>Part one.</p>\n\n\n\n\n<p>Part two.</p>"
    text = _text(raw)
    # Should not have more than 2 consecutive newlines.
    assert "\n\n\n" not in text


# ---------------------------------------------------------------------------
# Preview tests
# ---------------------------------------------------------------------------

def test_short_description_preview_equals_full():
    short = "We are looking for a great engineer to join our team."
    preview = _preview(short)
    assert preview == short


def test_long_description_preview_truncated_at_word_boundary():
    long_desc = ("We are looking for a talented software engineer " * 20).strip()
    preview = _preview(long_desc)
    assert preview is not None
    # Must be ≤ 300 chars (plus the ellipsis character which is 3 bytes but 1 char).
    # The ellipsis char itself is 1 character.
    assert len(preview) <= 305  # generous tolerance for the ellipsis
    assert preview.endswith("…")
    # Should not end mid-word.
    before_ellipsis = preview[:-1]
    assert not before_ellipsis[-1].isalpha() or " " in before_ellipsis


def test_preview_does_not_end_mid_sentence():
    text = "A " + ("word " * 100)
    preview = _preview(text)
    assert preview is not None
    assert "…" in preview


def test_html_long_description_preview():
    raw = "<p>" + ("This is a long job description paragraph. " * 20) + "</p>"
    bundle = clean_description(raw)
    assert bundle.description_preview is not None
    assert len(bundle.description_preview) <= 305


# ---------------------------------------------------------------------------
# Integration: full bundle structure
# ---------------------------------------------------------------------------

def test_full_bundle_has_all_four_fields():
    raw = "<p>We need a <strong>Python</strong> developer.</p><ul><li>5+ years Python</li></ul>"
    bundle = clean_description(raw)
    assert isinstance(bundle, DescriptionBundle)
    assert bundle.raw_description == raw
    assert bundle.description_text is not None
    assert bundle.description_html_safe is not None
    assert bundle.description_preview is not None


def test_plain_text_bundle_has_no_html_safe():
    """Plain text input should not produce an html_safe field (nothing to sanitise)."""
    raw = "Looking for a data engineer with 3+ years experience."
    bundle = clean_description(raw)
    assert bundle.description_text is not None
    # For pure text, html_safe is None — there is no HTML structure.
    assert bundle.description_html_safe is None


def test_mixed_real_world_jd():
    raw = """
    <div class="job-desc">
      <h2>About the Role</h2>
      <p>We are hiring a <strong>Senior Data Engineer</strong> for our analytics platform.</p>
      <ul>
        <li>Design and maintain ETL pipelines</li>
        <li>Work with Spark &amp; Databricks</li>
        <li>Collaborate with cross-functional teams</li>
      </ul>
      <p>Salary: $120,000 &ndash; $150,000 per year.</p>
      <script>trackView();</script>
    </div>
    """
    bundle = clean_description(raw)
    assert "Senior Data Engineer" in (bundle.description_text or "")
    assert "ETL pipelines" in (bundle.description_text or "")
    assert "trackView" not in (bundle.description_text or "")
    assert "&amp;" not in (bundle.description_text or "")
    assert "<script>" not in (bundle.description_html_safe or "")
    assert bundle.description_preview is not None
