from dataclasses import dataclass
from pathlib import Path
import json

from files.edit_parser import FileEdit, ALLOWED_OPERATIONS, NOTEBOOK_OPERATIONS
from files.structured_edit import StructuredEditAdapter
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
        structured_edit_adapter: StructuredEditAdapter | None = None,
    ):
        self.workspace_manager = workspace_manager
        self.file_reader = file_reader or FileReader()
        self.reference_detector = FileReferenceDetector()
        self.structured_edit_adapter = structured_edit_adapter or StructuredEditAdapter()

    def validate(self, edit: FileEdit) -> ValidatedEdit:
        if edit.operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"Unsupported edit operation: {edit.operation}")

        # Accept canonical references both with and without angle brackets.
        file_reference = edit.file.strip()
        if file_reference.startswith("<") and file_reference.endswith(">"):
            file_reference = file_reference[1:-1].strip()
        references = self.reference_detector.detect(f"<{file_reference}>")
        if len(references) != 1:
            raise ValueError(f"Invalid file reference: {edit.file}")

        reference = references[0]
        path = self.workspace_manager.resolve_path(
            f"{reference.workspace_id}/{reference.relative_path}"
        )
        is_structured_document = self.structured_edit_adapter.supports(path)

        if edit.operation in NOTEBOOK_OPERATIONS:
            if not is_structured_document:
                raise ValueError(
                    f"Operation '{edit.operation}' is supported only for a structured document with a registered adapter, not {path.suffix or 'files without an extension'}."
                )
            raw_content = self.file_reader.read(path)
            try:
                notebook = json.loads(raw_content)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Notebook is not valid JSON (line {error.lineno}, column {error.colno})."
                ) from error
            if not isinstance(notebook, dict):
                raise ValueError("Notebook JSON must contain a top-level object.")
            self.structured_edit_adapter.validate_edit(path, edit, notebook)
            return ValidatedEdit(edit=edit, path=path, match_start=0, match_end=0)

        if is_structured_document:
            raise ValueError(
                f"{path.suffix} must be edited with a format-aware structured operation; raw text edits of structured document JSON are disabled."
            )

        content = self.file_reader.read(path)
        if edit.operation in {"insert_start", "insert_end"}:
            return self._validate_position_operation(edit, path, content)

        matches = self._find_matches(content, edit.match)
        if len(matches) == 0:
            raise ValueError(f"No match found in {edit.file}.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous match in {edit.file}: {len(matches)} matches found."
            )

        start, end = matches[0]
        return ValidatedEdit(edit=edit, path=path, match_start=start, match_end=end)

    @staticmethod
    def _find_matches(content: str, match: str) -> list[tuple[int, int]]:
        if not match:
            raise ValueError("Match cannot be empty.")
        matches = []
        start = 0
        while True:
            index = content.find(match, start)
            if index == -1:
                break
            matches.append((index, index + len(match)))
            start = index + len(match)
        return matches

    @staticmethod
    def _validate_position_operation(edit: FileEdit, path: Path, content: str) -> ValidatedEdit:
        return ValidatedEdit(edit=edit, path=path, match_start=0, match_end=0)
