from playwright.sync_api import sync_playwright

from browser.connection import connect_to_chrome
from browser.chatgpt import ChatGPTBrowser
from context.builder import ContextBuilder
from memory.manager import MemoryManager
from memory.prompts import build_save_prompt
from memory.saver import MemorySaver
from context.session import MemoryContextSession
from terminal.ui import (
    print_header,
    print_response,
    print_not_ready,
    print_user_action,
    print_rate_limited,
    print_auth_required,
    print_send_error,
    print_unknown_state,
    wait_for_user,
    print_memory,
    print_memory_status,
)


def main():

    with sync_playwright() as p:

        # ====================================================
        # CONNECT TO CHROME
        # ====================================================

        print("Connecting to Chrome...")

        browser = connect_to_chrome(p)

        print("Connected!")

        # ====================================================
        # CHATGPT
        # ====================================================

        try:
            chatgpt = ChatGPTBrowser(browser)

        except RuntimeError as error:
            print(error)
            return

        print("ChatGPT found!")

        # ====================================================
        # MEMORY / CONTEXT
        # ====================================================

        memory = MemoryManager()
        context_builder = ContextBuilder()

        # OFF  → don't include memory
        # ON   → include memory
        # NEXT → include memory once
        memory_session = MemoryContextSession()
        memory_saver = MemorySaver()

        # ====================================================
        # HEADER
        # ====================================================

        print_header(
            memory_session.get_status()
        )

        # ====================================================
        # INTERACTIVE LOOP
        # ====================================================

        while True:

            prompt = input("> ").strip()

            if not prompt:
                continue

            # =================================================
            # EXIT
            # =================================================

            if prompt.lower() == "/exit":

                print("\nGoodbye.")

                break

            # =================================================
            # SHOW MEMORY
            # =================================================

            if prompt.lower() == "/memory":

                print_memory(
                    memory.read_all()
                )

                continue

            # =================================================
            # MEMORY USE
            # =================================================

            if prompt.lower() == "/memory use":

                memory_session.use_once()

                print("\nMemory: NEXT")

                print(
                    "Project memory will be included "
                    "in the next prompt only."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()

                continue

            # =================================================
            # MEMORY ON
            # =================================================

            if prompt.lower() == "/memory on":

                memory_session.enable()

                print("\nMemory: ON")

                print(
                    "The current project-memory snapshot "
                    "will be included in the next prompt."
                )

                print(
                    "It will not be resent with every prompt."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()

                continue

            # =================================================
            # MEMORY OFF
            # =================================================

            if prompt.lower() == "/memory off":

                memory_session.disable()

                print("\nMemory: OFF")

                print(
                    "Future prompts will not receive "
                    "project memory."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()

                continue

            # =================================================
            # MEMORY REFRESH
            # =================================================

            if prompt.lower() == "/memory refresh":

                memory_session.refresh()

                print("\nMemory refresh queued.")

                print(
                    "The current project-memory snapshot "
                    "will be included in the next prompt."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()

                continue

            # =================================================
            # SAVE — RESERVED FOR NEXT STEP
            # =================================================
            # =================================================
            # SAVE
            # =================================================

            if prompt.lower() == "/save":

                print("\n==============================")
                print("       SAVING MEMORY")
                print("==============================\n")

                print("Reviewing current conversation...")

                save_prompt = build_save_prompt()

                print("Sending save request to ChatGPT...\n")

                state, result = chatgpt.send_prompt(
                    save_prompt
                )

                if state == "NOT_READY":

                    print_not_ready(result)

                    wait_for_user(
                        "Fix the ChatGPT browser, "
                        "then press ENTER..."
                    )

                    continue

                if state == "SEND_ERROR":

                    print_send_error(result)

                    wait_for_user(
                        "Fix the browser and "
                        "press ENTER..."
                    )

                    continue

                if state == "RATE_LIMITED":

                    print_rate_limited(result)

                    wait_for_user(
                        "Press ENTER after checking ChatGPT..."
                    )

                    continue

                if state == "AUTH_REQUIRED":

                    print_auth_required(result)

                    wait_for_user(
                        "Sign in using the browser, "
                        "then press ENTER..."
                    )

                    continue

                if state == "USER_ACTION_REQUIRED":

                    print_user_action(result)

                    wait_for_user(
                        "Complete the action in the browser, "
                        "then press ENTER..."
                    )

                    continue

                if state == "TIMEOUT_UNKNOWN":

                    print_unknown_state()

                    wait_for_user(
                        "Press ENTER to continue..."
                    )

                    continue

                if state == "COMPLETED":

                    print("==============================")
                    print("ChatGPT's memory review:")
                    print("==============================\n")

                    print(result)

                    try:

                        saved_files = (
                            memory_saver.save_from_response(
                                result
                            )
                        )

                    except ValueError as error:

                        print(
                            "\nMemory proposal was rejected."
                        )

                        print(
                            f"Reason: {error}"
                        )

                        continue

                    except Exception as error:

                        print(
                            "\nCould not update project memory."
                        )

                        print(
                            f"Error: {error}"
                        )

                        continue

                    if not saved_files:

                        print(
                            "\nNo new important information "
                            "was identified."
                        )

                    else:

                        print(
                            "\nMemory updated successfully:"
                        )

                        for path in saved_files:

                            print(
                                f"✓ {path.name}"
                            )

                    print()

                    continue

            # =================================================
            # DETERMINE WHETHER MEMORY IS USED
            # =================================================

            include_memory = (
                memory_session.should_include_memory()
            )

            # =================================================
            # BUILD MODEL PROMPT
            # =================================================

            try:

                final_prompt = context_builder.build(
                    prompt,
                    include_memory=include_memory
                )

            except Exception as error:

                print("\nCould not build context.")
                print(error)

                continue

            # =================================================
            # SEND TO CHATGPT
            # =================================================

            print("\nSending...")

            state, result = chatgpt.send_prompt(
                final_prompt
            )

            # =================================================
            # MARK MEMORY AS SENT
            # =================================================

            if (
                include_memory
                and state not in [
                    "NOT_READY",
                    "SEND_ERROR"
                ]
            ):
                memory_session.mark_memory_sent()

            # =================================================
            # COMPLETED
            # =================================================

            if state == "COMPLETED":

                print_response(result)

            # =================================================
            # USER ACTION
            # =================================================

            elif state == "USER_ACTION_REQUIRED":

                print_user_action(result)

                wait_for_user(
                    "Complete the action in the browser, "
                    "then press ENTER..."
                )

            # =================================================
            # NOT READY
            # =================================================

            elif state == "NOT_READY":

                print_not_ready(result)

                wait_for_user(
                    "Fix the ChatGPT browser, "
                    "then press ENTER..."
                )

            # =================================================
            # RATE LIMITED
            # =================================================

            elif state == "RATE_LIMITED":

                print_rate_limited(result)

                wait_for_user(
                    "Press ENTER after checking ChatGPT..."
                )

            # =================================================
            # AUTH REQUIRED
            # =================================================

            elif state == "AUTH_REQUIRED":

                print_auth_required(result)

                wait_for_user(
                    "Sign in using the browser, "
                    "then press ENTER..."
                )

            # =================================================
            # SEND ERROR
            # =================================================

            elif state == "SEND_ERROR":

                print_send_error(result)

                wait_for_user(
                    "Fix the browser and press ENTER..."
                )

            # =================================================
            # UNKNOWN TIMEOUT
            # =================================================

            elif state == "TIMEOUT_UNKNOWN":

                print_unknown_state()

                wait_for_user(
                    "Press ENTER to continue..."
                )

            # =================================================
            # SHOW CURRENT MEMORY STATUS
            # =================================================

            print(
                f"Memory: {memory_session.get_status()}"
            )

            print()


if __name__ == "__main__":
    main()
