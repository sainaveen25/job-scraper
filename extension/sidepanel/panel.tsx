import {
  confirmSubmit,
  continueApplySession,
  fillCurrentPage,
  getApplySession,
  saveUnknownAnswer,
  startApplySession
} from "../shared/api";
import { saveApplyMateSession } from "../shared/auth";
import { MESSAGE_TYPES } from "../shared/constants";
import type { ApplySessionPayload, FieldDescriptor, PageDetection, RuntimeResponse, UnknownFieldPayload } from "../shared/models";
import { getLastTab, updateSessionState } from "../shared/storage";

type State = {
  detection?: PageDetection;
  session?: ApplySessionPayload | null | undefined;
  status: string;
  error?: string | undefined;
  busy: boolean;
};

const state: State = {
  status: "Ready",
  busy: false
};

const app = document.getElementById("app");
if (!app) {
  throw new Error("ApplyMate panel root missing.");
}
const root = app;

void refresh();

async function refresh(): Promise<void> {
  await withBusy("Detecting current page", async () => {
    state.detection = await sendToCurrentTab<PageDetection>(MESSAGE_TYPES.detectPage);
    state.session = await getApplySession().catch(() => null);
    if (state.detection) {
      state.session = await startApplySession(state.detection).catch(() => state.session);
    }
  });
}

function render(): void {
  const detection = state.detection;
  const session = state.session;
  const unresolved = session?.unresolvedFields ?? [];
  root.innerHTML = `
    <section class="header">
      <div class="brand">
        <strong>ApplyMate AI</strong>
        <span class="muted">Assisted autofill</span>
      </div>
      <span class="badge ${badgeClass(detection?.support)}">${badgeLabel(detection)}</span>
    </section>

    <section class="card">
      <div class="row"><span class="muted">Job</span><strong>${escapeHtml(session?.job?.title || detection?.pageTitle || "Current application")}</strong></div>
      <div class="row"><span class="muted">Company</span><span>${escapeHtml(String(session?.job?.company || "Not set"))}</span></div>
      <div class="row"><span class="muted">Resume</span><span>${escapeHtml(String(session?.resume?.fileName || session?.resume?.label || "No resume selected"))}</span></div>
    </section>

    <section class="card status ${state.error ? "error" : ""}">
      <strong>${escapeHtml(state.error ? "Needs attention" : state.status)}</strong>
      <div class="muted">${escapeHtml(progressSummary(session, detection))}</div>
      <div class="muted">${escapeHtml(debugSummary(detection))}</div>
    </section>

    <section class="card">
      <strong>ApplyMate session</strong>
      <div class="field-list">
        <div class="field">
          <label>API base URL</label>
          <input id="apiBaseUrl" autocomplete="off" placeholder="https://your-app.lovable.app">
        </div>
        <div class="field">
          <label>User ID</label>
          <input id="userId" autocomplete="username" placeholder="ApplyMate user ID">
        </div>
        <div class="field">
          <label>Session token</label>
          <input id="sessionToken" type="password" autocomplete="current-password" placeholder="ApplyMate session token">
        </div>
        <div class="field">
          <label>Apply Session ID</label>
          <input id="applySessionId" autocomplete="off" placeholder="Created from ApplyMate website">
        </div>
        <div class="field">
          <label>Extension token</label>
          <input id="extensionToken" type="password" autocomplete="off" placeholder="Optional short-lived token">
        </div>
        <button class="button secondary" id="saveSession">Save session</button>
      </div>
    </section>

    <section class="card actions">
      <button class="button" id="fill" ${state.busy ? "disabled" : ""}>Fill current page</button>
      <button class="button secondary" id="continue" ${state.busy ? "disabled" : ""}>Continue</button>
      <button class="button secondary" id="review" ${state.busy ? "disabled" : ""}>Review fields</button>
      <button class="button warning" id="submit" ${state.busy ? "disabled" : ""}>Submit with confirmation</button>
    </section>

    <section class="card">
      <strong>Detected fields</strong>
      <div class="muted">${detection?.fields.length ?? 0} on this page</div>
      <div class="field-list">
        ${(detection?.fields ?? []).slice(0, 6).map(renderDetectedField).join("")}
      </div>
    </section>

    <section class="card">
      <strong>Unresolved fields</strong>
      <div class="muted">${unresolved.length ? "Answer and save for next time." : "Nothing unresolved right now."}</div>
      <div class="field-list">
        ${unresolved.map(renderUnknownField).join("")}
      </div>
    </section>
  `;
  bindEvents();
}

function bindEvents(): void {
  document.getElementById("fill")?.addEventListener("click", () => void fillPage());
  document.getElementById("continue")?.addEventListener("click", () => void continuePage());
  document.getElementById("review")?.addEventListener("click", () => void refresh());
  document.getElementById("submit")?.addEventListener("click", () => void submitWithConfirmation());
  document.getElementById("saveSession")?.addEventListener("click", () => void saveSessionSettings());
  for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>("[data-save-answer]"))) {
    button.addEventListener("click", () => void saveAnswer(button.dataset.saveAnswer || ""));
  }
}

async function saveSessionSettings(): Promise<void> {
  const apiBaseUrl = document.querySelector<HTMLInputElement>("#apiBaseUrl")?.value.trim();
  const userId = document.querySelector<HTMLInputElement>("#userId")?.value.trim();
  const sessionToken = document.querySelector<HTMLInputElement>("#sessionToken")?.value.trim();
  const applySessionId = document.querySelector<HTMLInputElement>("#applySessionId")?.value.trim();
  const extensionToken = document.querySelector<HTMLInputElement>("#extensionToken")?.value.trim();
  if (!userId || !sessionToken) {
    state.error = "User ID and session token are required.";
    render();
    return;
  }
  await withBusy("Saving ApplyMate session", async () => {
    await saveApplyMateSession(userId, sessionToken, apiBaseUrl || undefined);
    if (applySessionId) {
      await updateSessionState({
        sessionId: applySessionId,
        extensionToken: extensionToken || undefined,
        currentUrl: state.detection?.currentUrl,
        lastPlatform: state.detection?.platform
      });
      state.session = await getApplySession().catch(() => state.session);
    }
    state.status = "ApplyMate session saved";
  });
}

async function fillPage(): Promise<void> {
  await withBusy("Filling current page", async () => {
    const detection = await sendToCurrentTab<PageDetection>(MESSAGE_TYPES.detectPage);
    const session = await fillCurrentPage(detection);
    if (session.fillInstructions?.length) {
      await sendToCurrentTab(MESSAGE_TYPES.fillPage, { instructions: session.fillInstructions });
    }
    state.detection = detection;
    state.session = session;
    state.status = `Filled ${session.fillInstructions?.length ?? 0} fields`;
  });
}

async function continuePage(): Promise<void> {
  await withBusy("Continuing", async () => {
    await continueApplySession();
    await sendToCurrentTab(MESSAGE_TYPES.continuePage);
    await refresh();
  });
}

async function submitWithConfirmation(): Promise<void> {
  const confirmed = window.confirm("Submit this application now? ApplyMate will click the final submit control on this page.");
  if (!confirmed) {
    state.status = "Submit cancelled";
    render();
    return;
  }
  await withBusy("Submitting", async () => {
    const response = await confirmSubmit();
    if (!response.submitInstruction?.requiresExplicitConfirmation) {
      throw new Error("Backend did not confirm submit readiness.");
    }
    await sendToCurrentTab(MESSAGE_TYPES.submitConfirmed);
    state.session = response;
    state.status = "Submit action sent";
  });
}

async function saveAnswer(index: string): Promise<void> {
  const field = state.session?.unresolvedFields?.[Number(index)];
  const input = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(`[data-answer-input="${index}"]`);
  if (!field || !input) {
    return;
  }
  await withBusy("Saving answer", async () => {
    const payload = {
      label: field.field.label,
      value: input.value,
      answerType: field.field.fieldType
    };
    state.session = await saveUnknownAnswer(state.detection?.platform ? { ...payload, platform: state.detection.platform } : payload);
    await fillPage();
  });
}

async function withBusy(status: string, fn: () => Promise<void>): Promise<void> {
  state.busy = true;
  state.status = status;
  state.error = undefined;
  render();
  try {
    await fn();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.busy = false;
    render();
  }
}

async function sendToCurrentTab<T = unknown>(type: string, payload?: unknown): Promise<T> {
  const tabId = await getLastTab();
  if (!tabId) {
    throw new Error("Open a job application tab, then click ApplyMate again.");
  }
  const response = (await chrome.tabs.sendMessage(tabId, { type, payload })) as RuntimeResponse<T>;
  if (!response.ok) {
    throw new Error(response.error || "Content script request failed.");
  }
  return response.data as T;
}

function renderDetectedField(field: FieldDescriptor): string {
  return `<div class="field"><strong>${escapeHtml(field.label || field.name || field.id)}</strong><div class="muted">${field.fieldType}${field.required ? " · required" : ""}${field.sensitive ? " · review" : ""}</div></div>`;
}

function renderUnknownField(field: UnknownFieldPayload, index: number): string {
  const protectedQuestion = field.reason.includes("sensitive") || field.field.sensitive;
  return `
    <div class="field">
      <label>${escapeHtml(field.field.label || field.field.name || "Unknown question")}</label>
      <div class="muted">${escapeHtml(field.reason)}</div>
      <textarea data-answer-input="${index}" ${protectedQuestion ? "placeholder=\"Protected question: review manually before saving\"" : "placeholder=\"Answer\""}></textarea>
      <button class="button secondary" data-save-answer="${index}" ${protectedQuestion ? "disabled" : ""}>Save answer</button>
    </div>
  `;
}

function progressSummary(session?: ApplySessionPayload | null, detection?: PageDetection): string {
  const filled = session?.fieldsFilled?.length ?? 0;
  const unresolved = session?.unresolvedFields?.length ?? 0;
  const detected = detection?.fields.length ?? 0;
  return `${detected} detected · ${filled} filled · ${unresolved} unresolved`;
}

function debugSummary(detection?: PageDetection): string {
  if (!detection?.debugLogs?.length) {
    return "No page debug logs yet";
  }
  return detection.debugLogs.join(" · ");
}

function badgeLabel(detection?: PageDetection): string {
  if (!detection) {
    return "No page";
  }
  if (detection.support === "supported") {
    return `${detection.platform} · Supported`;
  }
  if (detection.support === "partial") {
    return `${detection.platform} · Partial`;
  }
  return "Manual Assist";
}

function badgeClass(support?: string): string {
  if (support === "supported") {
    return "supported";
  }
  if (support === "partial") {
    return "partial";
  }
  return "";
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
