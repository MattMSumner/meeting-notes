"""Shape and provenance only, without interpreting the supplied prose."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["transcript", "notes"]
SectionKind = Literal["summary", "decisions", "actions", "review"]
SectionState = Literal["draft", "needs_review", "unavailable"]
KINDS: tuple[SectionKind, ...] = ("summary", "decisions", "actions", "review")

_TURN = re.compile(r"^\[([0-9]{2,}:[0-5][0-9]:[0-5][0-9])\] ([^:\r\n]+):[ \t]?(.*)$")


def _string(value: object, name: str, *, nonblank: bool = True) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if nonblank and not value.strip():
        raise ValueError(f"{name} must not be blank")


def _tuple(value: object, name: str) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")


def _refs(value: tuple[str, ...], name: str, *, required: bool = False) -> None:
    _tuple(value, name)
    for ref in value:
        _string(ref, name)
    if required and not value:
        raise ValueError(f"{name} must include focused sources")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must not repeat a source")


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    kind: SourceKind
    speaker: str
    timestamp: str
    text: str

    def __post_init__(self) -> None:
        for name in ("id", "kind", "speaker", "text"):
            _string(getattr(self, name), name)
        _string(self.timestamp, "timestamp", nonblank=False)
        if self.kind not in ("transcript", "notes"):
            raise ValueError("unknown source kind")
        if self.kind == "transcript" and not self.timestamp:
            raise ValueError("spoken sources need a timestamp")
        if self.kind == "notes" and self.timestamp:
            raise ValueError("written sources have no spoken timestamp")


def _turns(transcript: str) -> tuple[Source, ...]:
    sources: list[Source] = []
    speaker = timestamp = ""
    body: list[str] = []
    for line in transcript.splitlines(keepends=True):
        # Only remove the physical line ending; all wording and blank gaps survive.
        content = line.removesuffix("\n").removesuffix("\r")
        match = _TURN.fullmatch(content)
        if match:
            if speaker:
                sources.append(
                    Source(f"T{len(sources) + 1}", "transcript", speaker, timestamp, "".join(body))
                )
            timestamp, speaker, text = match.groups()
            _string(speaker, "speaker")
            ending = line[len(content) :]
            body = [text + ending]
        else:
            if content.startswith("[") or (content.strip() and not speaker):
                raise ValueError("transcript must contain timestamped speaker turns")
            if speaker:
                body.append(line)
    if speaker:
        sources.append(
            Source(f"T{len(sources) + 1}", "transcript", speaker, timestamp, "".join(body))
        )
    if not sources:
        raise ValueError("transcript must contain timestamped speaker turns")
    return tuple(sources)


@dataclass(frozen=True, slots=True)
class Snapshot:
    title: str
    started_at: str
    attendees: tuple[str, ...]
    my_name: str
    transcript: str
    handwritten_text: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in ("title", "started_at", "my_name", "transcript"):
            _string(getattr(self, name), name)
        _string(self.handwritten_text, "handwritten_text", nonblank=False)
        _tuple(self.attendees, "attendees")
        for attendee in self.attendees:
            _string(attendee, "attendee")
        _turns(self.transcript)

    @property
    def snapshot_id(self) -> str:
        fields = (
            self.title,
            self.started_at,
            self.attendees,
            self.my_name,
            self.transcript,
            self.handwritten_text,
        )
        return hashlib.sha256(json.dumps(fields, ensure_ascii=True).encode("utf-8")).hexdigest()

    @property
    def sources(self) -> tuple[Source, ...]:
        written = tuple(
            Source(f"N{index}", "notes", self.my_name, "", line)
            for index, line in enumerate(
                (line for line in self.handwritten_text.splitlines() if line.strip()), start=1
            )
        )
        return (*_turns(self.transcript), *written)


@dataclass(frozen=True, slots=True)
class Item:
    text: str
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _string(self.text, "item text")
        _refs(self.sources, "item sources", required=True)


@dataclass(frozen=True, slots=True)
class Section:
    kind: SectionKind
    state: SectionState
    snapshot_id: str
    generation_id: str
    items: tuple[Item, ...] = ()
    notice: str = ""
    review_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name in ("kind", "state", "snapshot_id", "generation_id"):
            _string(getattr(self, name), name)
        if self.kind not in KINDS:
            raise ValueError("unknown section kind")
        if self.state not in ("draft", "needs_review", "unavailable"):
            raise ValueError("unknown section state")
        _tuple(self.items, "items")
        for item in self.items:
            if type(item) is not Item:
                raise TypeError("items must contain Item records")
            item.validate()
        _string(self.notice, "notice", nonblank=self.state != "draft")
        _refs(self.review_sources, "review sources", required=self.state != "draft")
        if self.state == "unavailable" and self.items:
            raise ValueError("unavailable sections cannot contain accepted items")


@dataclass(frozen=True, slots=True)
class Draft:
    snapshot: Snapshot
    generation_id: str
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.snapshot) is not Snapshot:
            raise TypeError("draft needs a complete Snapshot")
        self.snapshot.validate()
        _string(self.generation_id, "generation_id")
        _tuple(self.sections, "sections")
        seen: set[SectionKind] = set()
        sources = {source.id: source for source in self.snapshot.sources}
        for section in self.sections:
            if type(section) is not Section:
                raise TypeError("sections must contain Section records")
            section.validate()
            if section.kind in seen:
                raise ValueError("section kinds must be distinct")
            seen.add(section.kind)
            if section.snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("section belongs to a different snapshot")
            if section.generation_id != self.generation_id:
                raise ValueError("section belongs to a different generation")
            refs = (
                *section.review_sources,
                *(ref for item in section.items for ref in item.sources),
            )
            for ref in refs:
                if ref not in sources:
                    raise ValueError("section cites an unknown source")
                if section.kind != "review" and sources[ref].kind != "transcript":
                    raise ValueError("spoken sections must cite transcript sources")
        if seen != set(KINDS):
            raise ValueError("draft needs exactly one of each section kind")
