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
    # ========================================================
    # STATE DETECTION
    # ========================================================

    def detect_page_state(self):
        """
        Detect obvious ChatGPT states.

        Important:
        We only inspect visible dialogs for now.
        We do NOT scan the entire page body because
        normal ChatGPT UI may contain words such as
        "usage limit" even when the model is available.

        Returns:
            (state, information)

        Possible states:
            RATE_LIMITED
            AUTH_REQUIRED
            USER_ACTION_REQUIRED
            None
        """

        # --------------------------------------------------------
        # Check visible dialogs only
        # --------------------------------------------------------

        dialogs = self.page.locator('[role="dialog"]:visible')

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
                "message limit",
                "rate limit",
                "too many requests",
            ]

            if any(keyword in lower for keyword in limit_keywords):
                return "RATE_LIMITED", text

            # ----------------------------------------------------
            # Authentication
            # ----------------------------------------------------

            auth_keywords = [
                "session expired",
                "please sign in",
                "please log in",
            ]

            if any(keyword in lower for keyword in auth_keywords):
                return "AUTH_REQUIRED", text

            # ----------------------------------------------------
            # Any other visible dialog
            # ----------------------------------------------------

            return "USER_ACTION_REQUIRED", text

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

            current_text = self.get_latest_assistant_text()

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

                state, information = self.detect_page_state()

                if state is not None:
                    return state, information

                return "TIMEOUT_UNKNOWN", ""

            time.sleep(0.5)

    # ========================================================
    # SEND PROMPT
    # ========================================================

    def send_prompt(self, prompt):
        """
        Send a prompt to ChatGPT.

        The composer can temporarily become unavailable while
        the ChatGPT UI is transitioning, so we actively wait
        for it to become visible, enabled, and editable.
        """

        if not isinstance(prompt, str):
            return (
                "SEND_ERROR",
                "Prompt must be a string."
            )

        prompt = prompt.strip()

        if not prompt:
            return (
                "SEND_ERROR",
                "Prompt cannot be empty."
            )

        previous_text = (
            self.get_latest_assistant_text()
        )

        # --------------------------------------------------------
        # Try several times because the ChatGPT composer can
        # temporarily become non-editable during UI transitions.
        # --------------------------------------------------------

        max_attempts = 5

        for attempt in range(1, max_attempts + 1):

            deadline = time.time() + 30

            while time.time() < deadline:

                textbox = self.get_textbox()

                try:
                    if (
                        textbox.count() > 0
                        and textbox.is_visible()
                        and textbox.is_enabled()
                        and textbox.is_editable()
                    ):
                        break

                except Exception:
                    pass

                time.sleep(0.5)

            else:
                if attempt == max_attempts:
                    return (
                        "NOT_READY",
                        "ChatGPT composer did not become "
                        "editable within the allowed time."
                    )

                time.sleep(1)

                continue

            # ----------------------------------------------------
            # Composer is actionable now.
            # ----------------------------------------------------

            try:

                textbox.scroll_into_view_if_needed(
                    timeout=5000
                )

                textbox.click(
                    timeout=5000
                )

                textbox.fill(
                    prompt,
                    timeout=15000
                )

                # ------------------------------------------------
                # Verify that the text actually entered the
                # composer.
                # ------------------------------------------------

                inserted_text = (
                    textbox.inner_text().strip()
                )

                if inserted_text != prompt:
                    raise RuntimeError(
                        "Prompt was not completely inserted "
                        "into the ChatGPT composer."
                    )

                # ------------------------------------------------
                # Send
                # ------------------------------------------------

                textbox.press(
                    "Enter",
                    timeout=10000
                )

                return self.wait_for_response(
                    previous_text
                )

            except Exception as error:

                # If this was the final attempt, report it.
                if attempt == max_attempts:

                    return (
                        "SEND_ERROR",
                        "Could not send prompt after "
                        f"{max_attempts} attempts: {error}"
                    )

                # Give the UI a moment to settle before retrying.
                time.sleep(1)

        return (
            "SEND_ERROR",
            "Unexpected send failure."
        )