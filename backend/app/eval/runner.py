import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.application.eval_explanation_service import EvalExplanationService, persist_eval_report
from app.config import get_settings

console = Console()
DATASET_OPTION = typer.Option(..., "--dataset", exists=True, readable=True)
OUTPUT_DIR_OPTION = typer.Option(None, "--output-dir")


def main(
    dataset: Path = DATASET_OPTION,
    output_dir: Path | None = OUTPUT_DIR_OPTION,
) -> None:
    report = asyncio.run(_run(dataset))
    destination = output_dir or dataset.parent / "results"
    persist_eval_report(report, destination)
    _render_table(report)


async def _run(dataset: Path):
    service = EvalExplanationService(get_settings())
    return await service.run_dataset(dataset)


def _render_table(report) -> None:
    table = Table(title="Eval Results")
    table.add_column("Case")
    table.add_column("Facts", justify="right")
    table.add_column("Cites", justify="right")
    table.add_column("Halluc", justify="right")
    table.add_column("Ground", justify="right")
    table.add_column("Useful", justify="right")
    table.add_column("Bullets", justify="right")

    for case in report["cases"]:
        metrics = case["metrics"]
        table.add_row(
            case["id"],
            f"{metrics['fact_coverage']:.2f}",
            f"{metrics['citation_coverage']:.2f}",
            f"{metrics['hallucination_penalty']:.2f}",
            _format_optional_metric(metrics.get("groundedness")),
            f"{metrics['usefulness']:.2f}",
            str(case["bullet_count"]),
        )

    console.print(table)


def _format_optional_metric(value) -> str:
    return "n/a" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    typer.run(main)
