"""``dataforge schema`` -- author the declared premise that authorises proven writes.

Exists because C4 left the operator with no paved path: a mined constraint confers no write
authority, so ``--schema`` is the only route to a proven repair, and nothing produced a
starting file. See :mod:`dataforge.schema_scaffold` for why the draft is deliberately inert.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from dataforge.cli.common import read_csv, resolve_cli_path
from dataforge.schema_inference import infer_schema
from dataforge.schema_scaffold import INERT_TYPE, build_schema_draft
from dataforge.transactions.files import atomic_write_bytes

schema_app = typer.Typer(help="Author the declared premise that authorises proven writes.")

_console = Console(stderr=True)


@schema_app.command("init")
def init(
    source: str = typer.Argument(..., help="CSV file to profile."),
    out: str | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Where to write the draft. Defaults to <source>.schema.yaml.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing draft. Refused by default so an edited premise is safe.",
    ),
) -> None:
    """Write a declared-premise DRAFT for a table, from what DataForge observes in it.

    The draft grants no write authority. Every column is declared ``string``, which cannot
    reject any CSV value and therefore confers no proof, so repairing with an unedited draft
    writes zero cells. Observed constraints are included commented out, with the evidence
    behind each, for you to accept deliberately.

    That asymmetry is the point: DataForge will tell you what it thinks is true about your
    data, and will not act on it until you say so.
    """
    resolved = resolve_cli_path(Path(source))
    if not resolved.is_file():
        _console.print(f"[red]No such file: {resolved}[/red]")
        raise typer.Exit(code=2)

    destination = resolve_cli_path(Path(out)) if out else resolved.with_suffix(".schema.yaml")

    # Refusing by default matters more here than in most places: the file this would clobber
    # is the operator's authored premise, which is the thing that authorises writes. Losing it
    # silently would be a data-loss bug one level up from the data.
    if destination.exists() and not force:
        _console.print(
            f"[red]{destination} already exists.[/red] Pass --force to overwrite it, "
            "or --out to write elsewhere. Refusing by default because an existing schema is "
            "an authored premise, not a cache."
        )
        raise typer.Exit(code=2)

    inference = infer_schema(read_csv(resolved))
    # Atomic, and for the same reason `write_constraint_review_artifact_atomic` is: this file
    # is premise-bearing. With --force it can replace a premise the operator authored, and a
    # torn write would leave a half-file that either fails to parse or -- worse -- parses into
    # a premise nobody wrote. `atomic_write_bytes` publishes via tempfile + fsync + os.replace,
    # so the operator's premise is either the old one or the new one, never a fragment.
    atomic_write_bytes(
        destination,
        build_schema_draft(inference, source=str(resolved)).encode("utf-8"),
    )

    column_count = len(getattr(inference, "columns", {}) or {})
    candidate_count = len(getattr(inference, "candidates", ()) or ())
    out_console = Console()
    out_console.print(
        Panel(
            f"Wrote a declared-premise draft to [bold]{destination}[/bold]\n"
            f"{column_count} column(s) declared `{INERT_TYPE}`; "
            f"{candidate_count} observed constraint(s) included as commented suggestions.\n\n"
            f"This draft authorises NO writes yet -- a `{INERT_TYPE}` column cannot reject a "
            "value, so it confers no proof.\n"
            "Edit it to assert what is true of your data, then:\n"
            f"  dataforge repair {resolved} --schema {destination} --dry-run",
            title="Declared Premise Draft",
            style="cyan",
        )
    )
