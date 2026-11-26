"""The new child owns exactly four wire bodies; all connections/processes are fake."""

# pyright: reportPrivateUsage=false

import json
from pathlib import Path
from typing import Any

import pytest

from . import _retention_http as h
from . import _stream_http as old
from . import retention_probe as p
from .test_stream_http import Child, Connection, Response


def bodies() -> list[bytes]:
    source = {name: (p.ROOT / name).read_bytes() for name in p.NAMES}
    files, _ = p._files(source, p.IDENTITY, "retention-probe-" + "a" * 32)
    return [files[f"requests/{slot}.json"] for slot in p.SLOTS]


@pytest.mark.parametrize("index", range(4))
def test_child_accepts_each_exact_retention_body_and_fixed_loopback(
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
    elif kind == "changed":
        value = p._load(body)
        value["think"] = True
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
