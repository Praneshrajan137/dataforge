"""The benchmark writer must not silently narrow a committed artifact.

**This is a regression test for something that actually happened.** On 2026-09-07, while
investigating the hospital anchor, a diagnostic
`dataforge bench --methods heuristic --datasets hospital --seeds 1` overwrote
`eval/results/agent_comparison.json` -- a committed artifact that `docs_truth`,
`benchmark_truth` and `tests/unit/test_corpus_tiering.py` all read -- replacing twelve records
with one. Nothing warned. The evidence survived only because the file happens to be tracked by
git, which is luck rather than a guarantee.

Frozen evidence that any diagnostic command can overwrite in place is not frozen, so the pin
here is the **refusal**, not the write.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataforge.bench.core import BenchmarkCoverageLossError, write_run_output


def _artifact(pairs: list[tuple[str, str]]) -> dict[str, object]:
    return {"records": [{"method": method, "dataset": dataset} for method, dataset in pairs]}


class _FakeOutput:
    """Minimal stand-in: write_run_output needs `.records` and `.model_dump_json()`."""

    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self.records = [{"method": method, "dataset": dataset} for method, dataset in pairs]

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps({"records": self.records}, indent=indent)


def test_narrowing_a_committed_artifact_is_refused(tmp_path: Path) -> None:
    """The exact command that destroyed the twelve-record artifact must now fail."""
    path = tmp_path / "agent_comparison.json"
    path.write_text(
        json.dumps(
            _artifact(
                [
                    ("random", "hospital"),
                    ("heuristic", "hospital"),
                    ("random", "flights"),
                    ("heuristic", "flights"),
                ]
            )
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()

    with pytest.raises(BenchmarkCoverageLossError) as caught:
        write_run_output(_FakeOutput([("heuristic", "hospital")]), path)

    message = str(caught.value)
    assert "random/hospital" in message, "the refusal must name what would have been destroyed"
    assert "--allow-coverage-loss" in message, "the refusal must name the deliberate override"
    assert path.read_bytes() == before, "the artifact must be byte-identical after a refusal"


def test_rerunning_the_same_coverage_is_allowed(tmp_path: Path) -> None:
    """A full re-run is the normal way to refresh an anchor and must not be blocked."""
    path = tmp_path / "a.json"
    pairs = [("random", "hospital"), ("heuristic", "hospital")]
    path.write_text(json.dumps(_artifact(pairs)), encoding="utf-8")

    write_run_output(_FakeOutput(pairs), path)

    assert len(json.loads(path.read_text(encoding="utf-8"))["records"]) == 2


def test_extending_coverage_is_allowed(tmp_path: Path) -> None:
    """Adding a method or dataset loses nothing, so it must not require the override."""
    path = tmp_path / "a.json"
    path.write_text(json.dumps(_artifact([("heuristic", "hospital")])), encoding="utf-8")

    write_run_output(_FakeOutput([("heuristic", "hospital"), ("heuristic", "flights")]), path)

    assert len(json.loads(path.read_text(encoding="utf-8"))["records"]) == 2


def test_the_override_still_permits_a_deliberate_narrowing(tmp_path: Path) -> None:
    """The guard is a tripwire, not a lock: an explicit narrowing must remain possible."""
    path = tmp_path / "a.json"
    path.write_text(
        json.dumps(_artifact([("random", "hospital"), ("heuristic", "hospital")])),
        encoding="utf-8",
    )

    write_run_output(_FakeOutput([("heuristic", "hospital")]), path, allow_coverage_loss=True)

    assert len(json.loads(path.read_text(encoding="utf-8"))["records"]) == 1


def test_writing_a_fresh_path_is_unaffected(tmp_path: Path) -> None:
    """There is nothing to protect when the file does not exist yet."""
    path = tmp_path / "nested" / "a.json"
    write_run_output(_FakeOutput([("heuristic", "hospital")]), path)
    assert path.exists()


def test_an_unreadable_existing_artifact_does_not_block_the_write(tmp_path: Path) -> None:
    """Corrupt bytes are not evidence, so they must not become an unfixable blocker.

    Without this the guard could wedge the repo: a truncated artifact would refuse every
    subsequent write, including the full re-run that would repair it.
    """
    path = tmp_path / "a.json"
    path.write_text("{not json", encoding="utf-8")

    write_run_output(_FakeOutput([("heuristic", "hospital")]), path)

    assert json.loads(path.read_text(encoding="utf-8"))["records"]


def test_the_cli_exposes_the_override_flag() -> None:
    """A guard with no documented escape hatch gets worked around by deleting the file."""
    from dataforge.cli.bench import bench

    names = bench.__annotations__
    assert "allow_coverage_loss" in names


class TestSeedCoverageIsAlsoProtected:
    """The seed is the third dimension the guard's own docstring names, and it was unguarded.

    ``write_run_output``'s docstring says it protects against "a narrower run -- one method, one
    dataset, one seed, as a diagnostic". The historical incident narrowed all three at once, so
    a (method, dataset) check caught it and the seed was never separately tested -- every
    fixture above omits the field entirely.

    ``dataforge bench --quick`` narrows ONLY the seed: it pins ``seeds = 1`` while running the
    same ``random,heuristic`` methods over the same two datasets. The (method, dataset) pairs
    are therefore identical, ``dropped`` is empty, and the write proceeds.

    Observed on 2026-09-13, not hypothesised: a ``--quick`` run replaced the committed
    twelve-record artifact (4 pairs x seeds 0,1,2) with four records (4 pairs x seed 0). The
    positional ledger anchor ``records/3/f1`` then retargeted from hospital/heuristic (0.8352)
    to flights/heuristic (0.0) and ``docs_truth`` failed. It failed LOUDLY only because the two
    values happen to differ; a re-ordering that preserved the value would have passed while
    pointing at different evidence.

    ``dataforge bench --quick`` is the command ``dataforge quickstart`` prints and the README
    cites for reproduction. The tool's recommended reproducibility check was the one command
    that silently narrowed the evidence it exists to confirm.
    """

    @staticmethod
    def _seeded(pairs: list[tuple[str, str]], seeds: list[int]) -> list[dict[str, object]]:
        return [
            {"method": method, "dataset": dataset, "seed": seed}
            for method, dataset in pairs
            for seed in seeds
        ]

    def test_dropping_seeds_is_refused(self, tmp_path: Path) -> None:
        """The exact shape of a ``--quick`` run over the committed artifact."""
        path = tmp_path / "agent_comparison.json"
        pairs = [
            ("random", "hospital"),
            ("heuristic", "hospital"),
            ("random", "flights"),
            ("heuristic", "flights"),
        ]
        path.write_text(json.dumps({"records": self._seeded(pairs, [0, 1, 2])}), encoding="utf-8")
        before = path.read_bytes()

        quick = _FakeOutput([])
        quick.records = self._seeded(pairs, [0])

        with pytest.raises(BenchmarkCoverageLossError) as caught:
            write_run_output(quick, path)

        assert "--allow-coverage-loss" in str(caught.value)
        assert path.read_bytes() == before, "the artifact must survive a refusal byte-for-byte"

    def test_rerunning_the_same_seeds_is_still_allowed(self, tmp_path: Path) -> None:
        """Refreshing an anchor with the full seed set must not need the override."""
        path = tmp_path / "a.json"
        pairs = [("heuristic", "hospital")]
        path.write_text(json.dumps({"records": self._seeded(pairs, [0, 1, 2])}), encoding="utf-8")

        same = _FakeOutput([])
        same.records = self._seeded(pairs, [0, 1, 2])
        write_run_output(same, path)

        assert len(json.loads(path.read_text(encoding="utf-8"))["records"]) == 3

    def test_adding_seeds_is_allowed(self, tmp_path: Path) -> None:
        """More evidence is never a loss."""
        path = tmp_path / "a.json"
        pairs = [("heuristic", "hospital")]
        path.write_text(json.dumps({"records": self._seeded(pairs, [0])}), encoding="utf-8")

        more = _FakeOutput([])
        more.records = self._seeded(pairs, [0, 1])
        write_run_output(more, path)

        assert len(json.loads(path.read_text(encoding="utf-8"))["records"]) == 2

    def test_a_seedless_artifact_is_still_comparable(self, tmp_path: Path) -> None:
        """Older artifacts predate the seed field and must not become unwritable.

        A guard that cannot read historical evidence would wedge the repository, which is the
        same failure mode the unreadable-artifact case above exists to prevent.
        """
        path = tmp_path / "a.json"
        path.write_text(json.dumps(_artifact([("heuristic", "hospital")])), encoding="utf-8")

        write_run_output(_FakeOutput([("heuristic", "hospital")]), path)

        assert json.loads(path.read_text(encoding="utf-8"))["records"]


class TestQuickIsADiagnosticNotAPublication:
    """``--quick`` must not write the shared evidence ledger at all.

    Guarding the ledger is necessary but not sufficient. With the seed axis added, the honest
    outcome of ``dataforge bench --quick`` against a committed multi-seed artifact became a
    refusal -- correct, but it arrives after the run and prints no coverage matrix, so the user
    who asked to CHECK the numbers gets neither the numbers nor the check.

    The resolution is not a weaker guard: it is that a diagnostic has no business writing the
    ledger. ``--quick`` redirects to a ``.quick.json`` sibling, so the committed evidence is
    never in the blast radius of a reproducibility check and the user still gets their matrix.
    """

    def test_quick_redirects_away_from_the_committed_ledger(self) -> None:
        from dataforge.cli.bench import _DEFAULT_OUTPUT_JSON

        assert Path("eval/results/agent_comparison.json") == _DEFAULT_OUTPUT_JSON
        redirected = _DEFAULT_OUTPUT_JSON.with_name(
            f"{_DEFAULT_OUTPUT_JSON.stem}.quick{_DEFAULT_OUTPUT_JSON.suffix}"
        )
        assert redirected != _DEFAULT_OUTPUT_JSON
        assert redirected.name == "agent_comparison.quick.json"

    def test_the_quick_artifact_is_ignored_by_git(self) -> None:
        """A diagnostic that dirties the working tree gets committed by accident.

        Once committed it becomes a second evidence file one seed deep, sitting beside a
        twelve-record ledger with the same record ordering -- precisely the confusion that made
        the positional anchor retarget silently.
        """
        ignore_file = Path(__file__).resolve().parents[2] / ".gitignore"
        patterns = ignore_file.read_text(encoding="utf-8").splitlines()
        assert "eval/results/*.quick.json" in patterns, (
            "the --quick diagnostic artifact must be gitignored"
        )

    def test_an_explicit_output_path_is_still_honoured(self) -> None:
        """The redirect must not hijack a path the user chose deliberately."""
        import inspect

        from dataforge.cli.bench import bench

        source = inspect.getsource(bench)
        assert "if output_json == _DEFAULT_OUTPUT_JSON:" in source, (
            "the redirect must be conditional on the default, so --output-json still wins"
        )
