"""Seven-case passage-selection freeze and single-use, host-assessed capture."""

# pyright: reportPrivateUsage=false

import re
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import _work_review_http as http
from . import action_diagnostic as d
from . import retention_probe as retention
from . import runtime_probe as runtime
from . import work_review as review
from . import work_review_examples as examples

ROOT = Path(__file__).resolve().parents[2]
HERE = runtime.HERE
CASES = examples.CASES
SLOTS = tuple(f"{index:02}-{case}" for index, case in enumerate(CASES, 1))
DECLARATION = HERE + "WORK_REVIEW_PROBE.md"
PROPOSAL = HERE + "work-review-proposal/"
PREVIEWS = (
    "partial-withdrawal.md",
    "replacement.md",
    "qualified-timing.md",
    "additional.md",
    "availability.md",
    "price-fact.md",
    "longer-context.md",
)
RUNTIME = (
    *retention.RUNTIME,
    *(
        HERE + name
        for name in (
            "work_review.py",
            "work_review_examples.py",
            "work_review_probe.py",
            "_work_review_http.py",
        )
    ),
)
NAMES = tuple(
    dict.fromkeys(
        (
            *retention.NAMES,
            *RUNTIME,
            DECLARATION,
            HERE + "WORK_REVIEW.md",
            HERE + "test_work_review.py",
            HERE + "test_work_review_examples.py",
            HERE + "test_work_review_probe.py",
            HERE + "test_work_review_http.py",
            *(
                PROPOSAL + name
                for name in (
                    "examples.json",
                    "authored-longer-input.json",
                    "sources.md",
                    *PREVIEWS,
                )
            ),
        )
    )
)
# Preserve inherited baselines independently; never refresh already imported modules.
LOADED = {
    **retention.LOADED,
    **{n: d._hash((ROOT / n).read_bytes()) for n in RUNTIME if n not in retention.LOADED},
    HERE + "_work_review_http.py": http.LOADED_SOURCE_SHA256,
}
# These accepted modules do not publish import baselines of their own.
ACCEPTED = {
    HERE + "work_review.py": "2f942043ae90a892141d81b7d705666d4e15e2907ed09d6ec4c2c4f59c493a68",
    HERE
    + "work_review_examples.py": "3ba19e633ff4d9bfcf20440a4d8a5e02ee4cc026e6ebf397be8b66c516883715",
    HERE + "WORK_REVIEW.md": "b14af073e970e67d753f9103d9cae9e0791ca331c8ca0898c024dc636e4325be",
}
LIMIT, GENERATION_LIMIT, METADATA_LIMIT = 1500, 180, 10
IDENTITY = runtime.IDENTITY
_bytes, _hash, _load = d._bytes, d._hash, runtime._load
_safe, _read, _write = runtime._safe, runtime._read, runtime._write
_inventory, _identity = runtime._inventory, runtime._identity
Stream = runtime.Stream
_stream = runtime._stream
Exchange = runtime.Exchange


def _save(path: Path, value: object) -> None:
    _write(path, _bytes(value))


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
    for name, pin in ACCEPTED.items():
        if _hash(source[name]) != pin:
            raise ValueError(f"Accepted work-review source changed: {name}")
    for name in d.RUNTIME:
        if source[name] != source[runtime.OLD + "source/" + name]:
            raise ValueError("Original decoder/runtime differs from committed historical freeze")
    return commit, source


def _settings() -> dict[str, Any]:
    return dict(
        contract="work-review-streaming-1",
        cases=list(CASES),
        requests=7,
        repetitions=1,
        model=http.MODEL,
        think=False,
        stream=True,
        temperature=0,
        num_ctx=32768,
        seconds=LIMIT,
        per_generation_seconds=GENERATION_LIMIT,
        per_metadata_seconds=METADATA_LIMIT,
        retries=0,
        server_compute_cancellation_guaranteed=False,
    )


def _files(
    source: dict[str, bytes], identity: dict[str, Any], generation: str
) -> tuple[dict[str, bytes], tuple[review.Prepared, ...]]:
    if type(generation) is not str or not re.fullmatch(
        "work-review-probe-[0-9a-f]{32}", generation
    ):
        raise ValueError("Invalid host generation identity")
    authored = examples.load_examples()
    mapping = _load(source[PROPOSAL + "examples.json"])
    provenance = {
        d.INPUT: examples.INPUT_HASH,
        PROPOSAL + "examples.json": examples.MAPPING_HASH,
        PROPOSAL + "authored-longer-input.json": examples.LONGER_HASH,
        PROPOSAL + "sources.md": examples.ANNEX_HASH,
        **{PROPOSAL + row["preview"]: row["preview_sha256"] for row in mapping["examples"]},
    }
    if any(_hash(source[name]) != pin for name, pin in provenance.items()):
        raise ValueError("Original authored input/mapping/annex/preview provenance drift")
    # The loader validates original mappings; only complete input snapshots feed prepare().
    snapshots = {case: authored[case].snapshot for case in CASES}
    packets = tuple(review.prepare(snapshots[case], f"{generation}/{case}") for case in CASES)
    files = {"source/" + name: data for name, data in source.items()}
    files.update(
        {
            "identity.json": _bytes(identity),
            "settings.json": _bytes(_settings()),
            "show-request.json": http.SHOW,
            "snapshots.json": d._snapshot_bytes({case: snapshots[case] for case in CASES}),
            "import-baselines.json": _bytes(LOADED),
            "authored-input-provenance.json": _bytes(
                dict(
                    original_files=provenance,
                    cases={
                        row["case"]: dict(
                            snapshot_id=row["snapshot_id"],
                            input_provenance=row["input_provenance"],
                        )
                        for row in mapping["examples"]
                    },
                    familiar_cases=6,
                    chief_authored_longer_not_held_out=True,
                    authored_selections_sent=False,
                )
            ),
        }
    )
    bindings: dict[str, Any] = {}
    for slot, packet, pin in zip(SLOTS, packets, http.CHAT_PINS, strict=True):
        body = packet.payload()
        body.update(
            model=http.MODEL,
            stream=True,
            think=False,
            options={"temperature": 0, "num_ctx": 32768},
        )
        wire = _bytes(body)
        if _hash(wire) != pin:
            raise ValueError("Actual wire bytes differ from approved seven-case pins")
        snapshot = d._snapshot_bytes({slot[3:]: packet.snapshot})
        files[f"requests/{slot}.json"] = wire
        files[f"snapshots/{slot}.json"] = snapshot
        bindings[slot] = dict(
            case=slot[3:],
            generation_id=packet.generation_id,
            snapshot_id=packet.snapshot.snapshot_id,
            snapshot_sha256=_hash(snapshot),
            request_sha256=_hash(wire),
            prepared_binding=packet.binding,
            model_neutral_payload_sha256=_hash(packet.payload_json.encode()),
        )
    files["bindings.json"] = _bytes(bindings)
    return files, packets


def _manifest(
    commit: str, generation: str, identity: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    return dict(
        format="work-review-streaming-1",
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
    generation = f"work-review-probe-{uuid.uuid4().hex}"
    files, _ = _files(source, identity, generation)
    manifest = _manifest(commit, generation, identity, files)
    for name, data in files.items():
        _write(output / name, data)
    _save(output / "manifest.json", manifest)
    return _hash(_bytes(manifest))


def _validate(output: Path, pin: str) -> tuple[dict[str, Any], tuple[review.Prepared, ...]]:
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


def _observe(slot: Path, artifact_errors: list[str]) -> runtime.Stream:
    stream = _stream(slot / "response")
    interrupt: BaseException | None = None
    for name, value in (
        ("progress.json", stream.progress()),
        ("observed.json", dict(content=stream.content, thinking=stream.thinking)),
    ):
        try:
            _save(slot / name, value)
        except BaseException as error:
            artifact_errors.append(f"{name}: {type(error).__name__}: {error}")
            if not isinstance(error, Exception):
                interrupt = interrupt or error
    if interrupt is not None:
        raise interrupt
    if artifact_errors:
        raise OSError("Progress artifacts incomplete; see artifact_errors")
    return stream


def _remaining(deadline: float, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError("Shared 1500-second deadline reached")
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


Assessment = Callable[[str, review.Result, float], dict[str, Any]]


def _assessment_ready(assess: Assessment) -> None:
    if not callable(assess):
        raise TypeError("Explicit Chief-owned assessment callback required")
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Bounded host assessment requires the main thread")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError("Host assessment cannot replace an existing real-time timer")


def _assess(
    slot: str,
    result: review.Result,
    deadline: float,
    assess: Assessment,
    clock: Callable[[], float],
) -> dict[str, Any]:
    _assessment_ready(assess)
    remaining = _remaining(deadline, clock)
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum: int, _frame: object) -> None:
        raise TimeoutError("Shared 1500-second deadline during host assessment")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, remaining)
        verdict = assess(slot, result, deadline)
        _remaining(deadline, clock)
        if (
            type(verdict) is not dict
            or set(verdict) != {"critical", "assessment"}
            or type(verdict["critical"]) is not bool
            or type(verdict["assessment"]) is not str
            or not verdict["assessment"].strip()
        ):
            raise ValueError(
                "Host assessment needs exactly critical:bool and nonblank assessment:str"
            )
        return dict(verdict)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def run(output: Path, approval: str, pin: str, assess: Assessment) -> dict[str, Any]:
    """Return sealed accounting and a separate post-seal observation; consume once."""
    return _run(output, approval, pin, http.exchange, time.monotonic, assess)


def _run(
    output: Path,
    approval: str,
    pin: str,
    exchange: Exchange,
    clock: Callable[[], float],
    assess: Assessment,
) -> dict[str, Any]:
    started = clock()
    deadline = started + LIMIT
    output = _safe(output)
    results = output / "results"
    results.mkdir(exist_ok=False)
    rows: list[dict[str, Any]] = [
        dict(
            slot=slot,
            case=case,
            think=False,
            state="unsent",
            possibly_sent=False,
            request_sha256=wire_pin,
            generation_id=None,
            snapshot_id=None,
            snapshot_sha256=None,
        )
        for slot, case, wire_pin in zip(SLOTS, CASES, http.CHAT_PINS, strict=True)
    ]
    stop = "capture complete; host assessments recorded; no automated model-quality PASS"
    complete = False
    active: dict[str, Any] | None = None
    slot_started = started
    artifact_errors: list[str] = []
    interrupt: BaseException | None = None

    def accounting(boundary: str, *, authoritative: bool) -> dict[str, Any]:
        ended = clock()
        reason = stop
        if complete and ended >= deadline:
            reason = "Shared 1500-second deadline during final saving/cleanup"
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
        _assessment_ready(assess)
        _remaining(deadline, clock)
        _, packets = _validate(output, pin)
        bindings = _load(_read(output, "bindings.json"))
        for row in rows:
            row.update(bindings[row["slot"]])
            row["manifest_sha256"] = pin
        _save(results / "slots.json", rows)
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
                    snapshot_sha256=row["snapshot_sha256"],
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
            except BaseException as exchange_error:
                if (slot / "response").exists():
                    try:
                        _observe(slot, artifact_errors)
                    except BaseException as saving_error:
                        artifact_errors.append(f"Progress save: {saving_error}")
                        if isinstance(exchange_error, Exception) and not isinstance(
                            saving_error, Exception
                        ):
                            raise
                raise
            else:
                stream = _observe(slot, artifact_errors)
            _remaining(deadline, clock)
            _gate(output, pin, slot / "after", deadline, exchange, clock)
            if _read(slot, "request.json") != request:
                raise ValueError("Actual request changed during generation")
            if artifact_errors:
                raise OSError("Progress artifacts incomplete; see artifact_errors")
            if not stream.progress()["valid"]:
                raise ValueError(f"Invalid stream: {stream.progress()['error']}")
            result = review.decode(packet, stream.content)
            markdown = review.render_result(result).encode()
            _save(slot / "result.json", asdict(result))
            _write(slot / "work-review.md", markdown)
            row.update(render_saved=True, result_binding=result.binding)
            # Every saved valid render is assessed, including the seventh/empty selection.
            verdict = _assess(row["slot"], result, deadline, assess, clock)
            _save(slot / "meaning-review.json", verdict)
            _remaining(deadline, clock)
            row["meaning_review"] = verdict
            if verdict["critical"]:
                raise ValueError("Critical host meaning assessment; later slots remain unsent")
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
            for key, path in (
                ("exchange", slot / "response" / "exchange.json"),
                ("progress", slot / "progress.json"),
            ):
                try:
                    if path.exists():
                        row[key] = _load(_read(path.parent, path.name))
                except BaseException as error:
                    artifact_errors.append(f"{row['slot']}/{key}: {type(error).__name__}: {error}")
                    if not isinstance(error, Exception):
                        interrupt = interrupt or error
            try:
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
