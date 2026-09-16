"""Generate the published JSON Schema for the repair attestation predicate.

WHY THIS EXISTS

``specs/SPEC_repair_attestation.md``:24 promises "one normative wire format with a published
JSON Schema and a stable ``predicateType`` URI", and line 154 goes further -- it declines to
restate the enums because they are "enums in the JSON Schema and generated into TypeScript".
No such schema existed anywhere in the repository. So a published specification cited a
normative artifact that was never shipped, and the real source of the enums was
``dataforge/domain/vocabulary.py``.

WHY IT IS GENERATED, NOT WRITTEN

A hand-written schema beside a verifier is two specifications, and they drift silently in the
reassuring direction. ``PRODUCT.md``:94-113 records the general form of that failure -- a gate
that hardcodes any part of the universe it polices "can only detect changes to the part it
derives" -- and the specific instance where four public documents and one gate all said
"eight detector families" while the code had eleven, so the prose and the gate agreed with
each other and both disagreed with the code.

Everything here is therefore derived:

* required predicate fields from ``REQUIRED_PREDICATE_FIELDS``, the tuple the verifier's own
  ``_check_schema`` iterates;
* required ``tool`` fields from ``REQUIRED_TOOL_FIELDS``;
* every enum from the closed vocabularies in ``dataforge.domain.vocabulary``;
* the statement and predicate type URIs from the attestation module's constants.

Adding a required field to the verifier changes this file's output, which fails ``--check``
until it is regenerated. That is the point.

WHAT THIS SCHEMA IS NOT

It is not the normative verifier. Structural validity is necessary and nowhere near
sufficient: ``verify_attestation`` additionally re-derives trust strength from provenance and
column authority, checks the subject digest against the data, and rejects a statement whose
subjects name an artifact the predicate does not describe. A document that satisfies this
schema and fails verification is expected, and the schema says so in its own description.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dataforge.attestation import (
    ATTESTATION_VERSION,
    CLOSED_VOCABULARIES,
    PREDICATE_TYPE,
    REQUIRED_PREDICATE_FIELDS,
    REQUIRED_TOOL_FIELDS,
    STATEMENT_TYPE,
)
from dataforge.domain.premise import PREMISE_FORMAT

# No vocabulary is imported by name any more. Every closed set arrives through
# CLOSED_VOCABULARIES, so this generator cannot know about four of them and miss three.

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "specs" / "repair_attestation.schema.json"

_SHA256 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}

#: A sorted array of column names, the shape of the premise's four set-valued fields.
_COLUMN_NAMES: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


def _digest_block(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "required": ["digest"],
        "properties": {
            "digest": {
                "type": "object",
                "required": ["sha256"],
                "properties": {"sha256": _SHA256},
            }
        },
    }


def build_schema() -> dict[str, Any]:
    """Return the JSON Schema, with every enum and required field derived."""
    projected: set[str] = set()

    def closed(key: str) -> dict[str, Any]:
        """Project one closed vocabulary the normative verifier enforces.

        Recording each projection is what lets this generator REFUSE below when a vocabulary the
        verifier enforces would go unpublished. Before 2026-09-16 this module hand-enumerated four
        vocabularies while ``_check_vocabulary`` enforced seven, so ``provenance`` and
        ``independent_verification`` were published nowhere -- and SPEC section 6.2's claim that the
        vocabularies are "published as enums in the JSON Schema" was false for the one vocabulary a
        committed vector tests. A clean-room implementation obeying section 7's "MUST fail closed on
        anything unrecognised" therefore rejected 20 of 26 vectors
        (docs/trust/specification-sufficiency.md).
        """
        members = CLOSED_VOCABULARIES.get(key)
        if members is None:
            raise SystemExit(
                f"{key!r} is not a closed vocabulary in dataforge.attestation.CLOSED_VOCABULARIES"
            )
        projected.add(key)
        return {"type": "string", "enum": sorted(members)}

    witness = {
        "type": "object",
        "description": (
            "The evidence this constraint-derived write rested on, as data. Values are "
            "published as sha256(value)[:16], never in plaintext: the predicate deliberately "
            "carries no cell values, and a witness stating a group's distribution in the "
            "clear would turn a shareable document into a data-disclosure vector. Hashing "
            "costs nothing that matters -- a third party HOLDING THE TABLE hashes their own "
            "group and compares counts, in SQL or any language, with no DataForge code, so "
            "the derivation stays fully checkable without trusting our labelling rule; a "
            "party without the table learns only the shape.\n\n"
            "The normative verifier checks this block's INTERNAL COHERENCE (support is a "
            "strict majority of group_size, the written value's count equals its support, "
            "counts sum to group_size unless truncation is declared). It does not recompute "
            "from the data, which would make the verifier a CSV parser and force two "
            "implementations to agree byte-for-byte on quoting and line endings."
        ),
        "required": [
            "constraint",
            "constraint_kind",
            "group_size",
            "support",
            "value_digests",
            "new_value_digest",
        ],
        "properties": {
            "constraint": {"type": "string", "minLength": 1},
            "constraint_kind": {"type": "string", "enum": ["functional_dependency"]},
            "determinant_columns": {"type": "array", "items": {"type": "string"}},
            "determinant_digests": {
                "type": "array",
                "items": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
            },
            "group_size": {"type": "integer", "minimum": 1},
            "support": {"type": "integer", "minimum": 1},
            "value_digests": {
                "type": "array",
                "items": {
                    # Draft 2020-12 spells positional tuples `prefixItems`; the Draft-07
                    # `items: [a, b]` form is a plain array-of-schemas there and silently
                    # validates nothing. Caught by the test that validates this schema
                    # against the 2020-12 metaschema.
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "prefixItems": [
                        {"type": "string", "pattern": "^[0-9a-f]{16}$"},
                        {"type": "integer", "minimum": 0},
                    ],
                },
            },
            "truncated": {"type": "boolean"},
            "old_value_digest": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
            "new_value_digest": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
        },
    }

    fix = {
        "type": "object",
        "required": ["row", "column", "provenance", "verification_strength"],
        "properties": {
            "row": {"type": "integer", "minimum": 0},
            "column": {"type": "string", "minLength": 1},
            "old_value": {"type": ["string", "null"]},
            "new_value": {"type": ["string", "null"]},
            "detector_id": {"type": ["string", "null"]},
            "provenance": {"minLength": 1, **closed("fixes[].provenance")},
            "verification_strength": {
                **closed("fixes[].verification_strength"),
                "description": (
                    "Re-derived by the verifier from provenance and column authority. A "
                    "recorded value stronger than the derivation is a REJECT; a recorded "
                    "plausibility_only is always believed."
                ),
            },
            "witness": witness,
        },
    }

    predicate = {
        "type": "object",
        "required": list(REQUIRED_PREDICATE_FIELDS),
        "properties": {
            "attestation_version": {"type": "string", "const": ATTESTATION_VERSION},
            "tool": {
                "type": "object",
                "required": list(REQUIRED_TOOL_FIELDS),
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "minLength": 1},
                    "contract_version": {"type": "string"},
                },
            },
            "produced_at": {"type": "string", "format": "date-time"},
            "mode": closed("mode"),
            "applied": {"type": "boolean"},
            "reversible": {"type": "boolean"},
            "source": _digest_block("The pre-repair artifact."),
            "post": {
                "oneOf": [
                    _digest_block("The post-repair artifact. Null on a dry run."),
                    {"type": "null"},
                ]
            },
            "authority": {
                "type": "object",
                "required": ["authoritative_columns", "accepted_constraint_ids"],
                "properties": {
                    "authoritative_columns": {"type": "array", "items": {"type": "string"}},
                    "accepted_constraint_ids": {"type": "array", "items": {"type": "string"}},
                    "constraints_digest": {
                        "oneOf": [
                            {
                                "type": "object",
                                "required": ["sha256"],
                                "properties": {"sha256": _SHA256},
                            },
                            {"type": "null"},
                        ]
                    },
                    "constraints": {
                        "description": (
                            "The constraints embedded IN FULL, not by reference. A digest and "
                            "an id list are dangling pointers: a verifier must be able to read "
                            "what a fix was proven against without fetching anything, which is "
                            "what makes offline verification possible. ADVISORY as of 2026-09-16: "
                            "this is the schema file as authored, for a human to read, and "
                            "`constraints_present` tests only that it is non-empty. The field a "
                            "verifier recomputes authority from is `premise`."
                        )
                    },
                    "premise": {
                        "oneOf": [
                            {
                                "type": "object",
                                "required": ["premise_format"],
                                "properties": {
                                    "premise_format": {
                                        "type": "string",
                                        "const": PREMISE_FORMAT,
                                    },
                                    "columns": {
                                        "type": "object",
                                        "additionalProperties": {"type": "string"},
                                    },
                                    "pii_columns": _COLUMN_NAMES,
                                    "primary_key_columns": _COLUMN_NAMES,
                                    "not_null_columns": _COLUMN_NAMES,
                                    "unique_columns": _COLUMN_NAMES,
                                    "functional_dependencies": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["determinant", "dependent"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "determinant": {
                                                    "type": "array",
                                                    "minItems": 1,
                                                    "items": {"type": "string"},
                                                },
                                                "dependent": {"type": "string"},
                                            },
                                        },
                                    },
                                    "accepted_values": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["column", "values"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "column": {"type": "string"},
                                                "values": {
                                                    "type": "array",
                                                    "minItems": 1,
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                    "regex_constraints": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["column", "pattern"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "column": {"type": "string"},
                                                "pattern": {"type": "string"},
                                            },
                                        },
                                    },
                                    "relationships": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": [
                                                "column",
                                                "reference",
                                                "reference_column",
                                            ],
                                            "additionalProperties": False,
                                            "properties": {
                                                "column": {"type": "string"},
                                                "reference": {"type": "string"},
                                                "reference_column": {"type": "string"},
                                            },
                                        },
                                    },
                                    "domain_bounds": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["column"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "column": {"type": "string"},
                                                "min_value": {"type": ["number", "null"]},
                                                "max_value": {"type": ["number", "null"]},
                                                "inclusive_min": {"type": "boolean"},
                                                "inclusive_max": {"type": "boolean"},
                                            },
                                        },
                                    },
                                    "aggregate_dependencies": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": [
                                                "source_column",
                                                "target_column",
                                                "aggregate",
                                            ],
                                            "additionalProperties": False,
                                            "properties": {
                                                "source_column": {"type": "string"},
                                                "target_column": {"type": "string"},
                                                "aggregate": {
                                                    "type": "string",
                                                    "enum": ["avg", "sum"],
                                                },
                                                "group_by": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                                "additionalProperties": False,
                                "description": (
                                    "The declared schema authority was computed from, in the "
                                    "canonical premise format of SPEC section 6.4.1. This is what "
                                    "`authority_is_entailed` recomputes `authoritative_columns` "
                                    "from, so the authority claim is arithmetic a reader can "
                                    "repeat rather than an assertion a reader must accept. "
                                    "`additionalProperties: false` is load-bearing at every level: "
                                    "a premise carrying a constraint this format cannot express "
                                    "would confer authority in-process while understating it here."
                                ),
                            },
                            {"type": "null"},
                        ]
                    },
                },
            },
            "fixes": {"type": "array", "items": fix},
            "held": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "row": {"type": "integer", "minimum": 0},
                        "column": {"type": "string"},
                        "review_reason": closed("held[].review_reason"),
                    },
                },
            },
            "verdicts": {
                "type": "object",
                "properties": {
                    "verifier": closed("verdicts.verifier"),
                    "safety": closed("verdicts.safety"),
                    "independent_verification": closed("verdicts.independent_verification"),
                },
            },
            "journal": {
                "type": "object",
                "properties": {
                    "txn_id": {"type": ["string", "null"]},
                    "head_sha256": {"oneOf": [_SHA256, {"type": "null"}]},
                },
            },
            "revert_command": {"type": ["string", "null"]},
            "model": {
                "type": ["object", "null"],
                "description": (
                    "Provider and model identity when any fix is LLM-origin; null otherwise. "
                    "Declared `string | null` until 2026-09-16, which contradicted both SPEC "
                    "section 6.2 and `build_attestation`, whose emitted value is `dict(model)`. "
                    "No vector caught it because every vector sets model to null."
                ),
            },
            "limitations": {"type": "array", "items": {"type": "string"}},
            "verification": {
                "type": "object",
                "properties": {"checks_available": {"type": "array", "items": {"type": "string"}}},
            },
        },
    }

    # Refuse on the unnameable. Every closed vocabulary the normative verifier enforces must be
    # published here, or a third party cannot enforce it and this schema's own claim to be the
    # publication point is false. PRODUCT.md section 1.3 records four earlier instances of a
    # generator that derived every projected VALUE while hand-enumerating WHICH vocabularies to
    # project; this is the assertion that stops a fifth.
    unpublished = sorted(set(CLOSED_VOCABULARIES) - projected)
    if unpublished:
        raise SystemExit(
            f"UNPUBLISHED CLOSED VOCABULARIES: {unpublished}. The normative verifier enforces "
            "these but this schema does not publish them, so an independent implementation "
            "cannot enforce them either. Project each one with closed('<key>')."
        )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dataforge.dev/schemas/RepairAttestation/v1.json",
        "title": "DataForge repair attestation (in-toto statement)",
        "description": (
            "Structural schema for the attestation promised at "
            "specs/SPEC_repair_attestation.md. GENERATED by "
            "scripts/ci/generate_attestation_schema.py from the verifier's own required-field "
            "tuples and the closed vocabularies in dataforge/domain/vocabulary.py -- never "
            "hand-edited, because a schema written beside a verifier is a second "
            "specification that drifts silently.\n\n"
            "Structural validity is NECESSARY AND NOT SUFFICIENT. verify_attestation "
            "additionally re-derives trust strength from provenance and column authority, "
            "checks the subject digest against the data, requires every subject to name the "
            "artifact the predicate describes, and verifies the DSSE signature when present. "
            "A document that satisfies this schema and fails verification is expected."
        ),
        "type": "object",
        "required": ["_type", "subject", "predicateType", "predicate"],
        "properties": {
            "_type": {"type": "string", "const": STATEMENT_TYPE},
            "predicateType": {"type": "string", "const": PREDICATE_TYPE},
            "subject": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "in-toto permits N subjects. Every subject must name the artifact the "
                    "predicate describes: duplicates are allowed, and a subject naming a "
                    "different artifact is a REJECT. Reading only subject[0] -- which both "
                    "verifiers did until 2026-08-29 -- let a valid attestation be extended "
                    "with a subject nobody attested."
                ),
                "items": {
                    "type": "object",
                    "required": ["digest"],
                    "properties": {
                        "name": {"type": "string"},
                        "digest": {
                            "type": "object",
                            "required": ["sha256"],
                            "properties": {"sha256": _SHA256},
                        },
                    },
                },
            },
            "predicate": predicate,
        },
    }


def render() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    rendered = render()
    if args.write:
        SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {SCHEMA_PATH.relative_to(REPO)}")
        return 0

    if not SCHEMA_PATH.is_file():
        print(
            f"MISSING: {SCHEMA_PATH.relative_to(REPO)} does not exist. "
            "Run scripts/ci/generate_attestation_schema.py --write."
        )
        return 1
    if SCHEMA_PATH.read_text(encoding="utf-8") != rendered:
        print(
            f"STALE: {SCHEMA_PATH.relative_to(REPO)} disagrees with the verifier's required "
            "fields or the closed vocabularies. Regenerate with --write; do not hand-edit."
        )
        return 1
    print(f"Attestation JSON Schema is current ({SCHEMA_PATH.relative_to(REPO)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
