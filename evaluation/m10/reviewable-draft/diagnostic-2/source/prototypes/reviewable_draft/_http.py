"""One fixed-loopback exchange, isolated so the parent can enforce a wall deadline."""

import hashlib
import http.client
import json
import sys
from pathlib import Path


def capture(
    method: str,
    endpoint: str,
    request: Path | None,
    output: Path,
    timeout: float,
    request_sha256: str | None = None,
) -> int:
    if (method, endpoint) not in {
        ("GET", "/api/version"),
        ("GET", "/api/tags"),
        ("POST", "/api/chat"),
    }:
        raise ValueError("Only fixed diagnostic endpoints are allowed")
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=timeout)
    try:
        # Unbuffered incremental capture survives a killed worker, including partial bodies.
        with (output / "body.raw").open("xb", buffering=0) as raw:
            body = request.read_bytes() if request is not None else None
            if method == "POST" and (
                body is None or hashlib.sha256(body).hexdigest() != request_sha256
            ):
                raise ValueError("Case request hash changed; not sent")
            connection.request(method, endpoint, body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            with (output / "headers.json").open("x") as stream:
                json.dump({"status": response.status, "headers": response.getheaders()}, stream)
            while True:
                try:
                    chunk = response.read1(65536)
                except http.client.IncompleteRead as error:
                    raw.write(error.partial)
                    raise
                if not chunk:
                    break
                raw.write(chunk)
            if response.length not in (None, 0):
                raise http.client.IncompleteRead(b"", response.length)
        return 0
    except FileExistsError:
        raise
    except Exception as error:
        with (output / "error.json").open("x") as stream:
            json.dump({"error": f"{type(error).__name__}: {error}"}, stream)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    method, endpoint, request, output, timeout, request_sha256 = sys.argv[1:]
    raise SystemExit(
        capture(
            method,
            endpoint,
            None if request == "-" else Path(request),
            Path(output),
            float(timeout),
            None if request_sha256 == "-" else request_sha256,
        )
    )
