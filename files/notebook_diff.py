"""Human-readable review formatter for Jupyter notebook cell edits.

This formatter intentionally works only on the notebook review path. Ordinary
text files continue to use ``DiffGenerator`` and retain the existing unified
text diff unchanged.
"""

from __future__ import annotations

import difflib
import json
from collections import defaultdict
from typing import Iterable

from files.edit_parser import FileEdit


class NotebookDiffFormatter:
    """Render a notebook edit proposal as a cell-level source diff."""

    def generate(
        self,
        original_content: str,
        proposed_content: str,
        file_name: str,
        edits: Iterable[FileEdit],
    ) -> str:
        original = self._load(original_content, "original")
        proposed = self._load(proposed_content, "proposed")
        original_cells = original["cells"]
        proposed_cells = proposed["cells"]
        edits = list(edits)

        source_edits = {}
        at_start = []
        at_end = []
        before = defaultdict(list)
        after = defaultdict(list)
        for edit in edits:
            if edit.operation == "edit_cell":
                source_edits[edit.cell_index] = edit
            elif edit.operation == "insert_cell":
                if edit.position == "start":
                    at_start.append(edit)
                elif edit.position == "end":
                    at_end.append(edit)
                elif edit.position == "before":
                    before[edit.cell_index].append(edit)
                elif edit.position == "after":
                    after[edit.cell_index].append(edit)
                else:
                    raise ValueError(
                        f"Unsupported notebook insertion position: {edit.position!r}"
                    )
            else:
                raise ValueError(
                    f"Unsupported operation in notebook review: {edit.operation!r}"
                )

        # Mirror the adapter's reconstruction order so each proposed cell can
        # be associated with its original cell or insertion operation exactly.
        layout = []
        for edit in at_start:
            layout.append(("insert", None, edit))
        for original_index in range(len(original_cells)):
            for edit in before[original_index]:
                layout.append(("insert", None, edit))
            layout.append(("existing", original_index, None))
            for edit in after[original_index]:
                layout.append(("insert", None, edit))
        for edit in at_end:
            layout.append(("insert", None, edit))

        if len(layout) != len(proposed_cells):
            raise ValueError(
                "Cannot format notebook review: proposed cell count does not match the staged edit plan."
            )

        sections = []
        for final_index, (kind, original_index, edit) in enumerate(layout):
            if kind == "existing":
                edit = source_edits.get(original_index)
                if edit is None:
                    continue
                old_cell = original_cells[original_index]
                new_cell = proposed_cells[final_index]
                old_source = self._source_text(old_cell.get("source", ""))
                new_source = self._source_text(new_cell.get("source", ""))
                if old_source == new_source:
                    continue
                cell_type = old_cell.get("cell_type", "unknown")
                heading = (
                    f"[MODIFY CELL] original index {original_index} ({cell_type}) "
                    f"-> proposed index {final_index}"
                )
                source_diff = list(difflib.unified_diff(
                    self._display_lines(old_source),
                    self._display_lines(new_source),
                    fromfile=f"original cell {original_index} source",
                    tofile=f"proposed cell {final_index} source",
                    n=3,
                ))
                if not source_diff:
                    continue
                sections.append(heading + "\n" + "".join(source_diff).rstrip("\n"))
                continue

            new_cell = proposed_cells[final_index]
            source = self._source_text(new_cell.get("source", ""))
            location = self._insertion_location(edit)
            cell_type = new_cell.get("cell_type", edit.cell_type or "unknown")
            heading = (
                f"[INSERT CELL] proposed index {final_index} ({cell_type}); {location}"
            )
            added_lines = list(difflib.unified_diff(
                [],
                self._display_lines(source),
                fromfile="/dev/null",
                tofile=f"proposed cell {final_index} source",
                n=3,
            ))
            if not source:
                body = "(empty source)"
            else:
                body = "".join(added_lines).rstrip("\n")
            sections.append(heading + "\n" + body)

        # An edit_cell that produces identical source is a true no-op even if
        # JSON serialization would otherwise make unrelated formatting differ.
        if not sections:
            return ""

        return (
            f"Notebook cell changes: {file_name}\n"
            "Cell indices in this review are zero-based.\n\n"
            + "\n\n".join(sections)
            + "\n"
        )

    @staticmethod
    def _load(content: str, label: str) -> dict:
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Cannot format {label} notebook review: invalid JSON at line {error.lineno}, column {error.colno}."
            ) from error
        if not isinstance(value, dict) or not isinstance(value.get("cells"), list):
            raise ValueError(
                f"Cannot format {label} notebook review: expected a JSON object with a cells list."
            )
        return value

    @staticmethod
    def _source_text(source) -> str:
        if isinstance(source, str):
            return source
        if isinstance(source, list) and all(isinstance(part, str) for part in source):
            return "".join(source)
        raise ValueError("Cannot format notebook review: a cell source is not text.")

    @staticmethod
    def _display_lines(source: str) -> list[str]:
        # difflib expects newline-terminated display lines for readable output.
        # This normalization is only for the review string; notebook content
        # itself is not changed by this formatter.
        return [line + "\n" for line in source.splitlines()]

    @staticmethod
    def _insertion_location(edit: FileEdit) -> str:
        if edit.position == "start":
            return "at notebook start"
        if edit.position == "end":
            return "at notebook end"
        if edit.position == "before":
            return f"before original index {edit.cell_index}"
        if edit.position == "after":
            return f"after original index {edit.cell_index}"
        return "at an unspecified position"
