from meeting_notes.merge import Line
from meeting_notes.pipeline import transcript_text


def test_labels_my_lines_with_my_name():
    lines = [Line(0.0, "Me", "Hi."), Line(2.0, "Them", "Hey.")]

    assert transcript_text(lines, "Sam") == "[00:00:00] Sam: Hi.\n[00:00:02] Them: Hey."


def test_a_turn_split_into_paragraphs_reaches_the_model_as_one_line():
    lines = [Line(0.0, "Me", "First."), Line(40.0, "Me", "Second."), Line(50.0, "Them", "Yes.")]

    assert transcript_text(lines, "Sam") == "[00:00:00] Sam: First. Second.\n[00:00:50] Them: Yes."
