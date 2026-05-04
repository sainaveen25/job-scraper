import { DEFAULT_API_BASE_URL, STORAGE_KEYS } from "./constants";
import type { ApplyMateSettings, ApplySessionState } from "./models";

export async function getSettings(): Promise<ApplyMateSettings> {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.settings);
  return {
    apiBaseUrl: DEFAULT_API_BASE_URL,
    ...(stored[STORAGE_KEYS.settings] ?? {})
  };
}

export async function saveSettings(settings: ApplyMateSettings): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEYS.settings]: settings });
}

export async function getSessionState(): Promise<ApplySessionState> {
  const stored = await chrome.storage.session.get(STORAGE_KEYS.session);
  return stored[STORAGE_KEYS.session] ?? {};
}

export async function saveSessionState(state: ApplySessionState): Promise<void> {
  await chrome.storage.session.set({ [STORAGE_KEYS.session]: state });
}

export async function updateSessionState(patch: Partial<ApplySessionState>): Promise<ApplySessionState> {
  const current = await getSessionState();
  const next = { ...current, ...patch };
  await saveSessionState(next);
  return next;
}

export async function clearSessionState(): Promise<void> {
  await chrome.storage.session.remove(STORAGE_KEYS.session);
}

export async function saveLastTab(tabId: number): Promise<void> {
  await chrome.storage.session.set({ [STORAGE_KEYS.lastTab]: tabId });
}

export async function getLastTab(): Promise<number | undefined> {
  const stored = await chrome.storage.session.get(STORAGE_KEYS.lastTab);
  return stored[STORAGE_KEYS.lastTab];
}
