"""Render authored synthetic previews without invoking the application or models."""

import argparse
from pathlib import Path

from prototypes.reviewable_draft.examples import CASES, load_examples, preview, write_previews


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *CASES), default="all")
    parser.add_argument(
        "--output-dir", type=Path, help="new directory only; never overwrite previews"
    )
    args = parser.parse_args()
    cases = CASES if args.case == "all" else (args.case,)
    if args.output_dir is not None:
        try:
            write_previews(args.output_dir, cases)
        except (FileExistsError, ValueError) as error:
            parser.error(str(error))
        print(f"Wrote {len(cases)} authored previews to {args.output_dir}; model requests: 0")
        return
    drafts = load_examples()
    print("\n\n---\n\n".join(preview(drafts[name]) for name in cases), end="")


if __name__ == "__main__":
    main()
