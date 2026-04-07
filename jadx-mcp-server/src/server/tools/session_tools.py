"""
JADX MCP Server - Analysis Session Persistence Tools

Save and restore AI analysis session context to local JSON files,
enabling multi-session workflow continuity.

Author: JADX-AI-MCP Contributors
License: See LICENSE file
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.server.logging_config import get_logger
from src.server.request_context import get_from_jadx_for_current_user as get_from_jadx

logger = get_logger("session_tools")

# Session name validation pattern: letters, digits, underscores, hyphens only
_SESSION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

# Default sessions directory
_SESSIONS_DIR = Path.home() / ".jadx-ai-mcp" / "sessions"


def _get_sessions_dir() -> Path:
    """Return the sessions directory path. Allows monkeypatching in tests."""
    return _SESSIONS_DIR


def _validate_session_name(name: str) -> Optional[str]:
    """Validate session name. Return error message if invalid, None if OK."""
    if not name:
        return "session_name cannot be empty"
    if not _SESSION_NAME_PATTERN.match(name):
        return (
            "session_name must contain only letters, digits, underscores, "
            "and hyphens (1-100 characters)"
        )
    return None


async def save_analysis_session(
    session_name: str,
    context: dict,
    instance_id: Optional[str] = None,
) -> dict:
    """
    Save the current analysis session context to a local JSON file.

    Args:
        session_name: Session name (alphanumeric, hyphens, underscores; 1-100 chars)
        context: AI analysis context dict containing:
            - analyzed_classes (list[str]): Classes already analyzed
            - findings (list[dict]): Issues discovered
            - notes (str): Analysis notes
            - current_focus (str): Current area of focus
            - next_steps (list[str]): Planned next steps
        instance_id: Optional. Target JADX instance name

    Returns:
        dict: {success, session_name, saved_at, file_path}

    MCP Tool: save_analysis_session
    Description: Save AI analysis session context to a local file for later restoration
    """
    logger.info(f"save_analysis_session: name={session_name}")

    # Validate session name
    error = _validate_session_name(session_name)
    if error:
        return {"error": "INVALID_SESSION_NAME", "message": error}

    # Fetch file-info metadata from JADX
    file_info: dict = {}
    try:
        file_info = await get_from_jadx("file-info", instance_id=instance_id)
        if isinstance(file_info, str):
            file_info = {}
    except Exception as exc:
        logger.warning(f"save_analysis_session: failed to fetch file-info: {exc}")

    sessions_dir = _get_sessions_dir()
    sessions_dir.mkdir(parents=True, exist_ok=True)

    file_path = sessions_dir / f"{session_name}.json"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Check for existing session to preserve previous_save_time
    previous_save_time: Optional[str] = None
    if file_path.exists():
        try:
            existing = json.loads(file_path.read_text(encoding="utf-8"))
            previous_save_time = existing.get("metadata", {}).get("saved_at")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"save_analysis_session: failed to read existing session: {exc}")

    session_data = {
        "metadata": {
            "session_name": session_name,
            "saved_at": now_iso,
            "previous_save_time": previous_save_time,
            "instance_id": instance_id,
            "file_info": file_info,
        },
        "context": context,
    }

    file_path.write_text(
        json.dumps(session_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"save_analysis_session: saved to {file_path}")
    return {
        "success": True,
        "session_name": session_name,
        "saved_at": now_iso,
        "file_path": str(file_path),
    }


async def load_analysis_session(
    session_name: str,
) -> dict:
    """
    Load a previously saved analysis session from local JSON file.

    Args:
        session_name: Name of the session to load

    Returns:
        dict: Complete session data (metadata + context), or error info

    MCP Tool: load_analysis_session
    Description: Load a previously saved analysis session to restore context
    """
    logger.info(f"load_analysis_session: name={session_name}")

    error = _validate_session_name(session_name)
    if error:
        return {"error": "INVALID_SESSION_NAME", "message": error}

    file_path = _get_sessions_dir() / f"{session_name}.json"

    if not file_path.exists():
        return {
            "error": "SESSION_NOT_FOUND",
            "message": f"Session '{session_name}' not found",
            "sessions_dir": str(_get_sessions_dir()),
        }

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "error": "READ_ERROR",
            "message": f"Failed to read session file: {exc}",
        }

    logger.info(f"load_analysis_session: loaded from {file_path}")
    return data


async def list_analysis_sessions() -> dict:
    """
    List all saved analysis sessions.

    Returns:
        dict: {sessions: [...], count, sessions_dir}

    MCP Tool: list_analysis_sessions
    Description: List all saved analysis sessions with summary info
    """
    logger.info("list_analysis_sessions")

    sessions_dir = _get_sessions_dir()
    if not sessions_dir.exists():
        return {
            "sessions": [],
            "count": 0,
            "sessions_dir": str(sessions_dir),
        }

    sessions: list[dict] = []
    for fp in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            metadata = data.get("metadata", {})
            context = data.get("context", {})
            notes = context.get("notes", "")

            # Extract file_type from metadata.file_info
            file_info = metadata.get("file_info", {})
            file_type = file_info.get("file_type", file_info.get("type", "unknown"))

            sessions.append({
                "session_name": metadata.get("session_name", fp.stem),
                "saved_at": metadata.get("saved_at", ""),
                "file_type": file_type,
                "notes_preview": notes[:100] if notes else "",
            })
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"list_analysis_sessions: skipping {fp.name}: {exc}")

    return {
        "sessions": sessions,
        "count": len(sessions),
        "sessions_dir": str(sessions_dir),
    }


# ==================== Module-level references ====================

_save_analysis_session = save_analysis_session
_load_analysis_session = load_analysis_session
_list_analysis_sessions = list_analysis_sessions


def register_session_tools(mcp, with_busy_check):
    """Register session persistence tools with the MCP server."""

    @mcp.tool()
    @with_busy_check
    async def save_analysis_session(
        session_name: str,
        context: dict,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Save the current AI analysis session context to a local file.

        Persists analyzed classes, findings, notes, and next steps so you can
        resume the analysis in a future session.

        Args:
            session_name: Session name (alphanumeric, hyphens, underscores; 1-100 chars)
            context: Analysis context dict with keys: analyzed_classes, findings,
                     notes, current_focus, next_steps
            instance_id: Optional. Target JADX instance name
        """
        return await _save_analysis_session(
            session_name, context, instance_id=instance_id,
        )

    @mcp.tool()
    @with_busy_check
    async def load_analysis_session(
        session_name: str,
    ) -> dict:
        """Load a previously saved analysis session to restore context.

        Args:
            session_name: Name of the session to load
        """
        return await _load_analysis_session(session_name)

    @mcp.tool()
    @with_busy_check
    async def list_analysis_sessions() -> dict:
        """List all saved analysis sessions with summary info.

        Returns session names, save times, file types, and notes previews.
        """
        return await _list_analysis_sessions()

    logger.info(
        "Session tools registered: save_analysis_session, "
        "load_analysis_session, list_analysis_sessions"
    )
