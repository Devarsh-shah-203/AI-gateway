from pathlib import Path

from .config import WorkspaceConfig


class WorkspaceManager:
    """
    Manages user-configured workspace directories.

    The AI Gateway itself is NOT considered a workspace.

    All future file reads and modifications should go
    through this manager for path validation.
    """

    def __init__(self, gateway_dir=None):

        if gateway_dir is None:

            gateway_dir = (
                Path(__file__)
                .resolve()
                .parents[1]
            )

        self.gateway_dir = Path(
            gateway_dir
        ).resolve()

        self.config = WorkspaceConfig(
            self.gateway_dir
        )

        self._directories = []

        self.reload()

    # --------------------------------------------------
    # Configuration
    # --------------------------------------------------

    def reload(self):
        """
        Reload workspace directories from disk.
        """

        self._directories = (
            self.config.load()
        )

    def _save(self):
        """
        Save current workspace configuration.
        """

        self.config.save(
            self._directories
        )

    # --------------------------------------------------
    # Directory validation
    # --------------------------------------------------

    def _validate_directory(self, path):
        """
        Validate a directory before adding it.
        """

        path = Path(path).expanduser().resolve()

        if not path.exists():
            raise ValueError(
                f"Workspace directory does not exist: {path}"
            )

        if not path.is_dir():
            raise ValueError(
                f"Workspace path is not a directory: {path}"
            )

        # ------------------------------------------------
        # Protect AI Gateway itself
        # ------------------------------------------------

        try:
            path.relative_to(
                self.gateway_dir
            )

            raise ValueError(
                "AI Gateway directory cannot be "
                "configured as a workspace."
            )

        except ValueError as error:

            # This ValueError means the path is NOT
            # inside the gateway directory.
            if str(error).startswith(
                "AI Gateway directory"
            ):
                raise

        return path

    # --------------------------------------------------
    # Add
    # --------------------------------------------------

    def add_directory(self, path):

        path = self._validate_directory(
            path
        )

        path_string = str(path)

        # Prevent duplicates
        for entry in self._directories:

            existing = Path(
                entry["path"]
            ).resolve()

            if existing == path:
                return entry

        # Create next stable id
        used_ids = {
            entry["id"]
            for entry in self._directories
        }

        workspace_id = 1

        while workspace_id in used_ids:
            workspace_id += 1

        entry = {
            "id": workspace_id,
            "path": path_string,
        }

        self._directories.append(
            entry
        )

        self._save()

        return entry

    # --------------------------------------------------
    # Remove
    # --------------------------------------------------

    def remove_directory(self, workspace_id):

        for index, entry in enumerate(
            self._directories
        ):

            if entry["id"] == workspace_id:

                removed = self._directories.pop(
                    index
                )

                self._save()

                return removed

        raise ValueError(
            f"Workspace directory #{workspace_id} "
            "does not exist."
        )

    # --------------------------------------------------
    # List
    # --------------------------------------------------

    def list_directories(self):

        return [
            entry.copy()
            for entry in self._directories
        ]

    # --------------------------------------------------
    # Resolve numeric alias
    # --------------------------------------------------

    def resolve_path(self, reference):

        if not isinstance(reference, str):
            raise TypeError(
                "Workspace reference must be a string."
            )

        reference = reference.strip()

        if not reference:
            raise ValueError(
                "Workspace reference cannot be empty."
            )

        # Expected:
        #
        # 1/file.py
        # 2/backend/auth.js
        #

        parts = reference.split(
            "/",
            1
        )

        if len(parts) != 2:
            raise ValueError(
                "Workspace file reference must use "
                "the format: <number>/<path>"
            )

        id_text, relative_path = parts

        if not id_text.isdigit():
            raise ValueError(
                "Workspace id must be a number."
            )

        workspace_id = int(id_text)

        if not relative_path.strip():
            raise ValueError(
                "Workspace file path cannot be empty."
            )

        directory = None

        for entry in self._directories:

            if entry["id"] == workspace_id:
                directory = Path(
                    entry["path"]
                ).resolve()
                break

        if directory is None:
            raise ValueError(
                f"Workspace directory #{workspace_id} "
                "does not exist."
            )

        # Convert `/` syntax to the current OS path.
        relative = Path(
            relative_path
        )

        resolved = (
            directory / relative
        ).resolve()

        # ------------------------------------------------
        # Security check
        # ------------------------------------------------

        try:

            resolved.relative_to(
                directory
            )

        except ValueError:

            raise ValueError(
                "Path is outside the configured "
                "workspace directory."
            )

        return resolved

    def clear(self):
        """
        Remove all configured workspace directories.

        This only clears the gateway configuration.
        It does NOT delete the actual directories or files.
        """

        self._directories = []

        self._save()

    def get_status(self):
        """
        Return workspace directories with their current
        filesystem availability.

        The configured entries themselves are not modified.
        """

        statuses = []

        for entry in self._directories:

            path = Path(
                entry["path"]
            ).resolve()

            status = (
                "OK"
                if path.exists() and path.is_dir()
                else "MISSING"
            )

            statuses.append(
                {
                    "id": entry["id"],
                    "path": str(path),
                    "status": status,
                }
            )

        return statuses