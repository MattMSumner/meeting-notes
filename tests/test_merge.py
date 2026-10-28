from meeting_notes.merge import Line, SpeakerTrack, merge
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
