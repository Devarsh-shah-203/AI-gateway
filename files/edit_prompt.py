"""Build structured, low-overhead prompts for AI Gateway file edits."""

EDIT_PROTOCOL = r"""You are in AI Gateway EDIT MODE. Propose file edits only; do not claim to have changed files directly.

Return exactly one <AI_EDIT> block containing one or more <EDIT> blocks. Close every opening tag with its matching closing tag. Do not put prose outside the block unless required information is missing.

Required format:
<AI_EDIT>
<EDIT>
operation: insert_end
file: 1/test.py
<MATCH>
</MATCH>
<CONTENT>
```python
def hello():
    print("hello")
```
</CONTENT>
<REASON>
Add the requested function.
</REASON>
</EDIT>
</AI_EDIT>

Allowed operations: replace, insert_before, insert_after, insert_start, insert_end.

Rules:
- file must be a provided workspace-relative file reference.
- For replace, insert_before, and insert_after, MATCH must be copied exactly from the current file and identify exactly one location.
- MATCH must be empty only for insert_start and insert_end.
- Put the exact new source text inside CONTENT, wrapped in one complete Markdown fence (for example ```python ... ```). The opening fence must have a matching closing fence on its own line. The gateway removes the fence before writing; it must never become part of the source file.
- Preserve code indentation, intentional blank lines, and line breaks inside CONTENT. Include all tags exactly as shown; never put a closing tag inside a code fence.
- Make only the requested changes. Do not use line numbers, JSON, unified diffs, or direct file modifications.
- REASON must briefly explain the edit.
- Put all requested file changes inside the same AI_EDIT block. If file context is missing or ambiguous, ask for it rather than guessing.
INSERTION RULES:

For insert_before:
- CONTENT contains only the new text to insert.
- Do not include MATCH in CONTENT.
- The gateway preserves the existing matched text automatically.

For insert_after:
- CONTENT contains only the new text to insert.
- Do not repeat MATCH at the beginning of CONTENT.
- The gateway preserves the existing matched text automatically.

For replace:
- CONTENT is the complete replacement for MATCH.
CURRENT PROJECT FILE CONTEXT:
{file_context}

CURRENT USER EDIT REQUEST:
{user_prompt}
"""

# Later edits in the same browser conversation reuse the already-established
# contract. This avoids resending the full instruction block on every edit.
EDIT_CONTINUATION = r"""Continue using the established AI Gateway edit contract. Return exactly one <AI_EDIT> block containing correctly closed <EDIT>, <MATCH>, <CONTENT>, and <REASON> tags. Use only the allowed operations; MATCH must be exact (empty only for insert_start/insert_end). Put CONTENT source inside one complete Markdown fence with a matching closing fence; the gateway strips the fence before writing. Preserve indentation and line breaks. Make only the current requested changes, and ask rather than guess when required file context is missing.

CURRENT PROJECT FILE CONTEXT:
{file_context}

CURRENT USER EDIT REQUEST:
{user_prompt}
"""


def build_edit_prompt(user_prompt, file_context, *, include_instructions=True):
    """Build the first full edit prompt or a compact continuation prompt.

    ``file_context`` must contain only files explicitly referenced by the
    current request. The file contents are intentionally refreshed each time
    because a previous approved edit may have changed them.
    """
    formatted_files = []

    for file in file_context:
        formatted_files.append(
            f'FILE: {file["reference"]}\n'
            f'PATH: {file["path"]}\n'
            f'CONTENT:\n'
            f'{file["content"]}'
        )

    files_text = "\n\n".join(formatted_files) if formatted_files else "(No project file was referenced.)"
    template = EDIT_PROTOCOL if include_instructions else EDIT_CONTINUATION

    return template.format(
        file_context=files_text,
        user_prompt=user_prompt,
    )
