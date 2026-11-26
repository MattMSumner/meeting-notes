"""Authored quote-selection examples, distinct from every captured model reply."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from . import extraction
from .model import Snapshot

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / "evaluation/m10/v11/pairs.json"
FIXTURES = ROOT / "tests/fixtures/quoted_draft.json"
INPUT_HASH = "d2c1fc42a6d6e59ad4fd766e226862d1f137e5cd1002b6984a94abcf2bc9d35f"
NOTICE = "> Authored quoted-selection example. No model generated this preview.\n\n"


def _load() -> tuple[dict[str, extraction.Result], str, str]:
    pair_bytes, fixture_bytes = PAIRS.read_bytes(), FIXTURES.read_bytes()
    pair_hash = hashlib.sha256(pair_bytes).hexdigest()
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    if pair_hash != INPUT_HASH:
        raise ValueError("Frozen forty-case inputs changed")
    rows = cast(list[dict[str, Any]], json.loads(pair_bytes))
    pairs = {row["id"]: row for row in rows}
    if len(rows) != 40 or len(pairs) != 40 or not set(extraction.CASES) <= set(pairs):
        raise ValueError("Expected forty unique original inputs")
    fixture = cast(dict[str, Any], json.loads(fixture_bytes))
    if set(fixture) != {"authored", "description", "cases"} or fixture["authored"] is not True:
        raise ValueError("Examples must be explicitly authored")
    if type(fixture["description"]) is not str:
        raise ValueError("Authored example description is required")
    authored_rows = cast(list[dict[str, Any]], fixture["cases"])
    if any(set(row) != {"id", "response"} for row in authored_rows):
        raise ValueError("Expected authored case IDs and responses only")
    authored = {row["id"]: row["response"] for row in authored_rows}
    if len(authored_rows) != len(extraction.CASES) or set(authored) != set(extraction.CASES):
        raise ValueError("Expected exactly six authored quote-selection cases")
    snapshots = {
        name: Snapshot(
            title=pairs[name]["meeting"]["title"],
            started_at=pairs[name]["meeting"]["started_at"],
            attendees=tuple(pairs[name]["meeting"]["attendees"]),
            my_name=pairs[name]["meeting"]["my_name"],
            transcript=pairs[name]["transcript"],
            handwritten_text=pairs[name]["handwritten_text"],
        )
        for name in extraction.CASES
    }
    packets = extraction.prepare(snapshots, f"authored-quoted-{fixture_hash[:12]}")
    results = {
        name: extraction.decode(packet, json.dumps(authored[name]))
        for name, packet in zip(extraction.CASES, packets, strict=True)
    }
    if not all(result.complete for result in results.values()):
        raise ValueError("Authored intended examples contain rejected selections")
    return results, pair_hash, fixture_hash


def load_examples() -> dict[str, extraction.Result]:
    return _load()[0]


def preview(result: extraction.Result) -> str:
    return NOTICE + extraction.render_result(result)


def write_previews(output: Path) -> None:
    """Create fresh previews only; captured source hashes describe the rendered bytes."""
    if output.exists():
        raise FileExistsError("Existing quoted previews and edits cannot be overwritten")
    results, input_hash, fixture_hash = _load()
    rendered = {f"{name}.md": preview(result) for name, result in results.items()}
    rendered["index.md"] = (
        "# Authored quoted-selection previews\n\n"
        "These demonstrate the offline compiler, not fresh model quality. "
        "The first diagnostic's defects remain unchanged.\n\n"
        + "\n".join(f"- [{name.replace('_', ' ')}]({name}.md)" for name in extraction.CASES)
        + "\n"
    )
    manifest = {
        "kind": "authored_quoted_selection_examples",
        "model_requests": 0,
        "input_sha256": input_hash,
        "fixture_sha256": fixture_hash,
        "files": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in rendered.items()
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, text in rendered.items():
        with (output / name).open("x") as stream:
            stream.write(text)
    with (output / "manifest.json").open("x") as stream:
        stream.write(json.dumps(manifest, indent=2) + "\n")
