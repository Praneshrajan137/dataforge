"""Bind `specs/SPEC_repair_attestation.md` to the code it specifies.

The first gate in this repository to read a `specs/SPEC_*.md` file at all. Until 2026-09-15
nothing did, so the highest-authority normative documents were the one category of published
prose with an **empty** policed population -- not a narrowed gate, no gate. Four false claims
survived there, including two in `PRODUCT.md` about the thesis itself.

Three populations must correspond exactly:

* **specified** -- the numbered check list in section 7 of the specification;
* **implemented** -- ``dataforge.attestation.NORMATIVE_CHECKS``, which ``AttestationCheck``
  refuses to construct a name outside of;
* **exercised** -- the check names some committed vector expects to fail.

and one more, because a closed set nobody publishes cannot be enforced by a stranger:

* **vocabularies** -- every key of ``dataforge.attestation.CLOSED_VOCABULARIES`` must be named
  in the specification and published as an enum in the generated JSON Schema.

Anything in one population and unnameable in another is a REFUSAL, not a warning. That is the
DO-178C shape ``PRODUCT.md`` section 1.3 prescribes: enumerate the artifact totally, give the
remainder a name and a reason, refuse on anything unnameable. It is used here rather than a
lower-bound assertion because the defect this gate exists to catch was invisible to two of
those: ``len(vectors) >= 15`` against 26 actual, and a hardcoded ten-name tuple against twelve
implemented checks. A lower bound cannot see a missing member.

Why the exemption lists are dictionaries rather than sets: an exemption without a stated reason
is indistinguishable from an oversight six months later, and a reason that no longer applies is
how a gate quietly stops covering something.

Usage:
    python scripts/ci/spec_correspondence.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dataforge.attestation import (  # noqa: E402
    CLOSED_VOCABULARIES,
    NORMATIVE_CHECKS,
)

SPEC = PROJECT_ROOT / "specs" / "SPEC_repair_attestation.md"
SCHEMA = PROJECT_ROOT / "specs" / "repair_attestation.schema.json"
VECTORS = PROJECT_ROOT / "tests" / "fixtures" / "attestation" / "vectors.json"

#: A numbered section-7 entry: ``3. `schema_complete` - every required field ...``
_CHECK_ITEM = re.compile(r"^\s*\d+\.\s+`([a-z_]+)`\s*-")

#: The normative check list is bounded by these two markers, so a numbered list elsewhere in the
#: document cannot inflate the parsed population.
_NORMATIVE_OPEN = "**Normative.**"
_NORMATIVE_CLOSE = "**Advisory.**"

#: Implemented checks that no vector can exercise a FAILURE for, each with its reason. Empty as of
#: 2026-09-15: `data_identity` and `witness_is_coherent` both gained failure vectors that day,
#: having had none since they were written.
NO_FAILURE_VECTOR_EXEMPT: dict[str, str] = {}

#: The minimum a non-vacuous section 7 must yield. A parse that silently matched nothing would make
#: every comparison below pass by emptiness, which is the failure mode this whole gate is about.
MINIMUM_PARSED_CHECKS = 8


def specified_checks(spec_text: str) -> list[str]:
    """Return the check names section 7 lists, in document order.

    Raises when the normative block cannot be located, rather than returning an empty list: a
    parser that yields nothing must not read as a document that specifies nothing.
    """
    start = spec_text.find(_NORMATIVE_OPEN)
    if start < 0:
        raise ValueError(
            f"cannot find {_NORMATIVE_OPEN!r} in the specification, so the normative check "
            "list cannot be located. Refusing rather than reporting an empty population."
        )
    end = spec_text.find(_NORMATIVE_CLOSE, start)
    block = spec_text[start:] if end < 0 else spec_text[start:end]

    names = [match.group(1) for line in block.splitlines() if (match := _CHECK_ITEM.match(line))]
    if len(names) < MINIMUM_PARSED_CHECKS:
        raise ValueError(
            f"section 7 parsed to only {len(names)} checks ({names}), below the "
            f"{MINIMUM_PARSED_CHECKS} a real list must have. Either the list moved or the "
            "pattern broke; both are refusals."
        )
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"section 7 lists these checks more than once: {duplicates}")
    return names


def exercised_checks(vectors_payload: dict[str, object]) -> set[str]:
    """Return every check name some vector expects to fail."""
    vectors = vectors_payload.get("vectors")
    if not isinstance(vectors, dict) or not vectors:
        raise ValueError("the vector file carries no vectors")
    exercised: set[str] = set()
    for case in vectors.values():
        if isinstance(case, dict):
            failures = case.get("expect_failures")
            if isinstance(failures, list):
                exercised.update(str(name) for name in failures)
    return exercised


def published_enums(schema: dict[str, object]) -> set[str]:
    """Return every predicate path the JSON Schema publishes as a closed enum.

    Walks the document rather than reading known locations, so a vocabulary that moves within the
    schema stays found and one that vanishes is reported.
    """
    found: set[str] = set()

    def walk(node: object, path: tuple[str, ...]) -> None:
        if not isinstance(node, dict):
            return
        if "enum" in node and path:
            found.add(".".join(path))
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for field, sub in value.items():
                    walk(sub, (*path, str(field)))
            elif key == "items":
                # An array's members share the array's path, marked so it reads like the
                # CLOSED_VOCABULARIES keys: `fixes[].provenance`.
                if path:
                    walk(value, (*path[:-1], f"{path[-1]}[]"))
            elif isinstance(value, dict):
                walk(value, path)

    walk(schema.get("properties", {}), ())
    return found


def _correspondence_errors(
    specified: list[str],
    implemented: tuple[str, ...],
    exercised: set[str],
    vocabularies: set[str],
    published: set[str],
    spec_text: str,
) -> list[str]:
    """Every way the four populations can fail to correspond."""
    errors: list[str] = []
    specified_set = set(specified)
    implemented_set = set(implemented)

    for name in sorted(implemented_set - specified_set):
        errors.append(
            f"CHECK NOT SPECIFIED: {name!r} is in NORMATIVE_CHECKS but section 7 does not list "
            "it. A third party cannot implement a check the specification does not name -- this "
            "is exactly how `witness_is_coherent` shipped in two verifiers and no document."
        )
    for name in sorted(specified_set - implemented_set):
        errors.append(
            f"CHECK NOT IMPLEMENTED: section 7 lists {name!r} but NORMATIVE_CHECKS does not. "
            "The specification promises a check nothing performs."
        )

    for name in sorted(implemented_set - exercised - set(NO_FAILURE_VECTOR_EXEMPT)):
        errors.append(
            f"CHECK NOT EXERCISED: no committed vector expects {name!r} to fail. Add one, or add "
            "it to NO_FAILURE_VECTOR_EXEMPT with the reason it cannot have one."
        )
    for name in sorted(set(NO_FAILURE_VECTOR_EXEMPT) - implemented_set):
        errors.append(
            f"STALE EXEMPTION: {name!r} is exempt from needing a vector but is no longer a "
            "normative check. An exemption that outlives its reason widens what goes unchecked."
        )
    for name in sorted(set(NO_FAILURE_VECTOR_EXEMPT) & exercised):
        errors.append(
            f"NEEDLESS EXEMPTION: {name!r} is exempt from needing a vector and has one. Remove "
            "the exemption, so the list keeps meaning what it says."
        )

    for path in sorted(vocabularies - published):
        errors.append(
            f"VOCABULARY NOT PUBLISHED: {path!r} is enforced by the normative tier but the JSON "
            "Schema publishes no enum for it, so an independent implementation cannot enforce it. "
            "This is the defect that cost a clean-room verifier 20 of 26 vectors."
        )
    for path in sorted(vocabularies):
        field = path.rsplit(".", 1)[-1]
        if f"`{field}`" not in spec_text and f"`{path}`" not in spec_text:
            errors.append(
                f"VOCABULARY NOT NAMED: {path!r} is a closed set the verifier enforces and the "
                "specification never mentions the field."
            )

    return errors


def check() -> int:
    spec_text = SPEC.read_text(encoding="utf-8")
    specified = specified_checks(spec_text)
    exercised = exercised_checks(json.loads(VECTORS.read_text(encoding="utf-8")))
    published = published_enums(json.loads(SCHEMA.read_text(encoding="utf-8")))
    vocabularies = set(CLOSED_VOCABULARIES)

    errors = _correspondence_errors(
        specified, NORMATIVE_CHECKS, exercised, vocabularies, published, spec_text
    )

    print(
        f"specified {len(specified)} | implemented {len(NORMATIVE_CHECKS)} | "
        f"exercised {len(exercised)} | closed vocabularies {len(vocabularies)} "
        f"({len(vocabularies & published)} published)"
    )

    if errors:
        print("\nSPEC CORRESPONDENCE FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "Specification, implementation, vectors and published vocabularies correspond exactly; "
        f"{len(NO_FAILURE_VECTOR_EXEMPT)} named exemption(s)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args(argv)
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
