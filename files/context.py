from files.references import FileReferenceDetector
from files.reader import FileReader


class FileContextBuilder:
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager
        self.detector = FileReferenceDetector()
        self.reader = FileReader()

    def build(self, prompt):
        references = self.detector.detect(prompt)

        file_context = []

        for reference in references:
            raw_reference = f"{reference.workspace_id}/{reference.relative_path}"

            path = self.workspace_manager.resolve_path(raw_reference)
            content = self.reader.read(path)

            file_context.append({
                "reference": f"<{raw_reference}>",
                "path": str(path),
                "content": content,
            })

        return file_context