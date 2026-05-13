"""
description_cleaner.py
======================
Convert raw job-description HTML (or plain text) into four clean fields using
**only Python stdlib** — no additional pip dependencies.

Fields produced:
  raw_description      — original value, preserved for audit/debug only.
  description_text     — full clean plain text (safe for AI prompts, ATS, etc.)
  description_html_safe — sanitized HTML (allowlisted tags only, no scripts/styles/events).
  description_preview  — ≤300-char word-boundary excerpt of description_text.

Usage::

    from job_scraper.description_cleaner import clean_description

    bundle = clean_description(raw_html)
    bundle.description_text     # plain text
    bundle.description_html_safe  # safe HTML for rendering
    bundle.description_preview  # card excerpt
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any


# ---------------------------------------------------------------------------
# Public data contract
# ---------------------------------------------------------------------------

@dataclass
class DescriptionBundle:
    """All four description representations derived from a single raw source."""

    raw_description: str | None
    description_text: str | None
    description_html_safe: str | None
    description_preview: str | None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PREVIEW_MAX_CHARS = 300

# Tags whose content (and the tag itself) is completely removed.
_BLOCK_TAGS: frozenset[str] = frozenset({"script", "style", "noscript", "head"})

# Tags in the safe-HTML allowlist (attributes also filtered below).
_SAFE_TAGS: frozenset[str] = frozenset({
    "p", "br", "ul", "ol", "li",
    "b", "strong", "em", "i",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "a", "span", "div", "section", "article",
    "blockquote", "pre", "code",
})

# Attributes allowed per tag in safe HTML.
_SAFE_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "width", "height"}),
}
_SAFE_ATTRS_DEFAULT: frozenset[str] = frozenset()

# Regex for collapsing runs of blank lines (used after conversion).
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


# ---------------------------------------------------------------------------
# HTML → plain text parser
# ---------------------------------------------------------------------------

class _TextParser(HTMLParser):
    """
    Walk an HTML tree and emit clean plain text with structural hints
    converted to whitespace/bullets.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0  # depth inside a blocked tag

    # -- HTMLParser callbacks -----------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth or tag in _BLOCK_TAGS:
            self._skip_depth += 1
            return

        tag_lower = tag.lower()
        if tag_lower in ("br",):
            self._parts.append("\n")
        elif tag_lower in ("p", "div", "section", "article"):
            self._parts.append("\n\n")
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n\n")
        elif tag_lower == "li":
            self._parts.append("\n• ")
        elif tag_lower in ("ul", "ol"):
            self._parts.append("\n")
        elif tag_lower in ("tr", "hr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return
        tag_lower = tag.lower()
        if tag_lower in ("p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n\n")
        elif tag_lower in ("ul", "ol", "li"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    # -- Result -------------------------------------------------------------

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse long horizontal whitespace (but preserve newlines).
        lines = [_MULTI_SPACE_RE.sub(" ", line) for line in raw.split("\n")]
        joined = "\n".join(line.strip() for line in lines)
        # Collapse 3+ consecutive blank lines to 2.
        joined = _MULTI_BLANK_RE.sub("\n\n", joined)
        return joined.strip()


# ---------------------------------------------------------------------------
# HTML → safe HTML sanitiser
# ---------------------------------------------------------------------------

class _SafeHTMLParser(HTMLParser):
    """
    Walk an HTML tree and emit HTML with only allowlisted tags/attributes.
    - Strips <script>, <style>, and all event attributes (on*).
    - Keeps structural/semantic tags from _SAFE_TAGS.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth or tag in _BLOCK_TAGS:
            self._skip_depth += 1
            return
        tag_lower = tag.lower()
        if tag_lower not in _SAFE_TAGS:
            return  # drop the tag but keep children
        allowed_attrs = _SAFE_ATTRS.get(tag_lower, _SAFE_ATTRS_DEFAULT)
        safe_attr_str = ""
        for attr_name, attr_val in attrs:
            if attr_name.lower().startswith("on"):
                continue  # strip all event handlers
            if attr_name.lower() not in allowed_attrs:
                continue
            # Sanitise href to prevent javascript: URIs.
            if attr_name.lower() == "href" and attr_val and attr_val.strip().lower().startswith("javascript"):
                continue
            escaped_val = html.escape(attr_val or "", quote=True)
            safe_attr_str += f' {attr_name}="{escaped_val}"'
        # Void elements.
        if tag_lower == "br":
            self._parts.append(f"<{tag_lower}{safe_attr_str} />")
        else:
            self._parts.append(f"<{tag_lower}{safe_attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return
        tag_lower = tag.lower()
        if tag_lower in _BLOCK_TAGS:
            return
        if tag_lower in _SAFE_TAGS and tag_lower != "br":
            self._parts.append(f"</{tag_lower}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self._skip_depth:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip_depth:
            self._parts.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self._parts).strip()


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]*>|&[a-zA-Z#]\w*;")


def _looks_like_html(value: str) -> bool:
    """Return True if the string contains HTML tags or entity references."""
    return bool(_HTML_TAG_RE.search(value))


# ---------------------------------------------------------------------------
# Preview builder
# ---------------------------------------------------------------------------

def _make_preview(text: str, max_chars: int = _PREVIEW_MAX_CHARS) -> str | None:
    """Return a word-boundary excerpt of *text* up to *max_chars* characters."""
    if not text:
        return None
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    truncated = stripped[:max_chars]
    # Walk backward to a word boundary.
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:") + "…"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def clean_description(raw: Any) -> DescriptionBundle:
    """
    Convert *raw* (str, bytes, or None) into a :class:`DescriptionBundle`.

    Args:
        raw: The original job description.  May be plain text or HTML.

    Returns:
        A :class:`DescriptionBundle` with all four fields populated.
        All fields are ``None`` when *raw* is empty/None.
    """
    if raw is None:
        return DescriptionBundle(
            raw_description=None,
            description_text=None,
            description_html_safe=None,
            description_preview=None,
        )

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    elif not isinstance(raw, str):
        raw = str(raw)

    if not raw.strip():
        return DescriptionBundle(
            raw_description=raw or None,
            description_text=None,
            description_html_safe=None,
            description_preview=None,
        )

    raw_description: str = raw

    if _looks_like_html(raw):
        # --- Plain text extraction -----------------------------------------
        text_parser = _TextParser()
        try:
            text_parser.feed(raw)
        except Exception:
            pass
        description_text: str | None = text_parser.get_text() or None

        # --- Safe HTML extraction ------------------------------------------
        safe_parser = _SafeHTMLParser()
        try:
            safe_parser.feed(raw)
        except Exception:
            pass
        description_html_safe: str | None = safe_parser.get_html() or None
    else:
        # Plain text input — decode any residual entities.
        decoded = html.unescape(raw)
        # Collapse excessive whitespace while preserving paragraphs.
        lines = [_MULTI_SPACE_RE.sub(" ", line) for line in decoded.split("\n")]
        description_text = _MULTI_BLANK_RE.sub("\n\n", "\n".join(line.strip() for line in lines)).strip() or None
        description_html_safe = None  # no HTML to sanitise

    description_preview = _make_preview(description_text or "") if description_text else None

    return DescriptionBundle(
        raw_description=raw_description,
        description_text=description_text,
        description_html_safe=description_html_safe,
        description_preview=description_preview,
    )
