from files.edit_parser import FileEdit
from files.edit_validator import ValidatedEdit


class EditEngine:

    def apply(
        self,
        validated_edit: ValidatedEdit,
        original_content: str,
    ) -> str:

        edit = validated_edit.edit

        if edit.operation == "replace":
            return self._replace(
                original_content,
                validated_edit.match_start,
                validated_edit.match_end,
                edit.content,
            )

        if edit.operation == "insert_before":
            return self._insert_before(
                original_content,
                validated_edit.match_start,
                edit.content,
            )

        if edit.operation == "insert_after":
            return self._insert_after(
                original_content,
                validated_edit.match_end,
                edit.content,
            )

        if edit.operation == "insert_start":
            return edit.content + original_content

        if edit.operation == "insert_end":
            return original_content + edit.content

        raise ValueError(
            f"Unsupported edit operation: {edit.operation}"
        )

    @staticmethod
    def _replace(
        content: str,
        start: int,
        end: int,
        replacement: str,
    ) -> str:

        return (
            content[:start]
            + replacement
            + content[end:]
        )

    @staticmethod
    def _insert_before(
        content: str,
        start: int,
        insertion: str,
    ) -> str:

        return (
            content[:start]
            + insertion
            + content[start:]
        )

    @staticmethod
    def _insert_after(
        content: str,
        end: int,
        insertion: str,
    ):

        return (
            content[:end]
            + insertion
            + content[end:]
        )