from playwright.sync_api import sync_playwright
import time


# ============================================================
# FIND CHATGPT PAGE
# ============================================================

def find_chatgpt_page(browser):
    """Find the currently open ChatGPT tab."""

    for context in browser.contexts:
        for page in context.pages:
            if "chatgpt.com" in page.url:
                return page

    return None


# ============================================================
# TEXTBOX
# ============================================================

def get_textbox(page):
    """Return the ChatGPT message textbox."""

    return page.get_by_role(
        "textbox",
        name="Chat with ChatGPT"
    )


def check_textbox_ready(page):
    """
    Check whether the ChatGPT composer is actually usable.

    Returns:
        (True, "")
        OR
        (False, reason)
    """

    textbox = get_textbox(page)

    # --------------------------------------------------------
    # Does the textbox exist?
    # --------------------------------------------------------

    if textbox.count() == 0:
        return False, "ChatGPT textbox was not found."

    # --------------------------------------------------------
    # Is it visible?
    # --------------------------------------------------------

    try:
        if not textbox.is_visible():
            return False, "ChatGPT textbox is not visible."
    except Exception:
        return False, "Could not determine textbox visibility."

    # --------------------------------------------------------
    # Is it enabled?
    # --------------------------------------------------------

    try:
        if not textbox.is_enabled():
            return False, "ChatGPT textbox is disabled."
    except Exception:
        return False, "Could not determine textbox state."

    # --------------------------------------------------------
    # Is it editable?
    # --------------------------------------------------------

    try:
        if not textbox.is_editable():
            return False, "ChatGPT textbox is not editable."
    except Exception:
        return False, "Could not determine whether textbox is editable."

    return True, ""


# ============================================================
# ASSISTANT MESSAGE HELPERS
# ============================================================

def get_assistant_messages(page):
    return page.locator(
        '[data-message-author-role="assistant"]'
    )


def get_latest_assistant_text(page):
    """Get text from the latest assistant message."""

    messages = get_assistant_messages(page)

    if messages.count() == 0:
        return ""

    try:
        return messages.nth(
            messages.count() - 1
        ).inner_text().strip()

    except Exception:
        return ""


# ============================================================
# PAGE STATE DETECTION
# ============================================================

def detect_page_state(page):
    """
    Look for states that need special handling.

    Returns:
        (state, information)

    Possible states:

        RATE_LIMITED
        AUTH_REQUIRED
        USER_ACTION_REQUIRED
        None
    """

    # --------------------------------------------------------
    # CHECK VISIBLE DIALOGS
    # --------------------------------------------------------

    dialogs = page.locator(
        '[role="dialog"]:visible'
    )

    for i in range(dialogs.count()):

        dialog = dialogs.nth(i)

        try:
            text = dialog.inner_text().strip()
        except Exception:
            text = ""

        if not text:
            continue

        lower = text.lower()

        # ----------------------------------------------------
        # Usage limit
        # ----------------------------------------------------

        limit_keywords = [
            "usage limit",
            "reached your limit",
            "limit reached",
            "try again later",
            "too many requests",
            "message limit",
            "rate limit",
        ]

        if any(
            keyword in lower
            for keyword in limit_keywords
        ):
            return "RATE_LIMITED", text

        # ----------------------------------------------------
        # Authentication
        # ----------------------------------------------------

        auth_keywords = [
            "sign in",
            "log in",
            "login",
            "session expired",
        ]

        if any(
            keyword in lower
            for keyword in auth_keywords
        ):
            return "AUTH_REQUIRED", text

        # ----------------------------------------------------
        # Other dialog
        # ----------------------------------------------------

        return "USER_ACTION_REQUIRED", text

    # --------------------------------------------------------
    # CHECK PAGE TEXT FOR LIMIT / AUTH
    # --------------------------------------------------------

    try:
        body_text = page.locator(
            "body"
        ).inner_text().strip()

    except Exception:
        body_text = ""

    lower_body = body_text.lower()

    # --------------------------------------------------------
    # Usage limit
    # --------------------------------------------------------

    limit_keywords = [
        "you've reached your limit",
        "you have reached your limit",
        "usage limit",
        "message limit",
        "rate limit",
    ]

    for keyword in limit_keywords:

        if keyword in lower_body:
            return "RATE_LIMITED", keyword

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    auth_keywords = [
        "session expired",
        "please log in",
        "please sign in",
    ]

    for keyword in auth_keywords:

        if keyword in lower_body:
            return "AUTH_REQUIRED", keyword

    return None, None


# ============================================================
# WAIT FOR RESPONSE
# ============================================================

def wait_for_response(page, previous_text):
    """
    Wait for a response to complete.

    Returns:

        ("COMPLETED", response)
        ("USER_ACTION_REQUIRED", information)
        ("RATE_LIMITED", information)
        ("AUTH_REQUIRED", information)
        ("TIMEOUT_UNKNOWN", information)
    """

    start_time = time.time()

    saw_new_response = False

    last_text = previous_text

    stable_since = None

    while True:

        # ----------------------------------------------------
        # Check special UI states
        # ----------------------------------------------------

        state, information = detect_page_state(page)

        if state in [
            "RATE_LIMITED",
            "AUTH_REQUIRED"
        ]:
            return state, information

        # ----------------------------------------------------
        # Read latest assistant response
        # ----------------------------------------------------

        current_text = get_latest_assistant_text(page)

        # ----------------------------------------------------
        # New response appeared
        # ----------------------------------------------------

        if (
            current_text
            and current_text != previous_text
        ):
            saw_new_response = True

        # ----------------------------------------------------
        # Response may be streaming
        # ----------------------------------------------------

        if saw_new_response:

            if current_text != last_text:

                last_text = current_text

                stable_since = time.time()

            # Text has not changed for 2 seconds
            if (
                stable_since is not None
                and time.time() - stable_since >= 2
            ):
                return "COMPLETED", current_text

        # ----------------------------------------------------
        # Safety timeout
        # ----------------------------------------------------

        if time.time() - start_time >= 180:

            state, information = detect_page_state(page)

            if state is not None:
                return state, information

            return (
                "TIMEOUT_UNKNOWN",
                ""
            )

        time.sleep(0.5)


# ============================================================
# MAIN
# ============================================================

with sync_playwright() as p:

    # ========================================================
    # CONNECT TO EXISTING CHROME
    # ========================================================

    print("Connecting to Chrome...")

    browser = p.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    print("Connected!")

    # ========================================================
    # FIND CHATGPT
    # ========================================================

    chat_page = find_chatgpt_page(browser)

    if chat_page is None:

        print("ChatGPT page not found.")

        raise SystemExit(1)

    print("ChatGPT found!")

    # ========================================================
    # START INTERACTIVE MODE
    # ========================================================

    print("\n==============================")
    print("        AI Gateway")
    print("==============================")
    print("Type /exit to quit.\n")

    while True:

        # ====================================================
        # CHECK WHETHER CHATGPT CAN RECEIVE INPUT
        # ====================================================

        ready, reason = check_textbox_ready(
            chat_page
        )

        if not ready:

            print(
                "\n=============================="
            )

            print(
                "CHATGPT IS NOT READY"
            )

            print(
                "==============================\n"
            )

            print(reason)

            print(
                "\nThe ChatGPT page may currently "
                "have another UI open."
            )

            print(
                "Check the browser and return to "
                "the normal conversation."
            )

            input(
                "\nPress ENTER after fixing the browser..."
            )

            # Re-check instead of blindly continuing
            continue

        # ====================================================
        # GET PROMPT
        # ====================================================

        prompt = input("> ").strip()

        # Ignore empty input
        if not prompt:
            continue

        # Exit
        if prompt.lower() == "/exit":

            print("\nGoodbye.")

            break

        # ====================================================
        # GET TEXTBOX AGAIN
        # ====================================================

        textbox = get_textbox(
            chat_page
        )

        # ====================================================
        # CAPTURE CURRENT RESPONSE
        # ====================================================

        previous_text = get_latest_assistant_text(
            chat_page
        )

        # ====================================================
        # SEND PROMPT
        # ====================================================

        print("\nSending...")

        try:

            textbox.fill(prompt)

            textbox.press("Enter")

        except Exception as error:

            print(
                "\nCould not send the prompt."
            )

            print(
                "ChatGPT may currently have "
                "another UI active."
            )

            print(
                f"\nTechnical details: {error}"
            )

            continue

        print(
            "Monitoring ChatGPT...\n"
        )

        # ====================================================
        # WAIT FOR RESPONSE
        # ====================================================

        state, result = wait_for_response(
            chat_page,
            previous_text
        )

        # ====================================================
        # COMPLETED
        # ====================================================

        if state == "COMPLETED":

            print(
                "=============================="
            )

            print(
                "ChatGPT:"
            )

            print(
                "==============================\n"
            )

            print(result)

            print()

        # ====================================================
        # USER ACTION REQUIRED
        # ====================================================

        elif state == "USER_ACTION_REQUIRED":

            print(
                "=============================="
            )

            print(
                "CHATGPT NEEDS YOUR INPUT"
            )

            print(
                "==============================\n"
            )

            print(result)

            print(
                "\nComplete the required action "
                "in the ChatGPT browser."
            )

            input(
                "\nPress ENTER after you have completed it..."
            )

        # ====================================================
        # RATE LIMITED
        # ====================================================

        elif state == "RATE_LIMITED":

            print(
                "=============================="
            )

            print(
                "CHATGPT USAGE LIMIT"
            )

            print(
                "==============================\n"
            )

            print(
                "ChatGPT appears to have reached "
                "a usage/message limit."
            )

            print("\nDetected information:")

            print(result)

            print(
                "\nCheck ChatGPT in the browser "
                "for available options."
            )

            input(
                "\nPress ENTER after checking..."
            )

        # ====================================================
        # AUTH REQUIRED
        # ====================================================

        elif state == "AUTH_REQUIRED":

            print(
                "=============================="
            )

            print(
                "AUTHENTICATION REQUIRED"
            )

            print(
                "==============================\n"
            )

            print(
                "The ChatGPT session may have "
                "expired."
            )

            print("\nDetected information:")

            print(result)

            input(
                "\nSign in using the browser, "
                "then press ENTER..."
            )

        # ====================================================
        # UNKNOWN TIMEOUT
        # ====================================================

        elif state == "TIMEOUT_UNKNOWN":

            print(
                "=============================="
            )

            print(
                "UNKNOWN CHATGPT STATE"
            )

            print(
                "==============================\n"
            )

            print(
                "ChatGPT did not produce a completed "
                "response within the safety limit."
            )

            print(
                "\nCurrent page:"
            )

            print(
                chat_page.url
            )

            print(
                "\nVisible page text "
                "(first 3000 characters):"
            )

            try:

                print(
                    chat_page.locator(
                        "body"
                    ).inner_text()[:3000]
                )

            except Exception:

                print(
                    "Could not read page text."
                )

            input(
                "\nPress ENTER to continue..."
            )