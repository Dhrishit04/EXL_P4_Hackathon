"""ModelProof command line."""

import importlib.util
import os

import typer

from modelproof import audit, config, graph, inventory, llm

app = typer.Typer(help="ModelProof: agentic model risk factory", no_args_is_help=True)


@app.callback()
def main() -> None:
    """ModelProof: agentic model risk factory. LLMs propose, deterministic code disposes."""


def _ids(model: str) -> list[str]:
    ids = list(config.MODELS) if model == "all" else [model]
    if bad := [m for m in ids if m not in config.MODELS]:
        raise typer.BadParameter(
            f"unknown model {bad[0]!r}; choose one of {', '.join(config.MODELS)} or all"
        )
    return ids


@app.command()
def discover(model: str = typer.Option("all", help="Model id or 'all'")) -> None:
    """Discover models and write the inventory (no human gates)."""
    from modelproof.agents import discover as agent

    for m in _ids(model):
        with llm.for_model(m):
            rec = agent.run(m)
        typer.echo(f"{m}: {rec.name} | tier {rec.risk_tier} | docs {rec.documentation_status}")
    graph._render("inventory")


@app.command()
def run(
    model: str = typer.Option(..., help="Model id or 'all'"),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", help="Approve every gate (recorded as auto)"
    ),
) -> None:
    """Run the pipeline for a model; stops at each human gate unless --auto-approve."""
    for m in _ids(model):
        r = graph.run(m, auto_approve=auto_approve)
        typer.echo(
            f"{m}: {r['status']} (inventory status: {r['inventory_status']}) thread {r['thread_id']}"
        )
        if r["status"] == "waiting":
            typer.echo(f"  gate {r['gate']}: {r['summary']}")
            typer.echo(
                f"  approve with: modelproof approve --thread {r['thread_id']} --decision approve"
            )


@app.command()
def approve(
    thread: str = typer.Option(..., help="Thread id from `modelproof status`"),
    decision: str = typer.Option(..., help="approve or reject"),
    comment: str = typer.Option("", help="Reviewer comment (passed to the re-run on reject)"),
    reviewer: str = typer.Option(os.environ.get("USER", "reviewer"), help="Reviewer name"),
) -> None:
    """Record a human decision at a pending gate and continue the run."""
    try:
        r = graph.resume(thread, decision, comment, reviewer)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    typer.echo(f"{r['model_id']}: {r['status']} (inventory status: {r['inventory_status']})")
    if r["status"] == "waiting":
        typer.echo(f"  next gate {r['gate']}: {r['summary']}")


@app.command()
def status() -> None:
    """Show the inventory and any pending gates."""
    recs = inventory.load()
    typer.echo(f"{'model':<10} {'name':<34} {'tier':>4} {'docs':<9} {'status':<22} drifts flags")
    for r in recs:
        typer.echo(
            f"{r.model_id:<10} {r.name[:34]:<34} {r.risk_tier:>4} {r.documentation_status:<9} "
            f"{r.status:<22} {len(r.doc_code_drifts):>6} {len(r.security_flags):>5}"
        )
    if not recs:
        typer.echo("(inventory is empty: run `modelproof discover`)")
    pending = graph.pending_gates()
    typer.echo(f"\n{len(pending)} pending gate(s)")
    for p in pending:
        typer.echo(f"  {p['thread_id']}  gate {p['gate']}: {p['summary']}")


@app.command()
def monitor(
    model: str = typer.Option(config.REBUILD_TARGET, help="Model id"),
    months: int = typer.Option(6, help="Months to simulate"),
) -> None:
    """Run the simulated monitoring for a rebuilt model."""
    from modelproof import data, monitoring, parity

    res = monitoring.simulate(
        model,
        data.load_cr_pd_002("holdout"),
        parity.score_fn(config.REBUILT / "cr_pd_002.py"),
        months=months,
    )
    typer.echo(f"{model}: {len(res.points)} months (simulated); trigger month: {res.trigger_month}")


@app.command()
def benchmark() -> None:
    """Write artifacts/metrics.json via scripts/benchmark.py."""
    spec = importlib.util.spec_from_file_location(
        "benchmark", config.ROOT / "scripts" / "benchmark.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    typer.echo(f"wrote {mod.main()}")


@app.command("verify-audit")
def verify_audit() -> None:
    """Check the audit log hash chain."""
    ok = audit.verify_chain()
    typer.echo(f"audit chain {'OK' if ok else 'BROKEN'} ({len(audit.read())} entries)")
    raise typer.Exit(0 if ok else 1)
