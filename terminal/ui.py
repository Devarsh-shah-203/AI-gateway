def print_header():
    print("\n==============================")
    print("        AI Gateway")
    print("==============================")
    print("Type /exit to quit.\n")


def print_response(response):
    print("==============================")
    print("ChatGPT:")
    print("==============================\n")
    print(response)
    print()


def print_not_ready(reason):
    print("==============================")
    print("CHATGPT IS NOT READY")
    print("==============================\n")
    print(reason)


def print_user_action(message):
    print("==============================")
    print("CHATGPT NEEDS YOUR INPUT")
    print("==============================\n")
    print(message)


def print_rate_limited(message):
    print("==============================")
    print("CHATGPT USAGE LIMIT")
    print("==============================\n")

    print("ChatGPT appears to have reached a usage limit.")
    print("\nDetected information:")
    print(message)


def print_auth_required(message):
    print("==============================")
    print("AUTHENTICATION REQUIRED")
    print("==============================\n")

    print("The ChatGPT session may have expired.")
    print("\nDetected information:")
    print(message)


def print_send_error(message):
    print("==============================")
    print("COULD NOT SEND PROMPT")
    print("==============================\n")
    print(message)


def print_unknown_state():
    print("==============================")
    print("UNKNOWN CHATGPT STATE")
    print("==============================\n")

    print("ChatGPT did not produce a completed response.")
    print("\nCheck the browser.")


def wait_for_user(message):
    input(f"\n{message}")