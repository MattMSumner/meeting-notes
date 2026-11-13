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


def main():
    run = read(ROOT / "run.json")
    assert run["status"] == "complete", "Wait for both captured arms"
    pairs = {p["id"]: p for p in read(FREEZE / "pairs.json")}
    expectations = {p["id"]: p for p in read(FREEZE / "expected.json")}
    assert len(pairs) == 40
    packets = []
    hashes = {}
    for arm in ("baseline", "proposed"):
        path = ROOT / (arm + ".jsonl")
        hashes[arm] = hashlib.sha256(path.read_bytes()).hexdigest()
        lines = path.read_text().splitlines()
        header, rows = json.loads(lines[0]), [json.loads(s) for s in lines[1:]]
        assert header["arm"] == arm and header["repetitions"] == 1
        assert [r["case"] for r in rows] == list(pairs)
        for row in rows:
            pair = pairs[row["case"]]
            audit = row.get("audit", {})
            stages = {}
            for stage, field in (("comparison", "comparison_attempts"), ("summary", "attempts")):
                stages[stage] = [
                    {
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
                    }
                    for a in audit.get(field, [])
                ]
            if not audit:
                stages["summary"] = [
                    {
                        "reply": sent.get("response", {}).get("message", {}).get("content"),
                        "error": sent.get("error"),
                    }
                    for sent in row["transport"]
                ]
            material = {
                "meeting": pair["meeting"],
                "transcript": pair["transcript"],
                "notes_supplied": pair["handwritten_text"] if arm == "proposed" else "",
                "declared_expectation": expectations[row["case"]]["expected"],
                "expected_relations_when_notes_supplied": expectations[row["case"]].get(
                    "expected_outcomes", []
                ),
                "summary": row.get("summary"),
                "error": row.get("error"),
                "selected": audit.get("selected"),
                "comparison_selected": audit.get("comparison_selected"),
                "attempts": stages,
            }
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
