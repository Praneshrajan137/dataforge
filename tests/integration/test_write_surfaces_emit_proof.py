"""Every surface that writes to a user's data must be able to emit the portable proof.

This gate exists because the suite already contained
``tests/integration/test_attestation_reaches_consumers.py`` -- a test whose name is exactly the
property -- and the property was still false on two of three write surfaces. That test imports
the emitter and calls it directly, so it proves the ARTIFACT is correct. It is structurally
incapable of noticing a command that never calls the emitter at all.

The result, until 2026-09-13:

    repair --apply --json          attestation emitted
    verify-apply --apply           nothing, while --proposer promised "recorded on the
                                   certificate"
    watch --apply --json           nothing

``verify-apply`` is the entry point for the declared primary wedge. Its consumers -- an
autonomous agent's operator, an auditor reading after the fact -- exist only for the evidence.
It proved every fix, applied them reversibly, and discarded the proof.

The population is DERIVED, never listed: it is the set of registered commands exposing an
``--apply`` flag. A future write surface joins this test automatically on the day it is
registered. A listed population would have to be remembered, and PRODUCT.md section 1.3 records
two separate defects caused by a frozen population that was restated instead of derived.

What is asserted is the MACHINE surface (``--json``, and ``--attest-out`` where the artifact is
a file). Human terminal output is not required to carry a statement -- it is required to say
where one went, which ``verify-apply`` now does and which
``tests/integration/test_guardrail_attestation.py`` pins.
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

from dataforge import cli

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_DIR = _REPO_ROOT / "dataforge" / "cli"

# The one shared emitter. A surface that does not reach this module cannot be emitting a
# statement, whatever else it prints.
_EMITTER_MODULE = "dataforge.cli.emit"
_EMITTER_NAMES = frozenset({"attest_result", "result_json", "write_attestation"})


def _write_commands() -> list[str]:
    """Derive the write surfaces: registered commands exposing ``--apply``."""
    found: list[str] = []
    for name in sorted(cli.command_names()):
        command = cli.resolve_command(name)
        if command is None:
            continue
        for param in command.params:
            if "--apply" in getattr(param, "opts", ()):
                found.append(name)
                break
    return found


def _module_path_for(command_name: str) -> Path:
    """Map a command to the module file that implements it.

    Resolved via ``callback.__module__`` rather than ``callback.__code__.co_filename``: Typer's
    decorator rebinds the code object, so ``co_filename`` reports ``cli/main.py`` for every
    command and would make this gate compare all three surfaces against one unrelated file.
    """
    command = cli.resolve_command(command_name)
    assert command is not None, command_name
    callback = command.callback
    assert callback is not None, f"{command_name} has no callback"
    module = import_module(callback.__module__)
    module_file = getattr(module, "__file__", None)
    assert module_file is not None, f"{callback.__module__} has no file"
    return Path(module_file).resolve()


def _reaches_emitter(module_file: Path) -> bool:
    """True when this module imports the shared emitter, at module or function scope.

    Parsed rather than string-matched: ``"attest"`` appears in prose in several of these files,
    and a gate that a comment can satisfy is a gate that proves nothing.
    """
    tree = ast.parse(module_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == _EMITTER_MODULE and any(
                alias.name in _EMITTER_NAMES for alias in node.names
            ):
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name == _EMITTER_MODULE for alias in node.names
        ):
            return True
    return False


class TestEveryWriteSurfaceCanEmitProof:
    def test_the_population_is_derived_and_not_empty(self) -> None:
        """Non-vacuity: a gate over an empty population passes while proving nothing."""
        commands = _write_commands()
        assert commands, "derived no write surfaces -- the --apply introspection has broken"
        # Pin the surfaces known at the time of writing so a SILENT disappearance is caught
        # too. New surfaces are welcome and join automatically; these three vanishing means
        # the derivation broke, not that the product shrank.
        assert {"repair", "verify-apply", "watch"} <= set(commands), commands

    @pytest.mark.parametrize("command_name", _write_commands())
    def test_write_surface_reaches_the_emitter(self, command_name: str) -> None:
        module_file = _module_path_for(command_name)
        assert _reaches_emitter(module_file), (
            f"'dataforge {command_name} --apply' writes to a user's data but its module "
            f"({module_file.relative_to(_REPO_ROOT)}) never imports {_EMITTER_MODULE}. "
            f"It can prove a fix and apply it, but not hand anyone the proof. "
            f"A certificate with a named consumer is a product; one without is a log line."
        )

    def test_the_emitter_is_a_single_shared_module(self) -> None:
        """One emitter, not one per surface.

        A reimplementation of a vetted path reproduces the defect the vetted path exists to
        avoid (PRODUCT.md section 1.4). Two attestation builders would drift, and the drift
        would be invisible because each would be internally consistent.
        """
        builders = [
            path
            for path in _CLI_DIR.glob("*.py")
            if "def attest_result(" in path.read_text(encoding="utf-8")
        ]
        assert [path.name for path in builders] == ["emit.py"], (
            f"attest_result is defined in more than one place: {[p.name for p in builders]}"
        )
