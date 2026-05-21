"""
JADX MCP Server - Instance Auto-Scaling Tools

Provides Docker-based JADX worker instance management. Allows scaling
the number of JADX analysis containers up or down via the Docker SDK.

Requires the ``docker`` Python package. All Docker operations are wrapped
in ImportError guards so the tools degrade gracefully when the package
is unavailable.

Author: jadx-ai-mcp contributors
License: See LICENSE file
"""

from typing import Optional

from src.server.logging_config import get_logger

logger = get_logger("scaling_tools")

# Container naming convention
_CONTAINER_PREFIX = "jadx-ai-mcp-worker-"

# Internal container port that JADX listens on
_INTERNAL_PORT = 8651

# Scaling bounds
_MIN_INSTANCES = 1
_MAX_INSTANCES = 10


def _docker_unavailable_error() -> dict:
    """Return a friendly error when the docker package is missing."""
    return {
        "error": "DOCKER_UNAVAILABLE",
        "message": (
            "The 'docker' Python package is not installed. "
            "Install it with: pip install docker"
        ),
    }


def _get_docker_client():
    """Try to create a Docker client. Returns (client, None) or (None, error_dict)."""
    try:
        import docker  # noqa: F811
    except ImportError:
        return None, _docker_unavailable_error()

    try:
        client = docker.from_env()
        client.ping()
        return client, None
    except Exception as exc:
        return None, {
            "error": "DOCKER_CONNECTION_FAILED",
            "message": f"Cannot connect to Docker daemon: {exc}",
        }


def _list_worker_containers(client) -> list:
    """List all containers matching the worker naming prefix."""
    all_containers = client.containers.list(all=True)
    workers = [
        c for c in all_containers if c.name.startswith(_CONTAINER_PREFIX)
    ]
    # Sort by name suffix (numeric) for deterministic ordering
    workers.sort(key=lambda c: c.name)
    return workers


def _container_info(container, base_port: int = 0) -> dict:
    """Extract status info from a Docker container object."""
    # Try to read the host port from port bindings
    port = 0
    ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
    tcp_key = f"{_INTERNAL_PORT}/tcp"
    if tcp_key in ports and ports[tcp_key]:
        try:
            port = int(ports[tcp_key][0].get("HostPort", 0))
        except (IndexError, ValueError, TypeError):
            pass

    # Memory limit from HostConfig
    mem_limit = container.attrs.get("HostConfig", {}).get("Memory", 0)
    if mem_limit and mem_limit > 0:
        mem_str = f"{mem_limit // (1024 ** 3)}g" if mem_limit >= 1024 ** 3 else f"{mem_limit // (1024 ** 2)}m"
    else:
        mem_str = "unlimited"

    # Uptime from state
    started_at = (
        container.attrs.get("State", {}).get("StartedAt", "")
    )

    return {
        "name": container.name,
        "port": port,
        "status": container.status,
        "memory_limit": mem_str,
        "started_at": started_at,
    }


async def scale_instances(
    desired_count: int,
    image: str = "xjoker/jadx-ai-mcp:latest",
    base_port: int = 8652,
    memory_limit: str = "4g",
) -> dict:
    """
    Scale JADX worker instances to the desired count via Docker.

    Creates or removes Docker containers named ``jadx-ai-mcp-worker-N``.
    Each container maps ``base_port + N`` on the host to port 8651 inside
    the container.

    Args:
        desired_count: Target number of worker instances (1-10).
        image: Docker image to use for new containers.
        base_port: Host port base; instance N gets ``base_port + N``.
        memory_limit: Docker memory limit string (e.g., "4g", "2048m").

    Returns:
        dict: Scaling result with created/removed container details.

    MCP Tool: scale_instances
    Description: Scale JADX Docker worker instances up or down to the desired count
    """
    logger.info(
        f"scale_instances: desired={desired_count}, image={image}, "
        f"base_port={base_port}, mem={memory_limit}"
    )

    # Validate desired_count
    if not isinstance(desired_count, int) or desired_count < _MIN_INSTANCES or desired_count > _MAX_INSTANCES:
        return {
            "error": "INVALID_INPUT",
            "message": f"desired_count must be an integer between {_MIN_INSTANCES} and {_MAX_INSTANCES}",
            "desired_count": desired_count,
        }

    client, err = _get_docker_client()
    if err:
        return err

    existing = _list_worker_containers(client)
    previous_count = len(existing)

    created: list[dict] = []
    removed: list[dict] = []

    if previous_count < desired_count:
        # Scale up: create missing containers
        # Determine which indices are already taken
        existing_indices: set[int] = set()
        for c in existing:
            suffix = c.name[len(_CONTAINER_PREFIX):]
            try:
                existing_indices.add(int(suffix))
            except ValueError:
                pass

        needed = desired_count - previous_count
        next_index = 0
        while len(created) < needed:
            if next_index not in existing_indices:
                name = f"{_CONTAINER_PREFIX}{next_index}"
                host_port = base_port + next_index
                try:
                    container = client.containers.run(
                        image,
                        name=name,
                        detach=True,
                        ports={f"{_INTERNAL_PORT}/tcp": host_port},
                        mem_limit=memory_limit,
                        restart_policy={"Name": "unless-stopped"},
                        environment={"TZ": "UTC"},
                    )
                    created.append({
                        "name": name,
                        "port": host_port,
                        "status": container.status,
                    })
                    logger.info(f"Created container {name} on port {host_port}")
                except Exception as exc:
                    logger.warning(f"Failed to create container {name}: {exc}")
                    created.append({
                        "name": name,
                        "port": host_port,
                        "status": f"error: {exc}",
                    })
            next_index += 1
            # Safety valve to avoid infinite loops
            if next_index > _MAX_INSTANCES + previous_count + 10:
                break

    elif previous_count > desired_count:
        # Scale down: remove excess containers (last ones first)
        to_remove = existing[desired_count:]
        for container in reversed(to_remove):
            try:
                container.stop(timeout=10)
                container.remove()
                removed.append({"name": container.name})
                logger.info(f"Removed container {container.name}")
            except Exception as exc:
                logger.warning(f"Failed to remove container {container.name}: {exc}")
                removed.append({"name": container.name, "error": str(exc)})

    # Refresh container list
    current_containers = _list_worker_containers(client)
    all_instances = [_container_info(c) for c in current_containers]

    return {
        "previous_count": previous_count,
        "current_count": len(current_containers),
        "desired_count": desired_count,
        "created": created,
        "removed": removed,
        "all_instances": all_instances,
    }


async def get_scaling_status() -> dict:
    """
    Get status of all JADX worker containers.

    Returns name, status, port, memory limit, and start time for each
    container matching the ``jadx-ai-mcp-worker-`` naming convention.

    Returns:
        dict: List of worker container statuses, or error if Docker is unavailable.

    MCP Tool: get_scaling_status
    Description: Report status of all JADX Docker worker containers
    """
    logger.info("get_scaling_status")

    client, err = _get_docker_client()
    if err:
        return err

    workers = _list_worker_containers(client)
    instances = [_container_info(c) for c in workers]

    return {
        "total_workers": len(instances),
        "instances": instances,
    }


def register_scaling_tools(mcp):
    """Register scaling tools with the MCP server.

    These tools do not call the JADX API, so ``with_busy_check`` is not needed.
    """

    @mcp.tool()
    async def scale_instances_tool(
        desired_count: int,
        image: str = "xjoker/jadx-ai-mcp:latest",
        base_port: int = 8652,
        memory_limit: str = "4g",
    ) -> dict:
        """Scale JADX Docker worker containers to desired count (1-10). Creates/removes jadx-ai-mcp-worker-N.

        Args:
            desired_count: Target count (1-10). image: Docker image. base_port: Host port base.
            memory_limit: Docker memory limit (e.g., "4g").
        Returns:
            dict: {previous_count, current_count, created: [...], removed: [...], all_instances}
        """
        return await scale_instances(
            desired_count, image=image, base_port=base_port, memory_limit=memory_limit,
        )

    @mcp.tool()
    async def get_scaling_status_tool() -> dict:
        """Get status of all JADX Docker worker containers (name, port, status, memory, uptime).

        Returns:
            dict: {total_workers: int, instances: [{name, port, status, memory_limit, started_at}]}
        """
        return await get_scaling_status()

    logger.info("Scaling tools registered: scale_instances, get_scaling_status")
