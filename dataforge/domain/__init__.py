"""The domain layer: DataForge's ubiquitous language, defined once.

Only closed vocabularies and the pure predicates over them live here. This package
imports nothing but the standard library so that every surface -- including the
dependency-free certificate verifier and the rich-free MCP package -- can depend on
the real vocabulary instead of copying it.
"""

from __future__ import annotations

from dataforge.domain.vocabulary import (
    ALL_PROVENANCE,
    NEXT_ACTION_HUMAN,
    NEXT_ACTIONS,
    OUTCOME_CODE_HUMAN,
    OUTCOME_CODES,
    REVIEW_REASON_HUMAN,
    REVIEW_REASONS,
    RUNG_ORDER,
    TRUSTED_PROVENANCE,
    UNTRUSTED_PROVENANCE,
    NextAction,
    OutcomeCode,
    Provenance,
    ReviewReason,
    Rung,
    Severity,
    VerificationStrength,
    is_trusted_provenance,
    rung_for,
    verification_strength_for,
)

__all__ = [
    "ALL_PROVENANCE",
    "NEXT_ACTIONS",
    "NEXT_ACTION_HUMAN",
    "NextAction",
    "OUTCOME_CODES",
    "OUTCOME_CODE_HUMAN",
    "OutcomeCode",
    "REVIEW_REASONS",
    "REVIEW_REASON_HUMAN",
    "RUNG_ORDER",
    "TRUSTED_PROVENANCE",
    "UNTRUSTED_PROVENANCE",
    "Provenance",
    "ReviewReason",
    "Rung",
    "Severity",
    "VerificationStrength",
    "is_trusted_provenance",
    "rung_for",
    "verification_strength_for",
]
