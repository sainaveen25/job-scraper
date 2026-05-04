import { getAuthHeaders, authenticatedPayload } from "./auth";
import type { ApplyMateSettings, ApplySessionPayload, PageDetection } from "./models";
import { clearSessionState, getSettings, getSessionState, updateSessionState } from "./storage";

type JsonValue = Record<string, unknown>;

export async function createApplySession(detection: PageDetection): Promise<ApplySessionPayload> {
  const settings = await requireSignedInSettings();
  const payload = await request<ApplySessionPayload>("/api/extension/apply-session/create", {
    method: "POST",
    body: {
      ...authenticatedPayload(settings),
      platform: detection.platform,
      job: {
        applyUrl: detection.currentUrl,
        jobUrl: detection.currentUrl,
        title: documentTitleFallback(detection.pageTitle),
        company: ""
      },
      profile: {},
      fieldMemory: []
    }
  });
  await updateSessionState({
    sessionId: payload.sessionId,
    extensionToken: payload.extensionToken,
    currentUrl: payload.currentUrl || payload.job?.applyUrl || payload.job?.jobUrl || detection.currentUrl,
    lastPlatform: payload.platform
  });
  return payload;
}

export async function getApplySession(): Promise<ApplySessionPayload | null> {
  const state = await getSessionState();
  if (!state.sessionId) {
    return null;
  }
  return request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}`, {
    method: "GET",
    extensionToken: state.extensionToken
  });
}

export async function startApplySession(detection: PageDetection): Promise<ApplySessionPayload> {
  const state = await ensureSession(detection);
  return request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}/start`, {
    method: "POST",
    extensionToken: state.extensionToken,
    body: {
      currentUrl: detection.currentUrl,
      pageTitle: detection.pageTitle,
      platform: detection.platform
    }
  });
}

export async function fillCurrentPage(detection: PageDetection): Promise<ApplySessionPayload> {
  const state = await ensureSession(detection);
  const payload = await request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}/fill-page`, {
    method: "POST",
    extensionToken: state.extensionToken,
    body: {
      currentUrl: detection.currentUrl,
      pageTitle: detection.pageTitle,
      platform: detection.platform,
      fields: detection.fields,
      hasNext: detection.hasNext,
      hasSubmit: detection.hasSubmit,
      step: detection.step,
      debugLogs: detection.debugLogs
    }
  });
  if (payload.extensionToken) {
    await updateSessionState({ extensionToken: payload.extensionToken });
  }
  return payload;
}

export async function continueApplySession(): Promise<ApplySessionPayload> {
  const state = await requireSessionState();
  return request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}/continue`, {
    method: "POST",
    extensionToken: state.extensionToken,
    body: {}
  });
}

export async function saveUnknownAnswer(args: {
  label: string;
  normalizedQuestion?: string;
  value: unknown;
  answerType: string;
  platform?: string;
}): Promise<ApplySessionPayload> {
  const state = await requireSessionState();
  return request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}/save-answer`, {
    method: "POST",
    extensionToken: state.extensionToken,
    body: {
      originalQuestion: args.label,
      normalizedQuestion: args.normalizedQuestion,
      answer: args.value,
      answerType: args.answerType,
      platform: args.platform
    }
  });
}

export async function confirmSubmit(): Promise<ApplySessionPayload> {
  const state = await requireSessionState();
  return request<ApplySessionPayload>(`/api/extension/apply-session/${state.sessionId}/submit`, {
    method: "POST",
    extensionToken: state.extensionToken,
    body: { confirm: true }
  });
}

async function ensureSession(detection: PageDetection): Promise<{ sessionId: string; extensionToken?: string | undefined }> {
  const state = await getSessionState();
  if (!state.sessionId) {
    throw new Error("Start this application from ApplyMate first so the selected job and tailored resume are available.");
  }
  const session = await getApplySession();
  if (!session) {
    await clearSessionState();
    throw new Error("ApplyMate session was not found. Reopen this application from ApplyMate.");
  }
  if (!sessionHasSelectedContext(session)) {
    throw new Error("ApplyMate session is missing the selected job or tailored resume. Reopen this application from ApplyMate.");
  }
  if (!sessionMatchesPage(session, detection)) {
    throw new Error("This ApplyMate session belongs to a different job page. Reopen the selected job from ApplyMate.");
  }
  const extensionToken = session.extensionToken || state.extensionToken;
  await updateSessionState({
    sessionId: session.sessionId,
    extensionToken,
    currentUrl: session.currentUrl || session.job?.applyUrl || session.job?.jobUrl || detection.currentUrl,
    selectedJobId: session.job?.id,
    lastPlatform: session.platform
  });
  return { sessionId: session.sessionId, extensionToken };
}

function sessionHasSelectedContext(session: ApplySessionPayload): boolean {
  return Boolean(session.job?.id && (session.resume?.id || session.resume?.fileName || session.resume?.label));
}

function sessionMatchesPage(session: ApplySessionPayload, detection: PageDetection): boolean {
  const sessionUrl = String(session.currentUrl || session.job?.applyUrl || session.job?.jobUrl || "");
  if (!sessionUrl) {
    return true;
  }
  try {
    const expected = new URL(sessionUrl);
    const actual = new URL(detection.currentUrl);
    return expected.hostname === actual.hostname && samePathPrefix(expected.pathname, actual.pathname);
  } catch {
    return sessionUrl === detection.currentUrl;
  }
}

function samePathPrefix(expectedPath: string, actualPath: string): boolean {
  const expected = normalizePath(expectedPath);
  const actual = normalizePath(actualPath);
  return actual.startsWith(expected) || expected.startsWith(actual);
}

function normalizePath(value: string): string {
  return value.replace(/\/apply\/?$/i, "").replace(/\/$/g, "");
}

async function requireSessionState(): Promise<{ sessionId: string; extensionToken?: string | undefined }> {
  const state = await getSessionState();
  if (!state.sessionId) {
    throw new Error("No ApplyMate apply session has been created for this tab.");
  }
  return { sessionId: state.sessionId, extensionToken: state.extensionToken };
}

async function requireSignedInSettings(): Promise<ApplyMateSettings> {
  const settings = await getSettings();
  if (!settings.userId || !settings.userSessionToken) {
    throw new Error("Sign in to ApplyMate before creating an apply session.");
  }
  return settings;
}

async function request<T>(
  path: string,
  options: { method: "GET" | "POST"; body?: JsonValue | undefined; extensionToken?: string | undefined }
): Promise<T> {
  const settings = await getSettings();
  const url = new URL(path, withTrailingSlash(settings.apiBaseUrl)).toString();
  const init: RequestInit = {
    method: options.method,
    headers: await getAuthHeaders(options.extensionToken),
    credentials: "include"
  };
  if (options.body) {
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`ApplyMate API request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

function withTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`;
}

function documentTitleFallback(title: string): string {
  return title.replace(/\s+/g, " ").trim() || "Job application";
}
