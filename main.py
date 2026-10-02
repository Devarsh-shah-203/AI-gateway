from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print("Connecting to Chrome...")

    browser = p.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    chat_page = None

    for context in browser.contexts:
        for page in context.pages:
            if "chatgpt.com" in page.url:
                chat_page = page
                break

    if chat_page is None:
        print("ChatGPT page not found.")
        raise SystemExit

    print("ChatGPT found!\n")

    # Look for ChatGPT message elements
    messages = chat_page.locator("[data-message-author-role]")

    print("Messages found:", messages.count())

    for i in range(messages.count()):
        message = messages.nth(i)

        role = message.get_attribute("data-message-author-role")

        print(f"\n--- Message {i} | {role} ---")
        print(message.inner_text())

    input("\nPress ENTER to finish...")