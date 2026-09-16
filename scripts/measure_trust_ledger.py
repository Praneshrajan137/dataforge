"""Measure the Trust Ledger over the adversarial corpus, under two schema premises.

This produces the committed artifact behind the project's outcome claims. It exists because
every prior number described a detector's agreement with a label set; none described what a
run does to a user's data.

The two-premise design is the finding. Both schemas cover every column, so the gate reports
every write as ``proven`` under both. The difference in measured corruption is attributable
entirely to how much the premise actually constrains -- turning
``docs/trust/authority-is-mutable.md``'s prose ("covering a column is not the same as
constraining the value") into a number.

Usage:
    python scripts/measure_trust_ledger.py            # print
    python scripts/measure_trust_ledger.py --write    # commit the artifact
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dataforge.detectors.base import Schema  # noqa: E402
from dataforge.engine.repair import VerifyAndApplyRequest, verify_and_apply  # noqa: E402
from dataforge.metrics import TrustLedger  # noqa: E402
from tests.adversarial.corpus import (  # noqa: E402
    ACCEPTED_VALUES_ONLY_SCHEMA,
    DDL_TYPICAL_SCHEMA,
    NON_ENCODABLE_TYPE_SCHEMA,
    NOT_NULL_ONLY_SCHEMA,
    PERMISSIVE_SCHEMA,
    PRIMARY_KEY_ONLY_SCHEMA,
    TIGHT_SCHEMA,
    UNENFORCEABLE_AGGREGATE_SCHEMA,
    UNENFORCEABLE_RELATIONSHIP_SCHEMA,
    UNIQUE_ONLY_SCHEMA,
    build_corpus,
    truth,
    write_table,
)

ARTIFACT = PROJECT_ROOT / "eval" / "results" / "trust_ledger_adversarial.json"


def _poke(source: Path, row: int, column: str, value: str) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    index = header.index(column)
    cells = lines[row + 1].split(",")
    cells[index] = value
    lines[row + 1] = ",".join(cells)
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _truth_or_none(row: int, column: str) -> str | None:
    try:
        return truth(row, column)
    except (IndexError, ValueError):
        return None


def measure(schema: Schema, label: str, *, only: str = "all") -> tuple[TrustLedger, dict[str, Any]]:
    """Run attacks individually and build a ledger from the outcomes.

    ``only`` selects the subset, and the subsets are NOT interchangeable:

    * ``discriminable`` -- attacks the stated constraints can reject. This is the gate's
      responsibility, and the only subset where a corruption is a defect.
    * ``undecidable`` -- attacks that satisfy every declared constraint and are merely
      false. These are written by design; the guarantee covering them is reversibility.
    * ``all`` -- both. Reported for completeness, but a corruption RATE over ``all`` is
      close to meaningless here: 16 of 17 proposals are hostile, so the rate measures the
      corpus's malice rather than any property of a workload. It is recorded with that
      warning rather than omitted, because omitting it would invite someone to recompute it
      later without the warning.
    """
    corpus = [
        attack
        for attack in build_corpus()
        if only == "all"
        or (only == "discriminable" and attack.discriminable)
        or (only == "undecidable" and not attack.discriminable)
    ]
    applied = 0
    corrections = 0
    corruptions = 0
    held = 0
    corrupting: list[str] = []
    wrongly_blocked: list[str] = []
    reversible = True

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "readings.csv"
        for attack in corpus:
            write_table(source)
            if attack.pre_corrupt is not None:
                row, column, wrong = attack.pre_corrupt
                _poke(source, row, column, wrong)

            result = verify_and_apply(
                VerifyAndApplyRequest(
                    source_path=source,
                    fixes=[attack.fix],
                    mode="apply",
                    schema=schema,
                    confirm_escalations=True,
                    proposer="adversarial-corpus",
                )
            )
            receipt = result.receipt
            if receipt.applied_fixes:
                applied += len(receipt.applied_fixes)
                if not receipt.reversible:
                    reversible = False
                for fix in receipt.applied_fixes:
                    expected = _truth_or_none(fix.row, fix.column)
                    if expected is None or fix.new_value != expected:
                        corruptions += 1
                        corrupting.append(attack.name)
                    else:
                        corrections += 1
            else:
                held += 1
                if attack.is_correct_proposal:
                    wrongly_blocked.append(attack.name)

    # Real errors present: one, introduced by the single legitimate attack's pre_corrupt.
    real_errors = sum(1 for attack in corpus if attack.pre_corrupt is not None)

    ledger = TrustLedger(
        cells_applied=applied,
        corrections=corrections,
        corruptions=corruptions,
        cells_held=held,
        cells_abstained=0,
        real_errors=real_errors,
        reversibility_verified=reversible,
    )
    detail = {
        "premise": label,
        "subset": only,
        "attacks": len(corpus),
        "corrupting_attacks": sorted(set(corrupting)),
        # Recorded from 2026-09-16, because zero corruptions is not a safety result and the
        # corruption count alone cannot tell SAFE from INERT. `permissive` and both
        # `unenforceable_*` arms all write zero; so would a premise that rejects everything.
        # The corpus carries exactly one legitimate proposal, and whether an arm keeps it is
        # the field that separates the two readings.
        "wrongly_blocked": sorted(set(wrongly_blocked)),
    }
    return ledger, detail


#: Arms that existed before the unenforceable-premise measurement was added. K1 in
#: ``eval/preregistration/authority_enforcement_correspondence.md`` binds the new arms to these:
#: if extending the harness moved an existing arm, the harness is what changed and no new number
#: may be reported until that is explained.
_PRE_EXISTING_ARMS: Final = ("tight", "permissive")


def _instrument_falsification_errors(results: dict[str, dict[str, Any]]) -> list[str]:
    """Return the ways this run disagrees with the committed artifact on the OLD arms.

    Bound to the artifact, never to a constant written in prose. A documented constant is
    exactly what rotted undetected for 54 days on the hospital anchor, which is why
    ``scripts/ci/anchor_truth.py`` exists; the same reasoning applies here.

    A missing artifact is not a pass. It returns a single error, because "there was nothing
    to check against" and "it checked out" must not read the same.
    """
    if not ARTIFACT.exists():
        return [f"{ARTIFACT.name} is absent, so the existing arms could not be reproduced."]

    committed = json.loads(ARTIFACT.read_text(encoding="utf-8")).get("premises", {})
    errors: list[str] = []
    for premise in _PRE_EXISTING_ARMS:
        if premise not in committed:
            errors.append(f"committed artifact has no {premise!r} premise to reproduce.")
            continue
        for subset, committed_record in committed[premise].items():
            fresh = results.get(premise, {}).get(subset)
            if fresh is None:
                errors.append(f"{premise}/{subset} was not measured in this run.")
                continue
            for key, was in sorted(committed_record.items()):
                now = fresh.get(key)
                if now != was:
                    errors.append(f"{premise}/{subset}.{key}: committed {was!r}, measured {now!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="commit the artifact")
    args = parser.parse_args()

    premises = {
        "tight": (TIGHT_SCHEMA, "tight (typed, bounded, patterned, enumerated)"),
        "permissive": (PERMISSIVE_SCHEMA, "permissive (every column declared str)"),
        # Each is `permissive` plus exactly one added field, so the delta against
        # `permissive` is attributable to that field alone. Both name every column in a
        # constraint kind `authoritative_columns` counts as authority and neither verifier
        # can reject on. See eval/preregistration/authority_enforcement_correspondence.md.
        "unenforceable_relationship": (
            UNENFORCEABLE_RELATIONSHIP_SCHEMA,
            "unenforceable (permissive + a relationship on every column)",
        ),
        "unenforceable_aggregate": (
            UNENFORCEABLE_AGGREGATE_SCHEMA,
            "unenforceable (permissive + an aggregate dependency on every column)",
        ),
        # Added 2026-09-16. The four arms above answer "can any verifier check this kind?".
        # These answer the question nobody had asked: HOW MUCH can each checkable kind
        # reject? `authoritative_columns` confers identical authority for all eight
        # enforceable kinds, and `TIGHT_SCHEMA`'s 0-of-14 is a bundle of four of them, so it
        # attributes strength to none of its members. A dbt manifest or a database's DDL
        # supplies a characteristic SUBSET -- and three of the kinds they supply are absent
        # from the tight bundle. See eval/preregistration/per_kind_authority.md.
        "not_null_only": (
            NOT_NULL_ONLY_SCHEMA,
            "one kind (permissive + not_null on every column)",
        ),
        "primary_key_only": (
            PRIMARY_KEY_ONLY_SCHEMA,
            "one kind (permissive + primary_key on every column)",
        ),
        "unique_only": (
            UNIQUE_ONLY_SCHEMA,
            "one kind (permissive + unique on every column)",
        ),
        "accepted_values_only": (
            ACCEPTED_VALUES_ONLY_SCHEMA,
            "one kind (permissive + accepted_values on every column)",
        ),
        "ddl_typical": (
            DDL_TYPICAL_SCHEMA,
            "what a DDL importer emits (not_null + a primary key + no discriminating types)",
        ),
        # Axis 2, added 2026-09-16: a type that confers authority and that no verifier can encode.
        # Measured on BOTH sides of the denylist-to-derived-set change, per K9.
        "non_encodable_type_only": (
            NON_ENCODABLE_TYPE_SCHEMA,
            "one uncheckable type (permissive + every column declared `date`)",
        ),
    }
    subsets = ("discriminable", "undecidable", "all")

    results: dict[str, dict[str, Any]] = {}
    for premise_name, (schema, label) in premises.items():
        results[premise_name] = {}
        print(f"\n=== {premise_name} premise: {label} ===")
        for subset in subsets:
            ledger, detail = measure(schema, label, only=subset)
            results[premise_name][subset] = {**detail, **ledger.as_dict()}
            print(f"\n  [{subset}] n={detail['attacks']}")
            for line in ledger.summary_lines():
                print(f"    {line}")
            if detail["corrupting_attacks"]:
                print(f"    written despite being wrong: {detail['corrupting_attacks']}")

    # The headline is generated rather than written, so it cannot drift from the numbers. It now
    # reports BOTH corruptions and writes, because after 2026-08-25 the corruption counts alone no
    # longer distinguish the premises -- both are zero -- and a sentence quoting only corruptions
    # would read as "the premise does not matter", which is the opposite of the finding.
    headline = (
        "Under a tight premise, "
        f"{results['tight']['discriminable']['corruptions']} of "
        f"{results['tight']['discriminable']['attacks']} constraint-violating attacks were "
        f"written, and {results['tight']['discriminable']['cells_applied']} cell(s) applied in "
        "total. Under a premise that declares every column str and therefore constrains nothing, "
        f"{results['permissive']['discriminable']['corruptions']} of "
        f"{results['permissive']['discriminable']['attacks']} were written, and "
        f"{results['permissive']['discriminable']['cells_applied']} cell(s) applied in total. The "
        "gate is identical in both runs; only the premise differs. Until 2026-08-25 the permissive "
        "premise wrote 10 of 14, because declaring a column str counted as authority over it; "
        "requiring a premise to discriminate before it confers proof "
        "(dataforge.domain.vocabulary.type_discriminates) took that to zero while leaving the "
        "tight premise's one legitimate repair intact. The premise still decides the outcome -- it "
        "now decides whether anything may be written at all, rather than whether corruption occurs."
    )

    # Generated, not written, for the same reason as the headline above: a sentence about a
    # correspondence defect must not be able to drift from the numbers that establish it. Phrased
    # in the past tense on purpose -- the defect is CLOSED, and a present-tense description of a
    # fixed defect is exactly the kind of stale claim this repository keeps finding.
    _relationship = results["unenforceable_relationship"]["discriminable"]
    _aggregate = results["unenforceable_aggregate"]["discriminable"]
    _permissive = results["permissive"]["discriminable"]
    _tight = results["tight"]["discriminable"]
    correspondence = (
        "Until 2026-09-14 authoritative_columns granted write authority for ten Schema "
        "constraint kinds while the SMT and Direct verifiers enforced six, so declaring a "
        "relationship or an aggregate dependency made an untrusted value `proven` with nothing "
        "able to reject it. Each premise here is the permissive premise plus exactly one added "
        "field, so the delta is attributable to that field alone. Measured before the fix, "
        "adding a relationship on every column took the premise from 0 writes to 11, corrupting "
        f"10 of {_permissive['attacks']}, and one applied injection was recorded as taking the "
        "table from 6 rows to 7; the aggregate premise was identical at 11 and 10. That "
        "reproduced the pre-2026-08-25 `str` figure exactly, so requiring a declared TYPE to "
        "discriminate had closed one door and left an equivalent one open. Both verifiers "
        "ACCEPTED in every case, so they agreed -- N-version diversity cannot catch a constraint "
        "kind absent from the specification both implementations share, and "
        "require_independent_agreement reads agreement as verification. After the fix the "
        f"unenforceable premises write {_relationship['cells_applied']} and "
        f"{_aggregate['cells_applied']} cells and corrupt {_relationship['corruptions']} and "
        f"{_aggregate['corruptions']}, collapsing onto the permissive premise's "
        f"{_permissive['cells_applied']}, while the tight premise keeps its "
        f"{_tight['cells_applied']} legitimate repair at {_tight['corruptions']} corruptions. "
        "The authority/enforcement partition is now asserted total against Schema's own fields "
        "by tests/unit/test_authority_enforcement_correspondence.py. CORRECTION 2026-09-16: the "
        "row-count clause above reports a PHYSICAL LINE count from an assertion that called "
        "splitlines() the table shape. A quoted CSV field may legally contain a newline, and "
        "the same attack measured with a CSV reader leaves the parsed row count and every "
        "per-row field count unchanged. It was a value corruption, not a structural one; "
        "whether the original was structural cannot be reproduced, because the unenforceable "
        "arms now write zero. See eval/preregistration/per_kind_authority.md amendment 1."
    )

    # Generated for the same reason as the two strings above. This one answers a question the
    # bundle-versus-permissive comparison cannot: eight kinds confer IDENTICAL authority, so how
    # much can each one actually reject? See eval/preregistration/per_kind_authority.md.
    _not_null = results["not_null_only"]["discriminable"]
    _unique = results["unique_only"]["discriminable"]
    _accepted = results["accepted_values_only"]["discriminable"]
    _primary_key = results["primary_key_only"]["discriminable"]
    _ddl = results["ddl_typical"]["discriminable"]
    per_kind = (
        "The tight premise's zero is a BUNDLE result -- discriminating types, accepted_values, "
        "regex_constraints and domain_bounds together -- so it attributes strength to none of "
        "its members. Measured one kind at a time against the same "
        f"{_permissive['attacks']} attacks, with the same gate: accepted_values alone corrupts "
        f"{_accepted['corruptions']} and keeps its {_accepted['corrections']} legitimate repair, "
        f"reproducing the whole bundle by itself; not_null alone corrupts "
        f"{_not_null['corruptions']}; unique alone corrupts {_unique['corruptions']}, matching "
        "the retired `str` premise's 10 exactly by a third independent route. So the bar for "
        "conferring authority -- can this reject a value at all -- is met by declarations whose "
        "measured power differs by a factor of ten. primary_key alone corrupts "
        f"{_primary_key['corruptions']}, but it is INERT rather than strong: "
        f"{_primary_key['wrongly_blocked']} is blocked too, because "
        "dataforge/safety/constitution.py refuses any edit to a declared key column before the "
        "verifier runs. The product consequence is ddl_typical, which is what a DDL importer "
        f"emits for a typical production table: it corrupts {_ddl['corruptions']} of "
        f"{_ddl['attacks']}. not_null is on roughly 56% of real columns and unique is one of "
        "dbt's four generic tests, so an importer treating either as an authority source would "
        "mass-produce the defect removed on 2026-08-25."
    )

    payload = {
        "measurement": "trust_ledger_adversarial",
        "headline": headline,
        "correspondence": correspondence,
        "per_kind_authority": per_kind,
        "note": (
            "Trust Ledger over the adversarial corpus, under nine schema premises and split "
            "by subset. 'discriminable' attacks violate a declared constraint and are the "
            "gate's responsibility. 'undecidable' attacks satisfy every declared constraint "
            "and are merely false; no verifier can reject them without ground truth, so "
            "they are written by design and the guarantee covering them is reversibility, "
            "not correctness."
        ),
        "rate_warning": (
            "Do NOT read the 'all' subset's corruption rate as a workload metric. This is "
            "an attack corpus: 16 of 17 proposals are hostile by construction, so that rate "
            "measures the corpus, not any real distribution of proposals."
        ),
        "reproduce": "python scripts/measure_trust_ledger.py",
        "premises": results,
    }

    print(f"\nHEADLINE: {headline}")

    # K1: the new arms are reported only if the old ones reproduce. Checked before --write and
    # before the correspondence headline is trusted, so a harness that has drifted cannot
    # publish a finding about someone else's drift.
    falsifications = _instrument_falsification_errors(results)
    if falsifications:
        print("\nINSTRUMENT FALSIFIED (K1). Reporting nothing; fix the harness first:")
        for error in falsifications:
            print(f"  - {error}")
        return 1
    print(
        "\nK1 satisfied: the pre-existing "
        f"{'/'.join(_PRE_EXISTING_ARMS)} arms reproduce the committed artifact field-for-field."
    )
    print(f"\nCORRESPONDENCE: {correspondence}")
    print(f"\nPER-KIND AUTHORITY: {per_kind}")

    if args.write:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nwrote {ARTIFACT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
