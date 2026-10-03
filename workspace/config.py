import json
from pathlib import Path


class WorkspaceConfig:
    """
    Handles persistent workspace configuration.

    Workspace configuration is stored locally and contains
    the directories that AI Gateway is allowed to access.
    """

    CONFIG_DIR_NAME = ".ai-gateway"
    CONFIG_FILE_NAME = "workspace.json"

    def __init__(self, gateway_dir):
        self.gateway_dir = Path(gateway_dir).resolve()

        self.config_dir = (
            self.gateway_dir / self.CONFIG_DIR_NAME
        )

        self.config_file = (
            self.config_dir / self.CONFIG_FILE_NAME
        )

    def ensure_config(self):
        """
        Create the configuration directory and file
        if they do not already exist.
        """

        self.config_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.config_file.exists():
            self.save([])

    def load(self):
        """
        Load configured workspace directories.

        Returns:
            list[str]
        """

        self.ensure_config()

        try:
            with self.config_file.open(
                "r",
                encoding="utf-8"
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Workspace configuration contains invalid JSON."
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Workspace configuration must be a JSON object."
            )

        directories = data.get("directories")

        if not isinstance(directories, list):
            raise ValueError(
                "'directories' must be a list."
            )

        validated = []

        for entry in directories:

            if not isinstance(entry, dict):
                raise ValueError(
                    "Each workspace entry must be an object."
                )

            workspace_id = entry.get("id")
            path = entry.get("path")

            if not isinstance(workspace_id, int):
                raise ValueError(
                    "Workspace id must be an integer."
                )

            if not isinstance(path, str) or not path.strip():
                raise ValueError(
                    "Workspace path must be a non-empty string."
                )

            validated.append(
                {
                    "id": workspace_id,
                    "path": path,
                }
            )

        return validated

    def save(self, directories):
        """
        Persist workspace directories.
        """

        if not isinstance(directories, list):
            raise TypeError(
                "directories must be a list."
            )

        self.config_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        data = {
            "directories": directories
        }

        with self.config_file.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )