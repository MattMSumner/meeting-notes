"""Authored synthetic examples check mechanics, not model or semantic quality."""

import importlib
import json
import socket
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, cast

import pytest

from . import actions as a
from . import examples
from .model import Snapshot

FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/actions_only.json"


def snapshots() -> dict[str, Snapshot]:
    return {name: draft.snapshot for name, draft in examples.load_examples().items()}


def packet(name: str = "additional") -> a.Prepared:
    return a.prepare(snapshots(), "authored-test")[a.CASES.index(name)]


def fields(name: str = "additional") -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text())
    return next(row["response"] for row in fixture["cases"] if row["id"] == name)


def decoded(name: str = "additional") -> a.Result:
    return a.decode(packet(name), json.dumps(fields(name)))


def reply(content: str) -> dict[str, Any]:
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content},
    }


def test_six_new_authored_replies_use_the_capture_wrapper_and_contract_order() -> None:
    fixture = json.loads(FIXTURE.read_text())
    assert set(fixture) == {"authored", "description", "cases"}
    assert fixture["authored"] is True and type(fixture["description"]) is str
    assert "not model quality" in fixture["description"]
    assert (
        tuple(row["id"] for row in fixture["cases"])
        == a.CASES
        == (
            "unit_equivalence",
            "accepted_status_answer",
            "partial_coordination_retracted",
            "cancellation_with_new_task",
            "qualified_external_timing",
            "additional",
        )
    )
    for row in fixture["cases"]:
        assert set(row) == {"id", "response"}
        assert set(row["response"]) == {"actions", "review_sources"}
        result = decoded(row["id"])
        result.validate()
        assert result.complete and not result.issues
        assert result.snapshot == packet(row["id"]).snapshot
        assert result.generation_id == packet(row["id"]).generation_id


def test_requests_include_complete_speech_and_metadata_but_exclude_all_writing() -> None:
    for name, p in zip(a.CASES, a.prepare(snapshots(), "host"), strict=True):
        body = p.body()
        assert p.generation_id == f"host/{name}"
        assert body["model"] == a.MODEL == "qwen3:30b"
        assert body["stream"] is False and body["think"] is True
        assert (
            body["options"]
            == {"temperature": 0, "num_ctx": a.CONTEXT}
            == {
                "temperature": 0,
                "num_ctx": 32768,
            }
        )
        assert body["messages"][0] == {"role": "system", "content": a.PROMPT}
        inputs = json.loads(body["messages"][1]["content"])
        assert set(inputs) == {"meeting", "sources"}
        assert inputs["meeting"] == {
            "title": p.snapshot.title,
            "started_at": p.snapshot.started_at,
            "attendees": list(p.snapshot.attendees),
            "my_name": p.snapshot.my_name,
        }
        assert inputs["sources"] == [
            {"id": s.id, "speaker": s.speaker, "timestamp": s.timestamp, "text": s.text}
            for s in p.snapshot.sources
            if s.kind == "transcript"
        ]
        for s in p.snapshot.sources:
            if s.kind == "notes":
                assert s.text not in p.request_json
    assert packet("accepted_status_answer").snapshot.handwritten_text == ""


def test_schema_has_only_two_fields_and_does_not_demand_unique_references() -> None:
    p = packet()
    schema = p.body()["format"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["actions", "review_sources"]
    props = schema["properties"]
    assert set(props) == {"actions", "review_sources"}
    item = props["actions"]["items"]
    assert item["additionalProperties"] is False
    assert (
        set(item["required"])
        == set(item["properties"])
        == {
            "source",
            "quote",
            "context_sources",
        }
    )
    ids = [s.id for s in p.snapshot.sources if s.kind == "transcript"]
    assert item["properties"]["source"]["enum"] == ids
    for refs in (item["properties"]["context_sources"], props["review_sources"]):
        assert refs["items"]["enum"] == ids
        assert "uniqueItems" not in refs


@pytest.mark.parametrize("change", ["writing", "speech", "title", "attendees", "generation"])
def test_saved_packets_and_results_reject_rebinding(change: str) -> None:
    p, result = packet(), decoded()
    if change == "generation":
        changes: dict[str, Any] = {"generation_id": "different-host"}
    else:
        attr = {"writing": "handwritten_text", "speech": "transcript"}.get(change, change)
        value = ("Someone",) if attr == "attendees" else getattr(p.snapshot, attr) + " changed"
        changes = {"snapshot": replace(p.snapshot, **{attr: value})}
    with pytest.raises(ValueError, match="different snapshot or generation"):
        replace(p, **changes).body()
    with pytest.raises(ValueError, match="different snapshot or generation"):
        replace(result, **changes)


def test_new_host_generations_and_writing_have_distinct_bindings_without_leaking_writing() -> None:
    inputs = snapshots()
    first = a.prepare(inputs, "first")[-1]
    inputs["additional"] = replace(inputs["additional"], handwritten_text="New private writing.")
    second = a.prepare(inputs, "second")[-1]
    assert first.request_json == second.request_json
    r1 = a.decode(first, json.dumps(fields()))
    r2 = a.decode(second, json.dumps(fields()))
    assert r1.snapshot.snapshot_id != r2.snapshot.snapshot_id
    assert r1.generation_id != r2.generation_id
    assert "New private writing." not in second.request_json
    assert "New private writing." in a.render_result(r2)


@pytest.mark.parametrize("change", ["model", "options", "format", "messages"])
def test_request_drift_fails_before_transport(change: str) -> None:
    p = packet()
    body = p.body()
    body[change] = "changed"
    with pytest.raises(ValueError, match="differs"):
        a.generate(
            replace(p, request_json=json.dumps(body)), lambda _: pytest.fail("Must not send")
        )


@pytest.mark.parametrize("identity", ["", " ", None, 42])
def test_host_generation_identity_is_required(identity: Any) -> None:
    with pytest.raises(ValueError, match="generation"):
        a.prepare(snapshots(), identity)
    with pytest.raises(ValueError, match="generation"):
        replace(packet(), generation_id=identity).body()


def test_missing_or_invalid_snapshot_fails_locally() -> None:
    inputs = snapshots()
    del inputs["additional"]
    with pytest.raises(KeyError):
        a.prepare(inputs, "missing")
    inputs["additional"] = cast(Any, None)
    with pytest.raises(TypeError, match="Snapshot"):
        a.prepare(inputs, "invalid")


@pytest.mark.parametrize("text", ["word " * 7000, "界" * 11000])
def test_complete_request_size_is_checked_before_any_transport(text: str) -> None:
    inputs = snapshots()
    inputs["additional"] = replace(inputs["additional"], transcript=f"[00:00:00] Sam: {text}")
    with pytest.raises(ValueError, match="context; not sent"):
        a.prepare(inputs, "oversized")


def test_excluded_writing_does_not_consume_the_model_context() -> None:
    inputs = snapshots()
    original = a.prepare(inputs, "host")[-1]
    inputs["additional"] = replace(inputs["additional"], handwritten_text="writing " * 10000)
    assert a.prepare(inputs, "host")[-1].request_json == original.request_json


def test_schema_and_source_metadata_count_toward_the_complete_context_limit() -> None:
    inputs = snapshots()
    inputs["additional"] = replace(
        inputs["additional"],
        transcript="\n".join(f"[00:00:00] Sam: Word {i}." for i in range(350)),
    )
    assert len(inputs["additional"].transcript.encode()) < a.CONTEXT // 2
    with pytest.raises(ValueError, match="context; not sent"):
        a.prepare(inputs, "metadata-too-large")


@pytest.mark.parametrize("location", ["root", "item"])
@pytest.mark.parametrize(
    "extra", ["summary", "state", "notice", "owner", "deadline", "generation_id"]
)
def test_extra_fields_are_fatal(location: str, extra: str) -> None:
    data = fields()
    target = data if location == "root" else data["actions"][0]
    target[extra] = "Invented prose"
    with pytest.raises(ValueError):
        a.decode(packet(), json.dumps(data))


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        "[]",
        '{"actions":[]}',
        '{"actions":[],"review_sources":[],"actions":[]}',
        '{"actions":[{"source":"T1","quote":"x","quote":"y","context_sources":[]}],'
        '"review_sources":[]}',
        '{"actions":NaN,"review_sources":[]}',
        '{"actions":',
        '{"actions":null,"review_sources":[]}',
        '{"actions":[],"review_sources":"T1"}',
        '{"actions":[{}],"review_sources":[]}',
    ],
)
def test_missing_malformed_duplicate_and_wrong_type_fields_are_fatal(content: str) -> None:
    with pytest.raises(ValueError):
        a.decode(packet(), content)


@pytest.mark.parametrize("location", ["source", "context_sources", "review_sources"])
@pytest.mark.parametrize("ref", ["T999", "N1", "", None, 1, ["T1"]])
def test_every_reference_is_validated_before_repetition_or_self_context_is_removed(
    location: str,
    ref: Any,
) -> None:
    data = fields()
    data["actions"] = [data["actions"][0], dict(data["actions"][0])]
    if location == "source":
        data["actions"][1][location] = ref
    elif location == "context_sources":
        data["actions"][1][location] = ["T1", "T1", ref]
    else:
        data[location] = ["T2", "T2", ref]
    with pytest.raises(ValueError):
        a.decode(packet(), json.dumps(data))


@pytest.mark.parametrize("key,value", [("quote", 1), ("quote", None), ("context_sources", "T1")])
def test_wrong_selection_types_are_fatal(key: str, value: Any) -> None:
    data = fields()
    data["actions"][0][key] = value
    with pytest.raises(ValueError):
        a.decode(packet(), json.dumps(data))


def test_known_repeats_self_context_and_identical_selections_are_canonicalized_in_order() -> None:
    data = fields()
    first, second = data["actions"]
    first["context_sources"] = ["T2", "T1", "T2", "T1"]
    data["actions"] = [first, dict(first, context_sources=["T2"]), second, second]
    data["review_sources"] = ["T2", "T1", "T2", "T1"]
    result = a.decode(packet(), json.dumps(data))
    assert result.complete and len(result.actions) == 2
    assert [(s.source, s.context_sources) for s in result.actions] == [
        ("T1", ("T2",)),
        ("T2", ("T1",)),
    ]
    assert result.review_sources == ("T2", "T1")


@pytest.mark.parametrize(
    "quote,code",
    [
        (" ", "quote_blank"),
        ("Invented rejected task", "quote_absent"),
        ("i will send the draft Friday.", "quote_absent"),
        ("I will send Friday.", "quote_absent"),
        ("I will send the draft Friday.\n", None),
    ],
)
def test_literal_failures_preserve_independent_work_and_focused_context(
    quote: str,
    code: str | None,
) -> None:
    data = fields()
    data["actions"][0]["quote"] = quote
    data["actions"][0]["context_sources"] = ["T1", "T2", "T2"]
    raw = reply(json.dumps(data))
    attempt = a.generate(packet(), lambda _: raw)
    assert attempt.error is None and attempt.result is not None
    assert json.loads(cast(str, attempt.response_json)) == raw
    result = attempt.result
    if code is None:
        assert result.complete and len(result.actions) == 2
    else:
        assert not result.complete and len(result.actions) == 1
        assert result.actions[0].source == "T2"
        assert result.review_sources == ("T1", "T2")
        assert result.issues == (a.Issue(0, cast(a.IssueCode, code), "T1", quote, ("T2",)),)
        text = a.render_result(result)
        assert text.index("**Incomplete action extraction.**") < text.index("## Suggested actions")
        assert "Alex here. I will review it next week." in text
        if quote.strip():
            assert quote not in text


@pytest.mark.parametrize("text,quote", [("Send it. Send it.", "Send it."), ("banana", "ana")])
def test_ambiguous_and_overlapping_quotes_require_focused_review(text: str, quote: str) -> None:
    inputs = snapshots()
    inputs["additional"] = replace(inputs["additional"], transcript=f"[00:00:00] Sam: {text}")
    p = a.prepare(inputs, "ambiguous")[-1]
    data: dict[str, Any] = {
        "actions": [{"source": "T1", "quote": quote, "context_sources": []}],
        "review_sources": [],
    }
    result = a.decode(p, json.dumps(data))
    assert not result.complete and not result.actions
    assert result.issues[0].code == "quote_ambiguous" and result.review_sources == ("T1",)
    rendered = a.render_result(result)
    assert "**Incomplete action extraction.**" in rendered
    assert "No suggestions supplied." in rendered
    assert "Independent valid selections remain" not in rendered


def test_unknown_context_is_fatal_even_when_the_quote_itself_is_absent() -> None:
    data = fields()
    data["actions"][0].update(quote="Absent wording", context_sources=["T1", "T999"])
    with pytest.raises(ValueError, match="reference"):
        a.decode(packet(), json.dumps(data))


def test_withdrawal_and_later_timing_remain_complete_context_without_invented_due() -> None:
    for name, qualifier in (
        ("partial_coordination_retracted", "I will not review the draft."),
        ("qualified_external_timing", "Not before next Friday unless finance objects."),
    ):
        result = decoded(name)
        assert len(result.actions) == 1 and "send the invoice" in result.actions[0].quote
        assert result.actions[0].context_sources == ("T2",)
        text = a.render_result(result)
        for s in result.snapshot.sources:
            assert s.text in text
        assert qualifier in text and "Due:" not in text
        assert "Spoken by Sam at 00\\:00\\:05" in text
    replacement = decoded("cancellation_with_new_task")
    assert replacement.actions[0].quote == "I will send the invoice."
    assert "Scratch that" in a.render_result(replacement)


def test_independent_undertakings_and_original_writing_are_separately_discoverable() -> None:
    result = decoded()
    assert len(result.actions) == 2
    text = a.render_result(result)
    assert "send the draft Friday" in text and "Alex here. I will review it next week." in text
    assert "Spoken by Them" in text
    actions, writing = text.split("## Original handwritten notes")
    assert "venue" not in actions and "40 seats" not in actions
    assert (
        result.snapshot.handwritten_text in writing and "excluded from this model task" in writing
    )
    assert "## Summary" not in text and "## Suggested decisions" not in text


def test_empty_actions_are_no_suggestions_not_verified_absence_and_prices_stay_original() -> None:
    for name in ("unit_equivalence", "accepted_status_answer"):
        result = decoded(name)
        assert not result.actions and result.complete
        text = a.render_result(result)
        assert "No suggestions supplied. This does not verify that no work was missed." in text
        assert "**Action-only AI draft — review required**" in text
    price = a.render_result(decoded("unit_equivalence"))
    assert "Support costs 120 dollars." in price and "Support costs 12000 cents." in price
    assert "equivalent" not in price and "conflict" not in price


def test_a_literal_price_as_action_is_mechanically_admissible_and_fails_semantic_criteria() -> None:
    data: dict[str, Any] = {
        "actions": [{"source": "T1", "quote": "Support costs 120 dollars.", "context_sources": []}],
        "review_sources": [],
    }
    result = a.decode(packet("unit_equivalence"), json.dumps(data))
    # This deliberately fails the no-price-as-work criterion in ACTIONS.md.
    assert result.complete and not result.issues and len(result.actions) == 1
    assert result.actions[0].quote == "Support costs 120 dollars."


def test_metadata_markup_and_fences_cannot_escape_their_presentation() -> None:
    inputs = snapshots()
    speech = "Send `draft` <script>x</script> **Friday**.\n```\n# source heading\n````"
    writing = "```\n# written heading\n<script>bad</script>\n`````\n[[private]]"
    inputs["additional"] = replace(
        inputs["additional"],
        title="Title\n# injection <script>x</script>",
        started_at="date\n![image](bad)",
        attendees=("<b>Guest</b>\n# heading",),
        my_name="Writer\n## forged",
        transcript=f"[00:00:00] <b>Sam</b>: {speech}",
        handwritten_text=writing,
    )
    p = a.prepare(inputs, "escape")[-1]
    result = a.decode(
        p,
        json.dumps(
            {
                "actions": [{"source": "T1", "quote": speech, "context_sources": []}],
                "review_sources": [],
            }
        ),
    )
    text = a.render_result(result)
    assert text.startswith("# Title \\# injection &lt;script&gt;x&lt;\\/script&gt;")
    assert "Started: date \\!\\[image\\]\\(bad\\)" in text
    assert "&lt;b&gt;Guest&lt;\\/b&gt; \\# heading" in text
    assert "Written by Writer \\#\\# forged" in text
    assert "Spoken by &lt;b&gt;Sam&lt;\\/b&gt;" in text
    assert (
        "Selected speech: “Send \\`draft\\` &lt;script&gt;x&lt;\\/script&gt; \\*\\*Friday" in text
    )
    assert f"`````text\n{speech}\n`````" in text
    assert f"``````text\n{writing}\n``````" in text


def test_results_are_immutable_and_revalidate_all_nested_values() -> None:
    result = decoded()
    for obj, attr, value in (
        (packet(), "generation_id", "forged"),
        (result, "actions", ()),
        (result.actions[0], "quote", "forged"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, value)
    invalid: tuple[dict[str, Any], ...] = (
        {"actions": list(result.actions)},
        {"review_sources": ["T1"]},
        {"issues": []},
        {"actions": (replace(result.actions[0], context_sources=cast(Any, ["T2"])),)},
        {"actions": (replace(result.actions[0], source="N1"),)},
        {"actions": (replace(result.actions[0], quote="Invented selection"),)},
        {"actions": (result.actions[0], result.actions[0])},
        {"review_sources": ("T1", "T1")},
    )
    for changes in invalid:
        with pytest.raises((ValueError, TypeError)):
            replace(result, **cast(Any, changes))
    object.__setattr__(result.actions[0], "quote", "forged after validation")
    with pytest.raises(ValueError, match="literal"):
        a.render_result(result)


def test_issues_must_match_their_sources_and_keep_focused_evidence() -> None:
    data = fields()
    data["actions"][0]["quote"] = "Rejected wording"
    result = a.decode(packet(), json.dumps(data))
    issue = result.issues[0]
    with pytest.raises(FrozenInstanceError):
        cast(Any, issue).quote = "mutated"
    for changes in (
        {"code": "quote_blank"},
        {"item_index": -1},
        {"source": "T999"},
        {"quote": "I will send the draft Friday."},
    ):
        with pytest.raises((ValueError, TypeError)):
            replace(result, issues=(replace(issue, **changes),))
    with pytest.raises(ValueError, match="focused review"):
        replace(result, review_sources=())


def test_explicit_transport_runs_once_and_cannot_mutate_saved_request_or_raw_response() -> None:
    p = packet()
    raw = reply(json.dumps(fields()))
    calls = 0

    def post(body: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        body["messages"] = []
        return raw

    attempt = a.generate(p, explicit_post=post)
    raw["message"]["content"] = "changed after capture"
    assert calls == 1 and attempt.error is None and attempt.result is not None
    assert attempt.result.complete and p.body()["messages"]
    assert (
        json.loads(cast(str, attempt.response_json))["message"]["content"]
        != raw["message"]["content"]
    )


@pytest.mark.parametrize(
    "failure",
    [
        "transport",
        "error",
        "length",
        "unfinished",
        "missing",
        "role",
        "content_type",
        "content",
        "shape",
    ],
)
def test_failures_preserve_raw_responses_and_errors_without_retry(failure: str) -> None:
    raw = reply(json.dumps(fields()))
    if failure == "length":
        raw["done_reason"] = "length"
    elif failure == "unfinished":
        raw["done"] = False
    elif failure == "missing":
        raw["message"] = {}
    elif failure == "role":
        raw["message"]["role"] = "user"
    elif failure == "content_type":
        raw["message"]["content"] = None
    elif failure == "content":
        raw["message"]["content"] = '{"actions":'
    elif failure == "shape":
        raw["message"]["content"] = "{}"
    elif failure == "error":
        raw = {"error": "synthetic server error"}
    calls = 0

    def post(_: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if failure == "transport":
            raise TimeoutError("synthetic timeout")
        return raw

    attempt = a.generate(packet(), post)
    assert calls == 1 and attempt.result is None and attempt.error
    if failure == "transport":
        assert attempt.response_json is None and attempt.error == "TimeoutError: synthetic timeout"
    else:
        assert json.loads(cast(str, attempt.response_json)) == raw


def test_import_and_render_have_no_io_or_implicit_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_: Any, **__: Any) -> Any:
        pytest.fail("No IO allowed")

    with monkeypatch.context() as context:
        for method in ("read_text", "read_bytes", "write_text", "write_bytes", "open"):
            context.setattr(Path, method, forbidden)
        context.setattr(socket, "create_connection", forbidden)
        context.setattr(socket.socket, "connect", forbidden)
        importlib.reload(a)
    # Reload first so the exact immutable record types match the renderer.
    p, result = packet(), decoded()
    with monkeypatch.context() as context:
        for method in ("read_text", "read_bytes", "write_text", "write_bytes", "open"):
            context.setattr(Path, method, forbidden)
        context.setattr(socket, "create_connection", forbidden)
        assert "Action-only AI draft" in a.render_result(result)
    with pytest.raises(TypeError):
        cast(Any, a.generate)(p)
