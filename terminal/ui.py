def print_header(memory_mode="OFF"):
    print()
    print("=" * 56)
    print("                    AI GATEWAY")
    print("=" * 56)
    print(f"  Memory: {memory_mode}")
    print()
    print("  /memory          View project memory")
    print("  /memory use      Use memory once")
    print("  /memory on/off   Enable or disable memory")
    print("  /memory refresh  Refresh the memory snapshot")
    print("  /save            Save durable project knowledge")
    print("  /exit            Quit")
    print("=" * 56)


def print_response(response):
    print()
    print("-" * 56)
    print("  ChatGPT")
    print("-" * 56)
    print(response)
    print()


def print_not_ready(reason):
    print()
    print("-" * 56)
    print("  CHATGPT IS NOT READY")
    print("-" * 56)
    print(reason)


def print_user_action(message):
    print()
    print("-" * 56)
    print("  CHATGPT NEEDS YOUR INPUT")
    print("-" * 56)
    print(message)


def print_rate_limited(message):
    print()
    print("-" * 56)
    print("  CHATGPT USAGE LIMIT")
    print("-" * 56)
    print("ChatGPT appears to have reached a usage limit.")
    print("\nDetected information:")
    print(message)


def print_auth_required(message):
    print()
    print("-" * 56)
    print("  AUTHENTICATION REQUIRED")
    print("-" * 56)
    print("The ChatGPT session may have expired.")
    print("\nDetected information:")
    print(message)


def print_send_error(message):
    print()
    print("-" * 56)
    print("  COULD NOT SEND PROMPT")
    print("-" * 56)
    print(message)


def print_unknown_state():
    print()
    print("-" * 56)
    print("  UNKNOWN CHATGPT STATE")
    print("-" * 56)
    print("ChatGPT did not produce a completed response.")
    print("\nCheck the browser.")


def wait_for_user(message):
    input(f"\n{message}")


def print_memory(memory):
    print()
    print("=" * 56)
    print("                    PROJECT MEMORY")
    print("=" * 56)

    for name, content in memory.items():

        title = name.replace(
            "_",
            " "
        ).upper()

        print()
        print(f"[ {title} ]")
        print("-" * 56)

        if content.strip():
            print(content.strip())
        else:
            print("[EMPTY]")

    print()


def print_memory_status(status):
    print(
        f"Memory: {status['mode']} "
        f"| Snapshot: {status['snapshot']}"
    )

from pathlib import Path
def print_workspace(directories):
    """
    Display the currently configured workspace directories.
    """

    print()
    print("=" * 56)
    print("                 WORKSPACE")
    print("=" * 56)

    if not directories:
        print()
        print("  No workspace directories configured.")
        print()
        print("  Add one with:")
        print("  /workspace add <directory>")
        print()
        print("=" * 56)
        return

    print()

    for entry in directories:

        path = Path(entry["path"])

        print(
            f"  [{entry['id']}] {path.name}"
        )

        print(
            f"      {path}"
        )

        print(
            f"      Status: {entry['status']}"
        )

        print()

    print(
        f"  {len(directories)} "
        f"directory{'ies' if len(directories) != 1 else ''} configured"
    )

    print("=" * 56)