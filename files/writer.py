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