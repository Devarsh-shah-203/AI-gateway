from dataclasses import dataclass
from pathlib import Path

from files.edit_parser import FileEdit, ALLOWED_OPERATIONS
from files.references import FileReferenceDetector
from files.reader import FileReader
from workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class ValidatedEdit:
    edit: FileEdit
    path: Path
    match_start: int
    match_end: int


class EditValidator:

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        file_reader: FileReader | None = None,
    ):
        self.workspace_manager = workspace_manager
        self.file_reader = file_reader or FileReader()
        self.reference_detector = FileReferenceDetector()

    def validate(self, edit: FileEdit) -> ValidatedEdit:

        # 1. Validate operation
        if edit.operation not in ALLOWED_OPERATIONS:
            raise ValueError(
                f"Unsupported edit operation: {edit.operation}"
            )

        # 2. Validate file reference syntax
        references = self.reference_detector.detect(
            f"<{edit.file}>"
        )

        if len(references) != 1:
            raise ValueError(
                f"Invalid file reference: {edit.file}"
            )

        reference = references[0]

        # 3. Resolve through WorkspaceManager
        path = self.workspace_manager.resolve_path(
            f"{reference.workspace_id}/{reference.relative_path}"
        )

        # 4. Read actual file
        content = self.file_reader.read(path)

        # 5. Match resolution
        if edit.operation in {"insert_start", "insert_end"}:
            return self._validate_position_operation(
                edit,
                path,
                content,
            )

        matches = self._find_matches(
            content,
            edit.match,
        )

        # 6. No match
        if len(matches) == 0:
            raise ValueError(
                f"No match found in {edit.file}."
            )

        # 7. Multiple matches
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous match in {edit.file}: "
                f"{len(matches)} matches found."
            )

        # 8. Exactly one match
        start, end = matches[0]

        return ValidatedEdit(
            edit=edit,
            path=path,
            match_start=start,
            match_end=end,
        )

    @staticmethod
    def _find_matches(
        content: str,
        match: str,
    ) -> list[tuple[int, int]]:

        if not match:
            raise ValueError(
                "Match cannot be empty."
            )

        matches = []

        start = 0

        while True:
            index = content.find(match, start)

            if index == -1:
                break

            matches.append(
                (index, index + len(match))
            )

            start = index + len(match)

        return matches

    @staticmethod
    def _validate_position_operation(
        edit: FileEdit,
        path: Path,
        content: str,
    ) -> ValidatedEdit:

        return ValidatedEdit(
            edit=edit,
            path=path,
            match_start=0,
            match_end=0,
        )