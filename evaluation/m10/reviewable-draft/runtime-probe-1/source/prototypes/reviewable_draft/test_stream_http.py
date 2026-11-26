"""Authored HTTP/process doubles only; never connect to Ollama."""

import http.client
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from . import _stream_http as h


class Response:
    status = 200
    length: int | None = None

    def __init__(self, chunks: list[bytes | Exception]) -> None:
        self.chunks = chunks

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/x-ndjson"), ("X-Example", "synthetic")]

    def read1(self, _: int) -> bytes:
        if not self.chunks:
            return b""
        value = self.chunks.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[tuple[str, str, bytes | None]] = []
        self.closed = False
        self.header_error = False

    def request(
        self, method: str, endpoint: str, body: bytes | None, headers: dict[str, str]
    ) -> None:
        assert headers == {"Content-Type": "application/json"}
        self.calls.append((method, endpoint, body))

    def getresponse(self) -> Response:
        if self.header_error:
            raise OSError("Synthetic header failure")
        return self.response

    def close(self) -> None:
        self.closed = True


def test_child_flushes_exact_split_bytes_offsets_origin_and_headers(tmp_path: Path) -> None:
    connection = Connection(Response([b"first\n\xc3", b"\xa9", b"last\n"]))
    ticks = iter([10.0, 10.1, 10.5, 11.0])

    def connect(host: str, port: int, *, timeout: float) -> Connection:
        assert (host, port, timeout) == ("127.0.0.1", 11434, 5)
        return connection

    assert (
        h.capture(
            "GET",
            "/api/version",
            None,
            tmp_path,
            5,
            None,
            connect=connect,
            clock=lambda: next(ticks),
        )
        == 0
    )
    assert (tmp_path / "body.raw").read_bytes() == b"first\n\xc3\xa9last\n"
    rows = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_bytes().splitlines()]
    assert [(r["offset"], r["length"]) for r in rows] == [(0, 7), (7, 1), (8, 5)]
    assert [r["seconds"] for r in rows] == pytest.approx([0.1, 0.5, 1])
    assert json.loads((tmp_path / "origin.json").read_bytes())["monotonic"] == 10
    assert json.loads((tmp_path / "headers.json").read_bytes())["status"] == 200
    assert connection.closed


@pytest.mark.parametrize("failure", ["headers", "body", "length", "partial"])
def test_child_preserves_errors_and_partial_raw(tmp_path: Path, failure: str) -> None:
    response = Response([b"saved", OSError("Synthetic body failure")])
    if failure == "length":
        response = Response([b"saved"])
        response.length = 3
    if failure == "partial":
        response = Response([b"saved", http.client.IncompleteRead(b"tail", 4)])
    connection = Connection(response)
    connection.header_error = failure == "headers"
    assert (
        h.capture("GET", "/api/tags", None, tmp_path, 1, None, connect=lambda *_a, **_k: connection)
        == 1
    )
    assert (tmp_path / "body.raw").read_bytes() == (
        b"" if failure == "headers" else b"savedtail" if failure == "partial" else b"saved"
    )
    assert (tmp_path / "error.json").exists() and connection.closed


@pytest.mark.parametrize("endpoint", ["/api/chat", "/api/show"])
def test_child_only_posts_hash_bound_fixed_requests(tmp_path: Path, endpoint: str) -> None:
    if endpoint == "/api/show":
        body = h.SHOW
    else:
        body = (
            Path(__file__).resolve().parents[2]
            / "evaluation/m10/reviewable-draft/runtime-investigation-1/"
            "proposed-requests/01-think-false.json"
        ).read_bytes()
    request = tmp_path / "request.json"
    request.write_bytes(body)
    output = tmp_path / "output"
    output.mkdir()
    connection = Connection(Response([b"{}\n"]))
    assert (
        h.capture(
            "POST",
            endpoint,
            request,
            output,
            1,
            h.hashlib.sha256(body).hexdigest(),
            connect=lambda *_a, **_k: connection,
        )
        == 0
    )
    assert connection.calls == [("POST", endpoint, body)]


@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("POST", "/api/generate"),
        ("GET", "/api/chat"),
        ("POST", "/api/pull"),
        ("GET", "http://example.invalid/api/tags"),
    ],
)
def test_child_rejects_other_endpoints_before_connect(
    tmp_path: Path,
    method: str,
    endpoint: str,
) -> None:
    def forbidden(*_a: Any, **_kw: Any) -> Any:
        pytest.fail("Forbidden connect")

    with pytest.raises(ValueError):
        h.capture(method, endpoint, None, tmp_path, 1, None, connect=forbidden)


@pytest.mark.parametrize(
    "endpoint,body",
    [
        ("/api/chat", b"{}"),
        ("/api/show", b'{"model":"wrong"}'),
    ],
)
def test_child_rejects_warmups_and_unbound_requests(
    tmp_path: Path,
    endpoint: str,
    body: bytes,
) -> None:
    request = tmp_path / "request.json"
    request.write_bytes(body)
    with pytest.raises(ValueError, match="not sent"):
        h.capture("POST", endpoint, request, tmp_path, 1, h.hashlib.sha256(body).hexdigest())


class Child:
    def __init__(self, failure: str) -> None:
        self.failure = failure
        self.waits: list[float | None] = []
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        if len(self.waits) == 1:
            if self.failure == "timeout":
                raise subprocess.TimeoutExpired("synthetic", timeout or 1)
            if self.failure == "interrupt":
                raise KeyboardInterrupt
            if self.failure == "wait":
                raise OSError("Synthetic wait failure")
        return 7 if self.failure == "exit" else 0

    def kill(self) -> None:
        self.killed = True


@pytest.mark.parametrize("failure", ["timeout", "interrupt", "wait", "exit", "spawn", "none"])
def test_parent_enforces_deadline_preserves_partial_and_reaps_only_child(
    tmp_path: Path,
    failure: str,
) -> None:
    child = Child(failure)
    launches = 0

    def spawn(command: list[str], **kwargs: Any) -> Child:
        nonlocal launches
        launches += 1
        assert command[1:3] == ["-I", "-u"]
        assert command[-6:-4] == ["GET", "/api/version"]
        if failure == "spawn":
            raise OSError("Synthetic spawn failure")
        (Path(command[-3]) / "body.raw").write_bytes(b"partial\n")
        kwargs["stderr"].write(b"Synthetic stderr")
        return child

    output = tmp_path / "exchange"
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            h.exchange("GET", "/api/version", None, output, 10, None, spawn=spawn, clock=lambda: 1)
    else:
        h.exchange("GET", "/api/version", None, output, 10, None, spawn=spawn, clock=lambda: 1)
    record = json.loads((output / "exchange.json").read_bytes())
    assert launches == 1
    assert record["killed"] == child.killed == (failure in ("timeout", "interrupt", "wait"))
    assert record["reaped"] == (failure != "spawn")
    assert record["timed_out"] == (failure == "timeout")
    assert record["server_compute_cancellation_guaranteed"] is False
    assert child.waits == ([9, None] if child.killed else [] if failure == "spawn" else [9])
    if failure != "spawn":
        assert (output / "body.raw").read_bytes() == b"partial\n"
        assert (output / "stderr.raw").read_bytes() == b"Synthetic stderr"


def test_expired_exchange_does_not_launch(tmp_path: Path) -> None:
    def forbidden(*_a: Any, **_kw: Any) -> Any:
        pytest.fail("Expired exchange must not launch")

    record = h.exchange(
        "GET", "/api/version", None, tmp_path / "expired", 1, None, spawn=forbidden, clock=lambda: 2
    )
    assert record["timed_out"] and not record["reaped"] and record["overrun_seconds"] == 1
