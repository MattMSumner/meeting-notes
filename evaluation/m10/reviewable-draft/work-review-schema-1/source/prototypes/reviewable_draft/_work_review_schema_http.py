"""Three-body schema loopback child; accepted transport mechanics stay unchanged."""

import hashlib
import http.client
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODEL = "qwen3.5:9b-q4_K_M"
CHAT_PINS = (
    "6556b82b67090f38798c89cdb82445a358b65658ba0eeb348127a7ed9655ee3e",
    "35bd3ba7659a74932ede68812a51c5cb20f30d1044ba57c936108334dedd92c4",
    "a3b65116c2dfe5db7842c9d04160889cb785d8a0921588eae204d3819b44d546",
)
SHOW = json.dumps({"model": MODEL}, sort_keys=True).encode()
# Keep the helper's own import boundary, even when the collector is imported later.
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False, sort_keys=True)
        stream.flush()


def capture(
    method: str,
    endpoint: str,
    request: Path | None,
    output: Path,
    timeout: float,
    pin: str | None,
    *,
    connect: Callable[..., Any] = http.client.HTTPConnection,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Only this explicitly invoked function performs HTTP; no redirects or retries."""
    if (method, endpoint) not in {
        ("GET", "/api/version"),
        ("GET", "/api/tags"),
        ("POST", "/api/show"),
        ("POST", "/api/chat"),
    }:
        raise ValueError("Disallowed endpoint")
    body = request.read_bytes() if request is not None else None
    if method == "GET":
        if body is not None or pin is not None:
            raise ValueError("Metadata GET must have no body")
    elif (
        body is None
        or hashlib.sha256(body).hexdigest() != pin
        or (endpoint == "/api/show" and body != SHOW)
        or (endpoint == "/api/chat" and pin not in CHAT_PINS)
    ):
        raise ValueError("Request differs from fixed wire bytes; not sent")
    origin = clock()
    save(
        output / "origin.json",
        {"clock": "time.monotonic", "monotonic": origin, "utc": datetime.now(UTC).isoformat()},
    )
    connection = connect("127.0.0.1", 11434, timeout=timeout)
    try:
        with (
            (output / "body.raw").open("xb", buffering=0) as raw,
            (output / "chunks.jsonl").open("xb", buffering=0) as chunks,
        ):
            offset = 0

            def record(chunk: bytes) -> None:
                nonlocal offset
                if chunk:
                    received = clock() - origin
                    raw.write(chunk)
                    chunks.write(
                        (
                            json.dumps(dict(offset=offset, length=len(chunk), seconds=received))
                            + "\n"
                        ).encode()
                    )
                    offset += len(chunk)

            connection.request(method, endpoint, body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            save(
                output / "headers.json",
                {"status": response.status, "headers": response.getheaders()},
            )
            while True:
                try:
                    chunk = response.read1(65536)
                except http.client.IncompleteRead as error:
                    record(error.partial)
                    raise
                if not chunk:
                    break
                record(chunk)
            if response.length not in (None, 0):
                raise http.client.IncompleteRead(b"", response.length)
        return 0
    except Exception as error:
        save(output / "error.json", {"error": f"{type(error).__name__}: {error}"})
        return 1
    finally:
        connection.close()


def exchange(
    method: str,
    endpoint: str,
    request: Path | None,
    output: Path,
    deadline: float,
    pin: str | None,
    *,
    spawn: Callable[..., Any] = subprocess.Popen,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Enforce the wall deadline and kill/reap only our HTTP child on failure."""
    output.mkdir(parents=True, exist_ok=False)
    started = clock()
    state: dict[str, Any] = dict(
        started_monotonic=started,
        deadline_monotonic=deadline,
        killed=False,
        reaped=False,
        timed_out=False,
        returncode=None,
        error=None,
        server_compute_cancellation_guaranteed=False,
    )
    child: Any = None
    interrupt: BaseException | None = None
    try:
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("Exchange deadline before launch")
        with (
            (output / "stderr.raw").open("xb", buffering=0) as stderr,
            (output / "stdout.raw").open("xb", buffering=0) as stdout,
        ):
            child = spawn(
                [
                    sys.executable,
                    "-I",
                    "-u",
                    str(Path(__file__).resolve()),
                    method,
                    endpoint,
                    "-" if request is None else str(request),
                    str(output),
                    str(remaining),
                    "-" if pin is None else pin,
                ],
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
            )
            remaining = deadline - clock()
            if remaining <= 0:
                raise TimeoutError("Exchange deadline after launch")
            state["returncode"] = child.wait(timeout=remaining)
            state["reaped"] = True
            if state["returncode"] != 0:
                raise OSError(f"HTTP child exited {state['returncode']}")
            if clock() >= deadline:
                raise TimeoutError("Exchange deadline reached")
    except BaseException as error:
        state["error"] = f"{type(error).__name__}: {error}"
        state["timed_out"] = isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
        if child is not None and not state["reaped"]:
            try:
                child.kill()
                state["killed"] = True
            except Exception as cleanup_error:
                state["kill_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
            try:
                state["returncode"] = child.wait()
                state["reaped"] = True
            except Exception as cleanup_error:
                state["reap_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
        if not isinstance(error, Exception):
            interrupt = error
    finally:
        ended = clock()
        state.update(elapsed=ended - started, overrun_seconds=max(0.0, ended - deadline))
        try:
            save(output / "exchange.json", state)
        except BaseException:
            if interrupt is not None:
                raise interrupt from None
            raise
    if interrupt is not None:
        raise interrupt
    return state


if __name__ == "__main__":
    method, endpoint, request, output, timeout, pin = sys.argv[1:]
    raise SystemExit(
        capture(
            method,
            endpoint,
            None if request == "-" else Path(request),
            Path(output),
            float(timeout),
            None if pin == "-" else pin,
        )
    )
