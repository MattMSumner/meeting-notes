import pytest

from meeting_notes.summary import (
    Detail,
    Details,
    Narrative,
    Summary,
    SummaryError,
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
    assert parse_response('{"details": []}', Details).details == []
    with pytest.raises(SummaryError, match="details: Field required"):
        parse_response("{}", Details)


@pytest.mark.parametrize("field", ["speaker", "subject", "quote"])
@pytest.mark.parametrize("value", ["", " \n "])
def test_detail_fields_cannot_be_blank(field: str, value: str):
    fields = {"speaker": "Sam", "subject": "Build", "quote": "Seventy is doable."}
    fields[field] = value
    with pytest.raises(ValueError, match=field):
        Detail.model_validate(fields)


def test_response_schemas_do_not_allow_extra_fields():
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response('{"details": [], "overview": "Invented."}', Details)
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response(VALID.replace('"overview":', '"details": [], "overview":'), Narrative)
    with pytest.raises(SummaryError, match="Extra inputs"):
        parse_response('{"speaker":"Sam","subject":"Cost","quote":"Seventy.","value":70}', Detail)


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
