"""Schema-grounded passage-selection freeze and single-use, host-assessed capture."""

# pyright: reportPrivateUsage=false

import json
import re
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import _work_review_schema_http as http
from . import action_diagnostic as d
from . import runtime_probe as runtime
from . import work_review as review
from . import work_review_probe as previous
from . import work_review_temperature as capped
from . import work_review_thinking as thinking

ROOT = Path(__file__).resolve().parents[2]
HERE = runtime.HERE
CASES = thinking.CASES
SLOTS = tuple(f"{index:02}-{case}" for index, case in enumerate(CASES, 1))
PROMPT_PREFIX = "\nOutput JSON Schema (also supplied in format):\n"
CRITERIA = "evaluation/m10/reviewable-draft/work-review-schema-1-analysis/criteria.json"
NUM_PREDICT = 4096
DECLARATION = HERE + "WORK_REVIEW_SCHEMA.md"
RUNTIME = (
    *dict.fromkeys((*capped.RUNTIME, *thinking.RUNTIME)),
    HERE + "work_review_schema.py",
    HERE + "_work_review_schema_http.py",
)
NAMES = tuple(
    dict.fromkeys(
        (
            *capped.NAMES,
            *thinking.NAMES,
            *RUNTIME,
            DECLARATION,
            HERE + "test_work_review_schema.py",
            HERE + "test_work_review_schema_http.py",
            CRITERIA,
        )
    )
)
# Preserve transitive import baselines, including helpers imported before this module.
if any(capped.LOADED[n] != h for n, h in thinking.LOADED.items() if n in capped.LOADED):
    raise ValueError("Inherited import baselines disagree; use a fresh interpreter")
LOADED = {
    **capped.LOADED,
    **thinking.LOADED,
    HERE + "work_review_schema.py": d._hash(Path(__file__).read_bytes()),
    HERE + "_work_review_schema_http.py": http.LOADED_SOURCE_SHA256,
}
ACCEPTED = {
    **capped.ACCEPTED,
    **thinking.ACCEPTED,
    HERE + "work_review_temperature.py": (
        "f8d2f2d165563cfe9828817dfebbb6bbd3c3410b394f3c4d532f710c0148208e"
    ),
    HERE + "_work_review_temperature_http.py": (
        "8d11def599e5ffb214bcb44746fbf69dc9bf7b9695ab7d3312341fb5a6f23d12"
    ),
    HERE + "WORK_REVIEW_TEMPERATURE.md": (
        "b232f79f42a1c41a5d4789d1847ee507fc3a8d60be9ea82c45900839a81894e7"
    ),
    HERE + "work_review_thinking.py": (
        "89d65d8e73bfb9d8991c7e15f123d46d0c652c9ba085268194639781e4c1dd7e"
    ),
    HERE + "_work_review_thinking_http.py": (
        "273c322c5a53ebe1417398f4407837c129b5e050275a494fbec5158a3a730134"
    ),
    HERE + "WORK_REVIEW_THINKING.md": (
        "c7fa9c85c9dbcbad84bfebd011f13fd9ff14f65c5824b4d647e0ee3e54e19ce4"
    ),
    CRITERIA: "b70b169239a9673526795a3b480913d2dbe53b4e63aed07536d457b9eebeca5e",
}
LIMIT, GENERATION_LIMIT, METADATA_LIMIT = 540, 180, 10
IDENTITY = runtime.IDENTITY
_bytes, _hash, _load = d._bytes, d._hash, runtime._load
_safe, _read, _write = runtime._safe, runtime._read, runtime._write
_inventory, _identity = runtime._inventory, runtime._identity
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
        contract="work-review-schema-1",
        cases=list(CASES),
        requests=3,
        repetitions=1,
        model=http.MODEL,
        think=True,
        stream=True,
        temperature=1,
        num_ctx=32768,
        num_predict=NUM_PREDICT,
        prompt_append_prefix=PROMPT_PREFIX,
        length_terminal_stops_as_incomplete=True,
        seconds=LIMIT,
        per_generation_seconds=GENERATION_LIMIT,
        per_metadata_seconds=METADATA_LIMIT,
        retries=0,
        server_compute_cancellation_guaranteed=False,
    )


_snapshots = thinking._snapshots
Stream = capped.Stream
_stream = capped._stream


def _files(
    source: dict[str, bytes], identity: dict[str, Any], generation: str
) -> tuple[dict[str, bytes], tuple[review.Prepared, ...]]:
    if type(generation) is not str or not re.fullmatch(
        "work-review-schema-[0-9a-f]{32}", generation
    ):
        raise ValueError("Invalid host generation identity")
    snapshots = _snapshots(source[d.INPUT])
    packets = tuple(
        review.prepare(snapshots[case], f"{generation}/{slot}")
        for case, slot in zip(CASES, SLOTS, strict=True)
    )
    files = {"source/" + name: data for name, data in source.items()}
    files.update(
        {
            "identity.json": _bytes(identity),
            "settings.json": _bytes(_settings()),
            "show-request.json": http.SHOW,
            "snapshots.json": d._snapshot_bytes(snapshots),
            "import-baselines.json": _bytes(LOADED),
            "input-provenance.json": _bytes(
                dict(
                    original_forty_sha256=d.INPUT_HASH,
                    familiar_cases=3,
                    schema_appended_to_system_only=True,
                    repetitions=1,
                    held_out=False,
                    authored_selections_sent=False,
                    historical_regrading=False,
                    causal_improvement_claim=False,
                )
            ),
        }
    )
    bindings: dict[str, Any] = {}
    for case, slot, packet, pin in zip(CASES, SLOTS, packets, http.CHAT_PINS, strict=True):
        if packet.snapshot != snapshots[case] or packet.generation_id != f"{generation}/{slot}":
            raise ValueError("Prepared packet differs from complete snapshot/generation")
        packet.validate()
        body = packet.payload()
        body["messages"][0]["content"] += (
            PROMPT_PREFIX
            + json.dumps(body["format"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        body.update(
            model=http.MODEL,
            stream=True,
            think=True,
            options={"temperature": 1, "num_ctx": 32768, "num_predict": NUM_PREDICT},
        )
        wire = _bytes(body)
        if _hash(wire) != pin:
            raise ValueError("Actual wire bytes differ from approved three-case schema pins")
        snapshot = d._snapshot_bytes({case: packet.snapshot})
        files[f"requests/{slot}.json"] = wire
        files[f"snapshots/{slot}.json"] = snapshot
        bindings[slot] = dict(
            case=case,
            temperature=1,
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
        format="work-review-schema-1",
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
    generation = f"work-review-schema-{uuid.uuid4().hex}"
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


def _observe(slot: Path, artifact_errors: list[str]) -> Stream:
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
        raise TimeoutError("Shared 540-second deadline reached")
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


Assessment = previous.Assessment
_assessment_ready = previous._assessment_ready
_assess = previous._assess


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
            temperature=1,
            think=True,
            state="unsent",
            transport_complete=False,
            terminal_outcome=None,
            render_saved=False,
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
    exhausted = False
    active: dict[str, Any] | None = None
    slot_started = started
    artifact_errors: list[str] = []
    interrupt: BaseException | None = None

    def accounting(boundary: str, *, authoritative: bool) -> dict[str, Any]:
        ended = clock()
        reason = stop
        if exhausted and ended >= deadline:
            reason = "Shared 540-second deadline during final saving/cleanup"
        elif exhausted and artifact_errors:
            reason = "Capture finalization failed; see artifact_errors"
        return dict(
            authoritative=authoritative,
            accounting_boundary=boundary,
            capture_complete=(
                exhausted
                and all(r["transport_complete"] for r in rows)
                and not artifact_errors
                and ended < deadline
            ),
            answer_complete=(
                complete
                and all(r["render_saved"] for r in rows)
                and not artifact_errors
                and ended < deadline
            ),
            semantic_complete=(
                complete
                and all(r.get("meaning_review", {}).get("critical") is False for r in rows)
                and not artifact_errors
                and ended < deadline
            ),
            automated_quality_pass=False,
            possibly_sent=sum(r["possibly_sent"] for r in rows),
            slots=[dict(r) for r in rows],
            stop_completed=[r["slot"] for r in rows if r["terminal_outcome"] == "stop"],
            length_censored=[r["slot"] for r in rows if r["terminal_outcome"] == "censored_length"],
            counts={
                "stop_completed": sum(r["terminal_outcome"] == "stop" for r in rows),
                "length_censored": sum(r["terminal_outcome"] == "censored_length" for r in rows),
                "failed": sum(r["state"] == "failed" for r in rows),
                "unsent": sum(not r["possibly_sent"] for r in rows),
                "transport_complete": sum(r["transport_complete"] for r in rows),
                "answers": sum(r["render_saved"] for r in rows),
                "meaning_reviews": sum("meaning_review" in r for r in rows),
            },
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
            progress = stream.progress()
            row.update(terminal_outcome=progress["terminal_outcome"])
            if stream.done_reason == "length":
                row.update(
                    state="censored_length",
                    length_counter_status=progress["length_counter_status"],
                    length_cap_match=progress["length_cap_match"],
                )
                row.update(transport_complete=True, elapsed=clock() - slot_started)
                _validate(output, pin)
                _remaining(deadline, clock)
                stop = "Length terminal censored/incomplete; later slots remain unsent"
                active = None
                break
            if "eval_count" in stream.returned and stream.returned["eval_count"] > NUM_PREDICT:
                raise ValueError("Stop terminal eval_count exceeds num_predict=4096")
            row["transport_complete"] = True
            result = review.decode(packet, stream.content)
            markdown = review.render_result(result).encode()
            _save(slot / "result.json", asdict(result))
            _write(slot / "work-review.md", markdown)
            row.update(render_saved=True, result_binding=result.binding)
            # Every saved valid render is assessed, including the final/empty selection.
            verdict = _assess(row["slot"], result, deadline, assess, clock)
            _save(slot / "meaning-review.json", verdict)
            _remaining(deadline, clock)
            row["meaning_review"] = verdict
            if verdict["critical"]:
                raise ValueError("Critical host meaning assessment; later slots remain unsent")
            _validate(output, pin)
            _remaining(deadline, clock)
            row.update(state="stop_completed", elapsed=clock() - slot_started)
            active = None
        exhausted = all(r["state"] == "stop_completed" for r in rows)
        complete = exhausted
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
                        if key == "progress" and row[key]["valid"]:
                            row["terminal_outcome"] = row[key]["terminal_outcome"]
                            if row["terminal_outcome"] == "censored_length":
                                row.update(
                                    length_counter_status=row[key]["length_counter_status"],
                                    length_cap_match=row[key]["length_cap_match"],
                                )
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
        seal_started = clock()
        write_started: float | None = None
        write_ended: float | None = None
        final = accounting("unsealed: inventory unavailable", authoritative=False)
        try:
            if inventory is not None:
                if (results / "final.json").exists():
                    inventory["final.json"] = _hash(_read(results, "final.json"))
                final = accounting(
                    "after final.json save and inventory hashing; before manifest.json write",
                    authoritative=True,
                )
                write_started = clock()
                try:
                    _save(
                        results / "manifest.json",
                        dict(files=inventory, accounting=final),
                    )
                finally:
                    write_ended = clock()
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
            seal_attempt_seconds=ended - seal_started,
            manifest_write_seconds=(
                write_ended - write_started
                if write_started is not None and write_ended is not None
                else None
            ),
            completion_eligible=(
                sealed and final["capture_complete"] and not artifact_errors and ended < deadline
            ),
            elapsed=ended - started,
            overrun_seconds=max(0.0, ended - deadline),
            deadline_reached=ended >= deadline,
        ),
    )
