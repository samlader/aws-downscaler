"""Tests for configuration handling."""

import pytest

from aws_downscaler.config import Config


def test_config_validation():
    """Test configuration validation."""
    # Test valid configuration
    config = Config(
        dry_run=False,
        default_uptime="Mon-Fri 09:00-17:00 UTC",
        default_downtime="Sat-Sun 00:00-23:59 UTC",
        grace_period=300,
        include_resources=["ecs", "rds"],
        exclude_resources=["prod-*"],
        downtime_scale=50,
    )
    assert config.dry_run is False
    assert config.default_uptime == "Mon-Fri 09:00-17:00 UTC"
    assert config.grace_period == 300
    assert config.downtime_scale == 50


def test_invalid_downtime_scale():
    """Test invalid downtime scale validation."""
    # Test negative scale
    with pytest.raises(ValueError, match="downtime_scale must be between 0 and 100"):
        Config(
            dry_run=False,
            default_uptime=None,
            default_downtime=None,
            grace_period=0,
            include_resources=None,
            exclude_resources=None,
            downtime_scale=-1,
        )

    # Test scale > 100
    with pytest.raises(ValueError, match="downtime_scale must be between 0 and 100"):
        Config(
            dry_run=False,
            default_uptime=None,
            default_downtime=None,
            grace_period=0,
            include_resources=None,
            exclude_resources=None,
            downtime_scale=101,
        )


def test_invalid_grace_period():
    """Test invalid grace period validation."""
    with pytest.raises(ValueError, match="grace_period must be non-negative"):
        Config(
            dry_run=False,
            default_uptime=None,
            default_downtime=None,
            grace_period=-1,
            include_resources=None,
            exclude_resources=None,
            downtime_scale=0,
        )


def test_should_process_resource():
    """Test resource filtering based on include/exclude patterns."""
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=["ecs", "rds"],
        exclude_resources=["prod-*", "test-db"],
        downtime_scale=0,
    )

    # Test included resource types
    assert config.should_process_resource("ecs", "dev-service")
    assert config.should_process_resource("rds", "staging-db")
    assert not config.should_process_resource("eks", "dev-cluster")

    # Test excluded resource names
    assert not config.should_process_resource("ecs", "prod-service")
    assert not config.should_process_resource("rds", "test-db")
    assert config.should_process_resource("ecs", "dev-service")


def test_get_resource_tags():
    """Test extracting downscaler tags from AWS resource tags."""
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    aws_tags = [
        {"Key": "Name", "Value": "test-service"},
        {"Key": "downscaler:uptime", "Value": "Mon-Fri 09:00-17:00 UTC"},
        {"Key": "downscaler:downtime-scale", "Value": "0"},
        {"Key": "Environment", "Value": "staging"},
    ]

    tags = config.get_resource_tags(aws_tags)
    assert len(tags) == 2
    assert tags["uptime"] == "Mon-Fri 09:00-17:00 UTC"
    assert tags["downtime-scale"] == "0"
