from memory.manager import MemoryManager


class ContextBuilder:
    """
    Builds the final prompt that will be sent to the model.

    Responsibilities:
    - Start with the user's prompt
    - Optionally include project memory
    - Optionally include project file context
    - Keep memory and file inclusion explicit

    This class does NOT:
    - communicate with the model
    - modify memory
    - decide what should be remembered
    - read files
    """

    def __init__(self, project_dir=None):
        self.memory = MemoryManager(
            project_dir=project_dir
        )

    def build(
        self,
        prompt,
        include_memory=False,
        file_context=None
    ):
        """
        Build the final prompt.

        Args:
            prompt: User's request.
            include_memory: Whether project memory
                            should be included.
            file_context: Optional list of project files
                          prepared by FileContextBuilder.

        Returns:
            str
        """

        if not isinstance(prompt, str):
            raise TypeError(
                "Prompt must be a string."
            )

        prompt = prompt.strip()

        if not prompt:
            raise ValueError(
                "Prompt cannot be empty."
            )

        if file_context is None:
            file_context = []

        sections = []

        # ----------------------------------------------------
        # Read memory
        # ----------------------------------------------------

        if include_memory:

            memory = self.memory.read_all()

            memory_sections = []

            for name, content in memory.items():

                if not content.strip():
                    continue

                title = name.replace(
                    "_", " "
                ).upper()

                memory_sections.append(
                    f"## {title}\n\n{content.strip()}"
                )

            if memory_sections:

                memory_text = "\n\n".join(
                    memory_sections
                )

                sections.append(
                    "PROJECT MEMORY\n"
                    "===============\n\n"
                    f"{memory_text}"
                )

        # ----------------------------------------------------
        # Project files
        # ----------------------------------------------------

        if file_context:

            file_sections = [
                "PROJECT FILES",
                "============="
            ]

            for file in file_context:

                file_sections.append("")
                file_sections.append(
                    file["reference"]
                )
                file_sections.append(
                    "-" * len(file["reference"])
                )
                file_sections.append(
                    file["content"]
                )

            sections.append(
                "\n".join(file_sections)
            )

        # ----------------------------------------------------
        # User request
        # ----------------------------------------------------

        sections.append(
            "USER REQUEST\n"
            "============\n\n"
            f"{prompt}"
        )

        return "\n\n".join(sections)