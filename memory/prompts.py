def build_save_prompt():
    """
    Build the instruction used by /save.

    The current ChatGPT conversation already contains the
    conversation history, so we only provide instructions
    for extracting durable project memory.
    """

    return """
Go
"""