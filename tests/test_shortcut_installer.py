import importlib.util
import shlex
import subprocess
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install-shortcuts.py"


def installer() -> Any:
    spec = importlib.util.spec_from_file_location("shortcut_installer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shortcut_settings_survive_without_terminal_or_shell_startup(tmp_path: Path):
    module = installer()
    executable = tmp_path / "notes with spaces"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$MEETING_NOTES_NOTES_DIR" "$@"\n')
    executable.chmod(0o700)
    module.NOTES = executable
    vault = str(tmp_path / 'vault $(touch SHOULD_NOT_EXIST) `echo nope` "quoted"')
    workflow = module.workflow(
        "start --ask-title",
        {
            "MEETING_NOTES_NOTES_DIR": vault,
            "PATH": "/custom tools/bin",
            "MEETING_NOTES_MAX_RECORDING_SECONDS": "3600",
            "UNRELATED_SECRET": "must-not-be-copied",
        },
    )
    parameters = workflow["WFWorkflowActions"][0]["WFWorkflowActionParameters"]
    assert parameters["Shell"] == "/bin/sh"
    script = parameters["Script"]
    assert "UNRELATED_SECRET" not in script and "must-not-be-copied" not in script
    completed = subprocess.run(
        ["/bin/sh", "-c", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
        env={"HOME": str(tmp_path)},
        cwd=tmp_path,
    )
    assert completed.stdout.splitlines() == [vault, "start", "--ask-title"]
    assert completed.stderr == ""
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()
    assert "/opt/homebrew/bin" in script
    assert "MEETING_NOTES_MAX_RECORDING_SECONDS=3600" in script


def test_all_shortcuts_use_the_same_plain_shell_launcher():
    module = installer()
    for args in module.SHORTCUTS.values():
        parameters = module.workflow(args, {})["WFWorkflowActions"][0]["WFWorkflowActionParameters"]
        command = shlex.split(parameters["Script"])
        assert command[:2] == ["exec", "/usr/bin/env"]
        assert command[-len(shlex.split(args)) :] == shlex.split(args)
        assert "zsh" not in command
