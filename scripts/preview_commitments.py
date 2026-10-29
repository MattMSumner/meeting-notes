"""Preview manually selected commitment quotes using only saved synthetic inputs."""

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Sequence
from datetime import datetime
from os.path import relpath
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from meeting_notes.meeting import Meeting
from meeting_notes.render import render_note, timestamp
from meeting_notes.summary import Summary
from meeting_notes.turns import parse_turns, selected_details

REPO = Path(__file__).resolve().parents[1]
CASES = (
    "golden",
    "availability",
    "numbers",
    "no_commitments",
    "conditional_commitments",
    "timing_roles",
    "accepted_requests",
)
ORIGINALS = CASES[:3]
HEADING = "## Decisions and commitments\n\n"


class _ArchivedSummary(BaseModel):
    case: str
    summary: Summary


class _Baseline(BaseModel):
    rows: list[_ArchivedSummary]


def quote_section(transcript: str, turn_ids: Sequence[str]) -> str:
    """Copy whole source turns, retaining their speaker and source order."""
    details = selected_details(turn_ids, parse_turns(transcript))
    lines: list[str] = []
    for detail in details:
        assert detail.start is not None
        quote = " ".join(detail.quote.split())
        lines.append(f"- **{detail.speaker} — {timestamp(detail.start)}:** “{quote}”")
    return HEADING + "\n".join(lines or ["_None selected._"]) + "\n\n"


def _commitment_bounds(note: str) -> tuple[int, int]:
    markers = [
        list(re.finditer(pattern, note, re.MULTILINE))
        for pattern in (r"^## Decisions\n\n", r"^## Action items\n\n", r"^Transcript: \[\[")
    ]
    if any(len(matches) != 1 for matches in markers):
        raise ValueError("Expected one Decisions, Action items and Transcript region")
    start, actions, end = (matches[0].start() for matches in markers)
    if not start < actions < end:
        raise ValueError("Expected Decisions followed by Action items and Transcript")
    if re.findall(r"^## .+$", note[start:end], re.MULTILINE) != [
        "## Decisions",
        "## Action items",
    ] or not re.fullmatch(r"Transcript: \[\[[^\r\n]+\]\]\n", note[end:]):
        raise ValueError("Ambiguous commitment section layout")
    return start, end


def replace_commitments(note: str, section: str) -> str:
    """Replace only the renderer's decisions/actions region, preserving its surroundings."""
    start, end = _commitment_bounds(note)
    if not section.startswith(HEADING) or not section.endswith("\n\n"):
        raise ValueError("Expected a complete quoted-commitments section")
    return note[:start] + section + note[end:]


def _summaries(rows: Sequence[_ArchivedSummary], cases: Sequence[str]) -> dict[str, Summary]:
    summaries = {row.case: row.summary for row in rows}
    if len(rows) != len(cases) or set(summaries) != set(cases):
        raise ValueError("Archived summaries must contain each expected fixture exactly once")
    return summaries


def _meeting(case: str) -> Meeting:
    if case == "numbers":
        return Meeting.new("Scanner project pricing", datetime(2026, 10, 21, 14, 0))
    title = "Lighthouse migration" if case in ORIGINALS else "Commitments check"
    return Meeting.new(title, datetime(2026, 10, 20, 10, 0))


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_previews(
    fixtures: Path,
    selections_path: Path,
    baseline_path: Path,
    full_path: Path,
    output: Path,
) -> None:
    """Validate and render all previews before creating a new output directory."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Preserve the existing preview output: {output}")
    sources = {
        "selections": selections_path,
        "baseline": baseline_path,
        "full": full_path,
        **{case: fixtures / f"{case}_transcript.txt" for case in CASES},
    }
    raw = {name: path.read_bytes() for name, path in sources.items()}
    selections = TypeAdapter(dict[str, list[str]]).validate_json(raw["selections"], strict=True)
    if set(selections) != set(CASES):
        raise ValueError("Selections must contain exactly the seven supported fixtures")
    baseline = _summaries(_Baseline.model_validate_json(raw["baseline"]).rows, CASES)
    full_rows = TypeAdapter(list[_ArchivedSummary]).validate_json(raw["full"])
    full = _summaries(full_rows, ORIGINALS)
    files: dict[str, str] = {}
    metrics: dict[str, dict[str, Any]] = {}
    index = [
        "# Quoted commitments preview",
        "",
        "All inputs are synthetic. Source turns were selected manually; no model calls ran.",
        "This tests the reading format, not model selection quality. The before sections",
        "come from saved baseline runs. Full-note pairs retain their saved overview and",
        "Details unchanged, including known defects. Quotes may repeat across sections.",
        "The full-note Transcript wiki links are illustrative; use the source links below",
        "to inspect each synthetic fixture.",
        "",
        "| Fixture | Quoted turns | Quote characters | Before section | After section "
        "| Details overlap |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case in CASES:
        transcript = raw[case].decode("utf-8")
        turns = parse_turns(transcript)
        quotes = selected_details(selections[case], turns)
        section = quote_section(transcript, selections[case])
        meeting = _meeting(case)
        baseline_note = render_note(meeting, baseline[case], meeting.id)
        start, end = _commitment_bounds(baseline_note)
        before = baseline_note[start:end]
        files[f"{case}-comparison.md"] = (
            f"# {case}: commitment sections\n\n"
            "Manually selected synthetic source turns; no model calls.\n\n"
            "# Before: saved generated commitments\n\n"
            + before
            + "# After: quoted source turns\n\n"
            + section
        )
        selected = set(selections[case])
        metric: dict[str, Any] = {
            "requested_ids": selections[case],
            "selected_ids": [turn.id for turn in turns if turn.id in selected],
            "quoted_turn_count": len(quotes),
            "quote_characters": sum(len(" ".join(quote.quote.split())) for quote in quotes),
            "before_section_characters": len(before),
            "after_section_characters": len(section),
        }
        overlap: int | None = None
        if case in full:
            full_before = render_note(meeting, full[case], meeting.id)
            full_after = replace_commitments(full_before, section)
            files[f"{case}-full-before.md"] = full_before
            files[f"{case}-full-after.md"] = full_after
            detail_sources = {(item.speaker, item.start, item.quote) for item in full[case].details}
            overlap = sum(
                (item.speaker, item.start, item.quote) in detail_sources for item in quotes
            )
            metric.update(
                details_overlap_count=overlap,
                full_before_characters=len(full_before),
                full_after_characters=len(full_after),
            )
        metrics[case] = metric
        source_link = Path(relpath(sources[case], output)).as_posix()
        index.append(
            f"| [{case}]({case}-comparison.md) · [source](<{source_link}>) | "
            f"{len(quotes)} | {metric['quote_characters']} | "
            f"{len(before)} | {len(section)} | {overlap if overlap is not None else '—'} |"
        )
    index += [
        "",
        "Character counts include spaces; section counts include Markdown and headings.",
        "Details overlap counts source turns shared by the two sections, matched by",
        "speaker, timestamp and exact stored text. Both copies remain visible.",
        "",
        "Full-note comparisons:",
        "",
        *(
            f"- {case}: [before]({case}-full-before.md) · [after]({case}-full-after.md)"
            for case in ORIGINALS
        ),
    ]
    files["index.md"] = "\n".join(index) + "\n"
    report = {
        "manual_selection": True,
        "model_calls": 0,
        "script_sha256": _hash(Path(__file__).read_bytes()),
        "inputs": {
            name: {"path": str(path), "sha256": _hash(raw[name])} for name, path in sources.items()
        },
        "cases": metrics,
    }
    files["report.json"] = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    output.mkdir(parents=True)
    for name, content in files.items():
        (output / name).write_text(content)


def check_output(path: Path) -> Path:
    """Keep CLI previews inside the excluded local preview directory."""
    allowed = REPO.resolve() / ".local/m9-quoted-preview"
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError(f"Preview output must be within {allowed}, without symlink escapes")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", str(resolved / "index.md")],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    if ignored.returncode != 0:
        raise ValueError(
            "Preview output must be ignored by Git. Add /.local/m9-quoted-preview/ "
            "to this checkout's .git/info/exclude before generating previews."
        )
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=REPO / ".local/m9-reference-experiment/baseline-screen.json",
    )
    parser.add_argument(
        "--full",
        type=Path,
        default=REPO / ".local/m9-handoff/artifacts/meeting-notes-m9-commitments/full.json",
    )
    parser.add_argument("--output", type=Path, default=REPO / ".local/m9-quoted-preview")
    args = parser.parse_args()
    output = check_output(args.output)
    generate_previews(
        REPO / "tests/fixtures",
        REPO / "tests/fixtures/commitment_quote_selections.json",
        args.baseline,
        args.full,
        output,
    )
    print(f"Created previews in {output}")


if __name__ == "__main__":
    main()
