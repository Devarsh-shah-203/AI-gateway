from pathlib import Path


class FileWriter:

    def write(
        self,
        path: Path,
        content: str,
    ) -> None:

        if not isinstance(path, Path):
            path = Path(path)

        path = path.resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"File does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        try:
            path.write_text(
                content,
                encoding="utf-8",
            )
        except PermissionError as error:
            raise PermissionError(
                f"Permission denied: {path}"
            ) from error

    def write_exact_text(
        self,
        path: Path,
        content: str,
        *,
        expected_content: str | None = None,
    ) -> None:
        """Write UTF-8 bytes without newline translation.

        ``expected_content`` enables a compare-before-write guard for reviewed
        edits: if the on-disk bytes changed after the diff was approved, refuse
        to overwrite the newer contents. The existing ``write`` API is unchanged.
        """
        if not isinstance(path, Path):
            path = Path(path)
        path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        if expected_content is not None:
            expected_bytes = expected_content.encode("utf-8")
            try:
                current_bytes = path.read_bytes()
            except PermissionError as error:
                raise PermissionError(f"Permission denied: {path}") from error
            if current_bytes != expected_bytes:
                raise RuntimeError(
                    f"File changed after its diff was reviewed: {path}. Refusing to overwrite it."
                )

        try:
            path.write_bytes(content.encode("utf-8"))
        except PermissionError as error:
            raise PermissionError(f"Permission denied: {path}") from error

