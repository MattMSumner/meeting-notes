from collections import Counter

import pytest

from meeting_notes.merge import Aside, Line, SpeakerTrack, merge
from meeting_notes.transcript import Segment


def seg(start: float, text: str) -> Segment:
    return Segment(start, start + 1.0, text)


def test_interleaves_speakers_by_start_time():
    me = SpeakerTrack("Me", 0.0, [seg(0.0, "Hi."), seg(10.0, "Sounds good.")])
    them = SpeakerTrack("Them", 0.0, [seg(4.0, "Hey, ready?")])

    assert merge([me, them]) == [
        Line(0.0, "Me", "Hi."),
        Line(4.0, "Them", "Hey, ready?"),
        Line(10.0, "Me", "Sounds good."),
    ]


def test_applies_each_channels_offset():
    # "Them" started recording 2.5 s after "Me", so its file times are 2.5 s behind.
    me = SpeakerTrack("Me", 0.0, [seg(3.0, "Second.")])
    them = SpeakerTrack("Them", 2.5, [seg(0.0, "First.")])

    assert merge([me, them]) == [Line(2.5, "Them", "First."), Line(3.0, "Me", "Second.")]


def test_joins_consecutive_segments_from_the_same_speaker():
    me = SpeakerTrack("Me", 0.0, [seg(0.0, "One."), seg(2.0, "Two.")])
    them = SpeakerTrack("Them", 0.0, [seg(5.0, "Three.")])

    assert merge([me, them]) == [Line(0.0, "Me", "One. Two."), Line(5.0, "Them", "Three.")]


def test_overlapping_speech_is_ordered_by_who_started_first():
    me = SpeakerTrack("Me", 0.0, [Segment(1.0, 6.0, "Long point.")])
    them = SpeakerTrack("Them", 0.0, [Segment(2.0, 3.0, "Interrupting!")])

    assert [line.speaker for line in merge([me, them])] == ["Me", "Them"]


def test_ties_go_to_the_first_track():
    me = SpeakerTrack("Me", 0.0, [seg(1.0, "Me too.")])
    them = SpeakerTrack("Them", 0.0, [seg(1.0, "Same time.")])

    assert [line.speaker for line in merge([me, them])] == ["Me", "Them"]
    assert [line.speaker for line in merge([them, me])] == ["Them", "Me"]


def test_empty_channels():
    assert merge([]) == []
    assert merge([SpeakerTrack("Me", 0.0, []), SpeakerTrack("Them", 0.0, [])]) == []
    only_them = merge(
        [SpeakerTrack("Me", 0.0, []), SpeakerTrack("Them", 1.0, [seg(0.0, "Hello?")])]
    )
    assert only_them == [Line(1.0, "Them", "Hello?")]


def test_splits_a_long_turn_into_paragraphs_at_a_sentence_end():
    me = SpeakerTrack(
        "Me",
        0.0,
        # Not at 20 s (too soon) or 31 s (mid-sentence): at 40 s, after "done."
        [
            seg(0.0, "First point."),
            seg(20.0, "Still on it,"),
            seg(31.0, "done."),
            seg(40.0, "Next."),
        ],
    )

    assert merge([me]) == [
        Line(0.0, "Me", "First point. Still on it, done."),
        Line(40.0, "Me", "Next."),
    ]


def test_splits_unpunctuated_speech_at_the_next_pause_after_a_minute():
    me = SpeakerTrack("Me", 0.0, [seg(0.0, "so the thing"), seg(45.0, "is that"), seg(61.0, "we")])

    assert merge([me]) == [Line(0.0, "Me", "so the thing is that"), Line(61.0, "Me", "we")]


def test_short_turns_stay_one_paragraph():
    me = SpeakerTrack("Me", 0.0, [seg(0.0, "One."), seg(29.0, "Two.")])

    assert merge([me]) == [Line(0.0, "Me", "One. Two.")]


def test_a_sentence_end_can_be_followed_by_a_closing_quote_or_an_ellipsis():
    for ending in ('he said "done."', "right?)", "and then\u2026"):
        me = SpeakerTrack("Me", 0.0, [seg(0.0, "Start."), seg(20.0, ending), seg(31.0, "Next.")])

        assert len(merge([me])) == 2, ending


def test_a_long_segment_starts_a_new_paragraph_rather_than_run_past_a_minute():
    me = SpeakerTrack("Me", 0.0, [seg(0.0, "so"), Segment(50.0, 90.0, "and a long stretch")])

    assert [line.start for line in merge([me])] == [0.0, 50.0]


@pytest.mark.parametrize(("speaker", "listener"), [("Me", "Them"), ("Them", "Me")])
def test_folds_an_overlapping_acknowledgment_after_its_segment(speaker: str, listener: str):
    tracks = [
        SpeakerTrack(speaker, 0.0, [Segment(0.0, 5.0, "First."), seg(6.0, "Next.")]),
        SpeakerTrack(listener, 0.0, [seg(2.0, "Yeah.")]),
    ]

    assert merge(tracks, fold_backchannels=True) == [
        Line(0.0, speaker, "First. Next.", (Aside(6, 2.0, listener, "Yeah."),))
    ]
    assert merge(tracks) == [
        Line(0.0, speaker, "First."),
        Line(2.0, listener, "Yeah."),
        Line(6.0, speaker, "Next."),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Yeah.",
        "YEP!",
        "yup",
        "Yes.",
        "OK",
        "Okay.",
        "Right.",
        "Uh-huh.",
        "MM–HMM.",
        "mhm",
        "  uh   huh  ",
        "Yeah, yeah, yeah.",
        "Yep. Okay!",
    ],
)
def test_recognizes_acknowledgments_without_changing_their_text(text: str):
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "The tests passed.")]),
        SpeakerTrack("Them", 0.0, [seg(1.0, text)]),
    ]

    [line] = merge(tracks, fold_backchannels=True)

    assert line.asides == (Aside(len(line.text), 1.0, "Them", text),)


@pytest.mark.parametrize(
    "text",
    [
        "Yeah?",
        "Yeah. I disagree.",
        "No.",
        "Wait!",
        "Sure.",
        "huh",
        "hmm",
        "",
        "...",
        "Yeah yeah yeah yeah.",
        "Uh-huh, mm-hmm.",
        "Yeah 2.",
        "Okay, maybe.",
    ],
)
def test_keeps_questions_and_substantive_or_long_responses_separate(text: str):
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "The tests passed.")]),
        SpeakerTrack("Them", 0.0, [seg(1.0, text)]),
    ]

    assert merge(tracks, fold_backchannels=True) == merge(tracks)


@pytest.mark.parametrize(
    ("start", "end", "folds"),
    [
        (1.0, 3.0, True),
        (1.0, 3.001, False),
        (3.0, 5.0, True),
        (3.0, 5.001, False),
        (0.0, 1.0, False),
        (5.0, 6.0, False),
        (6.0, 7.0, False),
    ],
)
def test_requires_a_short_run_entirely_inside_the_other_segment(
    start: float, end: float, folds: bool
):
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "The tests passed.")]),
        SpeakerTrack("Them", 0.0, [Segment(start, end, "Yeah.")]),
    ]

    assert len(merge(tracks, fold_backchannels=True)) == (1 if folds else 2)


def test_checks_overlap_and_timestamps_after_applying_channel_offsets():
    me = SpeakerTrack("Me", 10.0, [Segment(0.0, 5.0, "First."), seg(6.0, "Next.")])
    them = SpeakerTrack("Them", 11.5, [seg(0.0, "Yeah.")])

    assert merge([me, them], fold_backchannels=True) == [
        Line(10.0, "Me", "First. Next.", (Aside(6, 11.5, "Them", "Yeah."),))
    ]
    # These overlap in file time but not in recording time.
    them = SpeakerTrack("Them", 20.0, [seg(1.0, "Yeah.")])
    assert merge([me, them], fold_backchannels=True) == merge([me, them])


@pytest.mark.parametrize("host", ["Can we ship?", "Can we ship? Let's see.", "Okay.", "Yeah " * 4])
def test_does_not_fold_into_a_question_or_another_acknowledgment(host: str):
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, host)]),
        SpeakerTrack("Them", 0.0, [seg(1.0, "Yeah.")]),
    ]

    assert merge(tracks, fold_backchannels=True) == merge(tracks)


def test_folds_a_complete_run_of_repeated_acknowledgments():
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "First.")]),
        SpeakerTrack("Them", 0.0, [seg(1.0, "Yeah."), seg(2.0, "Okay.")]),
    ]

    assert merge(tracks, fold_backchannels=True) == [
        Line(0.0, "Me", "First.", (Aside(6, 1.0, "Them", "Yeah. Okay."),))
    ]


@pytest.mark.parametrize(
    "response",
    [
        [seg(1.0, "Yeah."), seg(2.0, "I disagree.")],
        [seg(1.0, "Yeah."), seg(3.0, "Okay.")],
        [Segment(1.0, 3.5, "Yeah."), seg(1.5, "Okay.")],
        [seg(1.0, "Yeah, yeah."), seg(2.0, "Okay, okay.")],
        [seg(4.0, "Yeah."), seg(5.0, "Okay.")],
    ],
)
def test_does_not_extract_a_backchannel_from_a_larger_run(response: list[Segment]):
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "First.")]),
        SpeakerTrack("Them", 0.0, response),
    ]

    assert merge(tracks, fold_backchannels=True) == merge(tracks)


def test_only_the_immediately_preceding_segment_can_host_an_aside():
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 10.0, "Long."), seg(2.0, "Short.")]),
        SpeakerTrack("Them", 0.0, [seg(4.0, "Yeah.")]),
    ]

    assert merge(tracks, fold_backchannels=True) == merge(tracks)


def test_an_aside_does_not_become_the_host_of_another_aside():
    tracks = [
        SpeakerTrack("Me", 0.0, [Segment(0.0, 5.0, "First."), Segment(2.0, 2.5, "Okay.")]),
        SpeakerTrack("Them", 0.0, [Segment(1.0, 3.0, "Yeah.")]),
    ]

    assert merge(tracks, fold_backchannels=True) == [
        Line(0.0, "Me", "First. Okay.", (Aside(6, 1.0, "Them", "Yeah."),))
    ]


@pytest.mark.parametrize("sentence_end", [".", ","])
def test_paragraph_breaks_depend_on_main_speech_not_asides(sentence_end: str):
    tracks = [
        SpeakerTrack(
            "Me",
            0.0,
            [
                Segment(0.0, 5.0, "First."),
                Segment(20.0, 25.0, f"Second{sentence_end}"),
                seg(35.0, "Third."),
                seg(61.0, "Fourth."),
            ],
        ),
        SpeakerTrack("Them", 0.0, [seg(1.0, "Yeah."), seg(21.0, "Okay.")]),
    ]

    lines = merge(tracks, fold_backchannels=True)

    assert [line.start for line in lines] == ([0.0, 35.0] if sentence_end == "." else [0.0, 61.0])
    assert lines[0].asides == (Aside(6, 1.0, "Them", "Yeah."), Aside(14, 21.0, "Them", "Okay."))
    assert lines[1].asides == ()
    # Folding keeps every word, including punctuation and its speaker, exactly once.
    original = Counter(
        (track.speaker, word)
        for track in tracks
        for segment in track.segments
        for word in segment.text.split()
    )
    displayed = Counter((line.speaker, word) for line in lines for word in line.text.split())
    displayed.update(
        (aside.speaker, word)
        for line in lines
        for aside in line.asides
        for word in aside.text.split()
    )
    assert displayed == original


def test_folding_handles_empty_and_single_speaker_recordings():
    assert merge([], fold_backchannels=True) == []
    track = SpeakerTrack("Me", 0.0, [seg(0.0, "Yeah."), seg(2.0, "Okay.")])
    assert merge([track], fold_backchannels=True) == merge([track])
