"""Fake-only coverage for the separate quoted-selection capture profile."""

# pyright: reportPrivateUsage=false

import json
from pathlib import Path
from typing import Any, cast

import pytest

from . import quoted_diagnostic as q
from .test_diagnostic import IDENTITY, FakeHTTP, git, read


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    for name in (*q.RUNTIME, q.INPUT, q.DECLARATION):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((q.ROOT / name).read_bytes())
    git(root, "init", "-q")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic quoted diagnostic source",
    )
    monkeypatch.setattr(q, "ROOT", root)
    return root


@pytest.fixture
def frozen(source: Path, tmp_path: Path) -> tuple[Path, str]:
    target = tmp_path / "quoted-freeze"
    return target, q.freeze(target, IDENTITY)


def authored() -> dict[str, dict[str, Any]]:
    fixture = cast(
        dict[str, Any],
        json.loads(
            (Path(__file__).resolve().parents[2] / "tests/fixtures/quoted_draft.json").read_bytes()
        ),
    )
    assert fixture["authored"] is True
    return {row["id"]: row["response"] for row in fixture["cases"]}


def response(fields: dict[str, Any]) -> bytes:
    return q._bytes(
        {
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(fields)},
        }
    )


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHTTP:
    fake = FakeHTTP()
    fields = authored()

    def prepare_body(method: str, _endpoint: str) -> None:
        if method == "GET":
            directory = fake.calls[-1][2]
            case = directory.parents[1].name[3:]
            fake.body = response(fields[case])

    fake.hook = prepare_body
    monkeypatch.setattr(q, "_http_process", fake.spawn)
    return fake


def test_separate_profile_freezes_its_actual_runtime_and_contract(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    manifest, packets = q._validate(target, digest)
    assert len(packets) == 6 and not http.calls
    assert manifest["format"] == "reviewable-draft-quoted-1"
    assert manifest["settings"]["contract"] == "source-quoted-actions-1"
    assert "source/prototypes/reviewable_draft/extraction.py" in manifest["files"]
    assert "source/prototypes/reviewable_draft/quoted_diagnostic.py" in manifest["files"]
    assert "source/prototypes/reviewable_draft/generation.py" in manifest["files"]
    assert (target / "EXPERIMENT.md").read_bytes() == (q.ROOT / q.DECLARATION).read_bytes()
    assert not (target / "results").exists()


def test_six_authored_quote_responses_capture_once_and_reproduce_the_saved_result(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert final["capture_complete"] is True
    assert final["possibly_sent"] == 6 and len(http.posts) == 6
    assert not final["failed"] and not final["unsent"] and not final["draft_incomplete_cases"]
    _, packets = q._validate(target, digest)
    for index, (name, packet) in enumerate(zip(q.generation.CASES, packets, strict=True), 1):
        slot = target / "results" / f"{index:02}-{name}"
        assert http.posts[index - 1] == packet.request_json.encode()
        assert read(slot / "extraction.json") == {"complete": True, "issues": []}
        raw = read(slot / "response/body.raw")
        result = q.generation.decode(packet, raw["message"]["content"])
        assert (slot / "draft.md").read_text() == (
            "> MODEL-GENERATED diagnostic capture. Quality assessment pending.\n\n"
            + q.generation.render_result(result)
        )
    before = len(http.posts)
    with pytest.raises(FileExistsError):
        q.run(target, "Another invocation is forbidden", digest)
    assert len(http.posts) == before


def test_selection_failure_retains_partial_work_and_raw_reply_then_stops(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    fields = authored()["additional"]
    fields["actions"]["items"].append(
        {"source": "T2", "quote": "Reschedule the Friday meeting.", "context_sources": []}
    )
    http.hook = lambda _method, _endpoint: None
    http.body = response(fields)
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"]
    assert final["possibly_sent"] == 1 and len(http.posts) == 1
    assert final["failed"] == ["additional"] and len(final["unsent"]) == 5
    slot = target / "results/01-additional"
    assert (slot / "response/body.raw").read_bytes() == http.body
    assert read(slot / "extraction.json")["complete"] is False
    assert read(slot / "extraction.json")["issues"]
    text = (slot / "draft.md").read_text()
    assert "incomplete" in text.lower() and "Reschedule" not in text
    assert "I will send the draft Friday" in text
    assert "Alex here" in text
    assert not read(slot / "outcome.json")["capture_complete"]


def test_new_extraction_source_drift_stops_before_network(
    source: Path, frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    path = source / "prototypes/reviewable_draft/extraction.py"
    path.write_bytes(path.read_bytes() + b"\n# changed after freeze\n")
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"] and final["possibly_sent"] == 0
    assert not http.calls


def test_manifest_pin_and_changed_quote_request_reject_unsent(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    request = target / "requests/additional.json"
    request.write_bytes(request.read_bytes() + b" ")
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"] and final["possibly_sent"] == 0
    assert not http.calls
