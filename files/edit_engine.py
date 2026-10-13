from files.edit_parser import FileEdit
from files.edit_validator import ValidatedEdit


class EditEngine:
    """Apply validated text edits while protecting line boundaries."""

    def apply(self, validated_edit: ValidatedEdit, original_content: str) -> str:
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
                validated_edit.match_start,
                validated_edit.match_end,
                edit.content,
            )

        if edit.operation == "insert_start":
            return EditEngine._insert_at_file_start(original_content, edit.content)

        if edit.operation == "insert_end":
            return EditEngine._insert_at_file_end(original_content, edit.content)

        raise ValueError(f"Unsupported edit operation: {edit.operation}")

    @staticmethod
    def _is_line_ending(value: str) -> bool:
        return value.endswith(("\n", "\r"))

    @classmethod
    def _insert_at_file_start(cls, original: str, insertion: str) -> str:
        if not insertion or not original:
            return insertion + original
        separator = "" if cls._is_line_ending(insertion) or original.startswith(("\n", "\r")) else "\n"
        return insertion + separator + original

    @classmethod
    def _insert_at_file_end(cls, original: str, insertion: str) -> str:
        if not insertion or not original:
            return original + insertion
        separator = "" if cls._is_line_ending(original) or insertion.startswith(("\n", "\r")) else "\n"
        return original + separator + insertion

    @classmethod
    def _insert_before(cls, original: str, start: int, insertion: str) -> str:
        if not insertion:
            return original

        # For line-oriented matches, insert before the indentation as well;
        # otherwise a later line can lose its original indentation.
        line_start = original.rfind("\n", 0, start) + 1
        prefix_on_line = original[line_start:start]
        is_line_start = not prefix_on_line.strip(" \t")

        if not is_line_start:
            return original[:start] + insertion + original[start:]

        start = line_start
        left = original[:start]
        right = original[start:]
        return cls._join_as_lines(left, insertion, right)

    @classmethod
    def _insert_after(cls, original: str, start: int, end: int, insertion: str) -> str:
        if not insertion:
            return original

        line_start = original.rfind("\n", 0, start) + 1
        prefix_on_line = original[line_start:start]
        is_line_start = not prefix_on_line.strip(" \t")

        if not is_line_start:
            return original[:end] + insertion + original[end:]

        # If MATCH omits the matched line's terminating newline, move past that
        # newline. Inserting before it creates joined lines or an extra blank.
        position = end
        if position < len(original) and original[position] == "\n":
            position += 1

        left = original[:position]
        right = original[position:]
        return cls._join_as_lines(left, insertion, right)

    @classmethod
    def _join_as_lines(cls, left: str, insertion: str, right: str) -> str:
        if not insertion:
            return left + right

        if left and not cls._is_line_ending(left) and not insertion.startswith(("\n", "\r")):
            insertion = "\n" + insertion

        if right:
            if not cls._is_line_ending(insertion) and not right.startswith(("\n", "\r")):
                insertion += "\n"
        elif not cls._is_line_ending(insertion):
            insertion += "\n"

        return left + insertion + right

    @staticmethod
    def _replace(original: str, start: int, end: int, replacement: str) -> str:
        prefix = original[:start]
        suffix = original[end:]

        # MATCH often excludes the line terminator while a fenced CONTENT
        # block conventionally includes one. Collapse only the duplicate
        # terminator at each splice boundary; preserve any additional blank line.
        if prefix.endswith("\n") and replacement.startswith("\n"):
            replacement = replacement[1:]
        if replacement.endswith("\n") and suffix.startswith("\n"):
            replacement = replacement[:-1]

        return prefix + replacement + suffix
