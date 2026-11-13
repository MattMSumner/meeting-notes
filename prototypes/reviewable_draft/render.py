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


def _source(source: Source) -> str:
    label = (
        f"Spoken by {_escape(source.speaker)} at {_escape(source.timestamp)}"
        if source.kind == "transcript"
        else f"Written by {_escape(source.speaker)}"
    )
    return f"{label}\n\n{_literal(source.text)}"


def render(draft: Draft) -> str:
    """Render only saved values; references establish provenance, not correctness."""
    if type(draft) is not Draft:
        raise TypeError("render needs a Draft")
    # Frozen dataclasses can still be forged; check every nesting boundary again.
    draft.validate()
    snapshot = draft.snapshot
    sources = {source.id: source for source in snapshot.sources}
    out = [
        f"# {_escape(snapshot.title)}",
        "**AI draft — review required**",
        "Review every suggestion. Source references do not verify meaning or acceptance.",
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
        state = {"draft": "AI draft", "needs_review": "Needs review", "unavailable": "Unavailable"}[
            section.state
        ]
        out.append(f"*{state} — review required*")
        if section.notice:
            out.append(_escape(section.notice))
        for item in section.items:
            out.append(f"- {_escape(item.text)}")
            for ref in item.sources:
                out.append("\n".join("  " + line for line in _source(sources[ref]).split("\n")))
        if not section.items and section.state == "draft":
            out.append("No suggestions supplied.")
        if section.review_sources:
            out.append("**Context to review**")
            out.extend(_source(sources[ref]) for ref in section.review_sources)
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
