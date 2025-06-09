"""ECS Service resource handler for AWS Downscaler."""

from typing import Any, Dict, List

import boto3
import structlog

from .base import BaseResource

logger = structlog.get_logger()


class ECSServiceResource(BaseResource):
    """Handler for ECS Service resources."""

    def __init__(self, session: boto3.Session, config: Any):
        """Initialize ECS resource handler."""
        super().__init__(session, config)
        self.client = session.client("ecs")

    def list_resources(self) -> List[Dict[str, Any]]:
        """List all ECS Services across all clusters."""
        resources = []

        paginator = self.client.get_paginator("list_clusters")
        clusters = []

        for page in paginator.paginate():
            clusters.extend(page["clusterArns"])

        for cluster in clusters:
            paginator = self.client.get_paginator("list_services")
            services = []

            for page in paginator.paginate(cluster=cluster):
                services.extend(page["serviceArns"])

            if services:
                for i in range(0, len(services), 10):
                    batch = services[i : i + 10]
                    response = self.client.describe_services(cluster=cluster, services=batch)
                    resources.extend(response["services"])

        return resources

    def get_current_scale(self, resource: Dict[str, Any]) -> int:
        """Get current desired count of the ECS service."""
        return resource["desiredCount"]

    def get_original_scale(self, resource: Dict[str, Any]) -> int:
        """Get maximum count from deployment configuration."""
        if "deploymentConfiguration" in resource:
            config = resource["deploymentConfiguration"]
            if "maximumPercent" in config:
                base_count = resource.get("desiredCount", 1)
                return int(base_count * config["maximumPercent"] / 100)
        return resource.get("desiredCount", 1)

    def set_scale(self, resource: Dict[str, Any], scale: int) -> None:
        """Set the desired count of the ECS service."""
        cluster = resource["clusterArn"]
        service = resource["serviceName"]

        self.client.update_service(cluster=cluster, service=service, desiredCount=scale)

        logger.info(
            "Updated ECS service desired count", cluster=cluster, service=service, count=scale
        )
