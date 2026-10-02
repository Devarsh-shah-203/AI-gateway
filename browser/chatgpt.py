import time


class ChatGPTBrowser:
    """
    Handles interaction with the ChatGPT web interface.
    """

    def __init__(self, browser):
        self.browser = browser
        self.page = self._find_chatgpt_page()

        if self.page is None:
            raise RuntimeError("ChatGPT page not found.")

    # ========================================================
    # FIND CHATGPT
    # ========================================================

    def _find_chatgpt_page(self):
        for context in self.browser.contexts:
            for page in context.pages:
                if "chatgpt.com" in page.url:
                    return page

        return None

    # ========================================================
    # TEXTBOX
    # ========================================================

    def get_textbox(self):
        return self.page.get_by_role(
            "textbox",
            name="Chat with ChatGPT"
        )

    def check_textbox_ready(self):
        """
        Check whether ChatGPT is currently ready
        to receive a prompt.

        Returns:
            (True, "")
            OR
            (False, reason)
        """

        textbox = self.get_textbox()

        if textbox.count() == 0:
            return False, "ChatGPT textbox was not found."

        try:
            if not textbox.is_visible():
                return False, "ChatGPT textbox is not visible."

            if not textbox.is_enabled():
                return False, "ChatGPT textbox is disabled."

            if not textbox.is_editable():
                return False, "ChatGPT textbox is not editable."

        except Exception as error:
            return False, f"Could not inspect textbox: {error}"

        return True, ""

    # ========================================================
    # ASSISTANT MESSAGES
    # ========================================================

    def get_assistant_messages(self):
        return self.page.locator(
            '[data-message-author-role="assistant"]'
        )

    def get_latest_assistant_text(self):
        messages = self.get_assistant_messages()

        if messages.count() == 0:
            return ""

        try:
            return messages.nth(
                messages.count() - 1
            ).inner_text().strip()

        except Exception:
            return ""

    # ========================================================
    # STATE DETECTION
    # ========================================================

    def detect_page_state(self):
        """
        Detect obvious ChatGPT states.

        Returns:
            (state, information)

        Possible states:
            RATE_LIMITED
            AUTH_REQUIRED
            USER_ACTION_REQUIRED
            None
        """

        dialogs = self.page.locator(
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

            limit_keywords = [
                "usage limit",
                "reached your limit",
                "limit reached",
                "too many requests",
                "message limit",
                "rate limit",
            ]

            if any(
                keyword in lower
                for keyword in limit_keywords
            ):
                return "RATE_LIMITED", text

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

            return "USER_ACTION_REQUIRED", text

        try:
            body_text = self.page.locator(
                "body"
            ).inner_text().strip()
        except Exception:
            body_text = ""

        lower_body = body_text.lower()

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

        auth_keywords = [
            "session expired",
            "please log in",
            "please sign in",
        ]

        for keyword in auth_keywords:
            if keyword in lower_body:
                return "AUTH_REQUIRED", keyword

        return None, None

    # ========================================================
    # WAIT FOR RESPONSE
    # ========================================================

    def wait_for_response(self, previous_text):
        """
        Wait for ChatGPT to finish responding.

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

            state, information = self.detect_page_state()

            if state in [
                "RATE_LIMITED",
                "AUTH_REQUIRED",
            ]:
                return state, information

            current_text = (
                self.get_latest_assistant_text()
            )

            if (
                current_text
                and current_text != previous_text
            ):
                saw_new_response = True

            if saw_new_response:

                if current_text != last_text:
                    last_text = current_text
                    stable_since = time.time()

                if (
                    stable_since is not None
                    and time.time() - stable_since >= 2
                ):
                    return "COMPLETED", current_text

            if time.time() - start_time >= 180:

                state, information = (
                    self.detect_page_state()
                )

                if state is not None:
                    return state, information

                return "TIMEOUT_UNKNOWN", ""

            time.sleep(0.5)

    # ========================================================
    # SEND PROMPT
    # ========================================================

    def send_prompt(self, prompt):
        """
        Send a prompt and return the result.

        Returns:
            (state, result)
        """

        ready, reason = (
            self.check_textbox_ready()
        )

        if not ready:
            return (
                "NOT_READY",
                reason
            )

        previous_text = (
            self.get_latest_assistant_text()
        )

        textbox = self.get_textbox()

        try:
            textbox.fill(prompt)
            textbox.press("Enter")

        except Exception as error:
            return (
                "SEND_ERROR",
                str(error)
            )

        return self.wait_for_response(
            previous_text
        )