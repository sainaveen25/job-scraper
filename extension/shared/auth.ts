import type { ApplyMateSettings } from "./models";
import { getSettings, saveSettings } from "./storage";

export async function getAuthHeaders(extensionToken?: string): Promise<Record<string, string>> {
  const settings = await getSettings();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (extensionToken) {
    headers.Authorization = `Bearer ${extensionToken}`;
  } else if (settings.userSessionToken) {
    headers.Authorization = `Bearer ${settings.userSessionToken}`;
  }
  return headers;
}

export function authenticatedPayload(settings: ApplyMateSettings): Record<string, unknown> {
  return {
    auth: {
      userId: settings.userId,
      sessionToken: settings.userSessionToken
    }
  };
}

export async function isSignedIn(): Promise<boolean> {
  const settings = await getSettings();
  return Boolean(settings.userId && settings.userSessionToken);
}

export async function saveApplyMateSession(userId: string, userSessionToken: string, apiBaseUrl?: string): Promise<void> {
  const settings = await getSettings();
  await saveSettings({
    ...settings,
    apiBaseUrl: apiBaseUrl || settings.apiBaseUrl,
    userId,
    userSessionToken
  });
}
