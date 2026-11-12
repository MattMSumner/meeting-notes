#!/usr/bin/env python3
"""Builds the Start and Stop meeting notes shortcuts and opens them for import.

Run them from Spotlight by typing their names (or give them Quick Keys in Spotlight's
settings). Each is a single "Run Shell Script" step that calls `notes`.

Usage: uv run scripts/install-shortcuts.py
Shortcuts asks to confirm each import. Running shell scripts needs Shortcuts → Settings →
Advanced → Allow Running Scripts.

Re-running replaces the shortcuts only if you delete the old ones first; otherwise
Shortcuts adds copies named "... 2".

Run from your configured terminal: supported MEETING_NOTES_* settings and PATH are
captured at installation. Reinstall after changing them; interactive shell files are
never sourced when running a shortcut."""

import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOTES = REPO / ".venv" / "bin" / "notes"

SHORTCUTS = {
    "Start meeting notes": "start --ask-title",
    "Stop meeting notes": "stop",
}


SETTINGS = (
    "MEETING_NOTES_DATA_DIR",
    "MEETING_NOTES_NOTES_DIR",
    "MEETING_NOTES_MODEL",
    "MEETING_NOTES_CAPTURE",
    "MEETING_NOTES_OLLAMA_URL",
    "MEETING_NOTES_SUMMARY_MODEL",
    "MEETING_NOTES_NUM_CTX",
    "MEETING_NOTES_MY_NAME",
    "MEETING_NOTES_SUMMARY_THINK",
    "MEETING_NOTES_MAX_RECORDING_SECONDS",
)


def workflow(notes_args: str, environment: Mapping[str, str] | None = None) -> dict[str, object]:
    environment = os.environ if environment is None else environment
    # Shortcuts has no terminal. Capture only application settings, not shell startup
    # code or unrelated credentials. Reinstall after changing these settings.
    path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    if environment.get("PATH"):
        path = environment["PATH"] + ":" + path
    arguments = ["/usr/bin/env", "PATH=" + path]
    arguments += [f"{name}={environment[name]}" for name in SETTINGS if name in environment]
    arguments += [str(NOTES), *shlex.split(notes_args)]
    script = "exec " + shlex.join(arguments)
    return {
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.runshellscript",
                "WFWorkflowActionParameters": {
                    "Script": script,
                    "Shell": "/bin/sh",
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
