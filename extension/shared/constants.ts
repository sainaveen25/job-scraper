export const DEFAULT_API_BASE_URL = "http://localhost:8000";
export const STORAGE_KEYS = {
  settings: "applymate.settings",
  session: "applymate.applySession",
  lastTab: "applymate.lastTab"
} as const;

export const SUPPORTED_ATS_HOSTS = [
  "boards.greenhouse.io",
  "job-boards.greenhouse.io",
  "jobs.lever.co",
  "myworkdayjobs.com"
];

export const MESSAGE_TYPES = {
  detectPage: "APPLYMATE_DETECT_PAGE",
  fillPage: "APPLYMATE_FILL_PAGE",
  continuePage: "APPLYMATE_CONTINUE_PAGE",
  prepareSubmit: "APPLYMATE_PREPARE_SUBMIT",
  submitConfirmed: "APPLYMATE_SUBMIT_CONFIRMED",
  contentReady: "APPLYMATE_CONTENT_READY",
  openPanel: "APPLYMATE_OPEN_PANEL"
} as const;
