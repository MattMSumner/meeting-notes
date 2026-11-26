"""The new child owns exactly three thinking wire bodies; all connections/processes are fake."""

# pyright: reportPrivateUsage=false

import http.client
import json
from pathlib import Path
from typing import Any

import pytest

from . import _stream_http as old
from . import _work_review_thinking_http as h
from . import work_review_thinking as p
from .test_stream_http import Child, Connection, Response


def bodies() -> list[bytes]:
    source = {name: (p.ROOT / name).read_bytes() for name in p.NAMES}
    files, _ = p._files(source, p.IDENTITY, "work-review-thinking-" + "a" * 32)
    return [files[f"requests/{slot}.json"] for slot in p.SLOTS]


@pytest.mark.parametrize("index", range(3))
def test_child_accepts_each_exact_work_review_body_and_fixed_loopback(
    tmp_path: Path, index: int
) -> None:
    body = bodies()[index]
    request = tmp_path / "request.json"
    request.write_bytes(body)
    connection = Connection(Response([b"first\n\xc3", b"\xa9last\n"]))

    def connect(host: str, port: int, *, timeout: float) -> Connection:
        assert (host, port, timeout) == ("127.0.0.1", 11434, 5)
        return connection

    assert (
        h.capture("POST", "/api/chat", request, tmp_path, 5, h.CHAT_PINS[index], connect=connect)
        == 0
    )
    assert connection.calls == [("POST", "/api/chat", body)] and connection.closed
    assert (tmp_path / "body.raw").read_bytes() == b"first\n\xc3\xa9last\n"
    assert len((tmp_path / "chunks.jsonl").read_bytes().splitlines()) == 2
    assert json.loads((tmp_path / "headers.json").read_bytes())["status"] == 200


@pytest.mark.parametrize(
    "kind",
    [
        "old_false",
        "previous_false",
        "retention",
        "old_true",
        "changed",
        "wrong_pin",
        "warmup",
        "show_extra",
        "endpoint",
        "redirect",
    ],
)
def test_child_rejects_old_pair_changed_body_or_other_request_before_connect(
    tmp_path: Path, kind: str
) -> None:
    body = bodies()[0]
    endpoint, method = "/api/chat", "POST"
    if kind.startswith("old_"):
        body = (
            p.ROOT
            / p.runtime.PROPOSAL
            / f"proposed-requests/0{1 if kind == 'old_false' else 2}-think-{kind[4:]}.json"
        ).read_bytes()
    elif kind == "previous_false":
        body = (p.ROOT / p.CACHED / "request.json").read_bytes()
    elif kind == "retention":
        from . import retention_probe

        source = {name: (p.ROOT / name).read_bytes() for name in retention_probe.NAMES}
        files, _ = retention_probe._files(source, p.IDENTITY, "retention-probe-" + "a" * 32)
        body = files[f"requests/{retention_probe.SLOTS[0]}.json"]
    elif kind == "changed":
        value = p._load(body)
        value["think"] = False
        body = p._bytes(value)
    elif kind == "warmup":
        body = b'{"model":"qwen3.5:9b-q4_K_M","messages":[]}'
    elif kind == "show_extra":
        endpoint, body = "/api/show", b'{"model":"qwen3.5:9b-q4_K_M","verbose":true}'
    elif kind == "endpoint":
        endpoint = "/api/pull"
    elif kind == "redirect":
        method, endpoint = "GET", "http://example.invalid/api/tags"
    request = tmp_path / "request.json"
    request.write_bytes(body)

    def forbidden(*_a: Any, **_k: Any) -> Any:
        pytest.fail("Disallowed connect")

    with pytest.raises(ValueError):
        h.capture(
            method,
            endpoint,
            request,
            tmp_path,
            1,
            "f" * 64 if kind == "wrong_pin" else p._hash(body),
            connect=forbidden,
        )
    assert not (tmp_path / "origin.json").exists()
    assert set(h.CHAT_PINS).isdisjoint(old.CHAT_PINS) and len(old.CHAT_PINS) == 2


@pytest.mark.parametrize("failure", ["timeout", "interrupt", "wait", "spawn", "none"])
def test_parent_launches_new_child_source_once_and_keeps_kill_reap_protocol(
    tmp_path: Path, failure: str
) -> None:
    child = Child(failure)
    calls: list[list[str]] = []

    def spawn(command: list[str], **kwargs: Any) -> Child:
        calls.append(command)
        assert command[1:3] == ["-I", "-u"]
        assert command[3] == str(Path(h.__file__).resolve()) != str(Path(old.__file__).resolve())
        if failure == "spawn":
            raise OSError("Synthetic spawn failure")
        (Path(command[-3]) / "body.raw").write_bytes(b"partial")
        kwargs["stderr"].write(b"synthetic")
        return child

    output = tmp_path / "exchange"
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            h.exchange("GET", "/api/version", None, output, 10, None, spawn=spawn, clock=lambda: 1)
    else:
        h.exchange("GET", "/api/version", None, output, 10, None, spawn=spawn, clock=lambda: 1)
    state = json.loads((output / "exchange.json").read_bytes())
    assert len(calls) == 1
    assert state["killed"] == child.killed == (failure in ("timeout", "interrupt", "wait"))
    assert state["reaped"] == (failure != "spawn")
    assert state["server_compute_cancellation_guaranteed"] is False


@pytest.mark.parametrize("failure", ["headers", "partial", "length"])
def test_new_child_preserves_partial_read_errors_and_closes_connection(
    tmp_path: Path,
    failure: str,
) -> None:
    response = Response([b"saved", http.client.IncompleteRead(b"tail", 4)])
    if failure == "length":
        response = Response([b"saved"])
        response.length = 3
    connection = Connection(response)
    connection.header_error = failure == "headers"
    assert (
        h.capture(
            "GET",
            "/api/tags",
            None,
            tmp_path,
            1,
            None,
            connect=lambda *_a, **_k: connection,
        )
        == 1
    )
    assert (tmp_path / "body.raw").read_bytes() == (
        b"" if failure == "headers" else b"savedtail" if failure == "partial" else b"saved"
    )
    assert (tmp_path / "error.json").exists() and connection.closed


@pytest.mark.parametrize("save_failure", [OSError, SystemExit])
def test_original_interrupt_wins_over_exchange_accounting_save_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    save_failure: type[BaseException],
) -> None:
    child = Child("interrupt")

    def fail_save(_path: Path, _value: object) -> None:
        raise save_failure("Authored storage failure")

    monkeypatch.setattr(h, "save", fail_save)
    with pytest.raises(KeyboardInterrupt):
        h.exchange(
            "GET",
            "/api/version",
            None,
            tmp_path / "exchange",
            10,
            None,
            spawn=lambda *_a, **_k: child,
            clock=lambda: 1,
        )
    assert child.killed and child.waits == [9, None]


def test_expired_new_exchange_cannot_spawn(tmp_path: Path) -> None:
    def forbidden(*_a: Any, **_k: Any) -> Any:
        pytest.fail("Expired exchange cannot launch")

    state = h.exchange(
        "GET",
        "/api/version",
        None,
        tmp_path / "expired",
        1,
        None,
        spawn=forbidden,
        clock=lambda: 2,
    )
    assert state["timed_out"] and not state["reaped"] and state["overrun_seconds"] == 1


@pytest.mark.parametrize("endpoint", ["/api/version", "/api/tags", "/api/show"])
def test_only_fixed_bodyless_gets_and_model_only_show_are_allowed(
    tmp_path: Path,
    endpoint: str,
) -> None:
    request = tmp_path / "request.json" if endpoint == "/api/show" else None
    if request is not None:
        request.write_bytes(h.SHOW)
    connection = Connection(Response([b"{}\n"]))
    assert (
        h.capture(
            "POST" if request else "GET",
            endpoint,
            request,
            tmp_path,
            5,
            p._hash(h.SHOW) if request else None,
            connect=lambda *_a, **_k: connection,
        )
        == 0
    )
    assert connection.closed


def test_new_allowlist_is_independent_of_every_old_policy() -> None:
    from . import _retention_http, _work_review_http

    assert len(h.CHAT_PINS) == len(set(h.CHAT_PINS)) == 3
    for policy in (old, _retention_http, _work_review_http):
        assert set(h.CHAT_PINS).isdisjoint(policy.CHAT_PINS)
    assert p._hash((p.ROOT / p.CACHED / "request.json").read_bytes()) not in h.CHAT_PINS
    assert (
        h.capture is not _work_review_http.capture and h.exchange is not _work_review_http.exchange
    )
