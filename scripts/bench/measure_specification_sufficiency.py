"""Measure whether the attestation specification is sufficient for an independent implementation.

Drives one or more CLEAN-ROOM verifiers over the committed conformance vectors and records where
each disagrees with the recorded verdict. Pre-registered in
``eval/preregistration/specification_sufficiency.md``.

The clean-room verifiers are the INSTRUMENT; the specification is the SUBJECT. Every disagreement is
scored as a specification defect unless it falls inside the narrow instrument carve-out fixed as K6
in the pre-registration -- which covers only a failure to produce a well-formed verdict at all
(crash, JSON parse error, crypto API misuse), never a semantic disagreement about which check fires.

Each arm is a self-contained Java 17 program invoked as::

    java -cp <dir> Verify --attestation <path> [--pubkey-hex <hex>] [--data <path>]

emitting one JSON object on stdout: ``{"ok": bool, "checks": [{"name", "status", "detail"}]}``.

Invocation mirrors ``tests/unit/test_attestation_vectors.py`` exactly -- the public key is supplied
only for signed documents -- so that a disagreement cannot be an artefact of a different call.

Usage:
    python scripts/bench/measure_specification_sufficiency.py --report
    python scripts/bench/measure_specification_sufficiency.py --emit
    python scripts/bench/measure_specification_sufficiency.py --report --arm armA
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VECTORS = PROJECT_ROOT / "tests" / "fixtures" / "attestation" / "vectors.json"
ARTIFACT = PROJECT_ROOT / "eval" / "results" / "specification_sufficiency.json"

#: Where each arm's compiled classes live. Derived from the arm name so a new arm needs no edit
#: here beyond its directory existing.
CLEANROOM_ROOT = PROJECT_ROOT / "eval" / "cleanroom"

#: What each arm was given as its specification surface. Recorded in the artifact because the whole
#: measurement is a comparison between these input sets.
ARM_INPUTS: dict[str, str] = {
    "armA": "specs/SPEC_repair_attestation.md",
    "armB": "specs/SPEC_repair_attestation.md + specs/repair_attestation.schema.json",
    "armC": "specs/SPEC_repair_attestation.md (amended)",
}

RUN_TIMEOUT_SECONDS = 120

#: Vectors added AFTER arms A and B were built and measured, each with the reason.
#:
#: Arms A and B were measured against the 26 vectors committed at the time, and that is the
#: pre-registered comparison. The four below were added as a RESULT of what those arms exposed, so
#: a rate computed over all 30 answers a different question and must not be quoted as the
#: pre-registered one. Both are emitted; neither is allowed to stand in for the other.
#:
#: Named individually rather than counted, so that a fifth vector added later cannot silently
#: enlarge the historical baseline and move a published figure.
VECTORS_ADDED_AFTER_MEASUREMENT: dict[str, str] = {
    "valid-data-identity-with-matching-bytes": "data_identity had zero vectors; format extended",
    "reject-data-identity-mismatched-bytes": "data_identity had zero vectors; format extended",
    "reject-signature-from-a-different-key": "section 9 required it and no vector supplied it",
    "reject-unrecognised-statement-type": "mutant A1 survived: only predicateType had a vector",
}


@dataclass
class VectorOutcome:
    """One arm's result on one vector."""

    vector: str
    expect_ok: bool
    expect_failures: list[str]
    actual_ok: bool | None
    actual_failures: list[str]
    reported_checks: list[str]
    verdict: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "vector": self.vector,
            "expect_ok": self.expect_ok,
            "expect_failures": self.expect_failures,
            "actual_ok": self.actual_ok,
            "actual_failures": self.actual_failures,
            "verdict": self.verdict,
            "detail": self.detail,
        }


@dataclass
class ArmResult:
    """Every outcome for one arm, plus the derived totals."""

    arm: str
    inputs: str
    outcomes: list[VectorOutcome] = field(default_factory=list)

    @property
    def agreeing(self) -> list[VectorOutcome]:
        return [outcome for outcome in self.outcomes if outcome.verdict == "AGREE"]

    @property
    def disagreeing(self) -> list[VectorOutcome]:
        return [outcome for outcome in self.outcomes if outcome.verdict != "AGREE"]

    @property
    def check_names(self) -> list[str]:
        """Every check name this arm ever reported, across all vectors.

        Derived from the arm's own output rather than declared, so an arm that reports a check on
        some documents and omits it on others is visible instead of averaged away.
        """
        names: set[str] = set()
        for outcome in self.outcomes:
            names.update(outcome.reported_checks)
        return sorted(names)

    def as_dict(self) -> dict[str, Any]:
        total = len(self.outcomes)
        agree = len(self.agreeing)
        baseline = [
            outcome
            for outcome in self.outcomes
            if outcome.vector not in VECTORS_ADDED_AFTER_MEASUREMENT
        ]
        baseline_agree = len([o for o in baseline if o.verdict == "AGREE"])
        return {
            "arm": self.arm,
            "inputs": self.inputs,
            "vectors_total": total,
            "vectors_agreeing": agree,
            "vectors_disagreeing": total - agree,
            "agreement_rate": round(agree / total, 4) if total else 0.0,
            # The pre-registered comparison: only the vectors that existed when arms A and B were
            # measured. Quote this one against those arms.
            "baseline_vectors_total": len(baseline),
            "baseline_vectors_agreeing": baseline_agree,
            "baseline_agreement_rate": (
                round(baseline_agree / len(baseline), 4) if baseline else 0.0
            ),
            "checks_reported_count": len(self.check_names),
            "checks_reported": self.check_names,
            "outcomes": [outcome.as_dict() for outcome in self.outcomes],
        }


def _load_vectors() -> dict[str, Any]:
    if not VECTORS.exists():
        raise SystemExit(f"MISSING: {VECTORS.relative_to(PROJECT_ROOT)}")
    payload: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))
    return payload


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"FAIL: {name} not found on PATH; a clean-room arm cannot be run.")
    return found


def compile_arm(arm_dir: Path, classes_dir: Path) -> None:
    """Compile an arm's committed Java sources into ``classes_dir``.

    Only sources are committed. Compiling on every run is what makes the arms reproducible
    evidence rather than an opaque binary somebody has to trust.
    """
    sources = sorted(arm_dir.glob("*.java"))
    if not sources:
        raise SystemExit(f"FAIL: no .java sources in {arm_dir}")
    completed = subprocess.run(
        [_tool("javac"), "-d", str(classes_dir), *[str(path) for path in sources]],
        capture_output=True,
        text=True,
        check=False,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise SystemExit(f"FAIL: javac failed for {arm_dir.name}:\n{completed.stderr}")


def _invoke(
    classes_dir: Path,
    document_path: Path,
    *,
    pubkey_hex: str | None,
    data_path: Path | None,
) -> tuple[int, str, str]:
    command = [
        _tool("java"),
        "-cp",
        str(classes_dir),
        "Verify",
        "--attestation",
        str(document_path),
    ]
    if data_path is not None:
        command += ["--data", str(data_path)]
    if pubkey_hex is not None:
        command += ["--pubkey-hex", pubkey_hex]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _parse_report(stdout: str) -> tuple[bool | None, list[str], list[str], str]:
    """Return (ok, failing check names, all reported check names, error detail)."""
    text = stdout.strip()
    if not text:
        return None, [], [], "arm produced no stdout"
    try:
        report = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [], [], f"arm stdout is not JSON: {exc}"
    if not isinstance(report, dict):
        return None, [], [], "arm stdout is not a JSON object"

    checks = report.get("checks")
    if not isinstance(checks, list):
        return None, [], [], "arm report has no 'checks' list"

    failing: list[str] = []
    reported: list[str] = []
    for entry in checks:
        if not isinstance(entry, dict):
            return None, [], [], "a check entry is not an object"
        name = entry.get("name")
        status = entry.get("status")
        if not isinstance(name, str) or not isinstance(status, str):
            return None, [], [], "a check entry lacks a string name or status"
        reported.append(name)
        if status == "fail":
            failing.append(name)

    ok = report.get("ok")
    if not isinstance(ok, bool):
        return None, [], reported, "arm report has no boolean 'ok'"
    return ok, sorted(failing), sorted(set(reported)), ""


def _classify(
    expect_ok: bool,
    expect_failures: list[str],
    actual_ok: bool | None,
    actual_failures: list[str],
    error: str,
) -> tuple[str, str]:
    """Score one vector against one arm's output.

    ``NO_VERDICT`` is the only category the K6 instrument carve-out can apply to. Every other
    non-``AGREE`` verdict is a semantic disagreement and therefore a specification defect.
    """
    if error:
        return "NO_VERDICT", error
    if actual_ok == expect_ok and actual_failures == expect_failures:
        return "AGREE", ""

    detail = f"expected ok={expect_ok} failures={expect_failures}; got ok={actual_ok} failures={actual_failures}"
    if actual_ok != expect_ok:
        kind = "WRONG_VERDICT_ACCEPTED" if actual_ok else "WRONG_VERDICT_REJECTED"
        return kind, detail
    return "WRONG_CHECKS", detail


def measure_arm(arm: str, classes_dir: Path, payload: dict[str, Any]) -> ArmResult:
    """Run every vector against one arm."""
    result = ArmResult(arm=arm, inputs=ARM_INPUTS.get(arm, "unrecorded"))
    pubkey = str(payload["test_public_key_hex"])
    vectors: dict[str, Any] = payload["vectors"]

    with tempfile.TemporaryDirectory(prefix=f"specsuff_{arm}_") as scratch:
        scratch_dir = Path(scratch)
        for name in sorted(vectors):
            case = vectors[name]
            document = case["document"]
            # Mirror tests/unit/test_attestation_vectors.py: the key is supplied only when the
            # document is a DSSE envelope, so a disagreement cannot be an artefact of the call.
            signed = isinstance(document, dict) and "payload" in document
            document_path = scratch_dir / f"{name}.json"
            document_path.write_text(json.dumps(document), encoding="utf-8")

            # Vectors that exercise `data_identity` carry their input bytes inline. Omitting this
            # made the runner report an arm as ACCEPTING a mismatched-digest document when the arm
            # had simply never been handed the bytes -- an instrument defect, found 2026-09-15 and
            # recorded as amendment 3 of the pre-registration.
            data_path: Path | None = None
            data_b64 = case.get("data_b64")
            if data_b64:
                data_path = scratch_dir / f"{name}.data"
                data_path.write_bytes(base64.b64decode(str(data_b64)))

            try:
                code, stdout, stderr = _invoke(
                    classes_dir,
                    document_path,
                    pubkey_hex=pubkey if signed else None,
                    data_path=data_path,
                )
            except subprocess.TimeoutExpired:
                result.outcomes.append(
                    VectorOutcome(
                        vector=name,
                        expect_ok=bool(case["expect_ok"]),
                        expect_failures=list(case["expect_failures"]),
                        actual_ok=None,
                        actual_failures=[],
                        reported_checks=[],
                        verdict="NO_VERDICT",
                        detail=f"timed out after {RUN_TIMEOUT_SECONDS}s",
                    )
                )
                continue

            ok, failing, reported, error = _parse_report(stdout)
            if error and code != 0:
                error = f"{error} (exit {code}: {stderr.strip()[:200]})"

            verdict, detail = _classify(
                bool(case["expect_ok"]), list(case["expect_failures"]), ok, failing, error
            )
            result.outcomes.append(
                VectorOutcome(
                    vector=name,
                    expect_ok=bool(case["expect_ok"]),
                    expect_failures=list(case["expect_failures"]),
                    actual_ok=ok,
                    actual_failures=failing,
                    reported_checks=reported,
                    verdict=verdict,
                    detail=detail,
                )
            )
    return result


def cross_arm_disagreements(results: list[ArmResult]) -> dict[str, Any]:
    """Where two arms disagree with EACH OTHER, independent of our verifier.

    This is the measurement that does not depend on our implementation being right about anything:
    two faithful readers of overlapping documents reaching different verdicts is direct evidence
    that the documents are ambiguous.
    """
    if len(results) < 2:
        return {"comparable": False, "pairs": {}}

    pairs: dict[str, Any] = {}
    for index, left in enumerate(results):
        for right in results[index + 1 :]:
            by_vector_left = {o.vector: o for o in left.outcomes}
            by_vector_right = {o.vector: o for o in right.outcomes}
            shared = sorted(set(by_vector_left) & set(by_vector_right))
            differing = [
                vector
                for vector in shared
                if (
                    by_vector_left[vector].actual_ok != by_vector_right[vector].actual_ok
                    or by_vector_left[vector].actual_failures
                    != by_vector_right[vector].actual_failures
                )
            ]
            pairs[f"{left.arm}_vs_{right.arm}"] = {
                "vectors_compared": len(shared),
                "vectors_differing": len(differing),
                "differing": differing,
            }
    return {"comparable": True, "pairs": pairs}


def build(arms: list[str]) -> dict[str, Any]:
    payload = _load_vectors()

    # Refuse on a stale name: an entry here that no longer matches a vector would quietly enlarge
    # the historical baseline and move a published figure.
    unknown = sorted(set(VECTORS_ADDED_AFTER_MEASUREMENT) - set(payload["vectors"]))
    if unknown:
        raise SystemExit(
            f"VECTORS_ADDED_AFTER_MEASUREMENT names vectors that do not exist: {unknown}"
        )

    results: list[ArmResult] = []
    for arm in arms:
        arm_dir = CLEANROOM_ROOT / arm
        if not arm_dir.is_dir() or not any(arm_dir.glob("*.java")):
            print(f"SKIP {arm}: no sources at {arm_dir.relative_to(PROJECT_ROOT)}")
            continue
        with tempfile.TemporaryDirectory(prefix=f"specsuff_classes_{arm}_") as classes:
            classes_dir = Path(classes)
            compile_arm(arm_dir, classes_dir)
            results.append(measure_arm(arm, classes_dir, payload))

    return {
        "schema": "dataforge_specification_sufficiency_v1",
        "note": (
            "Clean-room conformance measurement. The arms are the instrument; "
            "specs/SPEC_repair_attestation.md is the subject. Pre-registered in "
            "eval/preregistration/specification_sufficiency.md."
        ),
        "vectors_total": len(payload["vectors"]),
        "arms": {result.arm: result.as_dict() for result in results},
        "cross_arm": cross_arm_disagreements(results),
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"vectors: {report['vectors_total']}")
    for arm, data in sorted(report["arms"].items()):
        print(f"\n==> {arm}  ({data['inputs']})")
        print(
            f"    agree {data['vectors_agreeing']}/{data['vectors_total']}"
            f"  rate {data['agreement_rate']}"
            f"  |  baseline {data['baseline_vectors_agreeing']}/{data['baseline_vectors_total']}"
            f"  rate {data['baseline_agreement_rate']}"
            f"  |  checks {data['checks_reported_count']}"
        )
        print(f"    checks: {', '.join(data['checks_reported'])}")
        for outcome in data["outcomes"]:
            if outcome["verdict"] == "AGREE":
                continue
            print(f"    {outcome['verdict']:24s} {outcome['vector']}")
            print(f"        {outcome['detail']}")

    cross = report["cross_arm"]
    if cross["comparable"]:
        print("\n==> arm-versus-arm")
        for pair, data in sorted(cross["pairs"].items()):
            print(f"    {pair}: {data['vectors_differing']} of {data['vectors_compared']} differ")
            for vector in data["differing"]:
                print(f"        {vector}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", help="Arm to run; repeatable. Default: all.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", action="store_true", help="Print results, write nothing.")
    group.add_argument("--emit", action="store_true", help="Write the results artifact.")
    args = parser.parse_args(argv)

    arms = args.arm or sorted(ARM_INPUTS)
    report = build(arms)
    if not report["arms"]:
        print("FAIL: no arm produced results.")
        return 1

    _print_report(report)

    if args.emit:
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {ARTIFACT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
