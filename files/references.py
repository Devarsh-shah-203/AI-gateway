import re
from dataclasses import dataclass


FILE_REFERENCE_PATTERN = re.compile(
    r"<([^<>]+)>"
)


@dataclass(frozen=True)
class FileReference:
    """
    Represents a user-specified workspace file reference.
    """

    workspace_id: int
    relative_path: str


class FileReferenceDetector:
    """
    Detects file references written as:

        <1/file.py>
        <2/backend/auth.js>
        <3/model.ipynb>

    This class only detects and parses references.

    It does NOT:
    - access the filesystem
    - resolve absolute paths
    - validate workspace IDs
    """

    def detect(self, prompt):
        """
        Find all file references in a user prompt.

        Returns:
            list[FileReference]
        """

        if not isinstance(prompt, str):
            raise TypeError(
                "Prompt must be a string."
            )

        references = []

        for match in FILE_REFERENCE_PATTERN.finditer(
            prompt
        ):
            raw_reference = match.group(1).strip()

            reference = self._parse_reference(
                raw_reference
            )

            references.append(reference)

        return references

    @staticmethod
    def _parse_reference(raw_reference):
        """
        Parse:

            <workspace_id/relative_path>
        """

        if "/" not in raw_reference:
            raise ValueError(
                "Invalid file reference. "
                "Expected <workspace_id/path>."
            )

        workspace_id_text, relative_path = (
            raw_reference.split("/", 1)
        )

        workspace_id_text = (
            workspace_id_text.strip()
        )

        relative_path = (
            relative_path.strip()
        )

        if not workspace_id_text.isdigit():
            raise ValueError(
                "Workspace ID in file reference "
                "must be a number."
            )

        if not relative_path:
            raise ValueError(
                "File path in file reference "
                "cannot be empty."
            )

        # We intentionally keep path validation
        # inside WorkspaceManager.
        #
        # This detector only checks the syntax.

        return FileReference(
            workspace_id=int(
                workspace_id_text
            ),
            relative_path=relative_path,
        )