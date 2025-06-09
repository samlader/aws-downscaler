"""Tests for the ECS resource handler."""

from datetime import datetime, timezone
from typing import Any, Dict

import boto3
import pytest
from moto import mock_aws

from aws_downscaler.config import Config
from aws_downscaler.resources.ecs import ECSServiceResource


@pytest.fixture
def ecs_client(aws_credentials):
    """Create mock ECS client."""
    with mock_aws():
        yield boto3.client("ecs", region_name="us-east-1")


@pytest.fixture
def test_cluster(ecs_client):
    """Create a test ECS cluster."""
    response = ecs_client.create_cluster(clusterName="test-cluster")
    return response["cluster"]["clusterArn"]


@pytest.fixture
def test_service(ecs_client, test_cluster):
    """Create a test ECS service."""

    task_def = ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "test", "image": "test:latest", "cpu": 256, "memory": 512, "essential": True}
        ],
    )

    response = ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition=task_def["taskDefinition"]["taskDefinitionArn"],
        desiredCount=3,
        deploymentConfiguration={
            "maximumPercent": 167,
            "minimumHealthyPercent": 100,
        },
        tags=[
            {"key": "Name", "value": "test-service"},
            {"key": "downscaler:uptime", "value": "Mon-Fri 09:00-17:00 UTC"},
        ],
    )

    return response["service"]["serviceArn"]


def test_list_resources(ecs_client, test_service):
    """Test listing ECS services."""
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

    handler = ECSServiceResource(session, config)
    resources = handler.list_resources()

    assert len(resources) == 1
    assert resources[0]["serviceName"] == "test-service"
    assert resources[0]["desiredCount"] == 3


def test_get_current_scale(ecs_client, test_service):
    """Test getting current scale of ECS service."""
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

    handler = ECSServiceResource(session, config)
    resources = handler.list_resources()

    scale = handler.get_current_scale(resources[0])
    assert scale == 3


def test_get_original_scale(ecs_client, test_service):
    """Test getting original scale of ECS service."""
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

    handler = ECSServiceResource(session, config)
    resources = handler.list_resources()

    scale = handler.get_original_scale(resources[0])
    assert scale == 3


def test_set_scale(ecs_client, test_service):
    """Test setting scale of ECS service."""
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

    handler = ECSServiceResource(session, config)
    resources = handler.list_resources()

    handler.set_scale(resources[0], 1)
    updated = handler.list_resources()[0]
    assert updated["desiredCount"] == 1

    handler.set_scale(resources[0], 4)
    updated = handler.list_resources()[0]
    assert updated["desiredCount"] == 4


@mock_aws
def test_scale_down_ecs():
    """Test scaling down ECS service during downtime hours."""

    session = boto3.Session()
    ecs_client = session.client("ecs", region_name="us-east-1")

    ecs_client.create_cluster(clusterName="test-cluster")

    task_def = ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "test", "image": "test:latest", "cpu": 256, "memory": 512, "essential": True}
        ],
    )

    service = ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition=task_def["taskDefinition"]["taskDefinitionArn"],
        desiredCount=3,
        tags=[
            {"key": "downscaler:uptime", "value": "Mon-Fri 09:00-17:00 UTC"},
            {"key": "downscaler:downtime-scale", "value": "0"},
        ],
    )

    config = Config(
        dry_run=False,
        default_uptime=None,
        default_downtime="Sat-Sun 00:00-23:59 UTC",
        grace_period=0,
        include_resources=None,
        exclude_resources=None,
        downtime_scale=0,
    )

    handler = ECSServiceResource(session, config)
    resources = handler.list_resources()

    assert len(resources) == 1
    assert resources[0]["desiredCount"] == 3

    current_time = datetime(2024, 3, 16, 12, 0, tzinfo=timezone.utc)

    handler.check_and_scale(current_time)

    updated_resources = handler.list_resources()
    assert updated_resources[0]["desiredCount"] == 0
