import type { FieldDescriptor, FieldType, PageDetection } from "../shared/models";
import { detectPlatform } from "../shared/platform";
import { cssPath, isVisible, labelFor } from "./dom_utils";

const SENSITIVE_PATTERN = /\b(gender|race|ethnicity|veteran|disability|disabled|sexual orientation|pronouns|protected)\b/i;

export function detectPage(): PageDetection {
  const fields = detectFields();
  const platform = detectPlatform(location.href);
  const hasNext = hasButtonLike(/next|continue|save and continue|review/i);
  const hasSubmit = hasButtonLike(/submit|submit application|apply|send/i);
  return {
    ...platform,
    currentUrl: location.href,
    pageTitle: document.title,
    fields,
    hasNext,
    hasSubmit,
    step: inferStep(),
    debugLogs: [
      `platform=${platform.platform}`,
      `fields=${fields.length}`,
      `file_inputs=${fields.filter((field) => field.fieldType === "file").length}`,
      `has_next=${hasNext}`,
      `has_submit=${hasSubmit}`
    ]
  };
}

export function detectFields(): FieldDescriptor[] {
  const controls = Array.from(
    document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
      "input, textarea, select"
    )
  );
  const seenRadioNames = new Set<string>();
  const fields: FieldDescriptor[] = [];

  for (const control of controls) {
    const fieldType = classify(control);
    if (control.disabled || (fieldType !== "file" && !isVisible(control))) {
      continue;
    }
    if (fieldType === "unknown") {
      continue;
    }
    if (fieldType === "radio" && control instanceof HTMLInputElement && control.name) {
      if (seenRadioNames.has(control.name)) {
        continue;
      }
      seenRadioNames.add(control.name);
    }
    const label = labelFor(control);
    const descriptor: FieldDescriptor = {
      id: stableId(control, fields.length),
      label,
      selector: cssPath(control),
      fieldType,
      required: control.required || control.getAttribute("aria-required") === "true",
      options: optionsFor(control),
      value: currentValue(control),
      sensitive: fieldType === "password" || SENSITIVE_PATTERN.test(label),
      debug: {
        tag: control.tagName.toLowerCase(),
        type: control instanceof HTMLInputElement ? control.type : control.tagName.toLowerCase(),
        visible: isVisible(control)
      }
    };
    if (control.name) {
      descriptor.name = control.name;
    }
    if (fieldType === "radio" && control instanceof HTMLInputElement && control.name) {
      descriptor.groupSelector = `input[type="radio"][name="${CSS.escape(control.name)}"]`;
    }
    fields.push(descriptor);
  }
  return fields;
}

function classify(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): FieldType {
  if (control instanceof HTMLTextAreaElement) {
    return "textarea";
  }
  if (control instanceof HTMLSelectElement) {
    return "select";
  }
  const type = (control.getAttribute("type") || "text").toLowerCase();
  if (["button", "submit", "reset", "hidden", "image"].includes(type)) {
    return "unknown";
  }
  if (["radio", "checkbox", "file", "password"].includes(type)) {
    return type as FieldType;
  }
  return "text";
}

function optionsFor(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): string[] {
  if (control instanceof HTMLSelectElement) {
    return Array.from(control.options).map((option) => option.label || option.value).filter(Boolean);
  }
  if (control instanceof HTMLInputElement && control.type === "radio" && control.name) {
    return Array.from(document.querySelectorAll<HTMLInputElement>(`input[type="radio"][name="${CSS.escape(control.name)}"]`))
      .map((radio) => labelFor(radio) || radio.value)
      .filter(Boolean);
  }
  return [];
}

function currentValue(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): unknown {
  if (control instanceof HTMLInputElement && control.type === "checkbox") {
    return control.checked;
  }
  if (control instanceof HTMLInputElement && control.type === "file") {
    return undefined;
  }
  return control.value || undefined;
}

function stableId(control: Element, index: number): string {
  return control.id || control.getAttribute("name") || `field-${index + 1}`;
}

function hasButtonLike(pattern: RegExp): boolean {
  const controls = Array.from(document.querySelectorAll<HTMLElement>("button, input[type='button'], input[type='submit'], a, [role='button']"));
  return controls.some((control) => {
    const text = control instanceof HTMLInputElement ? control.value : control.textContent || "";
    const qa = control.getAttribute("data-qa") || control.getAttribute("data-automation-id") || "";
    const disabled = control.hasAttribute("disabled") || control.getAttribute("aria-disabled") === "true";
    return isVisible(control) && !disabled && pattern.test(`${text} ${qa}`);
  });
}

function inferStep(): number {
  const active = document.querySelector("[aria-current='step'], .active, [data-active='true']");
  const text = active?.textContent || document.body.textContent || "";
  const match = text.match(/\b(?:step|page)\s+(\d+)\b/i);
  return match ? Number(match[1]) : 1;
}
