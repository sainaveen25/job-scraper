import { MESSAGE_TYPES } from "../shared/constants";
import type { RuntimeRequest, RuntimeResponse } from "../shared/models";
import { detectPage } from "./field_detector";
import { continuePage, fillFields, submitAfterConfirmation } from "./field_filler";

const debugHistory: string[] = [];

chrome.runtime.onMessage.addListener(
  (request: RuntimeRequest, _sender, sendResponse: (response: RuntimeResponse) => void) => {
    void handleMessage(request)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error: unknown) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    return true;
  }
);

void chrome.runtime.sendMessage({ type: MESSAGE_TYPES.contentReady, payload: detectPage() });

async function handleMessage(request: RuntimeRequest): Promise<unknown> {
  switch (request.type) {
    case MESSAGE_TYPES.detectPage:
      return withDebug("detect_page", detectPage());
    case MESSAGE_TYPES.fillPage:
      return withDebug("fill_page", await fillFields((request.payload as { instructions?: [] } | undefined)?.instructions ?? []));
    case MESSAGE_TYPES.continuePage:
      return withDebug("continue_page", { moved: await continuePage() });
    case MESSAGE_TYPES.prepareSubmit:
      return withDebug("prepare_submit", detectPage());
    case MESSAGE_TYPES.submitConfirmed:
      return withDebug("submit_confirmed", { submitted: await submitAfterConfirmation() });
    default:
      throw new Error(`Unsupported ApplyMate content message: ${request.type}`);
  }
}

function withDebug<T extends object>(event: string, payload: T): T & { applymateDebugLogs: string[] } {
  debugHistory.push(`${new Date().toISOString()} ${event}`);
  return { ...payload, applymateDebugLogs: debugHistory.slice(-50) };
}
