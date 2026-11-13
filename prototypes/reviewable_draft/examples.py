"""Load authored design examples from unchanged synthetic inputs; no inference."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, cast

from prototypes.reviewable_draft import Draft, Item, Section, Snapshot, render

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / "evaluation/m10/v11/pairs.json"
FIXTURES = ROOT / "tests/fixtures/reviewable_draft.json"
CASES = (
    "empty",
    "additional",
    "unit_equivalence",
    "multi_claim_notes",
    "tentative_confirmed",
    "accepted_status_answer",
    "accepted_request_retracted",
    "cancellation_with_new_task",
    "partial_coordination_retracted",
    "qualified_external_timing",
)
Kind = Literal["summary", "decisions", "actions", "review"]
KINDS: tuple[Kind, ...] = ("summary", "decisions", "actions", "review")
STATES = ("draft", "needs_review", "unavailable")
PREVIEW_NOTICE = "> Authored offline example. No model generated this preview.\n\n"


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected an object with string keys")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(k, str) for k in mapping):
        raise ValueError("Expected an object with string keys")
    return cast(dict[str, Any], mapping)


def _rows(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return cast(list[Any], value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected text, including explicit empty text where appropriate")
    return value


def _refs(value: object) -> tuple[str, ...]:
    return tuple(_text(v) for v in _rows(value))


def _section(kind: Kind, value: object, snapshot: Snapshot, generation_id: str) -> Section:
    data = _object(value)
    if set(data) != {"state", "items", "notice", "review_sources"}:
        raise ValueError("Unknown or missing authored section fields")
    state = _text(data["state"])
    if state not in STATES:
        raise ValueError("Unknown authored section state")
    items: list[Item] = []
    for raw in _rows(data["items"]):
        item = _object(raw)
        if set(item) != {"text", "sources"}:
            raise ValueError("Unknown or missing authored item fields")
        items.append(Item(text=_text(item["text"]), sources=_refs(item["sources"])))
    return Section(
        kind=kind,
        state=state,
        snapshot_id=snapshot.snapshot_id,
        generation_id=generation_id,
        items=tuple(items),
        notice=_text(data["notice"]),
        review_sources=_refs(data["review_sources"]),
    )


def _load_examples() -> tuple[dict[str, Draft], str, str]:
    pair_bytes, fixture_bytes = PAIRS.read_bytes(), FIXTURES.read_bytes()
    pair_hash = hashlib.sha256(pair_bytes).hexdigest()
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    manifest = _object(json.loads((PAIRS.parent / "sha256.json").read_text()))
    if pair_hash != manifest["pairs.json"]:
        raise ValueError("Frozen synthetic inputs changed")
    pairs: dict[str, dict[str, Any]] = {}
    for raw in _rows(json.loads(pair_bytes)):
        pair = _object(raw)
        name = _text(pair["id"])
        if name in pairs:
            raise ValueError("Duplicate frozen case")
        pairs[name] = pair
    if len(pairs) != 40 or not set(CASES) <= set(pairs):
        raise ValueError("Expected the unchanged forty-case corpus")
    fixture = _object(json.loads(fixture_bytes))
    if set(fixture) != {"authored", "description", "cases"} or fixture["authored"] is not True:
        raise ValueError("Examples must be explicitly identified as authored")
    _text(fixture["description"])
    authored: dict[str, dict[str, Any]] = {}
    for raw in _rows(fixture["cases"]):
        entry = _object(raw)
        if set(entry) != {"id", "sections"}:
            raise ValueError("Unknown or missing authored case fields")
        name = _text(entry["id"])
        if name in authored:
            raise ValueError("Duplicate authored case")
        authored[name] = _object(entry["sections"])
    if set(authored) != set(CASES):
        raise ValueError("Expected exactly the ten declared diagnostic cases")
    result: dict[str, Draft] = {}
    for name in CASES:
        pair = pairs[name]
        meeting = _object(pair["meeting"])
        snapshot = Snapshot(
            title=_text(meeting["title"]),
            started_at=_text(meeting["started_at"]),
            attendees=_refs(meeting["attendees"]),
            my_name=_text(meeting["my_name"]),
            transcript=_text(pair["transcript"]),
            handwritten_text=_text(pair["handwritten_text"]),
        )
        generation_id = f"authored-prototype-{name}-{fixture_hash[:12]}"
        sections = authored[name]
        if set(sections) != set(KINDS):
            raise ValueError("Authored draft needs all four section kinds")
        result[name] = Draft(
            snapshot=snapshot,
            generation_id=generation_id,
            sections=tuple(_section(k, sections[k], snapshot, generation_id) for k in KINDS),
        )
    return result, pair_hash, fixture_hash


def load_examples() -> dict[str, Draft]:
    """Read only the frozen synthetic corpus and explicitly authored response fixtures."""
    return _load_examples()[0]


def preview(draft: Draft) -> str:
    return PREVIEW_NOTICE + render(draft)


def write_previews(output: Path, cases: tuple[str, ...] = CASES) -> None:
    """Export into a new directory, preserving every existing preview or user edit."""
    if output.exists():
        raise FileExistsError(f"Preview directory already exists: {output}")
    if not cases or len(set(cases)) != len(cases) or not set(cases) <= set(CASES):
        raise ValueError("Choose declared preview cases without duplicates")
    drafts, input_hash, fixture_hash = _load_examples()
    rendered = {name: preview(drafts[name]) for name in cases}
    index = (
        "# Reviewable draft previews\n\n"
        "These are authored synthetic design examples. No model generated them, "
        "and they establish no model quality or accepted meeting output.\n\n"
        + "\n".join(f"- [{name.replace('_', ' ')}]({name}.md)" for name in cases)
        + "\n"
    )
    provenance = {
        "kind": "authored_offline_rendering",
        "model_requests": 0,
        "inputs": "evaluation/m10/v11/pairs.json",
        "input_sha256": input_hash,
        "fixture_sha256": fixture_hash,
        "previews": {
            name: {
                "snapshot_id": drafts[name].snapshot.snapshot_id,
                "generation_id": drafts[name].generation_id,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
            for name, text in rendered.items()
        },
        "index_sha256": hashlib.sha256(index.encode()).hexdigest(),
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, text in {"index": index, **rendered}.items():
        with (output / f"{name}.md").open("x", encoding="utf-8") as stream:
            stream.write(text)
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(provenance, indent=2) + "\n")
