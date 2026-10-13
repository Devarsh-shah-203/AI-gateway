import re
from dataclasses import dataclass


EDIT_BLOCK_PATTERN = re.compile(
    r"<AI_EDIT>\s*(.*?)\s*</AI_EDIT>",
    re.DOTALL | re.IGNORECASE,
)

EDIT_PATTERN = re.compile(
    r"<EDIT>(.*?)</EDIT>",
    re.DOTALL | re.IGNORECASE,
)

ALLOWED_OPERATIONS = {
    "replace",
    "insert_before",
    "insert_after",
    "insert_start",
    "insert_end",
}


@dataclass(frozen=True)
class FileEdit:
    operation: str
    file: str
    match: str
    content: str
    reason: str


class EditParser:
    """Parse proposed edits without leaking Markdown fences into files."""

    def parse(self, response: str) -> list[FileEdit]:
        if not isinstance(response, str):
            raise TypeError("Response must be a string.")

        ai_edit_match = EDIT_BLOCK_PATTERN.search(response)
        if not ai_edit_match:
            raise ValueError("No <AI_EDIT> block found.")

        # Reject malformed or multiple outer blocks rather than silently
        # applying only the first proposal.
        remainder = response[:ai_edit_match.start()] + response[ai_edit_match.end():]
        if EDIT_BLOCK_PATTERN.search(remainder):
            raise ValueError("Multiple <AI_EDIT> blocks are not allowed.")

        raw_block = ai_edit_match.group(1)
        edit_blocks = EDIT_PATTERN.findall(raw_block)
        if not edit_blocks:
            raise ValueError("No <EDIT> blocks found inside <AI_EDIT>.")

        # If opening and closing EDIT tags are not balanced, do not accept a
        # partial set of edits.
        open_count = len(re.findall(r"<EDIT\s*>", raw_block, re.IGNORECASE))
        close_count = len(re.findall(r"</EDIT\s*>", raw_block, re.IGNORECASE))
        if open_count != close_count or open_count != len(edit_blocks):
            raise ValueError("Malformed <EDIT> tags in AI_EDIT block.")

        parsed_edits = []
        for index, block in enumerate(edit_blocks):
            operation = self._extract_field(block, "operation", index).strip()
            file = self._extract_field(block, "file", index).strip()
            match_text = self._extract_section(block, "MATCH", index)
            raw_content = self._extract_section(block, "CONTENT", index)
            content = self._unwrap_optional_code_fence(raw_content, index)
            reason = self._extract_section(block, "REASON", index).strip()

            if operation not in ALLOWED_OPERATIONS:
                raise ValueError(
                    f"Edit {index}: unsupported operation '{operation}'."
                )
            if not file:
                raise ValueError(f"Edit {index}: invalid file.")
            if not reason:
                raise ValueError(f"Edit {index}: reason must not be empty.")

            parsed_edits.append(
                FileEdit(
                    operation=operation,
                    file=file,
                    match=match_text,
                    content=content,
                    reason=reason,
                )
            )

        return parsed_edits

    @staticmethod
    def _extract_field(block: str, field_name: str, index: int) -> str:
        pattern = re.compile(
            rf"^\s*{re.escape(field_name)}\s*:\s*(.*?)\s*$",
            re.MULTILINE,
        )
        match = pattern.search(block)
        if not match:
            raise ValueError(f"Edit {index}: missing '{field_name}'.")
        return match.group(1)

    @classmethod
    def _extract_section(cls, block: str, section_name: str, index: int) -> str:
        pattern = re.compile(
            rf"<{re.escape(section_name)}>(.*?)</{re.escape(section_name)}>",
            re.DOTALL | re.IGNORECASE,
        )
        matches = list(pattern.finditer(block))
        if len(matches) != 1:
            raise ValueError(
                f"Edit {index}: expected exactly one <{section_name}> section."
            )
        # Remove only the single newline used to separate the tag from its
        # payload. Do not strip indentation, spaces, or intentional blank lines.
        return cls._remove_tag_separator_newlines(matches[0].group(1))

    @staticmethod
    def _remove_tag_separator_newlines(value: str) -> str:
        if value.startswith("\r\n"):
            value = value[2:]
        elif value.startswith(("\n", "\r")):
            value = value[1:]

        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith(("\n", "\r")):
            value = value[:-1]

        return value

    @staticmethod
    def _unwrap_optional_code_fence(content: str, index: int) -> str:
        """Strip one complete outer Markdown fence; reject unmatched fences.

        Unfenced content is accepted as a compatibility fallback. If a response
        begins or ends with a fence but the matching pair is missing, parsing
        fails before any file can be written.
        """
        if not content:
            return content

        lines = content.splitlines(keepends=True)
        if not lines:
            return content

        first = lines[0].rstrip("\r\n")
        last = lines[-1].rstrip("\r\n")
        opening = re.fullmatch(r"[ \t]*```[^\r\n]*", first) is not None
        closing = re.fullmatch(r"[ \t]*```[ \t]*", last) is not None

        if opening:
            if len(lines) < 2 or not closing:
                raise ValueError(
                    f"Edit {index}: CONTENT starts with a Markdown fence "
                    "but has no matching closing fence; refusing the edit."
                )
            # Keep all body line endings (including its conventional final
            # newline) while removing just the first and last fence lines.
            return "".join(lines[1:-1])

        if closing:
            raise ValueError(
                f"Edit {index}: CONTENT has a closing fence without an opening fence."
            )

        return content
