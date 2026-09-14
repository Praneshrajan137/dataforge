"""Tests for ``dataforge schema init`` -- the paved path to a declared premise.

The load-bearing test here is :func:`test_unedited_draft_writes_zero_cells`. C4
(``PRODUCT.md`` §1.5) removed write authority from mined constraints on measured grounds, so a
scaffold that emitted inferred types as *declarations* would hand that authority straight
back -- a mined premise with extra steps. The draft is inert by construction (every column
declared ``string``, which cannot reject a CSV value and so confers no proof), and that test
is what proves the construction holds through the real pipeline rather than in principle.

If it ever fails, the scaffold has begun conferring authority and C4 is gone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from dataforge.cli import app
from dataforge.cli.common import schema_from_mapping
from dataforge.schema_inference import infer_schema
from dataforge.schema_scaffold import INERT_TYPE, build_schema_draft
from dataforge.table import read_csv

runner = CliRunner()


def _write_fd_violating_csv(path: Path) -> None:
    """A table with a real, obvious functional dependency violation.

    ``state -> city`` holds on every row but the last. A premise declaring it would authorise
    a proven repair; the point of the tests below is that the *draft* does not declare it.
    """
    rows = "\n".join(f"{index},MA,boston" for index in range(1, 10))
    path.write_text(f"id,state,city\n{rows}\n10,MA,bostonn\n", encoding="utf-8")


class TestDraftIsInert:
    """Every property that keeps the draft from conferring authority."""

    def test_every_column_is_declared_inert(self, tmp_path: Path) -> None:
        source = tmp_path / "data.csv"
        _write_fd_violating_csv(source)
        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))

        parsed = yaml.safe_load(draft)
        assert parsed["columns"], "the draft must declare the columns it found"
        assert set(parsed["columns"].values()) == {INERT_TYPE}

    def test_no_constraint_section_is_active(self, tmp_path: Path) -> None:
        """Only ``columns`` may be live. Everything else must be commented out."""
        source = tmp_path / "data.csv"
        _write_fd_violating_csv(source)
        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))

        parsed = yaml.safe_load(draft)
        assert set(parsed) == {"columns"}, (
            f"a live constraint key would confer authority; found {sorted(parsed)}"
        )

    def test_parsed_draft_declares_no_functional_dependency(self, tmp_path: Path) -> None:
        """``fd_violation`` is one of two detectors permitted to write. Never seed it."""
        source = tmp_path / "data.csv"
        _write_fd_violating_csv(source)
        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))

        schema = schema_from_mapping(yaml.safe_load(draft))
        assert schema.functional_dependencies == ()
        assert schema.regex_constraints == ()
        assert schema.domain_bounds == ()
        assert schema.unique_columns == frozenset()

    def test_draft_states_that_it_grants_nothing(self, tmp_path: Path) -> None:
        """An operator must not have to infer the inertness from the YAML."""
        source = tmp_path / "data.csv"
        _write_fd_violating_csv(source)
        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))
        assert "NOTHING IN THIS FILE GRANTS WRITE AUTHORITY YET" in draft

    def test_draft_carries_evidence_for_suggestions(self, tmp_path: Path) -> None:
        """A suggestion without its evidence asks for blind trust."""
        source = tmp_path / "data.csv"
        _write_fd_violating_csv(source)
        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))
        assert "evidence:" in draft


def test_unedited_draft_writes_zero_cells(tmp_path: Path) -> None:
    """THE C4 GUARANTEE. Scaffold, then repair with the draft untouched -- nothing is written.

    Run through the CLI rather than the engine so the assertion covers the path a user takes,
    per ``PRODUCT.md`` §1.4: "An arm that models a user journey must be built from the code
    that journey runs."
    """
    source = tmp_path / "data.csv"
    _write_fd_violating_csv(source)
    before = source.read_bytes()

    init_result = runner.invoke(app, ["schema", "init", str(source)])
    assert init_result.exit_code == 0, init_result.stdout

    draft = source.with_suffix(".schema.yaml")
    assert draft.is_file()

    runner.invoke(app, ["repair", str(source), "--schema", str(draft), "--apply"])

    assert source.read_bytes() == before, (
        "an unedited draft authorised a write. The scaffold is conferring authority that C4 "
        "removed, and the inertness guarantee is broken."
    )


def test_init_refuses_to_clobber_an_existing_premise(tmp_path: Path) -> None:
    """An authored premise is what authorises writes; losing it silently is a real bug."""
    source = tmp_path / "data.csv"
    _write_fd_violating_csv(source)
    draft = source.with_suffix(".schema.yaml")
    draft.write_text("columns:\n  id: int\n", encoding="utf-8")

    result = runner.invoke(app, ["schema", "init", str(source)])

    assert result.exit_code == 2
    assert draft.read_text(encoding="utf-8") == "columns:\n  id: int\n"


def test_init_overwrites_with_force(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    _write_fd_violating_csv(source)
    draft = source.with_suffix(".schema.yaml")
    draft.write_text("columns:\n  id: int\n", encoding="utf-8")

    result = runner.invoke(app, ["schema", "init", str(source), "--force"])

    assert result.exit_code == 0, result.stdout
    assert "GRANTS WRITE AUTHORITY" in draft.read_text(encoding="utf-8")


def test_init_honours_explicit_out_path(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    _write_fd_violating_csv(source)
    target = tmp_path / "nested" / "premise.yaml"
    target.parent.mkdir()

    result = runner.invoke(app, ["schema", "init", str(source), "--out", str(target)])

    assert result.exit_code == 0, result.stdout
    assert target.is_file()


def test_init_reports_a_missing_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["schema", "init", str(tmp_path / "absent.csv")])
    assert result.exit_code == 2


class TestYamlSpecialColumnNames:
    """Column names from CSV headers can contain any character. The scaffold must produce
    valid YAML for all of them, not just the alphanumeric majority."""

    @pytest.mark.parametrize(
        "name",
        [
            "#comment",  # YAML comment prefix -- vanishes if unquoted
            "- dash",  # YAML block-sequence indicator -- changes structure
            "Amount: USD",  # colon-space -- YAML mapping separator, parse error
            "[bracket]",  # flow-sequence open -- parse error
            "{brace}",  # flow-mapping open -- parse error
            'has"quote',  # double-quote inside a key
            "has'apostrophe",  # single-quote (safe in YAML 1.1 plain scalars, but fragile)
        ],
    )
    def test_draft_round_trips_special_column_name(self, name: str, tmp_path: Path) -> None:
        """A column name with YAML-special characters must survive safe_load."""
        source = tmp_path / "data.csv"
        source.write_text(f"{name},normal\nval1,val2\n", encoding="utf-8")

        draft = build_schema_draft(infer_schema(read_csv(source)), source=str(source))
        parsed = yaml.safe_load(draft)

        assert isinstance(parsed, dict), f"YAML parse returned {type(parsed)}, not a dict"
        assert "columns" in parsed, f"no 'columns' key in parsed YAML: {parsed}"
        assert isinstance(parsed["columns"], dict), (
            f"'columns' is {type(parsed['columns'])}, not a dict -- a YAML-special column name "
            f"broke the structure"
        )
        assert name in parsed["columns"], (
            f"column {name!r} vanished from the parsed draft. "
            f"Parsed keys: {list(parsed['columns'].keys())}"
        )
