# AI Gateway — Discoveries

## Browser / Authentication
- Playwright's bundled Chromium caused a browser-security/sign-in problem.
- Using normal installed Chrome with a dedicated user-data directory worked.
- The working Chrome executable is:
  `C:\Program Files\Google\Chrome\Application\chrome.exe`
- The gateway's dedicated Chrome data directory is:
  `D:\Main\Desktop\ai-gateway\chrome-data`
- Chrome is started with remote debugging on port `9222`.
- Python successfully attaches with Playwright `connect_over_cdp("http://127.0.0.1:9222")`.

## ChatGPT DOM Findings
- ChatGPT exposes a textarea with placeholder `Ask anything`.
- The textbox has `aria-label="Chat with ChatGPT"`.
- A contenteditable textbox with role `textbox` was also observed.
- Assistant messages were successfully located using:
  `[data-message-author-role="assistant"]`

## Response Handling
- Simply waiting for a new assistant-message element was insufficient because the element can exist before its streamed text is populated.
- The working approach waits for the latest assistant text to appear and then waits for the text to remain unchanged for a short period.
- A previous timeout was caused by ChatGPT waiting for a human choice in an intermittent response-preference UI, not necessarily by ChatGPT failing to answer.

## UI Readiness
- Before sending a prompt, the gateway can check whether the ChatGPT textbox exists, is visible, enabled, and editable.
- This successfully prevented typing while another ChatGPT UI was open.

## Architecture Insight
Keep three concerns separate:
1. UI readiness — can we interact with the composer?
2. Conversation state — is ChatGPT generating, completed, or waiting for user action?
3. Provider availability — can the current free model accept another request?

## Provider Direction
Develop against ChatGPT only for now. Keep the provider interface generic enough for Claude and Gemini later.
