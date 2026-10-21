"""Notifications and dialogs, for when notes runs from a shortcut with no terminal."""

import subprocess
from typing import Protocol

APP_TITLE = "Meeting notes"
# AppleScript's "User canceled." error.
USER_CANCELED = "(-128)"


class DesktopError(Exception):
    pass


class Desktop(Protocol):
    def notify(self, message: str) -> None: ...

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        """Asks for a line of text. None if cancelled; DesktopError if it can't ask."""
        ...


def _applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MacDesktop:
    def notify(self, message: str) -> None:
        script = (
            f"display notification {_applescript_string(message)} "
            f"with title {_applescript_string(APP_TITLE)}"
        )
        subprocess.run(["osascript", "-e", script], capture_output=True)

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        script = (
            f"text returned of (display dialog {_applescript_string(prompt)} "
            f"default answer {_applescript_string(default)} "
            f'with title {_applescript_string(APP_TITLE)} buttons {{"Cancel", "Start"}} '
            'default button "Start" cancel button "Cancel")'
        )
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            if USER_CANCELED in result.stderr:
                return None
            raise DesktopError(result.stderr.strip() or f"osascript exited {result.returncode}")
        return result.stdout.rstrip("\n")
