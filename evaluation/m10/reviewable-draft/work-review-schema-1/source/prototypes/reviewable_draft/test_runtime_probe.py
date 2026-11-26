"""Offline authored streams, clocks and exchanges. No model-quality claims."""

# pyright: reportPrivateUsage=false

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from . import runtime_probe as p

REAL_ROOT = p.ROOT


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def read(path: Path) -> dict[str, Any]:
    return p._load(path.read_bytes())


def event(content: str = "", *, thinking: str = "", done: bool = False) -> dict[str, Any]:
    value: dict[str, Any] = dict(
        model=p.http.MODEL,
        created_at="2026-11-25T00:00:00Z",
        done=done,
        message=dict(role="assistant", content=content, thinking=thinking),
    )
    if done:
        # Exact key set of the committed Ollama terminal reply, with authored values.
        value.update(
            done_reason="stop",
            total_duration=120,
            load_duration=10,
            prompt_eval_count=30,
            prompt_eval_duration=20,
            eval_count=40,
            eval_duration=90,
            prompt_eval_cached_count=3,
        )
    return value


def line(value: object) -> bytes:
    return p._bytes(value) + b"\n"


def reply() -> bytes:
    return line(event(thinking="Authored é思考")) + line(
        event('{"actions": [], "review_sources": []}', done=True)
    )


@pytest.mark.parametrize("width", [1, 2, 3, 7, 31, 65536])
def test_split_ndjson_and_utf8_retains_terminal_content_and_actual_cache_field(width: int) -> None:
    raw = reply()
    stream = p.Stream()
    for index in range(0, len(raw), width):
        stream.feed(raw[index : index + width], index / 100)
    progress = stream.progress()
    assert progress["valid"] and progress["complete_events"] == 2
    assert stream.content == '{"actions": [], "review_sources": []}'
    assert stream.thinking == "Authored é思考"
    assert progress["thinking_characters"] == len(stream.thinking)
    assert progress["content_characters"] == len(stream.content)
    assert progress["returned"] == {name: event(done=True)[name] for name in p.COUNTS}
    assert progress["first_thinking_seconds"] is not None
    assert progress["first_content_seconds"] is not None
    assert progress["sizes_are_tokens"] is False
    saved = read(REAL_ROOT / p.OLD / "results/02-02-accepted_status_answer/response/body.raw")
    assert set(event(done=True)) == set(saved)


def test_content_and_thinking_accumulate_including_nonempty_final_event() -> None:
    stream = p.Stream()
    stream.feed(line(event("first", thinking="one")), 2)
    stream.feed(line(event("last", thinking="two", done=True)), 5)
    assert (stream.content, stream.thinking) == ("firstlast", "onetwo")
    assert stream.first_byte == stream.first_content == stream.first_thinking == 2
    assert stream.progress()["valid"]


@pytest.mark.parametrize(
    "mutation",
    [
        "model",
        "done_type",
        "role",
        "content_type",
        "thinking_type",
        "message_type",
        "error",
        "extra",
        "missing",
        "created_type",
        "count_type",
        "negative_count",
        "length",
        "reason_type",
        "nonterminal_reason",
        "nonterminal_count",
    ],
)
def test_malformed_event_shapes_are_rejected(mutation: str) -> None:
    value = event("answer", done=True)
    if mutation == "model":
        value["model"] = "another-model"
    if mutation == "done_type":
        value["done"] = 1
    if mutation == "role":
        value["message"]["role"] = "user"
    if mutation == "content_type":
        value["message"]["content"] = []
    if mutation == "thinking_type":
        value["message"]["thinking"] = None
    if mutation == "message_type":
        value["message"] = []
    if mutation == "error":
        value["error"] = "Synthetic server error"
    if mutation == "extra":
        value["unrecognized"] = True
    if mutation == "missing":
        value.pop("message")
    if mutation == "created_type":
        value["created_at"] = 1
    if mutation == "count_type":
        value["eval_count"] = True
    if mutation == "negative_count":
        value["eval_count"] = -1
    if mutation == "length":
        value["done_reason"] = "length"
    if mutation == "reason_type":
        value["done_reason"] = False
    if mutation == "nonterminal_reason":
        value["done"] = False
    if mutation == "nonterminal_count":
        value["done"] = False
        value.pop("done_reason")
    stream = p.Stream()
    stream.feed(line(value), 1)
    assert not stream.progress()["valid"] and stream.error
    assert not stream.content


@pytest.mark.parametrize(
    "tail",
    [
        b"",
        b"{}\n",
        b'{"x":1,"x":2}\n',
        b'{"nested":{"x":1,"x":2}}\n',
        b'{"x":NaN}\n',
        b'{"x":Infinity}\n',
        b"\xff\n",
        b"[]\n",
        b"\n",
    ],
)
def test_bad_json_and_missing_terminal_preserve_complete_progress(tail: bytes) -> None:
    stream = p.Stream()
    stream.feed(line(event(thinking="authored partial")) + tail, 1)
    assert not stream.progress()["valid"]
    assert stream.thinking == "authored partial" and stream.events == 1


@pytest.mark.parametrize(
    "tail", [b"\n", line(event(done=True)), line(event()), b"partial", b"\xc3"]
)
def test_any_trailing_event_or_bytes_invalidate_terminal(tail: bytes) -> None:
    stream = p.Stream()
    stream.feed(reply() + tail, 1)
    assert not stream.progress()["valid"]
    assert stream.content == '{"actions": [], "review_sources": []}'


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
        "Synthetic frozen probe source",
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
        self.raw = reply()
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
        data = b""
        if endpoint == "/api/chat":
            assert request is not None
            data = request.read_bytes()
            assert p._hash(data) == pin == p.http.CHAT_PINS[len(self.posts)]
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
                {key: self.identity[key] for key in ("capabilities", "thinking", "parameters")}
            )
        (directory / "body.raw").write_bytes(raw)
        (directory / "chunks.jsonl").write_bytes(
            line(dict(offset=0, length=len(raw), seconds=0.01))
        )
        p._save(directory / "origin.json", dict(monotonic=self.now, clock="time.monotonic"))
        p._save(directory / "headers.json", dict(status=200, headers=[]))
        state: dict[str, Any] = dict(error=None, returncode=0, timed_out=False, elapsed=0.1)
        self.now += 0.1
        if endpoint == "/api/chat" and self.failure:
            state.update(error="Synthetic " + self.failure, returncode=1)
            if self.failure == "timeout":
                self.now = deadline
                state.update(timed_out=True, killed=True, reaped=True)
            if self.failure == "headers":
                (directory / "headers.json").unlink()
                state.update(error=None, returncode=0)
        p._save(directory / "exchange.json", state)
        if endpoint == "/api/chat" and self.failure == "interrupt":
            raise KeyboardInterrupt
        return state


@pytest.fixture
def http() -> HTTP:
    return HTTP()


def run(
    frozen: tuple[Path, str], http: HTTP, approval: str = "Approved authored offline test"
) -> dict[str, Any]:
    return p._run(frozen[0], approval, frozen[1], http.exchange, http.clock)["accounting"]


def test_freeze_is_offline_exact_and_single_use(frozen: tuple[Path, str], http: HTTP) -> None:
    output, pin = frozen
    manifest, packets = p._validate(output, pin)
    assert not http.calls and len(packets) == 2
    assert p._inventory(output) == {**manifest["files"], "manifest.json": pin}
    bodies = [p._read(output, f"requests/{slot}.json") for slot in p.SLOTS]
    assert [p._hash(b) for b in bodies] == list(p.http.CHAT_PINS)
    first, second = [p._load(b) for b in bodies]
    assert first.pop("think") is False and second.pop("think") is True and first == second
    for index, packet in enumerate(packets):
        assert packet.generation_id == f"{manifest['generation_id']}/{p.SLOTS[index]}/{p.CASE}"
        assert packet.snapshot.snapshot_id == read(output / "snapshot.json")[p.CASE]["snapshot_id"]
        assert (
            packet.snapshot.handwritten_text
            == read(output / "snapshot.json")[p.CASE]["handwritten_text"]
        )
        assert packet.body()["model"] == "qwen3:30b" and packet.body()["stream"] is False
        assert bodies[index] != packet.request_json.encode()
    with pytest.raises(FileExistsError):
        p.freeze(output, dict(p.IDENTITY))


def test_success_two_serial_posts_gates_bindings_and_exact_results_inventory(
    frozen: tuple[Path, str],
    http: HTTP,
    tmp_path: Path,
) -> None:
    final = run(frozen, http)
    output, pin = frozen
    assert final["capture_complete"] and final["possibly_sent"] == len(http.posts) == 2
    assert final["completed"] == list(p.SLOTS) and not final["failed"] and not final["unsent"]
    assert len(http.calls) == 14
    assert all(t <= (180 if endpoint == "/api/chat" else 10) for _, endpoint, t in http.calls)
    manifest, packets = p._validate(output, pin)
    for index, packet in enumerate(packets):
        slot = output / "results" / p.SLOTS[index]
        assert (slot / "request.json").read_bytes() == http.posts[index]
        attempt = read(slot / "attempt.json")
        assert attempt["generation_id"] == packet.generation_id
        assert attempt["snapshot_id"] == packet.snapshot.snapshot_id
        assert attempt["request_sha256"] == p._hash(http.posts[index])
        result = p.actions.decode(packet, p._stream(slot / "response").content)
        assert (slot / "result.json").read_bytes() == p._bytes(p.asdict(result))
        assert (slot / "actions.md").read_text() == p.actions.render_result(result)
        assert "Authored" not in (slot / "actions.md").read_text()
        assert read(slot / "progress.json")["returned"]["prompt_eval_cached_count"] == 3
    seal = read(output / "results/manifest.json")
    assert final == seal["accounting"] and final["authoritative"]
    saved = seal["files"]
    assert saved == {
        name: sha
        for name, sha in p._inventory(output / "results").items()
        if name != "manifest.json"
    }
    (tmp_path / "analysis.json").write_text("{}")
    assert "analysis.json" not in saved
    with pytest.raises(FileExistsError):
        run(frozen, http)
    assert len(http.posts) == 2 and manifest["identity"] == p.IDENTITY


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "request",
        "manifest",
        "identity",
        "declaration",
        "input",
        "proposal",
        "import",
        "pin",
    ],
)
def test_tampering_stops_before_any_http_and_consumes_results(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    output, pin = frozen
    paths = dict(
        source=source / p.RUNTIME[-1],
        request=output / "requests/01-think-false.json",
        manifest=output / "manifest.json",
        identity=output / "identity.json",
        declaration=source / p.DECLARATION,
        input=source / p.d.INPUT,
        proposal=source / p.PROPOSAL / "proposal.json",
    )
    if change == "import":
        monkeypatch.setitem(p.LOADED, p.RUNTIME[-1], "f" * 64)
    elif change == "pin":
        pin = "f" * 64
    else:
        paths[change].write_bytes(b"Synthetic protected edit")
    final = p._run(output, "Authored approval", pin, http.exchange, http.clock)["accounting"]
    assert final["possibly_sent"] == 0 and final["unsent"] == list(p.SLOTS) and not http.calls
    assert not final["capture_complete"]
    if change in paths:
        assert paths[change].read_bytes() == b"Synthetic protected edit"


@pytest.mark.parametrize("key", list(p.IDENTITY))
def test_pre_generation_identity_gates_reject_drift(
    frozen: tuple[Path, str],
    http: HTTP,
    key: str,
) -> None:
    http.identity[key] = "changed"
    final = run(frozen, http)
    assert not http.posts and final["possibly_sent"] == 0 and not final["capture_complete"]


@pytest.mark.parametrize("failure", ["timeout", "exit", "headers", "interrupt"])
def test_first_transport_failure_preserves_progress_and_prevents_second(
    frozen: tuple[Path, str],
    http: HTTP,
    failure: str,
) -> None:
    http.failure = failure
    http.raw = line(event(thinking="Authored partial")) + b'{"message":"unfinished\xc3'
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            run(frozen, http)
        final = read(frozen[0] / "results/final.json")
    else:
        final = run(frozen, http)
    slot = frozen[0] / "results" / p.SLOTS[0]
    assert final["possibly_sent"] == 1 and len(http.posts) == 1
    assert final["failed"] == [p.SLOTS[0]] and final["unsent"] == [p.SLOTS[1]]
    assert len(http.calls) == 4  # No metadata behind uncertain server compute.
    assert (slot / "response/body.raw").read_bytes() == http.raw
    progress = read(slot / "progress.json")
    assert progress["complete_events"] == 1 and progress["thinking_characters"] == 16
    assert not progress["valid"] and not (slot / "actions.md").exists()
    assert read(slot / "attempt.json")["possibly_sent"]
    assert (frozen[0] / "results/manifest.json").exists()


@pytest.mark.parametrize("failure", ["stream", "structural", "literal", "after_identity", "source"])
def test_first_validation_failure_prevents_second_and_keeps_machine_evidence(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
    failure: str,
) -> None:
    if failure == "stream":
        http.raw = line(event(done=True)) + line(event(done=True))
    if failure == "structural":
        http.raw = line(event("{}", done=True))
    if failure == "literal":
        http.raw = line(
            event(
                json.dumps(
                    dict(
                        actions=[
                            dict(
                                source="T1",
                                quote="Synthetic invented quotation",
                                context_sources=[],
                            )
                        ],
                        review_sources=[],
                    )
                ),
                done=True,
            )
        )

    def change(endpoint: str, _: Path) -> None:
        if endpoint == "/api/chat" and failure == "after_identity":
            http.identity["parameters"] = "changed"
        if endpoint == "/api/chat" and failure == "source":
            path = source / p.RUNTIME[-1]
            path.write_bytes(path.read_bytes() + b"\n")

    http.hook = change
    final = run(frozen, http)
    slot = frozen[0] / "results" / p.SLOTS[0]
    assert len(http.posts) == final["possibly_sent"] == 1 and not final["capture_complete"]
    assert final["unsent"] == [p.SLOTS[1]] and not (slot / "actions.md").exists()
    assert (slot / "observed.json").exists()
    if failure == "literal":
        assert read(slot / "result.json")["issues"]


def test_spawn_failure_conservatively_counts_possibly_sent(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    original = http.exchange

    def exchange(
        method: str,
        endpoint: str,
        request: Path | None,
        directory: Path,
        deadline: float,
        pin: str | None,
    ) -> dict[str, Any]:
        if endpoint == "/api/chat":
            raise OSError("Synthetic spawn failure before wire POST")
        return original(method, endpoint, request, directory, deadline, pin)

    final = p._run(frozen[0], "Authored approval", frozen[1], exchange, http.clock)["accounting"]
    assert final["possibly_sent"] == 1 and not http.posts and final["unsent"] == [p.SLOTS[1]]


def test_validation_time_and_metadata_consume_shared_budget(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._validate
    calls = 0

    def validate(output: Path, pin: str) -> tuple[dict[str, Any], tuple[p.actions.Prepared, ...]]:
        nonlocal calls
        calls += 1
        result = original(output, pin)
        if calls == 2:
            http.now = 415
        return result

    monkeypatch.setattr(p, "_validate", validate)

    def advance(_: str, __: Path) -> None:
        http.now += 6

    http.hook = advance
    final = run(frozen, http)
    assert not http.posts and len(http.calls) == 1
    assert http.calls[0][2] == 5 and final["overrun_seconds"] > 0


def test_metadata_exchange_timeout_stops_before_generation(
    frozen: tuple[Path, str], http: HTTP
) -> None:
    def advance(_: str, __: Path) -> None:
        http.now += 11

    http.hook = advance
    final = run(frozen, http)
    assert len(http.calls) == 1 and not http.posts and final["possibly_sent"] == 0
    assert "TimeoutError" in final["stop_reason"]


def test_short_remaining_global_budget_caps_generation(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._validate
    calls = 0

    def validate(output: Path, pin: str) -> tuple[dict[str, Any], tuple[p.actions.Prepared, ...]]:
        nonlocal calls
        calls += 1
        result = original(output, pin)
        if calls == 3:
            http.now = 400
        return result

    monkeypatch.setattr(p, "_validate", validate)
    http.failure = "timeout"
    final = run(frozen, http)
    assert final["possibly_sent"] == 1 and http.calls[-1][2] == 20
    assert final["elapsed"] == 420


def test_source_gate_expiry_sends_nothing(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._validate

    def validate(output: Path, pin: str) -> tuple[dict[str, Any], tuple[p.actions.Prepared, ...]]:
        result = original(output, pin)
        http.now = 421
        return result

    monkeypatch.setattr(p, "_validate", validate)
    final = run(frozen, http)
    assert not http.calls and final["possibly_sent"] == 0 and final["overrun_seconds"] == 1


def test_partial_result_write_still_preserves_accounting_and_seal(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._write

    def write(path: Path, data: bytes) -> None:
        if path.name == "result.json":
            original(path, b'{"partial":')
            raise OSError("Synthetic storage failure")
        original(path, data)

    monkeypatch.setattr(p, "_write", write)
    final = run(frozen, http)
    assert final["possibly_sent"] == 1 and not final["capture_complete"]
    assert (frozen[0] / "results/manifest.json").exists()


def test_interrupt_is_not_masked_by_progress_storage_failure(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._save

    def save(path: Path, value: object) -> None:
        if path.name == "progress.json":
            raise OSError("Synthetic progress disk failure")
        original(path, value)

    http.failure = "interrupt"
    monkeypatch.setattr(p, "_save", save)
    with pytest.raises(KeyboardInterrupt):
        run(frozen, http)
    final = read(frozen[0] / "results/final.json")
    assert final["possibly_sent"] == 1 and final["artifact_errors"]
    assert (frozen[0] / "results/manifest.json").exists()


@pytest.mark.parametrize("save_error", [False, True])
def test_final_save_time_is_in_authoritative_saved_accounting(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    save_error: bool,
) -> None:
    original = p._save

    def save(path: Path, value: object) -> None:
        original(path, value)
        if path.name == "final.json":
            http.now = 421
            if save_error:
                raise OSError("Synthetic post-write failure")

    monkeypatch.setattr(p, "_save", save)
    returned = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock)
    final = returned["accounting"]
    snapshot = read(frozen[0] / "results/final.json")
    seal = read(frozen[0] / "results/manifest.json")
    assert (
        snapshot["authoritative"] is False
        and "pre-save snapshot" in snapshot["accounting_boundary"]
    )
    assert snapshot["capture_complete"] and snapshot["overrun_seconds"] == 0
    assert not snapshot["artifact_errors"]
    assert "semantic assessment pending" in snapshot["stop_reason"]
    assert final == seal["accounting"] and final["authoritative"]
    assert not final["capture_complete"] and final["overrun_seconds"] == 1
    assert "deadline" in final["stop_reason"].lower()
    assert bool(final["artifact_errors"]) is save_error
    assert seal["files"]["final.json"] == p._hash((frozen[0] / "results/final.json").read_bytes())
    assert final["slots"] == snapshot["slots"]
    assert returned["post_seal_observation"]["overrun_seconds"] == 1


def test_seal_write_wall_time_is_a_separate_observation_without_revising_saved_accounting(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._save

    def save(path: Path, value: object) -> None:
        original(path, value)
        if path.name == "manifest.json":
            http.now = 421

    monkeypatch.setattr(p, "_save", save)
    returned = p._run(frozen[0], "Authored approval", frozen[1], http.exchange, http.clock)
    seal = read(frozen[0] / "results/manifest.json")
    assert returned["accounting"] == seal["accounting"]
    assert seal["accounting"]["capture_complete"] and seal["accounting"]["overrun_seconds"] == 0
    assert not seal["accounting"]["artifact_errors"]
    assert "semantic assessment pending" in seal["accounting"]["stop_reason"]
    assert "before manifest.json write" in seal["accounting"]["accounting_boundary"]
    assert returned["post_seal_observation"]["overrun_seconds"] == 1
    assert returned["post_seal_observation"]["deadline_reached"]
    assert returned["post_seal_observation"]["sealed"]


def test_blank_approval_is_audited_and_never_sends(frozen: tuple[Path, str], http: HTTP) -> None:
    final = run(frozen, http, " ")
    assert not http.calls and final["possibly_sent"] == 0


def test_frozen_paths_reject_traversal_symlinks_and_extra_files(
    frozen: tuple[Path, str],
    tmp_path: Path,
) -> None:
    output, pin = frozen
    with pytest.raises(ValueError):
        p._read(output, "../escape")
    with pytest.raises(ValueError):
        p._read(output, "/absolute")
    link = tmp_path / "linked"
    link.symlink_to(output, target_is_directory=True)
    with pytest.raises(ValueError):
        p._validate(link, pin)
    request = output / "requests/01-think-false.json"
    original = tmp_path / "original"
    request.rename(original)
    request.symlink_to(original)
    with pytest.raises(ValueError):
        p._validate(output, pin)
    request.unlink()
    request.write_bytes(original.read_bytes())
    (output / "extra.json").write_text("{}")
    with pytest.raises(ValueError):
        p._validate(output, pin)


def test_descendant_head_can_publish_freeze_without_source_change(
    source: Path,
    frozen: tuple[Path, str],
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


def test_depth_one_source_freeze_uses_committed_files_only(
    source: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shallow = tmp_path / "shallow"
    subprocess.check_output(
        ["git", "clone", "--quiet", "--depth=1", source.as_uri(), str(shallow)],
        stderr=subprocess.PIPE,
    )
    assert git(shallow, "rev-parse", "--is-shallow-repository").strip() == b"true"
    monkeypatch.setattr(p, "ROOT", shallow)
    output = tmp_path / "shallow-freeze"
    p._validate(output, p.freeze(output, dict(p.IDENTITY)))


def test_unlogged_raw_tail_and_chunk_index_corruption_keep_raw_and_reject(tmp_path: Path) -> None:
    raw = reply()
    (tmp_path / "body.raw").write_bytes(raw)
    (tmp_path / "chunks.jsonl").write_bytes(line(dict(offset=0, length=1, seconds=0.1)))
    stream = p._stream(tmp_path)
    assert stream.content and not stream.progress()["valid"]
    assert stream.first_content is None
    (tmp_path / "chunks.jsonl").write_bytes(line(dict(offset=1, length=2, seconds=0.1)))
    assert not p._stream(tmp_path).progress()["valid"]
    assert (tmp_path / "body.raw").read_bytes() == raw


@pytest.mark.parametrize("logged_prefix", [False, True])
def test_unlogged_tail_retains_only_known_prefix_timing(
    tmp_path: Path,
    logged_prefix: bool,
) -> None:
    prefix = line(event("early", thinking="early thought"))
    (tmp_path / "body.raw").write_bytes(prefix + line(event("late", done=True)))
    if logged_prefix:
        (tmp_path / "chunks.jsonl").write_bytes(line(dict(offset=0, length=len(prefix), seconds=2)))
    stream = p._stream(tmp_path)
    assert stream.content == "earlylate" and stream.thinking == "early thought"
    assert stream.events == 2 and not stream.progress()["valid"]
    assert (stream.first_byte, stream.first_thinking, stream.first_content) == (
        (2, 2, 2) if logged_prefix else (None, None, None)
    )


@pytest.mark.parametrize("interrupt", [False, True])
def test_inventory_failure_keeps_independent_counts_and_original_interrupt(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    interrupt: bool,
) -> None:
    original = p._inventory

    def inventory(root: Path, *, omit_results: bool = False) -> dict[str, str]:
        if root.name == "results":
            raise OSError("Synthetic inventory read failure")
        return original(root, omit_results=omit_results)

    monkeypatch.setattr(p, "_inventory", inventory)
    if interrupt:
        http.failure = "interrupt"
        with pytest.raises(KeyboardInterrupt):
            run(frozen, http)
    else:
        final = run(frozen, http)
        assert not final["capture_complete"]
    saved = read(frozen[0] / "results/final.json")
    assert saved["possibly_sent"] == (1 if interrupt else 2)
    assert saved["artifact_errors"] and not saved["capture_complete"]
    assert "inventory" in " ".join(saved["artifact_errors"]).lower()
    if interrupt:
        assert saved["unsent"] == [p.SLOTS[1]]


def test_outcome_save_crossing_deadline_keeps_outcome_and_final_status_consistent(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = p._save

    def save(path: Path, value: object) -> None:
        original(path, value)
        if path.name == "outcome.json":
            http.now = 421

    monkeypatch.setattr(p, "_save", save)
    final = run(frozen, http)
    saved = read(frozen[0] / "results/final.json")
    assert not final["capture_complete"] and not saved["capture_complete"]
    assert final["overrun_seconds"] == saved["overrun_seconds"] == 1
    assert "deadline" in saved["stop_reason"].lower()
    for row in saved["slots"]:
        outcome = read(frozen[0] / "results" / row["slot"] / "outcome.json")
        assert outcome["state"] == row["state"]
