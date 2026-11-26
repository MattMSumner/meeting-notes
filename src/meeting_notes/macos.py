"""Notifications and dialogs, for when notes runs from a shortcut with no terminal."""

import subprocess
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode

APP_TITLE = "Meeting notes"
# AppleScript's "User canceled." error.
USER_CANCELED = "(-128)"


class DesktopError(Exception):
    pass


class Desktop(Protocol):
    def choose_meeting(self, choices: list[tuple[str, str]]) -> str | None:
        """Select one (stable ID, display label) pair, or cancel."""
        ...

    def open_note(self, path: Path) -> None: ...

    def notify(self, message: str) -> None: ...

    def ask_text(self, prompt: str, default: str = "") -> str | None:
        """Asks for a line of text. None if cancelled; DesktopError if it can't ask."""
        ...


def _applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MacDesktop:
    def choose_meeting(self, choices: list[tuple[str, str]]) -> str | None:
        if not choices:
            return None
        # Ordinals disambiguate duplicate labels, including titles containing suffixes.
        labels = [f"{i}. {label}" for i, (_, label) in enumerate(choices, 1)]
        items = ", ".join(_applescript_string(label) for label in labels)
        script = (
            f"set selected to choose from list {{{items}}} "
            f"with title {_applescript_string(APP_TITLE)} "
            'with prompt "Enhance which meeting?" '
            "multiple selections allowed false empty selection allowed false\n"
            'if selected is false then return ""\n'
            "return item 1 of selected"
        )
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        except OSError as error:
            raise DesktopError(str(error)) from error
        if result.returncode:
            if USER_CANCELED in result.stderr:
                return None
            raise DesktopError(result.stderr.strip())
        selected = result.stdout.rstrip("\n")
        if not selected:
            return None
        if selected not in labels:
            raise DesktopError("The selected meeting wasn't in the original list.")
        return choices[labels.index(selected)][0]

    def open_note(self, path: Path) -> None:
        query = urlencode({"path": str(path.resolve()), "paneType": "tab"}, quote_via=quote)
        try:
            result = subprocess.run(
                ["open", f"obsidian://open?{query}"], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DesktopError(str(error)) from error
        if result.returncode:
            raise DesktopError(result.stderr.strip() or f"open exited {result.returncode}")

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
