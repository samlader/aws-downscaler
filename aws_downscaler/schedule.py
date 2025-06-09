"""Time window and scheduling logic for AWS Downscaler."""

import time as time_module
from datetime import datetime
from typing import Optional

import boto3
import pytz
import structlog

from aws_downscaler.config import Config
from aws_downscaler.resources.asg import AutoScalingGroupResource
from aws_downscaler.resources.ecs import ECSServiceResource
from aws_downscaler.time_window import TimeWindow

logger = structlog.get_logger()


class Scheduler:
    """Scheduler for AWS resource scaling."""

    def __init__(self, config: Config):
        """Initialize scheduler with configuration."""
        self.config = config
        self.uptime_windows = TimeWindow.parse_time_specs(config.default_uptime)
        self.downtime_windows = TimeWindow.parse_time_specs(config.default_downtime)

        self.session = boto3.Session()

        self.resource_handlers = [
            AutoScalingGroupResource(self.session, self.config),
            ECSServiceResource(self.session, self.config),
        ]

    def is_uptime(self, now: Optional[datetime] = None) -> bool:
        """Check if current time is within uptime window."""
        if now is None:
            now = datetime.now(pytz.UTC)

        for window in self.uptime_windows:
            if window.is_active(now):
                return True

        for window in self.downtime_windows:
            if window.is_active(now):
                return False

        return True

    def run_once(self) -> None:
        """Run scaling check once."""
        now = datetime.now(pytz.UTC)
        is_up = self.is_uptime(now)
        logger.info(
            "Running scaling check",
            uptime=is_up,
            dry_run=self.config.dry_run,
        )

        for handler in self.resource_handlers:
            try:
                handler.check_and_scale(now)
            except Exception as e:
                logger.error(
                    "Error processing resource type",
                    handler=handler.__class__.__name__,
                    error=str(e),
                )

    def run(self, interval: int) -> None:
        """Run scaling checks in a loop."""
        logger.info(
            "Starting AWS Downscaler",
            uptime_windows=self.config.default_uptime,
            downtime_windows=self.config.default_downtime,
            dry_run=self.config.dry_run,
        )

        while True:
            try:
                self.run_once()
                time_module.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
