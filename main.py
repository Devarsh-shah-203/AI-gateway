from playwright.sync_api import sync_playwright

from browser.connection import connect_to_chrome
from browser.chatgpt import ChatGPTBrowser
from context.builder import ContextBuilder
from context.session import MemoryContextSession
from memory.manager import MemoryManager
from memory.prompts import build_save_prompt
from memory.saver import MemorySaver
from workspace.manager import WorkspaceManager
from terminal.ui import (
    print_auth_required,
    print_header,
    print_memory,
    print_memory_status,
    print_not_ready,
    print_rate_limited,
    print_response,
    print_send_error,
    print_unknown_state,
    print_user_action,
    wait_for_user,
    print_workspace,
)


def print_activity(title):
    """Show one clean status banner for an active request."""
    print("\n" + "-" * 56)
    print(f"  {title}")
    print("-" * 56)


def handle_interrupted_state(state, result):
    """
    Handle provider states that require user intervention.

    Returns:
        True  -> caller should continue the main loop.
        False -> state needs no interruption handling.
    """

    if state == "NOT_READY":
        print_not_ready(result)
        wait_for_user(
            "Fix the ChatGPT browser, then press ENTER..."
        )
        return True

    if state == "SEND_ERROR":
        print_send_error(result)
        wait_for_user(
            "Fix the browser and press ENTER..."
        )
        return True

    if state == "RATE_LIMITED":
        print_rate_limited(result)
        wait_for_user(
            "Press ENTER after checking ChatGPT..."
        )
        return True

    if state == "AUTH_REQUIRED":
        print_auth_required(result)
        wait_for_user(
            "Sign in using the browser, then press ENTER..."
        )
        return True

    if state == "USER_ACTION_REQUIRED":
        print_user_action(result)
        wait_for_user(
            "Complete the action in the browser, then press ENTER..."
        )
        return True

    if state == "TIMEOUT_UNKNOWN":
        print_unknown_state()
        wait_for_user(
            "Press ENTER to continue..."
        )
        return True

    return False


def save_memory_from_response(result, memory_saver):
    """Validate and safely persist a completed /save response."""

    try:
        saved_files = memory_saver.save_from_response(result)

    except ValueError as error:
        print("\nMemory proposal was rejected.")
        print(f"Reason: {error}")
        return

    except Exception as error:
        print("\nCould not update project memory.")
        print(f"Error: {error}")
        return

    if not saved_files:
        print("\nNo new important information was identified.")
        return

    print("\nMemory updated successfully:")

    for path in saved_files:
        print(f"  + {path.name}")


def main():
    with sync_playwright() as p:

        # --------------------------------------------------
        # CONNECT TO CHROME
        # --------------------------------------------------

        print_activity("Connecting to Chrome")

        browser = connect_to_chrome(p)

        print("  Connected.")

        # --------------------------------------------------
        # CHATGPT
        # --------------------------------------------------

        try:
            chatgpt = ChatGPTBrowser(browser)

        except RuntimeError as error:
            print(f"\n{error}")
            return

        print("  ChatGPT found.")

        # --------------------------------------------------
        # MEMORY / CONTEXT
        # --------------------------------------------------

        memory = MemoryManager()
        context_builder = ContextBuilder()

        # OFF  -> no memory injection
        # ON   -> include memory once, then snapshot is loaded
        # NEXT -> include memory in the next normal prompt only
        memory_session = MemoryContextSession()
        memory_saver = MemorySaver()

        # --------------------------------------------------
        # HEADER
        # --------------------------------------------------

        print_header(
            memory_session.get_status()
        )

        # --------------------------------------------------
        # INTERACTIVE LOOP
        # --------------------------------------------------

        while True:

            prompt = input("> ").strip()

            if not prompt:
                continue

            command = prompt.lower()

            # --------------------------------------------------
            # EXIT
            # --------------------------------------------------

            if command == "/exit":
                print("\nGoodbye.")
                break

            # --------------------------------------------------
            # SHOW MEMORY
            # --------------------------------------------------

            if command == "/memory":
                print_memory(
                    memory.read_all()
                )
                continue

            # --------------------------------------------------
            # WORKSPACE
            # --------------------------------------------------
            workspace = WorkspaceManager()

            if command == "/workspace":

                print_workspace(
                    workspace.get_status()
                )

                continue


            # --------------------------------------------------
            # WORKSPACE ADD
            # --------------------------------------------------

            if command.startswith("/workspace add"):

                raw_path = prompt[
                    len("/workspace add"):
                ].strip()

                if not raw_path:

                    print(
                        "\nUsage:"
                    )

                    print(
                        "  /workspace add <directory>"
                    )

                    continue

                # Allow paths with spaces wrapped in quotes.
                path = raw_path.strip('"')

                try:

                    entry = workspace.add_directory(
                        path
                    )

                except (ValueError, TypeError) as error:

                    print(
                        "\nCould not add workspace directory."
                    )

                    print(
                        f"Reason: {error}"
                    )

                    continue

                print(
                    "\nWorkspace directory added."
                )

                print(
                    f"  [{entry['id']}] "
                    f"{entry['path']}"
                )

                print()

                continue
            # --------------------------------------------------
            # WORKSPACE REMOVE
            # --------------------------------------------------

            if command.startswith("/workspace remove"):

                raw_id = prompt[
                    len("/workspace remove"):
                ].strip()

                if not raw_id:
                    print(
                        "\nUsage:\n"
                        "  /workspace remove <id>"
                    )
                    continue

                if not raw_id.isdigit():
                    print(
                        "\nWorkspace ID must be a number."
                    )
                    continue

                workspace_id = int(raw_id)

                try:
                    removed = workspace.remove_directory(
                        workspace_id
                    )

                except (ValueError, TypeError) as error:
                    print(
                        "\nCould not remove workspace directory."
                    )
                    print(
                        f"Reason: {error}"
                    )
                    continue

                print(
                    "\nWorkspace directory removed."
                )
                print(
                    f"  [{removed['id']}] "
                    f"{removed['path']}"
                )
                print()

                continue

            # --------------------------------------------------
            # WORKSPACE CLEAR
            # --------------------------------------------------

            if command == "/workspace clear":

                directories = workspace.list_directories()

                if not directories:
                    print(
                        "\nNo workspace directories are configured."
                    )
                    continue

                count = len(directories)

                workspace.clear()

                print(
                    f"\nWorkspace cleared. "
                    f"{count} director{'y' if count == 1 else 'ies'} removed."
                )

                continue

            # --------------------------------------------------
            # MEMORY USE
            # --------------------------------------------------

            if command == "/memory use":

                memory_session.use_once()

                print_activity("Memory mode: NEXT")
                print(
                    "  Project memory will be included "
                    "in the next normal prompt only."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()
                continue

            # --------------------------------------------------
            # MEMORY ON
            # --------------------------------------------------

            if command == "/memory on":

                memory_session.enable()

                print_activity("Memory mode: ON")
                print(
                    "  The current project-memory snapshot "
                    "will be included in the next normal prompt."
                )
                print(
                    "  It will not be resent with every prompt."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()
                continue

            # --------------------------------------------------
            # MEMORY OFF
            # --------------------------------------------------

            if command == "/memory off":

                memory_session.disable()

                print_activity("Memory mode: OFF")
                print(
                    "  Future prompts will not receive "
                    "project memory."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()
                continue

            # --------------------------------------------------
            # MEMORY REFRESH
            # --------------------------------------------------

            if command == "/memory refresh":

                memory_session.refresh()

                print_activity("Memory refresh queued")
                print(
                    "  The current project-memory snapshot "
                    "will be included in the next normal prompt."
                )

                print_memory_status(
                    memory_session.get_status()
                )

                print()
                continue

            # --------------------------------------------------
            # SAVE MEMORY
            # --------------------------------------------------

            if command == "/save":

                print_activity("Saving project memory")
                print("  Reviewing current conversation...")

                save_prompt = build_save_prompt()

                print("  Sending memory review to ChatGPT...")

                state, result = chatgpt.send_prompt(
                    save_prompt
                )

                if handle_interrupted_state(
                    state,
                    result
                ):
                    continue

                if state != "COMPLETED":
                    print("\nMemory save did not complete.")
                    continue

                print("\n" + "-" * 56)
                print("  ChatGPT memory review")
                print("-" * 56)
                print(result)

                save_memory_from_response(
                    result,
                    memory_saver
                )

                print()
                continue

            # --------------------------------------------------
            # DETERMINE MEMORY USAGE
            # --------------------------------------------------

            include_memory = (
                memory_session.should_include_memory()
            )

            # --------------------------------------------------
            # BUILD MODEL PROMPT
            # --------------------------------------------------

            try:
                final_prompt = context_builder.build(
                    prompt,
                    include_memory=include_memory
                )

            except Exception as error:
                print("\nCould not build context.")
                print(error)
                continue

            # --------------------------------------------------
            # SEND TO CHATGPT
            # --------------------------------------------------

            print_activity(
                "Sending request to ChatGPT"
            )

            if include_memory:
                print("  Project memory snapshot: attached")

            state, result = chatgpt.send_prompt(
                final_prompt
            )

            # --------------------------------------------------
            # MARK MEMORY AS SENT
            # --------------------------------------------------

            if (
                include_memory
                and state not in [
                    "NOT_READY",
                    "SEND_ERROR",
                ]
            ):
                memory_session.mark_memory_sent()

            # --------------------------------------------------
            # RESPONSE / INTERRUPTION
            # --------------------------------------------------

            if state == "COMPLETED":
                print_response(result)

            elif not handle_interrupted_state(
                state,
                result
            ):
                print("\nUnhandled ChatGPT state.")

            # --------------------------------------------------
            # MEMORY STATUS
            # --------------------------------------------------

            print_memory_status(
                memory_session.get_status()
            )

            print()


if __name__ == "__main__":
    main()
