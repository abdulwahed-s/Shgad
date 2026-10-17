"""Human-run sealing helper. Emit only a SHA-256 and aggregate counts.

Builders test this code with fabricated format probes only. They must never run
it against actual held-out questions. This helper does not write any files.
"""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    from data_contract import validate_question
else:
    from .data_contract import validate_question

ROOT = Path(__file__).resolve().parents[1]


def seal_manifest(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("Sealed input must be outside the repository")
    raw = path.read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    questions = []
    for line in lines:
        question = json.loads(
            line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
        )
        validate_question(question)
        questions.append(question)
    if len(questions) != 60 or len({q["id"] for q in questions}) != 60:
        raise ValueError("Invalid sealed counts")
    behaviors = Counter(q["spec"]["expected_behavior"] for q in questions)
    if behaviors["answer"] != 40 or behaviors["clarify"] + behaviors["refuse"] != 20:
        raise ValueError("Invalid sealed split")
    if any(q["arabic_review"] != "approved" for q in questions):
        raise ValueError("Arabic review is pending")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "total_count": len(questions),
        "counts_by_category": dict(Counter(q["category"] for q in questions)),
        "counts_by_behavior": dict(behaviors),
    }


def main():
    try:
        path = os.environ.get("HELDOUT_PATH")
        if not path:
            raise ValueError()
        result = seal_manifest(path)
    except (ValueError, TypeError, KeyError, UnicodeError, OSError):
        # No traceback, file path, failed row or exception text can expose content.
        print(
            "Sealing validation failed; check the format and review/count gates.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
