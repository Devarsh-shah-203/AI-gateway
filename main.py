from playwright.sync_api import sync_playwright

from browser.connection import connect_to_chrome
from browser.chatgpt import ChatGPTBrowser

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
)

from memory.manager import MemoryManager



def main():
    with sync_playwright() as p:

        # -----------------------------------------------
        # Connect to existing Chrome
        # -----------------------------------------------

        print("Connecting to Chrome...")

        browser = connect_to_chrome(p)

        print("Connected!")

        # -----------------------------------------------
        # Initialize ChatGPT browser provider
        # -----------------------------------------------

        try:
            chatgpt = ChatGPTBrowser(browser)

        except RuntimeError as error:
            print(error)
            return

        memory = MemoryManager()
        print("ChatGPT found!")

        # -----------------------------------------------
        # Start CLI
        # -----------------------------------------------

        print_header()


        # -----------------------------------------------
        # Interactive loop
        # -----------------------------------------------

        while True:

            prompt = input("> ").strip()

            # Ignore empty input
            if not prompt:
                continue

            if prompt.lower() == "/memory":
                print_memory(memory.read_all())
                continue

            # Exit
            if prompt.lower() == "/exit":
                print("\nGoodbye.")
                break

            # -------------------------------------------
            # Send prompt through ChatGPT provider
            # -------------------------------------------

            print("\nSending...")

            state, result = chatgpt.send_prompt(prompt)

            # -------------------------------------------
            # Completed
            # -------------------------------------------

            if state == "COMPLETED":

                print_response(result)

            # -------------------------------------------
            # ChatGPT needs user interaction
            # -------------------------------------------

            elif state == "USER_ACTION_REQUIRED":

               print_user_action(result)
               wait_for_user(
                    "Complete the action in the browser, "
                    "then press ENTER..."
                )

            # -------------------------------------------
            # UI isn't ready
            # -------------------------------------------

            elif state == "NOT_READY":

                print_not_ready(result)

                wait_for_user(
                    "Fix the ChatGPT browser, then press ENTER..."
                )

            # -------------------------------------------
            # Usage limit
            # -------------------------------------------

            elif state == "RATE_LIMITED":

                print_rate_limited(result)
                wait_for_user(
                    "Press ENTER after checking ChatGPT..."
                )

            # -------------------------------------------
            # Authentication required
            # -------------------------------------------

            elif state == "AUTH_REQUIRED":

                print_auth_required(result)
                wait_for_user(
                  "Sign in using the browser, then press ENTER..."
                )

            # -------------------------------------------
            # Sending failed
            # -------------------------------------------

            elif state == "SEND_ERROR":
                print_send_error(result)
                wait_for_user(
                    "Fix the browser and press ENTER..."
                )
                

            # -------------------------------------------
            # Unknown timeout/state
            # -------------------------------------------

            elif state == "TIMEOUT_UNKNOWN":

               print_unknown_state()
               wait_for_user(
                    "Press ENTER to continue..."
               )


if __name__ == "__main__":
    main()