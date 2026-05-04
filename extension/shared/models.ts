export type Platform = "greenhouse" | "lever" | "workday" | "generic";
export type PlatformSupport = "supported" | "partial" | "manual_assist";
export type FieldType = "text" | "textarea" | "select" | "radio" | "checkbox" | "file" | "password" | "unknown";

export interface FieldDescriptor {
  id: string;
  label: string;
  selector: string;
  name?: string;
  groupSelector?: string;
  fieldType: FieldType;
  required: boolean;
  options: string[];
  value?: unknown;
  sensitive: boolean;
  debug?: Record<string, unknown>;
}

export interface FillInstruction {
  selector?: string;
  name?: string;
  groupSelector?: string;
  label: string;
  fieldType: FieldType;
  value: unknown;
  source: "profile" | "memory" | "unknown" | string;
  requiresReview?: boolean;
}

export interface UnknownFieldPayload {
  field: FieldDescriptor;
  reason: string;
}

export interface PageDetection {
  platform: Platform;
  support: PlatformSupport;
  currentUrl: string;
  pageTitle: string;
  fields: FieldDescriptor[];
  hasNext: boolean;
  hasSubmit: boolean;
  step: number;
  debugLogs: string[];
}

export interface ApplyMateSettings {
  apiBaseUrl: string;
  userId?: string | undefined;
  userSessionToken?: string | undefined;
}

export interface ApplySessionState {
  sessionId?: string | undefined;
  extensionToken?: string | undefined;
  selectedJobId?: string | undefined;
  currentUrl?: string | undefined;
  lastPlatform?: Platform | undefined;
}

export interface ApplySessionPayload {
  sessionId: string;
  extensionToken?: string | undefined;
  job?: {
    id?: string;
    title?: string;
    company?: string;
    applyUrl?: string;
    jobUrl?: string;
    [key: string]: unknown;
  };
  resume?: {
    id?: string;
    label?: string;
    fileName?: string;
    mimeType?: string;
    [key: string]: unknown;
  } | null;
  profile?: Record<string, unknown>;
  fieldMemory?: Array<Record<string, unknown>>;
  platform: Platform;
  status?: string;
  progress?: Record<string, unknown>;
  unresolvedFields?: UnknownFieldPayload[];
  fieldsDetected?: FieldDescriptor[];
  fieldsFilled?: unknown[];
  fillInstructions?: FillInstruction[];
  resumeUpload?: {
    available: boolean;
    resumeId?: string;
    fileName?: string;
    mimeType?: string;
  };
  runHistory?: Array<Record<string, unknown>>;
  pageTitle?: string;
  currentUrl?: string;
  screenshotPath?: string;
  submitInstruction?: {
    action: string;
    requiresExplicitConfirmation: boolean;
  };
  error?: string;
  ok?: boolean;
}

export interface RuntimeRequest {
  type: string;
  payload?: unknown;
}

export interface RuntimeResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
