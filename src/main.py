"""CLI entry point for scraping agent."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from src.analysis.change_detector import ChangeDetector
from src.models.rate import SavingsRate
from src.models.types import Provider
from src.orchestrator import Orchestrator, OrchestratorResult
from src.storage.csv_store import CSVStorage
from src.storage.json_store import JSONStorage
from src.utils.browser import BrowserManager

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

DEFAULT_OUTPUT_DIR = Path("data")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Savings rate scraping agent for UK fintech providers."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["all", "tembo", "chip", "moneybox", "t212"]),
    default="all",
    help="Provider to scrape (default: all)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path (auto-generated if not provided)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: headless)",
)
@click.option(
    "--detect-changes",
    is_flag=True,
    help="Detect and report rate changes from previous scrape",
)
@click.pass_context
def scrape(
    ctx: click.Context,
    provider: str,
    output: str | None,
    output_format: str,
    headless: bool,
    detect_changes: bool,
) -> None:
    """Scrape savings rates from providers."""
    verbose = ctx.obj.get("verbose", False)

    # Determine providers
    providers = list(Provider) if provider == "all" else [Provider(provider)]

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ext = "json" if output_format == "json" else "csv"
        output_path = DEFAULT_OUTPUT_DIR / f"rates_latest.{ext}"

    # Create storage
    storage: JSONStorage | CSVStorage = (
        JSONStorage(output_path) if output_format == "json" else CSVStorage(output_path)
    )

    # Load existing rates for change detection
    change_detector = None
    if detect_changes:
        try:
            existing_rates = storage.load()
            change_detector = ChangeDetector(historical_rates=existing_rates)
            if verbose:
                click.echo(f"Loaded {len(existing_rates)} historical rates for comparison")
        except Exception as e:
            logger.warning("change_detector.load_failed", error=str(e))

    # Run scraping
    click.echo(f"Scraping rates from: {', '.join(p.value for p in providers)}")

    try:
        result = asyncio.run(_run_scrape(providers, storage, headless))
    except KeyboardInterrupt:
        click.echo("\nScraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error("scrape.failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Report results
    click.echo("\nResults:")
    click.echo(f"  Providers scraped: {result.successful_providers}/{len(providers)}")
    click.echo(f"  Rates found: {result.total_rates}")
    click.echo(f"  Duration: {result.duration_seconds:.2f}s")
    click.echo(f"  Output: {output_path}")

    # Report failures
    if result.failed_providers > 0:
        click.echo("\nFailed providers:")
        for r in result.results:
            if not r.success:
                click.echo(f"  - {r.provider.value}: {r.error}")

    # Detect changes if requested
    if change_detector and result.total_rates > 0:
        changes = change_detector.detect_changes(result.all_rates)
        significant = change_detector.get_significant_changes(changes)
        anomalies = change_detector.get_anomalies(changes)

        if significant or anomalies:
            click.echo("\nRate changes detected:")
            for change in significant:
                symbol = "+" if change.change_amount > 0 else ""
                click.echo(
                    f"  {change.product_name.value}: "
                    f"{change.previous_rate}% -> {change.current_rate}% "
                    f"({symbol}{change.change_amount}%)"
                )

            if anomalies:
                click.echo("\nAnomalies detected:")
                for anomaly in anomalies:
                    click.echo(f"  {anomaly.product_name.value}: {anomaly.anomaly_reason}")

    # Exit code
    if result.failed_providers > 0 and result.successful_providers == 0:
        sys.exit(1)


async def _run_scrape(
    providers: list[Provider],
    storage: JSONStorage | CSVStorage,
    headless: bool,
) -> OrchestratorResult:
    """Run scraping asynchronously."""
    async with BrowserManager(headless=headless) as browser:
        orchestrator = Orchestrator(
            browser=browser,
            storage=storage,
            providers=providers,
        )
        return await orchestrator.run()


@cli.command()
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="File format to show (default: json)",
)
@click.option(
    "--input",
    "-i",
    "input_path",
    type=click.Path(exists=True),
    default=None,
    help="Input file path (default: data/rates_latest.{format})",
)
@click.option(
    "--history",
    "-h",
    is_flag=True,
    help="Show all historical rates with timestamps (default: latest only)",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["all"] + [p.value for p in Provider]),
    default="all",
    help="Filter by provider (default: all)",
)
def show(
    output_format: str, input_path: str | None, history: bool, provider: str
) -> None:
    """Show stored rates."""
    if input_path:
        path = Path(input_path)
    else:
        ext = "json" if output_format == "json" else "csv"
        path = DEFAULT_OUTPUT_DIR / f"rates_latest.{ext}"

    if not path.exists():
        click.echo(f"No rates file found at {path}", err=True)
        sys.exit(1)

    # Load rates
    storage: JSONStorage | CSVStorage = (
        JSONStorage(path) if output_format == "json" else CSVStorage(path)
    )

    rates = storage.load()

    if not rates:
        click.echo("No rates found")
        return

    # Filter by provider if specified
    if provider != "all":
        rates = [r for r in rates if r.provider.value == provider]

    if not rates:
        click.echo(f"No rates found for provider: {provider}")
        return

    # Group by provider and product
    by_provider: dict[Provider, dict[str, list[SavingsRate]]] = {}
    for rate in rates:
        if rate.provider not in by_provider:
            by_provider[rate.provider] = {}
        product_key = rate.product_name.value
        if product_key not in by_provider[rate.provider]:
            by_provider[rate.provider][product_key] = []
        by_provider[rate.provider][product_key].append(rate)

    if history:
        # Show all rates with timestamps
        total_entries = sum(
            len(prod_rates) for prods in by_provider.values() for prod_rates in prods.values()
        )
        click.echo(f"Found {total_entries} rate entries:\n")

        for prov in sorted(by_provider.keys(), key=lambda p: p.value):
            click.echo(f"{prov.value.upper()}:")
            for product_name, product_rates in sorted(by_provider[prov].items()):
                # Sort by timestamp descending
                sorted_rates = sorted(product_rates, key=lambda r: r.scraped_at, reverse=True)
                click.echo(f"  {product_name}:")
                for rate in sorted_rates:
                    timestamp = rate.scraped_at.strftime("%Y-%m-%d %H:%M")
                    click.echo(f"    {timestamp}: {rate.rate}% ({rate.rate_type.value})")
            click.echo()
    else:
        # Show only latest rate per product
        unique_products = sum(len(products) for products in by_provider.values())
        click.echo(f"Latest rates ({unique_products} products):\n")

        for prov in sorted(by_provider.keys(), key=lambda p: p.value):
            click.echo(f"{prov.value.upper()}:")
            for product_name, product_rates in sorted(by_provider[prov].items()):
                # Get the latest rate by timestamp
                latest = max(product_rates, key=lambda r: r.scraped_at)
                timestamp = latest.scraped_at.strftime("%Y-%m-%d %H:%M")
                click.echo(
                    f"  {product_name}: {latest.rate}% ({latest.rate_type.value}) @ {timestamp}"
                )
            click.echo()


@cli.command()
def providers() -> None:
    """List available providers."""
    click.echo("Available providers:")
    for provider in Provider:
        click.echo(f"  - {provider.value}")


if __name__ == "__main__":
    cli()
