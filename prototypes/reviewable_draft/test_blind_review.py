"""Masked provenance and human score-lock mechanics, using authored replies only."""

# pyright: reportPrivateUsage=false

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from . import blind_review as b
from . import compare as c
from .test_compare import HTTP
from .test_compare import frozen as frozen
from .test_compare import http as http
from .test_compare import source as source
from .test_diagnostic import read


@pytest.fixture
def review(frozen: tuple[Path, str], http: HTTP, tmp_path: Path) -> Path:
    output, pin = frozen
    assert c.run(output, "Synthetic authored-response test", pin)["capture_complete"]
    target = tmp_path / "review"
    packet_sha = b.prepare(output, pin, target)
    assert packet_sha == c._hash((target / "packet.json").read_bytes())
    return target


def scores(output: Path) -> list[dict[str, Any]]:
    return [
        dict(id=row["id"], verdict="pass", evidence="Synthetic test evidence, not a quality grade.")
        for row in read(output / "packet.json")["records"]
    ]


def test_packet_has_eighteen_full_inputs_canonical_drafts_and_no_technical_identity(
    review: Path,
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    output, pin = frozen
    packet = read(review / "packet.json")
    key = read(review / "key.json")
    manifest, packets, baseline = c._validate(output, pin)
    assert len(http.posts) == 12
    assert Counter(r["case"] for r in packet["records"]) == dict.fromkeys(c.actions.CASES, 3)
    assert len({r["id"] for r in packet["records"]}) == 18
    assert Counter(v["arm"] for v in key["records"].values()) == {0: 6, 1: 6, 2: 6}
    text = (review / "packet.json").read_text()
    for hidden in [
        *c.PINS.values(),
        str(c.ROOT),
        manifest["generation_id"],
        "qwen3",
        "gemma",
        '"arm"',
        '"identity"',
        '"thinking"',
        "load_duration",
        "body.raw",
    ]:
        assert hidden not in text
    for row in packet["records"]:
        binding = key["records"][row["id"]]
        index = c.actions.CASES.index(row["case"])
        arm = int(binding["arm"])
        original = packets[(max(1, binding["arm"]) - 1) * 6 + index].original
        assert row["input"] == json.loads(c._bytes(asdict(original.snapshot)))
        if binding["arm"] == 0:
            original = c.actions.Prepared(
                original.snapshot,
                c._load(baseline["manifest.json"])["generation_id"] + "/" + row["case"],
                baseline[f"requests/{row['case']}.json"].decode(),
            )
            raw = baseline[f"results/{index + 1:02}-{row['case']}/response/body.raw"]
        else:
            raw = (
                output / "results" / packets[(arm - 1) * 6 + index].slot / "response/body.raw"
            ).read_bytes()
        assert row["draft"] == c.actions.render_result(c._replay(original, raw))
        assert row["capture_status"] == "complete"
        assert any(path.endswith("/response/body.raw") for path in binding["artifacts"])
        assert binding["record_sha256"] == c._hash(c._bytes(row))
    assert "partial_coordination_retracted" in packet["criteria"]
    assert "review burden" in packet["criteria"]


def test_failure_and_unsent_slots_are_present_without_fabricated_drafts(
    frozen: tuple[Path, str],
    http: HTTP,
    tmp_path: Path,
) -> None:
    output, pin = frozen
    http.responses["01-01-unit_equivalence"] = b"partial raw reply"
    final = c.run(output, "Synthetic test", pin)
    assert final["possibly_sent"] == 7
    target = tmp_path / "failed-review"
    b.prepare(output, pin, target)
    rows = read(target / "packet.json")["records"]
    assert len(rows) == 18
    assert Counter(row["capture_status"] for row in rows) == {
        "complete": 12,
        "failed": 1,
        "unsent": 5,
    }
    assert all(
        row["draft"] is None for row in rows if row["capture_status"] in ("failed", "unsent")
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unknown",
        "blank_evidence",
        "missing_evidence",
        "bad_verdict",
        "missing_verdict",
    ],
)
def test_malformed_scores_do_not_create_a_lock(review: Path, change: str) -> None:
    rows = scores(review)
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[-1] = rows[0]
    elif change == "unknown":
        rows[0]["id"] = "unknown-id"
    elif change == "blank_evidence":
        rows[0]["evidence"] = " "
    elif change.startswith("missing_"):
        del rows[0][change.removeprefix("missing_")]
    else:
        rows[0]["verdict"] = "automatically-good"
    with pytest.raises(ValueError):
        b.lock_scores(review, rows)
    assert not (review / "grades").exists()
    with pytest.raises(FileNotFoundError):
        b.join_scores(review)


def test_all_grades_lock_before_identity_join_and_preserve_original_assessor_bytes(
    review: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        b.join_scores(review)
    original = tmp_path / "assessor.json"
    data = json.dumps(scores(review), indent=3).encode() + b"\n"
    original.write_bytes(data)
    digest = b.lock_scores(review, original)
    assert (review / "grades/scores.json").read_bytes() == data
    assert digest == c._hash(data)
    joined = b.join_scores(review)
    assert len(joined["records"]) == 18 and joined["scores_sha256"] == digest
    assert {r["identity"]["model"] for r in joined["records"]} == {
        "qwen3:30b",
        *(m for m, _ in c.MODELS),
    }
    with pytest.raises(FileExistsError):
        b.lock_scores(review, scores(review))
    assert (review / "grades/scores.json").read_bytes() == data


@pytest.mark.parametrize(
    "file",
    ["packet.json", "key.json", "grades/scores.json", "grades/lock.json", "source", "added_source"],
)
def test_join_rejects_tampering_and_preserves_the_edit(review: Path, file: str) -> None:
    b.lock_scores(review, scores(review))
    if file == "added_source":
        path = Path(read(review / "key.json")["frozen"]) / "results/new-artifact.json"
    elif file == "source":
        key = read(review / "key.json")
        path = next(Path(n) for n in key["sources"] if n.endswith("response/body.raw"))
    else:
        path = review / file
    path.write_bytes(b"Synthetic user edit")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        b.join_scores(review)
    assert path.read_bytes() == b"Synthetic user edit"


@pytest.mark.parametrize("field", ["result.json", "actions.md", "attempt.json", "final.json"])
def test_capture_replay_rejects_self_rehashed_corruption_before_masking(
    frozen: tuple[Path, str],
    http: HTTP,
    tmp_path: Path,
    field: str,
) -> None:
    output, pin = frozen
    c.run(output, "Synthetic test", pin)
    root = output / "results"
    path = root / field if field == "final.json" else root / "01-01-unit_equivalence" / field
    if field == "actions.md":
        path.write_text("Synthetic changed draft")
    else:
        data = read(path)
        if field == "result.json":
            data["generation_id"] = "other-generation"
        elif field == "attempt.json":
            data["request_sha256"] = "f" * 64
        else:
            data["possibly_sent"] = 1
        path.write_bytes(c._bytes(data))
    seal = read(root / "manifest.json")
    seal["files"][path.relative_to(root).as_posix()] = c._hash(path.read_bytes())
    (root / "manifest.json").write_bytes(c._bytes(seal))
    with pytest.raises(ValueError):
        b.prepare(output, pin, tmp_path / "corrupt-review")


def test_preparation_and_lock_never_replace_existing_edits(
    review: Path,
    frozen: tuple[Path, str],
) -> None:
    output, pin = frozen
    b.lock_scores(review, scores(review))
    (review / "packet.json").write_bytes(b"Synthetic packet edit")
    (review / "grades/scores.json").write_bytes(b"Synthetic grade edit")
    with pytest.raises(FileExistsError):
        b.prepare(output, pin, review)
    with pytest.raises(ValueError):
        b.lock_scores(review, [])
    assert (review / "packet.json").read_bytes() == b"Synthetic packet edit"
    assert (review / "grades/scores.json").read_bytes() == b"Synthetic grade edit"


def test_duplicate_json_score_keys_are_rejected(review: Path, tmp_path: Path) -> None:
    path = tmp_path / "duplicate-keys.json"
    data = json.dumps(scores(review)).replace('"id":', '"id": "extra", "id":', 1)
    path.write_text(data)
    with pytest.raises(ValueError, match="Duplicate"):
        b.lock_scores(review, path)
    assert not (review / "grades").exists()
