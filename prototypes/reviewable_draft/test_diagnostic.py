"""Synthetic files and fake processes only; never contact an HTTP server."""

# pyright: reportPrivateUsage=false

import http.client as http_client
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from . import _http
from . import diagnostic as d
from .model import KINDS

IDENTITY = {"version": "synthetic-version", "model": "qwen3:30b", "digest": "a" * 64}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    for name in (*d.RUNTIME, d.INPUT, d.DECLARATION):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((d.ROOT / name).read_bytes())
    git(root, "init", "-q")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic diagnostic source",
    )
    monkeypatch.setattr(d, "ROOT", root)
    return root


@pytest.fixture
def frozen(source: Path, tmp_path: Path) -> Path:
    output = tmp_path / "freeze"
    digest = d.freeze(output, IDENTITY)
    (output.parent / "expected-manifest").write_text(digest)
    return output


def run(frozen: Path, approval: str) -> dict[str, Any]:
    return d.run(frozen, approval, (frozen.parent / "expected-manifest").read_text())


def reply(*, unavailable: bool = False) -> bytes:
    sections: dict[str, Any] = {
        kind: {"state": "draft", "items": [], "notice": "", "review_sources": []} for kind in KINDS
    }
    if unavailable:
        sections["review"] = {
            "state": "unavailable",
            "items": [],
            "notice": "Synthetic analysis unavailable; inspect this passage.",
            "review_sources": ["T1"],
        }
    return d._bytes(
        {
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(sections)},
        }
    )


class FakeHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Path, float]] = []
        self.posts: list[bytes] = []
        self.waits: list[float] = []
        self.body = reply()
        self.status = 200
        self.exit_code = 0
        self.interrupt = False
        self.timeout = False
        self.killed = 0
        self.reaped = 0
        self.identity = dict(IDENTITY)
        self.hook: Callable[[str, str], None] = lambda _method, _endpoint: None

    def spawn(self, command: list[str], **_: Any) -> Any:
        method, endpoint, request, directory, timeout, expected_request_hash = command[-6:]
        output = Path(directory)
        self.calls.append((method, endpoint, output, float(timeout)))
        if method == "POST":
            assert read(output.parent / "attempt.json")["possibly_sent"] is True
            assert read(output.parents[1] / "running.json")["state"] == "running"
            assert expected_request_hash == d._hash(Path(request).read_bytes())
            self.posts.append(Path(request).read_bytes())
            body, status = self.body, self.status
        elif endpoint == "/api/version":
            body, status = d._bytes({"version": self.identity["version"]}), 200
        else:
            body, status = (
                d._bytes(
                    {
                        "models": [
                            {
                                "name": self.identity["model"],
                                "digest": self.identity["digest"],
                            }
                        ]
                    }
                ),
                200,
            )
        (output / "body.raw").write_bytes(body)
        (output / "headers.json").write_bytes(d._bytes({"status": status}))
        self.hook(method, endpoint)
        owner = self

        class Process:
            def wait(self, timeout: float | None = None) -> int:
                if timeout is None:
                    owner.reaped += 1
                    return -9
                owner.waits.append(timeout)
                if method == "POST" and owner.interrupt:
                    raise KeyboardInterrupt
                if method == "POST" and owner.timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                return owner.exit_code if method == "POST" else 0

            def kill(self) -> None:
                owner.killed += 1

        return Process()


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> FakeHTTP:
    fake = FakeHTTP()
    monkeypatch.setattr(d, "_http_process", fake.spawn)
    return fake


def test_freeze_reads_original_once_without_authored_fixture_and_binds_every_runtime(
    source: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http: FakeHTTP,
) -> None:
    original = Path.read_bytes
    reads: list[Path] = []

    def guarded(path: Path) -> bytes:
        assert path.name != "reviewable_draft.json"
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    output = tmp_path / "freeze"
    d.freeze(output, IDENTITY)
    assert reads.count(source / d.INPUT) == 1
    assert not http.calls
    manifest = read(output / "manifest.json")
    assert manifest["candidate_commit"] == git(source, "rev-parse", "HEAD").decode().strip()
    assert manifest["identity"] == IDENTITY
    assert manifest["settings"]["requests"] == 6
    assert manifest["settings"]["seconds"] == 900
    assert manifest["settings"]["per_request_seconds"] == 600
    assert (output / "EXPERIMENT.md").read_bytes() == (source / d.DECLARATION).read_bytes()
    for name, digest in manifest["files"].items():
        assert d._hash((output / name).read_bytes()) == digest
    assert {f"source/{name}" for name in d.RUNTIME} <= manifest["files"].keys()
    snapshots = read(output / "snapshots.json")
    for name, packet in zip(
        d.generation.CASES,
        d._validate(output, d._hash((output / "manifest.json").read_bytes()))[1],
        strict=True,
    ):
        assert snapshots[name]["snapshot_id"] == packet.snapshot.snapshot_id
        assert snapshots[name]["sources"]
        assert packet.generation_id == manifest["generation_id"] + "/" + name
        assert (output / "requests" / f"{name}.json").read_bytes() == packet.request_json.encode()
    assert not (output / "sha256.json").exists()


def test_exclusive_freeze_preserves_existing_edits(frozen: Path) -> None:
    target = frozen / "requests/additional.json"
    target.write_bytes(b"synthetic user edit")
    with pytest.raises(FileExistsError):
        d.freeze(frozen, IDENTITY)
    assert target.read_bytes() == b"synthetic user edit"


@pytest.mark.parametrize(
    "change",
    [
        "packet",
        "snapshot",
        "missing_snapshot",
        "input",
        "source",
        "settings",
        "identity",
        "generation",
        "manifest_hash",
    ],
)
def test_invalid_freeze_is_claimed_and_rejected_before_any_network(
    frozen: Path,
    http: FakeHTTP,
    change: str,
) -> None:
    manifest = read(frozen / "manifest.json")
    if change in {"packet", "snapshot", "input", "source"}:
        name = {
            "packet": "requests/additional.json",
            "snapshot": "snapshots.json",
            "input": "pairs.json",
            "source": "source/prototypes/reviewable_draft/model.py",
        }[change]
        (frozen / name).write_bytes(b"synthetic changed bytes")
        # A recomputed manifest hash cannot conceal packet/input/source drift.
        manifest["files"][name] = d._hash(b"synthetic changed bytes")
    elif change == "missing_snapshot":
        (frozen / "snapshots.json").unlink()
    elif change == "settings":
        manifest["settings"]["requests"] = 7
    elif change == "identity":
        manifest["identity"]["version"] = "different-valid-version"
    elif change == "generation":
        manifest["generation_id"] = ""
    else:
        manifest["files"]["snapshots.json"] = "b" * 64
    (frozen / "manifest.json").write_bytes(d._bytes(manifest))
    (frozen.parent / "expected-manifest").write_text(d._hash(d._bytes(manifest)))
    final = run(frozen, "Synthetic approved audit context")
    assert not final["capture_complete"] and final["possibly_sent"] == 0
    assert final["unsent"] == list(d.generation.CASES)
    assert not http.calls
    before = {p: p.read_bytes() for p in frozen.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        run(frozen, "Different output intent cannot resume")
    assert all(p.read_bytes() == body for p, body in before.items())


@pytest.mark.parametrize(
    "field,value",
    [("version", ""), ("version", None), ("model", "other"), ("digest", " "), ("digest", "short")],
)
def test_identity_is_declared_without_metadata_lookup(
    source: Path,
    tmp_path: Path,
    http: FakeHTTP,
    field: str,
    value: Any,
) -> None:
    identity: dict[str, Any] = dict(IDENTITY)
    identity[field] = value
    with pytest.raises(ValueError):
        d.freeze(tmp_path / "invalid", identity)
    assert not http.calls


@pytest.mark.parametrize("name", [d.INPUT, d.DECLARATION, *d.RUNTIME])
def test_current_dirty_inputs_or_runtime_reject_unsent(
    frozen: Path,
    source: Path,
    http: FakeHTTP,
    name: str,
) -> None:
    path = source / name
    path.write_bytes(path.read_bytes() + b"\n")
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 0 and "Dirty" in final["stopping_reason"]
    assert not http.calls


def test_committed_input_drift_and_stale_import_are_rejected(
    frozen: Path,
    source: Path,
    http: FakeHTTP,
) -> None:
    path = source / d.INPUT
    path.write_bytes(path.read_bytes() + b"\n")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic drift",
    )
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 0 and not http.calls
    with pytest.raises(ValueError, match="input hash"):
        d.freeze(frozen.parent / "changed-input", IDENTITY)
    path.write_bytes((frozen / "pairs.json").read_bytes())
    runtime = source / d.RUNTIME[-1]
    runtime.write_bytes(runtime.read_bytes() + b"\n")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic runtime drift",
    )
    with pytest.raises(ValueError, match="Imported runtime changed"):
        d.freeze(frozen.parent / "stale-import", IDENTITY)


@pytest.mark.parametrize("unavailable", [False, True])
def test_six_fixed_serial_requests_with_metadata_and_no_quality_claim(
    frozen: Path,
    http: FakeHTTP,
    unavailable: bool,
) -> None:
    http.body = reply(unavailable=unavailable)
    before = {p: p.read_bytes() for p in frozen.rglob("*") if p.is_file()}
    final = run(frozen, "Chief's synthetic approval context")
    assert final["capture_complete"] and final["possibly_sent"] == 6
    assert final["completed"] == list(d.generation.CASES) and final["unsent"] == []
    assert final["draft_incomplete_cases"] == (list(d.generation.CASES) if unavailable else [])
    assert final["quality_assessment"] == "pending Chief/human assessment"
    assert [(m, p) for m, p, _, _ in http.calls] == [
        ("GET", "/api/version"),
        ("GET", "/api/tags"),
        ("POST", "/api/chat"),
        ("GET", "/api/version"),
        ("GET", "/api/tags"),
    ] * 6
    for index, name in enumerate(d.generation.CASES, 1):
        slot = frozen / "results" / f"{index:02}-{name}"
        assert http.posts[index - 1] == (frozen / "requests" / f"{name}.json").read_bytes()
        assert (slot / "response/body.raw").read_bytes() == http.body
        assert "MODEL-GENERATED diagnostic" in (slot / "draft.md").read_text()
        assert read(slot / "outcome.json")["capture_complete"]
    assert all(p.read_bytes() == body for p, body in before.items())
    with pytest.raises(FileExistsError):
        run(frozen, "No second invocation")
    assert len(http.posts) == 6


@pytest.mark.parametrize(
    "failure", ["malformed", "truncated", "length", "http", "transport", "timeout"]
)
def test_raw_failure_stops_without_retry_and_retains_prior_success(
    frozen: Path,
    http: FakeHTTP,
    failure: str,
) -> None:
    failed_body = b'{"partial":'

    def after_first(method: str, endpoint: str) -> None:
        if len(http.posts) == 1 and method == "GET" and endpoint == "/api/tags":
            http.body = failed_body
            if failure == "length":
                value = json.loads(reply())
                value["done_reason"] = "length"
                http.body = d._bytes(value)
            elif failure == "http":
                http.status = 503
            elif failure in {"transport", "truncated"}:
                http.exit_code = 1
            elif failure == "timeout":
                http.timeout = True

    http.hook = after_first
    final = run(frozen, "Synthetic approval")
    assert not final["capture_complete"] and final["possibly_sent"] == 2
    assert final["completed"] == ["additional"]
    assert final["unsent"] == list(d.generation.CASES[2:])
    first = frozen / "results/01-additional/draft.md"
    assert first.exists()
    assert (frozen / "results/02-unit_equivalence/response/body.raw").read_bytes() == http.body
    assert len(http.posts) == 2
    if failure == "timeout":
        assert http.killed == 1 and http.reaped == 1


@pytest.mark.parametrize("field", ["version", "model", "digest"])
@pytest.mark.parametrize("after", [False, True])
def test_metadata_identity_drift_stops_before_next_post(
    frozen: Path,
    http: FakeHTTP,
    field: str,
    after: bool,
) -> None:
    if after:

        def drift(method: str, _: str) -> None:
            if method == "POST":
                http.identity[field] = "different"

        http.hook = drift
    else:
        http.identity[field] = "different"
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == int(after)
    assert len(http.posts) == int(after)
    assert "identity drift" in final["stopping_reason"]
    if after:
        assert (frozen / "results/01-additional/response/body.raw").exists()


def test_drift_during_metadata_is_revalidated_before_post(
    frozen: Path,
    source: Path,
    http: FakeHTTP,
) -> None:
    def drift(_: str, endpoint: str) -> None:
        if endpoint == "/api/tags":
            (source / d.INPUT).write_bytes(b"synthetic drift")

    http.hook = drift
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 0 and not http.posts


def test_blank_approval_consumes_claim_without_network(frozen: Path, http: FakeHTTP) -> None:
    final = run(frozen, " ")
    assert final["possibly_sent"] == 0 and "Approval" in final["stopping_reason"]
    assert not http.calls


def test_keyboard_interrupt_kills_reaps_and_records_possible_send(
    frozen: Path,
    http: FakeHTTP,
) -> None:
    http.interrupt = True
    with pytest.raises(KeyboardInterrupt):
        run(frozen, "Synthetic approval")
    assert http.killed == 1 and http.reaped == 1
    final = read(frozen / "results/final.json")
    assert final["possibly_sent"] == 1 and len(final["unsent"]) == 5
    assert "KeyboardInterrupt" in final["stopping_reason"]
    assert len(http.calls) == 3  # Stop all; no metadata on interruption.
    assert (frozen / "results/01-additional/response/body.raw").read_bytes() == http.body


def test_elapsed_budget_includes_metadata_and_limits_child_wait(
    frozen: Path,
    http: FakeHTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(d.time, "monotonic", lambda: now[0])

    def elapsed(_: str, __: str) -> None:
        now[0] += 170

    http.hook = elapsed
    final = run(frozen, "Synthetic approval")
    assert len(http.posts) == 1 and not final["capture_complete"]
    assert [timeout for _, _, _, timeout in http.calls] == [600, 600, 560, 390, 220, 50]
    assert http.waits == [600, 560, 390, 220, 50]
    assert final["overrun_seconds"] == 120
    assert "deadline" in final["stopping_reason"]


@pytest.mark.parametrize("trickle", [False, True])
def test_hung_child_is_really_killed_and_reaped_without_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    trickle: bool,
) -> None:
    output = tmp_path / "exchange"
    script = (
        "import os, pathlib, time; "
        f"p=pathlib.Path({str(output)!r}); "
        "(p/'pid').write_text(str(os.getpid())); "
        "(p/'body.raw').write_bytes(b'partial')"
    )

    script += (
        "\nwith (p/'body.raw').open('ab', buffering=0) as stream:\n"
        "    while True:\n        stream.write(b'x'); time.sleep(0.01)\n"
        if trickle
        else "; time.sleep(10)"
    )

    def command(*_: Any) -> list[str]:
        return [sys.executable, "-B", "-c", script]

    monkeypatch.setattr(d, "_command", command)
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        d._exchange("GET", "/api/version", None, output, started + 0.3)
    assert time.monotonic() - started < 2
    pid = int((output / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert (output / "body.raw").read_bytes().startswith(b"partial")
    assert "TimeoutExpired" in read(output / "exchange.json")["error"]


@pytest.mark.parametrize("failure", ["none", "partial", "short", "http"])
def test_http_worker_captures_incrementally_to_exclusive_files_with_fixed_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    seen: list[tuple[Any, ...]] = []
    output = tmp_path / "exchange"
    output.mkdir()
    request = tmp_path / "request.json"
    request.write_bytes(b'{"synthetic":true}')

    class Response:
        status = 503 if failure == "http" else 200
        length: int | None = 9 if failure == "short" else None
        reads = 0

        def getheaders(self) -> list[tuple[str, str]]:
            return [("Synthetic", "header")]

        def read1(self, size: int) -> bytes:
            self.reads += 1
            assert size == 65536
            if self.reads == 1:
                return b"first"
            assert (output / "body.raw").read_bytes() == b"first"
            if failure == "partial":
                raise http_client.IncompleteRead(b"tail", 4)
            return b""

    class Connection:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            seen.append((*args, kwargs))

        def request(self, *args: Any) -> None:
            seen.append(args)

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            seen.append(("closed",))

    monkeypatch.setattr(_http.http.client, "HTTPConnection", Connection)
    code = _http.capture("POST", "/api/chat", request, output, 0.1, d._hash(request.read_bytes()))
    assert seen[0] == ("127.0.0.1", 11434, {"timeout": 0.1})
    assert seen[1][:3] == ("POST", "/api/chat", request.read_bytes())
    assert seen[-1] == ("closed",)
    assert code == int(failure in {"partial", "short"})
    assert (output / "body.raw").read_bytes() == (
        b"firsttail" if failure == "partial" else b"first"
    )
    assert read(output / "headers.json")["status"] == Response.status
    if code:
        assert (output / "error.json").exists()
    with pytest.raises(FileExistsError):
        _http.capture("POST", "/api/chat", request, output, 0.1, d._hash(request.read_bytes()))
    assert (output / "body.raw").read_bytes().startswith(b"first")
    with pytest.raises(ValueError, match="fixed"):
        _http.capture("GET", "http://elsewhere.invalid", None, output, 0.1)


def test_descendant_commit_can_record_freeze_before_capture(
    frozen: Path,
    source: Path,
    http: FakeHTTP,
) -> None:
    candidate = read(frozen / "manifest.json")["candidate_commit"]
    (source / "synthetic-freeze.json").write_bytes((frozen / "manifest.json").read_bytes())
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic freeze record",
    )
    assert git(source, "rev-parse", "HEAD").decode().strip() != candidate
    final = run(frozen, "Synthetic approval")
    assert final["capture_complete"] and len(http.posts) == 6
    metadata = read(frozen / "results/validated.json")
    assert metadata["candidate_commit"] == candidate
    assert metadata["identity"] == IDENTITY
    assert metadata["expected_manifest_sha256"] == d._hash((frozen / "manifest.json").read_bytes())


def test_descendant_cannot_commit_changed_runtime_and_still_use_old_freeze(
    frozen: Path,
    source: Path,
    http: FakeHTTP,
) -> None:
    path = source / d.RUNTIME[-1]
    path.write_bytes(path.read_bytes() + b"\n")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Synthetic changed runtime",
    )
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 0 and not http.calls
    assert "differs from candidate" in final["stopping_reason"]


@pytest.mark.parametrize("change", ["wrong_hash", "blank_hash", "self_consistent_identity"])
def test_expected_manifest_hash_pins_even_self_consistent_identity_rewrites(
    frozen: Path,
    http: FakeHTTP,
    change: str,
) -> None:
    expected = (frozen.parent / "expected-manifest").read_text()
    if change == "self_consistent_identity":
        manifest = read(frozen / "manifest.json")
        manifest["identity"]["version"] = "rewritten-valid-version"
        body = d._bytes(manifest["identity"])
        (frozen / "identity.json").write_bytes(body)
        manifest["files"]["identity.json"] = d._hash(body)
        (frozen / "manifest.json").write_bytes(d._bytes(manifest))
    elif change == "wrong_hash":
        expected = "f" * 64
    else:
        expected = ""
    final = d.run(frozen, "Synthetic approval", expected)
    assert final["possibly_sent"] == 0 and not http.calls
    assert not final["capture_complete"]
    assert read(frozen / "results/running.json")["expected_manifest_sha256"] == expected
    assert final["expected_manifest_sha256"] == expected


@pytest.mark.parametrize("change", ["duplicate", "count", "missing", "hash"])
def test_corpus_hash_unique_count_and_selected_ids_are_checked(
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    rows: list[dict[str, Any]] = json.loads((source / d.INPUT).read_bytes())
    if change == "duplicate":
        rows[-1]["id"] = rows[0]["id"]
    elif change == "count":
        rows.pop()
    elif change == "missing":
        next(r for r in rows if r["id"] == "additional")["id"] = "synthetic-other-case"
    data = d._bytes(rows)
    if change != "hash":
        monkeypatch.setattr(d, "INPUT_HASH", d._hash(data))
    with pytest.raises(ValueError):
        d._snapshots(data)


def test_prepared_packet_must_match_original_snapshot_and_host_generation(
    source: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    prepare = d.generation.prepare

    def wrong(
        snapshots: dict[str, d.Snapshot], generation_id: str
    ) -> tuple[d.generation.Prepared, ...]:
        packets = prepare(snapshots, generation_id)
        return (replace(packets[0], generation_id="wrong-host-generation"), *packets[1:])

    monkeypatch.setattr(d.generation, "prepare", wrong)
    with pytest.raises(ValueError, match="snapshot/generation"):
        d.freeze(tmp_path / "wrong-packet", IDENTITY)


def test_failed_artifact_write_cannot_submit_another_post(
    frozen: Path,
    http: FakeHTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write = d._write

    def full(path: Path, body: bytes) -> None:
        if path.name == "draft.md":
            raise OSError("Synthetic disk full")
        write(path, body)

    monkeypatch.setattr(d, "_write", full)
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 1 and len(http.posts) == 1
    assert "disk full" in final["stopping_reason"]
    assert (frozen / "results/01-additional/response/body.raw").read_bytes() == http.body


def test_copied_request_drift_during_metadata_is_rejected_unsent(
    frozen: Path,
    http: FakeHTTP,
) -> None:
    def drift(_: str, endpoint: str) -> None:
        if endpoint == "/api/tags":
            (frozen / "results/01-additional/request.json").write_bytes(b"synthetic user edit")

    http.hook = drift
    final = run(frozen, "Synthetic approval")
    assert final["possibly_sent"] == 0 and not http.posts
    assert "request changed" in final["stopping_reason"]
    assert (frozen / "results/01-additional/request.json").read_bytes() == b"synthetic user edit"


def test_worker_rejects_request_hash_drift_before_connection_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    request = tmp_path / "request.json"
    request.write_bytes(b"synthetic changed request")
    output = tmp_path / "exchange"
    output.mkdir()

    class Connection:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def request(self, *_: Any) -> None:
            calls.append("unexpected network request")

        def close(self) -> None:
            pass

    monkeypatch.setattr(_http.http.client, "HTTPConnection", Connection)
    assert _http.capture("POST", "/api/chat", request, output, 0.1, "f" * 64) == 1
    assert not calls and (output / "body.raw").read_bytes() == b""
    assert "hash changed" in read(output / "error.json")["error"]
