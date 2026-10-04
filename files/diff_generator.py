import difflib


class DiffGenerator:

    def generate(
        self,
        original_content: str,
        proposed_content: str,
        file_name: str,
    ) -> str:

        original_lines = original_content.splitlines(
            keepends=True
        )

        proposed_lines = proposed_content.splitlines(
            keepends=True
        )

        diff = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
        )

        return "".join(diff)