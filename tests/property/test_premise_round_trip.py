"""The premise wire format must reproduce the object it was given, or it is not a projection.

Why property-based rather than example-based: the format's whole job is to let a third party
recompute `authoritative_columns` from published data. If any `Schema` field fails to round-trip,
that column silently drops out of the recomputation, and the check built on top of it would report
agreement while the published premise understated the real authority basis. That is the same defect
shape as granting authority for a constraint kind no verifier enforces -- a gap between what the
engine acts on and what the artifact says.

Examples cannot cover an eleven-field product type with six nested rule collections. These
strategies generate all eleven.

The attestation suite deliberately stays example-based, because its vectors are a cross-language
artifact and a hypothesis counterexample cannot be handed to the TypeScript verifier. This file is
the exception because it tests a pure Python projection, not the protocol.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dataforge.domain.premise import (
    PREMISE_FORMAT,
    PREMISE_SET_FIELDS,
    PREMISE_TABLE_FIELDS,
    PremiseFormatError,
    authoritative_columns,
    premise_from_canonical,
    premise_to_canonical,
)
from dataforge.verifier.schema import (
    AcceptedValues,
    AggregateDependency,
    DomainBound,
    FunctionalDependency,
    RegexConstraint,
    RelationshipConstraint,
    Schema,
)

# Column names are drawn from a small pool so generated schemas actually overlap -- a premise whose
# every rule names a different column would never exercise the union in `authoritative_columns`.
_COLUMNS = st.sampled_from(["id", "city", "state", "zip", "score", "amount"])

# Includes both discriminating and non-discriminating spellings, plus one the verifiers cannot
# encode, so `type_discriminates` is exercised in all three directions.
_TYPES = st.sampled_from(["int", "integer", "float", "decimal", "real", "str", "string", "date"])

_VALUES = st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=4).map(tuple)


@st.composite
def _schemas(draw: st.DrawFn) -> Schema:
    """A Schema with every one of the eleven fields independently populated or empty."""
    columns = draw(st.dictionaries(_COLUMNS, _TYPES, max_size=4))

    def column_set() -> frozenset[str]:
        return frozenset(draw(st.lists(_COLUMNS, max_size=3)))

    return Schema(
        columns=columns,
        pii_columns=column_set(),
        primary_key_columns=column_set(),
        not_null_columns=column_set(),
        unique_columns=column_set(),
        functional_dependencies=tuple(
            draw(
                st.lists(
                    st.builds(
                        FunctionalDependency,
                        determinant=st.lists(_COLUMNS, min_size=1, max_size=2).map(tuple),
                        dependent=_COLUMNS,
                    ),
                    max_size=2,
                )
            )
        ),
        accepted_values=tuple(
            draw(
                st.lists(
                    st.builds(AcceptedValues, column=_COLUMNS, values=_VALUES),
                    max_size=2,
                )
            )
        ),
        regex_constraints=tuple(
            draw(
                st.lists(
                    st.builds(
                        RegexConstraint, column=_COLUMNS, pattern=st.text(min_size=1, max_size=8)
                    ),
                    max_size=2,
                )
            )
        ),
        relationships=tuple(
            draw(
                st.lists(
                    st.builds(
                        RelationshipConstraint,
                        column=_COLUMNS,
                        reference=st.text(min_size=1, max_size=6),
                        reference_column=_COLUMNS,
                    ),
                    max_size=2,
                )
            )
        ),
        domain_bounds=tuple(
            draw(
                st.lists(
                    st.builds(
                        DomainBound,
                        column=_COLUMNS,
                        min_value=st.one_of(
                            st.none(),
                            st.floats(
                                min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
                            ),
                        ),
                        max_value=st.one_of(
                            st.none(),
                            st.floats(
                                min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
                            ),
                        ),
                        inclusive_min=st.booleans(),
                        inclusive_max=st.booleans(),
                    ),
                    max_size=2,
                )
            )
        ),
        aggregate_dependencies=tuple(
            draw(
                st.lists(
                    st.builds(
                        AggregateDependency,
                        source_column=_COLUMNS,
                        target_column=_COLUMNS,
                        aggregate=st.sampled_from(["sum", "avg"]),
                        group_by=st.lists(_COLUMNS, max_size=2).map(tuple),
                    ),
                    max_size=2,
                )
            )
        ),
    )


class TestRoundTrip:
    """P1: every field survives the projection."""

    @settings(max_examples=200, deadline=None)
    @given(schema=_schemas())
    def test_the_projection_reproduces_the_schema(self, schema: Schema) -> None:
        """The whole claim: what comes back is what went in.

        Equality here is pydantic dataclass equality, which compares the rule tuples POSITIONALLY.
        So this also asserts that the format preserves rule order -- it does not sort them, because a
        format that reorders its input cannot reproduce it.
        """
        assert premise_from_canonical(premise_to_canonical(schema)) == schema

    @settings(max_examples=200, deadline=None)
    @given(schema=_schemas())
    def test_the_projection_is_json_native(self, schema: Schema) -> None:
        """A premise that cannot be serialised cannot be published.

        `frozenset` and `tuple` are not JSON types, and four Schema fields are the former and six
        the latter. This is the assertion that the conversion actually happened.
        """
        canonical = premise_to_canonical(schema)
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        assert json.loads(encoded) == canonical

    @settings(max_examples=200, deadline=None)
    @given(schema=_schemas())
    def test_the_projection_is_deterministic(self, schema: Schema) -> None:
        """The same Schema must digest identically, or `constraints_digest` means nothing."""
        first = json.dumps(premise_to_canonical(schema), sort_keys=True)
        second = json.dumps(premise_to_canonical(schema), sort_keys=True)
        assert first == second

    @settings(max_examples=200, deadline=None)
    @given(schema=_schemas())
    def test_authority_survives_the_round_trip(self, schema: Schema) -> None:
        """The property the normative check actually depends on.

        Even if equality above were ever relaxed, THIS must hold: a third party recomputing
        authority from the published premise must reach the set the engine reached. If it does not,
        the check reports disagreement on a correct attestation.
        """
        recovered = premise_from_canonical(premise_to_canonical(schema))
        assert authoritative_columns(recovered) == authoritative_columns(schema)

    @settings(max_examples=100, deadline=None)
    @given(schema=_schemas())
    def test_empty_fields_are_omitted_not_emitted(self, schema: Schema) -> None:
        """A premise declaring only column types is exactly {premise_format, columns}."""
        canonical = premise_to_canonical(schema)
        for key, value in canonical.items():
            assert value or key == "premise_format", f"{key} was emitted empty"


class TestFailsClosed:
    """K5: an unrecognised premise is a refusal, never a best-effort parse."""

    def test_a_missing_format_is_refused(self) -> None:
        with pytest.raises(PremiseFormatError, match="premise_format"):
            premise_from_canonical({"columns": {"amount": "int"}})

    def test_an_unrecognised_format_is_refused(self) -> None:
        with pytest.raises(PremiseFormatError, match="premise_format"):
            premise_from_canonical({"premise_format": "something/v9", "columns": {}})

    def test_an_unknown_top_level_key_is_refused(self) -> None:
        """The one that matters most: an ignored key could be a constraint the reader cannot see."""
        with pytest.raises(PremiseFormatError, match="unknown key"):
            premise_from_canonical({"premise_format": PREMISE_FORMAT, "check_constraints": ["x>0"]})

    def test_an_unknown_rule_attribute_is_refused(self) -> None:
        with pytest.raises(PremiseFormatError, match="unknown key"):
            premise_from_canonical(
                {
                    "premise_format": PREMISE_FORMAT,
                    "accepted_values": [{"column": "state", "values": ["il"], "nullable": True}],
                }
            )

    def test_a_wrong_container_shape_is_refused(self) -> None:
        """`schema_from_mapping` accepts a dict here. This format accepts exactly one shape."""
        with pytest.raises(PremiseFormatError, match="must be an array"):
            premise_from_canonical(
                {"premise_format": PREMISE_FORMAT, "accepted_values": {"state": ["il"]}}
            )

    def test_a_set_field_given_a_string_is_refused(self) -> None:
        """A bare string is a Sequence, so this is the case a naive isinstance check would pass."""
        with pytest.raises(PremiseFormatError, match="array of strings"):
            premise_from_canonical({"premise_format": PREMISE_FORMAT, "not_null_columns": "id"})

    def test_a_rule_violating_its_own_constraint_is_refused(self) -> None:
        """`AcceptedValues.values` has min_length=1; an empty enumeration constrains nothing."""
        with pytest.raises(PremiseFormatError, match="not a valid"):
            premise_from_canonical(
                {
                    "premise_format": PREMISE_FORMAT,
                    "accepted_values": [{"column": "state", "values": []}],
                }
            )

    def test_a_non_finite_bound_cannot_be_published(self) -> None:
        """JSON has no NaN. Refusing beats emitting a bound no reader can parse."""
        schema = Schema(domain_bounds=(DomainBound(column="score", min_value=float("inf")),))
        with pytest.raises(PremiseFormatError, match="JSON cannot represent"):
            premise_to_canonical(schema)

    def test_a_non_object_premise_is_refused(self) -> None:
        with pytest.raises(PremiseFormatError, match="must be an object"):
            premise_from_canonical(["not", "an", "object"])


class TestTotality:
    """The DO-178C shape: enumerate the artifact, name the remainder, refuse on the unnameable."""

    def test_every_schema_field_is_projected(self) -> None:
        """Importing the module already asserts this; this states it as a test so it is visible.

        `dataforge/domain/premise.py` raises at import time if a Schema field is unprojected, so a
        new constraint kind cannot be added without either projecting it or removing it. This test
        exists so the guarantee is documented where a reader looks for it.
        """
        import dataclasses

        projected = {"columns", *PREMISE_SET_FIELDS, *PREMISE_TABLE_FIELDS}
        declared = {field.name for field in dataclasses.fields(Schema)}
        assert projected == declared, (
            "the premise format and Schema have diverged. A field Schema has but the format lacks "
            "would confer authority in-process while the published premise understated it."
        )

    def test_the_existing_attestation_vector_premise_is_valid(self) -> None:
        """The payload the committed vectors carry must parse under the strict format.

        `{"columns": {"amount": "int"}}` is what `_with_authority` embeds, claiming authority over
        `["amount"]`. If this ever stops entailing exactly that column, the vectors are wrong rather
        than the check.
        """
        premise = {"premise_format": PREMISE_FORMAT, "columns": {"amount": "int"}}
        assert authoritative_columns(premise_from_canonical(premise)) == frozenset({"amount"})

    def test_a_non_discriminating_type_confers_nothing(self) -> None:
        """P6, as a unit: `str` is encodable but constrains nothing, so it grants no authority."""
        premise = {"premise_format": PREMISE_FORMAT, "columns": {"amount": "str"}}
        assert authoritative_columns(premise_from_canonical(premise)) == frozenset()

    def test_an_unencodable_type_confers_nothing(self) -> None:
        """The Axis-2 fix, now externally checkable: no verifier can encode `date`."""
        premise = {"premise_format": PREMISE_FORMAT, "columns": {"amount": "date"}}
        assert authoritative_columns(premise_from_canonical(premise)) == frozenset()
