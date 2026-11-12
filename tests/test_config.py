from pathlib import Path

import pytest

from meeting_notes.config import Config


def test_recording_cap_defaults_to_one_hour_and_can_be_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MEETING_NOTES_MAX_RECORDING_SECONDS", raising=False)
    assert Config.from_env().max_recording_seconds == 3600
    monkeypatch.setenv("MEETING_NOTES_MAX_RECORDING_SECONDS", "5400")
    assert Config.from_env().max_recording_seconds == 5400


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_recording_cap_cannot_be_disabled_with_invalid_values(seconds: float):
    with pytest.raises(ValueError, match="positive and finite"):
        Config(
            data_dir=Path("data"),
            notes_dir=Path("notes"),
            model="fake",
            max_recording_seconds=seconds,
        )
