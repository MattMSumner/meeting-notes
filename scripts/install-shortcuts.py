#!/usr/bin/env python3
"""Builds the "Start meeting notes" and "Stop meeting notes" shortcuts and opens them for import.

Run them from Spotlight by typing their names (or give them Quick Keys in Spotlight's
settings). Each is a single "Run Shell Script" step that calls `notes`.

Usage: uv run scripts/install-shortcuts.py
Shortcuts asks to confirm each import. Running shell scripts needs Shortcuts → Settings →
Advanced → Allow Running Scripts.

Re-running replaces the shortcuts only if you delete the old ones first; otherwise
Shortcuts adds copies named "... 2"."""

import plistlib
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOTES = REPO / ".venv" / "bin" / "notes"

SHORTCUTS = {
    "Start meeting notes": "start --ask-title",
    "Stop meeting notes": "stop",
}


def workflow(notes_args: str) -> dict[str, object]:
    # Through an interactive zsh so the command sees what a terminal would: Homebrew's PATH
    # (ffmpeg) and settings like MEETING_NOTES_MY_NAME from ~/.zshrc. Shortcuts runs
    # scripts with a bare environment otherwise.
    command = f"{shlex.quote(str(NOTES))} {notes_args}"
    script = f"exec /bin/zsh -lic {shlex.quote(command)}"
    return {
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.runshellscript",
                "WFWorkflowActionParameters": {
                    "Script": script,
                    "Shell": "/bin/zsh",
                    "WFInputMode": "to stdin",
                },
            }
        ],
        "WFWorkflowClientVersion": "2700",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4282601983,
            "WFWorkflowIconGlyphNumber": 59511,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": [],
        "WFWorkflowHasShortcutInputVariables": False,
    }


def main() -> int:
    if not NOTES.is_file():
        print(f"{NOTES} not found. Run `uv sync` first.", file=sys.stderr)
        return 1
    out = Path(tempfile.mkdtemp(prefix="meeting-notes-shortcuts-"))
    for name, notes_args in SHORTCUTS.items():
        unsigned = out / f"{name}.wflow"
        signed = out / f"{name}.shortcut"
        unsigned.write_bytes(plistlib.dumps(workflow(notes_args), fmt=plistlib.FMT_BINARY))
        signing = subprocess.run(
            ["shortcuts", "sign", "--mode", "anyone", "--input", unsigned, "--output", signed],
            capture_output=True,
            text=True,
        )
        if signing.returncode != 0:
            print(f"Couldn't sign {name}: {signing.stderr.strip()}", file=sys.stderr)
            return 1
        subprocess.run(["open", signed], check=True)
        print(f"Opened {name}: confirm the import in Shortcuts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
