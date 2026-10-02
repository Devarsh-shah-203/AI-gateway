# AI Gateway — Cookbooks

## Cookbook: Connect to the Current ChatGPT Browser Session

### Preconditions
- Start the dedicated Chrome profile with remote debugging on port `9222`.
- Sign into ChatGPT manually in that browser profile.

### Python Pattern
Use Playwright to attach to the running browser:

```python
browser = p.chromium.connect_over_cdp(
    "http://127.0.0.1:9222"
)
```

Then locate the ChatGPT tab by checking for `chatgpt.com` in the page URL.

## Cookbook: Find the ChatGPT Composer

```python
textbox = page.get_by_role(
    "textbox",
    name="Chat with ChatGPT"
)
```

Before using it, check that it exists, is visible, enabled, and editable.

## Cookbook: Find Assistant Messages

```python
messages = page.locator(
    '[data-message-author-role="assistant"]'
)
```

Use the latest assistant message for response extraction.

## Cookbook: Handle Streaming Responses

Do not read the assistant message immediately after the element appears. Wait until text exists, then monitor the text until it stops changing for a short stability period.

## Future Cookbooks
Add reusable recipes here for:
- File context injection
- Project-state loading
- Session summarization
- Git-aware context
- Claude browser provider
- Gemini browser provider
