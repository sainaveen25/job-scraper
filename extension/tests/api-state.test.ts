import test from "node:test";
import assert from "node:assert/strict";

import type { ApplySessionPayload, PageDetection } from "../shared/models";

type Store = Record<string, unknown>;

const localStore: Store = {};
const sessionStore: Store = {};
let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

function setupChromeMock(): void {
  Object.assign(globalThis, {
    chrome: {
      storage: {
        local: storageArea(localStore),
        session: storageArea(sessionStore)
      }
    }
  });
}

function storageArea(store: Store) {
  return {
    async get(key: string) {
      return { [key]: store[key] };
    },
    async set(value: Store) {
      Object.assign(store, value);
    },
    async remove(key: string) {
      delete store[key];
    }
  };
}

function resetStores(): void {
  for (const key of Object.keys(localStore)) {
    delete localStore[key];
  }
  for (const key of Object.keys(sessionStore)) {
    delete sessionStore[key];
  }
  fetchCalls = [];
}

const detection: PageDetection = {
  platform: "greenhouse",
  support: "supported",
  currentUrl: "https://boards.greenhouse.io/acme/jobs/123",
  pageTitle: "Backend Engineer",
  fields: [{ id: "first", label: "First Name", selector: "#first", fieldType: "text", required: true, options: [], sensitive: false }],
  hasNext: false,
  hasSubmit: true,
  step: 1,
  debugLogs: []
};

function sessionPayload(overrides: Partial<ApplySessionPayload> = {}): ApplySessionPayload {
  return {
    sessionId: "session_1",
    extensionToken: "short-lived-token",
    platform: "greenhouse",
    currentUrl: "https://boards.greenhouse.io/acme/jobs/123",
    job: {
      id: "job_1",
      title: "Backend Engineer",
      company: "Acme",
      applyUrl: "https://boards.greenhouse.io/acme/jobs/123"
    },
    resume: {
      id: "resume_1",
      fileName: "backend.pdf",
      mimeType: "application/pdf"
    },
    fillInstructions: [],
    unresolvedFields: [],
    ...overrides
  };
}

test("extension fill requires website-created Apply Session state", async () => {
  setupChromeMock();
  resetStores();
  const { fillCurrentPage } = await import("../shared/api");

  await assert.rejects(() => fillCurrentPage(detection), /Start this application from ApplyMate first/);
  assert.equal(fetchCalls.length, 0);
});

test("extension fill preserves selected job and tailored resume context", async () => {
  setupChromeMock();
  resetStores();
  const { saveSettings, saveSessionState } = await import("../shared/storage");
  const { fillCurrentPage } = await import("../shared/api");
  await saveSettings({ apiBaseUrl: "https://applymate.test", userId: "user_1", userSessionToken: "user-session-token" });
  await saveSessionState({ sessionId: "session_1", extensionToken: "short-lived-token" });
  const existing = sessionPayload();

  globalThis.fetch = async (url: string | URL | Request, init?: RequestInit) => {
    fetchCalls.push({ url: String(url), init });
    const body = String(url).endsWith("/fill-page")
      ? { ...existing, fillInstructions: [{ selector: "#first", label: "First Name", fieldType: "text", value: "Ada", source: "profile" }] }
      : existing;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  const response = await fillCurrentPage(detection);

  assert.equal(response.job?.id, "job_1");
  assert.equal(response.resume?.id, "resume_1");
  assert.equal(response.fillInstructions?.[0]?.selector, "#first");
  assert.equal(fetchCalls.length, 2);
});

test("extension blocks stale Apply Session state on a different job URL", async () => {
  setupChromeMock();
  resetStores();
  const { saveSettings, saveSessionState } = await import("../shared/storage");
  const { fillCurrentPage } = await import("../shared/api");
  await saveSettings({ apiBaseUrl: "https://applymate.test", userId: "user_1", userSessionToken: "user-session-token" });
  await saveSessionState({ sessionId: "session_1", extensionToken: "short-lived-token" });
  globalThis.fetch = async (url: string | URL | Request, init?: RequestInit) => {
    fetchCalls.push({ url: String(url), init });
    return new Response(JSON.stringify(sessionPayload({ currentUrl: "https://jobs.lever.co/acme/abc" })), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  await assert.rejects(() => fillCurrentPage(detection), /different job page/);
  assert.equal(fetchCalls.length, 1);
});

test("extension blocks sessions missing the tailored resume", async () => {
  setupChromeMock();
  resetStores();
  const { saveSettings, saveSessionState } = await import("../shared/storage");
  const { fillCurrentPage } = await import("../shared/api");
  await saveSettings({ apiBaseUrl: "https://applymate.test", userId: "user_1", userSessionToken: "user-session-token" });
  await saveSessionState({ sessionId: "session_1", extensionToken: "short-lived-token" });
  globalThis.fetch = async (url: string | URL | Request, init?: RequestInit) => {
    fetchCalls.push({ url: String(url), init });
    return new Response(JSON.stringify(sessionPayload({ resume: null })), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  await assert.rejects(() => fillCurrentPage(detection), /missing the selected job or tailored resume/);
  assert.equal(fetchCalls.length, 1);
});
