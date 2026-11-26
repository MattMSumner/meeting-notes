import json
import random
from pathlib import Path

root = Path(__file__).resolve().parents[1]
pairs = {p["id"]: p for p in json.loads((root / "pairs.json").read_text())}
rows = []
for arm in ("baseline", "proposed"):
    lines = (root / "results" / (arm + ".jsonl")).read_text().splitlines()
    assert len(lines) == 23
    for line in lines[1:]:
        row = json.loads(line)
        pair = pairs[row["case"]]
        audit = row.get("audit", {})
        selected = audit.get("selected")
        comparison_selected = audit.get("comparison_selected")
        comparison = None
        if comparison_selected is not None:
            comparison = json.loads(audit["comparison_attempts"][comparison_selected]["reply"])
        material = {
            "transcript": pair["transcript"],
            "notes_supplied": pair["handwritten_text"] if arm == "proposed" else "",
            "summary": row.get("summary"),
            "error": row.get("error"),
            "warnings": audit["attempts"][selected]["warnings"] if selected is not None else [],
            "comparison": comparison,
            "attempt_findings": [
                {
                    "stage": stage,
                    "blocking": a["blocking"],
                    "warnings": a["warnings"],
                    "error": a["error"],
                }
                for stage, field in [("comparison", "comparison_attempts"), ("summary", "attempts")]
                for a in audit.get(field, [])
            ],
        }
        rows.append(({"arm": arm, "case": row["case"], "repetition": row["repetition"]}, material))
random.SystemRandom().shuffle(rows)
key = {}
blinded = []
for index, (identity, material) in enumerate(rows, 1):
    identifier = f"R{index:02d}"
    key[identifier] = identity
    blinded.append({"id": identifier, **material})
for name, data in [("blind-key.json", key), ("blinded.json", blinded)]:
    with (root / "results" / name).open("x") as output:
        output.write(json.dumps(data, indent=2) + "\n")
print("Prepared 44 opaque scoring rows; key saved separately.")
