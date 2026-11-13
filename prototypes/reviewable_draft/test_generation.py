import json
from dataclasses import replace
from typing import Any, cast

import pytest

from . import examples
from .generation import CASES, CONTEXT, MODEL, Prepared, decode, generate, prepare


def packets() -> tuple[Prepared, ...]:
    return prepare({k: v.snapshot for k, v in examples.load_examples().items()}, "offline-test")


def response_fields(name: str = "additional") -> dict[str, Any]:
    draft = examples.load_examples()[name]
    return {
        s.kind: {
            "state": s.state,
            "items": [{"text": i.text, "sources": list(i.sources)} for i in s.items],
            "notice": s.notice,
            "review_sources": list(s.review_sources),
        }
        for s in draft.sections
    }


def reply(content: str) -> dict[str, Any]:
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content},
    }


def test_fixed_requests_keep_complete_inputs_and_omit_authored_target_text() -> None:
    prepared = packets()
    assert len(prepared) == 6
    for name, packet in zip(CASES, prepared, strict=True):
        assert packet.generation_id == f"offline-test/{name}"
        body = packet.body()
        assert body["model"] == MODEL
        assert body["stream"] is False and body["think"] is True
        assert body["options"] == {"temperature": 0, "num_ctx": CONTEXT}
        inputs = json.loads(body["messages"][1]["content"])
        assert inputs["transcript"] == packet.snapshot.transcript
        assert inputs["handwritten_text"] == packet.snapshot.handwritten_text
        assert inputs["meeting"]["my_name"] == packet.snapshot.my_name
        assert inputs["meeting"]["attendees"] == list(packet.snapshot.attendees)
        assert [s["text"] for s in inputs["sources"]] == [s.text for s in packet.snapshot.sources]
        assert set(inputs) == {"meeting", "transcript", "handwritten_text", "sources"}
        assert set(body["format"]["properties"]) == {"summary", "decisions", "actions", "review"}


def test_schema_cannot_cite_writing_as_spoken_work_or_set_host_identity() -> None:
    packet = packets()[0]
    fields = packet.body()["format"]["properties"]
    for kind in ("summary", "decisions", "actions", "review"):
        assert set(fields[kind]["properties"]) == {"state", "items", "notice", "review_sources"}
        ids = fields[kind]["properties"]["items"]["items"]["properties"]["sources"]["items"]["enum"]
        assert ids == [
            s.id for s in packet.snapshot.sources if kind == "review" or s.kind == "transcript"
        ]


def test_empty_writing_and_identical_snapshots_keep_separate_host_generations() -> None:
    snapshots = {k: v.snapshot for k, v in examples.load_examples().items()}
    a, b = prepare(snapshots, "a"), prepare(snapshots, "b")
    for index, name in enumerate(CASES):
        assert a[index].request_json == b[index].request_json
        content = json.dumps(response_fields(name))
        first, second = decode(a[index], content), decode(b[index], content)
        assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
        assert first.generation_id != second.generation_id
        with pytest.raises(ValueError, match="different generation"):
            replace(first, sections=second.sections)
    assert a[2].snapshot.handwritten_text == ""


def test_saved_packet_cannot_silently_change_inputs_or_request_settings() -> None:
    packet = packets()[0]
    body = packet.body()
    body["options"]["temperature"] = 1
    with pytest.raises(ValueError, match="differs"):
        replace(packet, request_json=json.dumps(body)).body()
    changed = replace(packet.snapshot, handwritten_text="Changed synthetic input.")
    with pytest.raises(ValueError, match="differs"):
        replace(packet, snapshot=changed).body()
    assert packet.body()["options"]["temperature"] == 0


@pytest.mark.parametrize("identity", ["", " ", None, 42])
def test_host_generation_identity_is_required(identity: Any) -> None:
    snapshots = {k: v.snapshot for k, v in examples.load_examples().items()}
    with pytest.raises(ValueError, match="generation"):
        prepare(snapshots, identity)


def test_oversized_complete_request_is_rejected_before_transport() -> None:
    snapshots = {k: v.snapshot for k, v in examples.load_examples().items()}
    snapshots[CASES[0]] = replace(snapshots[CASES[0]], handwritten_text="x" * 100_000)
    with pytest.raises(ValueError, match="context; not sent"):
        prepare(snapshots, "oversized")


@pytest.mark.parametrize("name", CASES)
def test_authored_responses_decode_without_semantic_classification(name: str) -> None:
    packet = packets()[CASES.index(name)]
    draft = decode(packet, json.dumps(response_fields(name)))
    assert draft.snapshot == packet.snapshot
    assert draft.generation_id == packet.generation_id
    assert all(s.generation_id == packet.generation_id for s in draft.sections)
    assert all(s.snapshot_id == packet.snapshot.snapshot_id for s in draft.sections)


@pytest.mark.parametrize("change", ["wrong_source", "unknown_source", "extra_identity", "items"])
def test_invalid_model_fields_are_rejected_instead_of_repaired(change: str) -> None:
    fields = response_fields()
    if change == "wrong_source":
        fields["actions"]["items"][0]["sources"] = ["N1"]
    elif change == "unknown_source":
        fields["actions"]["items"][0]["sources"] = ["T999"]
    elif change == "extra_identity":
        fields["actions"]["generation_id"] = "model-supplied"
    else:
        fields["actions"]["items"] = "an array was required"
    with pytest.raises(ValueError):
        decode(packets()[0], json.dumps(fields))


@pytest.mark.parametrize("content", ['{"summary":{},"summary":{}}', '{"value":NaN}', "[]"])
def test_ambiguous_or_non_json_model_content_is_rejected(content: str) -> None:
    with pytest.raises(ValueError):
        decode(packets()[0], content)


def test_unavailable_section_keeps_independent_work_without_rejected_items() -> None:
    fields = response_fields()
    review: dict[str, Any] = {
        "state": "unavailable",
        "notice": "Written-note analysis could not be supplied; inspect these passages.",
        "review_sources": ["T1", "N1"],
        "items": [],
    }
    fields["review"] = review
    packet = packets()[0]
    draft = decode(packet, json.dumps(fields))
    assert draft.sections[2].items
    assert draft.sections[3].state == "unavailable" and not draft.sections[3].items
    review["items"] = [{"text": "Rejected suggestion", "sources": ["T1"]}]
    with pytest.raises(ValueError, match="unavailable"):
        decode(packet, json.dumps(fields))


def test_fake_transport_is_called_once_and_cannot_mutate_saved_request_or_response() -> None:
    packet = packets()[0]
    raw = reply(json.dumps(response_fields()))
    calls: list[dict[str, Any]] = []

    def post(body: dict[str, Any]) -> dict[str, Any]:
        calls.append(body)
        body["messages"] = []
        return raw

    attempt = generate(packet, post)
    raw["message"]["content"] = "changed after capture"
    assert len(calls) == 1 and attempt.error is None and attempt.draft is not None
    assert packet.body()["messages"]
    assert attempt.response_json is not None
    assert json.loads(attempt.response_json)["message"]["content"] != "changed after capture"


@pytest.mark.parametrize("failure", ["transport", "length", "unfinished", "missing", "content"])
def test_failure_retains_captured_output_and_never_sends_a_correction(failure: str) -> None:
    calls = 0
    raw = reply(json.dumps(response_fields()))
    if failure == "length":
        raw["done_reason"] = "length"
    elif failure == "unfinished":
        raw["done"] = False
    elif failure == "missing":
        raw["message"] = {}
    elif failure == "content":
        raw["message"]["content"] = '{"summary": '

    def post(_: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if failure == "transport":
            raise TimeoutError("synthetic timeout")
        return raw

    attempt = generate(packets()[0], post)
    assert calls == 1 and attempt.draft is None and attempt.error
    if failure == "transport":
        assert attempt.response_json is None
    else:
        assert json.loads(cast(str, attempt.response_json)) == raw


def test_structurally_valid_wrong_meaning_remains_an_explicit_evaluation_concern() -> None:
    fields = response_fields()
    fields["summary"]["items"] = [{"text": "A fictional rocket was approved.", "sources": ["T1"]}]
    draft = decode(packets()[0], json.dumps(fields))
    assert draft.sections[0].items[0].text == "A fictional rocket was approved."
