import { MESSAGE_TYPES } from "../shared/constants";
import { detectPlatform } from "../shared/platform";
import { saveLastTab } from "../shared/storage";

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
  }
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
