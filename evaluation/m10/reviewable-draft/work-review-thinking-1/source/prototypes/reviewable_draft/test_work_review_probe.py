"""Offline seven-case capture and host assessment gates; no model or HTTP calls."""

# pyright: reportPrivateUsage=false

import select
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from . import work_review_probe as p
from .test_runtime_probe import event, git, line, read

REAL_ROOT = p.ROOT


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    for name in p.NAMES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REAL_ROOT / name).read_bytes())
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
        "Synthetic retention source",
    )
    monkeypatch.setattr(p, "ROOT", root)
    monkeypatch.setattr(p.examples, "PROPOSAL", root / p.PROPOSAL)
    monkeypatch.setattr(p.examples, "PAIRS", root / p.d.INPUT)
    return root


@pytest.fixture
def frozen(source: Path, tmp_path: Path) -> tuple[Path, str]:
    output = tmp_path / "freeze"
    return output, p.freeze(output, dict(p.IDENTITY))


class HTTP:
    def __init__(self) -> None:
        self.now = 0.0
        self.calls: list[tuple[str, str, float]] = []
        self.posts: list[bytes] = []
        self.raw = line(event('{"groups":[["T1"]]}', done=True))
        self.failure = ""
        self.identity = dict(p.IDENTITY)
        self.hook: Callable[[str, Path], None] = lambda _endpoint, _directory: None

    def clock(self) -> float:
        return self.now

    def exchange(
        self,
        method: str,
        endpoint: str,
        request: Path | None,
        directory: Path,
        deadline: float,
        pin: str | None,
    ) -> dict[str, Any]:
        self.calls.append((method, endpoint, deadline - self.now))
        directory.mkdir(parents=True, exist_ok=False)
        self.hook(endpoint, directory)
        if endpoint == "/api/chat":
            assert request is not None
            data = request.read_bytes()
            assert p._hash(data) == pin == p.http.CHAT_PINS[len(self.posts)]
            # A durable conservative attempt must precede the launch, for every case.
            assert read(directory.parent / "attempt.json")["possibly_sent"] is True
            self.posts.append(data)
            raw = self.raw
        elif endpoint == "/api/version":
            raw = p._bytes(dict(version=self.identity["version"]))
        elif endpoint == "/api/tags":
            raw = p._bytes(
                dict(models=[dict(name=self.identity["model"], digest=self.identity["digest"])])
            )
        else:
            assert endpoint == "/api/show" and method == "POST" and request is not None
            assert request.read_bytes() == p.http.SHOW and pin == p._hash(p.http.SHOW)
            raw = p._bytes(
                {k: self.identity[k] for k in ("capabilities", "thinking", "parameters")}
            )
        (directory / "body.raw").write_bytes(raw)
        (directory / "chunks.jsonl").write_bytes(
            line(dict(offset=0, length=len(raw), seconds=0.01))
        )
        p._save(directory / "headers.json", dict(status=200, headers=[]))
        state: dict[str, Any] = dict(error=None, returncode=0, timed_out=False)
        self.now += 0.1
        if endpoint == "/api/chat" and self.failure:
            state.update(error="Synthetic " + self.failure, returncode=1)
            if self.failure == "timeout":
                self.now = deadline
                state.update(timed_out=True, killed=True, reaped=True)
        p._save(directory / "exchange.json", state)
        if endpoint == "/api/chat" and self.failure == "interrupt":
            raise KeyboardInterrupt
        return state


@pytest.fixture
def http() -> HTTP:
    return HTTP()


def accepted(_slot: str, _result: p.review.Result, _deadline: float) -> dict[str, Any]:
    return dict(critical=False, assessment="Authored test host verdict; not model-quality evidence")


def run(frozen: tuple[Path, str], http: HTTP) -> dict[str, Any]:
    return p._run(
        *frozen[:1], "Authored offline approval", frozen[1], http.exchange, http.clock, accepted
    )


def test_exact_seven_packets_freeze_full_snapshots_and_separate_internal_baseline(
    frozen: tuple[Path, str],
) -> None:
    output, pin = frozen
    manifest, packets = p._validate(output, pin)
    assert p.CASES == (
        "partial_coordination_retracted",
        "cancellation_with_new_task",
        "qualified_external_timing",
        "additional",
        "accepted_status_answer",
        "unit_equivalence",
        "authored_longer_context",
    )
    assert len(packets) == 7 and manifest["generation_id"].startswith("work-review-probe-")
    settings = manifest["settings"]
    assert (
        settings["requests"],
        settings["repetitions"],
        settings["seconds"],
        settings["retries"],
    ) == (7, 1, 1500, 0)
    assert (settings["per_generation_seconds"], settings["per_metadata_seconds"]) == (180, 10)
    bindings = read(output / "bindings.json")
    snapshots = read(output / "snapshots.json")
    for slot, case, packet, wire_pin in zip(
        p.SLOTS, p.CASES, packets, p.http.CHAT_PINS, strict=True
    ):
        wire = p._read(output, f"requests/{slot}.json")
        body = p._load(wire)
        baseline = packet.payload()
        expected = {
            **baseline,
            "model": p.http.MODEL,
            "stream": True,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 32768},
        }
        assert wire == p._bytes(expected) and p._hash(wire) == wire_pin
        assert body["options"] == {"num_ctx": 32768, "temperature": 0}
        assert body["messages"] == baseline["messages"] and body["format"] == baseline["format"]
        assert "writing" not in p._load(body["messages"][1]["content"].encode())
        assert packet.generation_id == f"{manifest['generation_id']}/{case}"
        assert snapshots[case]["handwritten_text"] == packet.snapshot.handwritten_text
        assert snapshots[case]["transcript"] == packet.snapshot.transcript
        assert bindings[slot]["snapshot_id"] == packet.snapshot.snapshot_id
        assert bindings[slot]["snapshot_sha256"] == p._hash(
            p._read(output, f"snapshots/{slot}.json")
        )
        assert bindings[slot]["request_sha256"] == wire_pin
        assert (
            bindings[slot]["model_neutral_payload_sha256"]
            == p._hash(packet.payload_json.encode())
            != wire_pin
        )
    assert p._inventory(output) == {**manifest["files"], "manifest.json": pin}
    assert read(output / "import-baselines.json") == p.LOADED
    assert all(p.LOADED[n] == h for n, h in p.d.LOADED.items())
    assert p._hash(p._read(output, "source/" + p.d.INPUT)) == p.d.INPUT_HASH
    with pytest.raises(FileExistsError):
        p.freeze(output, dict(p.IDENTITY))


def test_seven_serial_generations_have_exact_accounting_and_replay_without_semantic_pass(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    returned = run(frozen, http)
    final = returned["accounting"]
    output, pin = frozen
    assert final["capture_complete"] and final["possibly_sent"] == len(http.posts) == 7
    assert final["completed"] == list(p.SLOTS) and not final["failed"] and not final["unsent"]
    assert "no automated model-quality PASS" in final["stop_reason"]
    assert len(http.calls) == 49
    assert all(0 < t <= (180 if endpoint == "/api/chat" else 10) for _, endpoint, t in http.calls)
    _, packets = p._validate(output, pin)
    for row, packet, body in zip(final["slots"], packets, http.posts, strict=True):
        slot = output / "results" / row["slot"]
        assert read(slot / "outcome.json") == row
        assert (
            read(slot / "attempt.json")["request_sha256"] == row["request_sha256"] == p._hash(body)
        )
        assert row["generation_id"] == packet.generation_id
        assert row["snapshot_id"] == packet.snapshot.snapshot_id
        result = p.review.decode(packet, p._stream(slot / "response").content)
        assert (slot / "result.json").read_bytes() == p._bytes(p.asdict(result))
        assert (slot / "work-review.md").read_text() == p.review.render_result(result)
        assert "Authored" not in (slot / "work-review.md").read_text()
    seal = read(output / "results/manifest.json")
    assert final == seal["accounting"] and final["authoritative"]
    assert seal["files"] == {
        n: h for n, h in p._inventory(output / "results").items() if n != "manifest.json"
    }
    assert returned["post_seal_observation"]["sealed"]
    with pytest.raises(FileExistsError):
        run(frozen, http)
    assert len(http.posts) == 7


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "longer",
        "mapping",
        "annex",
        "preview",
        "review_source",
        "example_source",
        "request",
        "manifest",
        "identity",
        "declaration",
        "input",
        "snapshot",
        "bindings",
        "import",
        "inherited_import",
        "pin",
        "extra",
    ],
)
def test_preflight_tamper_consumes_results_and_sends_nothing(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    output, pin = frozen
    paths = dict(
        source=source / p.RUNTIME[-1],
        longer=source / p.PROPOSAL / "authored-longer-input.json",
        mapping=source / p.PROPOSAL / "examples.json",
        annex=source / p.PROPOSAL / "sources.md",
        preview=source / p.PROPOSAL / p.PREVIEWS[-1],
        review_source=source / p.HERE / "work_review.py",
        example_source=source / p.HERE / "work_review_examples.py",
        request=output / f"requests/{p.SLOTS[0]}.json",
        manifest=output / "manifest.json",
        identity=output / "identity.json",
        declaration=source / p.DECLARATION,
        input=source / p.d.INPUT,
        snapshot=output / "snapshots.json",
        bindings=output / "bindings.json",
        extra=output / "extra.json",
    )
    if change in ("import", "inherited_import"):
        monkeypatch.setitem(
            p.LOADED, p.d.RUNTIME[0] if change == "inherited_import" else p.RUNTIME[-1], "f" * 64
        )
    elif change == "pin":
        pin = "f" * 64
    else:
        paths[change].write_bytes(b"Synthetic protected edit")
    final = p._run(output, "Authored approval", pin, http.exchange, http.clock, accepted)[
        "accounting"
    ]
    assert not http.calls and final["possibly_sent"] == 0 and final["unsent"] == list(p.SLOTS)
    assert len(final["slots"]) == 7 and not final["capture_complete"]
    with pytest.raises(FileExistsError):
        run(frozen, http)


@pytest.mark.parametrize("key", list(p.IDENTITY))
@pytest.mark.parametrize("phase", ["before", "after"])
def test_identity_default_drift_stops_whole_experiment(
    frozen: tuple[Path, str],
    http: HTTP,
    key: str,
    phase: str,
) -> None:
    if phase == "before":
        http.identity[key] = "changed"
    else:

        def drift(endpoint: str, _: Path) -> None:
            if endpoint == "/api/chat":
                http.identity[key] = "changed"

        http.hook = drift
    final = run(frozen, http)["accounting"]
    assert len(http.posts) == final["possibly_sent"] == (0 if phase == "before" else 1)
    assert not final["capture_complete"]
    assert final["unsent"] == list(p.SLOTS[0 if phase == "before" else 1 :])


@pytest.mark.parametrize(
    "failure", ["timeout", "exit", "interrupt", "stream", "structural", "reference"]
)
def test_first_failure_keeps_partial_bytes_and_all_seven_bound_slots(
    frozen: tuple[Path, str],
    http: HTTP,
    failure: str,
) -> None:
    if failure in ("timeout", "exit", "interrupt"):
        http.failure = failure
        http.raw = line(event(thinking="Authored partial")) + b'{"message":"unfinished\xc3'
    elif failure == "stream":
        http.raw = line(event('{"groups":[]}', done=True)) + line(event(done=True))
    elif failure == "structural":
        http.raw = line(event("{}", done=True))
    else:
        http.raw = line(event('{"groups":[["T999"]]}', done=True))
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            run(frozen, http)
        final = read(frozen[0] / "results/manifest.json")["accounting"]
    else:
        final = run(frozen, http)["accounting"]
    assert final["possibly_sent"] == len(http.posts) == 1 and final["failed"] == [p.SLOTS[0]]
    assert final["unsent"] == list(p.SLOTS[1:]) and not final["capture_complete"]
    assert len(http.calls) == (4 if failure in ("timeout", "exit", "interrupt") else 7)
    bindings = read(frozen[0] / "bindings.json")
    for row in final["slots"]:
        assert all(row[k] == v for k, v in bindings[row["slot"]].items())
    slot = frozen[0] / "results" / p.SLOTS[0]
    assert (slot / "response/body.raw").read_bytes() == http.raw
    assert (slot / "observed.json").exists() and not (slot / "work-review.md").exists()
    assert not (slot / "result.json").exists()


@pytest.mark.parametrize(
    "boundary", ["validation", "metadata", "generation", "outcome", "final", "seal"]
)
def test_shared_1500_seconds_includes_every_stage_and_seal_has_separate_observation(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    validate, save = p._validate, p._save

    def slow_validate(
        output: Path, pin: str
    ) -> tuple[dict[str, Any], tuple[p.review.Prepared, ...]]:
        result = validate(output, pin)
        http.now = 1501
        return result

    def slow_save(path: Path, value: object) -> None:
        save(path, value)
        if path.name == {
            "outcome": "outcome.json",
            "final": "final.json",
            "seal": "manifest.json",
        }.get(boundary):
            http.now = 1501

    if boundary == "validation":
        monkeypatch.setattr(p, "_validate", slow_validate)
    elif boundary == "metadata":
        http.hook = lambda _e, _d: setattr(http, "now", 1501)
    elif boundary == "generation":
        validations = 0

        def short_budget(
            output: Path, pin: str
        ) -> tuple[dict[str, Any], tuple[p.review.Prepared, ...]]:
            nonlocal validations
            validations += 1
            result = validate(output, pin)
            if validations == 3:
                http.now = 1480
            return result

        monkeypatch.setattr(p, "_validate", short_budget)
        http.failure = "timeout"
    else:
        monkeypatch.setattr(p, "_save", slow_save)
    returned = run(frozen, http)
    final = returned["accounting"]
    assert final == read(frozen[0] / "results/manifest.json")["accounting"]
    assert final["capture_complete"] is (boundary == "seal")
    assert returned["post_seal_observation"]["deadline_reached"]
    if boundary == "generation":
        assert http.calls[-1][2] <= 20 and len(http.posts) == 1
    elif boundary in ("validation", "metadata"):
        assert not http.posts
    else:
        snapshot = read(frozen[0] / "results/final.json")
        assert (
            not snapshot["authoritative"] and "pre-save snapshot" in snapshot["accounting_boundary"]
        )
        assert "before manifest.json write" in final["accounting_boundary"]
        if boundary == "final":
            assert snapshot["capture_complete"] and not final["capture_complete"]
        if boundary == "seal":
            assert (
                final["overrun_seconds"] == 0
                and returned["post_seal_observation"]["overrun_seconds"] == 1
            )


@pytest.mark.parametrize("artifact", ["progress.json", "result.json", "inventory", "final.json"])
@pytest.mark.parametrize("interrupt", [False, True])
def test_independent_artifacts_preserve_counts_and_original_interrupt(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
    interrupt: bool,
) -> None:
    save, inventory = p._save, p._inventory

    def fail_save(path: Path, value: object) -> None:
        if path.name == artifact:
            raise OSError("Synthetic storage failure")
        save(path, value)

    def fail_inventory(root: Path, *, omit_results: bool = False) -> dict[str, str]:
        if root.name == "results" and artifact == "inventory":
            raise OSError("Synthetic inventory failure")
        return inventory(root, omit_results=omit_results)

    monkeypatch.setattr(p, "_save", fail_save)
    monkeypatch.setattr(p, "_inventory", fail_inventory)
    if interrupt:
        http.failure = "interrupt"
        with pytest.raises(KeyboardInterrupt):
            run(frozen, http)
    else:
        final = run(frozen, http)["accounting"]
        assert not final["capture_complete"]
    output = frozen[0] / "results"
    saved = read(output / ("final.json" if artifact == "inventory" else "manifest.json"))
    final = saved if artifact == "inventory" else saved["accounting"]
    assert final["possibly_sent"] == (
        1 if interrupt or artifact in ("progress.json", "result.json") else 7
    )
    assert len(final["slots"]) == 7
    if artifact == "progress.json":
        assert (output / p.SLOTS[0] / "observed.json").exists()


def test_inherited_parser_and_tail_timing_are_exact_and_not_reimplemented(tmp_path: Path) -> None:
    assert p.Stream is p.runtime.Stream and p._stream is p.runtime._stream
    prefix = line(event("early", thinking="early thought"))
    (tmp_path / "body.raw").write_bytes(prefix + line(event("late", done=True)))
    (tmp_path / "chunks.jsonl").write_bytes(line(dict(offset=0, length=len(prefix), seconds=2)))
    stream = p._stream(tmp_path)
    assert stream.content == "earlylate" and not stream.progress()["valid"]
    assert (stream.first_byte, stream.first_thinking, stream.first_content) == (2, 2, 2)


def test_depth_one_and_unchanged_descendant_use_only_committed_files(
    source: Path,
    frozen: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git(
        source,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-qm",
        "Publish freeze",
    )
    p._validate(*frozen)
    shallow = tmp_path / "shallow"
    subprocess.check_output(
        ["git", "clone", "--quiet", "--depth=1", source.as_uri(), str(shallow)],
        stderr=subprocess.PIPE,
    )
    assert git(shallow, "rev-parse", "--is-shallow-repository").strip() == b"true"
    monkeypatch.setattr(p, "ROOT", shallow)
    monkeypatch.setattr(p.examples, "PROPOSAL", shallow / p.PROPOSAL)
    monkeypatch.setattr(p.examples, "PAIRS", shallow / p.d.INPUT)
    output = tmp_path / "shallow-freeze"
    p._validate(output, p.freeze(output, dict(p.IDENTITY)))


def test_import_and_pure_preparation_cannot_connect() -> None:
    script = """import socket
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("No network"))
socket.create_connection = socket.socket.connect
from prototypes.reviewable_draft import work_review_probe as p
source = {name: (p.ROOT / name).read_bytes() for name in p.NAMES}
files, packets = p._files(source, p._identity(p.IDENTITY), "work-review-probe-" + "a" * 32)
assert len(packets) == 7
"""
    subprocess.check_output([sys.executable, "-c", script], cwd=REAL_ROOT, stderr=subprocess.PIPE)


def test_assessment_occurs_after_every_saved_render_before_any_later_request(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    seen: list[str] = []
    http.raw = line(event('{"groups":[]}', done=True))

    def assess(slot: str, result: p.review.Result, deadline: float) -> dict[str, Any]:
        assert len(http.posts) == len(seen) + 1
        assert deadline == 1500 and http.now < deadline
        directory = frozen[0] / "results" / slot
        assert read(directory / "result.json")["binding"] == result.binding
        assert (directory / "work-review.md").read_text() == p.review.render_result(result)
        assert not result.groups and not (directory / "meaning-review.json").exists()
        seen.append(slot)
        return accepted(slot, result, deadline)

    def before_request(endpoint: str, directory: Path) -> None:
        if endpoint == "/api/version" and directory.parent.name == "before":
            assert len(seen) == len(http.posts)
            for slot in seen:
                verdict = read(frozen[0] / "results" / slot / "meaning-review.json")
                assert verdict["critical"] is False and verdict["assessment"].strip()

    http.hook = before_request
    final = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, assess)[
        "accounting"
    ]
    assert seen == list(p.SLOTS) and final["capture_complete"]


@pytest.mark.parametrize("critical_slot", [0, 3, 6])
def test_critical_host_assessment_keeps_render_and_leaves_later_slots_unsent(
    frozen: tuple[Path, str],
    http: HTTP,
    critical_slot: int,
) -> None:
    seen: list[str] = []

    def assess(slot: str, _result: p.review.Result, _deadline: float) -> dict[str, Any]:
        seen.append(slot)
        return dict(critical=slot == p.SLOTS[critical_slot], assessment="Authored host decision")

    final = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, assess)[
        "accounting"
    ]
    assert len(http.posts) == len(seen) == critical_slot + 1
    assert not final["capture_complete"] and "Critical host meaning" in final["stop_reason"]
    assert final["unsent"] == list(p.SLOTS[critical_slot + 1 :])
    slot = frozen[0] / "results" / p.SLOTS[critical_slot]
    assert (slot / "result.json").exists() and (slot / "work-review.md").exists()
    assert read(slot / "meaning-review.json")["critical"] is True


@pytest.mark.parametrize(
    "verdict",
    [
        None,
        {},
        {"critical": False},
        {"critical": 0, "assessment": "Authored"},
        {"critical": False, "assessment": " "},
        {"critical": False, "assessment": 1},
        {"critical": False, "assessment": "Authored", "extra": True},
    ],
)
def test_invalid_host_verdict_stops_with_valid_render_saved(
    frozen: tuple[Path, str],
    http: HTTP,
    verdict: Any,
) -> None:
    final = p._run(
        frozen[0],
        "Authored approval",
        frozen[1],
        http.exchange,
        http.clock,
        lambda _s, _r, _d: verdict,
    )["accounting"]
    slot = frozen[0] / "results" / p.SLOTS[0]
    assert not final["capture_complete"] and len(http.posts) == 1
    assert (slot / "result.json").exists() and (slot / "work-review.md").exists()
    assert not (slot / "meaning-review.json").exists()
    assert final["unsent"] == list(p.SLOTS[1:])


@pytest.mark.parametrize("failure", ["exception", "timeout", "interrupt", "save", "late_save"])
def test_callback_and_assessment_save_failures_stop_after_saved_render(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    save = p._save

    def assess(slot: str, result: p.review.Result, deadline: float) -> dict[str, Any]:
        if failure == "exception":
            raise OSError("Authored host failure")
        if failure == "interrupt":
            raise KeyboardInterrupt("Authored host interrupt")
        if failure == "timeout":
            http.now = deadline
        return accepted(slot, result, deadline)

    def save_review(path: Path, value: object) -> None:
        if path.name == "meaning-review.json" and failure == "save":
            raise OSError("Authored review save failure")
        save(path, value)
        if path.name == "meaning-review.json" and failure == "late_save":
            http.now = 1501

    monkeypatch.setattr(p, "_save", save_review)
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt, match="Authored host interrupt"):
            p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, assess)
        final = read(frozen[0] / "results/manifest.json")["accounting"]
    else:
        final = p._run(
            frozen[0],
            "Authored approval",
            frozen[1],
            http.exchange,
            http.clock,
            assess,
        )["accounting"]
    assert not final["capture_complete"] and len(http.posts) == 1
    assert final["unsent"] == list(p.SLOTS[1:])
    assert (frozen[0] / "results" / p.SLOTS[0] / "work-review.md").exists()


def test_missing_callback_cannot_send_and_run_has_no_default(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    with pytest.raises(TypeError):
        p.run(*frozen[:1], "Authored approval", frozen[1])  # pyright: ignore[reportCallIssue]
    final = p._run(
        frozen[0],
        "Authored approval",
        frozen[1],
        http.exchange,
        http.clock,
        None,  # type: ignore[arg-type]
    )["accounting"]
    assert not final["capture_complete"] and not http.calls


def test_blocking_host_callback_has_real_deadline_and_restores_timer() -> None:
    result = next(iter(p.examples.load_examples().values()))
    previous = signal.getsignal(signal.SIGALRM)

    def blocking(_slot: str, _result: p.review.Result, _deadline: float) -> dict[str, Any]:
        select.select([], [], [], 1)
        pytest.fail("Callback should have timed out")

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="host assessment"):
        p._assess(p.SLOTS[0], result, started + 0.01, blocking, time.monotonic)
    assert time.monotonic() - started < 1
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)


def test_host_assessment_refuses_other_thread_and_existing_timer() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match="main thread"):
            pool.submit(p._assessment_ready, accepted).result()
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        with pytest.raises(RuntimeError, match="existing real-time timer"):
            p._assessment_ready(accepted)
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


@pytest.mark.parametrize("change", ["uncommitted", "committed", "not_ancestor"])
def test_exact_source_and_ancestor_are_required(
    source: Path,
    frozen: tuple[Path, str],
    change: str,
) -> None:
    if change == "not_ancestor":
        with pytest.raises(subprocess.CalledProcessError):
            p._source("f" * 40)
        return
    (source / p.DECLARATION).write_bytes(b"Authored changed declaration")
    if change == "committed":
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
            "Changed declaration",
        )
    with pytest.raises(ValueError, match="Dirty|Committed source drift"):
        p._validate(*frozen)


def test_earlier_http_import_keeps_its_independent_source_baseline(source: Path) -> None:
    script = """from pathlib import Path
import subprocess
from prototypes.reviewable_draft import _work_review_http as http
path = Path(http.__file__)
original = http.LOADED_SOURCE_SHA256
path.write_bytes(path.read_bytes() + b"\\n# Authored changed helper source\\n")
subprocess.check_output(["git", "add", "."])
subprocess.check_output(["git", "-c", "user.name=Synthetic", "-c",
    "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
    "commit", "-qm", "Authored helper source change"])
from prototypes.reviewable_draft import work_review_probe as probe
assert probe.LOADED[probe.HERE + "_work_review_http.py"] == original
try:
    probe._source()
except ValueError as error:
    assert "Imported source drift" in str(error)
else:
    raise AssertionError("Earlier import baseline was refreshed")
"""
    subprocess.check_output(
        [sys.executable, "-B", "-c", script], cwd=source, stderr=subprocess.PIPE
    )
