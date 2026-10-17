"""Prepare a provider-neutral text representation of selected Jupyter notebook content.

This module never mutates a document. Context preparation uses a shared,
registerable adapter interface so structured formats can be supported without
separate edit workflows. The initial adapter handles Jupyter notebook JSON.
Notebook cell indices are zero-based. Encoded image/media payloads are deliberately
not sent through the current text-only browser transport; placeholders are used.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable


_IMAGE_MIME_PREFIX = "image/"
_NON_TEXT_MIME_PREFIXES = ("audio/", "video/")
_NON_TEXT_MIME_TYPES = {"application/pdf", "application/octet-stream"}
_EMBEDDED_IMAGE_DATA_URI = re.compile(
    r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=\r\n]+",
    re.IGNORECASE,
)


class StructuredContextBuilder:
    """Prepare context for structured documents through registered format adapters.

    The context-selection and formatting contract is shared. A format adapter is
    responsible only for understanding one document's structure; it does not
    implement a separate edit workflow. Additional formats can be registered
    without changing FileContextBuilder or provider transport.
    """

    def __init__(
        self,
        *,
        input_fn: Callable[[str], str] | None = None,
        output_fn: Callable[..., None] | None = None,
        preview_chars: int = 100,
    ) -> None:
        # Resolve builtins at call time so tests and callers can replace them.
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.preview_chars = max(20, int(preview_chars))
        self._handlers = {".ipynb": self._build_notebook_context}

    def register_handler(self, extension: str, handler: Callable[[Path, str], str]) -> None:
        """Register a context adapter for a file extension (for example, ``.ipynb``)."""
        if not isinstance(extension, str) or not extension.startswith("."):
            raise ValueError("Extension must start with a dot, such as '.ipynb'.")
        if not callable(handler):
            raise TypeError("Structured-context handler must be callable.")
        self._handlers[extension.lower()] = handler

    def supports(self, path: Path | str) -> bool:
        return Path(path).suffix.lower() in self._handlers

    def build(self, path: Path | str, reference: str) -> str:
        """Dispatch context preparation to the registered document-format adapter."""
        resolved_path = Path(path).resolve()
        handler = self._handlers.get(resolved_path.suffix.lower())
        if handler is None:
            raise ValueError(f"No structured-context adapter registered for {resolved_path.suffix!r}.")
        return handler(resolved_path, reference)

    def _build_notebook_context(self, path: Path, reference: str) -> str:
        """Parse notebook JSON and interactively select source cells and outputs."""
        path = Path(path).resolve()
        try:
            with path.open("r", encoding="utf-8") as notebook_file:
                notebook = json.load(notebook_file)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Notebook is not valid JSON: {path} (line {error.lineno}, column {error.colno})"
            ) from error
        except UnicodeDecodeError as error:
            raise ValueError(f"Notebook is not valid UTF-8 text: {path}") from error

        if not isinstance(notebook, dict):
            raise ValueError("Notebook JSON must contain a top-level object.")
        cells = notebook.get("cells")
        if not isinstance(cells, list):
            raise ValueError("Notebook JSON must contain a 'cells' list.")
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                raise ValueError(f"Notebook cell {index} must be a JSON object.")

        all_indices = set(range(len(cells)))
        self._show_notebook_summary(path, cells, notebook)

        included_cells = self._ask_indices(
            "Include cells [all / none / indices or ranges] (default: all): ",
            allowed=all_indices,
            default=all_indices,
            label="cell selection",
        )

        if not included_cells:
            output_cells: set[int] = set()
            self._write(
                "No cell source selected. The model will receive the cell index/type map "
                "so it can propose an insertion position, but no existing cell source."
            )
        else:
            output_cells = self._ask_indices(
                "Include outputs for [none / all / indices or ranges] (default: none): ",
                allowed=included_cells,
                default=set(),
                label="output selection",
            )

        return self._format_context(
            notebook=notebook,
            cells=cells,
            reference=reference,
            path=path,
            included_cells=included_cells,
            output_cells=output_cells,
        )

    def _show_notebook_summary(self, path: Path, cells: list, notebook: dict) -> None:
        metadata = notebook.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        kernelspec = metadata.get("kernelspec")
        kernelspec = kernelspec if isinstance(kernelspec, dict) else {}
        language_info = metadata.get("language_info")
        language_info = language_info if isinstance(language_info, dict) else {}

        self._write("\nNOTEBOOK CONTEXT SELECTION")
        self._write("-" * 56)
        self._write(f"File: {path.name}")
        self._write(f"Cells: {len(cells)} (indices are zero-based)")
        language = language_info.get("name") or kernelspec.get("language")
        kernel = kernelspec.get("display_name")
        if language:
            self._write(f"Language: {language}")
        if kernel:
            self._write(f"Kernel: {kernel}")

        self._write("\nCell index map:")
        for index, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "unknown")
            source = self._source_text(cell.get("source", ""))
            first_line = next((line.strip() for line in source.splitlines() if line.strip()), "")
            if len(first_line) > self.preview_chars:
                first_line = first_line[: self.preview_chars - 3] + "..."
            outputs = cell.get("outputs", [])
            output_count = len(outputs) if isinstance(outputs, list) else 0
            preview = f" — {first_line}" if first_line else ""
            output_summary = f" | outputs: {output_count}" if cell_type == "code" else ""
            self._write(f"  [{index}] {cell_type}{output_summary}{preview}")
        self._write("\nSource selection controls which cell source is sent. Output selection is separate.")
        self._write(
            "Image/media payloads are not embedded in the text prompt; selected outputs "
            "will describe them instead."
        )

    def _ask_indices(
        self,
        prompt: str,
        *,
        allowed: set[int],
        default: set[int],
        label: str,
    ) -> set[int]:
        while True:
            answer = self._input(prompt).strip().lower()
            if not answer:
                return set(default)
            if answer == "all":
                return set(allowed)
            if answer == "none":
                return set()
            try:
                selected = self.parse_indices(answer)
            except ValueError as error:
                self._write(f"Invalid {label}: {error}")
                continue
            invalid = selected - allowed
            if invalid:
                allowed_text = ", ".join(str(item) for item in sorted(allowed)) or "none"
                invalid_text = ", ".join(str(item) for item in sorted(invalid))
                self._write(
                    f"Invalid {label}: indices not allowed: {invalid_text}. "
                    f"Allowed indices: {allowed_text}."
                )
                continue
            return selected

    @staticmethod
    def parse_indices(expression: str) -> set[int]:
        """Parse inclusive, zero-based expressions such as ``0,2,5-7``."""
        expression = expression.strip()
        if not expression:
            raise ValueError("enter 'all', 'none', or comma-separated indices/ranges")

        selected: set[int] = set()
        for part in expression.split(","):
            part = part.strip()
            if not part:
                raise ValueError("empty item in index list")
            if re.fullmatch(r"\d+", part):
                selected.add(int(part))
                continue
            match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
            if not match:
                raise ValueError(f"'{part}' is not an index or range")
            start, end = map(int, match.groups())
            if start > end:
                raise ValueError(f"range '{part}' starts after it ends")
            selected.update(range(start, end + 1))
        return selected

    def _format_context(
        self,
        *,
        notebook: dict,
        cells: list,
        reference: str,
        path: Path,
        included_cells: set[int],
        output_cells: set[int],
    ) -> str:
        lines = [
            "JUPYTER NOTEBOOK CONTEXT",
            "========================",
            f"FILE: {reference}",
            f"PATH: {path}",
            f"TOTAL CELLS: {len(cells)}",
            "CELL INDICES: zero-based indices into the current notebook cells array",
            "SOURCE CELLS INCLUDED: " + self._format_index_set(included_cells),
            "OUTPUT CELLS INCLUDED: " + self._format_index_set(output_cells),
            "IMAGE/MEDIA POLICY: encoded media payloads are not sent in this text context; placeholders are used.",
            "",
            "CELL INDEX MAP (indices and types are provided to support insertion positioning):",
        ]

        for index, cell in enumerate(cells):
            cell_type = str(cell.get("cell_type", "unknown"))
            lines.append(f"[{index}] type={cell_type}")

        metadata = notebook.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        kernelspec = metadata.get("kernelspec")
        kernelspec = kernelspec if isinstance(kernelspec, dict) else {}
        language_info = metadata.get("language_info")
        language_info = language_info if isinstance(language_info, dict) else {}
        language = language_info.get("name") or kernelspec.get("language")
        kernel = kernelspec.get("display_name")
        if language or kernel:
            lines.extend(["", "NOTEBOOK METADATA:"])
            if language:
                lines.append(f"language: {language}")
            if kernel:
                lines.append(f"kernel: {kernel}")

        for index, cell in enumerate(cells):
            if index not in included_cells:
                continue
            cell_type = str(cell.get("cell_type", "unknown"))
            lines.extend(["", f"CELL {index} — {cell_type}", "SOURCE:"])
            lines.append(self._source_text(cell.get("source", "")))
            cell_metadata = cell.get("metadata")
            if isinstance(cell_metadata, dict):
                tags = cell_metadata.get("tags")
                if isinstance(tags, list) and tags:
                    lines.append("TAGS: " + ", ".join(str(tag) for tag in tags))

            if index in output_cells:
                lines.append("OUTPUTS:")
                outputs = cell.get("outputs", [])
                if not isinstance(outputs, list) or not outputs:
                    lines.append("(No stored outputs.)")
                else:
                    for output_index, output in enumerate(outputs):
                        if not isinstance(output, dict):
                            lines.append(f"Output {output_index}: [invalid output object omitted]")
                            continue
                        lines.extend(self._format_output(output_index, output))
        return "\n".join(lines)

    def _format_output(self, output_index: int, output: dict) -> list[str]:
        output_type = str(output.get("output_type", "unknown"))
        lines = [f"Output {output_index} (type={output_type}):"]

        if output_type == "stream":
            name = output.get("name", "stdout")
            lines.append(f"stream={name}")
            lines.append(self._source_text(output.get("text", "")))
            return lines

        if output_type == "error":
            lines.append(f"ename: {output.get('ename', '')}")
            lines.append(f"evalue: {output.get('evalue', '')}")
            traceback = output.get("traceback", [])
            if isinstance(traceback, list):
                lines.extend(str(line) for line in traceback)
            elif traceback:
                lines.append(str(traceback))
            return lines

        data = output.get("data", {})
        if not isinstance(data, dict):
            lines.append("[output data omitted because it is not a MIME bundle]")
            return lines

        if not data:
            lines.append("[No display data]")
            return lines

        for mime_type, value in data.items():
            mime_type = str(mime_type)
            if mime_type.lower().startswith(_IMAGE_MIME_PREFIX):
                lines.append(
                    f"{mime_type}: [image payload omitted; encoded payload size: "
                    f"{self._payload_length(value)} characters]"
                )
                continue
            if mime_type.lower().startswith(_NON_TEXT_MIME_PREFIXES) or mime_type.lower() in _NON_TEXT_MIME_TYPES:
                lines.append(
                    f"{mime_type}: [media/binary payload omitted; encoded payload size: "
                    f"{self._payload_length(value)} characters]"
                )
                continue

            rendered = self._render_mime_value(value)
            if mime_type.lower() == "text/html":
                rendered = _EMBEDDED_IMAGE_DATA_URI.sub("[embedded image payload omitted]", rendered)
            lines.append(f"{mime_type}:")
            lines.append(rendered)
        return lines

    @staticmethod
    def _source_text(source) -> str:
        if isinstance(source, str):
            return source
        if isinstance(source, list) and all(isinstance(item, str) for item in source):
            return "".join(source)
        if source is None:
            return ""
        raise ValueError("Notebook cell source must be a string or a list of strings.")

    @staticmethod
    def _render_mime_value(value) -> str:
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return "".join(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        if value is None:
            return "null"
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return repr(value)

    @staticmethod
    def _payload_length(value) -> int:
        if isinstance(value, str):
            return len(value)
        if isinstance(value, list):
            return sum(len(item) for item in value if isinstance(item, str))
        return len(json.dumps(value, ensure_ascii=False))

    @staticmethod
    def _format_index_set(indices: set[int]) -> str:
        if not indices:
            return "none"
        return ", ".join(str(item) for item in sorted(indices))

    def _input(self, prompt: str) -> str:
        if self.input_fn is not None:
            return self.input_fn(prompt)
        return input(prompt)

    def _write(self, *values) -> None:
        if self.output_fn is not None:
            self.output_fn(*values)
        else:
            print(*values)
