from collections import OrderedDict

from files.edit_parser import EditParser, NOTEBOOK_OPERATIONS
from files.edit_validator import EditValidator
from files.edit_engine import EditEngine
from files.diff_generator import DiffGenerator
from files.notebook_diff import NotebookDiffFormatter
from files.structured_edit import StructuredEditAdapter
from files.writer import FileWriter


class EditWorkflow:
    """Shared approval workflow for text files and structured notebook edits.

    Ordinary text-file operations keep their existing execution path. Notebook
    cell edits are grouped per notebook, validated against original cell indices,
    reviewed as one combined diff, and written once after approval.
    """

    def __init__(self, workspace_manager, approval_function):
        self.parser = EditParser()
        self.structured_edit_adapter = StructuredEditAdapter()
        self.validator = EditValidator(
            workspace_manager,
            structured_edit_adapter=self.structured_edit_adapter,
        )
        self.engine = EditEngine(self.structured_edit_adapter)
        self.diff_generator = DiffGenerator()
        self.notebook_diff_formatter = NotebookDiffFormatter()
        self.writer = FileWriter()
        self.approval_function = approval_function

    def run(self, response):
        edits = self.parser.parse(response)
        if not edits:
            raise ValueError("The model returned no edits.")

        # Prevalidate and stage notebook changes before the legacy text editing
        # loop writes anything. This ensures all operations for a notebook share
        # the same original cell map and invalid notebook edits cause no write.
        notebook_groups = OrderedDict()
        text_edits = []
        for edit in edits:
            if edit.operation in NOTEBOOK_OPERATIONS:
                validated = self.validator.validate(edit)
                key = validated.path.resolve()
                if key not in notebook_groups:
                    # Read bytes for notebooks: Path.read_text() performs
                    # universal-newline translation and would lose CRLF state.
                    original = validated.path.read_bytes().decode("utf-8")
                    notebook_groups[key] = {
                        "path": validated.path,
                        "original": original,
                        "edits": [],
                        "file_display": edit.file,
                    }
                notebook_groups[key]["edits"].append(edit)
            else:
                text_edits.append(edit)

        staged_notebooks = []
        for group in notebook_groups.values():
            proposed = self.engine.apply_structured_batch(
                group["path"], group["original"], group["edits"]
            )
            # Notebook review is rendered by a dedicated cell-level formatter.
            # The generic DiffGenerator and text-file path below are unchanged.
            diff = self.notebook_diff_formatter.generate(
                group["original"],
                proposed,
                group["file_display"],
                group["edits"],
            )
            if not diff:
                raise ValueError(
                    f"Notebook edit produced no changes: {group['file_display']}"
                )
            reasons = "\n".join(
                f"- {edit.reason}" for edit in group["edits"]
            )
            staged_notebooks.append({
                **group,
                "proposed": proposed,
                "diff": diff,
                "reason": reasons,
            })

        results = []
        # Preserve the established text-file path and approval behavior.
        for edit in text_edits:
            validated = self.validator.validate(edit)
            original_content = validated.path.read_text(encoding="utf-8")
            proposed_content = self.engine.apply(validated, original_content)
            diff = self.diff_generator.generate(original_content, proposed_content, edit.file)
            if not diff:
                raise ValueError(f"Edit produced no changes: {edit.file}")
            approved = self.approval_function(edit.file, edit.reason, diff)
            if not approved:
                results.append({"file": edit.file, "status": "REJECTED"})
                continue
            self.writer.write(validated.path, proposed_content)
            results.append({"file": edit.file, "status": "APPLIED"})

        for group in staged_notebooks:
            approved = self.approval_function(
                group["file_display"], group["reason"], group["diff"]
            )
            if not approved:
                results.append({"file": group["file_display"], "status": "REJECTED"})
                continue
            # Exact UTF-8 write avoids platform newline translation and checks
            # the original bytes have not changed since review.
            self.writer.write_exact_text(
                group["path"],
                group["proposed"],
                expected_content=group["original"],
            )
            results.append({"file": group["file_display"], "status": "APPLIED"})

        return results
