import pytest

from meeting_notes.summary import Detail, SummaryError
from meeting_notes.turns import parse_turns, selected_details


def test_selecting_a_turn_keeps_every_claim_and_qualification():
    text = "Forty is too low. A hundred is probably too much. Seventy is definitely doable."
    turns = parse_turns(f"[00:00:33] Them: {text}")

    assert selected_details(["t1"], turns) == [Detail(speaker="Them", start=33, quote=text)]


def test_equal_timestamps_have_distinct_ids_and_source_attribution():
    turns = parse_turns("[00:00:00] Sam: I am out Monday.\n[00:00:00] Them: I return Tuesday.")

    details = selected_details(["t2", "t1", "t2"], turns)

    assert [(turn.id, turn.start) for turn in turns] == [("t1", 0), ("t2", 0)]
    assert [(detail.speaker, detail.quote) for detail in details] == [
        ("Sam", "I am out Monday."),
        ("Them", "I return Tuesday."),
    ]


def test_selection_uses_source_order_rather_than_lexical_id_order():
    turns = parse_turns("\n".join(f"[00:00:{i:02}] Sam: Point {i}." for i in range(11)))

    assert [detail.quote for detail in selected_details(["t10", "t2", "t10"], turns)] == [
        "Point 1.",
        "Point 9.",
    ]


def test_multiline_and_long_turns_are_never_split_or_shortened():
    text = "The estimate is  about seventy.\n\nProbably\tfeasible,\u2028not agreed. " * 100
    turns = parse_turns(f"[01:02:03] Sam: {text}\n[01:05:00] Them: Thanks.\n")

    [detail] = selected_details(["t1"], turns)

    assert detail.quote == text
    assert detail.start == 3723


@pytest.mark.parametrize(
    "text",
    [
        "Unlabelled speech.",
        "Meeting: title\n[00:00:00] Sam: Hello.",
        "[00:00:00] Sam: Hello.\n[00:61:00] Them: Bad timestamp.",
        "[00:00:00] Sam: Hello.\n[00:00:01] Missing speaker.",
        "[00:00:00]  : Hello.",
        "[00:00:00] Sam: ",
    ],
)
def test_malformed_input_is_not_silently_dropped(text: str):
    with pytest.raises(SummaryError, match="Couldn't read transcript turns"):
        parse_turns(text)


def test_empty_input_and_empty_selection_are_valid():
    assert parse_turns(" \n ") == []
    assert selected_details([], []) == []
    assert selected_details([], parse_turns("[00:00:00] Sam: Hello.")) == []


def test_unknown_ids_are_not_silently_ignored():
    with pytest.raises(SummaryError, match="Unknown turn IDs: t0, t99"):
        selected_details(["t1", "t99", "t0"], parse_turns("[00:00:00] Sam: Hello."))
