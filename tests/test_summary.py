import pytest

from meeting_notes.summary import (
    Commitments,
    Detail,
    ExtractedAction,
    Overview,
    Summary,
    SummaryError,
    TurnSelection,
    parse_response,
    parse_summary,
)

VALID = """{
  "overview": "Planned the release.",
  "key_points": ["Tests pass."],
  "decisions": [],
  "action_items": [{"owner": "Me", "task": "Tag it", "due": null}]
}"""


def test_parses_a_valid_reply():
    summary = parse_summary(VALID)

    assert summary.overview == "Planned the release."
    assert summary.action_items[0].owner == "Me"
    assert summary.action_items[0].due is None
    assert summary.details == []


def test_extraction_requires_an_explicit_list_even_when_empty():
    assert parse_response('{"turn_ids": []}', TurnSelection).turn_ids == []
    with pytest.raises(SummaryError, match="turn_ids: Field required"):
        parse_response("{}", TurnSelection)


@pytest.mark.parametrize("field", ["speaker", "subject", "quote"])
@pytest.mark.parametrize("value", ["", " \n "])
def test_detail_fields_cannot_be_blank(field: str, value: str):
    fields = {"speaker": "Sam", "subject": "Build", "quote": "Seventy is doable."}
    fields[field] = value
    with pytest.raises(ValueError, match=field):
        Detail.model_validate(fields)


def test_response_schemas_do_not_allow_extra_fields():
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response('{"turn_ids": [], "overview": "Invented."}', TurnSelection)
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response(VALID, Overview)
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response('{"speaker":"Sam","subject":"Cost","quote":"Seventy.","value":70}', Detail)


def test_commitments_require_both_lists_even_when_empty():
    assert parse_response('{"decisions": [], "action_items": []}', Commitments).decisions == []
    for field in ("decisions", "action_items"):
        with pytest.raises(SummaryError, match="Field required"):
            parse_response('{"' + field + '": []}', Commitments)


@pytest.mark.parametrize(
    "item",
    [
        '{"text":"Ship.","turn_ids":[]}',
        '{"text":"Ship."}',
        '{"text":" ","turn_ids":["t1"]}',
        '{"text":"Ship.","turn_ids":[1]}',
        '{"text":"Ship.","turn_ids":[""]}',
    ],
)
def test_decisions_need_text_and_source_references(item: str):
    with pytest.raises(SummaryError):
        parse_response('{"decisions":[' + item + '],"action_items":[]}', Commitments)


@pytest.fixture
def action_data() -> dict[str, object]:
    return {
        "kind": "promise",
        "commitment_turn_ids": ["t1"],
        "request_turn_ids": [],
        "context_turn_ids": [],
        "related_timing": [],
        "action_timing": None,
        "owner": None,
        "task": "Check it",
    }


@pytest.mark.parametrize("field", ["owner", "task"])
def test_action_fields_are_required_and_cannot_be_blank(field: str, action_data: dict[str, object]):
    assert ExtractedAction.model_validate(action_data).owner is None
    action_data[field] = " "
    with pytest.raises(ValueError, match=field):
        ExtractedAction.model_validate(action_data)
    del action_data[field]
    with pytest.raises(ValueError, match=field):
        ExtractedAction.model_validate(action_data)


@pytest.mark.parametrize("field", list(ExtractedAction.model_fields))
def test_actions_require_every_evidence_field(field: str, action_data: dict[str, object]):
    del action_data[field]
    with pytest.raises(ValueError, match=field):
        ExtractedAction.model_validate(action_data)


@pytest.mark.parametrize("ids", [[], [" "], [1]])
def test_actions_need_nonblank_commitment_references(ids: object, action_data: dict[str, object]):
    action_data["commitment_turn_ids"] = ids
    with pytest.raises(ValueError, match="commitment_turn_ids"):
        ExtractedAction.model_validate(action_data)


def test_accepted_requests_require_the_request(action_data: dict[str, object]):
    action_data["kind"] = "accepted_request"
    with pytest.raises(ValueError, match="needs request_turn_ids"):
        ExtractedAction.model_validate(action_data)
    action_data["request_turn_ids"] = ["t2"]
    assert ExtractedAction.model_validate(action_data).request_turn_ids == ["t2"]


@pytest.mark.parametrize("kind", ["promise", "reported_commitment"])
def test_other_commitments_do_not_claim_request_evidence(kind: str, action_data: dict[str, object]):
    action_data.update(kind=kind, request_turn_ids=["t2"])
    with pytest.raises(ValueError, match="must have kind accepted_request"):
        ExtractedAction.model_validate(action_data)


@pytest.mark.parametrize("field", ["turn_id", "quote", "value"])
def test_timing_fields_are_required_and_nonblank(field: str, action_data: dict[str, object]):
    timing = {"turn_id": "t1", "quote": "I'll do it by Friday.", "value": "by Friday"}
    action_data["action_timing"] = timing
    timing[field] = " "
    with pytest.raises(ValueError, match=field):
        ExtractedAction.model_validate(action_data)
    del timing[field]
    with pytest.raises(ValueError, match=field):
        ExtractedAction.model_validate(action_data)


@pytest.mark.parametrize("start", [-1, float("inf"), float("nan")])
def test_source_times_must_be_finite_and_nonnegative(start: float):
    with pytest.raises(ValueError, match="start"):
        Detail(speaker="Sam", quote="Seventy is doable.", start=start)


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("Sure! Here are the notes:", "Invalid JSON"),
        ('{"overview": "x", "key_points": [], "decisions": []}', "action_items: Field required"),
        (VALID.replace('"Tag it"', "42"), "action_items.0.task"),
    ],
)
def test_explains_what_was_wrong_with_a_bad_reply(reply: str, reason: str):
    with pytest.raises(SummaryError, match=reason):
        parse_summary(reply)


def test_the_schema_sent_to_the_model_never_suggests_me_as_an_owner():
    # The prompt says to use my name; a schema saying "Me" contradicted it.
    assert (
        '"Me"'
        not in Summary.model_json_schema()["$defs"]["ActionItem"]["properties"]["owner"][
            "description"
        ]
    )
