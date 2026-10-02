from pathlib import Path
from datetime import datetime


class MemoryManager:
    """
    Manages local .ai project memory.

    Responsibilities:
    - Read memory
    - Read all memory
    - Safely append new memory

    This class:
    - Does NOT communicate with ChatGPT
    - Does NOT decide what should be remembered
    - Does NOT overwrite existing memory
    - Does NOT delete memory
    """

    MEMORY_FILES = {
        "plan": "plan.md",
        "progress": "progress.md",
        "discoveries": "discoveries.md",
        "closed_ideas": "closed-ideas.md",
        "cookbooks": "cookbooks.md",
    }

    def __init__(self, project_dir=None):

        if project_dir is None:
            project_dir = Path(__file__).parent.parent

        self.project_dir = Path(project_dir)
        self.memory_dir = self.project_dir / ".ai"

        # Make sure .ai exists
        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def _get_memory_path(self, name):
        """
        Return the path for an allowed memory file.

        Arbitrary paths are never accepted.
        """

        if name not in self.MEMORY_FILES:
            raise ValueError(
                f"Unknown memory file: {name}. "
                f"Allowed: {', '.join(self.MEMORY_FILES)}"
            )

        return self.memory_dir / self.MEMORY_FILES[name]

    # ========================================================
    # READ ONE
    # ========================================================

    def read(self, name):
        """
        Read one memory file.

        Example:
            memory.read("progress")
        """

        path = self._get_memory_path(name)

        if not path.exists():
            return ""

        return path.read_text(
            encoding="utf-8"
        )

    # ========================================================
    # READ ALL
    # ========================================================

    def read_all(self):
        """
        Read all memory files.

        Returns:
            dict[str, str]
        """

        memory = {}

        for name in self.MEMORY_FILES:
            memory[name] = self.read(name)

        return memory

    # ========================================================
    # APPEND MEMORY
    # ========================================================

    def append(self, name, content):
        """
        Safely append a new memory entry.

        Example:
            memory.append(
                "discoveries",
                "Found that X causes Y."
            )

        Existing content is never overwritten.
        """

        # Validate file name
        path = self._get_memory_path(name)

        # Validate content
        if not isinstance(content, str):
            raise TypeError(
                "Memory content must be a string."
            )

        content = content.strip()

        if not content:
            raise ValueError(
                "Memory content cannot be empty."
            )

        # Prevent accidental null bytes
        if "\x00" in content:
            raise ValueError(
                "Memory content contains an invalid null byte."
            )

        # Add timestamp
        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S %z"
        )

        entry = (
            f"\n\n## {timestamp}\n\n"
            f"{content}\n"
        )

        # APPEND ONLY
        with path.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(entry)

        return path