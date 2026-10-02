def print_header(memory_mode="OFF"):
    print("\n==============================")
    print("        AI Gateway")
    print("==============================")
    print(f"Memory: {memory_mode}")
    print("Type /exit to quit.")
    print("Type /memory to view project memory.")
    print("Type /memory use|on|off to control memory.\n")

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

def print_memory(memory):
    """
    Display project memory in the terminal.

    memory:
        dict[str, str]
    """

    print("\n================================")
    print("        PROJECT MEMORY")
    print("================================\n")

    for name, content in memory.items():

        title = name.replace("_", " ").upper()

        print("--------------------------------")
        print(title)
        print("--------------------------------")

        if content.strip():
            print(content.strip())
        else:
            print("[EMPTY]")

        print()

def print_memory_status(status):
    """
    Display current memory-context state.
    """

    print(
        f"Memory: {status['mode']} "
        f"| Snapshot: {status['snapshot']}"
    )