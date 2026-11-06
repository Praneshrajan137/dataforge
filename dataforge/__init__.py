"""DataForge public package.

The root package is the stable facade for integration surfaces. Symbols are
resolved lazily so importing :mod:`dataforge` does not eagerly import pandas,
FastAPI-facing helpers, or the SMT stack.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dataforge.cli.common import load_schema, schema_from_mapping
    from dataforge.detectors import Issue, Schema, Severity, run_all_detectors
    from dataforge.engine.repair import (
        CandidateFix,
        CandidateRepair,
        ExternalFix,
        ProofObligation,
        RepairFailure,
        RepairPipelineRequest,
        RepairPipelineResult,
        RepairReceipt,
        RootCause,
        VerifiedFix,
        VerifyAndApplyRequest,
        run_repair_pipeline,
        verify_and_apply,
    )
    from dataforge.gazetteer import GazetteerConflictError, ReferenceGazetteer
    from dataforge.integrations.dbt import (
        authoritative_schema_from_dbt_artifacts,
        authoritative_schema_from_dbt_manifest,
        schema_from_dbt_artifacts,
        schema_from_dbt_manifest,
    )
    from dataforge.repair_contract import CONTRACT_VERSION
    from dataforge.repairers import ProposedFix
    from dataforge.safety import (
        ConservationReport,
        SafetyContext,
        SafetyFilter,
        SafetyResult,
        SafetyVerdict,
        check_table_conservation,
    )
    from dataforge.schema_inference import (
        ConstraintCandidate,
        ConstraintReviewArtifact,
        ConstraintReviewError,
        ReviewedConstraintCandidate,
        SchemaInferenceResult,
        build_constraint_review_artifact,
        dump_constraint_review_artifact,
        infer_schema,
        infer_verification_schema,
        load_constraint_review_artifact,
    )
    from dataforge.stores import (
        DuckDBStore,
        PatchPlan,
        TableStoreError,
        TableStoreRepairResult,
        is_table_store_uri,
        run_table_store_repair,
        store_from_uri,
    )
    from dataforge.table import read_csv
    from dataforge.transactions.log import (
        TransactionAuditReport,
        TransactionAuditVerdict,
        TransactionLogError,
        journal_head_sha256_for,
        verify_transaction_log,
    )
    from dataforge.transactions.revert import TransactionRevertError, revert_transaction
    from dataforge.transactions.txn import CellFix, RepairTransaction
    from dataforge.triage_clusters import (
        CausalCluster,
        ClusterCompressionReport,
        cluster_repairs,
    )
    from dataforge.verifier import (
        ConstraintIR,
        SMTVerifier,
        VerificationResult,
        VerificationVerdict,
        constraint_ir_from_schema,
    )
    from dataforge.verifier.differential import differential_verify

__all__ = [
    "CONTRACT_VERSION",
    "CandidateFix",
    "CandidateRepair",
    "CausalCluster",
    "CellFix",
    "ClusterCompressionReport",
    "ConservationReport",
    "ExternalFix",
    "GazetteerConflictError",
    "ConstraintCandidate",
    "ConstraintReviewArtifact",
    "ConstraintReviewError",
    "ConstraintIR",
    "DuckDBStore",
    "Issue",
    "PatchPlan",
    "ProposedFix",
    "ProofObligation",
    "RepairFailure",
    "RepairPipelineRequest",
    "RepairPipelineResult",
    "RepairReceipt",
    "RepairTransaction",
    "ReferenceGazetteer",
    "RootCause",
    "ReviewedConstraintCandidate",
    "SMTVerifier",
    "SafetyContext",
    "SafetyFilter",
    "SafetyResult",
    "SafetyVerdict",
    "Schema",
    "SchemaInferenceResult",
    "Severity",
    "TransactionAuditReport",
    "TransactionAuditVerdict",
    "TransactionLogError",
    "TransactionRevertError",
    "TableStoreError",
    "TableStoreRepairResult",
    "VerificationResult",
    "VerificationVerdict",
    "VerifiedFix",
    "VerifyAndApplyRequest",
    "__version__",
    "verify_and_apply",
    "CellScore",
    "ReviewRanker",
    "load_schema",
    "build_constraint_review_artifact",
    "constraint_ir_from_schema",
    "dump_constraint_review_artifact",
    "load_constraint_review_artifact",
    "read_csv",
    "revert_transaction",
    "run_all_detectors",
    "run_repair_pipeline",
    "authoritative_schema_from_dbt_artifacts",
    "authoritative_schema_from_dbt_manifest",
    "schema_from_mapping",
    "schema_from_dbt_artifacts",
    "schema_from_dbt_manifest",
    "infer_schema",
    "infer_verification_schema",
    "is_table_store_uri",
    "journal_head_sha256_for",
    "run_table_store_repair",
    "store_from_uri",
    "verify_transaction_log",
    "check_table_conservation",
    "cluster_repairs",
    "differential_verify",
]

__version__ = "0.1.0"

_PUBLIC_EXPORTS: dict[str, tuple[str, str]] = {
    "CONTRACT_VERSION": ("dataforge.repair_contract", "CONTRACT_VERSION"),
    "CandidateFix": ("dataforge.engine.repair", "CandidateFix"),
    "CandidateRepair": ("dataforge.engine.repair", "CandidateRepair"),
    "CausalCluster": ("dataforge.triage_clusters", "CausalCluster"),
    "CellFix": ("dataforge.transactions.txn", "CellFix"),
    "ClusterCompressionReport": ("dataforge.triage_clusters", "ClusterCompressionReport"),
    "ConservationReport": ("dataforge.safety.conservation", "ConservationReport"),
    "ExternalFix": ("dataforge.engine.repair", "ExternalFix"),
    "GazetteerConflictError": ("dataforge.gazetteer", "GazetteerConflictError"),
    "ReferenceGazetteer": ("dataforge.gazetteer", "ReferenceGazetteer"),
    "ConstraintCandidate": ("dataforge.schema_inference", "ConstraintCandidate"),
    "ConstraintReviewArtifact": ("dataforge.schema_inference", "ConstraintReviewArtifact"),
    "ConstraintReviewError": ("dataforge.schema_inference", "ConstraintReviewError"),
    "ConstraintIR": ("dataforge.verifier", "ConstraintIR"),
    "DuckDBStore": ("dataforge.stores", "DuckDBStore"),
    "Issue": ("dataforge.detectors", "Issue"),
    "ProposedFix": ("dataforge.repairers", "ProposedFix"),
    "ProofObligation": ("dataforge.engine.repair", "ProofObligation"),
    "PatchPlan": ("dataforge.stores", "PatchPlan"),
    "RepairFailure": ("dataforge.engine.repair", "RepairFailure"),
    "RepairPipelineRequest": ("dataforge.engine.repair", "RepairPipelineRequest"),
    "RepairPipelineResult": ("dataforge.engine.repair", "RepairPipelineResult"),
    "RepairReceipt": ("dataforge.engine.repair", "RepairReceipt"),
    "RepairTransaction": ("dataforge.transactions.txn", "RepairTransaction"),
    "RootCause": ("dataforge.engine.repair", "RootCause"),
    "ReviewedConstraintCandidate": ("dataforge.schema_inference", "ReviewedConstraintCandidate"),
    "SMTVerifier": ("dataforge.verifier", "SMTVerifier"),
    "SafetyContext": ("dataforge.safety", "SafetyContext"),
    "SafetyFilter": ("dataforge.safety", "SafetyFilter"),
    "SafetyResult": ("dataforge.safety", "SafetyResult"),
    "SafetyVerdict": ("dataforge.safety", "SafetyVerdict"),
    "Schema": ("dataforge.detectors", "Schema"),
    "SchemaInferenceResult": ("dataforge.schema_inference", "SchemaInferenceResult"),
    "Severity": ("dataforge.detectors", "Severity"),
    "TransactionAuditReport": ("dataforge.transactions.log", "TransactionAuditReport"),
    "TransactionAuditVerdict": ("dataforge.transactions.log", "TransactionAuditVerdict"),
    "TransactionLogError": ("dataforge.transactions.log", "TransactionLogError"),
    "TransactionRevertError": ("dataforge.transactions.revert", "TransactionRevertError"),
    "TableStoreError": ("dataforge.stores", "TableStoreError"),
    "TableStoreRepairResult": ("dataforge.stores", "TableStoreRepairResult"),
    "VerificationResult": ("dataforge.verifier", "VerificationResult"),
    "VerificationVerdict": ("dataforge.verifier", "VerificationVerdict"),
    "VerifiedFix": ("dataforge.engine.repair", "VerifiedFix"),
    "VerifyAndApplyRequest": ("dataforge.engine.repair", "VerifyAndApplyRequest"),
    "verify_and_apply": ("dataforge.engine.repair", "verify_and_apply"),
    # Review-queue triage. Measured a decisive win on flooded queues (hospital
    # review precision 5.0% -> 40.7%, rayyan ~50x queue-precision lift) but was
    # previously reachable only through `dataforge bench` -- no export, no CLI
    # flag, no tool. Presentation-only: a score can never reach the apply gate.
    "CellScore": ("dataforge.review", "CellScore"),
    "ReviewRanker": ("dataforge.review", "ReviewRanker"),
    "load_schema": ("dataforge.cli.common", "load_schema"),
    "build_constraint_review_artifact": (
        "dataforge.schema_inference",
        "build_constraint_review_artifact",
    ),
    "constraint_ir_from_schema": ("dataforge.verifier", "constraint_ir_from_schema"),
    "dump_constraint_review_artifact": (
        "dataforge.schema_inference",
        "dump_constraint_review_artifact",
    ),
    "load_constraint_review_artifact": (
        "dataforge.schema_inference",
        "load_constraint_review_artifact",
    ),
    "read_csv": ("dataforge.table", "read_csv"),
    "revert_transaction": ("dataforge.transactions.revert", "revert_transaction"),
    "run_all_detectors": ("dataforge.detectors", "run_all_detectors"),
    "run_repair_pipeline": ("dataforge.engine.repair", "run_repair_pipeline"),
    "authoritative_schema_from_dbt_artifacts": (
        "dataforge.integrations.dbt",
        "authoritative_schema_from_dbt_artifacts",
    ),
    "authoritative_schema_from_dbt_manifest": (
        "dataforge.integrations.dbt",
        "authoritative_schema_from_dbt_manifest",
    ),
    "schema_from_mapping": ("dataforge.cli.common", "schema_from_mapping"),
    "schema_from_dbt_artifacts": ("dataforge.integrations.dbt", "schema_from_dbt_artifacts"),
    "schema_from_dbt_manifest": ("dataforge.integrations.dbt", "schema_from_dbt_manifest"),
    "infer_schema": ("dataforge.schema_inference", "infer_schema"),
    "infer_verification_schema": ("dataforge.schema_inference", "infer_verification_schema"),
    "is_table_store_uri": ("dataforge.stores", "is_table_store_uri"),
    "journal_head_sha256_for": ("dataforge.transactions.log", "journal_head_sha256_for"),
    "run_table_store_repair": ("dataforge.stores", "run_table_store_repair"),
    "store_from_uri": ("dataforge.stores", "store_from_uri"),
    "verify_transaction_log": ("dataforge.transactions.log", "verify_transaction_log"),
    "check_table_conservation": ("dataforge.safety.conservation", "check_table_conservation"),
    "cluster_repairs": ("dataforge.triage_clusters", "cluster_repairs"),
    "differential_verify": ("dataforge.verifier.differential", "differential_verify"),
}


def __getattr__(name: str) -> Any:
    """Resolve public facade exports on first use."""
    try:
        module_name, attribute_name = _PUBLIC_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
