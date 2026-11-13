"""Offline masked records and immutable human score lock; no semantic grading."""

# pyright: reportPrivateUsage=false

import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import actions, compare


def _capture(frozen: Path, pin: str, packets: tuple[compare.Packet, ...]) -> dict[str, bytes]:
    root = frozen / "results"
    data = {
        p.relative_to(root).as_posix(): compare._read(root, p.relative_to(root).as_posix())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    manifest = compare._load(data["manifest.json"])
    hashes = {n: compare._hash(b) for n, b in data.items() if n != "manifest.json"}
    if manifest != {"expected_manifest_sha256": pin, "files": hashes}:
        raise ValueError("Capture artifact set/hash differs")
    final = compare._load(data["final.json"])
    rows = final["slots"]
    if len(rows) != 12 or final["expected_manifest_sha256"] != pin:
        raise ValueError("Capture accounting differs")
    for packet, row in zip(packets, rows, strict=True):
        slot = packet.slot + "/"
        attempted = slot + "attempt.json" in data
        captured = slot + "response/body.raw" in data
        errors: list[str] = []
        outcome = compare._optional(data.get(slot + "outcome.json"), "outcome.json", errors)
        result = compare._optional(data.get(slot + "result.json"), "result.json", errors)
        timings = compare._optional(data.get(slot + "timings.json"), "timings.json", errors)
        expected = dict(
            slot=packet.slot,
            arm=packet.arm,
            case=packet.case,
            possibly_sent=attempted,
            captured=captured,
            result_saved=bool(result),
            capture_complete=outcome.get("capture_complete", False),
            issues=result.get("issues", []),
            error=outcome.get("error"),
            elapsed=outcome.get("elapsed", 0),
            timings=timings,
            artifact_errors=errors,
        )
        if row != expected or (
            row["capture_complete"]
            and not (attempted and captured and result and slot + "actions.md" in data)
        ):
            raise ValueError("Slot accounting differs")
        if (
            slot + "request.json" in data
            and data[slot + "request.json"] != packet.request_json.encode()
        ):
            raise ValueError("Actual challenger request differs")
        if attempted:
            attempt = compare._load(data[slot + "attempt.json"])
            if (
                attempt.get("possibly_sent") is not True
                or attempt.get("generation_id") != packet.original.generation_id
                or attempt.get("snapshot_id") != packet.original.snapshot.snapshot_id
                or attempt.get("request_sha256") != compare._hash(packet.request_json.encode())
                or not 0 < attempt["timeout"] <= 600
            ):
                raise ValueError("Attempt/source/generation binding differs")
        if slot + "timings.json" in data and not errors:
            response = compare._load(data[slot + "response/body.raw"])
            if expected["timings"] != {k: response[k] for k in compare.TIMINGS if k in response}:
                raise ValueError("Returned timings differ from raw response")
        if result:
            replay = compare._replay(packet.original, data[slot + "response/body.raw"])
            if data[slot + "result.json"] != compare._bytes(asdict(replay)) or (
                slot + "actions.md" in data
                and data[slot + "actions.md"] != actions.render_result(replay).encode()
            ):
                raise ValueError("Capture raw/result/render binding differs")
        elif slot + "actions.md" in data:
            raise ValueError("Draft without a saved result")
    lists = {
        "completed": [r["slot"] for r in rows if r["capture_complete"]],
        "failed": [r["slot"] for r in rows if r["possibly_sent"] and not r["capture_complete"]],
        "captured": [r["slot"] for r in rows if r["captured"]],
        "unsent": [r["slot"] for r in rows if not r["possibly_sent"]],
        "incomplete_cases": [r["slot"] for r in rows if r["issues"]],
    }
    if (
        any(final[k] != v for k, v in lists.items())
        or final["possibly_sent"] != sum(r["possibly_sent"] for r in rows)
        or final["capture_complete"]
        != (
            len(lists["completed"]) == 12
            and final["elapsed"] <= 1800
            and final["integrity_error"] is None
        )
    ):
        raise ValueError("Final accounting differs")
    return data


def prepare(frozen: Path, expectedSHA: str, output: Path) -> str:
    """Write packet.json, private key.json and manifest.json to NEW output; return packet SHA."""
    output.mkdir(parents=True, exist_ok=False)
    frozen = frozen.resolve()
    manifest, packets, baseline = compare._validate(frozen, expectedSHA)
    capture = _capture(frozen, expectedSHA, packets)
    sources = {str(frozen / name): digest for name, digest in manifest["files"].items()}
    sources[str(frozen / "manifest.json")] = expectedSHA
    sources.update({str(frozen / "results" / n): compare._hash(b) for n, b in capture.items()})
    sources.update(
        {str(compare.ROOT / compare.BASELINE / n): compare._hash(b) for n, b in baseline.items()}
    )
    sources.update(
        {str(compare.ROOT / name): manifest["files"][f"source/{name}"] for name in compare.RUNTIME}
    )
    records: list[dict[str, Any]] = []
    bindings: dict[str, Any] = {}
    for arm in (0, 1, 2):
        for index, case in enumerate(actions.CASES, 1):
            packet = packets[(max(1, arm) - 1) * 6 + index - 1]
            if arm == 0:
                directory = f"results/{index:02}-{case}/"
                data = baseline
                source = compare.ROOT / compare.BASELINE
                identity = compare._load(baseline["identity.json"])
            else:
                directory = packet.slot + "/"
                data = capture
                source = frozen / "results"
                identity = manifest["identities"][arm - 1]
            if arm == 0:
                outcome = compare._load(data[directory + "outcome.json"])
                has_result = True
                issues = compare._load(data[directory + "result.json"])["issues"]
            else:
                row = compare._load(capture["final.json"])["slots"][(arm - 1) * 6 + index - 1]
                outcome = row
                has_result = row["result_saved"]
                issues = row["issues"]
            draft: str | None = None
            if has_result:
                # The old banner is never shown: render both arms through the same function.
                original = packet.original
                if arm == 0:
                    original = actions.Prepared(
                        original.snapshot,
                        compare._load(baseline["manifest.json"])["generation_id"] + "/" + case,
                        baseline[f"requests/{case}.json"].decode(),
                    )
                result = compare._replay(original, data[directory + "response/body.raw"])
                draft = actions.render_result(result)
            status = (
                "complete"
                if outcome.get("capture_complete")
                else "failed"
                if directory + "attempt.json" in data
                else "unsent"
            )
            if has_result and issues:
                status = "incomplete"
            opaque = secrets.token_hex(16)
            record = dict(
                id=opaque,
                case=case,
                input=asdict(packet.original.snapshot),
                capture_status=status,
                draft=draft,
            )
            records.append(record)
            bindings[opaque] = dict(
                arm=arm,
                case=case,
                identity=identity,
                record_sha256=compare._hash(compare._bytes(record)),
                artifacts={
                    str(source / n): compare._hash(b)
                    for n, b in data.items()
                    if n.startswith(directory)
                },
            )
    secrets.SystemRandom().shuffle(records)
    declaration = (frozen / "ACTIONS.md").read_text()
    criteria = declaration.split("| Case | Prospective action-only criterion |", 1)[1].split(
        "\nStop on ", 1
    )[0]
    packet_bytes = compare._bytes(
        dict(criteria="| Case | Prospective action-only criterion |" + criteria, records=records)
    )
    key_bytes = compare._bytes(
        dict(
            frozen=str(frozen),
            expected_manifest_sha256=expectedSHA,
            sources=sources,
            records=bindings,
        )
    )
    compare._write(output / "packet.json", packet_bytes)
    compare._write(output / "key.json", key_bytes)
    compare._save(
        output / "manifest.json",
        dict(packet_sha256=compare._hash(packet_bytes), key_sha256=compare._hash(key_bytes)),
    )
    return compare._hash(packet_bytes)


def _verified(output: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = compare._load(compare._read(output, "manifest.json"))
    packet_bytes, key_bytes = (
        compare._read(output, "packet.json"),
        compare._read(output, "key.json"),
    )
    if manifest != dict(
        packet_sha256=compare._hash(packet_bytes), key_sha256=compare._hash(key_bytes)
    ):
        raise ValueError("Review packet/key changed")
    packet, key = compare._load(packet_bytes), compare._load(key_bytes)
    records = packet["records"]
    ids = [r["id"] for r in records]
    if len(ids) != 18 or len(set(ids)) != 18 or set(ids) != set(key["records"]):
        raise ValueError("Review requires exactly 18 unique records")
    for record in records:
        if compare._hash(compare._bytes(record)) != key["records"][record["id"]]["record_sha256"]:
            raise ValueError("Review record binding differs")
    for name, digest in key["sources"].items():
        path = Path(name)
        if compare._hash(compare._read(path.parent, path.name)) != digest:
            raise ValueError("Review source changed")
    captured = Path(key["frozen"]) / "results"
    if {str(p) for p in captured.rglob("*") if p.is_file()} != {
        name for name in key["sources"] if captured in Path(name).parents
    }:
        raise ValueError("Capture artifact set changed after review preparation")
    return manifest, packet, key


def _scores(value: object, ids: set[str]) -> list[dict[str, Any]]:
    scores = compare.d._rows(value)
    seen: set[str] = set()
    for score in scores:
        row = compare.d.json_helpers._object(score)
        if (
            set(row) != {"id", "verdict", "evidence"}
            or type(row["id"]) is not str
            or row["id"] not in ids
            or row["id"] in seen
            or row["verdict"] not in ("pass", "partial", "critical", "incomplete")
            or type(row["evidence"]) is not str
            or not row["evidence"].strip()
        ):
            raise ValueError("Scores need unique known id, verdict and nonblank source evidence")
        seen.add(row["id"])
    if seen != ids or len(scores) != 18:
        raise ValueError("Lock all 18 scores before joining identities")
    return scores


def lock_scores(output: Path, scores: Path | list[dict[str, Any]]) -> str:
    """Lock all 18 {id, verdict, evidence} scores once. A Path preserves original JSON bytes."""
    manifest, packet, _ = _verified(output)
    data = scores.read_bytes() if isinstance(scores, Path) else compare._bytes(scores)
    _scores(
        compare._load(b'{"scores":' + data + b"}")["scores"], {r["id"] for r in packet["records"]}
    )
    grades = output / "grades"
    grades.mkdir(exist_ok=False)
    compare._write(grades / "scores.json", data)
    digest = compare._hash(data)
    compare._save(
        grades / "lock.json",
        dict(
            **manifest,
            scores_sha256=digest,
            review_manifest_sha256=compare._hash(compare._read(output, "manifest.json")),
        ),
    )
    return digest


def join_scores(output: Path) -> dict[str, Any]:
    """Read-only join after the complete score lock, verifying all source and grade hashes."""
    lock = compare._load(compare._read(output, "grades/lock.json"))
    manifest, packet, key = _verified(output)
    data = compare._read(output, "grades/scores.json")
    if lock != dict(
        **manifest,
        scores_sha256=compare._hash(data),
        review_manifest_sha256=compare._hash(compare._read(output, "manifest.json")),
    ):
        raise ValueError("Locked grades or review hashes changed")
    scores = _scores(
        compare._load(b'{"scores":' + data + b"}")["scores"], {r["id"] for r in packet["records"]}
    )
    return dict(**lock, records=[dict(**score, **key["records"][score["id"]]) for score in scores])
