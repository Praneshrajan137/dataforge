"""Generate the committed golden attestation vectors.

These vectors are the conformance suite. Two independent implementations (Python and
TypeScript) must agree on every one, including every rejection -- which is what makes
``dataforge.repair.attestation/v1`` a specification rather than one program's behaviour.

Rules the vectors must obey:

* **No absolute paths anywhere.** The transaction journal already demonstrates why: it
  embeds absolute local paths inside its hash preimage, so two runs on identical bytes in
  different directories produce different chains. A vector that is machine-dependent
  cannot be a shared fixture.
* **A fixed signing key and fixed timestamps.** Vectors must be byte-reproducible, so
  nothing may come from the clock or from a random keypair.
* **One vector per distinct rejection reason**, because a suite that only proves the happy
  path proves almost nothing.

Usage:
    python scripts/ci/generate_attestation_vectors.py --write
    python scripts/ci/generate_attestation_vectors.py --check
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from dataforge.attestation import (  # noqa: E402
    ATTESTATION_VERSION,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    sign_attestation,
)
from dataforge.domain.premise import PREMISE_FORMAT  # noqa: E402

VECTOR_DIR = PROJECT_ROOT / "tests" / "fixtures" / "attestation"

# A fixed, published-in-the-repo test key. It signs test vectors and nothing else; it is
# not a trust root and must never be used to sign a real attestation.
TEST_SEED = bytes(range(32))

# A SECOND fixed key, used only to sign a vector that must then FAIL verification against the
# suite's published key. Section 9 required "a wrong-key signature REJECTS" from 2026-08-13 and
# no vector supplied it: the only signature rejection vector tampered with the payload and
# verified against the CORRECT key, which exercises a different code path entirely.
WRONG_SEED = bytes(range(100, 132))

# Bytes a `data_identity` vector can actually hash. Section 7's digest check had zero vectors
# from the day it was written, because the vector format carried no field for input bytes -- so
# the one check that binds an attestation to real bytes was the one check never exercised.
DATA_BYTES = b"id,amount\n1,100\n"
DATA_DIGEST = hashlib.sha256(DATA_BYTES).hexdigest()

POST_DIGEST = "b" * 64
SOURCE_DIGEST = "a" * 64
JOURNAL_HEAD = "c" * 64
CONSTRAINTS_DIGEST = "d" * 64

# The premise most authority-carrying vectors publish. `int` is in DISCRIMINATING_COLUMN_TYPES, so
# this entails authority over exactly `amount` -- which is what `_with_authority` claims. Written as
# a literal rather than via `premise_to_canonical` so the vectors remain readable as a wire format
# and a reimplementation can copy them without running Python.
_PREMISE_AMOUNT_INT: dict[str, Any] = {
    "premise_format": PREMISE_FORMAT,
    "columns": {"amount": "int"},
}


def _base_predicate() -> dict[str, Any]:
    return {
        "attestation_version": ATTESTATION_VERSION,
        "tool": {
            "name": "dataforge",
            "version": "0.1.0",
            "contract_version": "repair_contract_v2",
        },
        "produced_at": "2026-08-13T00:00:00Z",
        "mode": "apply",
        "applied": True,
        "reversible": True,
        "source": {"digest": {"sha256": SOURCE_DIGEST}},
        "post": {"digest": {"sha256": POST_DIGEST}},
        "authority": {
            "authoritative_columns": [],
            "accepted_constraint_ids": [],
            "constraints_digest": None,
            "constraints": None,
            "premise": None,
        },
        "fixes": [
            {
                "row": 7,
                "column": "amount",
                "detector_id": "decimal_shift",
                "provenance": "deterministic",
                "verification_strength": "proven",
            }
        ],
        "held": [],
        "verdicts": {
            "verifier": "accept",
            "safety": "allow",
            "independent_verification": "not_run",
        },
        "journal": {"txn_id": "txn-2026-08-13-vector", "head_sha256": JOURNAL_HEAD},
        "revert_command": "dataforge revert txn-2026-08-13-vector",
        "model": None,
        "limitations": [],
        "verification": {"checks_available": []},
    }


def _statement(predicate: dict[str, Any], *, subject_digest: str | None = None) -> dict[str, Any]:
    digest = subject_digest
    if digest is None:
        digest = POST_DIGEST if predicate.get("applied") else SOURCE_DIGEST
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "data.csv", "digest": {"sha256": digest}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }


def _with_authority(
    predicate: dict[str, Any], *, constraints: object, premise: object = _PREMISE_AMOUNT_INT
) -> dict[str, Any]:
    predicate["authority"] = {
        "authoritative_columns": ["amount"],
        "accepted_constraint_ids": ["amount-int"],
        "constraints_digest": {"sha256": CONSTRAINTS_DIGEST},
        "constraints": constraints,
        "premise": premise,
    }
    predicate["fixes"] = [
        {
            "row": 7,
            "column": "amount",
            "detector_id": "external",
            "provenance": "external",
            "verification_strength": "proven",
        }
    ]
    return predicate


def build_vectors() -> dict[str, dict[str, Any]]:
    """Every vector, with the verdict each implementation must reach."""
    vectors: dict[str, dict[str, Any]] = {}

    def add(
        name: str,
        document: Any,
        *,
        expect_ok: bool,
        expect_failures: list[str],
        data_b64: str | None = None,
    ) -> None:
        case: dict[str, Any] = {
            "description": name.replace("-", " "),
            "expect_ok": expect_ok,
            "expect_failures": sorted(expect_failures),
            "document": document,
        }
        if data_b64 is not None:
            # Present only on vectors that exercise `data_identity`. A runner that ignores this
            # field still reaches the recorded verdict on every other vector, so the extension is
            # backward-compatible -- but it will report `data_identity` skipped on these two and
            # disagree, which is the point of adding them.
            case["data_b64"] = data_b64
        vectors[name] = case

    add(
        "valid-deterministic-applied",
        _statement(_base_predicate()),
        expect_ok=True,
        expect_failures=[],
    )

    dry = _base_predicate()
    dry["mode"] = "dry_run"
    dry["applied"] = False
    dry["post"] = None
    dry["fixes"] = []
    dry["revert_command"] = None
    dry["journal"] = {"txn_id": None, "head_sha256": None}
    dry["verdicts"] = {
        "verifier": "not_run",
        "safety": "allow",
        "independent_verification": "not_run",
    }
    add("valid-dry-run", _statement(dry), expect_ok=True, expect_failures=[])

    add(
        "valid-external-on-covered-column",
        _statement(_with_authority(_base_predicate(), constraints={"columns": {"amount": "int"}})),
        expect_ok=True,
        expect_failures=[],
    )

    off = _with_authority(
        _base_predicate(),
        constraints={"columns": {"id": "int"}},
        # The premise must entail the claim this vector makes, or the vector would fail TWO checks
        # and stop isolating the one it exists for. `authoritative_columns` is overridden to `["id"]`
        # below, so the premise declares `id`. Leaving it as `amount` would also have been a
        # correct REJECT -- and a worse vector, because "one vector per distinct rejection reason"
        # is what lets a failure name point at a cause.
        premise={"premise_format": PREMISE_FORMAT, "columns": {"id": "int"}},
    )
    off["authority"]["authoritative_columns"] = ["id"]
    add(
        "reject-external-off-authority",
        _statement(off),
        expect_ok=False,
        expect_failures=["strength_is_earned"],
    )

    dangling = _with_authority(_base_predicate(), constraints=None, premise=None)
    add(
        "reject-schema-proven-without-embedded-constraints",
        _statement(dangling),
        expect_ok=False,
        # Gained `authority_is_entailed` on 2026-09-16. This document claims authority over `amount`
        # and publishes no premise at all, which is the shape EVERY attestation had before that date.
        # It now fails for two distinct reasons: no constraint payload for a human, and nothing a
        # third party could recompute the claim from. A vector gaining a failure name is a
        # strengthening; the assertion it already made is untouched.
        expect_failures=["authority_is_entailed", "constraints_present"],
    )

    # --- authority_is_entailed: the forgery the twelve preceding checks cannot see ---------------
    # Both of these pass every other normative check. That is the point: before this check existed a
    # producer could publish any authority claim beside any premise, so `proven` was an assertion a
    # reader had to accept rather than arithmetic a reader could repeat.
    forged = _with_authority(_base_predicate(), constraints={"columns": {"amount": "int"}})
    forged["authority"]["authoritative_columns"] = ["amount", "secret"]
    forged["fixes"].append(
        {
            "row": 3,
            "column": "secret",
            "detector_id": "external",
            "provenance": "external",
            "verification_strength": "proven",
        }
    )
    add(
        "reject-authority-wider-than-the-premise-entails",
        _statement(forged),
        expect_ok=False,
        expect_failures=["authority_is_entailed"],
    )

    # `str` is encodable but constrains nothing, so it confers no authority. Until 2026-08-25 a
    # premise declaring every column `str` let 10 of 14 adversarial writes through, each stamped
    # `proven`; this vector is that defect made externally checkable.
    non_discriminating = _with_authority(
        _base_predicate(),
        constraints={"columns": {"amount": "str"}},
        premise={"premise_format": PREMISE_FORMAT, "columns": {"amount": "str"}},
    )
    add(
        "reject-authority-from-a-non-discriminating-type",
        _statement(non_discriminating),
        expect_ok=False,
        expect_failures=["authority_is_entailed"],
    )

    # `date` genuinely narrows a value space, and no verifier can encode it, so a proposal on such a
    # column returns UNKNOWN and the authority could never be acted on. An implementation built from
    # the pre-2026-09-16 denylist reading ACCEPTS this vector, which is why the allowlist is
    # published in SPEC section 6.4.2 rather than described.
    unencodable = _with_authority(
        _base_predicate(),
        constraints={"columns": {"amount": "date"}},
        premise={"premise_format": PREMISE_FORMAT, "columns": {"amount": "date"}},
    )
    add(
        "reject-authority-from-a-type-no-verifier-can-encode",
        _statement(unencodable),
        expect_ok=False,
        expect_failures=["authority_is_entailed"],
    )

    # Fails closed on a key the format does not define. A permissive reader would ignore it and
    # reach REJECT anyway, by the wrong route, and could not tell an operator what is malformed.
    malformed_premise = _with_authority(
        _base_predicate(),
        constraints={"columns": {"amount": "int"}},
        premise={
            "premise_format": PREMISE_FORMAT,
            "columns": {"amount": "int"},
            "check_constraints": ["amount > 0"],
        },
    )
    add(
        "reject-premise-with-an-unrecognised-key",
        _statement(malformed_premise),
        expect_ok=False,
        expect_failures=["authority_is_entailed"],
    )

    # An unversioned premise has no agreed semantics. Accepting it would mean guessing at the
    # meaning of the very document that exists to remove guessing.
    unversioned_premise = _with_authority(
        _base_predicate(),
        constraints={"columns": {"amount": "int"}},
        premise={"columns": {"amount": "int"}},
    )
    add(
        "reject-premise-without-a-recognised-format",
        _statement(unversioned_premise),
        expect_ok=False,
        expect_failures=["authority_is_entailed"],
    )

    consensus = _base_predicate()
    consensus["fixes"] = [
        {
            "row": 0,
            "column": "city",
            "detector_id": "entity_consensus",
            "provenance": "entity_consensus",
            "verification_strength": "proven",
        }
    ]
    add(
        "reject-entity-consensus-claimed-proven",
        _statement(consensus),
        expect_ok=False,
        expect_failures=["strength_is_earned"],
    )

    downgraded = _with_authority(_base_predicate(), constraints={"columns": {"amount": "int"}})
    downgraded["fixes"][0]["provenance"] = "llm_live"
    downgraded["fixes"][0]["verification_strength"] = "plausibility_only"
    add(
        "reject-honest-downgrade-must-not-be-upgraded",
        _statement(downgraded),
        expect_ok=False,
        expect_failures=["strength_is_earned"],
    )

    unknown_provenance = _base_predicate()
    unknown_provenance["fixes"][0]["provenance"] = "some_future_corrector"
    add(
        "reject-unknown-provenance",
        _statement(unknown_provenance),
        expect_ok=False,
        expect_failures=["strength_is_earned", "vocabulary_closed"],
    )

    missing_strength = _base_predicate()
    missing_strength["fixes"][0]["verification_strength"] = None
    add(
        "reject-missing-verification-strength",
        _statement(missing_strength),
        expect_ok=False,
        expect_failures=["vocabulary_closed"],
    )

    unknown_reason = _base_predicate()
    unknown_reason["held"] = [{"row": 1, "column": "amount", "review_reason": "because_i_said_so"}]
    add(
        "reject-unknown-review-reason",
        _statement(unknown_reason),
        expect_ok=False,
        expect_failures=["vocabulary_closed"],
    )

    bad_version = _base_predicate()
    bad_version["attestation_version"] = "2"
    add(
        "reject-unrecognised-version",
        _statement(bad_version),
        expect_ok=False,
        expect_failures=["version_recognised"],
    )

    wrong_predicate = _statement(_base_predicate())
    wrong_predicate["predicateType"] = "https://example.com/SomethingElse/v1"
    add(
        "reject-unrecognised-predicate-type",
        wrong_predicate,
        expect_ok=False,
        expect_failures=["envelope_recognised"],
    )

    wrong_statement_type = _statement(_base_predicate())
    wrong_statement_type["_type"] = "https://in-toto.io/Statement/v0.1"
    add(
        # `envelope_recognised` tests TWO conditions and only `predicateType` had a vector, so
        # mutating the `_type` comparison to a constant survived the whole suite. Found by
        # scripts/ci/mutate_attestation.py on its first run, 2026-09-16. A check with a failure
        # vector is not the same as a check whose every condition has one.
        "reject-unrecognised-statement-type",
        wrong_statement_type,
        expect_ok=False,
        expect_failures=["envelope_recognised"],
    )

    no_version = _base_predicate()
    del no_version["tool"]["version"]
    add(
        "reject-missing-tool-version",
        _statement(no_version),
        expect_ok=False,
        expect_failures=["schema_complete"],
    )

    add(
        "reject-subject-digest-mismatch",
        _statement(_base_predicate(), subject_digest="9" * 64),
        expect_ok=False,
        expect_failures=["subject_matches_post_state"],
    )

    no_revert = _base_predicate()
    no_revert["revert_command"] = None
    add(
        "reject-applied-without-revert-command",
        _statement(no_revert),
        expect_ok=False,
        expect_failures=["reversibility_complete"],
    )

    rejected_verdict = _base_predicate()
    rejected_verdict["verdicts"]["verifier"] = "reject"
    add(
        "reject-verifier-rejected",
        _statement(rejected_verdict),
        expect_ok=False,
        expect_failures=["verdicts_accepting"],
    )

    # Signed vectors. The signature check is verified only when a key is supplied, so the
    # unsigned-report path is a vector too.
    key = Ed25519PrivateKey.from_private_bytes(TEST_SEED)
    signed = sign_attestation(_statement(_base_predicate()), private_key=key)
    add("valid-signed", copy.deepcopy(signed), expect_ok=True, expect_failures=[])

    tampered = copy.deepcopy(signed)
    payload = json.loads(base64.b64decode(tampered["payload"]))
    payload["predicate"]["applied"] = False
    tampered["payload"] = base64.b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    add(
        "reject-tampered-signed-payload",
        tampered,
        expect_ok=False,
        expect_failures=["signature"],
    )

    # in-toto v1 permits N subjects, and until 2026-08-29 both verifiers read subject[0] and
    # ignored the rest. These three vectors fix the resulting semantics in the format rather
    # than in one implementation's behaviour.
    duplicated = _statement(_base_predicate())
    duplicated["subject"] = [
        {"name": "data.csv", "digest": {"sha256": POST_DIGEST}},
        {"name": "copy.csv", "digest": {"sha256": POST_DIGEST}},
    ]
    add(
        "accept-multiple-subjects-naming-the-same-artifact",
        duplicated,
        expect_ok=True,
        expect_failures=[],
    )

    smuggled = _statement(_base_predicate())
    smuggled["subject"] = [
        {"name": "data.csv", "digest": {"sha256": POST_DIGEST}},
        {"name": "payload.csv", "digest": {"sha256": "f" * 64}},
    ]
    add(
        # The attack the subject[0] read allowed: take a valid attestation, append a subject
        # naming a file nobody attested, and a verifier that checks only the first subject
        # reports `verified` for a statement that now asserts something about that file too.
        "reject-extra-subject-naming-a-different-artifact",
        smuggled,
        expect_ok=False,
        expect_failures=["subject_matches_post_state"],
    )

    smuggled_first = _statement(_base_predicate())
    smuggled_first["subject"] = [
        {"name": "payload.csv", "digest": {"sha256": "f" * 64}},
        {"name": "data.csv", "digest": {"sha256": POST_DIGEST}},
    ]
    add(
        # Order must not decide the verdict. A verifier that searched for ANY matching
        # subject instead of requiring all of them would accept this, which is the same hole
        # reached from the other side.
        "reject-foreign-subject-listed-first",
        smuggled_first,
        expect_ok=False,
        expect_failures=["subject_matches_post_state"],
    )

    # Entailment witnesses. These vectors are the reason the witness exists: a witness states
    # arithmetic facts that can CONTRADICT EACH OTHER, so a wrong claim is catchable without
    # re-running the labelling rule that produced it. `strength_is_earned` cannot express any
    # of the four rejections below, because it re-derives strength with the same function the
    # engine used to stamp it.
    def _witnessed(witness: dict[str, Any]) -> dict[str, Any]:
        predicate = _base_predicate()
        predicate["fixes"][0]["witness"] = witness
        return _statement(predicate)

    coherent_witness: dict[str, Any] = {
        "constraint": "state -> city",
        "constraint_kind": "functional_dependency",
        "determinant_columns": ["state"],
        "determinant_digests": ["a" * 16],
        "group_size": 10,
        "value_digests": [["b" * 16, 9], ["c" * 16, 1]],
        "truncated": False,
        "support": 9,
        "old_value_digest": "c" * 16,
        "new_value_digest": "b" * 16,
    }

    add(
        "accept-coherent-entailment-witness",
        _witnessed(copy.deepcopy(coherent_witness)),
        expect_ok=True,
        expect_failures=[],
    )

    plurality = copy.deepcopy(coherent_witness)
    plurality.update(
        {
            "group_size": 5,
            "support": 2,
            "value_digests": [["b" * 16, 2], ["c" * 16, 1], ["d" * 16, 1], ["e" * 16, 1]],
        }
    )
    add(
        # The decisive one. Two votes of five across four distinct values is a PLURALITY, and
        # the shipped rule is a strict majority -- mutant M16 measures the difference at
        # 731 corrupted clean cells against 344 on flights. This fix carries `deterministic`
        # provenance and `proven` strength, so every other check in the suite accepts it.
        # Only the witness's own arithmetic contradicts it.
        "reject-witness-without-a-strict-majority",
        _witnessed(plurality),
        expect_ok=False,
        expect_failures=["witness_is_coherent"],
    )

    overcounted = copy.deepcopy(coherent_witness)
    overcounted["support"] = 11
    add(
        "reject-witness-whose-support-exceeds-its-group",
        _witnessed(overcounted),
        expect_ok=False,
        expect_failures=["witness_is_coherent"],
    )

    mismatched = copy.deepcopy(coherent_witness)
    mismatched["new_value_digest"] = "f" * 16
    add(
        # The written value is not in its own group's distribution, so the witness does not
        # support the write it accompanies.
        "reject-witness-whose-written-value-is-absent-from-its-group",
        _witnessed(mismatched),
        expect_ok=False,
        expect_failures=["witness_is_coherent"],
    )

    short_counts = copy.deepcopy(coherent_witness)
    short_counts["value_digests"] = [["b" * 16, 9]]
    add(
        # Counts summing below group_size while `truncated` is false hides rows. Truncation is
        # legitimate and must be declared; silently omitting values is how a minority the
        # write destroys disappears from the evidence.
        "reject-witness-with-undeclared-truncation",
        _witnessed(short_counts),
        expect_ok=False,
        expect_failures=["witness_is_coherent"],
    )

    # `data_identity` -- the only check that binds an attestation to actual bytes, and the only
    # one that had no vector at all until 2026-09-16. Both vectors below carry the bytes inline,
    # so the digest is real rather than the `b` * 64 placeholder every other vector uses.
    identity = _base_predicate()
    identity["post"] = {"digest": {"sha256": DATA_DIGEST}}
    add(
        "valid-data-identity-with-matching-bytes",
        _statement(copy.deepcopy(identity), subject_digest=DATA_DIGEST),
        expect_ok=True,
        expect_failures=[],
        data_b64=base64.b64encode(DATA_BYTES).decode("ascii"),
    )
    add(
        # The attack this forecloses: a well-formed, internally consistent, correctly signed
        # attestation presented alongside a DIFFERENT file. Every other check passes; only the
        # digest of the bytes in hand can tell.
        "reject-data-identity-mismatched-bytes",
        _statement(copy.deepcopy(identity), subject_digest=DATA_DIGEST),
        expect_ok=False,
        expect_failures=["data_identity"],
        data_b64=base64.b64encode(DATA_BYTES + b"2,200\n").decode("ascii"),
    )

    # A signature made by a key that is not the one the verifier is given. Distinct from
    # `reject-tampered-signed-payload`: there the payload changed and the key was right, here the
    # payload is untouched and the SIGNER is wrong. Section 9 has required this since 2026-08-13.
    wrong_key = Ed25519PrivateKey.from_private_bytes(WRONG_SEED)
    add(
        "reject-signature-from-a-different-key",
        sign_attestation(_statement(_base_predicate()), private_key=wrong_key),
        expect_ok=False,
        expect_failures=["signature"],
    )

    return vectors


def render() -> str:
    payload = {
        "format": "dataforge.repair.attestation/v1",
        "note": (
            "Conformance vectors. Every implementation must reach the recorded verdict for "
            "every vector. Signed vectors use the fixed test key below, which is a test "
            "fixture and not a trust root."
        ),
        "test_public_key_hex": Ed25519PrivateKey.from_private_bytes(TEST_SEED)
        .public_key()
        .public_bytes_raw()
        .hex(),
        "vectors": build_vectors(),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()

    target = VECTOR_DIR / "vectors.json"
    rendered = render()

    if args.write:
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"wrote {target.relative_to(PROJECT_ROOT)} ({len(build_vectors())} vectors)")
        return 0

    if not target.exists():
        print(f"MISSING: {target.relative_to(PROJECT_ROOT)}")
        return 1
    if target.read_text(encoding="utf-8") != rendered:
        print(f"STALE: {target.relative_to(PROJECT_ROOT)} does not match the generator.")
        return 1
    print(f"Attestation vectors are current ({len(build_vectors())} vectors).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
