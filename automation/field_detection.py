from __future__ import annotations

import re
from typing import Any

from automation.field_mapping import is_sensitive_question, normalize_question
from automation.models import Field, FieldType


FIELD_SCAN_SCRIPT = r"""
() => {
  const fields = [];
  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width >= 0 && rect.height >= 0;
  };
  const labelFor = (el) => {
    const bits = [];
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) bits.push(lab.innerText);
    }
    const label = el.closest('label');
    if (label) bits.push(label.innerText);
    bits.push(el.getAttribute('aria-label'));
    bits.push(el.getAttribute('placeholder'));
    bits.push(el.name);
    const wrapper = el.closest('[data-qa], [data-testid], .field, .form-field, .application-question, .question');
    if (wrapper) {
      const wrapperLabel = wrapper.querySelector('label, legend, .label, .question, [class*="label"]');
      if (wrapperLabel) bits.push(wrapperLabel.innerText);
    }
    return bits.filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  };
  const selectorFor = (el, index) => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
    return `[data-applymate-field-index="${index}"]`;
  };
  const nodes = [...document.querySelectorAll('input, textarea, select')];
  nodes.forEach((el, index) => {
    if (!isVisible(el) && el.type !== 'file') return;
    el.setAttribute('data-applymate-field-index', index);
    let type = 'text';
    if (el.tagName.toLowerCase() === 'textarea') type = 'textarea';
    else if (el.tagName.toLowerCase() === 'select') type = 'select';
    else if (el.type === 'radio') type = 'radio';
    else if (el.type === 'checkbox') type = 'checkbox';
    else if (el.type === 'file') type = 'file';
    else if (el.type === 'password') type = 'password';
    const options = type === 'select'
      ? [...el.options].map((option) => option.innerText || option.value).filter(Boolean)
      : [];
    fields.push({
      label: labelFor(el),
      field_type: type,
      selector: selectorFor(el, index),
      name: el.name || null,
      required: Boolean(el.required || el.getAttribute('aria-required') === 'true'),
      options,
      value: el.value || null,
    });
  });
  return fields;
}
"""


def field_type_from_string(value: str | None) -> FieldType:
    try:
        return FieldType(value or "unknown")
    except ValueError:
        return FieldType.UNKNOWN


def fields_from_payload(payload: list[dict[str, Any]]) -> list[Field]:
    fields: list[Field] = []
    for item in payload:
        label = re.sub(r"\s+", " ", str(item.get("label") or item.get("name") or "")).strip()
        field = Field(
            label=label,
            field_type=field_type_from_string(item.get("field_type")),
            selector=item.get("selector"),
            name=item.get("name"),
            required=bool(item.get("required")),
            options=[str(option) for option in item.get("options") or []],
            value=item.get("value"),
            sensitive=is_sensitive_question(label),
            normalized_question=normalize_question(label),
        )
        fields.append(field)
    return fields


async def scan_dom_fields(page: Any) -> list[Field]:
    payload = await page.evaluate(FIELD_SCAN_SCRIPT)
    return fields_from_payload(payload or [])
