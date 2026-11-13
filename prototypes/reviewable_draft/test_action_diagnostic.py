"""Fake-only action capture coverage; no model requests."""

# pyright: reportPrivateUsage=false

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from . import action_diagnostic as q
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
        "Synthetic action-only diagnostic source",
    )
    monkeypatch.setattr(q, "ROOT", root)
    return root


@pytest.fixture
def frozen(source: Path, tmp_path: Path) -> tuple[Path, str]:
    target = tmp_path / "actions-freeze"
    return target, q.freeze(target, IDENTITY)


def authored() -> dict[str, dict[str, Any]]:
    fixture = cast(
        dict[str, Any],
        json.loads(
            (Path(__file__).resolve().parents[2] / "tests/fixtures/actions_only.json").read_bytes()
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
    assert manifest["format"] == "reviewable-actions-only-1"
    assert manifest["settings"]["contract"] == "spoken-actions-only-1"
    assert "source/prototypes/reviewable_draft/actions.py" in manifest["files"]
    assert "source/prototypes/reviewable_draft/action_diagnostic.py" in manifest["files"]
    assert "source/prototypes/reviewable_draft/generation.py" in manifest["files"]
    assert (target / "EXPERIMENT.md").read_bytes() == (q.ROOT / q.DECLARATION).read_bytes()
    assert not (target / "results").exists()
    for packet in packets:
        body = packet.body()
        assert set(body["format"]["properties"]) == {"actions", "review_sources"}
        user_input = body["messages"][-1]["content"]
        for source in packet.snapshot.sources:
            if source.kind == "notes":
                assert source.text not in user_input


def test_six_action_only_responses_capture_once_and_reproduce_saved_results(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert final["capture_complete"] is True
    assert final["possibly_sent"] == 6 and len(http.posts) == 6
    assert not final["failed"] and not final["unsent"] and not final["incomplete_cases"]
    _, packets = q._validate(target, digest)
    for index, (name, packet) in enumerate(zip(q.generation.CASES, packets, strict=True), 1):
        slot = target / "results" / f"{index:02}-{name}"
        assert http.posts[index - 1] == packet.request_json.encode()
        raw = read(slot / "response/body.raw")
        result = q.generation.decode(packet, raw["message"]["content"])
        assert read(slot / "result.json") == json.loads(json.dumps(asdict(result)))
        assert not (slot / "draft.json").exists()
        assert (slot / "actions.md").read_text() == (
            "> MODEL-GENERATED diagnostic capture. Quality assessment pending.\n\n"
            + q.generation.render_result(result)
        )
    before = len(http.posts)
    with pytest.raises(FileExistsError):
        q.run(target, "Another invocation is forbidden", digest)
    assert len(http.posts) == before


def test_literal_failure_retains_independent_work_and_raw_reply_then_stops(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    fields: dict[str, Any] = {
        "actions": [
            {"source": "T1", "quote": "Support costs 120 dollars.", "context_sources": []},
            {"source": "T1", "quote": "Invented task.", "context_sources": []},
        ],
        "review_sources": [],
    }
    # A literal factual selection passes mechanics, not the semantic criterion.
    http.hook = lambda _method, _endpoint: None
    http.body = response(fields)
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"]
    assert final["possibly_sent"] == 1 and len(http.posts) == 1
    assert final["failed"] == ["unit_equivalence"] and len(final["unsent"]) == 5
    slot = target / "results/01-unit_equivalence"
    assert (slot / "response/body.raw").read_bytes() == http.body
    assert read(slot / "result.json")["issues"]
    text = (slot / "actions.md").read_text()
    assert "incomplete" in text.lower() and "Invented task" not in text
    assert "Support costs 120 dollars" in text
    assert not read(slot / "outcome.json")["capture_complete"]


def test_duplicate_known_references_do_not_abort_capture_or_rewrite_raw_reply(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    fields = authored()
    fields["unit_equivalence"]["review_sources"] = ["T1", "T1"]

    def duplicate_body(method: str, _endpoint: str) -> None:
        if method == "GET":
            directory = http.calls[-1][2]
            http.body = response(fields[directory.parents[1].name[3:]])

    http.hook = duplicate_body
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert final["capture_complete"] and len(http.posts) == 6
    slot = target / "results/01-unit_equivalence"
    raw = read(slot / "response/body.raw")
    assert json.loads(raw["message"]["content"])["review_sources"] == ["T1", "T1"]
    assert read(slot / "result.json")["review_sources"] == ["T1"]


def test_new_action_source_drift_stops_before_network(
    source: Path, frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    path = source / "prototypes/reviewable_draft/actions.py"
    path.write_bytes(path.read_bytes() + b"\n# changed after freeze\n")
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"] and final["possibly_sent"] == 0
    assert not http.calls


def test_manifest_pin_and_changed_quote_request_reject_unsent(
    frozen: tuple[Path, str], http: FakeHTTP
) -> None:
    target, digest = frozen
    request = target / "requests/unit_equivalence.json"
    request.write_bytes(request.read_bytes() + b" ")
    final = q.run(target, "Synthetic fake-transport approval", digest)
    assert not final["capture_complete"] and final["possibly_sent"] == 0
    assert not http.calls
