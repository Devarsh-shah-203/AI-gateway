def build_save_prompt(memory):
    """
    Build the instruction used by /save.

    The current model conversation already contains the
    conversation history, so we do not need to copy it into
    this prompt.

    We only provide the current local project memory so the
    model can avoid unnecessary duplicates.
    """

    if not isinstance(memory, dict):
        raise TypeError(
            "Memory must be provided as a dictionary."
        )

    sections = []

    for name, content in memory.items():

        if not content.strip():
            continue

        title = name.replace(
            "_", " "
        ).upper()

        sections.append(
            f"## {title}\n\n{content.strip()}"
        )

    memory_text = "\n\n".join(sections)

    return f"""
You are maintaining persistent memory for a software project or another type of project.

Review the ENTIRE conversation so far and identify only
information that is genuinely useful for future sessions.

Your goal is to keep project memory compact, accurate,
and useful.

IMPORTANT:
- The conversation history is already available to you.
- Do not ask the user to provide the conversation again.
- Do not save routine conversation.
- Do not save casual discussion.
- Do not save duplicate information.
- Do not invent information.
- Do not delete existing memory.
- Do not rewrite existing memory.
- Only propose new information that should persist.

Useful things to remember include:

- Important project decisions
- Completed work
- Important technical discoveries
- Approaches that failed and should not be repeated
- Reusable solutions or patterns
- Important future tasks or next steps

Choose the most appropriate memory file:

- plan
- progress
- discoveries
- closed_ideas
- cookbooks

CURRENT LOCAL PROJECT MEMORY
============================

{memory_text if memory_text else "[No existing memory]"}


MEMORY UPDATE PROTOCOL
======================

Return your normal explanation first.

Then return EXACTLY ONE machine-readable block:

<AI_MEMORY>
{{
    "updates": [
        {{
            "file": "progress",
            "content": "..."
        }}
    ]
}}
</AI_MEMORY>

The "file" field MUST be one of:

- plan
- progress
- discoveries
- closed_ideas
- cookbooks

The "content" field must contain only the new information
that should be appended to that memory file.

If nothing new and important should be saved, return:

<AI_MEMORY>
{{
    "updates": []
}}
</AI_MEMORY>

Do not return any filesystem commands.
Do not return file paths outside the allowed memory files.
"""