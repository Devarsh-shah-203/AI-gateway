"""Provider-neutral structured-document edit dispatch and Jupyter handler.

The shared edit workflow calls this generic registry; format-specific behavior
is contained in the registered handler. The Jupyter handler changes only cell
source or inserts cells, preserving unrelated notebook data.
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Iterable

from files.edit_parser import FileEdit, NOTEBOOK_OPERATIONS


class _JupyterNotebookHandler:
    """Format-specific handler registered behind the generic structured adapter."""

    def validate_edit(self, edit: FileEdit, notebook: dict) -> None:
        if edit.operation not in NOTEBOOK_OPERATIONS:
            raise ValueError(f"Unsupported notebook operation: {edit.operation}")
        cells = notebook.get("cells")
        if not isinstance(cells, list):
            raise ValueError("Notebook JSON must contain a 'cells' list.")
        if any(not isinstance(cell, dict) for cell in cells):
            raise ValueError("Every notebook cell must be a JSON object.")

        if edit.operation == "edit_cell":
            if edit.cell_index is None:
                raise ValueError("edit_cell requires cell_index.")
            if edit.cell_index < 0 or edit.cell_index >= len(cells):
                raise ValueError(
                    f"Cell index {edit.cell_index} is outside the notebook's current range 0-{len(cells) - 1}."
                )
            cell = cells[edit.cell_index]
            cell_type = cell.get("cell_type")
            if cell_type not in {"code", "markdown"}:
                raise ValueError(
                    f"Cell {edit.cell_index} has unsupported cell_type {cell_type!r}; only code and markdown cells can be edited."
                )
            current_source = self._source_text(cell.get("source", ""))
            if not self._same_guard(current_source, edit.match):
                raise ValueError(
                    f"Cell {edit.cell_index} MATCH does not match its current source; refusing a potentially stale edit."
                )
            if edit.cell_type is not None or edit.position is not None:
                raise ValueError("edit_cell must not specify cell_type or position.")
            return

        if edit.operation == "insert_cell":
            if edit.match:
                raise ValueError("insert_cell requires an empty MATCH block.")
            if edit.cell_type not in {"code", "markdown"}:
                raise ValueError("insert_cell requires cell_type 'code' or 'markdown'.")
            if edit.position not in {"before", "after", "start", "end"}:
                raise ValueError("insert_cell requires position 'before', 'after', 'start', or 'end'.")
            if edit.position in {"before", "after"}:
                if edit.cell_index is None:
                    raise ValueError(f"position '{edit.position}' requires cell_index.")
                if edit.cell_index < 0 or edit.cell_index >= len(cells):
                    raise ValueError(
                        f"Insertion target cell index {edit.cell_index} is outside the notebook's current range 0-{len(cells) - 1}."
                    )
            elif edit.cell_index is not None:
                raise ValueError(f"position '{edit.position}' must not specify cell_index.")
            return

    def apply_batch(self, original_content: str, edits: Iterable[FileEdit]) -> str:
        """Apply notebook edits atomically against the original cell index map."""
        notebook = self._load(original_content)
        edits = list(edits)
        if not edits:
            raise ValueError("No notebook edits were supplied.")

        # Validate every operation against the same original document before
        # changing a cell or constructing insertions. This prevents earlier
        # insertions from shifting the targets of later operations.
        for edit in edits:
            self.validate_edit(edit, notebook)

        source_edits: dict[int, FileEdit] = {}
        insertions: dict[tuple[str, int | None], list[FileEdit]] = {}
        for edit in edits:
            if edit.operation == "edit_cell":
                if edit.cell_index in source_edits:
                    raise ValueError(
                        f"Multiple edit_cell operations target original cell {edit.cell_index}; combine them into one edit."
                    )
                source_edits[edit.cell_index] = edit
            else:
                key = (edit.position, edit.cell_index)
                insertions.setdefault(key, []).append(edit)

        # Rebuild from the original array. All cell_index values continue to
        # refer to the original notebook, not the incrementally shifted list.
        original_cells = notebook["cells"]
        result_cells: list[dict] = []
        for edit in insertions.get(("start", None), []):
            result_cells.append(self._new_cell(edit, notebook))

        for original_index, original_cell in enumerate(original_cells):
            for edit in insertions.get(("before", original_index), []):
                result_cells.append(self._new_cell(edit, notebook))

            cell = deepcopy(original_cell)
            source_edit = source_edits.get(original_index)
            if source_edit is not None:
                old_source = original_cell.get("source", "")
                cell["source"] = self._encode_source(source_edit.content, old_source)
            result_cells.append(cell)

            for edit in insertions.get(("after", original_index), []):
                result_cells.append(self._new_cell(edit, notebook))

        for edit in insertions.get(("end", None), []):
            result_cells.append(self._new_cell(edit, notebook))

        updated_notebook = deepcopy(notebook)
        updated_notebook["cells"] = result_cells
        return self._dump(updated_notebook, original_content)

    @staticmethod
    def _load(raw: str) -> dict:
        try:
            notebook = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Notebook is not valid JSON (line {error.lineno}, column {error.colno})."
            ) from error
        if not isinstance(notebook, dict):
            raise ValueError("Notebook JSON must contain a top-level object.")
        if not isinstance(notebook.get("cells"), list):
            raise ValueError("Notebook JSON must contain a 'cells' list.")
        return notebook

    @staticmethod
    def _source_text(value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(part, str) for part in value):
            return "".join(value)
        raise ValueError("Notebook cell source must be a string or a list of strings.")

    @classmethod
    def _same_guard(cls, current: str, supplied: str) -> bool:
        current = current.replace("\r\n", "\n").replace("\r", "\n")
        supplied = supplied.replace("\r\n", "\n").replace("\r", "\n")
        # The parser removes the separator newline around MATCH. Accept exactly
        # one omitted terminal newline, but do not normalize indentation or any
        # internal whitespace.
        return (
            current == supplied
            or current.removesuffix("\n") == supplied
            or current == supplied.removesuffix("\n")
        )

    @staticmethod
    def _encode_source(source: str, prior_source):
        if isinstance(prior_source, list):
            return source.splitlines(keepends=True)
        return source

    @staticmethod
    def _new_cell(edit: FileEdit, notebook: dict) -> dict:
        source = edit.content.splitlines(keepends=True)
        # Avoid treating a final newline as a separate empty source entry.
        # splitlines(keepends=True) already has that behavior.
        cell = {
            "cell_type": edit.cell_type,
            "metadata": {},
            "source": source,
        }
        if edit.cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []

        minor = notebook.get("nbformat_minor", 0)
        has_cell_ids = any(
            isinstance(existing, dict) and "id" in existing
            for existing in notebook.get("cells", [])
        )
        if (isinstance(minor, int) and minor >= 5) or has_cell_ids:
            existing_ids = {
                existing.get("id")
                for existing in notebook.get("cells", [])
                if isinstance(existing, dict) and isinstance(existing.get("id"), str)
            }
            new_id = uuid.uuid4().hex[:8]
            while new_id in existing_ids:
                new_id = uuid.uuid4().hex[:8]
            cell["id"] = new_id
        return cell

    @staticmethod
    def _dump(notebook: dict, original_content: str) -> str:
        # Keep the notebook's indentation, line-ending convention, Unicode, and
        # trailing-newline convention to minimize unrelated textual changes.
        indent_match = re.search(r'(?m)^([ \t]+)"cells"\s*:', original_content)
        indent = len(indent_match.group(1)) if indent_match else 1
        newline = "\r\n" if "\r\n" in original_content else "\n"
        trailing_newline = original_content.endswith(("\n", "\r"))
        serialized = json.dumps(notebook, ensure_ascii=False, indent=indent)
        if newline != "\n":
            serialized = serialized.replace("\n", newline)
        if trailing_newline:
            serialized += newline
        return serialized


class StructuredEditAdapter:
    """Provider-neutral registry/dispatcher for structured document edit handlers.

    The shared validator and workflow depend on this generic interface, not on
    notebook-specific details. A new structured format can register a handler
    implementing ``validate_edit`` and ``apply_batch`` for its own representation.
    """

    def __init__(self):
        self._handlers = {".ipynb": _JupyterNotebookHandler()}

    def register_handler(self, extension: str, handler) -> None:
        if not isinstance(extension, str) or not extension.startswith("."):
            raise ValueError("Extension must start with a dot, such as '.ipynb'.")
        has_validator = callable(getattr(handler, "validate_edit", None))
        has_batch_applier = callable(getattr(handler, "apply_batch", None))
        if not has_validator or not has_batch_applier:
            raise TypeError("Structured edit handler must implement validate_edit and apply_batch.")
        self._handlers[extension.lower()] = handler

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self._handlers

    def validate_edit(self, path: str | Path, edit: FileEdit, document: dict) -> None:
        handler = self._get_handler(path)
        handler.validate_edit(edit, document)

    def apply_batch(
        self, path: str | Path, original_content: str, edits: Iterable[FileEdit]
    ) -> str:
        handler = self._get_handler(path)
        return handler.apply_batch(original_content, edits)

    def _get_handler(self, path: str | Path):
        extension = Path(path).suffix.lower()
        handler = self._handlers.get(extension)
        if handler is None:
            raise ValueError(f"No structured edit adapter is registered for {extension!r}.")
        return handler
