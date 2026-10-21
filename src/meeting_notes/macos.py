"""Notifications and dialogs, for when notes runs from a shortcut with no terminal."""

import subprocess
from typing import Protocol

APP_TITLE = "Meeting notes"


class Desktop(Protocol):
    def notify(self, message: str) -> None: ...

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        """Asks for a line of text. None if cancelled."""
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
            return None  # cancelled
        return result.stdout.rstrip("\n")
