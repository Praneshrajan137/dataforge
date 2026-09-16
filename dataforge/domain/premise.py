"""The premise wire format: how a declared schema is published so a third party can check it.

Why this module exists, dated 2026-09-16.

An attestation's `authority` block carries `authoritative_columns` -- the set of columns the engine
claims write authority over -- and that list is the load-bearing claim in the whole certificate,
because `strength_is_earned` derives every fix's strength from membership in it. Until this module
existed, the list was **unbound to the premise it came from**:

* `authority.constraints` was the operator's `--schema` YAML re-read from disk, or, via
  ``attest build --constraints``, an arbitrary JSON file. Neither was a projection of the parsed
  ``Schema`` that ``authoritative_columns`` was actually computed from.
* The only check that mentioned it, ``constraints_present``, asserted
  ``isinstance(constraints, Mapping) and bool(constraints)`` -- non-emptiness -- while its detail
  string claimed the constraints "support the schema-proven writes".
* ``constraints_digest`` was computed over the payload sitting beside it and verified by nobody: it
  appeared three times in ``dataforge/attestation/__init__.py``, all inside ``build_attestation``,
  and zero times in either the TypeScript or the three clean-room Java verifiers.

So a producer could emit any ``authoritative_columns`` beside any ``constraints`` payload and pass
all twelve normative checks. The thesis says a third party can verify *without trusting DataForge*;
at the premise layer they could only read our own claim back to themselves.

**What makes the claim checkable is that it is a pure function of the premise.**
:func:`authoritative_columns` takes a ``Schema`` and two fixed allowlists. Publish the premise in a
form that round-trips, publish the rule in the specification, and any implementation can recompute
the set and compare. That is arithmetic on published data rather than trust.

Why the rule lives *here* and not in ``dataforge/engine/repair.py``, where it used to:
``dataforge/attestation/__init__.py`` imports nothing from this package except
``dataforge.domain.vocabulary``. The verifier is deliberately decoupled from the repair engine, so a
third party running the normative tier does not drag in the repairer. Moving the rule into the domain
layer is what lets the verifier apply it. The alternative -- a second implementation of the rule next
to the verifier -- is the hand-maintained-duplicate defect this repository has recorded four times.

**One shape per field, and anything else is a refusal.** ``dataforge/cli/common.py``'s
``schema_from_mapping`` accepts two different shapes for ``accepted_values`` and
``regex_constraints``, renames ``min``/``max`` to ``min_value``/``max_value``, and silently
``continue``s past malformed input at seven separate sites. That is fine for a convenience loader
reading a file a human wrote. It is not fine for a normative wire format: a third party cannot be
asked to reproduce silent discards, and a premise whose shape is unrecognised must not be allowed to
confer authority by default. Everything here fails closed.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from dataforge.domain.vocabulary import constraint_kind_confers_authority, type_discriminates
from dataforge.verifier.schema import (
    AcceptedValues,
    AggregateDependency,
    DomainBound,
    FunctionalDependency,
    RegexConstraint,
    RelationshipConstraint,
    Schema,
)

__all__ = [
    "PREMISE_FORMAT",
    "PREMISE_SET_FIELDS",
    "PREMISE_TABLE_FIELDS",
    "PremiseFormatError",
    "authoritative_columns",
    "authoritative_columns_from_premise",
    "columns_named_by_constraint_kind",
    "conferring_kinds",
    "premise_from_canonical",
    "premise_to_canonical",
]

#: The wire format's identity, carried inside every published premise.
#:
#: Required, and an unrecognised value is a refusal rather than a best-effort parse. A premise whose
#: format nobody has agreed on cannot be the basis of a claim that a third party checks -- the
#: reader would be guessing at the semantics of the very document that is supposed to remove guessing.
PREMISE_FORMAT: Final[str] = "dataforge.premise/v1"

_FORMAT_KEY: Final[str] = "premise_format"

#: ``Schema`` fields holding an unordered set of column names. Projected as a **sorted list**,
#: because a set has no order and sorting is the only canonical representation of one.
PREMISE_SET_FIELDS: Final[tuple[str, ...]] = (
    "pii_columns",
    "primary_key_columns",
    "not_null_columns",
    "unique_columns",
)

#: ``Schema`` fields holding an ordered tuple of structured rules, and the type of one rule.
#:
#: Projected as a list **in the schema's own order**, not sorted. Sorting would make two
#: semantically equal premises digest identically, which is superficially attractive, but it would
#: also mean ``premise_from_canonical(premise_to_canonical(s)) != s`` for any schema whose rules were
#: not already in sorted order -- and a format that cannot reproduce the object it was given is not a
#: faithful projection. The authority rule unions across rules, so order affects no verdict; the only
#: cost is that reordering the same rules changes the digest, which is a property of the object and
#: not a defect in the format.
PREMISE_TABLE_FIELDS: Final[dict[str, type]] = {
    "functional_dependencies": FunctionalDependency,
    "accepted_values": AcceptedValues,
    "regex_constraints": RegexConstraint,
    "relationships": RelationshipConstraint,
    "domain_bounds": DomainBound,
    "aggregate_dependencies": AggregateDependency,
}

#: The one field that is neither a set of names nor a table of rules.
_MAPPING_FIELD: Final[str] = "columns"


class PremiseFormatError(ValueError):
    """A published premise could not be read, so no authority may be derived from it.

    Raised rather than returning a partial ``Schema``. A premise that is half-understood would
    confer authority over whichever columns happened to parse, which is the failure mode the whole
    module is built to prevent.
    """


def _projected_fields() -> frozenset[str]:
    """Every ``Schema`` field this format knows how to project.

    Derived from the three tables above so the totality assertion below has something to compare
    against. A hand-written list here could not be checked, which is the shape of the defect
    recorded four times in ``PRODUCT.md`` section 1.3.
    """
    return frozenset({_MAPPING_FIELD, *PREMISE_SET_FIELDS, *PREMISE_TABLE_FIELDS})


def _schema_fields() -> frozenset[str]:
    return frozenset(field.name for field in dataclasses.fields(Schema))


_UNPROJECTED_SCHEMA_FIELDS: Final[frozenset[str]] = _schema_fields() - _projected_fields()
if _UNPROJECTED_SCHEMA_FIELDS:  # pragma: no cover - import-time refusal
    raise PremiseFormatError(
        f"Schema fields {sorted(_UNPROJECTED_SCHEMA_FIELDS)} are not projected by "
        f"{PREMISE_FORMAT}. A field the wire format cannot express could still confer write "
        "authority in-process, so the published premise would understate the authority basis -- "
        "the same defect as granting authority for a constraint kind no verifier enforces. Project "
        "it, or remove it from Schema."
    )

_UNKNOWN_PROJECTED_FIELDS: Final[frozenset[str]] = _projected_fields() - _schema_fields()
if _UNKNOWN_PROJECTED_FIELDS:  # pragma: no cover - import-time refusal
    raise PremiseFormatError(
        f"{PREMISE_FORMAT} projects {sorted(_UNKNOWN_PROJECTED_FIELDS)}, which are not Schema "
        "fields. The projection would publish a constraint the engine never reads."
    )


def _finite(value: float, *, where: str) -> float:
    if not math.isfinite(value):
        raise PremiseFormatError(
            f"{where} is {value!r}, which JSON cannot represent. A non-finite bound cannot be "
            "published, so it cannot be part of a checkable premise."
        )
    return value


def _rule_to_canonical(rule: object) -> dict[str, Any]:
    """Project one constraint rule, converting tuples to lists and validating floats."""
    projected: dict[str, Any] = {}
    for field in dataclasses.fields(rule):  # type: ignore[arg-type]
        value = getattr(rule, field.name)
        if isinstance(value, tuple):
            projected[field.name] = list(value)
        elif isinstance(value, float):
            projected[field.name] = _finite(value, where=f"{type(rule).__name__}.{field.name}")
        else:
            projected[field.name] = value
    return projected


def premise_to_canonical(schema: Schema) -> dict[str, Any]:
    """Project a ``Schema`` into the published, JSON-native premise format.

    Deterministic: the same ``Schema`` always yields byte-identical JSON under sorted-key encoding.
    Empty fields are **omitted** rather than emitted as empty containers, which keeps a small premise
    small and means a premise declaring only column types is exactly
    ``{"premise_format": ..., "columns": {...}}``.

    Lossless: :func:`premise_from_canonical` reconstructs an equal ``Schema`` from the result, for
    every ``Schema`` that can be published at all. The one case that cannot is a non-finite
    ``DomainBound``, which raises rather than being silently dropped.
    """
    canonical: dict[str, Any] = {_FORMAT_KEY: PREMISE_FORMAT}

    if schema.columns:
        canonical[_MAPPING_FIELD] = {str(k): str(v) for k, v in sorted(schema.columns.items())}

    for field_name in PREMISE_SET_FIELDS:
        members = getattr(schema, field_name)
        if members:
            canonical[field_name] = sorted(str(member) for member in members)

    for field_name in PREMISE_TABLE_FIELDS:
        rules = getattr(schema, field_name)
        if rules:
            canonical[field_name] = [_rule_to_canonical(rule) for rule in rules]

    return canonical


def _require_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PremiseFormatError(f"{where} must be an object, got {type(value).__name__}")
    return value


def _require_str_list(value: object, *, where: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PremiseFormatError(
            f"{where} must be an array of strings, got {type(value).__name__}. The convenience "
            "loader accepts other shapes; this format does not, because a reader cannot be asked "
            "to guess."
        )
    for entry in value:
        if not isinstance(entry, str):
            raise PremiseFormatError(f"{where} contains a non-string entry {entry!r}")
    return list(value)


def _rule_from_canonical(payload: object, rule_type: type, *, where: str) -> Any:
    """Reconstruct one rule, refusing an unknown or missing key rather than defaulting."""
    mapping = _require_mapping(payload, where=where)
    expected = {field.name for field in dataclasses.fields(rule_type)}
    unknown = sorted(set(mapping) - expected)
    if unknown:
        raise PremiseFormatError(
            f"{where} has unknown key(s) {unknown}. A premise carrying a constraint attribute this "
            "format does not define cannot be checked, so it is refused rather than ignored."
        )
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(rule_type):
        if field.name not in mapping:
            continue
        value = mapping[field.name]
        if isinstance(value, list):
            kwargs[field.name] = tuple(value)
        else:
            kwargs[field.name] = value
    try:
        return rule_type(**kwargs)
    except (TypeError, ValueError) as error:
        raise PremiseFormatError(f"{where} is not a valid {rule_type.__name__}: {error}") from error


def premise_from_canonical(payload: object) -> Schema:
    """Reconstruct a ``Schema`` from a published premise, or refuse.

    The exact inverse of :func:`premise_to_canonical`. Every failure mode is a
    :class:`PremiseFormatError`: an absent or unrecognised ``premise_format``, an unknown top-level
    key, a wrong container shape, an unknown rule attribute, or a rule that violates its own
    constraints. Nothing is skipped, because skipping is how a premise would confer authority through
    a channel the format cannot express.
    """
    mapping = _require_mapping(payload, where="premise")

    declared_format = mapping.get(_FORMAT_KEY)
    if declared_format != PREMISE_FORMAT:
        raise PremiseFormatError(
            f"premise_format is {declared_format!r}, expected {PREMISE_FORMAT!r}. An unversioned or "
            "unrecognised premise has no agreed semantics, so no authority may be derived from it."
        )

    unknown = sorted(set(mapping) - _projected_fields() - {_FORMAT_KEY})
    if unknown:
        raise PremiseFormatError(
            f"premise has unknown key(s) {unknown}. Refused rather than ignored: an ignored key "
            "could be a constraint the producer believes confers authority and the reader cannot see."
        )

    kwargs: dict[str, Any] = {}

    if _MAPPING_FIELD in mapping:
        columns = _require_mapping(mapping[_MAPPING_FIELD], where="premise.columns")
        for column, declared in columns.items():
            if not isinstance(declared, str):
                raise PremiseFormatError(
                    f"premise.columns[{column!r}] must be a string type name, got "
                    f"{type(declared).__name__}"
                )
        kwargs[_MAPPING_FIELD] = dict(columns)

    for field_name in PREMISE_SET_FIELDS:
        if field_name in mapping:
            kwargs[field_name] = frozenset(
                _require_str_list(mapping[field_name], where=f"premise.{field_name}")
            )

    for field_name, rule_type in PREMISE_TABLE_FIELDS.items():
        if field_name not in mapping:
            continue
        raw = mapping[field_name]
        if isinstance(raw, str) or not isinstance(raw, Sequence):
            raise PremiseFormatError(
                f"premise.{field_name} must be an array of objects, got {type(raw).__name__}"
            )
        kwargs[field_name] = tuple(
            _rule_from_canonical(entry, rule_type, where=f"premise.{field_name}[{index}]")
            for index, entry in enumerate(raw)
        )

    try:
        return Schema(**kwargs)
    except (TypeError, ValueError) as error:
        raise PremiseFormatError(f"premise is not a valid Schema: {error}") from error


def columns_named_by_constraint_kind(schema: Schema) -> dict[str, frozenset[str]]:
    """Map every ``Schema`` constraint kind to the columns it names.

    Keyed by ``Schema`` field name so the mapping can be checked for TOTALITY against
    ``dataclasses.fields(Schema)``. That check is the point: the previous implementation was a
    hand-written run of ``covered |=`` statements, and a hand-written union cannot be compared
    against anything. A new constraint kind now fails
    ``tests/unit/test_authority_enforcement_correspondence.py`` rather than either silently
    joining the authority set or silently staying out of it.

    Naming a column is not the same as constraining it, which is why this function only
    reports what each kind *names*; :func:`authoritative_columns` decides which of those
    kinds may confer authority.

    Moved here from ``dataforge/engine/repair.py`` on 2026-09-16 so the attestation verifier can
    apply the rule without importing the repair engine. There is still exactly one implementation.
    """
    named: dict[str, frozenset[str]] = {
        "columns": frozenset(
            column for column, declared in schema.columns.items() if type_discriminates(declared)
        ),
        "pii_columns": frozenset(schema.pii_columns),
        "primary_key_columns": frozenset(schema.primary_key_columns),
        "not_null_columns": frozenset(schema.not_null_columns),
        "unique_columns": frozenset(schema.unique_columns),
        "accepted_values": frozenset(rule.column for rule in schema.accepted_values),
        "regex_constraints": frozenset(rule.column for rule in schema.regex_constraints),
        "domain_bounds": frozenset(bound.column for bound in schema.domain_bounds),
        "relationships": frozenset(rule.column for rule in schema.relationships),
        "aggregate_dependencies": frozenset(
            column
            for dependency in schema.aggregate_dependencies
            for column in (dependency.source_column, dependency.target_column)
        ),
        # A value in either position is checked by the FD, so both sides are named. This is a
        # deliberate widening of `entailment_strength.md`'s specification, which names only the
        # dependent; it is sound because the determinant is genuinely checked.
        "functional_dependencies": frozenset(
            column
            for fd in schema.functional_dependencies
            for column in (*fd.determinant, fd.dependent)
        ),
    }
    return named


def conferring_kinds(schema: Schema) -> dict[str, frozenset[str]]:
    """Return only the kinds that confer authority, and the columns each confers it over.

    The per-kind view that ``authoritative_columns`` discards. Measured on 2026-09-16, the eight
    conferring kinds differ by a factor of ten in what they can actually reject -- declared alone,
    ``accepted_values`` admits 0 of 14 adversarial writes and ``unique_columns`` admits 10
    (``docs/trust/per-kind-authority.md``). A reader who can see WHICH kind conferred authority can
    weigh that; a reader handed a flat list of column names cannot. This is what puts the kind into
    the attestation's check detail without adding a forgeable field to the document.
    """
    return {
        kind: columns
        for kind, columns in columns_named_by_constraint_kind(schema).items()
        if columns and constraint_kind_confers_authority(kind)
    }


def authoritative_columns(schema: Schema | None) -> frozenset[str]:
    """Return the columns an authoritative schema actually constrains.

    ``authoritative_schema_present`` used to be a table-level boolean, and that was a
    real defect, verified end-to-end on 2026-08-09: accepting ONE inferred
    ``column_type`` candidate on column ``id`` produced an effective schema of
    ``{"id": "int"}`` with no other constraints, which flipped an ``external`` garbage
    fix on the UNRELATED column ``city`` from held to applied -- and stamped it
    ``proven`` in the certificate. Narrow evidence was granting blanket authority, and
    because ``external`` is not in ``_LLM_PROVENANCE`` it also bypassed the calibration
    threshold. That is a truthfulness violation, not merely an unproven write.

    Authority is therefore scoped to the columns the schema speaks about. A column counts
    as covered when the schema declares a **discriminating** type for it or names it in a
    constraint **a verifier can reject on**.

    **A declared type is not automatically a constraint.** Listing a column as ``str`` says
    nothing that can reject a value, and counting it as authority was the next instance of the
    same defect one level down. Measured on ``eval/results/trust_ledger_adversarial.json``:
    declaring every column ``str`` let **10 of 14** constraint-violating attacks be written and
    stamped ``proven``, against 0 of 14 under a premise that actually constrained. See
    :func:`~dataforge.domain.vocabulary.type_discriminates` and
    ``eval/preregistration/entailment_strength.md``.

    **And naming a column in an UNCHECKABLE constraint is not a constraint either** -- the
    third instance of the same defect, closed 2026-09-14. This function granted authority for
    ten constraint kinds while ``SMTVerifier`` and ``DirectVerifier`` enforce six, so a
    ``relationships`` or ``aggregate_dependencies`` declaration conferred ``proven`` on a value
    nothing could reject. Adding one relationship field to the permissive premise -- changing
    nothing else -- took it from 0 writes to **11 writes, 10 of 14 corrupted**, reproducing the
    pre-2026-08-25 ``str`` figure exactly. (An earlier version of this docstring added that one
    applied injection took the table from 6 rows to 7. That clause is **withdrawn**: it reported a
    physical line count from an assertion that called ``splitlines()`` the table shape, and a quoted
    CSV field may legally contain a newline. Measured with a CSV reader the parsed row count and
    every per-row field count are unchanged. See
    ``docs/trust/authority-enforcement-correspondence.md``.) Both verifiers ACCEPTED, so they
    agreed, and ``require_independent_agreement`` reads agreement as verification: N-version
    diversity cannot catch a constraint kind absent from the specification both implementations
    share. The authority/enforcement partition now lives in
    :data:`~dataforge.domain.vocabulary.ENFORCEABLE_CONSTRAINT_KINDS` and is asserted total
    against ``Schema``'s fields. See ``docs/trust/authority-enforcement-correspondence.md``.

    **This is the rule a third party recomputes.** It is published verbatim in
    ``specs/SPEC_repair_attestation.md`` and re-applied by the ``authority_is_entailed`` normative
    check, so the attestation's ``authoritative_columns`` is arithmetic a reader can verify rather
    than a claim a reader must accept.
    """
    if schema is None:
        return frozenset()
    named = columns_named_by_constraint_kind(schema)
    covered: set[str] = set()
    for kind, columns in named.items():
        if constraint_kind_confers_authority(kind):
            covered |= columns
    return frozenset(covered)


def authoritative_columns_from_premise(payload: object) -> frozenset[str]:
    """Recompute the authoritative column set from a published premise.

    The whole point of the module in one call: parse the premise strictly, then apply the same rule
    the engine applied. Raises :class:`PremiseFormatError` if the premise cannot be read, which the
    caller must treat as a failed check rather than an empty result -- an unreadable premise
    supporting a non-empty authority claim is exactly the case that must be rejected.
    """
    return authoritative_columns(premise_from_canonical(payload))
