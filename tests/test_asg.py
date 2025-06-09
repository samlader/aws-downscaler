"""Tests for the Auto Scaling Group resource handler."""

from datetime import datetime, timezone
from typing import Any, Dict

import boto3
import pytest
from moto import mock_aws

from aws_downscaler.config import Config
from aws_downscaler.resources.asg import AutoScalingGroupResource


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def asg_client(aws_credentials):
    """Create mock ASG client."""
    with mock_aws():
        yield boto3.client("autoscaling", region_name="us-east-1")


@pytest.fixture
def test_asg(asg_client):
    """Create a test Auto Scaling Group."""
    asg_client.create_launch_configuration(
        LaunchConfigurationName="test-lc", ImageId="ami-12345678", InstanceType="t2.micro"
    )

    asg_client.create_auto_scaling_group(
        AutoScalingGroupName="test-asg",
        LaunchConfigurationName="test-lc",
        MinSize=1,
        MaxSize=5,
        DesiredCapacity=3,
        AvailabilityZones=["us-east-1a"],
        Tags=[
            {"Key": "Name", "Value": "test-asg", "PropagateAtLaunch": True},
            {
                "Key": "downscaler:uptime",
                "Value": "Mon-Fri 09:00-17:00 UTC",
                "PropagateAtLaunch": False,
            },
        ],
    )

    return "test-asg"


def test_list_resources(asg_client, test_asg):
    """Test listing Auto Scaling Groups."""
    session = boto3.Session()
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = AutoScalingGroupResource(session, config)
    resources = handler.list_resources()

    assert len(resources) == 1
    assert resources[0]["AutoScalingGroupName"] == test_asg
    assert resources[0]["MinSize"] == 1
    assert resources[0]["MaxSize"] == 5
    assert resources[0]["DesiredCapacity"] == 3


def test_get_current_scale(asg_client, test_asg):
    """Test getting current scale of ASG."""
    session = boto3.Session()
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = AutoScalingGroupResource(session, config)
    resources = handler.list_resources()

    scale = handler.get_current_scale(resources[0])
    assert scale == 3


def test_get_original_scale(asg_client, test_asg):
    """Test getting original (maximum) scale of ASG."""
    session = boto3.Session()
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = AutoScalingGroupResource(session, config)
    resources = handler.list_resources()

    scale = handler.get_original_scale(resources[0])
    assert scale == 5


def test_set_scale(asg_client, test_asg):
    """Test setting scale of ASG."""
    session = boto3.Session()
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = AutoScalingGroupResource(session, config)
    resources = handler.list_resources()

    handler.set_scale(resources[0], 1)
    updated = handler.list_resources()[0]
    assert updated["DesiredCapacity"] == 1

    handler.set_scale(resources[0], 4)
    updated = handler.list_resources()[0]
    assert updated["DesiredCapacity"] == 4

    handler.set_scale(resources[0], 10)
    updated = handler.list_resources()[0]
    assert updated["DesiredCapacity"] == 5

    handler.set_scale(resources[0], 0)
    updated = handler.list_resources()[0]
    assert updated["DesiredCapacity"] == 1


@mock_aws
def test_scale_down_asg():
    """Test scaling down ASG during downtime hours."""

    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    client = boto3.client("autoscaling", region_name="us-east-1")

    client.create_launch_configuration(
        LaunchConfigurationName="test-lc", ImageId="ami-12345678", InstanceType="t2.micro"
    )

    client.create_auto_scaling_group(
        AutoScalingGroupName="test-asg",
        LaunchConfigurationName="test-lc",
        MinSize=1,
        MaxSize=5,
        DesiredCapacity=3,
        AvailabilityZones=["us-east-1a"],
        Tags=[
            {"Key": "Name", "Value": "test-asg", "PropagateAtLaunch": True},
            {
                "Key": "downscaler:uptime",
                "Value": "Mon-Fri 09:00-17:00 UTC",
                "PropagateAtLaunch": False,
            },
        ],
    )

    session = boto3.Session()
    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime=None,
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = AutoScalingGroupResource(session, config)
    resources = handler.list_resources()

    now = datetime.now(timezone.utc)
    handler._process_resource(resources[0], now)
    updated = handler.list_resources()[0]
    assert updated["DesiredCapacity"] == 1
