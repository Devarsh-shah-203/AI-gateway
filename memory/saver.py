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

    def save_from_response(self, response):
        """
        Parse a model response and apply all
        validated memory updates.

        Returns:
            list of saved file paths
        """

        updates = self.parser.parse(response)

        saved_files = []

        for update in updates:

            path = self.manager.append(
                update["file"],
                update["content"]
            )

            saved_files.append(path)

        return saved_files