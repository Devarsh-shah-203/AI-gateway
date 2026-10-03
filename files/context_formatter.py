class FileContextFormatter:

    def format(self, file_context):
        if not file_context:
            return ""

        sections = ["PROJECT FILES", "============="]

        for file in file_context:
            sections.append("")
            sections.append(file["reference"])
            sections.append("-" * len(file["reference"]))
            sections.append(file["content"])

        return "\n".join(sections)