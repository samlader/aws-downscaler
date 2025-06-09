"""Auto Scaling Group resource handler for AWS Downscaler."""

from typing import Any, Dict, List

import boto3
import structlog

from .base import BaseResource

logger = structlog.get_logger()


class AutoScalingGroupResource(BaseResource):
    """Handler for Auto Scaling Group resources."""

    def __init__(self, session: boto3.Session, config: Any):
        """Initialize ASG resource handler."""
        super().__init__(session, config)
        self.client = session.client("autoscaling")

    def list_resources(self) -> List[Dict[str, Any]]:
        """List all Auto Scaling Groups."""
        paginator = self.client.get_paginator("describe_auto_scaling_groups")
        resources = []

        for page in paginator.paginate():
            resources.extend(page["AutoScalingGroups"])

        return resources

    def get_current_scale(self, resource: Dict[str, Any]) -> int:
        """Get current desired capacity of the ASG."""
        return resource["DesiredCapacity"]

    def get_original_scale(self, resource: Dict[str, Any]) -> int:
        """Get maximum size of the ASG as the original scale."""
        return resource["MaxSize"]

    def set_scale(self, resource: Dict[str, Any], scale: int) -> None:
        """Set the desired capacity of the ASG."""
        asg_name = resource["AutoScalingGroupName"]

        # Ensure we dont exceed the ASG limits
        scale = max(resource["MinSize"], min(scale, resource["MaxSize"]))

        self.client.update_auto_scaling_group(AutoScalingGroupName=asg_name, DesiredCapacity=scale)

        logger.info("Updated Auto Scaling Group capacity", asg=asg_name, capacity=scale)
