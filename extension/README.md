# ApplyMate AI Chrome Extension

Manifest V3 extension for assisted ApplyMate job application autofill.

The ApplyMate website and backend are the primary product flow. Apply Sessions,
manual assist, saved answers, progress, and explicit submit gating must work in
any browser without this extension. This bundle is an optional Chrome enhancement
that can detect fields and apply backend-provided instructions directly in the
page when the user installs it.

## What It Does

- Opens a right-side Chrome side panel on job application pages.
- Detects Greenhouse, Lever, Workday, and generic form pages.
- Uses the user's authenticated ApplyMate session to create/fetch Apply Sessions.
- Sends current page field descriptors to the ApplyMate backend.
- Receives compact fill instructions and applies them in the content script.
- Shows unresolved fields and lets users save reusable answers.
- Keeps protected demographic questions in manual review.
- Requires explicit confirmation before final submit.

Core creation, review, manual assist, and submit confirmation should remain
available from the web control center even when the extension is absent,
disabled, or running in an unsupported browser.

## Build

```bash
cd extension
npm install
npm run check
npm run package
```

Load `extension/dist` in Chrome via `chrome://extensions` -> Developer mode -> Load unpacked.
The packaged Web Store candidate is written to `extension/release/applymate-ai-extension-0.1.0.zip`.

## Authentication

No backend secrets are embedded in the extension.

The extension stores:

- ApplyMate API base URL
- ApplyMate user ID
- ApplyMate user session token
- short-lived Apply Session extension token in session storage

Production should use HTTPS only and set a backend `APPLYMATE_EXTENSION_TOKEN_SECRET` so extension tokens are stable across backend instances.

## Permissions

Declared permissions:

- `sidePanel`: right-side assistant UI.
- `storage`: local/session settings and current Apply Session pointer.
- `activeTab` and `scripting`: user-triggered manual assist on unsupported pages.
- `tabs`: identify the active job application tab for panel-to-content messaging.

Host permissions are scoped to supported ATS domains, ApplyMate Lovable deployments, and localhost development.

## Chrome Web Store Notes

- Complete the Store Listing and Privacy tabs before publishing.
- Use a privacy policy URL that explains page field detection, ApplyMate account/session usage, and no sale of user data.
- Do not request broad host permissions unless manual assist requires them; prefer optional host permissions requested after user action.
- Chrome Web Store publishing requires a Google account with 2-step verification enabled.
- Avoid building release automation around Chrome Web Store API v1; Google marks v1 deprecated and supported only until October 15, 2026.

## Manual Assist

Unsupported pages can be used after the user clicks the extension action. The service worker injects the content script with `activeTab` and opens the side panel.

## Greenhouse And Lever Hardening

The test fixtures under `tests/fixtures/` cover common Greenhouse and Lever shapes:

- explicit and nearby labels
- Greenhouse-style nested answer names
- Lever `.application-label` blocks
- hidden resume inputs
- select/radio/checkbox controls
- submit-only versus continue-step pages

File inputs cannot be assigned arbitrary local files by extension JavaScript. ApplyMate marks the target input, scrolls to it, and requests the picker/manual upload flow while keeping the selected tailored resume visible in the panel.
