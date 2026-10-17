from files.references import FileReferenceDetector
from files.reader import FileReader
from files.structured_context import StructuredContextBuilder


class FileContextBuilder:
    def __init__(self, workspace_manager, *, structured_context_builder=None):
        self.workspace_manager = workspace_manager
        self.detector = FileReferenceDetector()
        self.reader = FileReader()
        self.structured_context_builder = (
            structured_context_builder or StructuredContextBuilder()
        )

    def build(self, prompt):
        references = self.detector.detect(prompt)

        file_context = []

        for reference in references:
            raw_reference = f"{reference.workspace_id}/{reference.relative_path}"

            path = self.workspace_manager.resolve_path(raw_reference)
            if self.structured_context_builder.supports(path):
                content = self.structured_context_builder.build(
                    path,
                    reference=f"<{raw_reference}>",
                )
            else:
                content = self.reader.read(path)

            file_context.append({
                "reference": f"<{raw_reference}>",
                "path": str(path),
                "content": content,
            })

        return file_context
