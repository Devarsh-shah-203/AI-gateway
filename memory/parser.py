import json


MEMORY_START = "<AI_MEMORY>"
MEMORY_END = "</AI_MEMORY>"


class MemoryParser:
    """
    Parses structured memory proposals returned by an LLM.

    Expected format:

    <AI_MEMORY>
    {
        "updates": [
            {
                "file": "progress",
                "content": "Something important..."
            }
        ]
    }
    </AI_MEMORY>
    """

    ALLOWED_FILES = {
        "plan",
        "progress",
        "discoveries",
        "closed_ideas",
        "cookbooks",
    }

    def parse(self, response):
        """
        Extract and validate the AI_MEMORY block.

        Returns:
            list[dict]

        Returns [] only when no AI_MEMORY block exists
        or when updates is explicitly an empty list.
        """

        if not isinstance(response, str):
            raise TypeError(
                "Response must be a string."
            )

        start = response.find(MEMORY_START)
        end = response.find(MEMORY_END)

        # ----------------------------------------------------
        # No memory block
        # ----------------------------------------------------

        if start == -1 and end == -1:
            return []

        # One tag exists without the other
        if start == -1 or end == -1:
            raise ValueError(
                "Incomplete AI_MEMORY block."
            )

        # ----------------------------------------------------
        # Make sure the closing tag comes after opening tag
        # ----------------------------------------------------

        if end <= start:
            raise ValueError(
                "Invalid AI_MEMORY block."
            )

        # ----------------------------------------------------
        # Reject multiple memory blocks
        # ----------------------------------------------------

        second_start = response.find(
            MEMORY_START,
            start + len(MEMORY_START)
        )

        second_end = response.find(
            MEMORY_END,
            end + len(MEMORY_END)
        )

        if second_start != -1 or second_end != -1:
            raise ValueError(
                "Multiple AI_MEMORY blocks are not allowed."
            )

        # ----------------------------------------------------
        # Extract JSON
        # ----------------------------------------------------

        json_start = start + len(MEMORY_START)

        payload = response[
            json_start:end
        ].strip()

        if not payload:
            raise ValueError(
                "AI_MEMORY block is empty."
            )

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:
            data = json.loads(payload)

        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON inside AI_MEMORY: {error}"
            ) from error

        # ----------------------------------------------------
        # Validate root structure
        # ----------------------------------------------------

        if not isinstance(data, dict):
            raise ValueError(
                "AI_MEMORY must contain a JSON object."
            )

        # "updates" must exist
        if "updates" not in data:
            raise ValueError(
                "AI_MEMORY must contain an 'updates' field."
            )

        updates = data["updates"]

        # "updates" must be a list
        if not isinstance(updates, list):
            raise ValueError(
                "'updates' must be a list."
            )

        validated = []

        # ----------------------------------------------------
        # Validate every update
        # ----------------------------------------------------

        for update in updates:

            if not isinstance(update, dict):
                raise ValueError(
                    "Each memory update must be an object."
                )

            file_name = update.get("file")
            content = update.get("content")

            # ------------------------------------------------
            # File validation
            # ------------------------------------------------

            if file_name not in self.ALLOWED_FILES:
                raise ValueError(
                    f"Invalid memory file: {file_name}"
                )

            # ------------------------------------------------
            # Content validation
            # ------------------------------------------------

            if not isinstance(content, str):
                raise ValueError(
                    "Memory content must be a string."
                )

            content = content.strip()

            if not content:
                raise ValueError(
                    "Memory content cannot be empty."
                )

            validated.append(
                {
                    "file": file_name,
                    "content": content,
                }
            )

        return validated