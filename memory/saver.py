from .manager import MemoryManager
from .parser import MemoryParser


class MemorySaver:
    """
    Converts an LLM memory proposal into safe
    updates to the local .ai memory files.
    """

    def __init__(self, project_dir=None):
        self.manager = MemoryManager(
            project_dir=project_dir
        )

        self.parser = MemoryParser()

    @staticmethod
    def _normalize_text(text):
        """
        Normalize text for duplicate comparison.

        Differences in:
        - capitalization
        - extra spaces
        - newlines

        are ignored.
        """
        return " ".join(text.lower().split())

    def _is_duplicate(self, file_name, content):
        """
        Check whether the proposed memory content
        already exists in the corresponding memory file.
        """

        existing_content = self.manager.read(file_name)

        if not existing_content:
            return False

        normalized_existing = self._normalize_text(existing_content)
        normalized_new = self._normalize_text(content)

        return normalized_new in normalized_existing

    def save_from_response(self, response):
        """
        Parse a model response and apply all
        validated memory updates.

        Duplicate updates are skipped.

        Returns:
            list of saved file paths
        """

        updates = self.parser.parse(response)

        saved_files = []

        for update in updates:

            file_name = update["file"]
            content = update["content"]

            # Skip content that already exists.
            if self._is_duplicate(file_name, content):
                continue

            path = self.manager.append(
                file_name,
                content
            )

            saved_files.append(path)

        return saved_files