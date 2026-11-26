"""Pure Markdown presentation of a saved, mechanically validated draft."""

import html
import re
import string

from .model import KINDS, Draft, SectionKind, Source

_TITLES: dict[SectionKind, str] = {
    "summary": "Summary",
    "decisions": "Suggested decisions",
    "actions": "Suggested actions",
    "review": "Passages to review",
}


def _escape(text: str) -> str:
    # Inline data cannot start a new Markdown block or introduce HTML/Obsidian markup.
    return "".join(
        html.escape(char)
        if char in "&<>\"'"
        else "\\" + char
        if char in string.punctuation
        else char
        for char in " ".join(text.splitlines())
    )


def _literal(text: str) -> str:
    # A source containing fences must not close its enclosing literal block.
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    ending = "" if text.endswith("\n") else "\n"
    return f"{fence}text\n{text}{ending}{fence}"


def _label(source: Source) -> str:
    return (
        f"Spoken by {_escape(source.speaker)} at {_escape(source.timestamp)}"
        if source.kind == "transcript"
        else f"Written by {_escape(source.speaker)}"
    )


def _source(source: Source) -> str:
    return f"{_label(source)}\n\n{_literal(source.text)}"


def render(draft: Draft) -> str:
    """Render only saved values; references establish provenance, not correctness."""
    if type(draft) is not Draft:
        raise TypeError("render needs a Draft")
    # Frozen dataclasses can still be forged; check every nesting boundary again.
    draft.validate()
    snapshot = draft.snapshot
    sources = {source.id: source for source in snapshot.sources}
    cited: dict[str, int] = {}

    def citations(refs: tuple[str, ...]) -> str:
        for ref in refs:
            if ref not in cited:
                cited[ref] = len(cited) + 1
        return "Sources: " + "; ".join(f"{cited[ref]} — {_label(sources[ref])}" for ref in refs)

    out = [
        f"# {_escape(snapshot.title)}",
        "**AI draft — review required**",
        "Review and edit these suggestions before using them. Source excerpts are included below.",
    ]
    if any(section.state == "unavailable" for section in draft.sections):
        out.append(
            "**Incomplete draft.** Some analysis is unavailable; usable suggestions remain below."
        )
    out.extend(
        (
            f"Started: {_escape(snapshot.started_at)}",
            "Attendees: "
            + (", ".join(_escape(name) for name in snapshot.attendees) or "Not supplied"),
        )
    )
    sections = {section.kind: section for section in draft.sections}
    for kind in KINDS:
        section = sections[kind]
        out.append(f"## {_TITLES[kind]}")
        if section.state != "draft":
            out.append("**Needs review**" if section.state == "needs_review" else "**Unavailable**")
        if section.notice:
            out.append(_escape(section.notice))
        for item in section.items:
            out.append(f"- {_escape(item.text)}")
            out.append("  " + citations(item.sources))
        if not section.items and section.state == "draft":
            out.append("No suggestions supplied.")
        if section.review_sources:
            out.append("**Context to review**\n\n" + citations(section.review_sources))
    if cited:
        out.append("## Source excerpts")
        for ref, number in cited.items():
            out.append(f"### Source {number}\n\n{_source(sources[ref])}")
    out.extend(
        (
            "## Original handwritten notes",
            f"Written by {_escape(snapshot.my_name)}; kept as supplied.",
            _literal(snapshot.handwritten_text)
            if snapshot.handwritten_text
            else "No handwritten notes.",
        )
    )
    return "\n\n".join(out) + "\n"
