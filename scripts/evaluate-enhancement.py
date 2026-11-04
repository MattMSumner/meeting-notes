#!/usr/bin/env python3
"""Run one frozen M10 arm only after choosing repetitions and a request budget."""

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "evaluation" / "m10"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", choices=("v1", "v2", "v3"), default="v1")
    parser.add_argument("--arm", choices=("baseline", "proposed"), required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="explicitly permit local inference")
    args = parser.parse_args()
    if not args.run or args.repetitions < 1 or args.max_requests < 1:
        parser.error("Choose a positive repetition count and request budget, then pass --run.")
    root = ROOT if args.freeze == "v1" else ROOT / args.freeze
    manifest = json.loads((root / "sha256.json").read_text())
    for name, expected in manifest.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            parser.error(f"Frozen material changed: {name}")
    # Import the frozen implementation, independently of the installed working tree.
    sys.path.insert(0, str(root / args.arm))
    from meeting_notes.meeting import Meeting
    from meeting_notes.ollama import OllamaSummarizer, http_post
    from meeting_notes.summary import SummaryError

    settings = json.loads((root / "settings.json").read_text())
    pairs = json.loads((root / "pairs.json").read_text())
    post = http_post("http://localhost:11434")
    requests = 0
    trace: list[dict[str, Any]] = []

    def bounded_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        nonlocal requests
        if requests >= args.max_requests:
            raise SummaryError("Chosen request budget exhausted")
        requests += 1
        attempt: dict[str, Any] = {"request": deepcopy(body), "request_number": requests}
        trace.append(attempt)
        try:
            response = post(path, body)
        except SummaryError as error:
            attempt["error"] = str(error)
            raise
        attempt["response"] = response
        return response

    # Exclusive creation prevents replacing previous evaluation evidence.
    with args.output.open("x", encoding="utf-8") as output:
        output.write(
            json.dumps(
                {
                    "freeze": args.freeze,
                    "arm": args.arm,
                    "repetitions": args.repetitions,
                    "max_requests": args.max_requests,
                    "settings": settings,
                    "frozen_hashes": manifest,
                }
            )
            + "\n"
        )
        for repetition in range(args.repetitions):
            for pair in pairs:
                if requests >= args.max_requests:
                    return
                trace = []
                context = pair["meeting"]
                meeting = Meeting.new(
                    context["title"],
                    datetime.fromisoformat(context["started_at"]),
                    tuple(context["attendees"]),
                )
                model = OllamaSummarizer(
                    settings["model"],
                    settings["num_ctx"],
                    bounded_post,
                    context["my_name"],
                    think=settings["think"],
                )
                result: dict[str, Any] = {"case": pair["id"], "repetition": repetition + 1}
                try:
                    if args.arm == "baseline":
                        summary = model.summarize(meeting, pair["transcript"])
                    else:
                        summary = model.summarize(
                            meeting, pair["transcript"], handwritten_text=pair["handwritten_text"]
                        )
                    result["summary"] = summary.model_dump()
                except SummaryError as error:
                    result["error"] = str(error)
                audit = getattr(model, "audit", None)
                if audit is not None:
                    result["audit"] = audit.model_dump()
                result["transport"] = trace
                result["requests_so_far"] = requests
                output.write(json.dumps(result) + "\n")
                output.flush()


if __name__ == "__main__":
    main()
