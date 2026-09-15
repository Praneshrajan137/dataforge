"""A gate step must run the script it claims to run.

Verified as a LIVE defect on 2026-09-14, and it is the worst shape a defect in this file can
take, because the step it disabled is the one that detects other gates disappearing.

`scripts/ci/backend_gate.py` contained:

    GateCommand(
        "gate population",
        [PYTHON, "scripts/ci/hf_space_frontmatter.py", "scripts/ci/gate_population.py", "--check"],
    )

That is ONE interpreter invocation. `hf_space_frontmatter.py` is the script;
`gate_population.py --check` are argv entries it never reads -- its `main()` takes no parameters
and the module has no argparse. So the step printed "HF Space YAML front-matter valid", reported
**PASS** under the name "gate population", and `gate_population.py` never executed. Two checks
were collapsed into one named slot, so one of them was also running under another's name.

Three properties made it serious:

* `gate_population.py` appears in **no** workflow. Searching `.github/workflows/*.yml` for it
  returns one comment and zero run steps, and CI never invokes `make gate-population`. This
  malformed command was its only path to execution.
* It is the META-gate. It is what makes a deleted test, a vanished claim, a removed mutant or a
  dropped gate step detectable at all. Its absence hid a defect CLASS, not an instance.
* `ci.yml` and `Makefile` both justify OTHER decisions with the words *"was frozen against
  removal by scripts/ci/gate_population.py -- and no workflow ever executed it"*, citing this gate
  as the trustworthy freezing mechanism in the same sentence that explains why unexecuted
  protection is worthless. Every "frozen against removal" claim in the repository was false.

The symptom was visible and unread: `gate_population.py --check` reported 136 un-emitted pytest
node additions when finally run by hand on 2026-09-14.

What this module gates is the INVOCATION SHAPE, not that particular step. A step name is a claim
about what ran, and this asserts the claim is true of the argv beside it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_GATE = _ROOT / "scripts" / "ci" / "backend_gate.py"

#: Callees whose first positional argument is a step name and whose second is an argv list.
_STEP_CONSTRUCTORS = frozenset({"_run", "GateCommand"})

#: Steps whose argv legitimately names a second `.py` path, each with the reason. Empty, and it
#: must stay empty unless a real case appears: this is the named-remainder half of the rule, so a
#: legitimate exception is recorded here rather than weakening the assertion for everything.
_SECOND_SCRIPT_ALLOWED: dict[str, str] = {}


def _step_invocations() -> list[tuple[str, list[str]]]:
    """Return every (step name, argv literal) pair declared in the backend gate.

    Non-literal argv entries (`*PYTHON_PATHS`, f-strings, variables) are rendered as the sentinel
    ``"<dynamic>"`` rather than dropped, so a dynamic entry can never be mistaken for an absent
    one.
    """
    tree = ast.parse(_BACKEND_GATE.read_text(encoding="utf-8"))
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else None
        if name not in _STEP_CONSTRUCTORS or len(node.args) < 2:
            continue
        step, argv_node = node.args[0], node.args[1]
        if not (isinstance(step, ast.Constant) and isinstance(step.value, str)):
            continue
        if not isinstance(argv_node, ast.List):
            continue
        argv: list[str] = []
        for element in argv_node.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                argv.append(element.value)
            else:
                argv.append("<dynamic>")
        found.append((step.value, argv))
    return found


def _is_script(entry: str) -> bool:
    """Return whether an argv entry is a path to a Python script.

    Excludes config overrides and globs. `latency budgets` passes
    ``-o python_files=bench_*.py`` to pytest, which ends in ``.py`` and is neither a path nor a
    script -- treating it as one made the existence assertion fire on a correct step. Narrowing
    the predicate is right here: a rule that cries wolf gets deleted, and this rule guards the
    step that guards every other gate.
    """
    return entry.endswith(".py") and "=" not in entry and "*" not in entry


#: Collected once. The parametrize ids below are the STEP NAMES alone, deliberately: an earlier
#: draft used the argv in the id, which made every pytest node id change whenever any step's
#: arguments changed, and `gate_population.py` would then report that churn as tests removed and
#: added. A gate that reports noise gets its manifest re-emitted without being read, which is how
#: a real removal would slip through.
_INVOCATIONS: list[tuple[str, list[str]]] = _step_invocations()
_IDS: list[str] = [step for step, _ in _INVOCATIONS]


class TestEveryStepRunsTheScriptItNames:
    """The defect, pinned. A second `.py` path in argv is silently ignored by the first."""

    def test_at_least_one_step_was_found(self) -> None:
        """Non-vacuity: an AST walk that finds nothing would pass every test below."""
        assert len(_INVOCATIONS) >= 30, (
            f"only {len(_INVOCATIONS)} step invocations parsed out of backend_gate.py; the AST "
            "walk has stopped seeing the command table and every assertion here is now vacuous"
        )

    @pytest.mark.parametrize(("step", "argv"), _INVOCATIONS, ids=_IDS)
    def test_a_direct_script_invocation_passes_no_second_script(
        self, step: str, argv: list[str]
    ) -> None:
        """`python a.py b.py` runs a.py and ignores b.py. That is the bug.

        Scoped to DIRECT script invocation. `python -m ruff check <paths>` legitimately passes
        `.py` arguments, and `PYTHON_PATHS` contains real module paths, so a blanket rule would
        fire on every linter step.
        """
        if len(argv) < 2 or not _is_script(argv[1]):
            return  # not a direct script invocation (e.g. `-m module`, or npm)
        extra = [entry for entry in argv[2:] if _is_script(entry)]
        if step in _SECOND_SCRIPT_ALLOWED:
            return

        assert extra == [], (
            f"step {step!r} runs {argv[1]!r} and passes {extra} as arguments, which that script "
            "will ignore unless it reads sys.argv. This is the 2026-09-14 defect: the step "
            f"reported PASS under the name {step!r} while a different script ran. Split it into "
            "separate steps, or record it in _SECOND_SCRIPT_ALLOWED with the reason."
        )

    @pytest.mark.parametrize(("step", "argv"), _INVOCATIONS, ids=_IDS)
    def test_the_named_script_exists(self, step: str, argv: list[str]) -> None:
        """A step pointing at a path that is not there fails loudly; this fails earlier."""
        for entry in argv:
            if _is_script(entry):
                assert (_ROOT / entry).exists(), f"step {step!r} names missing script {entry!r}"

    def test_step_names_are_unique(self) -> None:
        """Two steps sharing a name make one of them unattributable in the population manifest.

        This is how the front-matter check came to run under the population check's name.
        """
        names = [step for step, _ in _INVOCATIONS]
        duplicates = sorted({name for name in names if names.count(name) > 1})

        assert duplicates == [], f"duplicate gate step names: {duplicates}"


class TestThePopulationGateIsActuallyReachable:
    """The specific regression, named, so it cannot recur quietly."""

    def test_gate_population_is_invoked_as_a_script(self) -> None:
        invocations = dict(_INVOCATIONS)
        argv = invocations.get("gate population")

        assert argv is not None, "the 'gate population' step has disappeared from the backend gate"
        assert any(entry.endswith("gate_population.py") for entry in argv), (
            "the 'gate population' step no longer names gate_population.py at all"
        )
        script_positions = [index for index, entry in enumerate(argv) if _is_script(entry)]
        assert len(script_positions) == 1, (
            "the 'gate population' step names more than one script again; the first one wins and "
            "the rest are ignored argv"
        )
        assert argv[script_positions[0]].endswith("gate_population.py"), (
            "gate_population.py is an ARGUMENT rather than the script being run, which is exactly "
            "the state that disabled it between 2026-08-28 and 2026-09-14"
        )

    def test_a_ci_workflow_runs_it(self) -> None:
        """Its only invocation used to be inside the backend gate, and that one was broken.

        A gate reachable from exactly one place is one edit away from being unreachable, so this
        asserts an independent path exists.
        """
        workflows = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
        assert workflows, "no workflow files found; this test would otherwise be vacuous"

        runners = [
            path.name
            for path in workflows
            if any(
                marker in path.read_text(encoding="utf-8")
                for marker in ("make gate-population", "gate_population.py --check")
            )
        ]

        assert runners, (
            "no workflow runs the gate population check. Between 2026-08-28 and 2026-09-14 the "
            "only invocation was a malformed backend-gate command that ran a different script, "
            "so nothing detected a deleted test, a vanished claim or a dropped gate step."
        )

    def test_the_makefile_target_exists(self) -> None:
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "gate-population:" in makefile
        assert "gate_population.py --check" in makefile
