import type { Platform, PlatformSupport } from "./models";

export function detectPlatform(url: string): { platform: Platform; support: PlatformSupport } {
  const host = safeHost(url);
  if (host === "boards.greenhouse.io" || host === "job-boards.greenhouse.io") {
    return { platform: "greenhouse", support: "supported" };
  }
  if (host === "jobs.lever.co") {
    return { platform: "lever", support: "supported" };
  }
  if (host.endsWith(".myworkdayjobs.com")) {
    return { platform: "workday", support: "partial" };
  }
  return { platform: "generic", support: "manual_assist" };
}

function safeHost(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}
