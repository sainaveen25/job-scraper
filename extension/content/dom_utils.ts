export function cssPath(element: Element): string {
  if (element.id) {
    return `#${CSS.escape(element.id)}`;
  }
  const parts: string[] = [];
  let current: Element | null = element;
  while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
    let selector = current.nodeName.toLowerCase();
    const name = current.getAttribute("name");
    if (name) {
      selector += `[name="${cssAttr(name)}"]`;
      parts.unshift(selector);
      break;
    }
    const parentElement: Element | null = current.parentElement;
    if (parentElement) {
      const siblings = Array.from(parentElement.children).filter((child: Element) => child.nodeName === current?.nodeName);
      if (siblings.length > 1) {
        selector += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      }
    }
    parts.unshift(selector);
    current = parentElement;
  }
  return parts.join(" > ");
}

export function labelFor(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): string {
  const dataLabel = control.getAttribute("data-qa") || control.getAttribute("data-testid") || control.getAttribute("data-automation-id");
  const id = control.id;
  if (id) {
    const explicit = document.querySelector(`label[for="${cssAttr(id)}"]`);
    if (explicit?.textContent) {
      return cleanText(explicit.textContent);
    }
  }
  const wrappingLabel = control.closest("label");
  if (wrappingLabel?.textContent) {
    return cleanText(wrappingLabel.textContent);
  }
  const aria = control.getAttribute("aria-label") || control.getAttribute("aria-labelledby");
  if (aria) {
    const labelled = aria
      .split(/\s+/)
      .map((part) => document.getElementById(part)?.textContent || "")
      .join(" ");
    return cleanText(labelled || aria);
  }
  const closestField = control.closest(".field, .field-wrapper, .application-field, .application-question, .input-wrapper, .form-group, fieldset, li, div");
  const nearby = closestField?.querySelector("label, legend, .application-label, .field-label, [data-qa*='label' i], span, p");
  const previous = previousLabelText(control);
  const placeholder = control instanceof HTMLSelectElement ? "" : control.placeholder;
  return cleanText(nearby?.textContent || previous || placeholder || dataLabel || control.name || control.id || "");
}

export function isVisible(element: HTMLElement): boolean {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
}

export function cleanText(value: string): string {
  return value
    .replace(/\*/g, "")
    .replace(/\b(required|optional)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function previousLabelText(control: Element): string {
  let current: Element | null = control;
  for (let index = 0; index < 3; index += 1) {
    current = current.previousElementSibling;
    if (!current) {
      break;
    }
    const text = cleanText(current.textContent || "");
    if (text) {
      return text;
    }
  }
  return "";
}

function cssAttr(value: string): string {
  return CSS.escape(value).replace(/"/g, '\\"');
}
