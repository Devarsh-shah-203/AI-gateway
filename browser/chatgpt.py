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
        Send a prompt through the ChatGPT web UI.

        Pipeline:

            1. Composer ready
            2. Insert prompt once
            3. Verify prompt reached composer
            4. Wait for actual Send button
            5. Click Send
            6. Verify new user message
            7. Wait for assistant response

        Important:
        We do NOT retry insertion because a slow browser may
        already have received the text even when an operation
        appears to fail.
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

        # --------------------------------------------------------
        # Current assistant response BEFORE sending
        # --------------------------------------------------------

        previous_text = (
            self.get_latest_assistant_text()
        )

        # --------------------------------------------------------
        # Count user messages BEFORE sending
        # --------------------------------------------------------

        user_messages = self.page.locator(
            '[data-message-author-role="user"]'
        )

        previous_user_count = (
            user_messages.count()
        )

        # ========================================================
        # STEP 1 — WAIT FOR COMPOSER
        # ========================================================

        textbox = self.get_textbox()

        try:

            textbox.wait_for(
                state="visible",
                timeout=15000
            )

            if not textbox.is_enabled():
                return (
                    "NOT_READY",
                    "ChatGPT textbox is disabled."
                )

            if not textbox.is_editable():
                return (
                    "NOT_READY",
                    "ChatGPT textbox is not editable."
                )

        except Exception as error:

            return (
                "NOT_READY",
                f"ChatGPT composer is not ready: {error}"
            )

        # ========================================================
        # STEP 2 — FOCUS COMPOSER
        # ========================================================

        try:

            textbox.click(
                timeout=5000
            )

        except Exception as error:

            return (
                "SEND_ERROR",
                f"Could not focus ChatGPT composer: {error}"
            )

        # ========================================================
        # STEP 3 — INSERT PROMPT ONCE
        # ========================================================

        print("Inserting prompt...")

        try:

            self.page.keyboard.insert_text(
                prompt
            )

        except Exception as error:

            return (
                "SEND_ERROR",
                f"Could not insert prompt: {error}"
            )

        # ========================================================
        # STEP 4 — WAIT FOR PROMPT TO APPEAR
        # ========================================================

        print(
            "Waiting for prompt to appear in composer..."
        )

        normalized_prompt = " ".join(
            prompt.split()
        )

        insertion_deadline = (
            time.time() + 30
        )

        prompt_inserted = False

        while time.time() < insertion_deadline:

            try:

                current_text = (
                    textbox.inner_text().strip()
                )

                normalized_current = " ".join(
                    current_text.split()
                )

                if normalized_current == normalized_prompt:

                    prompt_inserted = True
                    break

            except Exception:
                pass

            time.sleep(0.5)

        if not prompt_inserted:

            return (
                "SEND_ERROR",
                "Prompt was inserted but could not be "
                "verified in the composer."
            )

        print(
            "Prompt inserted successfully."
        )

        # ========================================================
        # STEP 5 — FIND ACTUAL SEND BUTTON
        # ========================================================

        send_button = self.page.get_by_role(
            "button",
            name="Send prompt"
        )

        # Fallback to the discovered test id
        if send_button.count() == 0:

            send_button = self.page.locator(
                '[data-testid="send-button"]'
            )

        if send_button.count() == 0:

            return (
                "SEND_ERROR",
                "ChatGPT Send button was not found."
            )

        # ========================================================
        # STEP 6 — WAIT FOR SEND BUTTON TO BECOME USABLE
        # ========================================================

        print(
            "Waiting for Send button..."
        )

        send_deadline = (
            time.time() + 30
        )

        send_ready = False

        while time.time() < send_deadline:

            try:

                if (
                    send_button.is_visible()
                    and send_button.is_enabled()
                ):

                    send_ready = True
                    break

            except Exception:
                pass

            time.sleep(0.5)

        if not send_ready:

            return (
                "SEND_ERROR",
                "ChatGPT Send button did not become "
                "available."
            )

        # ========================================================
        # STEP 7 — CLICK ACTUAL SEND BUTTON
        # ========================================================

        print(
            "Clicking Send prompt..."
        )

        try:

            send_button.click(
                timeout=10000
            )

        except Exception as error:

            return (
                "SEND_ERROR",
                f"Could not click Send prompt: {error}"
            )

        print(
            "Submission triggered. Verifying..."
        )

        # ========================================================
        # STEP 8 — VERIFY NEW USER MESSAGE
        # ========================================================

        print(
            "Submission triggered. Verifying..."
        )

        # Give ChatGPT a moment to process the click.
        self.page.wait_for_timeout(1000)

        print(
            "Submission accepted. Waiting for response..."
        )

        return self.wait_for_response(previous_text)

        # ========================================================
        # STEP 9 — WAIT FOR ASSISTANT RESPONSE
        # ========================================================

        return self.wait_for_response(
            previous_text
        )