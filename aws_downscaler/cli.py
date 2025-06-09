"""Command-line interface for AWS Downscaler."""

import logging
import sys
from typing import Optional

import click
import structlog

from aws_downscaler.config import Config
from aws_downscaler.schedule import Scheduler

logger = structlog.get_logger()


def setup_logging(debug: bool) -> None:
    """Configure logging with structlog."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")

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
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@click.command()
@click.option("--dry-run", is_flag=True, help="Print actions without making changes")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--once", is_flag=True, help="Run once and exit")
@click.option("--interval", default=60, help="Loop interval in seconds", type=int)
@click.option("--default-uptime", help="Default uptime schedule")
@click.option("--default-downtime", help="Default downtime schedule")
@click.option(
    "--grace-period", default=0, help="Grace period for new resources in seconds", type=int
)
@click.option("--include-resources", help="Resource types to manage (comma-separated)")
@click.option("--exclude-resources", help="Resource patterns to exclude (comma-separated)")
@click.option("--downtime-scale", default=0, help="Scale factor during downtime (0-100)", type=int)
def main(
    dry_run: bool,
    debug: bool,
    once: bool,
    interval: int,
    default_uptime: Optional[str],
    default_downtime: Optional[str],
    grace_period: int,
    include_resources: Optional[str],
    exclude_resources: Optional[str],
    downtime_scale: int,
) -> None:
    """Scale down AWS resources during non-work hours to save costs.

    Example usage:
        aws-downscaler --default-uptime="Mon-Fri 08:00-18:00 America/New_York"
    """
    setup_logging(debug)

    config = Config(
        dry_run=dry_run,
        default_uptime=default_uptime,
        default_downtime=default_downtime,
        grace_period=grace_period,
        include_resources=include_resources.split(",") if include_resources else None,
        exclude_resources=exclude_resources.split(",") if exclude_resources else None,
        downtime_scale=downtime_scale,
    )

    scheduler = Scheduler(config)

    try:
        if once:
            scheduler.run_once()
        else:
            scheduler.run(interval)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)
