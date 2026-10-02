from playwright.sync_api import sync_playwright
import time


def find_chatgpt_page(browser):
    for context in browser.contexts:
        for page in context.pages:
            if "chatgpt.com" in page.url:
                return page

    return None


with sync_playwright() as p:
    print("Connecting to Chrome...")

    browser = p.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    print("Connected!")

    chat_page = find_chatgpt_page(browser)

    if chat_page is None:
        print("ChatGPT page not found.")
        raise SystemExit(1)

    print("ChatGPT found!")

    textbox = chat_page.get_by_role(
        "textbox",
        name="Chat with ChatGPT"
    )

    if textbox.count() == 0:
        print("Textbox not found.")
        raise SystemExit(1)

    prompt = input("\n> ")

    assistant_messages = chat_page.locator(
        '[data-message-author-role="assistant"]'
    )

    old_count = assistant_messages.count()

    print("\nSending...")
    textbox.fill(prompt)
    textbox.press("Enter")

    print("Waiting for ChatGPT...")

    # Wait until a NEW assistant message exists AND it has text
    chat_page.wait_for_function(
        """
        oldCount => {
            const messages = document.querySelectorAll(
                '[data-message-author-role="assistant"]'
            );

            if (messages.length <= oldCount) {
                return false;
            }

            const latest = messages[messages.length - 1];

            return latest.innerText.trim().length > 0;
        }
        """,
        arg=old_count,
        timeout=120000
    )

    print("Response detected!")

    latest_message = assistant_messages.nth(
        assistant_messages.count() - 1
    )

    # Wait for the streamed response to stabilize
    previous_text = ""
    stable_since = time.time()

    while True:
        current_text = latest_message.inner_text().strip()

        if current_text != previous_text:
            previous_text = current_text
            stable_since = time.time()

        # Response hasn't changed for 2 seconds
        if current_text and time.time() - stable_since >= 2:
            break

        # Safety timeout
        if time.time() - stable_since > 120:
            break

        time.sleep(0.5)

    print("\n================================")
    print("ChatGPT:")
    print("================================\n")

    print(previous_text)

    print("\n================================")
    print("Done.")
    print("================================")

    input("\nPress ENTER to exit...")