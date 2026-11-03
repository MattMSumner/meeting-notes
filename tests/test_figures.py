import pytest

from meeting_notes.figures import numbers, unsaid_numbers, verify_details
from meeting_notes.summary import ActionItem, Detail, Summary, SummaryError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$120,000 total", [("$120,000", 120000)]),
        ("about 120k", [("120k", 120000)]),
        ("1.5 million", [("1.5 million", 1500000)]),
        ("$80-90k", [("$80", 80), ("90k", 90000)]),
        ("a hundred and twenty thousand", [("a hundred and twenty thousand", 120000)]),
        ("eighty to ninety thousand", [("eighty", 80), ("ninety thousand", 90000)]),
        ("twenty-five people", [("twenty-five", 25)]),
        ("a hundred plus", [("a hundred", 100)]),
        ("the forty, seventy", [("forty", 40), ("seventy", 70)]),
        ("five six", [("five", 5), ("six", 6)]),
        ("[00:00:30] Sam: hi", []),
        ("and a few more", []),
    ],
)
def test_finds_numbers_in_digits_and_words(text: str, expected: list[tuple[str, float]]):
    assert list(numbers(text)) == expected


def summary(*key_points: str, due: str | None = None) -> Summary:
    return Summary(
        overview="Talked about pricing.",
        key_points=list(key_points),
        decisions=[],
        action_items=[ActionItem(owner="Sam", task="Send the quote", due=due)],
    )


SAID = """[00:00:15] Sam: All in, I'm thinking about a hundred and twenty thousand.
[00:00:24] Sam: The build itself, eighty to ninety thousand is what I'm aiming for.
[00:00:33] Them: Seventy for the build is definitely doable."""


def test_numbers_said_in_words_or_digits_are_not_flagged():
    assert (
        unsaid_numbers(summary("$120,000 total, $80,000-$90,000 build, $70k doable."), SAID) == []
    )
    assert unsaid_numbers(summary("$120K total, $80-90K build."), SAID) == []


def test_flags_a_number_worked_out_from_the_ones_said():
    assert unsaid_numbers(summary("$120,000 total: $90,000 build and $30,000 support."), SAID) == [
        "$30,000"
    ]
    assert unsaid_numbers(summary("$80-90k build and $30-40k support."), SAID) == ["$30", "40k"]


def test_timestamps_are_not_something_anyone_said():
    # 30 and 33 appear only in the timestamps.
    assert unsaid_numbers(summary("$33,000 for support."), SAID) == ["$33,000"]


def test_checks_action_items_and_ignores_small_counts():
    assert unsaid_numbers(summary("Two options came up.", due="October 24"), SAID) == ["24"]


def test_checks_numbers_in_detail_subjects_and_quotes():
    result = summary()
    result.details = [Detail(speaker="Sam", subject="$30,000 retainer", quote="Thirty thousand.")]

    assert unsaid_numbers(result, SAID) == ["$30,000", "Thirty thousand"]


def test_source_times_are_metadata_not_spoken_numbers():
    result = summary()
    result.details = [Detail(speaker="Them", start=33, quote="Seventy is doable.")]

    assert unsaid_numbers(result, SAID) == []


@pytest.mark.parametrize(
    ("start", "quote"),
    [(15, "Seventy for the build is definitely doable."), (33, "Seventy for the build")],
)
def test_timestamped_details_must_copy_the_whole_turn_at_that_time(start: float, quote: str):
    with pytest.raises(SummaryError, match="details.0.quote"):
        verify_details([Detail(speaker="Them", start=start, quote=quote)], SAID)


def test_verifies_quotes_with_only_whitespace_normalized():
    quote = Detail(
        speaker="Them",
        subject="Build budget",
        quote="Seventy for\n the build is definitely doable.",
    )

    verify_details([quote], SAID)
    assert quote.quote == "Seventy for\n the build is definitely doable."
    verify_details([], SAID)


@pytest.mark.parametrize(
    ("speaker", "quote"),
    [
        ("Sam", "Seventy for the build is definitely doable."),
        ("Nadia", "Seventy for the build is definitely doable."),
        ("them", "Seventy for the build is definitely doable."),
        ("Them", "$70k for the build is definitely doable."),
        ("Them", "Seventy for the build is the maximum."),
        ("Them", "seventy for the build is definitely doable."),
        ("Them", "Seventy for the build is definitely doable!"),
        ("Sam", "a hundred and twenty thousand. The build itself"),
        ("Sam", "eighty to ninety thousand is what I'm aiming for. Seventy"),
        ("Sam", "All in, … a hundred and twenty thousand."),
        ("Sam", "120k budget"),
    ],
)
def test_rejects_quotes_without_a_verbatim_match_in_one_turn(speaker: str, quote: str):
    with pytest.raises(SummaryError, match="details.0.quote"):
        verify_details([Detail(speaker=speaker, subject="Price", quote=quote)], SAID)
