import { MESSAGE_TYPES } from "../shared/constants";
import { detectPlatform } from "../shared/platform";
import type { ApplySessionPayload, PageDetection } from "../shared/models";
import { fillCurrentPage, startApplySession } from "../shared/api";
import { saveLastTab, updateSessionState } from "../shared/storage";

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) {
    return;
  }
  await saveLastTab(tab.id);
  await ensureContentScript(tab.id);
  await chrome.sidePanel.open({ tabId: tab.id });
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  await saveLastTab(tabId);
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type === MESSAGE_TYPES.contentReady && sender.tab?.id) {
    void saveLastTab(sender.tab.id);
    void autoLoadActiveSession(sender.tab.id, message.payload as PageDetection);
  }
});

chrome.runtime.onMessageExternal.addListener((message, _sender, sendResponse) => {
  void handleExternalMessage(message)
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error: unknown) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
  return true;
});

async function ensureContentScript(tabId: number): Promise<void> {
  const tab = await chrome.tabs.get(tabId);
  const url = tab.url || "";
  const { support } = detectPlatform(url);
  if (support !== "manual_assist") {
    return;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content/content_script.js"]
    });
  } catch {
    // Chrome blocks injection on internal pages and restricted schemes. The side panel will show a manual message.
  }
}

async function handleExternalMessage(message: unknown): Promise<ApplySessionPayload | { status: string }> {
  if (!message || typeof message !== "object" || (message as { type?: string }).type !== MESSAGE_TYPES.sessionHandoff) {
    throw new Error("Unsupported ApplyMate extension message.");
  }
  const payload = (message as { payload?: Partial<ApplySessionPayload> }).payload;
  if (!payload?.sessionId) {
    throw new Error("ApplyMate handoff requires a sessionId.");
  }
  await updateSessionState({
    sessionId: payload.sessionId,
    extensionToken: payload.extensionToken,
    currentUrl: payload.currentUrl || payload.applyUrl || payload.job?.applyUrl || payload.job?.jobUrl,
    selectedJobId: payload.job?.id,
    lastPlatform: payload.platform
  });
  return { status: "handoff_saved" };
}

async function autoLoadActiveSession(tabId: number, detection: PageDetection | undefined): Promise<void> {
  if (!detection || detection.support === "manual_assist") {
    return;
  }
  try {
    await startApplySession(detection);
    const session = await fillCurrentPage(detection);
    if (session.fillInstructions?.length) {
      await chrome.tabs.sendMessage(tabId, { type: MESSAGE_TYPES.fillPage, payload: { instructions: session.fillInstructions } });
    }
  } catch {
    // The side panel displays detailed mismatch/sign-in/session errors when opened.
  }
}
