"""Authored responses and fake clients only. These tests make no quality claims."""

# pyright: reportPrivateUsage=false

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from . import compare as c
from .test_action_diagnostic import authored, response
from .test_diagnostic import FakeHTTP, git, read

REAL_ROOT = c.ROOT
BASELINE_SOURCE = {
    name: git(REAL_ROOT, "show", f"{c.PINS['source']}:{name}") for name in c.d.RUNTIME
}


def identities() -> list[dict[str, Any]]:
    return [
        dict(
            model=model,
            version="0.40.9",
            digest=digest,
            capabilities=[
                "completion",
                "vision",
                *(["audio"] if index else []),
                "tools",
                "thinking",
            ],
            thinking={"values": [False, True], "default": True},
        )
        for index, (model, digest) in enumerate(c.MODELS)
    ]


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "source"
    for name in (*c.RUNTIME, c.DECLARATION, c.d.DECLARATION, c.d.INPUT):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REAL_ROOT / name).read_bytes())
    shutil.copytree(REAL_ROOT / c.BASELINE, root / c.BASELINE)
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
        "Synthetic source and pinned cached evidence",
    )
    original_git = c._git

    def local_git(*args: str) -> bytes:
        # The synthetic repository has its own history, but reuses the exact cached baseline.
        if args == ("show", f"{c.PINS['freeze']}:{c.BASELINE}/manifest.json"):
            return (REAL_ROOT / c.BASELINE / "manifest.json").read_bytes()
        if len(args) == 2 and args[0] == "show" and args[1].startswith(c.PINS["source"] + ":"):
            return BASELINE_SOURCE[args[1].split(":", 1)[1]]
        return original_git(*args)

    monkeypatch.setattr(c, "ROOT", root)
    monkeypatch.setattr(c, "_git", local_git)
    return root


@pytest.fixture
def frozen(source: Path, tmp_path: Path) -> tuple[Path, str]:
    output = tmp_path / "freeze"
    return output, c.freeze(output, identities())


class HTTP(FakeHTTP):
    def __init__(self) -> None:
        super().__init__()
        self.identities = identities()
        self.fields = authored()
        self.responses: dict[str, bytes] = {}
        self.before_spawn: Callable[[str, str, Path], None] = lambda _method, _endpoint, _path: None

    def spawn(self, command: list[str], **kwargs: Any) -> Any:
        method, endpoint, _, directory, _, _ = command[-6:]
        output = Path(directory)
        slot = output.parent if method == "POST" else output.parents[1]
        arm = int(slot.name[:2])
        case = slot.name[6:]
        self.identity = dict(self.identities[arm - 1])
        default = c._load(response(self.fields[case]))
        default.update(load_duration=10, eval_duration=30)
        self.body = self.responses.get(slot.name, c._bytes(default))
        self.before_spawn(method, endpoint, output)
        return super().spawn(command, **kwargs)


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> HTTP:
    fake = HTTP()
    monkeypatch.setattr(c.d, "_http_process", fake.spawn)
    return fake


def test_freeze_pins_transitive_source_old_declaration_and_actual_model_only_packets(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    output, pin = frozen
    manifest, packets, baseline = c._validate(output, pin)
    assert len(packets) == 12 and not http.calls
    assert (output / "ACTIONS.md").read_bytes() == (source / c.d.DECLARATION).read_bytes()
    assert {f"source/{n}" for n in c.RUNTIME} <= set(manifest["files"])
    assert "source/prototypes/reviewable_draft/action_diagnostic.py" in manifest["files"]
    assert "source/prototypes/reviewable_draft/blind_review.py" in manifest["files"]
    assert len(json.loads((output / "pairs.json").read_bytes())) == 40
    assert manifest["baseline"] == c.PINS
    for packet in packets:
        body = c._load((output / f"requests/{packet.slot}.json").read_bytes())
        old = c._load(baseline[f"requests/{packet.case}.json"])
        assert body.pop("model") == identities()[packet.arm - 1]["model"]
        old.pop("model")
        assert body == old
        assert (
            packet.original.generation_id
            == f"{manifest['generation_id']}/{packet.arm}/{packet.case}"
        )
        assert (
            packet.original.snapshot.handwritten_text
            == read(output / "snapshots.json")[packet.case]["handwritten_text"]
        )
    assert not (output / "results").exists()


@pytest.mark.parametrize("field", ["model", "version", "digest", "capabilities", "thinking"])
def test_identity_declarations_are_exact_offline(
    source: Path, tmp_path: Path, http: HTTP, field: str
) -> None:
    values = identities()
    values[0][field] = "changed"
    with pytest.raises(ValueError):
        c.freeze(tmp_path / "invalid", values)
    assert not http.calls


@pytest.mark.parametrize(
    "change", ["source", "old_declaration", "request", "baseline", "identity", "pin"]
)
def test_drift_rejects_before_http_and_consumes_single_use(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
    change: str,
) -> None:
    output, pin = frozen
    paths = {
        "source": source / "prototypes/reviewable_draft/blind_review.py",
        "old_declaration": source / c.d.DECLARATION,
        "request": output / "requests/01-01-unit_equivalence.json",
        "baseline": source / c.BASELINE / "results/01-unit_equivalence/response/body.raw",
        "identity": output / "identities.json",
    }
    if change == "pin":
        pin = "f" * 64
    else:
        paths[change].write_bytes(b"Synthetic user edit")
    final = c.run(output, "Fake-only approval", pin)
    assert final["possibly_sent"] == 0 and len(final["unsent"]) == 12 and not http.calls
    with pytest.raises(FileExistsError):
        c.run(output, "No resumption", pin)
    if change != "pin":
        assert paths[change].read_bytes() == b"Synthetic user edit"


def test_twelve_serial_actual_requests_have_bound_raw_results_and_audited_accounting(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    output, pin = frozen
    final = c.run(output, "Fake-only approval", pin)
    assert final["capture_complete"] and final["possibly_sent"] == len(http.posts) == 12
    assert not final["failed"] and not final["unsent"] and not final["incomplete_cases"]
    _, packets, _ = c._validate(output, pin)
    for packet, actual in zip(packets, http.posts, strict=True):
        slot = output / "results" / packet.slot
        assert actual == packet.request_json.encode() == (slot / "request.json").read_bytes()
        assert c._load(actual)["model"] == packet.model
        result = c._replay(packet.original, (slot / "response/body.raw").read_bytes())
        assert (slot / "result.json").read_bytes() == c._bytes(asdict(result))
        assert (slot / "actions.md").read_text() == c.actions.render_result(result)
        assert read(slot / "attempt.json")["snapshot_id"] == packet.original.snapshot.snapshot_id
        assert read(slot / "timings.json") == {"load_duration": 10, "eval_duration": 30}
        assert final["slots"][packets.index(packet)]["timings"] == {
            "load_duration": 10,
            "eval_duration": 30,
        }
        with pytest.raises(ValueError, match="generation"):
            replace(packet.original, generation_id="another-generation").body()
    sealed = read(output / "results/manifest.json")
    assert sealed["files"] == {
        n: h for n, h in c._inventory(output / "results").items() if n != "manifest.json"
    }
    assert len(http.calls) == 60 and max(t for _, _, _, t in http.calls) <= 600
    with pytest.raises(FileExistsError):
        c.run(output, "No second invocation", pin)
    assert len(http.posts) == 12


@pytest.mark.parametrize("failure", ["structural", "literal", "timeout", "disk"])
def test_failed_arm_preserves_raw_and_partial_results_and_only_continues_after_gates(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    output, pin = frozen
    slot = "01-01-unit_equivalence"
    http.responses[slot] = b'{"partial":'
    if failure in ("literal", "disk"):
        http.responses[slot] = response(
            {
                "actions": [
                    {"source": "T1", "quote": "Support costs 120 dollars.", "context_sources": []},
                    {"source": "T1", "quote": "Made up task.", "context_sources": []},
                ],
                "review_sources": [],
            }
        )
    if failure == "timeout":

        def timeout(method: str, _: str, path: Path) -> None:
            http.timeout = method == "POST" and path.parent.name == slot

        http.before_spawn = timeout
    if failure == "disk":
        write = c._write

        def full(path: Path, data: bytes) -> None:
            if path.name == "actions.md":
                raise OSError("Synthetic disk full")
            write(path, data)

        monkeypatch.setattr(c, "_write", full)
    final = c.run(output, "Fake-only approval", pin)
    assert not final["capture_complete"]
    assert final["possibly_sent"] == (1 if failure == "disk" else 7)
    assert final["failed"] == [slot]
    assert (output / "results" / slot / "response/body.raw").read_bytes() == http.responses[slot]
    if failure in ("literal", "disk"):
        assert final["incomplete_cases"] == [slot]
        assert read(output / "results" / slot / "result.json")["issues"]
    if failure != "disk":
        assert len(final["completed"]) == 6
        second = next(
            i for i, (method, _, _, _) in enumerate(http.calls[3:], 3) if method == "POST"
        )
        assert [m for m, _, _, _ in http.calls[second - 2 : second]] == ["GET", "GET"]
    if failure == "timeout":
        assert http.killed == http.reaped == 1


@pytest.mark.parametrize(
    "drift", ["identity", "metadata", "source", "request", "baseline", "response_model"]
)
def test_drift_during_capture_stops_batch_instead_of_continuing_other_arm(
    source: Path,
    frozen: tuple[Path, str],
    http: HTTP,
    drift: str,
) -> None:
    output, pin = frozen

    def change(method: str, endpoint: str, path: Path) -> None:
        if drift == "identity":
            http.identity["digest"] = "f" * 64
        elif drift == "metadata" and method == "GET":
            raise OSError("Synthetic metadata failure")
        elif drift == "source" and endpoint == "/api/tags":
            p = source / "prototypes/reviewable_draft/actions.py"
            p.write_bytes(p.read_bytes() + b"\n")
        elif drift == "request" and endpoint == "/api/tags":
            (path.parents[1] / "request.json").write_bytes(b"Synthetic edited request")
        elif drift == "baseline" and method == "POST":
            (source / c.BASELINE / "results/final.json").write_bytes(b"Synthetic edited evidence")
        elif drift == "response_model" and method == "POST":
            body = c._load(http.body)
            body["model"] = "different-model"
            http.body = c._bytes(body)

    http.before_spawn = change
    final = c.run(output, "Fake-only approval", pin)
    assert final["possibly_sent"] == (1 if drift in ("baseline", "response_model") else 0)
    assert not final["completed"] or all(s.startswith("01-") for s in final["completed"])
    assert len(final["arms"]) == 1


def test_arm_ceiling_does_not_transfer_time_and_shared_deadline_counts_metadata(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, pin = frozen
    now = [0.0]
    monkeypatch.setattr(c.time, "monotonic", lambda: now[0])

    def advance(method: str, _: str) -> None:
        if method == "POST":
            now[0] += 901

    http.hook = advance
    final = c.run(output, "Fake-only approval", pin)
    assert final["possibly_sent"] == 2 and not final["capture_complete"]
    assert final["elapsed"] == 1802 and final["overrun_seconds"] == 2
    assert all(a["elapsed"] == 901 for a in final["arms"])
    assert all(t <= 600 for _, _, _, t in http.calls)
    assert final["captured"] == ["01-01-unit_equivalence", "02-01-unit_equivalence"]
    assert all(not row["capture_complete"] for row in final["slots"])


def test_interrupt_keeps_raw_and_accounts_all_unsent_slots_without_resume(
    frozen: tuple[Path, str],
    http: HTTP,
) -> None:
    output, pin = frozen
    http.interrupt = True
    with pytest.raises(KeyboardInterrupt):
        c.run(output, "Fake-only approval", pin)
    final = read(output / "results/final.json")
    assert final["possibly_sent"] == 1 and len(final["unsent"]) == 11
    assert len(final["captured"]) == 1 and http.killed == http.reaped == 1
    assert (output / "results/manifest.json").exists()


def test_existing_output_edits_survive_repeated_freeze(frozen: tuple[Path, str]) -> None:
    output, _ = frozen
    path = output / "identities.json"
    path.write_bytes(b"Synthetic protected edit")
    with pytest.raises(FileExistsError):
        c.freeze(output, identities())
    assert path.read_bytes() == b"Synthetic protected edit"


def test_metadata_time_counts_and_metadata_timeout_stops_the_batch(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, pin = frozen
    now = [0.0]
    monkeypatch.setattr(c.time, "monotonic", lambda: now[0])

    def advance(_method: str, _endpoint: str) -> None:
        now[0] += 170

    http.hook = advance
    final = c.run(output, "Synthetic test", pin)
    assert final["possibly_sent"] == 1 and len(final["arms"]) == 1
    assert final["elapsed"] == 1020 and final["arms"][0]["overrun_seconds"] == 120
    assert [t for _, _, _, t in http.calls] == [600, 600, 560, 390, 220, 50]


def test_partial_artifact_write_still_seals_attempt_and_unsent_accounting(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from . import blind_review

    output, pin = frozen
    save = c._save

    def partial(path: Path, value: object) -> None:
        if path.name == "result.json":
            c._write(path, b'{"partial":')
            raise OSError("Synthetic partial write")
        save(path, value)

    monkeypatch.setattr(c, "_save", partial)
    final = c.run(output, "Synthetic test", pin)
    assert final["possibly_sent"] == 1 and len(final["unsent"]) == 11
    assert final["slots"][0]["artifact_errors"] and not final["capture_complete"]
    assert (output / "results/manifest.json").exists()
    target = tmp_path / "partial-write-review"
    blind_review.prepare(output, pin, target)
    records = read(target / "packet.json")["records"]
    assert len(records) == 18
    assert all(r["draft"] is None for r in records if r["capture_status"] != "complete")


def test_arm_expiring_during_source_gate_leaves_metadata_for_the_next_arm(
    frozen: tuple[Path, str],
    http: HTTP,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, pin = frozen
    now = [0.0]
    calls = 0
    validate = c._validate

    def expires(
        path: Path, expected: str
    ) -> tuple[dict[str, Any], tuple[c.Packet, ...], dict[str, bytes]]:
        nonlocal calls
        result = validate(path, expected)
        calls += 1
        if calls == 2:
            now[0] = 901
        return result

    monkeypatch.setattr(c.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(c, "_validate", expires)
    final = c.run(output, "Synthetic test", pin)
    assert final["possibly_sent"] == 6 and len(final["arms"]) == 2
    assert all(name.startswith("02-") for name in final["completed"])
    assert all(name.startswith("01-") for name in final["unsent"])
