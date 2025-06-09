"""Base resource class for AWS Downscaler."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

import boto3
import structlog

from ..config import Config
from ..time_window import TimeWindow

logger = structlog.get_logger()


class BaseResource(ABC):
    """Base class for AWS resources that can be scaled."""

    def __init__(self, session: boto3.Session, config: Config):
        """Initialize base resource with AWS session and configuration."""
        self.session = session
        self.config = config

    @abstractmethod
    def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources of this type."""
        pass

    @abstractmethod
    def get_current_scale(self, resource: Dict[str, Any]) -> int:
        """Get current scale of the resource."""
        pass

    @abstractmethod
    def get_original_scale(self, resource: Dict[str, Any]) -> int:
        """Get original (maximum) scale of the resource."""
        pass

    @abstractmethod
    def set_scale(self, resource: Dict[str, Any], scale: int) -> None:
        """Set the scale of the resource."""
        pass

    def get_resource_name(self, resource: Dict[str, Any]) -> str:
        """Get the name or identifier of the resource."""
        for field in ["Name", "name", "ResourceName", "ServiceName", "Id", "ResourceId", "Arn"]:
            if field in resource:
                return resource[field]

        tags = resource.get("Tags", [])
        for tag in tags:
            if tag.get("Key") == "Name":
                return tag.get("Value", "unknown")

        return "unknown"

    def get_resource_tags(self, resource: Dict[str, Any]) -> Dict[str, str]:
        """Get downscaler-specific tags for the resource."""
        aws_tags = resource.get("Tags", [])
        return self.config.get_resource_tags(aws_tags)

    def should_process(self, resource: Dict[str, Any], now: datetime) -> bool:
        """Check if a resource should be processed."""
        name = self.get_resource_name(resource)
        tags = self.get_resource_tags(resource)

        if tags.get("exclude") == "true":
            logger.debug("Resource is excluded", resource=name)
            return False

        exclude_until = tags.get("exclude-until")
        if exclude_until:
            try:
                until_dt = datetime.fromisoformat(exclude_until.replace("Z", "+00:00"))
                if now < until_dt:
                    logger.debug("Resource excluded until", resource=name, until=exclude_until)
                    return False
            except ValueError:
                logger.warning(
                    "Invalid exclude-until timestamp", resource=name, value=exclude_until
                )

        if self.config.include_resources:
            if name not in self.config.include_resources:
                logger.debug("Resource not in include list", resource=name)
                return False

        if self.config.exclude_resources:
            if name in self.config.exclude_resources:
                logger.debug("Resource in exclude list", resource=name)
                return False

        return True

    def check_and_scale(self, now: datetime) -> None:
        """Check and scale all resources of this type."""
        resources = self.list_resources()

        for resource in resources:
            name = self.get_resource_name(resource)

            if not self.should_process(resource, now):
                logger.debug("Skipping excluded resource", resource=name)
                continue

            try:
                self._process_resource(resource, now)
            except Exception as e:
                logger.error("Error processing resource", resource=name, error=str(e))

    def _process_resource(self, resource: Dict[str, Any], now: datetime) -> None:
        """Process a single resource for scaling."""
        name = self.get_resource_name(resource)
        tags = self.get_resource_tags(resource)

        uptime = TimeWindow.parse_time_specs(tags.get("uptime", self.config.default_uptime))
        downtime = TimeWindow.parse_time_specs(tags.get("downtime", self.config.default_downtime))

        current_scale = self.get_current_scale(resource)
        original_scale = self.get_original_scale(resource)

        try:
            downtime_scale = int(tags.get("downtime-scale", str(self.config.downtime_scale)))
            if downtime_scale < 0 or downtime_scale > 100:
                logger.warning(
                    "Invalid downtime-scale value, using config default",
                    resource=name,
                    value=downtime_scale,
                )
                downtime_scale = self.config.downtime_scale
        except (ValueError, TypeError):
            logger.warning(
                "Invalid downtime-scale value, using config default",
                resource=name,
                value=tags.get("downtime-scale"),
            )
            downtime_scale = self.config.downtime_scale

        in_grace_period = False
        if self.config.grace_period > 0:
            for window in uptime:
                if window.is_within_grace_period(now, self.config.grace_period):
                    logger.debug("Resource in grace period", resource=name, window=str(window))
                    in_grace_period = True
                    break

        if in_grace_period:
            logger.debug("Resource in grace period, skipping scaling", resource=name)
            return

        target_scale = original_scale

        # Priority order:
        # 1. Uptime window (keep at original scale)
        # 2. Downtime window (scale down)
        # 3. Outside uptime window (scale down)
        if any(window.is_active(now) for window in uptime):
            logger.debug(
                "Resource in uptime window, keeping original scale",
                resource=name,
                scale=original_scale,
            )
        else:
            # Scale down if:
            # 1. We're in a downtime window, or
            # 2. We have uptime windows defined but we're outside them, or
            # 3. We have no uptime windows but have downtime windows
            if (
                any(window.is_active(now) for window in downtime)
                or (uptime and not any(window.is_active(now) for window in uptime))
                or (not uptime and downtime)
            ):
                target_scale = int(original_scale * downtime_scale / 100)
                logger.debug(
                    "Resource outside uptime window, scaling down",
                    resource=name,
                    original_scale=original_scale,
                    downtime_scale=downtime_scale,
                    target_scale=target_scale,
                )
            else:
                logger.debug(
                    "No active windows, keeping original scale", resource=name, scale=original_scale
                )

        if self.config.dry_run:
            logger.info(
                "Would scale resource",
                resource=name,
                from_scale=current_scale,
                to_scale=target_scale,
            )
        else:
            logger.info(
                "Scaling resource", resource=name, from_scale=current_scale, to_scale=target_scale
            )
            self.set_scale(resource, target_scale)
