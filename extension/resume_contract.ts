/**
 * resume_contract.ts
 * ==================
 * TypeScript interfaces for the ApplyMate resume generation / tailor
 * edge function.  Mirrors automation/resume_contract.py exactly so
 * the Supabase edge function and the Python backend share one contract.
 *
 * Usage in edge function:
 *   import type { ResumeTailorInput, ResumeTailorOutput } from "./resume_contract";
 */

// ---------------------------------------------------------------------------
// Error contract
// ---------------------------------------------------------------------------

export type ResumeErrorCode =
  | "rate_limited"
  | "credits_exhausted"
  | "ai_empty"
  | "ai_upstream"
  | "invalid_input"
  | "unknown";

/**
 * Structured error returned to the frontend.
 * `userMessage` is safe to display in the UI.
 * The raw technical detail is NEVER included — it stays in server logs only.
 */
export interface ResumeError {
  code: ResumeErrorCode;
  userMessage: string;
}

// ---------------------------------------------------------------------------
// Content contract
// ---------------------------------------------------------------------------

/**
 * Known section types — extend as needed.
 * Edge function should use these values consistently.
 */
export type ResumeSectionType =
  | "summary"
  | "experience"
  | "education"
  | "skills"
  | "projects"
  | "certifications"
  | "publications"
  | "awards"
  | "custom";

/** One structured section of a generated resume. */
export interface ResumeSection {
  sectionType: ResumeSectionType | string;
  heading: string;
  /** Markdown or plain text content for this section. */
  content: string;
}

// ---------------------------------------------------------------------------
// Export metadata
// ---------------------------------------------------------------------------

export type ResumeKind = "base" | "tailored";
export type ResumeFormat = "markdown" | "pdf" | "docx" | "html";

/**
 * Metadata returned with every resume export or generation result.
 * Always present regardless of success/failure.
 */
export interface ResumeExportMeta {
  resumeKind: ResumeKind;
  format: ResumeFormat;
  generatedAt: string; // ISO 8601
  jobTitle: string | null;
  targetDomain: string | null;
  atsOptimised: boolean;
  /** Whether LinkedIn / GitHub / Portfolio links were included when available. */
  includeLinks: boolean;
}

// ---------------------------------------------------------------------------
// Tailor input contract
// ---------------------------------------------------------------------------

/**
 * Full validated input sent to the resume-tailor edge function.
 *
 * AI Prompt Guidance (non-software-biased):
 * - Use `targetDomain` (e.g. "electrical_engineering") as the primary context.
 * - Use `jobTitle` as the specific role — do NOT assume software engineering.
 * - Use `descriptionText` (clean plain text) — NEVER send raw HTML to the AI.
 * - Tailor language to the domain: skip "tech stack" for civil/mechanical roles.
 */
export interface ResumeTailorInput {
  // Job context (required for tailoring)
  jobTitle: string;
  /** Clean plain text — never raw HTML. */
  descriptionText: string;
  /** Category/domain of the role, e.g. "data_engineering", "mechanical_engineering". */
  targetDomain: string;

  // User identity (required)
  userId: string;
  resumeKind: ResumeKind;

  // Profile (optional but improve quality)
  fullName?: string | null;
  email?: string | null;
  phone?: string | null;
  education?: EducationEntry[];
  workExperience?: WorkExperienceEntry[];
  skills?: string[];

  // Links (included in export when provided)
  linkedinUrl?: string | null;
  githubUrl?: string | null;
  portfolioUrl?: string | null;

  // Base resume reference (for tailored variant)
  selectedResumeId?: string | null;
  selectedResumeLabel?: string | null;
  /** Raw text of the base resume to tailor from. */
  selectedResumeContent?: string | null;

  preferredFormat?: ResumeFormat;
}

// ---------------------------------------------------------------------------
// Profile sub-types
// ---------------------------------------------------------------------------

export interface EducationEntry {
  institution?: string | null;
  degree?: string | null;
  field?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  gpa?: string | null;
  highlights?: string[];
}

export interface WorkExperienceEntry {
  company?: string | null;
  title?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  current?: boolean;
  location?: string | null;
  bullets?: string[];
  description?: string | null;
}

// ---------------------------------------------------------------------------
// Tailor output contract
// ---------------------------------------------------------------------------

/**
 * Unified output returned by the resume-tailor edge function.
 *
 * On success: `ok` is true, `sections` and/or `rawContent` are set, `error` is null.
 * On failure: `ok` is false, `error` is set, `sections` may be empty.
 *
 * Frontend rules:
 * - Use `sections` to render a structured resume viewer.
 * - Use `rawContent` for PDF/DOCX export download.
 * - Display `error.userMessage` for any failure — do NOT show raw exception text.
 * - Use `exportMeta.resumeKind` to label the resume as "Base" or "Tailored".
 */
export interface ResumeTailorOutput {
  ok: boolean;
  exportMeta: ResumeExportMeta;
  sections: ResumeSection[];
  /** Full markdown / docx / PDF content string for download. */
  rawContent: string | null;
  error: ResumeError | null;
}

// ---------------------------------------------------------------------------
// Apply Session resume metadata (used in extension handoff)
// ---------------------------------------------------------------------------

/** Minimal resume metadata carried in the Apply Session / handoff payload. */
export interface SelectedResumeMeta {
  id: string | null;
  fileName: string | null;
  fileType: string | null;
  resumeKind: ResumeKind;
  label?: string | null;
}

// ---------------------------------------------------------------------------
// Score contract
// ---------------------------------------------------------------------------

export type ScoreSource = "ats_match" | "relevance" | "ranking" | "provided" | "unknown";

/**
 * Normalised match/relevance score (0–100).
 * Always present in job cards and Apply Session payloads when enough data exists.
 */
export interface JobMatchScore {
  /** Normalised score 0–100 (null if not computable). */
  matchScore: number | null;
  scoreSource: ScoreSource;
}
