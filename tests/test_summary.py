import pytest

from meeting_notes.summary import (
    Commitments,
    Detail,
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


@pytest.mark.parametrize("field", ["owner", "task", "due"])
def test_action_fields_are_required_and_cannot_be_blank(field: str):
    data = {
        "decisions": [],
        "action_items": [{"owner": None, "task": "Check it", "due": None, "turn_ids": ["t1"]}],
    }
    assert Commitments.model_validate(data).action_items[0].owner is None
    data["action_items"][0][field] = " "
    with pytest.raises(ValueError, match=field):
        Commitments.model_validate(data)
    del data["action_items"][0][field]
    with pytest.raises(ValueError, match=field):
        Commitments.model_validate(data)


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
