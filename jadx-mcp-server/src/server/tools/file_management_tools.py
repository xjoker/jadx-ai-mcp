"""JADX MCP Server — File Management Tools

Two tools that let the AI client discover and switch the file being analyzed
without touching the JADX GUI. Both are gated by the Java-side FilePathSandbox
(JADX_FILE_ROOT env or /apks by default in Docker); requests outside the root
are rejected with HTTP 400/503.

Inspired by ghidra-mcp's import_file design, hardened with a real path
sandbox so AI cannot read arbitrary host files.
"""

from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("file_management_tools")


async def list_available_files(
    subdir: Optional[str] = None,
    pattern: Optional[str] = None,
    recursive: bool = False,
    instance_id: Optional[str] = None,
) -> dict:
    """List loadable files (APK/JAR/AAR/DEX/CLASS/ZIP) under the JADX file sandbox.

    The sandbox root is set by the JADX_FILE_ROOT environment variable on the
    plugin host, falling back to /apks in Docker deployments. Paths returned
    are relative to that root; pass any of them straight into load_file().

    Args:
        subdir: Optional sub-path under the root to scope the listing.
        pattern: Glob pattern (default "*"). Examples: "*.apk", "test-*".
        recursive: Recurse into subdirectories. Default false.
        instance_id: Target JADX instance name; omit for the default instance.

    Returns:
        dict with: root, base, count, files=[{path, absolute, size_bytes,
                                              extension, loadable}].
    """
    params: dict = {"recursive": "true" if recursive else "false"}
    if subdir:
        params["subdir"] = subdir
    if pattern:
        params["pattern"] = pattern
    return await get_from_jadx(
        "list-available-files",
        params,
        instance_id=instance_id,
    )


async def load_file(
    path: str,
    mode: str = "replace",
    instance_id: Optional[str] = None,
) -> dict:
    """Load an APK/JAR/AAR/DEX/CLASS into the running JADX instance.

    Replaces (or appends to) the currently open file. Decompilation continues
    in the background after this call returns; poll /decompile-status via the
    standard decompile_status tool to know when analysis is ready.

    The path must live inside the configured JADX_FILE_ROOT sandbox (or
    /apks in Docker). Paths escaping the root, missing files, or unsupported
    extensions are rejected with HTTP 400.

    Args:
        path: Path under the sandbox root (e.g. "target.apk" or
              "subdir/foo.jar"). Absolute paths are accepted as long as they
              canonicalize inside the root.
        mode: "replace" (default — close current project, open this file) or
              "append" (add to current project; useful for APK + dependency JARs).
        instance_id: Target JADX instance name; omit for the default instance.

    Returns:
        dict with: dispatched, mode, path, ready=false, poll_with, note.
        ready is always false because JADX decompiles asynchronously; clients
        should call get_decompile_status until cached_percentage stabilises.
    """
    if mode not in ("replace", "append"):
        return {
            "error": f"mode must be 'replace' or 'append', got: {mode}",
        }
    return await get_from_jadx(
        "load-file",
        instance_id=instance_id,
        method="POST",
        json_body={"path": path, "mode": mode},
    )


def register_file_management_tools(mcp, with_busy_check):
    """Register file-management tools with the MCP server."""

    @mcp.tool()
    async def list_available_files_tool(
        subdir: Optional[str] = None,
        pattern: Optional[str] = None,
        recursive: bool = False,
        instance_id: Optional[str] = None,
    ) -> dict:
        """List loadable files inside the JADX file sandbox.

        Use this before load_file to discover what APK/JAR/AAR/DEX/CLASS
        files are available. Returns paths relative to the sandbox root that
        can be passed directly to load_file.

        Args:
            subdir: Optional sub-path under the root to scope the listing.
            pattern: Glob, e.g. "*.apk". Default "*".
            recursive: Recurse into subdirectories. Default false.
            instance_id: Target JADX instance; omit for the default.
        """
        return await list_available_files(
            subdir=subdir,
            pattern=pattern,
            recursive=recursive,
            instance_id=instance_id,
        )

    # load_file mutates the analyzed project; wrap in busy-check so concurrent
    # requests do not race with an in-flight decompilation.
    @mcp.tool()
    @with_busy_check
    async def load_file_tool(
        path: str,
        mode: str = "replace",
        instance_id: Optional[str] = None,
    ) -> dict:
        """Load an APK/JAR/AAR/DEX/CLASS into the running JADX instance.

        Switches what JADX is analyzing without touching the GUI. The plugin
        validates the path against its sandbox (JADX_FILE_ROOT / /apks).
        Decompilation continues asynchronously — poll get_decompile_status to
        know when analysis is ready.

        Args:
            path: Path under the sandbox root (relative or absolute that
                  canonicalizes inside the root).
            mode: "replace" (close & open) or "append" (merge into current
                  project; for APK + dependency JARs only).
            instance_id: Target JADX instance; omit for the default.
        """
        return await load_file(path=path, mode=mode, instance_id=instance_id)
