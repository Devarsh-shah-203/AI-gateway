from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print("Connecting to existing Chrome...")

    browser = p.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    print("Connected!")

    # Find the ChatGPT tab
    chat_page = None

    for context in browser.contexts:
        for page in context.pages:
            if "chatgpt.com" in page.url:
                chat_page = page
                break

    if chat_page is None:
        print("ChatGPT page not found.")
        raise SystemExit

    print("ChatGPT found!")

    # Find the message textbox
    textbox = chat_page.get_by_role(
        "textbox",
        name="Chat with ChatGPT"
    )

    print("Textbox count:", textbox.count())

    # Test message
    message = "Hello from my terminal!"

    print("Sending:", message)

    textbox.fill(message)
    textbox.press("Enter")

    print("Message sent!")

    input("\nPress ENTER to finish...")