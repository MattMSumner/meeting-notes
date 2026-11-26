"""Explicit IO for seven authored mappings and fresh, reproducible offline previews."""

# pyright: reportPrivateUsage=false
# Share only the existing pure JSON and literal presentation helpers.

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from . import work_review as review
from .generation import _json, _load
from .model import Snapshot
from .render import _escape, _literal

ROOT = Path(__file__).parent.parent.parent
PROPOSAL = ROOT / "prototypes/reviewable_draft/work-review-proposal"
PAIRS = ROOT / "evaluation/m10/v11/pairs.json"
MAPPING_HASH = "41da04cdb6b63a07fb3c0d2d68d4cccf7a0f35ccaae01f229719ed5ad4a196e4"
INPUT_HASH = "d2c1fc42a6d6e59ad4fd766e226862d1f137e5cd1002b6984a94abcf2bc9d35f"
LONGER_HASH = "f84fa2480b11b493ad18639f0f18e1565f47e6e0d2f6d03934a1bf6530d7da1e"
ANNEX_HASH = "50722c65c6488ff06ccb0e3121494bb1d74890569e525cc26dee936992a3c206"
CASES = (
    "partial_coordination_retracted",
    "cancellation_with_new_task",
    "qualified_external_timing",
    "additional",
    "accepted_status_answer",
    "unit_equivalence",
    "authored_longer_context",
)
FAILURES = ("incomplete_longer_context", "unavailable_additional")
NOTICE = (
    "> Authored offline work-review preview. No model generated these selections. "
    "No model-quality or saved-effort evidence.\n\n"
)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_hash(text: str) -> str:
    return _hash(text.encode("utf-8"))


def _read(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if _hash(data) != expected:
        raise ValueError(f"Authored provenance changed: {path.name}")
    return data


def _snapshot(data: dict[str, Any]) -> Snapshot:
    return Snapshot(
        title=data["title"],
        started_at=data["started_at"],
        attendees=tuple(data["attendees"]),
        my_name=data["my_name"],
        transcript=data["transcript"],
        handwritten_text=data["handwritten_text"],
    )


def _saved_snapshot(snapshot: Snapshot) -> dict[str, Any]:
    return {
        **asdict(snapshot),
        "snapshot_id": snapshot.snapshot_id,
        "sources": [asdict(source) for source in snapshot.sources],
    }


def _load_examples() -> tuple[dict[str, review.Result], dict[str, Any]]:
    mapping = _load(_read(PROPOSAL / "examples.json", MAPPING_HASH).decode("utf-8"))
    pair_bytes = _read(PAIRS, INPUT_HASH)
    longer = _load(_read(PROPOSAL / "authored-longer-input.json", LONGER_HASH).decode("utf-8"))
    _read(PROPOSAL / "sources.md", ANNEX_HASH)
    if (
        mapping["authored"] is not True
        or mapping["model_generated"] is not False
        or mapping["input_sha256"] != INPUT_HASH
        or mapping["authored_input_sha256"] != LONGER_HASH
        or mapping["sources_annex_sha256"] != ANNEX_HASH
        or longer["held_out"] is not False
        or longer["model_generated"] is not False
    ):
        raise ValueError("Expected honest authored provenance")
    rows = cast(list[dict[str, Any]], json.loads(pair_bytes))
    pairs = {row["id"]: row for row in rows}
    if len(rows) != 40 or len(pairs) != 40:
        raise ValueError("Expected all forty unchanged unique inputs")
    authored = cast(list[dict[str, Any]], mapping["examples"])
    if tuple(row["case"] for row in authored) != CASES:
        raise ValueError("Expected seven original authored mappings")
    results: dict[str, review.Result] = {}
    for row in authored:
        name: str = row["case"]
        if name == "authored_longer_context":
            saved: dict[str, Any] = longer["snapshot"][name]
            snapshot = _snapshot(saved)
            # Check every stored field and source, not just the selected turns.
            if _json(_saved_snapshot(snapshot)) != _json(saved):
                raise ValueError("Complete authored snapshot differs from saved identity")
        else:
            pair = pairs[name]
            snapshot = _snapshot(
                {
                    **pair["meeting"],
                    "transcript": pair["transcript"],
                    "handwritten_text": pair["handwritten_text"],
                }
            )
        snapshot.validate()
        if (
            snapshot.snapshot_id != row["snapshot_id"]
            or _text_hash(snapshot.transcript) != row["transcript_sha256"]
            or _text_hash(snapshot.handwritten_text) != row["handwritten_text_sha256"]
        ):
            raise ValueError("Complete snapshot identity changed")
        _read(PROPOSAL / row["preview"], row["preview_sha256"])
        packet = review.prepare(snapshot, f"authored-work-review-{MAPPING_HASH}/{name}")
        result = review.decode(packet, _json({"groups": row["groups"]}))
        selected = {ref for group in result.groups for ref in group.refs}
        if {
            source.id: _text_hash(source.text)
            for source in snapshot.sources
            if source.id in selected
        } != row["selected_source_sha256"]:
            raise ValueError("Authored selected source hashes changed")
        results[name] = result
    return results, mapping


def load_examples() -> dict[str, review.Result]:
    """Read and verify only the seven saved synthetic source-based mappings."""
    return _load_examples()[0]


def failure_examples(results: dict[str, review.Result]) -> dict[str, review.Result]:
    """Author explicit failure demonstrations from saved inputs, without any IO."""
    longer = results["authored_longer_context"]
    additional = results["additional"]
    longer.validate()
    additional.validate()
    return {
        FAILURES[0]: review.host_incomplete(
            review.prepare(longer.snapshot, f"{longer.generation_id}/incomplete"),
            '{"groups":[["T11"]]}',
        ),
        FAILURES[1]: review.host_unavailable(
            review.prepare(additional.snapshot, f"{additional.generation_id}/unavailable")
        ),
    }


def preview(result: review.Result) -> str:
    """Render saved authored values only; no file reads or requests."""
    label = (
        "> Authored failure demonstration; not a passing coverage example.\n\n"
        if result.state != "draft"
        else ""
    )
    return NOTICE + label + review.render_result(result)


def _artifacts() -> dict[str, bytes]:
    results, mapping = _load_examples()
    results.update(failure_examples(results))
    files: dict[str, str] = {
        f"{name}.md": preview(result)
        + f"\n[Complete synthetic source](sources.md#{name.replace('_', '-')})\n"
        for name, result in results.items()
    }
    files["index.md"] = (
        "# Authored offline work-review previews\n\n"
        + NOTICE
        + "Seven manual mappings: six familiar development inputs and one Chief-authored "
        "longer input, not held out. The longer example selects four of sixteen speech "
        "turns in two groups. These are work-section previews, not full meeting drafts. "
        "Earlier action failures and grades remain unchanged.\n\n"
        + "\n".join(f"- [{name.replace('_', ' ')}]({name}.md)" for name in CASES)
        + "\n\nAuthored failure demonstrations, not passing coverage examples. The incomplete "
        "example retains an independent valid group but omits other work/context; the "
        "unavailable example accepts no groups. Neither repairs a malformed reply.\n\n"
        + "\n".join(f"- [{name.replace('_', ' ')}]({name}.md)" for name in FAILURES)
        + "\n\n[Complete synthetic sources](sources.md) do not rescue omitted selected work. "
        "Relevance, context, missing work and review burden remain empirical. "
        "The manifest records authored provenance, not a runtime freeze or production "
        "persistence. No inference or live metadata calls ran.\n"
    )
    annex = ["# Complete authored synthetic sources", NOTICE]
    for name, result in results.items():
        snapshot = result.snapshot
        annex.extend(
            [
                f"## {name.replace('_', '-')}",
                "Complete source for inspection; not focused work-retention coverage.",
                _literal(snapshot.transcript),
                "### Original handwritten notes",
                f"Written by {_escape(snapshot.my_name)}; kept as supplied.",
                _literal(snapshot.handwritten_text),
            ]
        )
    files["sources.md"] = "\n\n".join(annex) + "\n"
    provenance = {
        "authored": True,
        "model_generated": False,
        "model_quality_evidence": False,
        "saved_effort_evidence": False,
    }
    saved = {
        **provenance,
        "kind": "authored-work-review-preview-data",
        "results": {name: asdict(result) for name, result in results.items()},
    }
    files["results.json"] = json.dumps(saved, ensure_ascii=False, indent=2) + "\n"
    original_rows = {row["case"]: row for row in mapping["examples"]}
    manifest = {
        **provenance,
        "kind": "authored-work-review-preview-provenance",
        "production_persistence": False,
        "runtime_freeze": False,
        "model_requests": 0,
        "input_sha256": INPUT_HASH,
        "mapping_sha256": MAPPING_HASH,
        "authored_input_sha256": LONGER_HASH,
        "proposal_annex_sha256": ANNEX_HASH,
        "cases": {
            name: {
                "snapshot_id": result.snapshot_id,
                "generation_id": result.generation_id,
                "result_binding": result.binding,
                "state": result.state,
                "authored_failure_demonstration": name in FAILURES,
                "input_provenance": original_rows[
                    "authored_longer_context"
                    if name == FAILURES[0]
                    else "additional"
                    if name == FAILURES[1]
                    else name
                ]["input_provenance"],
                "mapping_sha256": _text_hash(_json([group.refs for group in result.groups])),
                "transcript_sha256": _text_hash(result.snapshot.transcript),
                "handwritten_text_sha256": _text_hash(result.snapshot.handwritten_text),
            }
            for name, result in results.items()
        },
        "files": {name: _text_hash(text) for name, text in files.items()},
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return {name: text.encode("utf-8") for name, text in files.items()}


def write_previews(output: Path) -> None:
    """Create one new directory exclusively; refuse existing paths and symlink parents."""
    # Validate and render everything before reserving output. No overwrite or resume.
    files = _artifacts()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Existing previews or edits cannot be overwritten")
    if ".." in output.parts or any(parent.is_symlink() for parent in output.parents):
        raise ValueError("Use an ordinary output path without symlinks or parent traversal")
    output.mkdir(exist_ok=False)
    for name, data in files.items():
        with (output / name).open("xb") as stream:
            stream.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--case", choices=(*CASES, *FAILURES))
    mode.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.output_dir is not None:
        write_previews(args.output_dir)
    else:
        results = load_examples()
        results.update(failure_examples(results))
        print(preview(results[args.case]), end="")


if __name__ == "__main__":
    main()
