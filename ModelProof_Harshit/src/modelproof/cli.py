"""ModelProof command line. (Scaffold: only verify-audit for now; the rest lands with graph.py.)"""

import typer

from modelproof import audit

app = typer.Typer(help="ModelProof: agentic model risk factory", no_args_is_help=True)


@app.callback()
def main() -> None:
    """ModelProof: agentic model risk factory."""


@app.command("verify-audit")
def verify_audit() -> None:
    """Check the audit log hash chain."""
    ok = audit.verify_chain()
    typer.echo(f"audit chain {'OK' if ok else 'BROKEN'} ({len(audit.read())} entries)")
    raise typer.Exit(0 if ok else 1)
