class MemoryContextSession:
    """
    Controls when project memory is included in prompts.

    Modes:

        OFF
            Memory is not included.

        ON
            Memory is included when a new snapshot is needed.
            After the snapshot is sent, it is not resent for
            every subsequent prompt.

        NEXT
            Memory is included once, then returns to OFF.

    Refresh:
        Forces the current memory snapshot to be included
        in the next prompt while preserving the current mode.
    """

    OFF = "OFF"
    ON = "ON"
    NEXT = "NEXT"

    def __init__(self):
        self.mode = self.OFF

        # Has the current memory snapshot already been
        # supplied to the current ChatGPT conversation?
        self.snapshot_loaded = False

        # Has the user explicitly requested a refresh?
        self.refresh_pending = False

    # ========================================================
    # COMMANDS
    # ========================================================

    def use_once(self):
        """
        Include memory in the next prompt only.
        """

        self.mode = self.NEXT
        self.snapshot_loaded = False
        self.refresh_pending = False

    def enable(self):
        """
        Enable project-memory mode.

        The current snapshot will be included in the
        next prompt.
        """

        self.mode = self.ON
        self.snapshot_loaded = False
        self.refresh_pending = False

    def disable(self):
        """
        Stop future memory injection.
        """

        self.mode = self.OFF
        self.refresh_pending = False

    def refresh(self):
        """
        Force the current memory snapshot to be included
        in the next prompt.

        The current ON/OFF mode is preserved.
        """

        self.refresh_pending = True

    # ========================================================
    # DECISION
    # ========================================================

    def should_include_memory(self):
        """
        Determine whether the next user prompt should
        include project memory.
        """

        # Explicit refresh always wins.
        if self.refresh_pending:
            return True

        # One-time use.
        if self.mode == self.NEXT:
            return True

        # ON but current snapshot hasn't been loaded yet.
        if (
            self.mode == self.ON
            and not self.snapshot_loaded
        ):
            return True

        return False

    # ========================================================
    # AFTER SUCCESSFUL SEND
    # ========================================================

    def mark_memory_sent(self):
        """
        Call this after a prompt containing memory has
        actually been sent to ChatGPT.
        """

        self.snapshot_loaded = True
        self.refresh_pending = False

        # NEXT automatically becomes OFF after use.
        if self.mode == self.NEXT:
            self.mode = self.OFF

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self):
        """
        Return a human-readable status.
        """

        if self.mode == self.OFF:
            mode = "OFF"

        elif self.mode == self.ON:
            mode = "ON"

        else:
            mode = "NEXT"

        if self.refresh_pending:
            snapshot = "REFRESH PENDING"

        elif self.snapshot_loaded:
            snapshot = "LOADED"

        else:
            snapshot = "NOT LOADED"

        return {
            "mode": mode,
            "snapshot": snapshot,
        }