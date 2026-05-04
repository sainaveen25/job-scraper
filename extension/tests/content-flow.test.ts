import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

import { detectPage } from "../content/field_detector";
import { continuePage, fillFields } from "../content/field_filler";

function loadFixture(name: string, url: string): void {
  const html = readFileSync(join("tests", "fixtures", name), "utf8");
  const dom = new JSDOM(html, { url, pretendToBeVisual: true });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    location: dom.window.location,
    Node: dom.window.Node,
    Element: dom.window.Element,
    HTMLElement: dom.window.HTMLElement,
    HTMLInputElement: dom.window.HTMLInputElement,
    HTMLTextAreaElement: dom.window.HTMLTextAreaElement,
    HTMLSelectElement: dom.window.HTMLSelectElement,
    CSS: dom.window.CSS || { escape: (value: string) => value.replace(/"/g, '\\"') },
    Event: dom.window.Event
  });
  Object.defineProperty(dom.window.HTMLElement.prototype, "getBoundingClientRect", {
    configurable: true,
    value() {
      if ((this as HTMLElement).style.display === "none") {
        return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
      }
      return { width: 100, height: 20, top: 0, left: 0, right: 100, bottom: 20 };
    }
  });
}

test("Greenhouse detects fields, hidden resume input, radios, and submit state", () => {
  loadFixture("greenhouse-step.html", "https://boards.greenhouse.io/acme/jobs/123");

  const page = detectPage();

  assert.equal(page.platform, "greenhouse");
  assert.equal(page.support, "supported");
  assert.equal(page.hasSubmit, true);
  assert.equal(page.hasNext, false);
  assert.equal(page.fields.some((field) => field.fieldType === "file" && field.label.includes("Resume")), true);
  assert.equal(page.fields.some((field) => field.fieldType === "radio" && field.options.includes("Yes")), true);
  assert.equal(page.debugLogs.some((line) => line.startsWith("fields=")), true);
});

test("Greenhouse fills text/radio fields and requests manual resume upload", async () => {
  loadFixture("greenhouse-step.html", "https://boards.greenhouse.io/acme/jobs/123");
  const page = detectPage();

  const result = await fillFields([
    { selector: "#first_name", label: "First Name", fieldType: "text", value: "Ada", source: "profile" },
    { selector: "#email", label: "Email", fieldType: "text", value: "ada@example.com", source: "profile" },
    {
      selector: "#work-auth-yes",
      groupSelector: 'input[type="radio"][name="job_application[answers_attributes][1][boolean_value]"]',
      label: "Authorized",
      fieldType: "radio",
      value: "Yes",
      source: "profile"
    },
    {
      selector: "#resume",
      label: "Resume",
      fieldType: "file",
      value: "resume_1",
      source: "resume",
      requiresReview: true
    }
  ]);

  assert.equal((document.querySelector("#first_name") as HTMLInputElement).value, "Ada");
  assert.equal((document.querySelector("#email") as HTMLInputElement).value, "ada@example.com");
  assert.equal((document.querySelector("#work-auth-yes") as HTMLInputElement).checked, true);
  assert.equal(result.filled, 3);
  assert.equal(result.uploadRequested, 1);
});

test("Lever detects application-label fields, select, checkbox, resume, and continue", async () => {
  loadFixture("lever-step.html", "https://jobs.lever.co/acme/abc");

  const page = detectPage();

  assert.equal(page.platform, "lever");
  assert.equal(page.support, "supported");
  assert.equal(page.hasNext, true);
  assert.equal(page.hasSubmit, false);
  assert.equal(page.fields.some((field) => field.label === "Full name"), true);
  assert.equal(page.fields.some((field) => field.fieldType === "select" && field.options.includes("United States")), true);
  assert.equal(page.fields.some((field) => field.fieldType === "checkbox"), true);
  assert.equal(await continuePage(), true);
});

test("Lever fills full page controls and keeps submit separate", async () => {
  loadFixture("lever-step.html", "https://jobs.lever.co/acme/abc");

  const result = await fillFields([
    { selector: 'input[name="name"]', label: "Full name", fieldType: "text", value: "Ada Lovelace", source: "profile" },
    { selector: 'input[name="email"]', label: "Email", fieldType: "text", value: "ada@example.com", source: "profile" },
    { selector: "#country", label: "Country", fieldType: "select", value: "United States", source: "profile" },
    {
      selector: 'input[name="sponsorship"]',
      groupSelector: 'input[type="radio"][name="sponsorship"]',
      label: "Sponsorship",
      fieldType: "radio",
      value: "No",
      source: "profile"
    },
    { selector: 'input[name="privacy"]', label: "Privacy", fieldType: "checkbox", value: true, source: "memory" }
  ]);

  assert.equal((document.querySelector('input[name="name"]') as HTMLInputElement).value, "Ada Lovelace");
  assert.equal((document.querySelector("#country") as HTMLSelectElement).value, "US");
  assert.equal((document.querySelector('input[name="sponsorship"][value="No"]') as HTMLInputElement).checked, true);
  assert.equal((document.querySelector('input[name="privacy"]') as HTMLInputElement).checked, true);
  assert.equal(result.filled, 5);
});
