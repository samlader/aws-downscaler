"""Tests for the base resource class."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
import pytz
from freezegun import freeze_time

from aws_downscaler.config import Config
from aws_downscaler.resources.base import BaseResource
from aws_downscaler.schedule import TimeWindow


class TestResource(BaseResource):
    """Test resource class for unit tests."""

    def __init__(self, session, config):
        super().__init__(session, config)
        self.scale_called = False
        self.scale_args = None

    def list_resources(self):
        return [
            {
                "ResourceId": "test-1",
                "Name": "test-1",
                "current_scale": 10,
                "original_scale": 10,
                "Tags": [],
            }
        ]

    def get_resource_name(self, resource):
        """Get resource name from Name, Id, or ResourceId."""
        return resource.get("Name") or resource.get("Id") or resource.get("ResourceId") or "unknown"

    def get_resource_tags(self, resource):
        """Get resource tags, stripping downscaler: prefix."""
        tags = {}
        for tag in resource.get("Tags", []):
            key = tag["Key"]
            if key.startswith("downscaler:"):
                key = key.replace("downscaler:", "")
                tags[key] = tag["Value"]
        return tags

    def get_current_scale(self, resource):
        return resource["current_scale"]

    def get_original_scale(self, resource):
        return resource["original_scale"]

    def set_scale(self, resource, scale):
        self.scale_called = True
        self.scale_args = (resource, scale)
        resource["current_scale"] = scale


def test_get_resource_name():
    """Test resource name extraction."""
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    resource = TestResource(None, config)

    assert resource.get_resource_name({"Name": "test"}) == "test"

    assert resource.get_resource_name({"Id": "test-id"}) == "test-id"

    assert resource.get_resource_name({}) == "unknown"


def test_get_resource_tags():
    """Test resource tag extraction."""
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    resource = TestResource(None, config)

    tags = resource.get_resource_tags(
        {
            "Tags": [
                {"Key": "downscaler:uptime", "Value": "Mon-Fri 09:00-17:00 UTC"},
                {"Key": "Name", "Value": "test"},
            ]
        }
    )

    assert "uptime" in tags
    assert tags["uptime"] == "Mon-Fri 09:00-17:00 UTC"
    assert "Name" not in tags

    assert resource.get_resource_tags({}) == {}


def test_should_process():
    """Test resource processing rules."""
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    resource = TestResource(None, config)
    now = datetime(2024, 1, 1, 12, 0, tzinfo=pytz.UTC)

    assert resource.should_process({"ResourceId": "test-1", "Tags": []}, now)

    assert not resource.should_process(
        {"ResourceId": "test-2", "Tags": [{"Key": "downscaler:exclude", "Value": "true"}]}, now
    )

    assert not resource.should_process(
        {
            "ResourceId": "test-3",
            "Tags": [{"Key": "downscaler:exclude-until", "Value": "2024-01-02T12:00:00Z"}],
        },
        now,
    )

    now = datetime(2024, 1, 3, 12, 0, tzinfo=pytz.UTC)
    assert resource.should_process(
        {
            "ResourceId": "test-3",
            "Tags": [{"Key": "downscaler:exclude-until", "Value": "2024-01-02T12:00:00Z"}],
        },
        now,
    )


@freeze_time("2024-01-01 14:30:00 UTC")
def test_process_resource():
    """Test resource processing logic."""
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=50,
    )

    resource = TestResource(None, config)
    test_resource = {
        "ResourceId": "test-1",
        "Name": "test-1",
        "current_scale": 10,
        "original_scale": 10,
        "Tags": [],
    }

    now = datetime(2024, 1, 1, 6, 0, tzinfo=pytz.UTC)
    resource._process_resource(test_resource, now)
    assert resource.scale_called
    assert resource.scale_args[1] == 5


def test_check_and_scale():
    """Test resource scaling based on time windows."""
    session = MagicMock()
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=50,
    )

    resource = TestResource(session, config)

    now = datetime(2024, 3, 13, 10, 0, tzinfo=pytz.UTC)
    resource.check_and_scale(now)

    assert resource.scale_called
    assert resource.scale_args[0]["ResourceId"] == "test-1"
    assert resource.scale_args[1] == 10


def test_dry_run():
    """Test dry run mode."""
    session = MagicMock()
    config = Config(
        dry_run=True,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=50,
    )

    resource = TestResource(session, config)

    now = datetime(2024, 3, 13, 10, 0, tzinfo=pytz.UTC)
    resource.check_and_scale(now)

    assert not resource.scale_called


def test_excluded_resource():
    """Test handling of excluded resources."""
    session = MagicMock()
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=50,
    )

    class ExcludedResource(TestResource):
        def list_resources(self):
            return [
                {
                    "ResourceId": "test-1",
                    "Name": "test-1",
                    "current_scale": 10,
                    "original_scale": 10,
                    "Tags": [{"Key": "downscaler:exclude", "Value": "true"}],
                }
            ]

    resource = ExcludedResource(session, config)

    now = datetime(2024, 3, 13, 10, 0, tzinfo=pytz.UTC)
    resource.check_and_scale(now)

    assert not resource.scale_called


def test_grace_period():
    """Test grace period handling."""
    session = MagicMock()
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=300,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=50,
    )

    resource = TestResource(session, config)

    now = datetime(2024, 3, 13, 17, 3, tzinfo=pytz.UTC)
    resource.check_and_scale(now)

    assert not resource.scale_called

    now = datetime(2024, 3, 13, 17, 6, tzinfo=pytz.UTC)
    resource.scale_called = False
    resource.check_and_scale(now)

    assert resource.scale_called
    assert resource.scale_args[1] == 5


def test_custom_downtime_scale():
    """Test custom downtime scale from tags."""
    session = MagicMock()
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    class CustomScaleResource(TestResource):
        def list_resources(self):
            return [
                {
                    "ResourceId": "test-1",
                    "Name": "test-1",
                    "current_scale": 10,
                    "original_scale": 10,
                    "Tags": [
                        {"Key": "downscaler:uptime", "Value": "Mon-Fri 09:00-17:00 UTC"},
                        {"Key": "downscaler:downtime-scale", "Value": "50"},
                    ],
                }
            ]

    resource = CustomScaleResource(session, config)

    now = datetime(2024, 3, 13, 18, 0, tzinfo=pytz.UTC)
    resource.check_and_scale(now)

    assert resource.scale_called
    assert resource.scale_args[1] == 5
