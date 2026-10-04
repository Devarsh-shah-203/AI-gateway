from files.edit_parser import EditParser
from files.edit_validator import EditValidator
from files.edit_engine import EditEngine
from files.diff_generator import DiffGenerator
from files.writer import FileWriter


class EditWorkflow:

    def __init__(
        self,
        workspace_manager,
        approval_function,
    ):
        self.parser = EditParser()
        self.validator = EditValidator(workspace_manager)
        self.engine = EditEngine()
        self.diff_generator = DiffGenerator()
        self.writer = FileWriter()
        self.approval_function = approval_function

    def run(self, response):
        edits = self.parser.parse(response)

        if not edits:
            raise ValueError(
                "The model returned no edits."
            )

        results = []

        for edit in edits:

            validated = self.validator.validate(edit)

            original_content = validated.path.read_text(
                encoding="utf-8"
            )

            proposed_content = self.engine.apply(
                validated,
                original_content,
            )

            diff = self.diff_generator.generate(
                original_content,
                proposed_content,
                edit.file,
            )

            if not diff:
                raise ValueError(
                    f"Edit produced no changes: {edit.file}"
                )

            approved = self.approval_function(
                edit.file,
                edit.reason,
                diff,
            )

            if not approved:
                results.append({
                    "file": edit.file,
                    "status": "REJECTED",
                })
                continue

            self.writer.write(
                validated.path,
                proposed_content,
            )

            results.append({
                "file": edit.file,
                "status": "APPLIED",
            })

        return results