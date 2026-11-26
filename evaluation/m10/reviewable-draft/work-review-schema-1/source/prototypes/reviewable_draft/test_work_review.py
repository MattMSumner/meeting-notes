import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from . import work_review as review
from .model import Snapshot


def snapshot() -> Snapshot:
    return Snapshot(
        "Synthetic review",
        "2026-11-26T09:00:00-05:00",
        ("Them",),
        "Sam",
        "[00:00:00] Sam: I will review and send.  \n\n"
        "  Keep this indentation.\n"
        "[00:00:05] Sam: I will not review.\n"
        + "".join(f"[00:00:{index:02}] Them: A fact {index}.\n" for index in range(10, 19))
        + "[00:00:20] Sam: For sending: not before Friday, unless finance objects.\n",
        "  My own note.  \n\n\tDo not normalize this.\n",
    )


def packet() -> review.Prepared:
    return review.prepare(snapshot(), "host-generation")


def decode(groups: object) -> review.Result:
    return review.decode(packet(), json.dumps({"groups": groups}))


def test_payload_has_only_model_neutral_messages_and_groups_schema() -> None:
    prepared = packet()
    payload = prepared.payload()
    assert set(payload) == {"messages", "format"}
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    data = json.loads(payload["messages"][1]["content"])
    assert set(data) == {"meeting", "speech"}
    assert data["speech"] == [
        {
            "id": source.id,
            "speaker": source.speaker,
            "timestamp": source.timestamp,
            "text": source.text,
        }
        for source in prepared.snapshot.sources
        if source.kind == "transcript"
    ]
    assert prepared.snapshot.handwritten_text not in json.dumps(data)
    schema = payload["format"]
    assert schema == {
        "type": "object",
        "additionalProperties": False,
        "required": ["groups"],
        "properties": {
            "groups": {
                "type": "array",
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "enum": [f"T{index}" for index in range(1, 13)],
                    },
                },
            }
        },
    }
    assert review.decode(prepared, '{"groups":[["T1","T2"]]}').state == "draft"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{",
        '```json\n{"groups":[]}\n```',
        "[]",
        "null",
        "{}",
        '{"groups":[],"notice":"ok"}',
        '{"groups":[],"actions":[]}',
        '{"groups":[],"groups":[]}',
        '{"groups":NaN}',
        '{"groups":Infinity}',
        '{"groups":-Infinity}',
        '{"groups":null}',
        '{"groups":{}}',
        '{"groups":"T1"}',
        '{"groups":["T1"]}',
        '{"groups":[[]]}',
        '{"groups":[{"refs":["T1"]}]}',
        '{"groups":[[null]]}',
        '{"groups":[[true]]}',
        '{"groups":[[1]]}',
        '{"groups":[[1.0]]}',
        '{"groups":[["T99"]]}',
        '{"groups":[["N1"]]}',
        '{"groups":[["T1","T1",false]]}',
        '{"groups":[["T1"],["T1"],["N1"]]}',
        '{"groups":[["T1"],["T1","T99"]]}',
        '{"groups":[["T1"]],"state":"incomplete"}',
        '{"groups":[["T1"]]} trailing',
    ],
)
def test_invalid_content_is_never_accepted_or_salvaged(content: str) -> None:
    for route in (review.decode, review.host_incomplete):
        with pytest.raises((ValueError, TypeError)):
            route(packet(), content)


@pytest.mark.parametrize(
    "extra",
    [
        "quote",
        "title",
        "owner",
        "deadline",
        "currentness",
        "confidence",
        "state",
        "notice",
        "snapshot_id",
    ],
)
def test_wire_cannot_add_prose_semantics_or_host_fields(extra: str) -> None:
    with pytest.raises(ValueError, match="only groups"):
        review.decode(packet(), json.dumps({"groups": [["T1"]], extra: "anything"}))


def test_valid_duplicates_normalize_in_snapshot_order_without_merging_overlaps() -> None:
    result = decode(
        [
            ["T10", "T2", "T2"],
            ["T1", "T2"],
            ["T2", "T10"],
            ["T2", "T3"],
            ["T1"],
            ["T1", "T3"],
        ]
    )
    assert [group.refs for group in result.groups] == [
        ("T1", "T2"),
        ("T1",),
        ("T1", "T3"),
        ("T2", "T10"),
        ("T2", "T3"),
    ]
    text = review.render_result(result)
    assert text.count("I will not review.") == 3
    assert text.count("\n\n---\n\n") == 4


def test_bindings_include_complete_snapshot_generation_and_nested_groups() -> None:
    original = decode([["T1"]])
    other_generation = review.decode(review.prepare(snapshot(), "other"), '{"groups":[["T1"]]}')
    for changed in (
        replace(snapshot(), handwritten_text="Other writing."),
        replace(snapshot(), title="Other title"),
        replace(snapshot(), started_at="2026-11-27"),
        replace(snapshot(), attendees=("Someone else",)),
        replace(snapshot(), my_name="Someone else"),
        replace(snapshot(), transcript=snapshot().transcript.replace("A fact 10", "A fact ten")),
    ):
        with pytest.raises(ValueError):
            replace(original, snapshot=changed)
        with pytest.raises(ValueError):
            replace(packet(), snapshot=changed, snapshot_id=changed.snapshot_id)
        fresh = review.decode(review.prepare(changed, "host-generation"), '{"groups":[["T1"]]}')
        with pytest.raises(ValueError):
            replace(fresh, groups=original.groups)
    with pytest.raises(ValueError, match="different snapshot or generation"):
        replace(other_generation, groups=original.groups)
    with pytest.raises(ValueError):
        replace(original.groups[0], generation_id="other")
    with pytest.raises(ValueError):
        replace(original.groups[0], refs=("T2",))
    with pytest.raises(ValueError):
        replace(original, generation_id="other")
    with pytest.raises(ValueError):
        replace(packet(), generation_id="other")


def test_payload_mutation_does_not_change_saved_request_and_tampering_is_rejected() -> None:
    prepared = packet()
    body = prepared.payload()
    body["messages"][1]["content"] = "changed"
    body["format"]["properties"]["groups"]["items"]["items"]["enum"].append("N1")
    body["think"] = True
    assert prepared.payload() != body
    with pytest.raises(ValueError, match="input or settings|differs"):
        # Altering a schema, message, or settings cannot become an accepted packet.
        replace(prepared, payload_json=json.dumps(body))


def test_frozen_values_and_render_boundary_revalidate_forged_records() -> None:
    result = decode([["T1", "T2"]])
    for target, attribute, value in (
        (result.groups[0], "refs", ("T3",)),
        (result.snapshot, "handwritten_text", "edited"),
        (packet(), "generation_id", "other"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, attribute, value)
    object.__setattr__(result.groups[0], "refs", ("N1",))
    with pytest.raises(ValueError):
        review.render_result(result)
    result = decode([["T1"]])
    object.__setattr__(result.snapshot, "transcript", "[00:00:00] Sam: Different text.")
    with pytest.raises(ValueError):
        review.render_result(result)
    result = decode([["T1"]])
    object.__setattr__(result, "groups", [])
    with pytest.raises(TypeError):
        review.render_result(result)


def test_literal_turns_keep_whitespace_conditions_and_separate_source_ownership() -> None:
    result = decode([["T1", "T2", "T12"], ["T3"]])
    text = review.render_result(result)
    for source in result.snapshot.sources:
        if source.id in {"T1", "T2", "T12", "T3"}:
            assert source.text in text
    assert "  \n\n  Keep this indentation.\n" in text
    assert "not before Friday, unless finance objects.\n" in text
    assert "Spoken by Sam at 00\\:00\\:00" in text
    assert "Spoken by Them at 00\\:00\\:10" in text
    before_writing, writing = text.split("## Original handwritten notes")
    assert result.snapshot.handwritten_text not in before_writing
    assert result.snapshot.handwritten_text in writing
    assert "Written by Sam; kept as supplied." in writing
    assert "A fact 11" not in text
    for hidden in ("Suggested actions", "- [ ]", "T1", result.snapshot_id, result.generation_id):
        assert hidden not in text


def test_malicious_metadata_and_fences_stay_literal_without_hiding_source_strings() -> None:
    saved = replace(
        snapshot(),
        title="Unsafe\n## injected <script> [[link]]",
        my_name="Author\n## injection",
        transcript="[00:00:00] <script>[[Sam]]: ```\nT1 host-generation\n````\n<script>\n",
        handwritten_text="```\n# private-style heading\n````\n",
    )
    result = review.decode(review.prepare(saved, "host-generation"), '{"groups":[["T1"]]}')
    text = review.render_result(result)
    assert "\n## injected" not in text and "\n## injection" not in text
    assert "&lt;script&gt;\\[\\[Sam\\]\\]" in text
    assert "`````text\n```\nT1 host-generation\n````\n<script>\n`````" in text
    assert saved.handwritten_text in text


def test_empty_incomplete_and_unavailable_do_not_claim_absence_or_lose_writing() -> None:
    prepared = packet()
    ordinary = review.decode(prepared, '{"groups":[]}')
    incomplete = review.host_incomplete(prepared, '{"groups":[["T12"]]}')
    unavailable = review.host_unavailable(prepared)
    empty_text = review.render_result(ordinary)
    assert ordinary.state == "draft" and not ordinary.groups
    assert "No passages selected" in empty_text
    assert "does not establish absence of work" in empty_text
    assert "Incomplete selection" not in empty_text
    assert "**Incomplete selection.**" in review.render_result(incomplete)
    assert "not before Friday" in review.render_result(incomplete)
    assert "I will review and send" not in review.render_result(incomplete)
    assert not unavailable.groups
    assert "**Passage selection unavailable.**" in review.render_result(unavailable)
    for result in (ordinary, incomplete, unavailable):
        assert result.snapshot == prepared.snapshot
        assert prepared.snapshot.handwritten_text in review.render_result(result)
    with pytest.raises(ValueError):
        replace(incomplete, state="unavailable")


def test_reference_valid_missing_context_and_irrelevant_groups_remain_quality_defects() -> None:
    # T1 omits its withdrawal and later timing; T3 is only a fact. Both are valid wire.
    for groups in ([["T1"]], [["T3"]], [["T1", "T3"]]):
        result = decode(groups)
        assert result.state == "draft" and result.groups
        assert "I will not review" not in review.render_result(result)
    # Structural acceptance deliberately supplies no semantic grade or correction.


def test_pure_preparation_payload_decoding_and_rendering_do_not_read_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Unexpected IO")

    monkeypatch.setattr(Path, "read_text", unexpected)
    monkeypatch.setattr(Path, "read_bytes", unexpected)
    monkeypatch.setattr("builtins.open", unexpected)
    prepared = packet()
    prepared.payload()
    assert review.render_result(review.decode(prepared, '{"groups":[["T1"]]}'))
