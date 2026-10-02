from memory.manager import MemoryManager


class ContextBuilder:
    """
    Builds the final prompt that will be sent to the model.

    Responsibilities:
    - Start with the user's prompt
    - Optionally include project memory
    - Keep memory inclusion explicit

    This class does NOT:
    - communicate with ChatGPT
    - modify memory
    - decide what should be remembered
    """

    def __init__(self, project_dir=None):
        self.memory = MemoryManager(
            project_dir=project_dir
        )

    def build(self, prompt, include_memory=False):
        """
        Build the final prompt.

        Args:
            prompt: User's request.
            include_memory: Whether project memory
                            should be included.

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

        # ----------------------------------------------------
        # No memory
        # ----------------------------------------------------

        if not include_memory:
            return prompt

        # ----------------------------------------------------
        # Read memory
        # ----------------------------------------------------

        memory = self.memory.read_all()

        sections = []

        for name, content in memory.items():

            if not content.strip():
                continue

            title = name.replace(
                "_", " "
            ).upper()

            sections.append(
                f"## {title}\n\n{content.strip()}"
            )

        # ----------------------------------------------------
        # No memory exists
        # ----------------------------------------------------

        if not sections:
            return prompt

        # ----------------------------------------------------
        # Build final prompt
        # ----------------------------------------------------

        memory_text = "\n\n".join(sections)

        return (
            "PROJECT MEMORY\n"
            "===============\n\n"
            f"{memory_text}\n\n"
            "USER REQUEST\n"
            "============\n\n"
            f"{prompt}"
        )