"""Offline freeze and single-use streaming pair. Only explicit run() uses HTTP."""

# pyright: reportPrivateUsage=false

import re
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import _stream_http as http
from . import action_diagnostic as d
from . import actions

ROOT = Path(__file__).resolve().parents[2]
HERE = "prototypes/reviewable_draft/"
PROPOSAL = "evaluation/m10/reviewable-draft/runtime-investigation-1/"
OLD = "evaluation/m10/reviewable-draft/model-comparison-1/"
CASE = "accepted_status_answer"
SLOTS = ("01-think-false", "02-think-true")
DECLARATION = HERE + "RUNTIME_PROBE.md"
RUNTIME = (*d.RUNTIME, HERE + "runtime_probe.py", HERE + "_stream_http.py")
NAMES = (
    *RUNTIME,
    DECLARATION,
    HERE + "test_runtime_probe.py",
    HERE + "test_stream_http.py",
    d.DECLARATION,
    d.INPUT,
    PROPOSAL + "proposal.json",
    PROPOSAL + "proposed-requests/01-think-false.json",
    PROPOSAL + "proposed-requests/02-think-true.json",
    OLD + "results/01-02-accepted_status_answer/request.json",
    *(OLD + "source/" + name for name in d.RUNTIME),
)
LOADED = {
    **d.LOADED,
    **{n: d._hash((ROOT / n).read_bytes()) for n in RUNTIME if n not in d.LOADED},
}
LIMIT, GENERATION_LIMIT, METADATA_LIMIT = 420, 180, 10
IDENTITY: dict[str, Any] = dict(
    version="0.40.13",
    model=http.MODEL,
    digest="56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90",
    capabilities=["completion", "vision", "tools", "thinking"],
    thinking={"values": [False, True], "default": True},
    parameters="presence_penalty               1.5\ntemperature                    1\n"
    "top_k                          20\ntop_p                          0.95",
)
COUNTS = (
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
    "prompt_eval_count",
    "eval_count",
    "prompt_eval_cached_count",
)
_bytes, _hash = d._bytes, d._hash


def _load(data: bytes) -> dict[str, Any]:
    return d.json_helpers._load(data.decode("utf-8", errors="strict"))


def _safe(path: Path) -> Path:
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Paths must not traverse symlinks or parents")
    return path.absolute()


def _read(root: Path, name: str) -> bytes:
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Expected a relative artifact path")
    return _safe(root / name).read_bytes()


def _write(path: Path, data: bytes) -> None:
    d._write(_safe(path), data)


def _save(path: Path, value: object) -> None:
    _write(path, _bytes(value))


def _inventory(root: Path, *, omit_results: bool = False) -> dict[str, str]:
    _safe(root)
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        _safe(path)
        name = path.relative_to(root).as_posix()
        if omit_results and (name == "results" or name.startswith("results/")):
            continue
        if path.is_file():
            files[name] = _hash(path.read_bytes())
        elif not path.is_dir():
            raise ValueError("Artifacts must be ordinary files/directories")
    return files


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def _source(candidate: str | None = None) -> tuple[str, dict[str, bytes]]:
    head = _git("rev-parse", "HEAD").decode().strip()
    commit = head if candidate is None else candidate
    if type(commit) is not str or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Expected an exact reviewed source commit")
    _git("merge-base", "--is-ancestor", commit, head)
    if _git("status", "--porcelain=v1", "--untracked-files=all", "--", *NAMES):
        raise ValueError("Dirty source/input/proposal/declaration")
    source = {name: _read(ROOT, name) for name in NAMES}
    # One Git process avoids repeatedly paying process startup during every gate.
    blobs = subprocess.check_output(
        ["git", "-C", str(ROOT), "cat-file", "--batch"],
        input="".join(f"{commit}:{name}\n" for name in NAMES).encode(),
        stderr=subprocess.PIPE,
    )
    for name, data in source.items():
        header, blobs = blobs.split(b"\n", 1)
        fields = header.split()
        if len(fields) != 3 or fields[1] != b"blob":
            raise ValueError(f"Missing committed source blob: {name}")
        size = int(fields[2])
        committed, blobs = blobs[:size], blobs[size + 1 :]
        if data != committed:
            raise ValueError(f"Committed source drift: {name}")
        if name in LOADED and _hash(data) != LOADED[name]:
            raise ValueError(f"Imported source drift: {name}; use a fresh interpreter")
    for name in d.RUNTIME:
        if source[name] != source[OLD + "source/" + name]:
            raise ValueError("Original decoder/runtime differs from committed historical freeze")
    return commit, source


def _identity(value: object) -> dict[str, Any]:
    identity = d.json_helpers._object(value)
    if _bytes(identity) != _bytes(IDENTITY):
        raise ValueError("Identity/defaults differ from the fresh 0.40.13 declaration")
    return identity


def _settings() -> dict[str, Any]:
    return dict(
        contract="runtime-streaming-pair-1",
        case=CASE,
        requests=2,
        order=[False, True],
        stream=True,
        seconds=LIMIT,
        per_generation_seconds=GENERATION_LIMIT,
        per_metadata_seconds=METADATA_LIMIT,
        retries=0,
        server_compute_cancellation_guaranteed=False,
    )


def _files(
    source: dict[str, bytes],
    identity: dict[str, Any],
    generation: str,
) -> tuple[dict[str, bytes], tuple[actions.Prepared, ...]]:
    if type(generation) is not str or not re.fullmatch("runtime-probe-[0-9a-f]{32}", generation):
        raise ValueError("Invalid host generation identity")
    snapshots = d._snapshots(source[d.INPUT])
    packets = tuple(
        next(
            p
            for p in actions.prepare(snapshots, f"{generation}/{slot}")
            if p.snapshot == snapshots[CASE]
        )
        for slot in SLOTS
    )
    files = {"source/" + name: data for name, data in source.items()}
    files.update(
        {
            "identity.json": _bytes(identity),
            "settings.json": _bytes(_settings()),
            "show-request.json": http.SHOW,
            "snapshot.json": d._snapshot_bytes({CASE: snapshots[CASE]}),
        }
    )
    old = source[OLD + "results/01-02-accepted_status_answer/request.json"]
    if _hash(old) != "31830bb17204c729a13ae2ad6bd422c7ad7e0554f4522419fdef121b71843c9e":
        raise ValueError("Historical actual request drift")
    proposal = _load(source[PROPOSAL + "proposal.json"])
    if (
        proposal["case"],
        proposal["generation_requests"],
        proposal["overall_seconds"],
        proposal["per_generation_seconds"],
        proposal["retries"],
    ) != (CASE, 2, 420, 180, 0):
        raise ValueError("Proposal scope drift")
    bindings: dict[str, Any] = {}
    for index, (slot, packet) in enumerate(zip(SLOTS, packets, strict=True)):
        body = packet.body()
        body.update(model=http.MODEL, stream=True, think=bool(index))
        wire = _bytes(body)
        proposed = source[PROPOSAL + f"proposed-requests/{slot}.json"]
        historical = _load(old)
        historical.update(stream=True, think=bool(index))
        if wire != proposed or _hash(wire) != http.CHAT_PINS[index] or wire != _bytes(historical):
            raise ValueError("Actual wire bytes differ from approved proposed requests")
        files[f"requests/{slot}.json"] = wire
        bindings[slot] = dict(
            generation_id=packet.generation_id,
            snapshot_id=packet.snapshot.snapshot_id,
            request_sha256=_hash(wire),
            internal_decoder_request_sha256=_hash(packet.request_json.encode()),
        )
    files["bindings.json"] = _bytes(bindings)
    return files, packets


def _manifest(
    commit: str, generation: str, identity: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    return dict(
        format="runtime-streaming-pair-1",
        candidate_commit=commit,
        generation_id=generation,
        identity=identity,
        settings=_settings(),
        files={name: _hash(data) for name, data in files.items()},
    )


def freeze(output: Path, identity: dict[str, Any]) -> str:
    """Exclusively freeze committed source, declarations and exact wire bytes; no HTTP."""
    output = _safe(output)
    output.mkdir(parents=True, exist_ok=False)
    identity = _identity(identity)
    commit, source = _source()
    generation = f"runtime-probe-{uuid.uuid4().hex}"
    files, _ = _files(source, identity, generation)
    manifest = _manifest(commit, generation, identity, files)
    for name, data in files.items():
        _write(output / name, data)
    _save(output / "manifest.json", manifest)
    return _hash(_bytes(manifest))


def _validate(output: Path, pin: str) -> tuple[dict[str, Any], tuple[actions.Prepared, ...]]:
    data = _read(output, "manifest.json")
    if type(pin) is not str or not re.fullmatch("[0-9a-f]{64}", pin) or _hash(data) != pin:
        raise ValueError("Manifest pin drift")
    manifest = _load(data)
    identity = _identity(manifest["identity"])
    commit, source = _source(manifest["candidate_commit"])
    files, packets = _files(source, identity, manifest["generation_id"])
    expected = _manifest(commit, manifest["generation_id"], identity, files)
    if data != _bytes(expected):
        raise ValueError("Frozen manifest/declaration drift")
    inventory = {**expected["files"], "manifest.json": pin}
    if _inventory(output, omit_results=True) != inventory:
        raise ValueError("Frozen source/request/identity/inventory drift")
    return manifest, packets


class Stream:
    """Strict NDJSON accumulation; partial text never constitutes a valid reply."""

    def __init__(self) -> None:
        self.pending = b""
        self.content = ""
        self.thinking = ""
        self.events = 0
        self.done = False
        self.error: str | None = None
        self.first_byte: float | None = None
        self.first_thinking: float | None = None
        self.first_content: float | None = None
        self.returned: dict[str, Any] = {}

    def feed(self, chunk: bytes, received: float) -> None:
        if chunk and self.first_byte is None:
            self.first_byte = received
        self.pending += chunk
        while b"\n" in self.pending and self.error is None:
            line, self.pending = self.pending.split(b"\n", 1)
            try:
                self._event(_load(line), received)
            except (ValueError, TypeError, KeyError, UnicodeError) as error:
                self.error = f"{type(error).__name__}: {error}"

    def _event(self, event: dict[str, Any], received: float) -> None:
        if self.done:
            raise ValueError("Trailing event after terminal event")
        allowed = {"model", "created_at", "message", "done", "done_reason", *COUNTS}
        if not set(event) <= allowed or not {"model", "message", "done"} <= event.keys():
            raise ValueError("Malformed/error stream event")
        if event["model"] != http.MODEL or type(event["done"]) is not bool:
            raise ValueError("Stream model/done identity differs")
        if "created_at" in event and type(event["created_at"]) is not str:
            raise ValueError("Malformed created_at")
        message = d.json_helpers._object(event["message"])
        if (
            not {"role", "content"} <= message.keys()
            or not set(message) <= {"role", "content", "thinking"}
            or message["role"] != "assistant"
            or type(message["content"]) is not str
            or ("thinking" in message and type(message["thinking"]) is not str)
        ):
            raise ValueError("Malformed assistant message")
        counts = {name: event[name] for name in COUNTS if name in event}
        if any(type(v) is not int or v < 0 for v in counts.values()):
            raise ValueError("Malformed returned count/duration")
        if event["done"]:
            if event.get("done_reason") != "stop":
                raise ValueError("Incomplete/length terminal event")
        elif "done_reason" in event or counts:
            raise ValueError("Terminal fields on a nonterminal event")
        content, thinking = message["content"], message.get("thinking", "")
        content.encode("utf-8", errors="strict")
        thinking.encode("utf-8", errors="strict")
        if content and self.first_content is None:
            self.first_content = received
        if thinking and self.first_thinking is None:
            self.first_thinking = received
        self.content += content
        self.thinking += thinking
        self.events += 1
        self.done = event["done"]
        if self.done:
            self.returned = counts

    def progress(self) -> dict[str, Any]:
        valid = self.done and not self.pending and self.error is None
        return dict(
            valid=valid,
            complete_events=self.events,
            terminal_seen=self.done,
            error=self.error or (None if valid else "Incomplete NDJSON stream"),
            trailing_bytes=len(self.pending),
            content_characters=len(self.content),
            thinking_characters=len(self.thinking),
            first_byte_seconds=self.first_byte,
            first_thinking_seconds=self.first_thinking,
            first_content_seconds=self.first_content,
            timing_basis="received complete event relative to child monotonic origin; not GPU time",
            sizes_are_tokens=False,
            returned=self.returned,
        )


def _stream(directory: Path) -> Stream:
    """Replay complete logged chunks plus any unlogged partial tail after child failure."""
    stream = Stream()
    raw_path = directory / "body.raw"
    raw = raw_path.read_bytes() if raw_path.exists() else b""
    chunks = directory / "chunks.jsonl"
    offset, previous = 0, 0.0
    try:
        for line in chunks.read_bytes().splitlines(keepends=True) if chunks.exists() else []:
            if not line.endswith(b"\n"):
                break  # A kill between raw.write and chunks.write can leave unlogged bytes.
            row = _load(line)
            start, length, seconds = row["offset"], row["length"], row["seconds"]
            if (
                set(row) != {"offset", "length", "seconds"}
                or type(start) is not int
                or type(length) is not int
                or length <= 0
                or start != offset
                or offset + length > len(raw)
                or type(seconds) not in (int, float)
                or not previous <= seconds < float("inf")
            ):
                raise ValueError("Invalid raw-chunk index")
            stream.feed(raw[offset : offset + length], seconds)
            offset += length
            previous = seconds
        if offset != len(raw):
            # Parse progress, but do not invent a receive timestamp for unlogged bytes.
            known = (stream.first_byte, stream.first_thinking, stream.first_content)
            stream.feed(raw[offset:], previous)
            stream.first_byte, stream.first_thinking, stream.first_content = known
            stream.error = stream.error or "Unlogged raw tail; receive timing unknown"
    except Exception as error:
        stream.error = f"{type(error).__name__}: {error}"
    return stream


def _observe(slot: Path) -> Stream:
    stream = _stream(slot / "response")
    _save(slot / "progress.json", stream.progress())
    _save(slot / "observed.json", dict(content=stream.content, thinking=stream.thinking))
    return stream


Exchange = Callable[[str, str, Path | None, Path, float, str | None], dict[str, Any]]


def _remaining(deadline: float, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError("Shared 420-second deadline reached")
    return remaining


def _checked_exchange(
    method: str,
    endpoint: str,
    request: Path | None,
    directory: Path,
    deadline: float,
    pin: str | None,
    exchange: Exchange,
    clock: Callable[[], float],
) -> bytes:
    _remaining(deadline, clock)
    state = exchange(method, endpoint, request, directory, deadline, pin)
    if state.get("error") or state.get("returncode") != 0 or state.get("timed_out"):
        raise OSError(f"Exchange failed: {state}")
    _remaining(deadline, clock)
    headers = _load(_read(directory, "headers.json"))
    if type(headers.get("status")) is not int or headers["status"] != 200:
        raise ValueError("Expected HTTP 200")
    if (directory / "error.json").exists():
        raise OSError("HTTP child error artifact")
    return _read(directory, "body.raw")


def _gate(
    output: Path,
    pin: str,
    directory: Path,
    deadline: float,
    exchange: Exchange,
    clock: Callable[[], float],
) -> None:
    _remaining(deadline, clock)
    manifest, _ = _validate(output, pin)
    identity = manifest["identity"]
    replies: dict[str, dict[str, Any]] = {}
    for name in ("version", "tags", "show"):
        _remaining(deadline, clock)
        body = _checked_exchange(
            "POST" if name == "show" else "GET",
            "/api/" + name,
            output / "show-request.json" if name == "show" else None,
            directory / name,
            min(deadline, clock() + METADATA_LIMIT),
            _hash(http.SHOW) if name == "show" else None,
            exchange,
            clock,
        )
        replies[name] = _load(body)
    if replies["version"].get("version") != identity["version"]:
        raise ValueError("Live service version drift")
    models = d._rows(replies["tags"].get("models"))
    matches = [
        d.json_helpers._object(m)
        for m in models
        if d.json_helpers._object(m).get("name") == identity["model"]
    ]
    if len(matches) != 1 or matches[0].get("digest") != identity["digest"]:
        raise ValueError("Live model digest drift")
    show = replies["show"]
    if any(
        _bytes(show.get(k)) != _bytes(identity[k])
        for k in ("capabilities", "thinking", "parameters")
    ):
        raise ValueError("Live model capabilities/thinking/defaults drift")
    _validate(output, pin)
    _remaining(deadline, clock)


def run(output: Path, approval: str, pin: str) -> dict[str, Any]:
    """Return sealed accounting and a separate post-seal observation; consume once."""
    return _run(output, approval, pin, http.exchange, time.monotonic)


def _run(
    output: Path,
    approval: str,
    pin: str,
    exchange: Exchange,
    clock: Callable[[], float],
) -> dict[str, Any]:
    started = clock()
    deadline = started + LIMIT
    output = _safe(output)
    results = output / "results"
    results.mkdir(exist_ok=False)
    rows: list[dict[str, Any]] = [
        dict(slot=s, think=bool(i), state="unsent", possibly_sent=False)
        for i, s in enumerate(SLOTS)
    ]
    stop = "capture complete; separate semantic assessment pending"
    complete = False
    active: dict[str, Any] | None = None
    slot_started = started
    artifact_errors: list[str] = []
    interrupt: BaseException | None = None

    def accounting(boundary: str, *, authoritative: bool) -> dict[str, Any]:
        ended = clock()
        reason = stop
        if complete and ended >= deadline:
            reason = "Shared 420-second deadline during final saving/cleanup"
        elif complete and artifact_errors:
            reason = "Capture finalization failed; see artifact_errors"
        return dict(
            authoritative=authoritative,
            accounting_boundary=boundary,
            capture_complete=complete and not artifact_errors and ended < deadline,
            possibly_sent=sum(r["possibly_sent"] for r in rows),
            slots=[dict(r) for r in rows],
            completed=[r["slot"] for r in rows if r["state"] == "complete"],
            failed=[r["slot"] for r in rows if r["state"] == "failed"],
            unsent=[r["slot"] for r in rows if not r["possibly_sent"]],
            stop_reason=reason,
            artifact_errors=list(artifact_errors),
            elapsed=ended - started,
            overrun_seconds=max(0.0, ended - deadline),
            server_compute_cancellation_guaranteed=False,
        )

    try:
        _save(
            results / "running.json",
            dict(
                approval=approval,
                approval_is_authentication=False,
                manifest_sha256=pin,
                started_monotonic=started,
                deadline_monotonic=deadline,
                settings=_settings(),
            ),
        )
        if type(approval) is not str or not approval.strip():
            raise ValueError("Nonempty approval audit context required")
        _remaining(deadline, clock)
        _, packets = _validate(output, pin)
        _remaining(deadline, clock)
        for row, packet in zip(rows, packets, strict=True):
            active = row
            slot_started = clock()
            slot = results / row["slot"]
            slot.mkdir()
            _gate(output, pin, slot / "before", deadline, exchange, clock)
            request = _read(output, f"requests/{row['slot']}.json")
            _write(slot / "request.json", request)
            _validate(output, pin)
            _remaining(deadline, clock)
            if _read(slot, "request.json") != request:
                raise ValueError("Actual request drift before generation")
            # Conservative even if spawn fails or the deadline expires before the POST.
            row.update(state="attempted", possibly_sent=True)
            _save(
                slot / "attempt.json",
                dict(
                    possibly_sent=True,
                    request_sha256=_hash(request),
                    manifest_sha256=pin,
                    generation_id=packet.generation_id,
                    snapshot_id=packet.snapshot.snapshot_id,
                    started_monotonic=clock(),
                ),
            )
            generation_deadline = min(deadline, clock() + GENERATION_LIMIT)
            row["generation_deadline_monotonic"] = generation_deadline
            stream = Stream()
            try:
                _checked_exchange(
                    "POST",
                    "/api/chat",
                    slot / "request.json",
                    slot / "response",
                    generation_deadline,
                    _hash(request),
                    exchange,
                    clock,
                )
            except BaseException:
                if (slot / "response").exists():
                    try:
                        _observe(slot)
                    except Exception as saving_error:
                        artifact_errors.append(f"Progress save: {saving_error}")
                raise
            else:
                stream = _observe(slot)
            _remaining(deadline, clock)
            _gate(output, pin, slot / "after", deadline, exchange, clock)
            if _read(slot, "request.json") != request:
                raise ValueError("Actual request changed during generation")
            if not stream.progress()["valid"]:
                raise ValueError(f"Invalid stream: {stream.progress()['error']}")
            result = actions.decode(packet, stream.content)
            _save(slot / "result.json", asdict(result))
            if result.issues:
                raise ValueError("Literal selection failure; see preserved result issues")
            _write(slot / "actions.md", actions.render_result(result).encode())
            _validate(output, pin)
            _remaining(deadline, clock)
            row.update(state="complete", elapsed=clock() - slot_started)
            active = None
        complete = True
    except BaseException as error:
        stop = f"{type(error).__name__}: {error}"
        if active is not None:
            active.update(
                state="failed" if active["possibly_sent"] else "unsent",
                error=stop,
                elapsed=clock() - slot_started,
            )
        if not isinstance(error, Exception):
            interrupt = error
    finally:
        # Best effort after storage errors: never lose all other accounting to one artifact.
        for row in rows:
            slot = results / row["slot"]
            try:
                response = slot / "response"
                if (response / "exchange.json").exists():
                    row["exchange"] = _load(_read(response, "exchange.json"))
                if (slot / "progress.json").exists():
                    row["progress"] = _load(_read(slot, "progress.json"))
                if not (slot / "outcome.json").exists():
                    _save(slot / "outcome.json", row)
            except BaseException as error:
                artifact_errors.append(f"{row['slot']}: {type(error).__name__}: {error}")
                if not isinstance(error, Exception):
                    interrupt = interrupt or error
        inventory: dict[str, str] | None = None
        try:
            inventory = _inventory(results)
        except BaseException as error:
            artifact_errors.append(f"Inventory: {type(error).__name__}: {error}")
            if not isinstance(error, Exception):
                interrupt = interrupt or error
        try:
            _save(
                results / "final.json",
                accounting(
                    "pre-save snapshot, before final.json write; consult manifest.json accounting",
                    authoritative=False,
                ),
            )
        except BaseException as saving_error:
            artifact_errors.append(f"Final save: {saving_error}")
            if not isinstance(saving_error, Exception):
                interrupt = interrupt or saving_error
        sealed = False
        final = accounting("unsealed: inventory unavailable", authoritative=False)
        try:
            if inventory is not None:
                if (results / "final.json").exists():
                    inventory["final.json"] = _hash(_read(results, "final.json"))
                final = accounting(
                    "after final.json save and inventory hashing; before manifest.json write",
                    authoritative=True,
                )
                _save(
                    results / "manifest.json",
                    dict(files=inventory, accounting=final),
                )
                sealed = True
        except BaseException as saving_error:
            artifact_errors.append(f"Seal save/hash: {saving_error}")
            if not isinstance(saving_error, Exception):
                interrupt = interrupt or saving_error
            final = accounting("unsealed: manifest save/hash failed", authoritative=False)
    ended = clock()
    if interrupt is not None:
        raise interrupt
    # Never silently revise accounting after its write-once seal.
    return dict(
        accounting=final,
        post_seal_observation=dict(
            boundary="after manifest write attempt; separate from sealed accounting",
            sealed=sealed,
            elapsed=ended - started,
            overrun_seconds=max(0.0, ended - deadline),
            deadline_reached=ended >= deadline,
        ),
    )
