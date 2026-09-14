"""The portable artifact must carry proof, never payload.

Assessed 2026-09-13 while looking for a PII exposure in the attestation, on the assumption that
an artifact describing cell repairs must embed cell values, and that a receipt covering personal
data therefore becomes regulated data the moment it leaves the machine.

**The assumption was wrong, and the design is better than the concern.** Two artifacts exist and
they split along exactly the right line:

- the **receipt** (``repair_receipt_v1``, printed by ``--json``) carries ``old_value`` and
  ``new_value``. It is local, and it is what a human reads.
- the **attestation** (``--attest-out``, in-toto/DSSE) carries ``column``, ``row``,
  ``detector_id``, ``provenance`` and ``verification_strength`` -- and no values whatsoever. The
  content of the change is conveyed only through the post-state SHA-256 digest.

So the artifact designed to travel is the one that cannot leak data, and the artifact that holds
data does not travel. A verifier holding the data file can still confirm the digest; a verifier
without it learns *what was proven where*, never *what the values were*. Measured: repairing a
``salary`` cell to ``999123`` produced a 1.6 KB artifact containing neither ``999123`` nor the
old ``50000``, and an untouched ``ssn`` column's values appeared nowhere.

**Why this file exists even though the property already holds.** Nothing guarded it. The property
is one plausible-sounding pull request away from silent regression -- adding ``new_value`` to the
predicate "so the diff is readable in the artifact" would be an easy review to wave through, and
it would convert every attestation over regulated data into an exfiltration channel with no test
objecting. This repository's recurring defect is not wrong invariants; it is correct invariants
with no consumer and no guard.

Column NAMES do travel, in ``fixes`` and in the embedded constraints. That is deliberate and
necessary: strength is derived from column authority, so a verifier that cannot see which column
was written cannot re-derive whether the write was authorised. Schema metadata is disclosed;
table contents are not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from dataforge.cli import app

runner = CliRunner()

# Values chosen to be unmistakable if they ever appear: no digest, index or version string will
# contain them by coincidence, unlike a short value such as "15" which does occur inside hex.
_SENSITIVE_NEW = "9187364520117"
_SENSITIVE_OLD = "5541983267740"
_UNTOUCHED_PII = "111-22-3333"


def _emit(tmp_path: Path) -> tuple[dict[str, Any], str]:
    """Apply one proven repair to a sensitive column and return (statement, raw bytes)."""
    csv_path = tmp_path / "payroll.csv"
    schema_path = tmp_path / "schema.json"
    fixes_path = tmp_path / "fixes.json"
    artifact = tmp_path / "attestation.json"

    # `salary` is float -- discriminating, so it confers proof. `ssn` is str and is never the
    # repair target: it is here to catch bulk-table leakage as distinct from changed-cell leakage.
    csv_path.write_text(
        f"id,ssn,salary\n1,{_UNTOUCHED_PII},{_SENSITIVE_OLD}\n2,444-55-6666,60000\n",
        encoding="utf-8",
    )
    schema_path.write_text(
        '{"columns": {"id": "str", "ssn": "str", "salary": "float"}}', encoding="utf-8"
    )
    fixes_path.write_text(
        json.dumps([{"row": 0, "column": "salary", "new_value": _SENSITIVE_NEW}]),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "verify-apply",
            str(csv_path),
            "--fixes",
            str(fixes_path),
            "--schema",
            str(schema_path),
            "--apply",
            "--confirm-escalations",
            "--attest-out",
            str(artifact),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert artifact.exists(), "no artifact was written"
    raw = artifact.read_text(encoding="utf-8")
    return json.loads(raw), raw


class TestTheTravellingArtifactCarriesNoTableData:
    def test_the_repaired_value_does_not_travel(self, tmp_path: Path) -> None:
        _, raw = _emit(tmp_path)
        assert _SENSITIVE_NEW not in raw, (
            "the attestation embedded the value it wrote. Every attestation over regulated data "
            "is now a copy of that data, and the artifact is designed to leave the machine."
        )

    def test_the_replaced_value_does_not_travel(self, tmp_path: Path) -> None:
        """The old value is the more dangerous of the two: it is the real record."""
        _, raw = _emit(tmp_path)
        assert _SENSITIVE_OLD not in raw, "the attestation embedded the value it overwrote"

    def test_untouched_columns_do_not_travel(self, tmp_path: Path) -> None:
        """A repair to one column must not export the rest of the row."""
        _, raw = _emit(tmp_path)
        assert _UNTOUCHED_PII not in raw, "a cell the repair never touched appeared in the artifact"

    def test_the_fix_records_authority_not_content(self, tmp_path: Path) -> None:
        """Non-vacuity: the artifact must still say something useful about each change.

        Without this, deleting the ``fixes`` list entirely would satisfy every assertion above
        while destroying the artifact's purpose. Privacy bought by saying nothing is not a
        result.
        """
        statement, _ = _emit(tmp_path)
        predicate = statement.get("predicate", statement)
        fixes = predicate["fixes"]
        assert len(fixes) == 1, fixes
        recorded = fixes[0]

        # What a third party needs to re-derive whether the write was authorised.
        assert recorded["column"] == "salary"
        assert recorded["row"] == 0
        assert recorded["provenance"] == "external"
        assert recorded["verification_strength"] == "proven"

        # And what it must not need: the values.
        assert "new_value" not in recorded, "value fields must not be added to the predicate"
        assert "old_value" not in recorded, "value fields must not be added to the predicate"

    def test_the_change_is_still_pinned_by_a_digest(self, tmp_path: Path) -> None:
        """Value-freedom must not cost verifiability.

        The digest is what makes "no values" safe rather than vague: a verifier holding the data
        can confirm the exact post-state, so withholding the values loses nothing checkable.
        """
        statement, _ = _emit(tmp_path)
        predicate = statement.get("predicate", statement)
        digest = predicate["post"]["digest"]["sha256"]
        assert isinstance(digest, str) and len(digest) == 64
        assert all(character in "0123456789abcdef" for character in digest)

    def test_the_receipt_by_contrast_does_carry_values(self, tmp_path: Path) -> None:
        """Pins the SPLIT, not just one half.

        If the receipt also stopped carrying values, these tests would still pass while the
        product lost the diff a human reviews. The distinction being asserted is that values
        stay local and proofs travel -- so both halves need pinning, or a future change could
        "fix" the wrong one.
        """
        csv_path = tmp_path / "d.csv"
        schema_path = tmp_path / "s.json"
        fixes_path = tmp_path / "f.json"
        csv_path.write_text("id,salary\n1,10\n", encoding="utf-8")
        schema_path.write_text('{"columns": {"id": "str", "salary": "float"}}', encoding="utf-8")
        fixes_path.write_text(
            json.dumps([{"row": 0, "column": "salary", "new_value": _SENSITIVE_NEW}]),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "verify-apply",
                str(csv_path),
                "--fixes",
                str(fixes_path),
                "--schema",
                str(schema_path),
                "--apply",
                "--confirm-escalations",
                "--json",
            ],
        )
        payload = json.loads(result.stdout)
        applied = payload["receipt"]["applied_fixes"]
        assert applied and applied[0]["new_value"] == _SENSITIVE_NEW, (
            "the local receipt must keep the values a human needs to review the change"
        )
