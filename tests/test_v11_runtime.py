"""Authored V11 transport replies; no archived response conversion or model inference."""

import json
from pathlib import Path
from typing import Any, Literal

import pytest
from comparison_helpers import account, additional
from test_current_ollama import MEETING, Transport, model, reply
from test_v11_compiler import action, draft

from meeting_notes.audit import V11Audit
from meeting_notes.comparison_v11 import Claim, Comparison
from meeting_notes.contract_v11 import SupportedText, TimingUpdate
from meeting_notes.evidence import Evidence, Generation
from meeting_notes.ollama import OllamaError, OllamaSummarizer
from meeting_notes.render import render_note
from meeting_notes.spans_v11 import Anchor, snapshot
from meeting_notes.store import MeetingDir
from meeting_notes.summary import Summary, SummaryError


def generation(engine: OllamaSummarizer, summary: Summary) -> Generation:
    audit = engine.audit
    return Generation(
        version=10,
        summary=summary,
        audit=audit,
        evidence=Evidence(
            transcript=audit.snapshot.transcript or "",
            context=audit.context,
            handwritten_original=audit.handwritten_original,
            handwritten_text=audit.snapshot.notes or "",
        ),
    )


@pytest.mark.parametrize(
    "field", ["overview", "undertaking", "context", "timing", "update", "original"]
)
def test_forbidden_note_ids_fail_on_initial_and_correction_without_fallback(field: str):
    transcript = "[00:00:00] Sam: I will send the invoice Friday."
    notes = "I will send the invoice Friday."
    saved = snapshot(transcript, notes)
    value = draft(action(saved.sources[0], "Friday"))
    selected = value.action_items[0]
    if field == "overview":
        value.overview = [SupportedText(text="Invoice discussion.", sources=["N1"])]
    elif field == "undertaking":
        selected.undertaking.source_id = "N1"
    elif field == "context":
        selected.context = [Anchor(source_id="N1", quote=notes)]
    elif field == "timing":
        selected.timing = Anchor(source_id="N1", quote="Friday")
    elif field == "original":
        selected.original_commitment_id = "N1"
    else:
        value.timing_updates = [
            TimingUpdate(
                original_commitment_id="T1", evidence=[Anchor(source_id="N1", quote="Friday")]
            )
        ]
    transport = Transport(additional(notes), value.model_dump_json(), value.model_dump_json())
    engine = model(transport)
    with pytest.raises(SummaryError, match="Invalid transcript source: N1"):
        engine.summarize(MEETING, transcript, handwritten_text=notes)
    assert len(transport.requests) == 3 and engine.audit.selected is None
    assert all(attempt.blocking for attempt in engine.audit.attempts)
    schema = transport.requests[1]["format"]
    assert "N1" not in json.dumps(schema)
    assert set(schema["properties"]) == {
        "overview",
        "key_points",
        "decisions",
        "action_items",
        "timing_updates",
    }


@pytest.mark.parametrize("section", ["overview", "key_points", "decisions"])
def test_notes_numbers_cannot_enter_spoken_core_on_either_attempt(section: str):
    value = draft()
    setattr(value, section, [SupportedText(text="Price is 500 dollars.", sources=["T1"])])
    transport = Transport(additional("Written price 500 dollars."), *[value.model_dump_json()] * 2)
    engine = model(transport)
    with pytest.raises(SummaryError, match="in notes"):
        engine.summarize(
            MEETING, "Spoken price 120 dollars.", handwritten_text="Written price 500 dollars."
        )
    assert engine.audit.selected is None
    assert all(a.selection_errors and a.compilation for a in engine.audit.attempts)


@pytest.mark.parametrize("valid_first", [False, True])
def test_wrong_source_correction_only_falls_back_to_valid_first_draft(valid_first: bool):
    first = reply("An ungrounded cost 999 dollars." if valid_first else "Price 500 dollars.")
    transport = Transport(
        additional("Written price 500 dollars."), first, reply("Price 500 dollars.")
    )
    engine = model(transport)
    if valid_first:
        result = engine.summarize(
            MEETING, "Spoken price 120 dollars.", handwritten_text="Written price 500 dollars."
        )
        assert result.overview == "An ungrounded cost 999 dollars."
        assert engine.audit.selected == 0
        generation(engine, result)
    else:
        with pytest.raises(SummaryError, match="in notes"):
            engine.summarize(
                MEETING, "Spoken price 120 dollars.", handwritten_text="Written price 500 dollars."
            )
        assert engine.audit.selected is None
    assert engine.audit.attempts[1].selection_errors


def test_invented_action_cannot_become_a_valid_fallback():
    transcript = "[00:00:00] Sam: Service costs 120 dollars."
    value = draft(action(snapshot(transcript).sources[0]))
    transport = Transport(value.model_dump_json(), value.model_dump_json())
    engine = model(transport)
    with pytest.raises(SummaryError, match="Noncommitment T1"):
        engine.summarize(MEETING, transcript)
    assert engine.audit.selected is None
    assert all(
        a.compilation and a.compilation.commitments[0].disposition == "rejected"
        for a in engine.audit.attempts
    )


def test_removing_invented_action_does_not_protect_its_mere_source_id():
    transcript = "[00:00:00] Sam: Service costs 120 dollars. I will check the invoice."
    sources = snapshot(transcript).sources
    first = draft(action(sources[0]), action(sources[1]))
    correction = draft(action(sources[1]))
    transport = Transport(first.model_dump_json(), correction.model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, transcript)
    assert len(result.action_items) == 1 and result.action_items[0].task == sources[1].text
    assert engine.audit.selected == 1 and not engine.audit.attempts[1].selection_errors
    generation(engine, result)


@pytest.mark.parametrize("lost", ["action", "timing", "external_timing", "agreement"])
@pytest.mark.parametrize("blocked_first", [False, True])
def test_correction_preserves_admissible_evidence_even_from_blocked_draft(
    lost: str, blocked_first: bool
):
    transcript = (
        "[00:00:00] Sam: I will send the invoice by Friday. "
        "Actually Monday instead. Cost 120 dollars. Agreed, release Tuesday."
    )
    sources = snapshot(transcript).sources
    first = draft(action(sources[0], "Friday"))
    first.key_points = [SupportedText(text="Cost 999 dollars.", sources=["T3"])]
    first.decisions = [SupportedText(text="Release Tuesday.", sources=["T4"])]
    first.timing_updates = [
        TimingUpdate(
            original_commitment_id="T1", evidence=[Anchor(source_id="T2", quote=sources[1].text)]
        )
    ]
    if lost == "external_timing":
        first.timing_updates = []
        first.action_items[0].timing = Anchor(source_id="T2", quote="Monday")
    if blocked_first:
        first.overview = [SupportedText(text="Bad reference.", sources=["missing"])]
    correction = first.model_copy(deep=True)
    correction.overview = []
    correction.key_points[0].text = "Cost 120 dollars."
    if lost == "action":
        correction.action_items = []
        correction.timing_updates = []
    elif lost in ("timing", "external_timing"):
        correction.action_items[0].timing = None
        correction.timing_updates = []
    else:
        correction.decisions = []
    transport = Transport(first.model_dump_json(), correction.model_dump_json())
    engine = model(transport)
    if blocked_first:
        with pytest.raises(SummaryError, match="Correction lost"):
            engine.summarize(MEETING, transcript)
        assert engine.audit.selected is None
    else:
        result = engine.summarize(MEETING, transcript)
        assert engine.audit.selected == 0
        assert result.action_items and result.decisions
        generation(engine, result)
    assert any("Correction lost" in error for error in engine.audit.attempts[1].selection_errors)


@pytest.mark.parametrize("failure", ["malformed", "transport", "context"])
def test_valid_fallback_preserves_compilation_and_roundtrips_after_correction_failure(failure: str):
    first = reply("Cost 999 dollars." + (" x" * 50000 if failure == "context" else ""))
    correction = OllamaError("offline") if failure == "transport" else "not json"
    transport = Transport(first, correction)
    engine = model(transport)
    result = engine.summarize(MEETING, "Cost 120 dollars.")
    saved = generation(engine, result)
    assert engine.audit.selected == 0
    assert Generation.model_validate_json(saved.model_dump_json()) == saved
    assert len(engine.audit.attempts) == 2
    assert len(transport.requests) == (1 if failure == "context" else 2)


def test_uncertain_commitment_and_comparison_persist_outside_checklist_without_retry(
    tmp_path: Path,
):
    transcript = "[00:00:00] Sam: I will send the invoice."
    notes = "Please review the invoice."
    comparison = Comparison(
        claims=[
            Claim(
                note=account("N1", notes),
                transcript=[],
                outcome="uncertain",
                reason="Association is unresolved.",
            )
        ]
    )
    value = draft(action(snapshot(transcript).sources[0]))
    value.action_items[0].disposition = "uncertain"
    transport = Transport(comparison.model_dump_json(), value.model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, transcript, handwritten_text=notes)
    saved = generation(engine, result)
    directory = MeetingDir(tmp_path)
    directory.save_summary(result, saved.evidence, engine.audit)
    assert directory.load_generation() == saved
    assert len(transport.requests) == 2 and not result.action_items
    assert engine.audit.attempts[0].compilation
    assert engine.audit.attempts[0].compilation.commitments[0].disposition == "uncertain"
    rendered = render_note(MEETING, result, "synthetic", warnings=engine.audit.attempts[0].warnings)
    assert "Commitment review required" in rendered and "Comparison review required" in rendered
    assert transcript.split("Sam: ")[1] in rendered and "- [ ]" not in rendered


def saved_with_spans() -> Generation:
    transcript = "[00:00:00] Sam: I will send the invoice Friday. Agreed, release Monday."
    notes = "Personal context, and written reminder.\r\n"
    comparison = Comparison(
        claims=[
            Claim(
                note=account("N1", "Personal context"),
                transcript=[],
                outcome="additional",
                reason="Written context.",
            ),
            Claim(
                note=account("N1", "written reminder."),
                transcript=[],
                outcome="additional",
                reason="Written reminder.",
            ),
        ]
    )
    value = draft(action(snapshot(transcript).sources[0], "Friday"))
    value.decisions = [SupportedText(text="Release Monday.", sources=["T2"])]
    transport = Transport(comparison.model_dump_json(), value.model_dump_json())
    engine = model(transport)
    return generation(engine, engine.summarize(MEETING, transcript, handwritten_text=notes))


@pytest.mark.parametrize(
    "artifact",
    [
        "draft",
        "comparison",
        "context",
        "snapshot",
        "sources",
        "gap",
        "relation",
        "commitment",
        "agreement",
        "warnings",
        "blocking",
        "selection_errors",
        "selected",
        "comparison_selected",
        "original",
        "effective",
        "response",
        "request",
        "schema",
        "extra_attempt",
    ],
)
def test_wrapper_10_rejects_tampered_inputs_selections_and_compilation(artifact: str):
    saved = saved_with_spans()
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    audit = data["audit"]
    attempt = audit["attempts"][0]
    compilation = attempt["compilation"]
    if artifact == "draft":
        compilation["draft"]["decisions"][0]["text"] = "Changed prose."
    elif artifact == "comparison":
        raw = json.loads(audit["comparison_attempts"][0]["reply"])
        raw["claims"][0]["reason"] = "Changed reason."
        audit["comparison_attempts"][0]["reply"] = json.dumps(raw)
        audit["comparison_attempts"][0]["response"]["message"]["content"] = json.dumps(raw)
    elif artifact == "context":
        compilation["context"] += " altered"
    elif artifact == "snapshot":
        compilation["snapshot"]["notes"] += " altered"
    elif artifact == "sources":
        compilation["snapshot"]["sources"][0]["speaker"] = "Someone else"
    elif artifact == "gap":
        audit["comparison_attempts"][0]["resolution"]["gaps"][0]["text"] = ", or "
    elif artifact == "relation":
        compilation["resolution"]["claims"][0]["outcome"] = "uncertain"
    elif artifact == "commitment":
        compilation["commitments"][0]["owner"] = "Someone else"
    elif artifact == "agreement":
        compilation["agreements"] = []
    elif artifact in ("warnings", "blocking", "selection_errors"):
        attempt[artifact].append("altered")
    elif artifact in ("selected", "comparison_selected"):
        audit[artifact] = 1
    elif artifact == "original":
        data["evidence"]["handwritten_original"] += " altered"
    elif artifact == "effective":
        data["evidence"]["handwritten_text"] += " altered"
    elif artifact == "response":
        attempt["response"]["message"]["content"] = "{}"
    elif artifact == "request":
        attempt["request"]["messages"][1]["content"] += " altered"
    elif artifact == "schema":
        attempt["request"]["format"]["$defs"]["SourceID"]["enum"].append("N1")
    else:
        audit["attempts"].append(attempt.copy())
    with pytest.raises(ValueError):
        Generation.model_validate(data)


def test_wrapper_10_keeps_full_snapshot_separators_and_spans():
    saved = saved_with_spans()
    assert isinstance(saved.audit, V11Audit)
    audit = saved.audit
    assert audit.snapshot.notes == saved.evidence.handwritten_text
    resolution = audit.comparison_attempts[0].resolution
    assert resolution and any(gap.text == ", and " for gap in resolution.gaps)
    assert resolution.claims[0].id == "N1.C1" and resolution.claims[1].id == "N1.C2"
    assert Generation.model_validate_json(saved.model_dump_json()) == saved


@pytest.mark.parametrize("location", ["elsewhere in transcript", "only in metadata"])
def test_numbers_from_another_transcript_passage_or_metadata_block_selection(location: str):
    transcript = (
        "Cost 120 dollars. Other service 500 dollars."
        if location == "elsewhere in transcript"
        else "Cost 120 dollars."
    )
    number = "500" if location == "elsewhere in transcript" else "2026"
    transport = Transport(*[reply(f"Cost {number} dollars.")] * 2)
    engine = model(transport)
    with pytest.raises(SummaryError, match=location):
        engine.summarize(MEETING, transcript)
    assert engine.audit.selected is None
    assert all(attempt.selection_errors for attempt in engine.audit.attempts)


@pytest.mark.parametrize("missing", ["action", "agreement"])
def test_omitted_independent_evidence_is_corrected_without_a_partial_result(missing: str):
    transcript = "[00:00:00] Sam: I will send the invoice. Agreed, release Monday."
    value = draft(action(snapshot(transcript).sources[0]))
    value.decisions = [SupportedText(text="Release Monday.", sources=["T2"])]
    first = value.model_copy(deep=True)
    if missing == "action":
        first.action_items = []
    else:
        first.decisions = []
    transport = Transport(first.model_dump_json(), value.model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, transcript)
    assert engine.audit.selected == 1 and result.action_items and result.decisions
    assert engine.audit.attempts[0].compilation and engine.audit.attempts[0].compilation.blocking
    generation(engine, result)


@pytest.mark.parametrize(
    "text,basis",
    [
        ("Alex will send the invoice.", "third-person"),
        ("The invoice is on me.", "implied"),
        ("I will send the invoice and check the logs.", "coordinated"),
        ("If approval arrives, I will send the invoice by Friday.", "explicit"),
    ],
)
def test_recognized_commitment_forms_reach_current_runtime(
    text: str, basis: Literal["explicit", "third-person", "implied", "coordinated"]
):
    transcript = "[00:00:00] Sam: " + text
    value = draft(action(snapshot(transcript).sources[0]))
    value.action_items[0].basis = basis
    transport = Transport(value.model_dump_json())
    engine = model(transport)
    result = engine.summarize(MEETING, transcript)
    assert len(transport.requests) == 1 and len(result.action_items) == 1
    assert result.action_items[0].task == text
    generation(engine, result)


@pytest.mark.parametrize("first_comparison", ["bad comparison", '{"claims":[]}'])
def test_wrapper_10_recomputes_both_corrected_stages_and_invalid_findings(first_comparison: str):
    template = saved_with_spans()
    assert isinstance(template.audit, V11Audit)
    transport = Transport(
        first_comparison,
        template.audit.comparison_attempts[0].reply or "",
        "bad draft",
        template.audit.attempts[0].reply or "",
    )
    engine = model(transport)
    result = engine.summarize(
        MEETING, template.evidence.transcript, handwritten_text=template.evidence.handwritten_text
    )
    saved = generation(engine, result)
    assert len(transport.requests) == 4
    assert engine.audit.selected == engine.audit.comparison_selected == 1
    assert Generation.model_validate_json(saved.model_dump_json()) == saved


@pytest.mark.parametrize(
    "artifact", ["correction_history", "selection_errors", "remove_correction"]
)
def test_replay_rejects_tampering_with_failed_corrections_and_fallback(artifact: str):
    transport = Transport(reply("Cost 999 dollars."), "not json")
    engine = model(transport)
    saved = generation(engine, engine.summarize(MEETING, "Cost 120 dollars."))
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    attempts = data["audit"]["attempts"]
    if artifact == "correction_history":
        attempts[1]["request"]["messages"][3]["content"] = "Forget earlier issues."
    elif artifact == "selection_errors":
        attempts[1]["selection_errors"] = ["invented finding"]
    else:
        attempts.pop()
    with pytest.raises(ValueError):
        Generation.model_validate(data)


def test_v11_replay_needs_no_original_files_or_inference(monkeypatch: pytest.MonkeyPatch):
    import socket

    saved = saved_with_spans()
    serialized = saved.model_dump_json()

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Replay must use only saved inputs")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(OllamaSummarizer, "summarize", forbidden)
    assert Generation.model_validate_json(serialized) == saved


def protocol_generation(
    *,
    notes: bool = False,
    comparison_first: str | None = None,
    summary_first: str | None = None,
    summary_last: str | dict[str, Any] | Exception | None = None,
) -> Generation:
    responses: list[str | dict[str, Any] | Exception] = []
    if notes:
        if comparison_first is not None:
            responses.append(comparison_first)
        responses.append(additional("Written café context."))
    if summary_first is not None:
        responses.append(summary_first)
    responses.append(reply("Cost 120 dollars.") if summary_last is None else summary_last)
    engine = model(Transport(*responses))
    return generation(
        engine,
        engine.summarize(
            MEETING,
            "Cost 120 dollars.",
            handwritten_text="Written café context." if notes else "",
        ),
    )


def protocol_attempts(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [*data["audit"]["comparison_attempts"], *data["audit"]["attempts"]]


def body_tokens(body: dict[str, Any]) -> int:
    # Pin the established accounting, independently of the shared runtime/replay helper.
    return (len(json.dumps(body, ensure_ascii=False)) + 2) // 3 + 4096


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize("corrections", [False, True])
def test_replay_accepts_exact_full_body_budget_and_rejects_one_token_under(
    notes: bool, corrections: bool
):
    saved = protocol_generation(
        notes=notes,
        comparison_first="bad comparison" if corrections else None,
        summary_first="bad draft" if corrections else None,
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    attempts = protocol_attempts(data)
    # Account for the decimal context setting's own serialized size too.
    context = 32768
    for _ in range(3):
        context = max(body_tokens(a["request"]) for a in attempts)
        for attempt in attempts:
            attempt["request"]["options"]["num_ctx"] = context
    assert max(body_tokens(a["request"]) for a in attempts) == context
    assert Generation.model_validate_json(Generation.model_validate(data).model_dump_json())
    for attempt in attempts:
        attempt["request"]["options"]["num_ctx"] = context - 1
    with pytest.raises(ValueError, match="Oversized request"):
        Generation.model_validate(data)


@pytest.mark.parametrize(
    "stage,index,notes",
    [
        ("summary", 0, False),
        ("summary", 0, True),
        ("summary", 1, False),
        ("summary", 1, True),
        ("comparison", 0, True),
        ("comparison", 1, True),
    ],
)
def test_replay_checks_budget_on_each_sent_stage_and_attempt(stage: str, index: int, notes: bool):
    saved = protocol_generation(
        notes=notes,
        comparison_first="bad " * 4000 if stage == "comparison" and index else None,
        summary_first=reply("Cost 999 dollars." + " x" * 8000)
        if stage == "summary" and index
        else None,
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    attempts = protocol_attempts(data)
    stage_attempts = data["audit"]["comparison_attempts" if stage == "comparison" else "attempts"]
    target = stage_attempts[index]
    if index:
        first_size = body_tokens(stage_attempts[0]["request"])
        context = (first_size + body_tokens(target["request"])) // 2
    elif stage == "summary" and notes:
        comparison_size = max(
            body_tokens(a["request"]) for a in data["audit"]["comparison_attempts"]
        )
        context = (comparison_size + body_tokens(target["request"])) // 2
    else:
        context = 1
    for attempt in attempts:
        attempt["request"]["options"]["num_ctx"] = context
    assert body_tokens(target["request"]) > context
    if index:
        assert body_tokens(stage_attempts[0]["request"]) <= context
    if stage == "summary":
        assert all(
            body_tokens(a["request"]) <= context for a in data["audit"]["comparison_attempts"]
        )
    with pytest.raises(ValueError, match="Oversized request"):
        Generation.model_validate(data)


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [
        ("num_ctx", "32768"),
        ("num_ctx", True),
        ("num_ctx", 32768.0),
        ("num_ctx", None),
        ("num_ctx", 0),
        ("num_ctx", -1),
        ("options", []),
        ("options", None),
        ("temperature", True),
        ("temperature", "0"),
        ("temperature", 1),
        ("think", "true"),
        ("think", 1),
        ("stream", 0),
        ("stream", True),
        ("model", 1),
    ],
)
def test_replay_rejects_malformed_settings_even_when_all_attempts_agree(
    notes: bool, field: str, value: Any
):
    data: dict[str, Any] = json.loads(protocol_generation(notes=notes).model_dump_json())
    for attempt in protocol_attempts(data):
        if field in ("num_ctx", "temperature"):
            attempt["request"]["options"][field] = value
        else:
            attempt["request"][field] = value
    with pytest.raises(ValueError, match="Request"):
        Generation.model_validate(data)


@pytest.mark.parametrize("context", [True, 32768.0, "32768", None, 0, -1])
def test_runtime_rejects_malformed_context_before_transport(context: Any):
    transport = Transport(reply())
    engine = model(transport, context=context)
    with pytest.raises(OllamaError, match="positive integer"):
        engine.summarize(MEETING, "The plan was discussed.")
    assert not transport.requests and engine.audit.attempts[0].response is None


@pytest.mark.parametrize(
    "stage,index,notes",
    [
        ("summary", 0, False),
        ("summary", 0, True),
        ("summary", 1, False),
        ("summary", 1, True),
        ("comparison", 0, True),
        ("comparison", 1, True),
    ],
)
def test_replay_rejects_truncated_responses_masquerading_as_complete(
    stage: str, index: int, notes: bool
):
    saved = protocol_generation(
        notes=notes,
        comparison_first="bad comparison" if stage == "comparison" and index else None,
        summary_first="bad draft" if stage == "summary" and index else None,
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    attempts = data["audit"]["comparison_attempts" if stage == "comparison" else "attempts"]
    attempts[index]["response"]["done_reason"] = "length"
    with pytest.raises(ValueError, match="response error differs"):
        Generation.model_validate(data)


FAILED_RESPONSES: list[dict[str, Any] | Exception] = [
    {"message": {"content": reply()}, "done_reason": "length"},
    {"done_reason": "length"},
    {"error": "missing message"},
    {"message": {}},
    {"message": None},
    {"message": []},
    OllamaError("offline"),
    OllamaError(""),
]


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize("response", FAILED_RESPONSES)
def test_failed_summary_correction_keeps_valid_fallback_and_replays_its_raw_failure(
    notes: bool, response: dict[str, Any] | Exception
):
    saved = protocol_generation(
        notes=notes, summary_first=reply("Cost 999 dollars."), summary_last=response
    )
    assert isinstance(saved.audit, V11Audit)
    audit = saved.audit
    failed = audit.attempts[1]
    assert audit.selected == 0 and saved.summary.overview == "Cost 999 dollars."
    assert failed.error is not None and failed.compilation is None
    assert not failed.blocking and not failed.warnings
    assert Generation.model_validate_json(saved.model_dump_json()) == saved


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("response", FAILED_RESPONSES)
def test_comparison_response_failure_never_advances_to_summary_or_replays_as_success(
    index: int, response: dict[str, Any] | Exception
):
    responses: list[str | dict[str, Any] | Exception] = ["bad comparison"] if index else []
    responses.append(response)
    transport = Transport(*responses)
    engine = model(transport)
    with pytest.raises(SummaryError):
        engine.summarize(MEETING, "Cost 120 dollars.", handwritten_text="Written café context.")
    assert len(transport.requests) == index + 1
    assert not engine.audit.attempts and engine.audit.comparison_selected is None
    data: dict[str, Any] = json.loads(protocol_generation(notes=True).model_dump_json())
    data["audit"]["comparison_attempts"] = [
        a.model_dump() for a in engine.audit.comparison_attempts
    ]
    with pytest.raises(ValueError, match="Comparison failed before summary"):
        Generation.model_validate(data)


@pytest.mark.parametrize("notes", [False, True])
def test_oversized_summary_correction_is_unsent_and_preserves_valid_fallback(notes: bool):
    saved = protocol_generation(
        notes=notes, summary_first=reply("Cost 999 dollars." + " x" * 50000)
    )
    assert isinstance(saved.audit, V11Audit)
    failed = saved.audit.attempts[1]
    assert failed.error == "Complete request exceeds context; not sent"
    assert body_tokens(failed.request) > failed.request["options"]["num_ctx"]
    assert failed.response is None and failed.reply is None and failed.compilation is None
    assert saved.audit.selected == 0
    assert Generation.model_validate_json(saved.model_dump_json()) == saved


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize("artifact", ["response", "reply", "compilation"])
def test_unsent_oversized_correction_cannot_have_response_reply_or_compilation(
    notes: bool, artifact: str
):
    saved = protocol_generation(
        notes=notes, summary_first=reply("Cost 999 dollars." + " x" * 50000)
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    failed = data["audit"]["attempts"][1]
    if artifact == "response":
        failed["response"] = {"error": "missing message"}
    elif artifact == "reply":
        failed["reply"] = "not json"
    else:
        failed["compilation"] = data["audit"]["attempts"][0]["compilation"]
    with pytest.raises(ValueError):
        Generation.model_validate(data)


@pytest.mark.parametrize("notes", [False, True])
def test_falsely_claimed_unsent_size_failure_cannot_hide_a_fitting_correction(notes: bool):
    saved = protocol_generation(
        notes=notes, summary_first=reply("Cost 999 dollars."), summary_last=OllamaError("offline")
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    failed = data["audit"]["attempts"][1]
    assert body_tokens(failed["request"]) < failed["request"]["options"]["num_ctx"]
    failed["error"] = "Complete request exceeds context; not sent"
    with pytest.raises(ValueError, match="request that fits"):
        Generation.model_validate(data)


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize(
    "error", ["offline", "Model ran out of context", "Ollama reply had no message", ""]
)
def test_complete_raw_response_cannot_be_hidden_as_a_failed_correction(notes: bool, error: str):
    saved = protocol_generation(
        notes=notes, summary_first=reply("Cost 999 dollars."), summary_last=OllamaError("offline")
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    failed = data["audit"]["attempts"][1]
    failed["response"] = {"message": {"content": reply("Cost 120 dollars.")}}
    failed["reply"] = failed["response"]["message"]["content"]
    failed["error"] = error
    with pytest.raises(ValueError, match="response error differs"):
        Generation.model_validate(data)


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize(
    "artifact", ["missing_response", "missing_error", "wrong_error", "wrong_reply"]
)
def test_failed_response_requires_exact_raw_reply_and_error_bindings(notes: bool, artifact: str):
    saved = protocol_generation(
        notes=notes,
        summary_first=reply("Cost 999 dollars."),
        summary_last={"message": {"content": reply()}, "done_reason": "length"},
    )
    data: dict[str, Any] = json.loads(saved.model_dump_json())
    failed = data["audit"]["attempts"][1]
    if artifact == "missing_response":
        failed["response"] = None
    elif artifact == "missing_error":
        failed["error"] = None
    elif artifact == "wrong_error":
        failed["error"] = "offline"
    else:
        failed["reply"] = "changed reply"
    with pytest.raises(ValueError):
        Generation.model_validate(data)
