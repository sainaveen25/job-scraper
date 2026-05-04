import type { FillInstruction } from "../shared/models";

export async function fillFields(instructions: FillInstruction[]): Promise<{ filled: number; failed: number; uploadRequested: number; logs: string[] }> {
  let filled = 0;
  let failed = 0;
  let uploadRequested = 0;
  const logs: string[] = [];
  for (const instruction of instructions) {
    try {
      const result = await fillOne(instruction);
      logs.push(`${instruction.fieldType}:${instruction.label}:${result}`);
      if (result === "filled") {
        filled += 1;
      } else if (result === "upload_requested") {
        uploadRequested += 1;
      } else {
        failed += 1;
      }
    } catch {
      failed += 1;
      logs.push(`${instruction.fieldType}:${instruction.label}:failed`);
    }
  }
  return { filled, failed, uploadRequested, logs };
}

export async function continuePage(): Promise<boolean> {
  return clickFirst(/next|continue|save and continue|review/i);
}

export async function submitAfterConfirmation(): Promise<boolean> {
  return clickFirst(/submit|submit application|apply|send/i);
}

async function fillOne(instruction: FillInstruction): Promise<"filled" | "upload_requested" | "skipped"> {
  if (!instruction.selector) {
    return "skipped";
  }
  const element = document.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(instruction.selector);
  if (!element || instruction.fieldType === "password") {
    return "skipped";
  }
  if (instruction.fieldType === "file") {
    if (element.tagName.toLowerCase() === "input") {
      element.dataset.applymateResumeUploadRequested = "true";
      try {
        element.scrollIntoView({ block: "center", inline: "nearest" });
        element.click();
      } catch {
        // Browsers may reject synthetic file picker opens. The marker still lets the UI explain manual upload.
      }
      return "upload_requested";
    }
    return "skipped";
  }
  if (element instanceof HTMLSelectElement) {
    selectBest(element, String(instruction.value ?? ""));
  } else if (element instanceof HTMLInputElement && element.type === "checkbox") {
    element.checked = Boolean(instruction.value);
  } else if (element instanceof HTMLInputElement && element.type === "radio") {
    fillRadio(element, String(instruction.value ?? ""), instruction.groupSelector);
  } else {
    element.value = String(instruction.value ?? "");
  }
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  return "filled";
}

function selectBest(select: HTMLSelectElement, value: string): void {
  const lower = value.toLowerCase();
  const option = Array.from(select.options).find((item) => {
    const label = (item.label || item.textContent || "").toLowerCase();
    return label === lower || label.includes(lower) || lower.includes(label) || item.value.toLowerCase() === lower;
  });
  if (option) {
    select.value = option.value;
  }
}

function fillRadio(radio: HTMLInputElement, value: string, groupSelector?: string): void {
  const group = groupSelector
    ? Array.from(document.querySelectorAll<HTMLInputElement>(groupSelector))
    : radio.name
      ? Array.from(document.querySelectorAll<HTMLInputElement>(`input[type="radio"][name="${CSS.escape(radio.name)}"]`))
    : [radio];
  const lower = value.toLowerCase();
  const match = group.find((candidate) => {
    const label = labelText(candidate).toLowerCase();
    return candidate.value.toLowerCase() === lower || label.includes(lower) || lower.includes(label);
  });
  (match || radio).checked = true;
}

function clickFirst(pattern: RegExp): boolean {
  const controls = Array.from(document.querySelectorAll<HTMLElement>("button, input[type='button'], input[type='submit'], a, [role='button']"));
  const target = controls.find((control) => {
    const text = control instanceof HTMLInputElement ? control.value : control.textContent || "";
    const qa = control.getAttribute("data-qa") || control.getAttribute("data-automation-id") || "";
    const disabled = control.hasAttribute("disabled") || control.getAttribute("aria-disabled") === "true";
    return !disabled && pattern.test(`${text} ${qa}`);
  });
  if (!target) {
    return false;
  }
  target.click();
  return true;
}

function labelText(input: HTMLInputElement): string {
  if (input.id) {
    const label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
    if (label?.textContent) {
      return label.textContent;
    }
  }
  return input.closest("label")?.textContent || input.value;
}
