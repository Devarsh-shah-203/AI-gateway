import re
from dataclasses import dataclass


EDIT_BLOCK_PATTERN = re.compile(
    r"<AI_EDIT>\s*(.*?)\s*</AI_EDIT>",
    re.DOTALL,
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

    def parse(self, response: str) -> list[FileEdit]:

        if not isinstance(response, str):
            raise TypeError("Response must be a string.")

        ai_edit_match = EDIT_BLOCK_PATTERN.search(response)

        if not ai_edit_match:
            raise ValueError("No <AI_EDIT> block found.")

        raw_block = ai_edit_match.group(1)

        edit_blocks = EDIT_PATTERN.findall(raw_block)

        if not edit_blocks:
            raise ValueError(
                "No <EDIT> blocks found inside <AI_EDIT>."
            )

        parsed_edits = []

        for index, block in enumerate(edit_blocks):

            operation = self._extract_field(
                block,
                "operation",
                index,
            )

            file = self._extract_field(
                block,
                "file",
                index,
            )

            match_text = self._extract_section(
                block,
                "MATCH",
                index,
            )

            content = self._extract_section(
                block,
                "CONTENT",
                index,
            )

            reason = self._extract_section(
                block,
                "REASON",
                index,
            )

            operation = operation.strip()
            file = file.strip()
            reason = reason.strip()

            if operation not in ALLOWED_OPERATIONS:
                raise ValueError(
                    f"Edit {index}: unsupported operation "
                    f"'{operation}'."
                )

            if not file:
                raise ValueError(
                    f"Edit {index}: invalid file."
                )

            if not reason:
                raise ValueError(
                    f"Edit {index}: reason must not be empty."
                )

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
    def _extract_field(
        block: str,
        field_name: str,
        index: int,
    ) -> str:
        pattern = re.compile(
            rf"^\s*{re.escape(field_name)}\s*:\s*(.*?)\s*$",
            re.MULTILINE,
        )

        match = pattern.search(block)

        if not match:
            raise ValueError(
                f"Edit {index}: missing '{field_name}'."
            )

        return match.group(1)

    @staticmethod
    def _extract_section(   
        block: str,
        section_name: str,
        index: int,
    ) -> str:
        pattern = re.compile(
            rf"<{re.escape(section_name)}>(.*?)"
            rf"</{re.escape(section_name)}>",
            re.DOTALL | re.IGNORECASE,
        )

        match = pattern.search(block)

        if not match:
            raise ValueError(
                f"Edit {index}: missing "
                f"<{section_name}> section."
            )

        return match.group(1).strip("\r\n")