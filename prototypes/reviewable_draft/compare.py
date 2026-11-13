"""Frozen model-only screen. Only run() performs HTTP; no retries or quality verdicts."""

# pyright: reportPrivateUsage=false

import re
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import action_diagnostic as d
from . import actions

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = "prototypes/reviewable_draft/MODEL_COMPARISON.md"
RUNTIME = (
    *d.RUNTIME,
    "prototypes/reviewable_draft/compare.py",
    "prototypes/reviewable_draft/blind_review.py",
)
BASELINE = "evaluation/m10/reviewable-draft/diagnostic-3"
PINS = {
    "source": "287d85b2229e0c03c6434337a2337bf777e5a136",
    "freeze": "7381d8e7316bfe2e5cdac7277e9cbb789b3bd2e4",
    "manifest": "472027ef8be047233a3a8cf75630c922afe28c96b73911b844619c16b33e8bd3",
    "results": "9a88959f821a186293492003fef40d80a11fd955c4cbc5115877c45ad83be77f",
}
MODELS = (
    ("qwen3.5:9b-q4_K_M", "56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90"),
    ("gemma4:12b-it-q4_K_M", "6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b"),
)
LOADED = {
    **d.LOADED,
    **{name: d._hash((ROOT / name).read_bytes()) for name in RUNTIME if name not in d.LOADED},
}
LIMIT, ARM_LIMIT = 1800, 900
TIMINGS = (
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
    "prompt_eval_count",
    "eval_count",
)
_bytes, _hash, _write, _save = d._bytes, d._hash, d._write, d._save


def _load(data: bytes) -> dict[str, Any]:
    return d.json_helpers._load(data.decode("utf-8"))


def _read(root: Path, name: str) -> bytes:
    root = root.resolve()
    path = root / name
    if (
        Path(name).is_absolute()
        or ".." in Path(name).parts
        or any(p.is_symlink() for p in (path, *path.parents) if p == root or root in p.parents)
    ):
        raise ValueError("Artifacts must be ordinary files inside their directory")
    return path.read_bytes()


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def _source(candidate: str | None = None) -> tuple[str, dict[str, bytes]]:
    head = _git("rev-parse", "HEAD").decode().strip()
    commit = head if candidate is None else candidate
    if type(commit) is not str or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Expected an exact candidate commit")
    _git("merge-base", "--is-ancestor", commit, head)
    names = (*RUNTIME, DECLARATION, d.DECLARATION, d.INPUT)
    if _git("status", "--porcelain=v1", "--untracked-files=all", "--", *names):
        raise ValueError("Dirty comparison source/input/declaration")
    source = {name: _read(ROOT, name) for name in names}
    for name, data in source.items():
        if data != _git("show", f"{commit}:{name}"):
            raise ValueError(f"Source differs from candidate: {name}")
        if name in LOADED and _hash(data) != LOADED[name]:
            raise ValueError(f"Imported runtime changed: {name}; use a fresh interpreter")
    return commit, source


def _identities(value: object) -> list[dict[str, Any]]:
    rows = d._rows(value)
    if len(rows) != 2:
        raise ValueError("Expected both fixed challenger identities")
    for row, (model, digest) in zip(rows, MODELS, strict=True):
        identity = d.json_helpers._object(row)
        capabilities = [
            "completion",
            "vision",
            *(["audio"] if model.startswith("gemma") else []),
            "tools",
            "thinking",
        ]
        expected = dict(
            model=model,
            version="0.40.9",
            digest=digest,
            capabilities=capabilities,
            thinking={"values": [False, True], "default": True},
        )
        if _bytes(identity) != _bytes(expected):
            raise ValueError("Model/version/digest/capabilities/thinking differs from declaration")
    return rows


def _settings() -> dict[str, Any]:
    return {
        **d._settings(),
        "contract": "model-only-screen-1",
        "model": [m for m, _ in MODELS],
        "requests": 12,
        "seconds": LIMIT,
        "per_arm_requests": 6,
        "per_arm_seconds": ARM_LIMIT,
    }


@dataclass(frozen=True)
class Packet:
    """Actual wire request plus an unchanged, host-bound internal decoding packet."""

    original: actions.Prepared
    model: str
    slot: str
    arm: int
    case: str

    @property
    def request_json(self) -> str:
        body = self.original.body()
        body["model"] = self.model
        return d.json_helpers._json(body)


def _replay(packet: actions.Prepared, raw: bytes) -> actions.Result:
    attempt = actions.generate(packet, lambda _: _load(raw))
    if attempt.error is not None or attempt.result is None:
        raise ValueError(attempt.error)
    return attempt.result


def _baseline(source: dict[str, bytes]) -> dict[str, bytes]:
    """Read each pinned baseline artifact once and verify raw-to-render provenance."""
    root = ROOT / BASELINE
    saved: dict[str, bytes] = {}
    for name, pin in (
        ("manifest.json", PINS["manifest"]),
        ("results/manifest.json", PINS["results"]),
    ):
        saved[name] = _read(root, name)
        if _hash(saved[name]) != pin:
            raise ValueError("Baseline manifest drift")
        prefix = "results/" if name.startswith("results/") else ""
        for file, digest in _load(saved[name])["files"].items():
            data = _read(root, prefix + file)
            if _hash(data) != digest:
                raise ValueError(f"Baseline artifact drift: {prefix + file}")
            saved[prefix + file] = data
    manifest = _load(saved["manifest.json"])
    if manifest["candidate_commit"] != PINS["source"] or saved["manifest.json"] != _git(
        "show", f"{PINS['freeze']}:{BASELINE}/manifest.json"
    ):
        raise ValueError("Baseline source/freeze binding differs")
    for name in d.RUNTIME:
        if source[name] != _git("show", f"{PINS['source']}:{name}"):
            raise ValueError("Baseline runtime differs from its source commit")
    expected, packets = d._files(source, manifest["generation_id"], manifest["identity"])
    if set(expected) != set(manifest["files"]) or any(saved[n] != b for n, b in expected.items()):
        raise ValueError("Baseline source/request/snapshot/settings binding differs")
    final = _load(saved["results/final.json"])
    if (
        not final["capture_complete"]
        or final["possibly_sent"] != 6
        or final["completed"] != list(actions.CASES)
    ):
        raise ValueError("Baseline capture accounting differs")
    for index, (case, packet) in enumerate(zip(actions.CASES, packets, strict=True), 1):
        slot = f"results/{index:02}-{case}/"
        request = packet.request_json.encode()
        attempt = _load(saved[slot + "attempt.json"])
        if (
            saved[slot + "request.json"] != request
            or attempt["generation_id"] != packet.generation_id
            or attempt["request_sha256"] != _hash(request)
        ):
            raise ValueError("Baseline actual request/generation binding differs")
        result = _replay(packet, saved[slot + "response/body.raw"])
        render = (
            "> MODEL-GENERATED diagnostic capture. Quality assessment pending.\n\n"
            + actions.render_result(result)
        )
        if (
            saved[slot + "result.json"] != _bytes(asdict(result))
            or saved[slot + "actions.md"] != render.encode()
        ):
            raise ValueError("Baseline raw/result/render binding differs")
    return saved


def _files(
    source: dict[str, bytes],
    identities: list[dict[str, Any]],
    generation: str,
    baseline: dict[str, bytes],
) -> tuple[dict[str, bytes], tuple[Packet, ...]]:
    if type(generation) is not str or not re.fullmatch("comparison-[0-9a-f]{32}", generation):
        raise ValueError("Expected a host comparison generation")
    snapshots = d._snapshots(source[d.INPUT])
    packets = tuple(
        Packet(original, identity["model"], f"{arm:02}-{index:02}-{case}", arm, case)
        for arm, identity in enumerate(identities, 1)
        for index, (case, original) in enumerate(
            zip(actions.CASES, actions.prepare(snapshots, f"{generation}/{arm}"), strict=True), 1
        )
    )
    for packet in packets:
        baseline_request = _load(baseline[f"requests/{packet.case}.json"])
        baseline_request["model"] = packet.model
        if packet.request_json.encode() != _bytes(baseline_request):
            raise ValueError("Only the request model field may vary")
        if (
            packet.original.snapshot != snapshots[packet.case]
            or packet.original.generation_id != f"{generation}/{packet.arm}/{packet.case}"
        ):
            raise ValueError("Packet snapshot/generation binding differs")
    files = {f"source/{name}": source[name] for name in RUNTIME}
    files.update(
        {
            "MODEL_COMPARISON.md": source[DECLARATION],
            "ACTIONS.md": source[d.DECLARATION],
            "identities.json": _bytes(identities),
            "settings.json": _bytes(_settings()),
            "baseline-pins.json": _bytes(PINS),
            "pairs.json": source[d.INPUT],
            "snapshots.json": d._snapshot_bytes(snapshots),
            **{f"requests/{p.slot}.json": p.request_json.encode() for p in packets},
        }
    )
    return files, packets


def freeze(output: Path, identities: list[dict[str, Any]]) -> str:
    """Exclusively freeze committed inputs/runtime and 12 actual requests; return SHA256."""
    output.mkdir(parents=True, exist_ok=False)
    identities = _identities(identities)
    commit, source = _source()
    baseline = _baseline(source)
    generation = f"comparison-{uuid.uuid4().hex}"
    files, _ = _files(source, identities, generation, baseline)
    manifest = dict(
        format="model-only-screen-1",
        candidate_commit=commit,
        generation_id=generation,
        identities=identities,
        settings=_settings(),
        baseline=PINS,
        files={name: _hash(data) for name, data in files.items()},
    )
    for name, data in files.items():
        _write(output / name, data)
    _save(output / "manifest.json", manifest)
    return _hash(_bytes(manifest))


def _validate(
    output: Path, pin: str
) -> tuple[dict[str, Any], tuple[Packet, ...], dict[str, bytes]]:
    """Return (manifest, ordered actual Packets, verified baseline bytes by relative path)."""
    data = _read(output, "manifest.json")
    if type(pin) is not str or not re.fullmatch("[0-9a-f]{64}", pin) or _hash(data) != pin:
        raise ValueError("Expected manifest SHA256 differs")
    manifest = _load(data)
    if (
        set(manifest)
        != {
            "format",
            "candidate_commit",
            "generation_id",
            "identities",
            "settings",
            "baseline",
            "files",
        }
        or manifest["format"] != "model-only-screen-1"
        or _bytes(manifest["settings"]) != _bytes(_settings())
        or manifest["baseline"] != PINS
    ):
        raise ValueError("Frozen declaration/settings/baseline differs")
    identities = _identities(manifest["identities"])
    _, source = _source(manifest["candidate_commit"])
    baseline = _baseline(source)
    expected, packets = _files(source, identities, manifest["generation_id"], baseline)
    if set(expected) != set(manifest["files"]):
        raise ValueError("Frozen artifact set differs")
    for name, data in expected.items():
        if _read(output, name) != data or _hash(data) != manifest["files"][name]:
            raise ValueError(f"Frozen source/input/request differs: {name}")
    return manifest, packets, baseline


class _BatchStop(ValueError):
    pass


class _ArmStop(ValueError):
    pass


def _gates(
    frozen: Path,
    pin: str,
    slot: Path,
    phase: str,
    identity: dict[str, Any],
    deadline: float,
    overall: float,
) -> None:
    try:
        d._remaining(overall)
        if time.monotonic() >= deadline:
            raise _ArmStop("Arm elapsed deadline reached")
        _validate(frozen, pin)
        d._remaining(overall)
        if time.monotonic() >= deadline:
            raise _ArmStop("Arm elapsed deadline reached")
        d._metadata(slot / phase, identity, deadline)
        _validate(frozen, pin)
        d._remaining(overall)
    except _ArmStop:
        raise
    except Exception as error:
        raise _BatchStop(f"Gate: {type(error).__name__}: {error}") from error


def _capture(
    frozen: Path,
    pin: str,
    packet: Packet,
    identity: dict[str, Any],
    deadline: float,
    overall: float,
) -> None:
    slot = frozen / "results" / packet.slot
    request = packet.request_json.encode()
    _write(slot / "request.json", request)
    _gates(frozen, pin, slot, "before", identity, deadline, overall)
    if _read(slot, "request.json") != request:
        raise _BatchStop("Actual request changed before POST")
    d._remaining(overall)
    if time.monotonic() >= deadline:
        raise _ArmStop("Arm elapsed deadline reached")
    _save(
        slot / "attempt.json",
        dict(
            possibly_sent=True,
            generation_id=packet.original.generation_id,
            snapshot_id=packet.original.snapshot.snapshot_id,
            request_sha256=_hash(request),
            timeout=d._remaining(deadline),
        ),
    )
    error: Exception | None = None
    result: actions.Result | None = None
    response: dict[str, Any] = {}
    try:
        raw = d._exchange(
            "POST", "/api/chat", slot / "request.json", slot / "response", deadline, _hash(request)
        )
        response = _load(raw)
        if response.get("model", packet.model) != packet.model:
            raise _BatchStop("Response model identity drift")
        result = _replay(packet.original, raw)
    except Exception as exc:
        error = exc
    if response:
        _save(slot / "timings.json", {key: response[key] for key in TIMINGS if key in response})
    if error is None and result is not None:
        _save(slot / "result.json", asdict(result))
        _write(slot / "actions.md", actions.render_result(result).encode())
        if result.issues:
            error = _ArmStop("Literal selection failure; partial actions retained")
    if isinstance(error, _BatchStop):
        raise error
    _gates(frozen, pin, slot, "after", identity, deadline, overall)
    if error is not None:
        raise _ArmStop(f"{type(error).__name__}: {error}") from error


def _inventory(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): _hash(_read(root, p.relative_to(root).as_posix()))
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _optional(data: bytes | None, name: str, errors: list[str]) -> dict[str, Any]:
    if data is None:
        return {}
    try:
        return _load(data)
    except (ValueError, UnicodeError) as exc:
        # A failed exclusive write can leave a partial JSON artifact. Still seal the audit.
        errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return {}


def _account(results: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm in (1, 2):
        for index, case in enumerate(actions.CASES, 1):
            name = f"{arm:02}-{index:02}-{case}"
            slot = results / name
            errors: list[str] = []

            def saved(
                file: str, directory: Path = slot, problems: list[str] = errors
            ) -> dict[str, Any]:
                return _optional(
                    _read(directory, file) if (directory / file).exists() else None, file, problems
                )

            outcome, result, timings = (
                saved("outcome.json"),
                saved("result.json"),
                saved("timings.json"),
            )
            attempted = (slot / "attempt.json").exists()
            rows.append(
                dict(
                    slot=name,
                    arm=arm,
                    case=case,
                    possibly_sent=attempted,
                    captured=(slot / "response/body.raw").exists(),
                    result_saved=bool(result),
                    capture_complete=outcome.get("capture_complete", False),
                    issues=result.get("issues", []),
                    error=outcome.get("error"),
                    elapsed=outcome.get("elapsed", 0),
                    timings=timings,
                    artifact_errors=errors,
                )
            )
    return rows


def run(output: Path, approval: str, pin: str) -> dict[str, Any]:
    """Claim results once; return final accounting. Interrupts persist audit then re-raise.

    results/manifest.json is an exact capture inventory. Keep launch, report and review
    artifacts outside results/ so subsequent integrity checks preserve that inventory.
    """
    started = time.monotonic()
    overall = started + LIMIT
    results = output / "results"
    results.mkdir(exist_ok=False)
    arms: list[dict[str, Any]] = []
    reason = "Capture finished; see arm outcomes; semantic assessment pending"
    try:
        _save(
            results / "running.json",
            dict(
                state="running",
                approval=approval,
                expected_manifest_sha256=pin,
                settings=_settings(),
                approval_is_authentication=False,
            ),
        )
        if type(approval) is not str or not approval.strip():
            raise _BatchStop("Approval audit context is required")
        manifest, packets, _ = _validate(output, pin)
        d._remaining(overall)
        _save(
            results / "validated.json",
            dict(
                candidate_commit=manifest["candidate_commit"],
                generation_id=manifest["generation_id"],
                identities=manifest["identities"],
            ),
        )
        for arm, identity in enumerate(manifest["identities"], 1):
            arm_started = started if arm == 1 else time.monotonic()
            deadline = min(overall, arm_started + ARM_LIMIT)
            arm_reason = "Six captures completed; semantic assessment pending"
            try:
                for packet in (p for p in packets if p.arm == arm):
                    slot_started = time.monotonic()
                    slot = results / packet.slot
                    slot.mkdir(exist_ok=False)
                    error: BaseException | None = None
                    try:
                        _capture(output, pin, packet, identity, deadline, overall)
                        d._remaining(overall)
                        if time.monotonic() >= deadline:
                            raise _ArmStop("Arm elapsed deadline reached")
                    except BaseException as exc:
                        error = exc
                        raise
                    finally:
                        _save(
                            slot / "outcome.json",
                            dict(
                                capture_complete=error is None,
                                error=None if error is None else f"{type(error).__name__}: {error}",
                                elapsed=time.monotonic() - slot_started,
                            ),
                        )
            except BaseException as exc:
                arm_reason = f"{type(exc).__name__}: {exc}"
                if not isinstance(exc, _ArmStop):
                    raise
                d._remaining(overall)
            finally:
                elapsed = time.monotonic() - arm_started
                arms.append(
                    dict(
                        arm=arm,
                        elapsed=elapsed,
                        overrun_seconds=max(0, elapsed - ARM_LIMIT),
                        stopping_reason=arm_reason,
                    )
                )
    except BaseException as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if not isinstance(exc, Exception):
            raise
    finally:
        rows = _account(results)
        integrity_error: str | None = None
        try:
            _validate(output, pin)
        except Exception as exc:
            integrity_error = f"{type(exc).__name__}: {exc}"
        inventory = _inventory(results)
        elapsed = time.monotonic() - started
        final = dict(
            capture_complete=all(r["capture_complete"] for r in rows)
            and elapsed <= LIMIT
            and integrity_error is None,
            integrity_error=integrity_error,
            expected_manifest_sha256=pin,
            slots=rows,
            arms=arms,
            possibly_sent=sum(r["possibly_sent"] for r in rows),
            completed=[r["slot"] for r in rows if r["capture_complete"]],
            failed=[r["slot"] for r in rows if r["possibly_sent"] and not r["capture_complete"]],
            captured=[r["slot"] for r in rows if r["captured"]],
            unsent=[r["slot"] for r in rows if not r["possibly_sent"]],
            incomplete_cases=[r["slot"] for r in rows if r["issues"]],
            elapsed=elapsed,
            overrun_seconds=max(0, elapsed - LIMIT),
            stopping_reason=reason,
            quality_assessment="pending independent masked assessment",
            server_compute_cancellation_guaranteed=False,
        )
        final_bytes = _bytes(final)
        _write(results / "final.json", final_bytes)
        _save(
            results / "manifest.json",
            dict(
                expected_manifest_sha256=pin, files={**inventory, "final.json": _hash(final_bytes)}
            ),
        )
    return final
