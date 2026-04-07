"""
Unit tests for instance auto-scaling tools.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from server.tools.scaling_tools import (
    _CONTAINER_PREFIX,
    _MAX_INSTANCES,
    _MIN_INSTANCES,
    get_scaling_status,
    scale_instances,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_container(name: str, status: str = "running", host_port: int = 8652, memory: int = 0) -> MagicMock:
    """Create a mock Docker container."""
    c = MagicMock()
    c.name = name
    c.status = status
    c.attrs = {
        "NetworkSettings": {
            "Ports": {
                "8651/tcp": [{"HostPort": str(host_port)}],
            },
        },
        "HostConfig": {"Memory": memory},
        "State": {"StartedAt": "2026-04-07T00:00:00Z"},
    }
    return c


def _mock_docker_client(containers: list[MagicMock] | None = None) -> MagicMock:
    """Create a mock Docker client with optional pre-existing containers."""
    client = MagicMock()
    client.ping.return_value = True
    all_containers = containers or []
    client.containers.list.return_value = all_containers

    def _run(image, **kwargs):
        c = MagicMock()
        c.name = kwargs.get("name", "test")
        c.status = "running"
        return c

    client.containers.run.side_effect = _run
    return client


# ---------------------------------------------------------------------------
# Docker unavailable tests
# ---------------------------------------------------------------------------

class TestDockerUnavailable:
    """Verify graceful handling when the docker package is missing."""

    @pytest.mark.asyncio
    async def test_scale_instances_without_docker(self):
        with patch.dict(sys.modules, {"docker": None}):
            # Force reimport to pick up the mocked module state
            with patch("server.tools.scaling_tools._get_docker_client") as mock_get:
                mock_get.return_value = (None, {
                    "error": "DOCKER_UNAVAILABLE",
                    "message": "The 'docker' Python package is not installed. Install it with: pip install docker",
                })
                result = await scale_instances(desired_count=2)

        assert result["error"] == "DOCKER_UNAVAILABLE"
        assert "pip install docker" in result["message"]

    @pytest.mark.asyncio
    async def test_get_scaling_status_without_docker(self):
        with patch("server.tools.scaling_tools._get_docker_client") as mock_get:
            mock_get.return_value = (None, {
                "error": "DOCKER_UNAVAILABLE",
                "message": "The 'docker' Python package is not installed.",
            })
            result = await get_scaling_status()

        assert result["error"] == "DOCKER_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Tests for desired_count range enforcement."""

    @pytest.mark.asyncio
    async def test_desired_count_below_minimum(self):
        result = await scale_instances(desired_count=0)
        assert result["error"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_desired_count_above_maximum(self):
        result = await scale_instances(desired_count=11)
        assert result["error"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_desired_count_negative(self):
        result = await scale_instances(desired_count=-1)
        assert result["error"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_min_max_constants(self):
        assert _MIN_INSTANCES == 1
        assert _MAX_INSTANCES == 10


# ---------------------------------------------------------------------------
# Scale up tests
# ---------------------------------------------------------------------------

class TestScaleUp:
    """Tests for creating new containers."""

    @pytest.mark.asyncio
    async def test_scale_up_from_zero(self):
        client = _mock_docker_client(containers=[])
        # After creation, list returns the new containers
        created_containers = [_make_container(f"{_CONTAINER_PREFIX}{i}", host_port=8652 + i) for i in range(2)]
        client.containers.list.side_effect = [[], created_containers]

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await scale_instances(desired_count=2)

        assert result["previous_count"] == 0
        assert result["desired_count"] == 2
        assert len(result["created"]) == 2
        assert result["created"][0]["name"] == f"{_CONTAINER_PREFIX}0"
        assert result["created"][1]["name"] == f"{_CONTAINER_PREFIX}1"

    @pytest.mark.asyncio
    async def test_scale_up_preserves_existing(self):
        existing = [_make_container(f"{_CONTAINER_PREFIX}0", host_port=8652)]
        after = existing + [_make_container(f"{_CONTAINER_PREFIX}1", host_port=8653)]
        client = _mock_docker_client(containers=existing)
        client.containers.list.side_effect = [existing, after]

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await scale_instances(desired_count=2)

        assert result["previous_count"] == 1
        assert len(result["created"]) == 1
        assert result["created"][0]["name"] == f"{_CONTAINER_PREFIX}1"

    @pytest.mark.asyncio
    async def test_container_run_called_with_correct_params(self):
        client = _mock_docker_client(containers=[])
        client.containers.list.side_effect = [[], []]

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            await scale_instances(
                desired_count=1, image="custom:v2", base_port=9000, memory_limit="2g",
            )

        call_kwargs = client.containers.run.call_args
        assert call_kwargs[0][0] == "custom:v2"  # image
        assert call_kwargs[1]["mem_limit"] == "2g"
        assert call_kwargs[1]["environment"] == {"TZ": "UTC"}
        assert call_kwargs[1]["restart_policy"] == {"Name": "unless-stopped"}


# ---------------------------------------------------------------------------
# Scale down tests
# ---------------------------------------------------------------------------

class TestScaleDown:
    """Tests for removing excess containers."""

    @pytest.mark.asyncio
    async def test_scale_down_removes_last(self):
        containers = [
            _make_container(f"{_CONTAINER_PREFIX}0", host_port=8652),
            _make_container(f"{_CONTAINER_PREFIX}1", host_port=8653),
            _make_container(f"{_CONTAINER_PREFIX}2", host_port=8654),
        ]
        after = containers[:1]
        client = _mock_docker_client(containers=containers)
        client.containers.list.side_effect = [containers, after]

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await scale_instances(desired_count=1)

        assert result["previous_count"] == 3
        assert len(result["removed"]) == 2
        # Containers 1 and 2 should have been stopped and removed
        containers[1].stop.assert_called_once()
        containers[1].remove.assert_called_once()
        containers[2].stop.assert_called_once()
        containers[2].remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_change_when_already_at_desired(self):
        containers = [_make_container(f"{_CONTAINER_PREFIX}0", host_port=8652)]
        client = _mock_docker_client(containers=containers)
        client.containers.list.side_effect = [containers, containers]

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await scale_instances(desired_count=1)

        assert result["previous_count"] == 1
        assert result["created"] == []
        assert result["removed"] == []


# ---------------------------------------------------------------------------
# get_scaling_status tests
# ---------------------------------------------------------------------------

class TestGetScalingStatus:
    """Tests for the status reporting function."""

    @pytest.mark.asyncio
    async def test_returns_all_workers(self):
        containers = [
            _make_container(f"{_CONTAINER_PREFIX}0", host_port=8652, memory=4 * 1024**3),
            _make_container(f"{_CONTAINER_PREFIX}1", host_port=8653, status="exited"),
        ]
        client = _mock_docker_client(containers=containers)

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await get_scaling_status()

        assert result["total_workers"] == 2
        assert result["instances"][0]["name"] == f"{_CONTAINER_PREFIX}0"
        assert result["instances"][0]["status"] == "running"
        assert result["instances"][0]["memory_limit"] == "4g"
        assert result["instances"][1]["status"] == "exited"

    @pytest.mark.asyncio
    async def test_empty_when_no_workers(self):
        client = _mock_docker_client(containers=[])

        with patch("server.tools.scaling_tools._get_docker_client", return_value=(client, None)):
            result = await get_scaling_status()

        assert result["total_workers"] == 0
        assert result["instances"] == []
