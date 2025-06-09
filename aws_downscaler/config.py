"""Configuration handling for AWS Downscaler."""

import fnmatch
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Config:
    """Configuration settings for AWS Downscaler."""

    dry_run: bool
    default_uptime: Optional[str]
    default_downtime: Optional[str]
    grace_period: int
    include_resources: Optional[List[str]]
    exclude_resources: Optional[List[str]]
    downtime_scale: int

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.downtime_scale < 0 or self.downtime_scale > 100:
            raise ValueError("downtime_scale must be between 0 and 100")

        if self.grace_period < 0:
            raise ValueError("grace_period must be non-negative")

    def should_process_resource(self, resource_type: str, resource_name: str) -> bool:
        """Check if a resource should be processed based on include/exclude patterns."""
        if self.include_resources and resource_type not in self.include_resources:
            return False

        if self.exclude_resources:
            for pattern in self.exclude_resources:
                if pattern.endswith("*"):
                    if fnmatch.fnmatch(resource_name, pattern):
                        return False
                elif pattern == resource_name:
                    return False

        return True

    def get_resource_tags(self, aws_tags: List[Dict[str, str]]) -> Dict[str, str]:
        """Extract relevant downscaler tags from AWS resource tags."""
        tags = {}
        for tag in aws_tags:
            key = tag.get("Key", "").lower()
            if key.startswith("downscaler:"):
                tags[key.replace("downscaler:", "")] = tag.get("Value", "")
        return tags
