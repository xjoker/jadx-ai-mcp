"""JADX MCP Server — Workflow Tools

High-level tools that compose existing primitives (instance registry, file
loading, decompile status) into AI-friendly single-call operations.

Two tools are exposed:
- analyze_apk(path, strategy) — smart file routing with auto-strategy
- list_loaded_files()          — aggregated view of what each instance holds
"""

from typing import Optional

import httpx

from ..instance_registry import InstanceRegistry
from ..logging_config import get_logger
from ..user_auth import UserAuthManager

logger = get_logger("workflow_tools")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NO_FILE_SIGNALS = ("no file", "no apk", "not loaded", "")


def _instance_has_no_file(apk_info: dict) -> bool:
    """Return True when apk_info indicates the instance has no file loaded."""
    if not apk_info:
        return True
    pkg = apk_info.get("apk_package", "").lower().strip()
    fname = apk_info.get("file_name", "").lower().strip()
    status = apk_info.get("status", "").lower().strip()
    # Any of these signals "nothing loaded"
    if pkg in _NO_FILE_SIGNALS or status in ("no_file", "no file", "empty"):
        return True
    if not pkg and not fname:
        return True
    return False


async def _fetch_apk_info(instance) -> dict:
    """Fetch /apk-info from an instance; return {} on failure."""
    try:
        token = instance.token or InstanceRegistry.get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{instance.url}/apk-info", headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.debug(f"_fetch_apk_info({instance.name}): {exc}")
        return {}


async def _fetch_decompile_status(instance) -> dict:
    """Fetch /decompile-status from an instance; return {} on failure."""
    try:
        token = instance.token or InstanceRegistry.get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{instance.url}/decompile-status", headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.debug(f"_fetch_decompile_status({instance.name}): {exc}")
        return {}


async def _load_file_on_instance(instance, path: str, mode: str = "replace") -> dict:
    """POST /load-file to a specific instance. Returns the raw response dict."""
    try:
        token = instance.token or InstanceRegistry.get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{instance.url}/load-file",
                json={"path": path, "mode": mode},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
    except Exception as exc:
        logger.error(f"_load_file_on_instance({instance.name}): {exc}")
        return {"error": f"{type(exc).__name__}: {exc}"}


def _instance_summary(instance) -> dict:
    """Return a small summary dict for an instance."""
    return {
        "name": instance.name,
        "host": instance.host,
        "port": instance.port,
    }


# ---------------------------------------------------------------------------
# Core logic functions (testable without MCP)
# ---------------------------------------------------------------------------

async def analyze_apk(
    path: str,
    strategy: str = "auto",
    instance_id: Optional[str] = None,
) -> dict:
    """Smart APK loading with automatic instance routing.

    Behavior per strategy:
    - "auto": inspect instance landscape and route intelligently
    - "replace": load on default instance (drop whatever is there)
    - "new_instance": find a free instance or return guidance to scale
    - "append": append on default instance (adds JAR deps to open project)

    Args:
        path: Sandbox-relative path (e.g. "target.apk").
        strategy: auto | replace | new_instance | append
        instance_id: Optional override — target this specific instance.

    Returns:
        dict with status, instance, path, ready, poll_with, next_steps.
    """
    if strategy not in ("auto", "replace", "new_instance", "append"):
        return {
            "status": "error",
            "instance": None,
            "path": path,
            "ready": False,
            "poll_with": None,
            "next_steps": [
                f"strategy must be one of: auto, replace, new_instance, append — got '{strategy}'"
            ],
        }

    # Resolve user context for access control
    user = UserAuthManager.get_current_user()
    username = user.name if user else None
    is_admin = user.is_admin if user else False

    # -------------------------------------------------------------------------
    # strategy="replace"
    # -------------------------------------------------------------------------
    if strategy == "replace":
        target = (
            InstanceRegistry.get_instance(instance_id)
            if instance_id
            else InstanceRegistry.get_default_for_user(username, is_admin)
        )
        if not target:
            return {
                "status": "error",
                "instance": None,
                "path": path,
                "ready": False,
                "poll_with": None,
                "next_steps": ["No JADX instance available. Add one with add_jadx_instance."],
            }
        result = await _load_file_on_instance(target, path, mode="replace")
        if "error" in result:
            return {
                "status": "error",
                "instance": _instance_summary(target),
                "path": path,
                "ready": False,
                "poll_with": None,
                "next_steps": [result["error"]],
            }
        return {
            "status": "loaded",
            "instance": _instance_summary(target),
            "path": path,
            "ready": False,
            "poll_with": "get_decompile_status",
            "next_steps": ["File is loading. Poll get_decompile_status until cached_percentage stabilises."],
        }

    # -------------------------------------------------------------------------
    # strategy="append"
    # -------------------------------------------------------------------------
    if strategy == "append":
        target = (
            InstanceRegistry.get_instance(instance_id)
            if instance_id
            else InstanceRegistry.get_default_for_user(username, is_admin)
        )
        if not target:
            return {
                "status": "error",
                "instance": None,
                "path": path,
                "ready": False,
                "poll_with": None,
                "next_steps": ["No JADX instance available. Add one with add_jadx_instance."],
            }
        result = await _load_file_on_instance(target, path, mode="append")
        if "error" in result:
            return {
                "status": "error",
                "instance": _instance_summary(target),
                "path": path,
                "ready": False,
                "poll_with": None,
                "next_steps": [result["error"]],
            }
        return {
            "status": "loaded",
            "instance": _instance_summary(target),
            "path": path,
            "ready": False,
            "poll_with": "get_decompile_status",
            "next_steps": [
                "Dependency appended to open project. "
                "Poll get_decompile_status until cached_percentage stabilises."
            ],
        }

    # -------------------------------------------------------------------------
    # strategy="new_instance"
    # -------------------------------------------------------------------------
    if strategy == "new_instance":
        all_instances = InstanceRegistry.list_instances_for_user(username, is_admin)
        connected = [i for i in all_instances if i.get("status") == "connected"]

        # Find a free connected instance
        for inst_dict in connected:
            inst = InstanceRegistry.get_instance(inst_dict["name"])
            if inst is None:
                continue
            apk_info = await _fetch_apk_info(inst)
            if _instance_has_no_file(apk_info):
                result = await _load_file_on_instance(inst, path, mode="replace")
                if "error" in result:
                    continue  # try next free instance
                return {
                    "status": "loaded",
                    "instance": _instance_summary(inst),
                    "path": path,
                    "ready": False,
                    "poll_with": "get_decompile_status",
                    "next_steps": [
                        f"Loaded on free instance '{inst.name}'. "
                        "Poll get_decompile_status until cached_percentage stabilises."
                    ],
                }

        return {
            "status": "all_busy",
            "instance": None,
            "path": path,
            "ready": False,
            "poll_with": None,
            "next_steps": [
                "All instances are busy. Options:",
                "1. Call scale_instances(target_count=<n>) to spin up more Docker workers.",
                "2. Call analyze_apk(path, strategy='replace') to overwrite the default instance.",
                "3. Call remove_jadx_instance(name) to free an existing instance first.",
            ],
        }

    # -------------------------------------------------------------------------
    # strategy="auto"
    # -------------------------------------------------------------------------
    all_instances = InstanceRegistry.list_instances_for_user(username, is_admin)
    connected = [i for i in all_instances if i.get("status") == "connected"]

    # Branch 1: no connected instances at all
    if not connected:
        return {
            "status": "error",
            "instance": None,
            "path": path,
            "ready": False,
            "poll_with": None,
            "next_steps": [
                "No connected JADX instances found.",
                "Add one with add_jadx_instance(host, port) and retry.",
            ],
        }

    # Branch 2: single instance
    if len(connected) == 1:
        inst = InstanceRegistry.get_instance(connected[0]["name"])
        apk_info = await _fetch_apk_info(inst)

        if _instance_has_no_file(apk_info):
            # Free — load directly
            result = await _load_file_on_instance(inst, path, mode="replace")
            if "error" in result:
                return {
                    "status": "error",
                    "instance": _instance_summary(inst),
                    "path": path,
                    "ready": False,
                    "poll_with": None,
                    "next_steps": [result["error"]],
                }
            return {
                "status": "loaded",
                "instance": _instance_summary(inst),
                "path": path,
                "ready": False,
                "poll_with": "get_decompile_status",
                "next_steps": [
                    "File is loading. Poll get_decompile_status until cached_percentage stabilises."
                ],
            }
        else:
            # Single instance with a file loaded — ambiguous
            loaded_name = apk_info.get("file_name") or apk_info.get("apk_package") or "unknown"
            return {
                "status": "ambiguous",
                "instance": _instance_summary(inst),
                "path": path,
                "ready": False,
                "poll_with": None,
                "next_steps": [
                    f"The only instance '{inst.name}' already has '{loaded_name}' loaded.",
                    "Choose one of:",
                    f"  analyze_apk('{path}', strategy='replace')     — replace '{loaded_name}'",
                    f"  analyze_apk('{path}', strategy='new_instance') — spin up a new worker first",
                    f"  analyze_apk('{path}', strategy='append')       — add as dependency to current project",
                ],
            }

    # Branch 3: multiple instances — find a free one
    for inst_dict in connected:
        inst = InstanceRegistry.get_instance(inst_dict["name"])
        if inst is None:
            continue
        apk_info = await _fetch_apk_info(inst)
        if _instance_has_no_file(apk_info):
            result = await _load_file_on_instance(inst, path, mode="replace")
            if "error" in result:
                continue
            return {
                "status": "loaded",
                "instance": _instance_summary(inst),
                "path": path,
                "ready": False,
                "poll_with": "get_decompile_status",
                "next_steps": [
                    f"Loaded on free instance '{inst.name}'. "
                    "Poll get_decompile_status until cached_percentage stabilises."
                ],
            }

    # Branch 4: all instances busy
    return {
        "status": "all_busy",
        "instance": None,
        "path": path,
        "ready": False,
        "poll_with": None,
        "next_steps": [
            "All instances are busy with loaded files. Options:",
            "1. Call scale_instances(target_count=<n>) to spin up more Docker workers.",
            "2. Call analyze_apk(path, strategy='replace') to overwrite the default instance.",
            "3. Call remove_jadx_instance(name) to free an existing instance first.",
        ],
    }


async def list_loaded_files(instance_id: Optional[str] = None) -> dict:
    """Aggregate what file each instance is currently analyzing.

    Calls /apk-info and /decompile-status on every accessible instance,
    or just the specified one if instance_id is provided.

    Args:
        instance_id: Optional specific instance name to query.

    Returns:
        dict with instances list, each entry having:
          name, loaded_file, decompile_progress, available
    """
    user = UserAuthManager.get_current_user()
    username = user.name if user else None
    is_admin = user.is_admin if user else False

    if instance_id:
        inst = InstanceRegistry.get_instance(instance_id)
        targets = [inst] if inst else []
    else:
        all_instances = InstanceRegistry.list_instances_for_user(username, is_admin)
        targets = [
            InstanceRegistry.get_instance(i["name"])
            for i in all_instances
            if InstanceRegistry.get_instance(i["name"]) is not None
        ]

    results = []
    for inst in targets:
        apk_info = await _fetch_apk_info(inst)
        decompile_status = await _fetch_decompile_status(inst)

        loaded_file = (
            apk_info.get("file_name")
            or apk_info.get("apk_package")
            or None
        )
        if loaded_file and _instance_has_no_file(apk_info):
            loaded_file = None

        progress = decompile_status.get("cached_percentage") or decompile_status.get("percentage") or 0.0
        if isinstance(progress, (int, float)):
            decompile_progress = round(float(progress) / 100.0, 2)
        else:
            decompile_progress = 0.0

        available = (inst.status == "connected") and _instance_has_no_file(apk_info)

        results.append({
            "name": inst.name,
            "host": inst.host,
            "port": inst.port,
            "status": inst.status,
            "loaded_file": loaded_file,
            "decompile_progress": decompile_progress,
            "available": available,
        })

    return {
        "instances": results,
        "count": len(results),
        "free_count": sum(1 for r in results if r["available"]),
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_workflow_tools(mcp, with_busy_check):
    """Register workflow tools (analyze_apk, list_loaded_files) with the MCP server."""

    @mcp.tool()
    async def analyze_apk_tool(
        path: str,
        strategy: str = "auto",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Load an APK/JAR into the best available JADX instance with smart routing.

        strategy="auto" (default): inspect instances and route automatically;
          returns "ambiguous" or "all_busy" when human guidance is needed.
        strategy="replace": load on default instance, replacing whatever is there.
        strategy="new_instance": find or use a free instance; return all_busy if none.
        strategy="append": append to current project (useful for dep JARs).

        Args:
            path: Sandbox-relative file path (e.g. "target.apk"). strategy: auto|replace|new_instance|append.
            instance_id: Pin to a specific instance name (omit for auto-routing).
        Returns:
            dict: {status: loaded|ambiguous|all_busy|error, instance, path, ready: false,
                   poll_with, next_steps}
        """
        return await analyze_apk(path=path, strategy=strategy, instance_id=instance_id)

    @mcp.tool()
    async def list_loaded_files_tool(
        instance_id: Optional[str] = None,
    ) -> dict:
        """Show what APK/JAR each JADX instance is currently analyzing and whether it is free.

        Args:
            instance_id: Query a specific instance only (omit for all instances).
        Returns:
            dict: {instances: [{name, loaded_file, decompile_progress, available}], count, free_count}
        """
        return await list_loaded_files(instance_id=instance_id)

    logger.info("Workflow tools registered: analyze_apk, list_loaded_files")
