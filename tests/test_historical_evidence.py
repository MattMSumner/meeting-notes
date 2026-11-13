"""Frozen artifacts and saved wrapper-9 generations survive current source changes."""

import hashlib
import json
import socket
from pathlib import Path
from typing import Any, NoReturn

import pytest

from meeting_notes.audit import ComparisonAudit
from meeting_notes.evidence import Generation

ROOT = Path(__file__).resolve().parents[1] / "evaluation/m10"
V10 = ROOT / "v10"

# Pin the manifests too: editing an artifact and its digest must not bless a rewrite.
MANIFESTS = {
    "sha256.json": (18, "f1353ef3f12f8cd7d89a79d13f18a20b42557f23ab9aecbf9ef54785ed2338c9"),
    "results/sha256.json": (
        9,
        "c9d52013e0f4d22120fc503516380a2ee09759a1e8f2cd989ea51b8c5cd5662f",
    ),
    "v2/sha256.json": (20, "02ee4e317669395b1f689bba53f35a45971216b264d7e54d5aeee6e23dfba20b"),
    "v2/results/sha256.json": (
        9,
        "e362fd4a82452bdcd1e09acd28ca61d91bd8e30836f2a00ad1a9e0ca008c497a",
    ),
    "v3/sha256.json": (23, "117b666fdb5930f18ee9c4ba18a1d13e2fd3b2dcfcf9015ed20ceaa17a03c86b"),
    "v3/results/sha256.json": (
        9,
        "8bfe9dd453665d1d650db6313093d5fbc7ebc92d5cc707071f0fa69ade8430f8",
    ),
    "v4/sha256.json": (28, "accc2e31492122d9de177ab33879116df79ce99249080ce817c9f3cdb2aa4da2"),
    "v4/results/sha256.json": (
        9,
        "640aca57e333d90c687b841eaaadeb5751a6a6e7014b88387788bbac2ae3620f",
    ),
    "v5/sha256.json": (31, "83cdb4a25cfc0417abde02d7f83801a24802d89d949d933f15e175026fe3471e"),
    "v5/results/sha256.json": (
        9,
        "12700a7027009d438c8c84291de979a567c8487992b3d492249e1cb6c7057ad8",
    ),
    "v6/sha256.json": (33, "896f4fab2a0d24bf4e2015c8d25b844e8419c87b2fdb86c3cf93421664ea2f75"),
    "v6/results/sha256.json": (
        9,
        "e16dbeb8ab3d646d8ddb2d9cf8d028e84be0ed2bcf8655635046c6f733fc8a80",
    ),
    "v7/sha256.json": (36, "6362561da030eaa2e2daa2c1f6a89dbd34805ab94b269589059a2d8e069975cd"),
    "v7/results/sha256.json": (
        9,
        "a032356a1d53a7d255304708ff1388bbcd8c8d57f9cadc9e0551828416be54ed",
    ),
    "v8/sha256.json": (33, "c9148871993cef1906683d9c048eacb9a74d9310a9f6bf98c04da0178223db84"),
    "v8/results/sha256.json": (
        10,
        "34010c91dbb421800ea487f0c936b7a8c24cdd971146e3b6e2a8775f1d015318",
    ),
    "v9/sha256.json": (36, "e24daf07a023a1bcd88bce1f892c8d74149c67bdded85ad611385f77648f23ec"),
    "v9/results/sha256.json": (
        9,
        "9f332775b1096abef38cacdb2ec67174afdefcc6e8a20e04545de4d7a0d4574e",
    ),
    "v10/sha256.json": (42, "774c66bb1e3e9b1c643c544ab21b651bd4f3e529af7975974d36151144ca55df"),
    "v10/results/sha256.json": (
        14,
        "3669bb6df3d7591e4e39df7fee6b8c3ba96299526e0c1a560cae93c19e1d000b",
    ),
}

SELECTED_CASES = (
    "empty",
    "sparse",
    "additional",
    "conflicting",
    "ambiguous_dates",
    "same_speaker_tasks",
    "coordinated_tasks",
    "later_timing",
    "revised_timing",
    "shared_numbers",
    "status_conflict",
    "tentative_task",
    "front_loaded_timing",
    "unit_equivalence",
    "unit_disagreement",
    "proposal_rejected",
    "additive_context",
)


def test_all_historical_input_and_result_manifests_are_unchanged():
    folders = [Path("."), *(Path(f"v{version}") for version in range(2, 11))]
    assert set(MANIFESTS) == {
        str(folder / name) for folder in folders for name in ("sha256.json", "results/sha256.json")
    }
    verified = 0
    for name, (count, digest) in MANIFESTS.items():
        path = ROOT / name
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest, name
        entries: dict[str, str] = json.loads(content)
        assert len(entries) == count, name
        for artifact, expected in entries.items():
            frozen = path.parent / artifact
            assert hashlib.sha256(frozen.read_bytes()).hexdigest() == expected, str(frozen)
            verified += 1
    assert verified == 396


@pytest.fixture(scope="module")
def saved_results() -> dict[str, dict[str, Any]]:
    # Read the evidence directly; results/verify.py writes into the frozen results folder.
    header, *rows = [
        json.loads(line) for line in (V10 / "results/proposed.jsonl").read_text().splitlines()
    ]
    pairs = json.loads((V10 / "pairs.json").read_text())
    assert header["frozen_hashes"] == json.loads((V10 / "sha256.json").read_text())
    assert header["settings"] == json.loads((V10 / "settings.json").read_text())
    assert len(rows) == len(pairs) == 22
    assert {row["case"] for row in rows} == {pair["id"] for pair in pairs}
    selected = {row["case"]: row for row in rows if "summary" in row}
    assert len(selected) == len(SELECTED_CASES) == 17
    assert set(selected) == set(SELECTED_CASES)
    return selected


@pytest.mark.parametrize("case", SELECTED_CASES)
def test_v10_selected_generation_replays_and_roundtrips_without_inference(
    case: str, saved_results: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
):
    def no_connection(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("Historical replay must not connect to a model or other service")

    monkeypatch.setattr(socket.socket, "connect", no_connection)
    row = saved_results[case]
    pairs = {pair["id"]: pair for pair in json.loads((V10 / "pairs.json").read_text())}
    pair = pairs[case]
    audit = row["audit"]
    assert audit["validator_version"] == "grounding-v8"
    assert audit["selected"] is not None
    attempt = audit["attempts"][audit["selected"]]
    # The original request carries the exact saved context, independent of current prompts.
    context, separator, _ = attempt["request"]["messages"][1]["content"].partition(
        "\nTranscript sources"
    )
    assert separator
    generation = Generation.model_validate(
        {
            "version": 9,
            "summary": row["summary"],
            "audit": audit,
            "evidence": {
                "transcript": pair["transcript"],
                "context": context,
                "handwritten_original": pair["handwritten_text"],
                "handwritten_text": pair["handwritten_text"],
            },
        }
    )
    assert generation.version == 9
    assert generation.summary.model_dump() == row["summary"]
    assert isinstance(generation.audit, ComparisonAudit)
    assert generation.audit.model_dump() == audit
    selected = generation.audit.selected
    assert selected is not None
    replays = [json.loads(line) for line in (V10 / "results/replay.jsonl").read_text().splitlines()]
    assert len(replays) == 17
    assert {replay["case"] for replay in replays} == set(SELECTED_CASES)
    replay = next(replay for replay in replays if replay["case"] == case)
    assert replay["wrapper_version"] == 9 and replay["summary_matches"]
    assert generation.audit.attempts[selected].warnings == replay["warnings"]
    assert Generation.model_validate_json(generation.model_dump_json()) == generation

    if case == "unit_disagreement":
        # Historical replay must retain this known failure, even after new saves reject it.
        assert json.loads(attempt["reply"])["action_items"][0]["original_commitment_id"] == "T1"
        assert [action.task for action in generation.summary.action_items] == [
            "Support costs 120 dollars."
        ]
