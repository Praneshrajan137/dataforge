"""Authority must correspond to enforcement: a declaration that cannot reject confers nothing.

Verified as a LIVE defect on 2026-09-14, end-to-end with real writes to disk and a real
change of table shape.

``authoritative_columns`` granted write authority for TEN ``Schema`` constraint kinds while
``SMTVerifier`` and ``DirectVerifier`` enforce SIX. A premise whose only statement about a
column was a ``relationships`` or ``aggregate_dependencies`` declaration therefore made an
untrusted value ``proven`` -- with nothing anywhere able to reject it.

Three properties made it serious, and they are the same three that made the 2026-08-09 and
2026-08-25 instances serious:

* It needed no unusual flags. ``verify_and_apply`` ships as a CLI command and an MCP tool.
* ``dataforge/integrations/dbt.py`` maps dbt's built-in ``relationships`` test onto the
  field, so importing a dbt manifest reaches it without doing anything unusual. This is the
  realistic path, not the adversarial one.
* The receipt said ``proven``. That is a truthfulness violation rather than merely an
  unproven write, and truthfulness is this project's core product claim.

Measured, by adding ONE field to the permissive premise and changing nothing else
(``eval/results/trust_ledger_adversarial.json``, ``docs/trust/authority-enforcement-correspondence.md``):
0 writes became **11**, with **10 of 14** discriminable attacks corrupted -- exactly the
pre-2026-08-25 ``str`` figure -- and one applied injection took the table from 6 rows to 7.

**Why N-version diversity could not catch it.** Both verifiers are written from the same
``Schema`` specification and both omit the same kinds, so both returned ACCEPT and
``require_independent_agreement`` read their agreement as verification. Diversity cannot
detect a constraint kind absent from the specification the implementations share. That is
``PRODUCT.md`` section 1.3's "two mutually-consistent wrong artifacts reading as
verification", one level deeper than the prose-versus-gate case it was written about.

**What this module gates.** Not the fix -- ``test_column_scoped_authority.py`` covers
behaviour. This gates the *population*: that the authority/enforcement partition is TOTAL
over ``Schema``'s own fields, so a new constraint kind fails a test instead of silently
joining either side. ``PRODUCT.md`` section 1.3: "Derive the population a gate polices;
never restate it." The previous implementation was a hand-written run of ``covered |=``
statements, and a hand-written union cannot be compared against anything.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

from dataforge.domain.vocabulary import (
    ENFORCEABLE_CONSTRAINT_KINDS,
    UNENFORCEABLE_CONSTRAINT_KINDS,
    constraint_kind_confers_authority,
)
from dataforge.engine.repair import (
    authoritative_columns,
    columns_named_by_constraint_kind,
)
from dataforge.verifier import direct as direct_module
from dataforge.verifier import smt as smt_module
from dataforge.verifier.schema import (
    AcceptedValues,
    AggregateDependency,
    DomainBound,
    FunctionalDependency,
    RegexConstraint,
    RelationshipConstraint,
    Schema,
)


def _schema_field_names() -> frozenset[str]:
    """Every declared field of ``Schema``, derived rather than restated."""
    return frozenset(field.name for field in dataclasses.fields(Schema))


class TestThePartitionIsTotal:
    """Every ``Schema`` field must be classified, so a new one cannot slip in unclassified."""

    def test_partition_covers_every_schema_field(self) -> None:
        classified = ENFORCEABLE_CONSTRAINT_KINDS | frozenset(UNENFORCEABLE_CONSTRAINT_KINDS)
        unclassified = _schema_field_names() - classified

        assert unclassified == frozenset(), (
            f"Schema field(s) {sorted(unclassified)} are classified neither enforceable nor "
            "unenforceable. Add each to ENFORCEABLE_CONSTRAINT_KINDS if a verifier can reject "
            "on it, or to UNENFORCEABLE_CONSTRAINT_KINDS with the reason it cannot. Leaving a "
            "field out is how relationships and aggregate_dependencies conferred proof for "
            "months on a value nothing could check."
        )

    def test_partition_names_no_field_that_does_not_exist(self) -> None:
        """A stale entry is as bad as a missing one: it reads as coverage of nothing."""
        classified = ENFORCEABLE_CONSTRAINT_KINDS | frozenset(UNENFORCEABLE_CONSTRAINT_KINDS)
        phantom = classified - _schema_field_names()

        assert phantom == frozenset(), f"classified but not a Schema field: {sorted(phantom)}"

    def test_the_two_halves_are_disjoint(self) -> None:
        overlap = ENFORCEABLE_CONSTRAINT_KINDS & frozenset(UNENFORCEABLE_CONSTRAINT_KINDS)

        assert overlap == frozenset(), (
            f"{sorted(overlap)} is both enforceable and not; the partition is incoherent"
        )

    def test_the_coverage_map_is_also_total(self) -> None:
        """``columns_named_by_constraint_kind`` must speak about every field too.

        A partition that is total while the map it drives is not would silently drop a kind
        from consideration -- failing safe, but invisibly, and invisible is what this whole
        class of defect is made of.
        """
        mapped = frozenset(columns_named_by_constraint_kind(Schema()))

        assert mapped == _schema_field_names(), (
            "columns_named_by_constraint_kind does not name every Schema field. "
            f"missing: {sorted(_schema_field_names() - mapped)}; "
            f"extra: {sorted(mapped - _schema_field_names())}"
        )

    def test_every_unenforceable_kind_states_a_reason(self) -> None:
        """An exemption without a reason is an exemption nobody can review."""
        for kind, reason in UNENFORCEABLE_CONSTRAINT_KINDS.items():
            assert len(reason.strip()) >= 80, f"{kind} has no substantive reason recorded"


class TestEnforceabilityMatchesTheVerifiers:
    """The enforceable set must match what the verifiers actually branch on.

    This is the check that did not exist. Both verifiers are derived by hand from ``Schema``,
    and nothing compared either against the authority rule, so all three drifted apart in
    silence.

    Read via AST rather than by executing the verifiers, because the question is *which
    constraint kinds does this source consult* -- a structural property. A behavioural probe
    would need a crafted violation per kind and would answer a narrower question.
    """

    @staticmethod
    def _attributes_read(module_path: Path) -> frozenset[str]:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        return frozenset(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))

    @pytest.mark.parametrize("module", [smt_module, direct_module])
    def test_each_verifier_consults_every_enforceable_kind(self, module: object) -> None:
        source = Path(inspect.getfile(module))  # type: ignore[arg-type]
        attributes = self._attributes_read(source)

        # `columns` is consulted through `column_type()`/`_normalize_type`, not by field name.
        expected = ENFORCEABLE_CONSTRAINT_KINDS - {"columns"}
        # Both verifiers reach `accepted_values` etc. through the `_for(column)` accessors.
        consulted = attributes | {name.removesuffix("_for") for name in attributes}
        missing = {kind for kind in expected if kind not in consulted}

        assert missing == set(), (
            f"{source.name} never reads {sorted(missing)}, yet declaring one confers write "
            "authority. Either add the check to this verifier or move the kind to "
            "UNENFORCEABLE_CONSTRAINT_KINDS."
        )

    @pytest.mark.parametrize("module", [smt_module, direct_module])
    def test_no_verifier_pretends_to_check_an_unenforceable_kind(self, module: object) -> None:
        """The inverse direction, which is what makes this gate falsifiable.

        If a verifier DOES learn to check referential integrity, this test fails and forces
        the kind to be promoted rather than left unauthoritative by an out-of-date exemption.
        An exemption that outlives its reason is a silent loss of capability.
        """
        source = Path(inspect.getfile(module))  # type: ignore[arg-type]
        attributes = self._attributes_read(source)
        consulted = attributes | {name.removesuffix("_for") for name in attributes}

        promoted = {
            kind
            for kind in UNENFORCEABLE_CONSTRAINT_KINDS
            if kind in consulted and kind != "pii_columns"
        }

        assert promoted == set(), (
            f"{source.name} now reads {sorted(promoted)}, which is listed as unenforceable. If "
            "this verifier can genuinely reject on it, move it to "
            "ENFORCEABLE_CONSTRAINT_KINDS and re-measure the adversarial corpus."
        )


class TestUnenforceableKindsConferNoAuthority:
    """The behavioural consequence, per kind, on a column with nothing else said about it."""

    _CASES = {
        "relationships": Schema(
            relationships=(
                RelationshipConstraint(column="city", reference="ref", reference_column="name"),
            )
        ),
        "aggregate_dependencies": Schema(
            aggregate_dependencies=(
                AggregateDependency(
                    source_column="city", aggregate="sum", target_column="city_total"
                ),
            )
        ),
        "pii_columns": Schema(pii_columns=frozenset({"city"})),
    }

    @pytest.mark.parametrize("kind", sorted(_CASES))
    def test_declaring_only_this_kind_covers_nothing(self, kind: str) -> None:
        assert authoritative_columns(self._CASES[kind]) == frozenset(), (
            f"declaring {kind} alone conferred authority. Measured consequence of exactly this: "
            "11 writes and 10 of 14 corruptions on the adversarial corpus, and a table that "
            "went from 6 rows to 7"
        )

    @pytest.mark.parametrize("kind", sorted(UNENFORCEABLE_CONSTRAINT_KINDS))
    def test_the_predicate_refuses_it(self, kind: str) -> None:
        assert not constraint_kind_confers_authority(kind)

    def test_an_unrecognised_kind_fails_closed(self) -> None:
        """The opposite direction from ``type_discriminates``, and deliberately so."""
        assert not constraint_kind_confers_authority("some_future_constraint")


class TestEnforceableKindsStillConferAuthority:
    """Non-vacuity. The rule removes free authority, not the ability to declare authority.

    Without this, the whole change is satisfiable by making ``authoritative_columns`` return
    the empty set -- which would pass every assertion above and destroy the product.
    """

    _CASES = {
        "columns": (Schema(columns={"city": "int"}), {"city"}),
        "not_null_columns": (Schema(not_null_columns=frozenset({"city"})), {"city"}),
        "primary_key_columns": (Schema(primary_key_columns=frozenset({"city"})), {"city"}),
        "unique_columns": (Schema(unique_columns=frozenset({"city"})), {"city"}),
        "accepted_values": (
            Schema(accepted_values=(AcceptedValues(column="city", values=("boston",)),)),
            {"city"},
        ),
        "regex_constraints": (
            Schema(regex_constraints=(RegexConstraint(column="city", pattern="^b"),)),
            {"city"},
        ),
        "domain_bounds": (
            Schema(domain_bounds=(DomainBound(column="city", min_value=0.0),)),
            {"city"},
        ),
        "functional_dependencies": (
            Schema(
                functional_dependencies=(
                    FunctionalDependency(determinant=("zip",), dependent="city"),
                )
            ),
            {"zip", "city"},
        ),
    }

    @pytest.mark.parametrize("kind", sorted(_CASES))
    def test_declaring_this_kind_confers_authority(self, kind: str) -> None:
        schema, expected = self._CASES[kind]

        assert authoritative_columns(schema) == frozenset(expected), (
            f"{kind} stopped conferring authority. The enforceability rule is too strict and "
            "has destroyed the verification-layer feature rather than corrected it. Do not "
            "relax this assertion; revert the rule"
        )

    def test_every_enforceable_kind_has_a_non_vacuity_case(self) -> None:
        """So adding a kind to the enforceable set cannot skip its own evidence."""
        assert frozenset(self._CASES) == ENFORCEABLE_CONSTRAINT_KINDS

    def test_an_unenforceable_kind_does_not_dilute_a_real_one(self) -> None:
        """A mixed premise keeps the authority it earned and gains none it did not."""
        schema = Schema(
            columns={"zip": "int"},
            relationships=(
                RelationshipConstraint(column="city", reference="ref", reference_column="name"),
            ),
            pii_columns=frozenset({"state"}),
        )

        assert authoritative_columns(schema) == frozenset({"zip"})
