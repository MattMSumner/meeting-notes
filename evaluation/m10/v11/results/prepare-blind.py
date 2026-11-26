#!/usr/bin/env python3
"""Create opaque scoring packets once, without changing captured model evidence."""

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FREEZE = ROOT.parent


def read(path):
    return json.loads(path.read_text())


def write_once(name, value):
    with (ROOT / name).open("x") as output:
        output.write(json.dumps(value, indent=2) + "\n")


def response_metadata(response):
    message = (response or {}).get("message")
    return {
        "received": response is not None,
        "message_type": type(message).__name__,
        "content_present": isinstance(message, dict) and "content" in message,
        **{
            k: response[k]
            for k in ("model", "done", "done_reason", "error")
            if k in (response or {})
        },
    }


def packet_material(row, pair, expectation, arm, diagnostics):
    audit = row.get("audit", {})
    stages = {}
    for stage, field in (("comparison", "comparison_attempts"), ("summary", "attempts")):
        stages[stage] = [
            {
                "response_metadata": response_metadata(a.get("response")),
                **{
                    k: a[k]
                    for k in (
                        "reply",
                        "error",
                        "blocking",
                        "warnings",
                        "resolution",
                        "compilation",
                        "selection_errors",
                    )
                    if k in a
                },
            }
            for a in audit.get(field, [])
        ]
    if not audit:
        assert arm == "baseline" and diagnostics is not None
        attempts = diagnostics["attempts"]
        assert {a["index"] for a in attempts if a["sent"]} == set(range(len(row["transport"])))
        stages["summary"] = []
        for attempt in attempts:
            sent = row["transport"][attempt["index"]] if attempt["sent"] else {}
            response = sent.get("response")
            message = (response or {}).get("message")
            stages["summary"].append(
                {
                    **attempt,
                    "reply": message.get("content") if isinstance(message, dict) else None,
                    "response_metadata": response_metadata(response),
                }
            )
    return {
        "meeting": pair["meeting"],
        "transcript": pair["transcript"],
        "notes_supplied": pair["handwritten_text"] if arm == "proposed" else "",
        "declared_expectation": expectation["expected"],
        "expected_relations_when_notes_supplied": expectation.get("expected_outcomes", []),
        "summary": row.get("summary"),
        "error": row.get("error"),
        "selected": audit.get("selected") if audit else diagnostics["selected_attempt"],
        "comparison_selected": audit.get("comparison_selected"),
        "attempts": stages,
    }


def main():
    run = read(ROOT / "run.json")
    assert run["status"] == "complete", "Wait for both captured arms"
    verification = read(ROOT / "verification/completion.json")
    assert verification["evidence_integrity"] == "verified"
    assert verification["recorded_slots"] == verification["expected_slots"] == 80
    for name in ("run.json", "baseline.jsonl", "proposed.jsonl"):
        assert (
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            == verification["input_sha256"][name]
        )
    pairs = {p["id"]: p for p in read(FREEZE / "pairs.json")}
    expectations = {p["id"]: p for p in read(FREEZE / "expected.json")}
    assert len(pairs) == 40
    packets = []
    hashes = {}
    for arm in ("baseline", "proposed"):
        diagnostics = {o["case"]: o for o in verification["arms"][arm]["outcomes"]}
        path = ROOT / (arm + ".jsonl")
        hashes[arm] = hashlib.sha256(path.read_bytes()).hexdigest()
        lines = path.read_text().splitlines()
        header, rows = json.loads(lines[0]), [json.loads(s) for s in lines[1:]]
        assert header["arm"] == arm and header["repetitions"] == 1
        assert [r["case"] for r in rows] == list(pairs)
        for row in rows:
            material = packet_material(
                row, pairs[row["case"]], expectations[row["case"]], arm, diagnostics[row["case"]]
            )
            identity = {"arm": arm, "case": row["case"], "repetition": row["repetition"]}
            packets.append((identity, material))
    random.SystemRandom().shuffle(packets)
    key, blinded = {}, []
    for index, (identity, material) in enumerate(packets, 1):
        label = f"R{index:03d}"
        key[label] = identity
        blinded.append({"id": label, **material})
    write_once("blind-key.json", key)
    write_once("blinded.json", blinded)
    write_once(
        "blind-preparation.json",
        {
            "captured_output_sha256": hashes,
            "run_sha256": hashlib.sha256((ROOT / "run.json").read_bytes()).hexdigest(),
            "verification_sha256": hashlib.sha256(
                (ROOT / "verification/completion.json").read_bytes()
            ).hexdigest(),
            "files_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ("blind-key.json", "blinded.json")
            },
            "rows": len(blinded),
            "method": "SystemRandom opaque labels; key kept separate until assessments lock.",
            "limitations": (
                "Notes and output structure reveal arms; agent assessment is not fully blinded "
                "or independent held-out evidence."
            ),
        },
    )
    print("Prepared 80 opaque scoring packets; the arm key is separate.")


if __name__ == "__main__":
    main()
