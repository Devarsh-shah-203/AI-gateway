EDIT_PROMPT = """
You are in EDIT MODE.

The user has explicitly requested a change to project files.
Propose the exact edits. Do not modify files yourself.

Return exactly one <AI_EDIT> block containing one or more <EDIT> blocks.

Format:

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
</CONTENT> <REASON> Add the requested function. </REASON> </EDIT> </AI_EDIT>

Allowed operations:

replace
insert_before
insert_after
insert_start
insert_end

Rules:

file must be a provided workspace-relative file.
For replace, insert_before, and insert_after, MATCH must be copied exactly from the provided file.
MATCH must identify exactly one location.
For insert_start and insert_end, MATCH is empty.
CONTENT is the exact text to write.
Preserve all indentation, whitespace, and newlines in CONTENT.
Use a Markdown code fence for source code inside CONTENT.
Do not include the code fence itself in the file content.
Make only the requested changes.
Do not use line numbers.
Do not return JSON or a unified diff.
Do not modify files directly.
REASON briefly explains the proposed change.
Put all required edits inside the same <AI_EDIT> block.

If the required file or information is missing, ask for it instead of guessing.

before sending check that all tags have written properly and are closed accordingly
PROJECT FILE CONTEXT:
{file_context}

USER EDIT REQUEST:
{user_prompt}
"""


def build_edit_prompt(user_prompt, file_context):
    formatted_files = []

    for file in file_context:
        formatted_files.append(
            f'FILE: {file["reference"]}\n'
            f'PATH: {file["path"]}\n'
            f'CONTENT:\n'
            f'{file["content"]}'
        )

    files_text = "\n\n" + "\n\n".join(formatted_files)

    return (
        EDIT_PROMPT
        .replace("{file_context}", files_text)
        .replace("{user_prompt}", user_prompt)
    )