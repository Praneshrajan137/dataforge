"""Help text is a claim surface, and it was the least policed one in the repository.

``--help`` is the first thing a user reads and, until 2026-09-13, nothing checked it. On that date
``dataforge verify-apply --proposer`` was found advertising *"Attribution recorded on the
certificate"* for a command that never called the attestation emitter at all. The promise was
plausible, reviewed, committed, and false for the entire life of the flag.

An independent claim-model sweep then put ~25+ behavioural promises in CLI help text with **zero**
gate coverage: ``docs_truth`` polices only the quantitative claims registered in
``docs/quantitative_claims.yaml``, which is an allowlist, and help strings are not in it.

This gate closes the narrow, mechanically checkable part of that surface: **a command that names a
portable artifact in its help text must be able to produce one.** It deliberately does not attempt
to adjudicate prose. A gate that tried to verify every adjective would either be unfalsifiable
itself or would block ordinary wording changes, and the project's own rule is that a check must be
able to fail for a real reason and only for a real reason.

The population is DERIVED by parsing ``help=`` keywords out of the AST of every ``dataforge/cli``
module -- not grepped, because the word "attestation" appears in prose and docstrings throughout
these files and a gate a comment can satisfy proves nothing. A new command joins this test on the
day it is written.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_DIR = _REPO_ROOT / "dataforge" / "cli"

#: Naming one of these in help text promises the user a portable, third-party-checkable artifact.
#: "certificate" is included because the project uses it for BOTH the local receipt and the
#: portable attestation, and a user reading help text cannot tell which they are being promised --
#: so either meaning obliges the command to reach the emitter.
_ARTIFACT_WORDS = ("certificate", "attestation")

#: Reaching either of these means the module can actually produce or verify the artifact.
_EMITTER_MODULES = ("dataforge.cli.emit", "dataforge.attestation")


def _help_strings(module_file: Path) -> list[str]:
    """Every ``help=`` value in the module, read from the AST rather than by grep."""
    found: list[str] = []
    for node in ast.walk(ast.parse(module_file.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "help":
                continue
            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, TypeError, SyntaxError):
                continue  # An f-string or a name: not a static promise this gate can judge.
            if isinstance(value, str):
                found.append(value)
    return found


def _reaches_emitter(module_file: Path) -> bool:
    tree = ast.parse(module_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and any(node.module.startswith(m) for m in _EMITTER_MODULES):
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name.startswith(m) for alias in node.names for m in _EMITTER_MODULES
        ):
            return True
    return False


def _modules() -> list[Path]:
    return sorted(path for path in _CLI_DIR.glob("*.py") if path.name != "__init__.py")


def _promising_modules() -> list[Path]:
    """Derived population: modules whose help text names a portable artifact."""
    return [
        path
        for path in _modules()
        if any(word in text.lower() for text in _help_strings(path) for word in _ARTIFACT_WORDS)
    ]


class TestHelpTextDoesNotPromiseWhatTheCommandCannotProduce:
    def test_the_population_is_derived_and_not_empty(self) -> None:
        """Non-vacuity: a gate over an empty population passes while proving nothing."""
        promising = _promising_modules()
        assert promising, (
            "no CLI module names a certificate or attestation in its help text. Either the "
            "AST-based help extraction has broken, or the product stopped advertising its "
            "portable artifact -- both are findings, not passes."
        )
        names = {path.name for path in promising}
        # verify_apply is the one that was actually broken; keep it pinned by name so the
        # regression cannot vanish by the help text being quietly reworded.
        assert "verify_apply.py" in names, sorted(names)

    @pytest.mark.parametrize("module_file", _promising_modules(), ids=lambda p: p.name)
    def test_a_module_promising_an_artifact_can_emit_one(self, module_file: Path) -> None:
        promises = [
            text
            for text in _help_strings(module_file)
            if any(word in text.lower() for word in _ARTIFACT_WORDS)
        ]
        assert _reaches_emitter(module_file), (
            f"{module_file.relative_to(_REPO_ROOT)} advertises a portable artifact in help text "
            f"but never imports {' or '.join(_EMITTER_MODULES)}, so it cannot produce or check "
            f"one. The offending promise(s):\n"
            + "\n".join(f"  - {text!r}" for text in promises)
            + "\n\nThis is the --proposer defect of 2026-09-13: help text is a claim, and a claim "
            "a user reads before anything else is the worst place to be wrong."
        )

    def test_every_cli_module_is_parseable_so_none_is_silently_skipped(self) -> None:
        """A module this gate cannot parse is a module it silently exempts.

        Without this, a syntax-level change that broke extraction would shrink the population to
        zero and every other assertion here would pass vacuously.
        """
        for path in _modules():
            assert isinstance(_help_strings(path), list), path
