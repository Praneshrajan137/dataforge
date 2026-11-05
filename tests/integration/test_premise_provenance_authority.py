"""C4: write authority follows a constraint's provenance, not the miner's confidence.

The change under test is one line at the authority source in `run_repair_pipeline`:
`covered_columns` is derived from the DECLARED schema, not from the declared schema merged
with candidates a human accepted in `dataforge constraints review`.

Why this needed its own test file, stated plainly: **the entire existing suite passed
unchanged when C4 was switched on by default.** That is not evidence the change is safe; it
is evidence that nothing in the suite exercised the mined-premise write path. A change that
no test can see is indistinguishable from no change, which is the defect class this
repository keeps finding. These tests make C4 observable in both directions.

The evidence behind the default is in `docs/trust/premise-acquisition-result.md`: across ten
externally annotated tables, the best of four in-table measures discards 16 of 143
hand-annotated true dependencies when its threshold is carried to a table it was not fitted
on. A confidence floor cannot fix a premise, because the statistic a floor reads does not
carry the signal.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dataforge.engine.repair import RepairPipelineRequest, run_repair_pipeline
from dataforge.schema_inference import (
    ConstraintCandidate,
    ConstraintReviewArtifact,
    ReviewedConstraintCandidate,
)

# Four rows sharing determinant "10001". Three say Springfield, one says Shelbyville, so a
# miner sees an approximate dependency zip -> city and the majority repair rewrites row 4.
_CSV = """zip,city
10001,Springfield
10001,Springfield
10001,Springfield
10001,Shelbyville
"""


def _accepted_fd_artifact(source: Path) -> ConstraintReviewArtifact:
    """A review artifact in which a human accepted a MINED functional dependency.

    This is the shipped zero-config premise: `profile` mines candidates,
    `constraints review --accept` records the decision, `repair` consumes it.
    """
    reviewed = ReviewedConstraintCandidate(
        candidate_id="cnd-0123456789abcdef",
        decision="accepted",
        candidate=ConstraintCandidate(
            kind="functional_dependency",
            columns=("zip",),
            dependent="city",
            confidence=0.75,
            evidence="3 of 4 rows agree on the dependent value for determinant 10001",
        ),
    )
    return ConstraintReviewArtifact(
        source_path=str(source),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        row_count=4,
        candidates=[reviewed],
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "cities.csv"
    path.write_text(_CSV, encoding="utf-8")
    return path


class TestC4ChangesBehaviour:
    """Both directions, because a one-directional test cannot show a gate fires."""

    def test_a_mined_premise_does_not_authorise_a_write_by_default(self, source: Path) -> None:
        original = source.read_bytes()

        result = run_repair_pipeline(
            RepairPipelineRequest(
                source_path=source,
                mode="apply",
                constraints=_accepted_fd_artifact(source),
            )
        )

        assert source.read_bytes() == original, (
            "a constraint mined from the table and accepted in review must not, by itself, "
            "authorise rewriting a cell"
        )
        assert result.fixes == [], "no fix may be applied from a mined premise alone"

    def test_restoring_mined_authority_restores_the_write(self, source: Path) -> None:
        """The opt-in must actually opt in, or the default is untestable."""
        original = source.read_bytes()

        run_repair_pipeline(
            RepairPipelineRequest(
                source_path=source,
                mode="apply",
                constraints=_accepted_fd_artifact(source),
                mined_constraints_grant_write_authority=True,
            )
        )

        assert source.read_bytes() != original, (
            "with mined authority restored this write happened before 2026-09-07; if it no "
            "longer does, the default is not what is being measured"
        )

    def test_the_hold_is_reported_with_an_honest_reason(self, source: Path) -> None:
        """`floor_cannot_verify` would be a lie here: a schema exists.

        The fix was refused because the covering constraint was mined rather than declared,
        and the receipt has to say that. A misleading reason attached to a correct refusal is
        still a truthfulness defect, and PRODUCT.md's doctrine treats it as one.
        """
        result = run_repair_pipeline(
            RepairPipelineRequest(
                source_path=source,
                mode="dry_run",
                constraints=_accepted_fd_artifact(source),
            )
        )

        reasons = {
            candidate.review_reason
            for candidate in result.receipt.suggested_fixes
            if candidate.review_reason is not None
        }
        assert "mined_constraint_not_declared" in reasons, (
            f"expected the mined-premise hold to be named; got {sorted(reasons)}"
        )
        assert "floor_cannot_verify" not in reasons, (
            "'no authoritative schema' is false here -- one exists, the constraint was "
            "merely not declared"
        )


class TestC4LeavesTheDeclaredArmAlone:
    """K2 in the pre-registration: if the declared premise moves, C4 is withdrawn."""

    def test_a_declared_dependency_still_authorises_the_write(self, source: Path) -> None:
        from dataforge.detectors.base import FunctionalDependency, Schema

        original = source.read_bytes()
        declared = Schema(
            columns={"zip": "str", "city": "str"},
            functional_dependencies=(FunctionalDependency(determinant=("zip",), dependent="city"),),
        )

        run_repair_pipeline(
            RepairPipelineRequest(source_path=source, mode="apply", schema=declared)
        )

        assert source.read_bytes() != original, (
            "C4 must not touch the declared path; the user stated this constraint"
        )

    def test_no_premise_at_all_still_writes_nothing(self, source: Path) -> None:
        original = source.read_bytes()

        run_repair_pipeline(RepairPipelineRequest(source_path=source, mode="apply"))

        assert source.read_bytes() == original


class TestMinedAuthorityAttestation:
    """When --trust-mined-constraints is active, the effective merged schema is attested."""

    def test_mined_authority_emits_verifiable_attestation(self, source: Path) -> None:
        from dataforge.attestation import verify_attestation
        from dataforge.cli.emit import attest_result

        result = run_repair_pipeline(
            RepairPipelineRequest(
                source_path=source,
                mode="apply",
                constraints=_accepted_fd_artifact(source),
                mined_constraints_grant_write_authority=True,
            )
        )
        assert result.receipt.applied is True
        assert result.receipt.authoritative_columns == ["city", "zip"]
        assert result.authority_schema is not None
        assert "authority_schema" not in result.model_dump()

        payload = attest_result(
            result,
            source_path=source,
            schema_path=None,
            mined_authority=True,
        )
        assert "attestation" in payload, payload.get("attestation_unavailable")
        statement = payload["attestation"]
        verification = verify_attestation(statement, data_bytes=source.read_bytes())
        assert verification.ok, [c.as_dict() for c in verification.failures]
        by_name = {c.name: c for c in verification.checks}
        assert by_name["authority_is_entailed"].ok is True
        assert by_name["witness_is_coherent"].ok is True
        assert by_name["witness_is_coherent"].skipped is False

    def test_mined_authority_without_effective_schema_fails_closed(self, source: Path) -> None:
        from dataforge.cli.emit import attest_result
        from dataforge.engine.repair import RepairPipelineResult

        result = run_repair_pipeline(
            RepairPipelineRequest(
                source_path=source,
                mode="apply",
                constraints=_accepted_fd_artifact(source),
                mined_constraints_grant_write_authority=True,
            )
        )
        stripped = RepairPipelineResult(
            receipt=result.receipt,
            issues=result.issues,
            fixes=result.fixes,
            failures=result.failures,
            transaction=result.transaction,
            authority_schema=None,
        )
        payload = attest_result(
            stripped,
            source_path=source,
            schema_path=None,
            mined_authority=True,
        )
        assert "attestation" not in payload
        assert "attestation_unavailable" in payload

    def test_schema_to_mapping_round_trips_every_field(self) -> None:
        from dataforge.cli.common import schema_from_mapping, schema_to_mapping
        from dataforge.verifier.schema import (
            AcceptedValues,
            AggregateDependency,
            DomainBound,
            FunctionalDependency,
            RegexConstraint,
            RelationshipConstraint,
            Schema,
        )

        schema = Schema(
            columns={"zip": "str", "city": "str", "amount": "float"},
            functional_dependencies=(FunctionalDependency(determinant=("zip",), dependent="city"),),
            pii_columns=frozenset({"zip"}),
            primary_key_columns=frozenset({"zip"}),
            not_null_columns=frozenset({"city"}),
            unique_columns=frozenset({"zip"}),
            accepted_values=(AcceptedValues(column="city", values=("Springfield", "Shelbyville")),),
            regex_constraints=(RegexConstraint(column="zip", pattern=r"^\d{5}$"),),
            relationships=(
                RelationshipConstraint(column="zip", reference="zips", reference_column="code"),
            ),
            domain_bounds=(
                DomainBound(
                    column="amount",
                    min_value=0.0,
                    max_value=100.0,
                    inclusive_min=True,
                    inclusive_max=False,
                ),
            ),
            aggregate_dependencies=(
                AggregateDependency(
                    source_column="amount",
                    aggregate="sum",
                    target_column="amount",
                    group_by=("zip",),
                ),
            ),
        )
        assert schema_from_mapping(schema_to_mapping(schema)) == schema
