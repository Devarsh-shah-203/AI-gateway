from pathlib import Path


class FileReader:
    """
    Reads user-selected workspace files.

    This class receives an already-resolved path.
    Workspace/path validation remains the responsibility
    of WorkspaceManager.
    """

    def read(self, path):
        """
        Read a text file as UTF-8.

        Returns:
            str
        """

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
            return path.read_text(
                encoding="utf-8"
            )

        except UnicodeDecodeError as error:
            raise ValueError(
                f"File is not valid UTF-8 text: {path}"
            ) from error

        except PermissionError as error:
            raise PermissionError(
                f"Permission denied: {path}"
            ) from error