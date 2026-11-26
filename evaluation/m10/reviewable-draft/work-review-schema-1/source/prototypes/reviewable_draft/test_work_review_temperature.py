"""Offline two-temperature thinking capture and host assessment gates; no model or HTTP calls."""

# pyright: reportPrivateUsage=false

import json
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

from . import work_review_temperature as p
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
        self.raws: list[bytes] = []
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
            raw = self.raws[len(self.posts) - 1] if self.raws else self.raw
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


def test_exact_packets_preserve_original_control_and_distinct_slot_generations(
    frozen: tuple[Path, str],
) -> None:
    output, pin = frozen
    manifest, packets = p._validate(output, pin)
    assert p.CASES == ("front_loaded_timing",)
    assert len(packets) == 2 and manifest["generation_id"].startswith("work-review-temperature-")
    settings = manifest["settings"]
    assert (
        settings["requests"],
        settings["repetitions"],
        settings["seconds"],
        settings["retries"],
    ) == (2, 1, 600, 0)
    assert (settings["per_generation_seconds"], settings["per_metadata_seconds"]) == (180, 10)
    assert settings["order"] == [0, 1] and settings["num_predict"] == 4096
    bindings = read(output / "bindings.json")
    snapshots = read(output / "snapshots.json")
    assert packets[0].snapshot == packets[1].snapshot
    assert packets[0].generation_id != packets[1].generation_id
    assert packets[0].binding != packets[1].binding
    bodies: list[dict[str, Any]] = []
    for temperature, slot, packet, wire_pin in zip(
        p.TEMPERATURES, p.SLOTS, packets, p.http.CHAT_PINS, strict=True
    ):
        wire = p._read(output, f"requests/{slot}.json")
        body = p._load(wire)
        expected = {
            **packet.payload(),
            "model": p.http.MODEL,
            "stream": True,
            "think": True,
            "options": {"temperature": temperature, "num_ctx": 32768, "num_predict": 4096},
        }
        assert wire == p._bytes(expected) and p._hash(wire) == wire_pin
        assert "seed" not in body["options"]
        assert "writing" not in p._load(body["messages"][1]["content"].encode())
        assert packet.generation_id == f"{manifest['generation_id']}/{slot}"
        assert snapshots[p.CASE]["handwritten_text"] == packet.snapshot.handwritten_text
        assert snapshots[p.CASE]["transcript"] == packet.snapshot.transcript
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
        bodies.append(body)
    bodies[0]["options"]["temperature"] = 1
    assert bodies[0] == bodies[1]
    assert p._inventory(output) == {**manifest["files"], "manifest.json": pin}
    assert read(output / "import-baselines.json") == p.LOADED
    assert all(p.LOADED[n] == h for n, h in p.previous.LOADED.items())
    assert p._hash(p._read(output, "source/" + p.d.INPUT)) == p.d.INPUT_HASH
    assert not any("cached-failure" in n or "work-review-probe-1/results" in n for n in p.NAMES)
    with pytest.raises(FileExistsError):
        p.freeze(output, dict(p.IDENTITY))


def test_two_serial_generations_have_exact_accounting_and_replay_without_semantic_pass(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    returned = run(frozen, http)
    final = returned["accounting"]
    output, pin = frozen
    assert final["capture_complete"] and final["possibly_sent"] == len(http.posts) == 2
    assert final["stop_completed"] == list(p.SLOTS) and not final["failed"] and not final["unsent"]
    assert "no automated model-quality PASS" in final["stop_reason"]
    assert len(http.calls) == 14
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
    assert len(http.posts) == 2


@pytest.mark.parametrize(
    "change",
    [
        "source",
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
    assert len(final["slots"]) == 2 and not final["capture_complete"]
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
def test_first_failure_keeps_partial_bytes_and_all_two_bound_slots(
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
def test_shared_600_seconds_includes_every_stage_and_seal_has_separate_observation(
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
        http.now = 601
        return result

    def slow_save(path: Path, value: object) -> None:
        save(path, value)
        if path.name == {
            "outcome": "outcome.json",
            "final": "final.json",
            "seal": "manifest.json",
        }.get(boundary):
            http.now = 601

    if boundary == "validation":
        monkeypatch.setattr(p, "_validate", slow_validate)
    elif boundary == "metadata":
        http.hook = lambda _e, _d: setattr(http, "now", 601)
    elif boundary == "generation":
        validations = 0

        def short_budget(
            output: Path, pin: str
        ) -> tuple[dict[str, Any], tuple[p.review.Prepared, ...]]:
            nonlocal validations
            validations += 1
            result = validate(output, pin)
            if validations == 3:
                http.now = 580
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
    assert returned["post_seal_observation"]["completion_eligible"] is False
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
        1 if interrupt or artifact in ("progress.json", "result.json") else 2
    )
    assert len(final["slots"]) == 2
    if artifact == "progress.json":
        assert (output / p.SLOTS[0] / "observed.json").exists()


def test_local_parser_keeps_known_prefix_timing_and_refuses_unknown_tail(tmp_path: Path) -> None:
    assert p.Stream is not p.runtime.Stream and p._stream is not p.runtime._stream
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
    output = tmp_path / "shallow-freeze"
    p._validate(output, p.freeze(output, dict(p.IDENTITY)))
    # The rejection body must also reproduce in the closed, depth-one source tree.
    script = """import sys
from pathlib import Path
from prototypes.reviewable_draft.test_work_review_temperature_http import (
    test_child_rejects_old_pair_changed_body_or_other_request_before_connect as check,
)
check(Path(sys.argv[1]), "previous_false")
"""
    rejection = tmp_path / "shallow-rejection"
    rejection.mkdir()
    subprocess.check_output(
        [sys.executable, "-B", "-c", script, str(rejection)],
        cwd=shallow,
        stderr=subprocess.PIPE,
    )


def test_import_and_pure_preparation_cannot_connect() -> None:
    script = """import socket
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("No network"))
socket.create_connection = socket.socket.connect
from prototypes.reviewable_draft import work_review_temperature as p
source = {name: (p.ROOT / name).read_bytes() for name in p.NAMES}
files, packets = p._files(source, p._identity(p.IDENTITY), "work-review-temperature-" + "a" * 32)
assert len(packets) == 2
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
        assert deadline == 600 and http.now < deadline
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


@pytest.mark.parametrize("critical_slot", [0, 1])
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
            http.now = 601

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
    snapshot = p._snapshots((REAL_ROOT / p.d.INPUT).read_bytes())[p.CASES[0]]
    result = p.review.decode(p.review.prepare(snapshot, "authored-timeout-test"), '{"groups":[]}')
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
from prototypes.reviewable_draft import _work_review_temperature_http as http
path = Path(http.__file__)
original = http.LOADED_SOURCE_SHA256
path.write_bytes(path.read_bytes() + b"\\n# Authored changed helper source\\n")
subprocess.check_output(["git", "add", "."])
subprocess.check_output(["git", "-c", "user.name=Synthetic", "-c",
    "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
    "commit", "-qm", "Authored helper source change"])
from prototypes.reviewable_draft import work_review_temperature as probe
assert probe.LOADED[probe.HERE + "_work_review_temperature_http.py"] == original
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


def test_original_forty_loader_preserves_complete_control_and_old_globals() -> None:
    from . import _work_review_http as previous_http
    from . import actions

    old_cases, old_pins = actions.CASES, previous_http.CHAT_PINS
    original = (REAL_ROOT / p.d.INPUT).read_bytes()
    snapshots = p._snapshots(original)
    assert tuple(snapshots) == p.CASES
    rows = {row["id"]: row for row in p.d._rows(json.loads(original))}
    assert len(rows) == 40 and "front_loaded_timing" not in old_cases
    for case, snapshot in snapshots.items():
        row = rows[case]
        assert snapshot.title == row["meeting"]["title"]
        assert snapshot.started_at == row["meeting"]["started_at"]
        assert snapshot.attendees == tuple(row["meeting"]["attendees"])
        assert snapshot.my_name == row["meeting"]["my_name"]
        assert snapshot.transcript == row["transcript"]
        assert snapshot.handwritten_text == row["handwritten_text"]
    assert actions.CASES is old_cases and previous_http.CHAT_PINS is old_pins
    assert p.LOADED.items() >= p.previous.LOADED.items()
    assert set(p.previous.NAMES) <= set(p.NAMES)
    with pytest.raises(ValueError, match="forty-case input hash"):
        p._snapshots(original + b" ")


@pytest.mark.parametrize("index", range(2))
@pytest.mark.parametrize("artifact", ["request", "snapshot", "binding", "prepared", "generation"])
def test_every_slot_is_bound_and_checked_before_any_launch(
    frozen: tuple[Path, str],
    http: HTTP,
    index: int,
    artifact: str,
) -> None:
    output, pin = frozen
    slot = p.SLOTS[index]
    if artifact in ("binding", "prepared", "generation"):
        path = output / "bindings.json"
        data = read(path)
        key = {
            "binding": "snapshot_id",
            "prepared": "prepared_binding",
            "generation": "generation_id",
        }[artifact]
        data[slot][key] = "Authored incorrect binding"
        path.write_bytes(p._bytes(data))
    else:
        folder = "requests" if artifact == "request" else "snapshots"
        (output / folder / f"{slot}.json").write_bytes(b"Authored changed slot")
    final = run((output, pin), http)["accounting"]
    assert not http.calls and final["possibly_sent"] == 0
    assert final["unsent"] == list(p.SLOTS) and not final["capture_complete"]


@pytest.mark.parametrize("failure", ["spawn", "http", "child_error", "request_drift"])
def test_transport_and_actual_request_failures_stop_without_later_requests(
    frozen: tuple[Path, str],
    http: HTTP,
    failure: str,
) -> None:
    def fail(endpoint: str, directory: Path) -> None:
        if endpoint != "/api/chat":
            return
        if failure == "spawn":
            raise OSError("Authored spawn failure")
        if failure == "http":
            p._save(directory / "headers.json", dict(status=302, headers=[]))
        elif failure == "child_error":
            p._save(directory / "error.json", dict(error="Authored child failure"))
        else:
            (directory.parent / "request.json").write_bytes(b"Authored changed actual request")

    # The ordinary fake writes headers, so apply HTTP-status drift after it returns.
    original = http.exchange

    def exchange(
        method: str,
        endpoint: str,
        request: Path | None,
        directory: Path,
        deadline: float,
        pin: str | None,
    ) -> dict[str, Any]:
        state = original(method, endpoint, request, directory, deadline, pin)
        if endpoint == "/api/chat" and failure == "http":
            (directory / "headers.json").write_bytes(p._bytes(dict(status=302, headers=[])))
        return state

    if failure != "http":
        http.hook = fail
    final = p._run(frozen[0], "Authored approval", frozen[1], exchange, http.clock, accepted)[
        "accounting"
    ]
    assert not final["capture_complete"] and final["possibly_sent"] == 1
    assert final["unsent"] == list(p.SLOTS[1:])
    assert not (frozen[0] / "results" / p.SLOTS[0] / "work-review.md").exists()


@pytest.mark.parametrize("artifact", ["meaning-review.json", "outcome.json", "manifest.json"])
def test_independent_save_failure_never_masks_original_assessment_interrupt(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    save = p._save

    def save_failure(path: Path, value: object) -> None:
        if path.name == artifact:
            raise SystemExit("Authored saving interrupt")
        save(path, value)

    monkeypatch.setattr(p, "_save", save_failure)

    def interrupted(_slot: str, _result: p.review.Result, _deadline: float) -> dict[str, Any]:
        raise KeyboardInterrupt("Authored original interrupt")

    with pytest.raises(KeyboardInterrupt, match="Authored original interrupt"):
        p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, interrupted)
    assert len(http.posts) == 1


def length_reply(content: str = "", count: int | None = 4096) -> bytes:
    value = event(content, thinking="Synthetic thought", done=True)
    value["done_reason"] = "length"
    if count is None:
        del value["eval_count"]
    else:
        value["eval_count"] = count
    return line(value)


@pytest.mark.parametrize("content", ["", "{", '{"groups":[]}', '{"groups":[["T1"]]}'])
def test_two_length_captures_never_decode_render_or_assess_even_parseable_content(
    frozen: tuple[Path, str], http: HTTP, content: str
) -> None:
    http.raw = length_reply(content)

    def forbidden(_slot: str, _result: p.review.Result, _deadline: float) -> dict[str, Any]:
        pytest.fail("Censored length cannot reach Chief assessment")

    returned = p._run(
        frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, forbidden
    )
    final = returned["accounting"]
    assert final["capture_complete"] and not final["answer_complete"]
    assert not final["semantic_complete"] and final["automated_quality_pass"] is False
    assert final["length_censored"] == list(p.SLOTS) and not final["stop_completed"]
    assert not final["failed"] and not final["unsent"]
    assert final["counts"] == dict(
        stop_completed=0,
        length_censored=2,
        failed=0,
        unsent=0,
        transport_complete=2,
        answers=0,
        meaning_reviews=0,
    )
    assert len(http.calls) == 14 and len(http.posts) == 2
    assert final == read(frozen[0] / "results/manifest.json")["accounting"]
    for row in final["slots"]:
        slot = frozen[0] / "results" / row["slot"]
        assert row["state"] == row["terminal_outcome"] == "censored_length"
        assert row["length_cap_match"] is True and row["length_counter_status"] == "matches"
        assert not row["render_saved"]
        progress = read(slot / "progress.json")
        assert progress["valid"] and not progress["answer_complete"]
        assert progress["returned"]["eval_count"] == 4096
        assert read(slot / "observed.json")["content"] == content
        assert (slot / "response/body.raw").read_bytes() == http.raw
        assert read(slot / "after/show/headers.json")["status"] == 200
        assert not any(
            (slot / n).exists() for n in ("result.json", "work-review.md", "meaning-review.json")
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_terminal_outcomes_assess_only_stop_and_keep_semantics_incomplete(
    frozen: tuple[Path, str], http: HTTP, reverse: bool
) -> None:
    http.raws = [length_reply('{"groups":[["T1"]]}'), line(event('{"groups":[["T1"]]}', done=True))]
    if reverse:
        http.raws.reverse()
    reviewed: list[str] = []

    def assess(slot: str, result: p.review.Result, deadline: float) -> dict[str, Any]:
        reviewed.append(slot)
        return accepted(slot, result, deadline)

    final = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, assess)[
        "accounting"
    ]
    assert reviewed == final["stop_completed"] == [p.SLOTS[0 if reverse else 1]]
    assert final["length_censored"] == [p.SLOTS[1 if reverse else 0]]
    assert (
        final["capture_complete"]
        and not final["answer_complete"]
        and not final["semantic_complete"]
    )
    assert final["counts"]["answers"] == final["counts"]["meaning_reviews"] == 1


@pytest.mark.parametrize("count", [None, 0, 4095, 4097])
def test_length_missing_or_different_counter_is_explicit_and_stops_after_post_gate(
    frozen: tuple[Path, str], http: HTTP, count: int | None
) -> None:
    http.raw = length_reply('{"groups":[]}', count)
    final = run(frozen, http)["accounting"]
    assert len(http.posts) == 1 and len(http.calls) == 7
    assert final["length_censored"] == final["failed"] == [p.SLOTS[0]]
    assert final["unsent"] == [p.SLOTS[1]] and not final["capture_complete"]
    row = final["slots"][0]
    assert row["length_cap_match"] is (None if count is None else False)
    assert row["length_counter_status"] == ("missing" if count is None else "differs")
    progress = row["progress"]
    assert ("eval_count" in progress["returned"]) is (count is not None)
    assert "exact num_predict=4096" in final["stop_reason"]
    assert final["counts"]["answers"] == final["counts"]["meaning_reviews"] == 0


@pytest.mark.parametrize("reason", ["stop", "length"])
@pytest.mark.parametrize("width", [1, 2, 7, 65536])
def test_local_stream_split_utf8_and_terminal_counts(reason: str, width: int) -> None:
    terminal = event("last", done=True)
    terminal["done_reason"] = reason
    terminal["eval_count"] = 4096
    raw = line(event("first", thinking="Authored é思考")) + line(terminal)
    stream = p.Stream()
    for index in range(0, len(raw), width):
        stream.feed(raw[index : index + width], index / 100)
    progress = stream.progress()
    assert progress["valid"] and progress["answer_complete"] is (reason == "stop")
    assert stream.content == "firstlast" and stream.thinking == "Authored é思考"
    assert progress["returned"] == {name: terminal[name] for name in p.runtime.COUNTS}
    assert progress["complete_events"] == 2 and not progress["sizes_are_tokens"]
    old = p.runtime.Stream()
    old.feed(raw, 1)
    assert old.progress()["valid"] is (reason == "stop")


@pytest.mark.parametrize(
    "kind",
    [
        "unknown_reason",
        "reason_missing",
        "nonterminal_reason",
        "error",
        "model",
        "done_type",
        "message",
        "thinking",
        "role",
        "created",
        "extra",
        "count_bool",
        "count_negative",
        "utf8",
        "duplicate_key",
        "nonfinite",
        "trailing_event",
        "trailing_done",
        "trailing_bytes",
        "no_newline",
        "empty",
        "no_terminal",
    ],
)
def test_malformed_stream_or_eof_stops_without_answer_or_later_generation(
    frozen: tuple[Path, str], http: HTTP, kind: str
) -> None:
    value = p._load(length_reply('{"groups":[]}'))
    raw: bytes | None = None
    if kind == "unknown_reason":
        value["done_reason"] = "other"
    elif kind == "reason_missing":
        del value["done_reason"]
    elif kind == "nonterminal_reason":
        value["done"] = False
    elif kind == "error":
        value = {"error": "Authored failure"}
    elif kind == "model":
        value["model"] = "different"
    elif kind == "done_type":
        value["done"] = 1
    elif kind == "message":
        value["message"]["content"] = []
    elif kind == "thinking":
        value["message"]["thinking"] = None
    elif kind == "role":
        value["message"]["role"] = "user"
    elif kind == "created":
        value["created_at"] = 1
    elif kind == "extra":
        value["extra"] = True
    elif kind == "count_bool":
        value["eval_count"] = True
    elif kind == "count_negative":
        value["eval_count"] = -1
    elif kind == "utf8":
        raw = b"\xff\n"
    elif kind == "duplicate_key":
        raw = line(value).replace(b'"done": true', b'"done": false, "done": true')
    elif kind == "nonfinite":
        raw = line(value).replace(b'"eval_count": 4096', b'"eval_count": NaN')
    elif kind in ("trailing_event", "trailing_done"):
        raw = line(value) + line(event(done=kind == "trailing_done"))
    elif kind == "trailing_bytes":
        raw = line(value) + b" "
    elif kind == "no_newline":
        raw = line(value)[:-1]
    elif kind == "empty":
        raw = b""
    else:
        raw = line(event("partial"))
    http.raw = line(value) if raw is None else raw
    # The fake index represents only positive-sized transport chunks.
    if not http.raw:
        http.raw = b"\n"
    final = run(frozen, http)["accounting"]
    assert len(http.posts) == 1 and not final["capture_complete"]
    assert final["failed"] == [p.SLOTS[0]] and final["unsent"] == [p.SLOTS[1]]
    assert final["counts"]["answers"] == final["counts"]["meaning_reviews"] == 0


@pytest.mark.parametrize(
    "kind",
    ["offset", "length", "outside", "time", "nan", "inf", "shape", "partial_index", "unlogged"],
)
def test_replay_requires_exact_index_and_preserves_unknown_receive_timing(
    tmp_path: Path, kind: str
) -> None:
    raw = length_reply('{"groups":[]}')
    (tmp_path / "body.raw").write_bytes(raw)
    row: dict[str, Any] = dict(offset=0, length=len(raw), seconds=1)
    if kind == "offset":
        row["offset"] = 1
    elif kind == "length":
        row["length"] = 0
    elif kind == "outside":
        row["length"] += 1
    elif kind == "time":
        row["seconds"] = -1
    elif kind == "shape":
        row["extra"] = 1
    if kind in ("nan", "inf"):
        index = json.dumps({**row, "seconds": float(kind)}).encode() + b"\n"
    else:
        index = line(row)
    if kind == "partial_index":
        index = index[:-1]
    if kind == "unlogged":
        index = b""
    (tmp_path / "chunks.jsonl").write_bytes(index)
    stream = p._stream(tmp_path)
    assert not stream.progress()["valid"]
    if kind in ("partial_index", "unlogged"):
        assert stream.content == '{"groups":[]}'
        assert stream.first_byte is stream.first_content is stream.first_thinking is None


@pytest.mark.parametrize(
    "artifact", ["progress.json", "observed.json", "outcome.json", "final.json", "manifest.json"]
)
def test_censored_finalization_failures_never_claim_completion(
    frozen: tuple[Path, str], http: HTTP, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    http.raw = length_reply()
    save = p._save

    def fail(path: Path, value: object) -> None:
        if path.name == artifact:
            raise OSError("Authored storage failure")
        save(path, value)

    monkeypatch.setattr(p, "_save", fail)
    returned = run(frozen, http)
    assert not returned["accounting"]["capture_complete"]
    assert not returned["post_seal_observation"]["completion_eligible"]
    assert returned["accounting"]["artifact_errors"]
    first = frozen[0] / "results" / p.SLOTS[0]
    assert (first / "response/body.raw").exists()
    if artifact == "progress.json":
        assert (first / "observed.json").exists()
    if artifact == "observed.json":
        assert (first / "progress.json").exists()


@pytest.mark.parametrize("failure", ["timeout", "exit"])
def test_transport_failure_cannot_accept_even_fully_logged_length_terminal(
    frozen: tuple[Path, str], http: HTTP, failure: str
) -> None:
    http.raw = length_reply('{"groups":[["T1"]]}')
    http.failure = failure
    final = run(frozen, http)["accounting"]
    assert len(http.calls) == 4 and len(http.posts) == 1
    assert final["length_censored"] == final["failed"] == [p.SLOTS[0]]
    assert final["unsent"] == [p.SLOTS[1]]
    assert not final["capture_complete"] and final["counts"]["transport_complete"] == 0
    assert final["counts"]["answers"] == final["counts"]["meaning_reviews"] == 0


def test_censored_terminal_still_requires_post_identity_gate(
    frozen: tuple[Path, str], http: HTTP
) -> None:
    http.raw = length_reply()

    def drift(endpoint: str, _directory: Path) -> None:
        if endpoint == "/api/chat":
            http.identity["parameters"] = "Authored changed defaults"

    http.hook = drift
    final = run(frozen, http)["accounting"]
    assert len(http.posts) == 1 and len(http.calls) == 7
    assert final["length_censored"] == final["failed"] == [p.SLOTS[0]]
    assert final["unsent"] == [p.SLOTS[1]] and not final["capture_complete"]
    assert "defaults drift" in final["stop_reason"]


def test_seal_attempt_and_manifest_write_have_separate_observable_wall_times(
    frozen: tuple[Path, str], http: HTTP, monkeypatch: pytest.MonkeyPatch
) -> None:
    save = p._save

    def measured(path: Path, value: object) -> None:
        save(path, value)
        if path.name == "manifest.json":
            http.now += 0.5

    monkeypatch.setattr(p, "_save", measured)
    returned = run(frozen, http)
    sealed = read(frozen[0] / "results/manifest.json")["accounting"]
    observation = returned["post_seal_observation"]
    assert sealed == returned["accounting"]
    assert observation["manifest_write_seconds"] == pytest.approx(0.5)
    assert observation["seal_attempt_seconds"] >= observation["manifest_write_seconds"]
    assert observation["elapsed"] - sealed["elapsed"] == pytest.approx(0.5)
    assert observation["completion_eligible"]


@pytest.mark.parametrize("bad_slot", [0, 1])
@pytest.mark.parametrize("count", [4097, 10000])
def test_stop_counter_above_cap_fails_before_decode_render_review_or_continuation(
    frozen: tuple[Path, str], http: HTTP, bad_slot: int, count: int
) -> None:
    terminal = event('{"groups":[["T1"]]}', done=True)
    terminal["eval_count"] = count
    http.raws = [http.raw, http.raw]
    http.raws[bad_slot] = line(terminal)
    reviewed: list[str] = []

    def assess(slot: str, result: p.review.Result, deadline: float) -> dict[str, Any]:
        reviewed.append(slot)
        return accepted(slot, result, deadline)

    final = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock, assess)[
        "accounting"
    ]
    assert len(http.posts) == bad_slot + 1 and reviewed == list(p.SLOTS[:bad_slot])
    assert len(http.calls) == 7 * (bad_slot + 1)
    assert final["failed"] == [p.SLOTS[bad_slot]]
    assert final["unsent"] == list(p.SLOTS[bad_slot + 1 :])
    assert not final["capture_complete"] and not final["answer_complete"]
    assert not final["semantic_complete"] and "exceeds num_predict=4096" in final["stop_reason"]
    slot = frozen[0] / "results" / p.SLOTS[bad_slot]
    assert (slot / "response/body.raw").read_bytes() == line(terminal)
    progress = read(slot / "progress.json")
    assert progress["valid"] and progress["terminal_outcome"] == "stop"
    assert progress["returned"]["eval_count"] == count
    assert read(slot / "observed.json")["content"] == terminal["message"]["content"]
    assert not any(
        (slot / n).exists() for n in ("result.json", "work-review.md", "meaning-review.json")
    )


@pytest.mark.parametrize("count", [None, 0, 4095, 4096])
def test_stop_at_or_below_cap_and_absent_counter_allow_review_and_next_request(
    frozen: tuple[Path, str], http: HTTP, count: int | None
) -> None:
    terminal = event('{"groups":[["T1"]]}', done=True)
    if count is None:
        del terminal["eval_count"]
    else:
        terminal["eval_count"] = count
    http.raw = line(terminal)
    final = run(frozen, http)["accounting"]
    assert final["capture_complete"] and final["answer_complete"] and final["semantic_complete"]
    assert len(http.posts) == 2 and final["counts"]["meaning_reviews"] == 2
    for row in final["slots"]:
        returned = row["progress"]["returned"]
        assert ("eval_count" in returned) is (count is not None)
        if count is not None:
            assert returned["eval_count"] == count
