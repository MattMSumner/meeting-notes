"""Explicit offline freeze and single-use, bounded diagnostic capture. No quality verdict."""

# pyright: reportPrivateUsage=false
# Reuse the generator JSON checks without changing its deliberately small public API.

import hashlib
import json
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from . import _http, generation
from .model import Snapshot
from .render import render

ROOT = Path(__file__).resolve().parents[2]
INPUT = "evaluation/m10/v11/pairs.json"
INPUT_HASH = "d2c1fc42a6d6e59ad4fd766e226862d1f137e5cd1002b6984a94abcf2bc9d35f"
DECLARATION = "prototypes/reviewable_draft/EXPERIMENT.md"
RUNTIME = (
    "prototypes/__init__.py",
    *(
        f"prototypes/reviewable_draft/{name}.py"
        for name in ("__init__", "model", "render", "generation", "diagnostic", "_http")
    ),
)
LIMIT = 900
PER_REQUEST = 600
_http_process = subprocess.Popen
# Detect files replaced after this interpreter imported its runtime.
LOADED = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in RUNTIME}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(value: object) -> bytes:
    return generation._json(value).encode("utf-8")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()


def _save(path: Path, value: object) -> None:
    _write(path, _bytes(value))


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def _source(candidate: str | None = None) -> tuple[str, dict[str, bytes]]:
    names = (*RUNTIME, DECLARATION, INPUT)
    head = _git("rev-parse", "HEAD").decode().strip()
    commit = head if candidate is None else candidate
    if type(commit) is not str or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Expected an exact candidate commit")
    if candidate is not None:
        try:
            _git("merge-base", "--is-ancestor", commit, head)
        except subprocess.CalledProcessError as error:
            raise ValueError("HEAD must descend from frozen candidate") from error
    if _git("status", "--porcelain=v1", "--untracked-files=all", "--", *names):
        raise ValueError("Dirty diagnostic source/input/declaration")
    data = {name: (ROOT / name).read_bytes() for name in names}
    for name, content in data.items():
        if content != _git("show", f"{commit}:{name}"):
            raise ValueError(f"Source differs from candidate commit: {name}")
        if name in LOADED and _hash(content) != LOADED[name]:
            raise ValueError(f"Imported runtime changed: {name}; use a fresh interpreter")
    return commit, data


def _identity(value: object) -> dict[str, Any]:
    identity = generation._object(value)
    if set(identity) != {"version", "model", "digest"} or any(
        type(v) is not str or not v.strip() or v != v.strip() for v in identity.values()
    ):
        raise ValueError("Declare nonblank version/model/digest identity")
    if identity["model"] != "qwen3:30b" or not re.fullmatch("[0-9a-f]{64}", identity["digest"]):
        raise ValueError("Expected qwen3:30b and its exact SHA256 digest")
    return identity


def _settings() -> dict[str, Any]:
    return {
        "cases": list(generation.CASES),
        "requests": 6,
        "seconds": 900,
        "per_request_seconds": 600,
        "model": "qwen3:30b",
        "temperature": 0,
        "think": True,
        "num_ctx": 32768,
        "stream": False,
        "retries": 0,
    }


def _rows(value: object) -> list[Any]:
    if type(value) is not list:
        raise ValueError("Expected a JSON array")
    return cast(list[Any], value)


def _snapshots(data: bytes) -> dict[str, Snapshot]:
    if _hash(data) != INPUT_HASH:
        raise ValueError("Original forty-case input hash changed")
    rows = _rows(json.loads(data))
    if len(rows) != 40:
        raise ValueError("Expected forty original cases")
    pairs: dict[str, Any] = {}
    for raw in rows:
        pair = generation._object(raw)
        name = pair["id"]
        if type(name) is not str or name in pairs:
            raise ValueError("Expected forty unique case IDs")
        pairs[name] = pair
    if not set(generation.CASES) <= pairs.keys():
        raise ValueError("Missing selected case")
    return {
        name: Snapshot(
            title=pairs[name]["meeting"]["title"],
            started_at=pairs[name]["meeting"]["started_at"],
            attendees=tuple(pairs[name]["meeting"]["attendees"]),
            my_name=pairs[name]["meeting"]["my_name"],
            transcript=pairs[name]["transcript"],
            handwritten_text=pairs[name]["handwritten_text"],
        )
        for name in generation.CASES
    }


def _snapshot_bytes(snapshots: dict[str, Snapshot]) -> bytes:
    return _bytes(
        {
            name: {
                **asdict(snapshot),
                "snapshot_id": snapshot.snapshot_id,
                "sources": [asdict(s) for s in snapshot.sources],
            }
            for name, snapshot in snapshots.items()
        }
    )


def _files(
    source: dict[str, bytes], generation_id: str, identity: dict[str, Any]
) -> tuple[dict[str, bytes], tuple[generation.Prepared, ...]]:
    snapshots = _snapshots(source[INPUT])
    packets = generation.prepare(snapshots, generation_id)
    if len(packets) != 6:
        raise ValueError("Expected six fixed packets")
    for name, packet in zip(generation.CASES, packets, strict=True):
        if packet.snapshot != snapshots[name] or packet.generation_id != f"{generation_id}/{name}":
            raise ValueError("Prepared packet differs from its snapshot/generation")
        body = packet.body()
        if (body["model"], body["stream"], body["think"], body["options"]) != (
            "qwen3:30b",
            False,
            True,
            {"temperature": 0, "num_ctx": 32768},
        ):
            raise ValueError("Packet settings differ from declared settings")
    files = {f"source/{name}": source[name] for name in RUNTIME}
    files.update(
        {
            "EXPERIMENT.md": source[DECLARATION],
            "identity.json": _bytes(identity),
            "settings.json": _bytes(_settings()),
            "pairs.json": source[INPUT],
            "snapshots.json": _snapshot_bytes(snapshots),
            **{
                f"requests/{name}.json": packet.request_json.encode("utf-8")
                for name, packet in zip(generation.CASES, packets, strict=True)
            },
        }
    )
    return files, packets


def freeze(output: Path, identity: dict[str, str]) -> str:
    """Freeze committed source and six exact packets into a NEW directory; no network."""
    output.mkdir(parents=True, exist_ok=False)
    declared = _identity(identity)
    commit, source = _source()
    generation_id = f"diagnostic-{uuid.uuid4().hex}"
    files, _ = _files(source, generation_id, declared)
    manifest = {
        "format": "reviewable-draft-diagnostic-1",
        "candidate_commit": commit,
        "generation_id": generation_id,
        "identity": declared,
        "settings": _settings(),
        "files": {name: _hash(data) for name, data in files.items()},
    }
    for name, data in files.items():
        _write(output / name, data)
    manifest_bytes = _bytes(manifest)
    _write(output / "manifest.json", manifest_bytes)
    return _hash(manifest_bytes)


def _validate(
    frozen: Path, expected_manifest_sha256: str
) -> tuple[dict[str, Any], tuple[generation.Prepared, ...]]:
    frozen = frozen.resolve()
    manifest_bytes = (frozen / "manifest.json").read_bytes()
    if type(expected_manifest_sha256) is not str or not re.fullmatch(
        "[0-9a-f]{64}", expected_manifest_sha256
    ):
        raise ValueError("Chief must supply the expected manifest SHA256")
    if _hash(manifest_bytes) != expected_manifest_sha256:
        raise ValueError("Manifest differs from Chief's expected SHA256")
    manifest = generation._load(manifest_bytes.decode("utf-8"))
    if set(manifest) != {
        "format",
        "candidate_commit",
        "generation_id",
        "identity",
        "settings",
        "files",
    }:
        raise ValueError("Unexpected freeze manifest")
    if manifest["format"] != "reviewable-draft-diagnostic-1" or _bytes(
        manifest["settings"]
    ) != _bytes(_settings()):
        raise ValueError("Frozen settings differ")
    _identity(manifest["identity"])
    _, source = _source(manifest["candidate_commit"])
    expected, packets = _files(source, manifest["generation_id"], manifest["identity"])
    hashes = generation._object(manifest["files"])
    if set(hashes) != set(expected):
        raise ValueError("Missing or unexpected frozen artifacts")
    for name, data in expected.items():
        path = frozen / name
        if any(p.is_symlink() for p in (path, *path.parents) if frozen in p.parents):
            raise ValueError("Frozen artifacts cannot be symlinks")
        saved = path.read_bytes()
        if saved != data or _hash(saved) != hashes[name]:
            raise ValueError(f"Frozen packet/input/source differs: {name}")
    return manifest, packets


def _remaining(deadline: float) -> float:
    remaining = min(PER_REQUEST, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Diagnostic elapsed deadline reached")
    return remaining


def _command(
    method: str,
    endpoint: str,
    request: Path | None,
    output: Path,
    timeout: float,
    request_sha256: str | None,
) -> list[str]:
    return [
        sys.executable,
        "-B",
        str(Path(_http.__file__).resolve()),
        method,
        endpoint,
        str(request) if request is not None else "-",
        str(output.resolve()),
        str(timeout),
        request_sha256 if request_sha256 is not None else "-",
    ]


def _exchange(
    method: str,
    endpoint: str,
    request: Path | None,
    output: Path,
    deadline: float,
    request_sha256: str | None = None,
) -> bytes:
    timeout = _remaining(deadline)
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    error: str | None = None
    try:
        with (output / "stderr.txt").open("xb") as stderr:
            process = _http_process(
                _command(method, endpoint, request, output, timeout, request_sha256),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
            )
            try:
                code = process.wait(timeout=min(timeout, _remaining(deadline)))
            except BaseException:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                finally:
                    process.wait()
                raise
        if code:
            raise RuntimeError(f"HTTP worker failed (exit {code}); retain raw/error evidence")
        headers = generation._load((output / "headers.json").read_text())
        if headers["status"] != 200:
            raise ValueError(f"HTTP status {headers['status']}")
        body = (output / "body.raw").read_bytes()
        _remaining(deadline)
        return body
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _save(
            output / "exchange.json",
            {
                "method": method,
                "endpoint": endpoint,
                "timeout": timeout,
                "elapsed": time.monotonic() - started,
                "error": error,
                "server_compute_cancellation_guaranteed": False,
            },
        )


def _metadata(output: Path, identity: dict[str, Any], deadline: float) -> None:
    _remaining(deadline)
    output.mkdir(exist_ok=False)
    version = generation._load(
        _exchange("GET", "/api/version", None, output / "version", deadline).decode("utf-8")
    )
    tags = generation._load(
        _exchange("GET", "/api/tags", None, output / "tags", deadline).decode("utf-8")
    )
    models = [generation._object(m) for m in _rows(tags.get("models"))]
    matches = [m for m in models if m.get("name") == identity["model"]]
    if (
        version.get("version") != identity["version"]
        or len(matches) != 1
        or matches[0].get("digest") != identity["digest"]
    ):
        raise ValueError("Local version/model/digest identity drift")


def _capture_slot(
    frozen: Path,
    slot: Path,
    packet: generation.Prepared,
    manifest: dict[str, Any],
    deadline: float,
    expected_manifest_sha256: str,
) -> bool:
    incomplete = False
    _write(slot / "request.json", packet.request_json.encode("utf-8"))
    _metadata(slot / "before", manifest["identity"], deadline)
    _validate(frozen, expected_manifest_sha256)
    request_bytes = packet.request_json.encode("utf-8")
    if (slot / "request.json").read_bytes() != request_bytes:
        raise ValueError("Case request changed before POST")
    _save(
        slot / "attempt.json",
        {
            "possibly_sent": True,
            "generation_id": packet.generation_id,
            "request_sha256": _hash(packet.request_json.encode("utf-8")),
            "timeout": _remaining(deadline),
        },
    )
    errors: list[str] = []
    try:
        raw = _exchange(
            "POST",
            "/api/chat",
            slot / "request.json",
            slot / "response",
            deadline,
            _hash(request_bytes),
        )
        # Reuse the generator's response completeness and content checks, without transport.
        attempt = generation.generate(packet, lambda _: generation._load(raw.decode("utf-8")))
        if attempt.error is not None or attempt.draft is None:
            raise ValueError(attempt.error)
        incomplete = any(s.state == "unavailable" for s in attempt.draft.sections)
        _save(slot / "draft.json", asdict(attempt.draft))
        _write(
            slot / "draft.md",
            (
                "> MODEL-GENERATED diagnostic capture. Quality assessment pending.\n\n"
                + render(attempt.draft)
            ).encode("utf-8"),
        )
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
    # Capture identity after failed responses too, while the elapsed budget permits it.
    try:
        _metadata(slot / "after", manifest["identity"], deadline)
        _validate(frozen, expected_manifest_sha256)
        _remaining(deadline)
    except Exception as error:
        errors.append(f"After POST: {type(error).__name__}: {error}")
    if errors:
        raise ValueError("; ".join(errors))
    return incomplete


def run(frozen: Path, approval: str, expected_manifest_sha256: str) -> dict[str, Any]:
    """Claim frozen/results once; explicit invocation is the only network entry point.

    Approval is mandatory audit context, not authentication. No retry or resume exists.
    KeyboardInterrupt is re-raised after child cleanup and final audit persistence.
    """
    started = time.monotonic()
    frozen = frozen.resolve()
    deadline = started + LIMIT
    results = frozen / "results"
    results.mkdir(exist_ok=False)
    reason = "capture completed; semantic acceptance pending"
    completed: list[str] = []
    incomplete: list[str] = []
    slot: Path | None = None
    slot_started = started
    try:
        _save(
            results / "running.json",
            {
                "state": "running",
                "approval": approval,
                "possibly_sent": 0,
                "case_order": list(generation.CASES),
                "settings": _settings(),
                "approval_is_authentication": False,
                "expected_manifest_sha256": expected_manifest_sha256,
            },
        )
        if type(approval) is not str or not approval.strip():
            raise ValueError("Approval audit context is required")
        manifest, packets = _validate(frozen, expected_manifest_sha256)
        _save(
            results / "validated.json",
            {
                "candidate_commit": manifest["candidate_commit"],
                "generation_id": manifest["generation_id"],
                "identity": manifest["identity"],
                "expected_manifest_sha256": expected_manifest_sha256,
            },
        )
        for index, (name, packet) in enumerate(zip(generation.CASES, packets, strict=True), 1):
            slot_started = time.monotonic()
            slot = results / f"{index:02}-{name}"
            slot.mkdir(exist_ok=False)
            is_incomplete = _capture_slot(
                frozen, slot, packet, manifest, deadline, expected_manifest_sha256
            )
            _remaining(deadline)
            _save(
                slot / "outcome.json",
                {
                    "capture_complete": True,
                    "draft_incomplete": is_incomplete,
                    "elapsed": time.monotonic() - slot_started,
                },
            )
            if is_incomplete:
                incomplete.append(name)
            completed.append(name)
            slot = None
    except BaseException as error:
        reason = f"{type(error).__name__}: {error}"
        if slot is not None:
            _save(
                slot / "outcome.json",
                {
                    "capture_complete": False,
                    "error": reason,
                    "elapsed": time.monotonic() - slot_started,
                    "possibly_sent": (slot / "attempt.json").exists(),
                },
            )
        if not isinstance(error, Exception):
            raise
    finally:
        attempted = [
            name
            for index, name in enumerate(generation.CASES, 1)
            if (results / f"{index:02}-{name}" / "attempt.json").exists()
        ]
        elapsed = time.monotonic() - started
        if len(completed) == 6 and elapsed > LIMIT:
            reason = "Elapsed ceiling exceeded during capture finalization"
        final = {
            "capture_complete": len(completed) == 6 and elapsed <= LIMIT,
            "completed": completed,
            "draft_incomplete_cases": incomplete,
            "possibly_sent": len(attempted),
            "expected_manifest_sha256": expected_manifest_sha256,
            "attempted": attempted,
            "failed": [name for name in attempted if name not in completed],
            "captured": [
                name
                for index, name in enumerate(generation.CASES, 1)
                if (results / f"{index:02}-{name}" / "response/body.raw").exists()
            ],
            "unsent": [name for name in generation.CASES if name not in attempted],
            "elapsed": elapsed,
            "overrun_seconds": max(0, elapsed - LIMIT),
            "stopping_reason": reason,
            "quality_assessment": "pending Chief/human assessment",
            "server_compute_cancellation_guaranteed": False,
        }
        _save(results / "final.json", final)
    return final
