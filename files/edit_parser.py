"""Parse the provider-neutral AI Gateway edit protocol."""

from __future__ import annotations

import re
from dataclasses import dataclass


EDIT_BLOCK_PATTERN = re.compile(
    r"<AI_EDIT\s*>(.*?)</AI_EDIT\s*>", re.DOTALL | re.IGNORECASE
)
EDIT_PATTERN = re.compile(
    r"<EDIT\s*>(.*?)</EDIT\s*>", re.DOTALL | re.IGNORECASE
)

ALLOWED_OPERATIONS = {
    "replace",
    "insert_before",
    "insert_after",
    "insert_start",
    "insert_end",
    # Structured Jupyter notebook operations. These are handled by the same
    # validator/workflow, using a document-format adapter.
    "edit_cell",
    "insert_cell",
}

NOTEBOOK_OPERATIONS = {"edit_cell", "insert_cell"}


@dataclass(frozen=True)
class FileEdit:
    operation: str
    file: str
    match: str
    content: str
    reason: str
    cell_index: int | None = None
    cell_type: str | None = None
    position: str | None = None


class EditParser:
    """Parse proposed edits while keeping Markdown fences out of file data."""

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

        raw_block = self._repair_unambiguous_missing_edit_closers(ai_edit_match.group(1))
        edit_blocks = EDIT_PATTERN.findall(raw_block)
        if not edit_blocks:
            raise ValueError("No <EDIT> blocks found inside <AI_EDIT>.")

        open_count = len(re.findall(r"<EDIT\s*>", raw_block, re.IGNORECASE))
        close_count = len(re.findall(r"</EDIT\s*>", raw_block, re.IGNORECASE))
        if open_count != close_count or open_count != len(edit_blocks):
            raise ValueError("Malformed <EDIT> tags in AI_EDIT block.")

        parsed_edits: list[FileEdit] = []
        for index, block in enumerate(edit_blocks):
            # Header metadata must come before MATCH. Read fields only from the
            # header so source code containing text like "cell_index: 3" cannot
            # accidentally become protocol metadata.
            header = re.split(r"<MATCH\s*>", block, maxsplit=1, flags=re.IGNORECASE)[0]
            operation = self._extract_field(header, "operation", index).strip().lower()
            file = self._extract_field(header, "file", index).strip()
            cell_index_raw = self._extract_optional_field(header, "cell_index", index)
            cell_type_raw = self._extract_optional_field(header, "cell_type", index)
            position_raw = self._extract_optional_field(header, "position", index)

            cell_index = None
            if cell_index_raw is not None:
                if not re.fullmatch(r"\d+", cell_index_raw.strip()):
                    raise ValueError(f"Edit {index}: cell_index must be a zero-based non-negative integer.")
                cell_index = int(cell_index_raw.strip())

            cell_type = cell_type_raw.strip().lower() if cell_type_raw is not None else None
            position = position_raw.strip().lower() if position_raw is not None else None

            match_text = self._extract_section(block, "MATCH", index)
            raw_content = self._extract_section(block, "CONTENT", index)
            content = self._unwrap_optional_code_fence(raw_content, index)
            reason = self._extract_section(block, "REASON", index).strip()

            if operation not in ALLOWED_OPERATIONS:
                raise ValueError(f"Edit {index}: unsupported operation '{operation}'.")
            if not file:
                raise ValueError(f"Edit {index}: invalid file.")
            if not reason:
                raise ValueError(f"Edit {index}: reason must not be empty.")

            self._validate_operation_metadata(
                index=index,
                operation=operation,
                cell_index=cell_index,
                cell_type=cell_type,
                position=position,
            )

            parsed_edits.append(
                FileEdit(
                    operation=operation,
                    file=file,
                    match=match_text,
                    content=content,
                    reason=reason,
                    cell_index=cell_index,
                    cell_type=cell_type,
                    position=position,
                )
            )

        return parsed_edits


    @staticmethod
    def _repair_unambiguous_missing_edit_closers(raw_block: str) -> str:
        """Repair only missing </EDIT> tags after a completed REASON section.

        Some model responses omit an operation's closing </EDIT> and start the
        next <EDIT>, or close the outer AI_EDIT block immediately after
        </REASON>. When the REASON section is already closed at either boundary,
        the intended boundary is unambiguous. Incomplete MATCH/CONTENT/REASON
        sections are not repaired; the normal parser rejects them.
        """
        # If a completed operation is followed directly by a new operation,
        # supply the missing close. Leave already well-formed operations alone.
        raw_block = re.sub(
            r"(</REASON\s*>)(?=\s*<EDIT\s*>)",
            r"\1\n</EDIT>",
            raw_block,
            flags=re.IGNORECASE,
        )

        # EDIT_BLOCK_PATTERN removes the outer closing tag before this helper
        # runs, so the final incomplete operation ends at the end of raw_block.
        raw_block = re.sub(
            r"(</REASON\s*>)(\s*)$",
            r"\1\n</EDIT>\2",
            raw_block,
            flags=re.IGNORECASE,
        )
        return raw_block

    @staticmethod
    def _extract_field(block: str, field_name: str, index: int) -> str:
        values = EditParser._extract_field_values(block, field_name)
        if not values:
            raise ValueError(f"Edit {index}: missing '{field_name}'.")
        if len(values) > 1:
            raise ValueError(f"Edit {index}: duplicate '{field_name}' field.")
        return values[0]

    @staticmethod
    def _extract_optional_field(block: str, field_name: str, index: int) -> str | None:
        values = EditParser._extract_field_values(block, field_name)
        if len(values) > 1:
            raise ValueError(f"Edit {index}: duplicate '{field_name}' field.")
        return values[0] if values else None

    @staticmethod
    def _extract_field_values(block: str, field_name: str) -> list[str]:
        pattern = re.compile(
            rf"^\s*{re.escape(field_name)}\s*:\s*(.*?)\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        return [match.group(1) for match in pattern.finditer(block)]

    @staticmethod
    def _validate_operation_metadata(
        *, index: int, operation: str, cell_index: int | None,
        cell_type: str | None, position: str | None,
    ) -> None:
        if operation == "edit_cell":
            if cell_index is None:
                raise ValueError(f"Edit {index}: edit_cell requires cell_index.")
            if cell_type is not None or position is not None:
                raise ValueError(f"Edit {index}: edit_cell does not accept cell_type or position.")
            return

        if operation == "insert_cell":
            if cell_type not in {"code", "markdown"}:
                raise ValueError(f"Edit {index}: insert_cell requires cell_type: code or markdown.")
            if position not in {"before", "after", "start", "end"}:
                raise ValueError(f"Edit {index}: insert_cell requires position: before, after, start, or end.")
            if position in {"before", "after"} and cell_index is None:
                raise ValueError(f"Edit {index}: position '{position}' requires cell_index.")
            if position in {"start", "end"} and cell_index is not None:
                raise ValueError(f"Edit {index}: position '{position}' must not specify cell_index.")
            return

        if cell_index is not None or cell_type is not None or position is not None:
            raise ValueError(f"Edit {index}: notebook fields are only valid for edit_cell or insert_cell.")

    @classmethod
    def _extract_section(cls, block: str, section_name: str, index: int) -> str:
        pattern = re.compile(
            rf"<{re.escape(section_name)}\s*>(.*?)</{re.escape(section_name)}\s*>",
            re.DOTALL | re.IGNORECASE,
        )
        matches = list(pattern.finditer(block))
        if len(matches) != 1:
            raise ValueError(f"Edit {index}: expected exactly one <{section_name}> section.")
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
        """Strip one complete outer fence of any length; reject half-fences.

        Supporting four-backtick outer fences permits a Markdown notebook cell
        to contain an ordinary triple-backtick code fence without confusing the
        content fence with the code fence inside the cell.
        """
        if not content:
            return content
        lines = content.splitlines(keepends=True)
        if not lines:
            return content

        first = lines[0].rstrip("\r\n")
        last = lines[-1].rstrip("\r\n")
        opening_match = re.fullmatch(r"[ \t]*(`{3,})([^\r\n]*)", first)
        closing_any = re.fullmatch(r"[ \t]*`{3,}[ \t]*", last) is not None

        if opening_match:
            fence = opening_match.group(1)
            expected_close = re.fullmatch(re.escape(fence) + r"[ \t]*", last) is not None
            if len(lines) < 2 or not expected_close:
                raise ValueError(
                    f"Edit {index}: CONTENT must use one complete outer fence with a matching closing fence; refusing the edit."
                )
            body = "".join(lines[1:-1])
            # One line ending belongs to the fence layout (the closing fence
            # must start on its own line). Any additional final line ending is
            # intentional content and remains in the payload.
            if body.endswith("\r\n"):
                body = body[:-2]
            elif body.endswith(("\n", "\r")):
                body = body[:-1]
            return body

        if closing_any:
            raise ValueError(f"Edit {index}: CONTENT has a closing fence without an opening fence.")
        return content
