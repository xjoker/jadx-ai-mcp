"""
Minimal operational status page for the MCP server.

Keeps the page intentionally simple and read-only so it can be served directly
from FastMCP custom routes without a frontend build step.
"""

from __future__ import annotations

import json
import secrets
from collections import Counter
from datetime import datetime, timezone
from html import escape
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from .busy_tracker import InstanceBusyTracker
from .health_monitor import HealthMonitor
from .http_auth_middleware import STATUS_AUTH_COOKIE, authenticate_http_request
from .instance_registry import InstanceRegistry
from .user_auth import AuthenticatedUser, UserAuthManager


SOURCE_LABELS = {
    "config": "Config File",
    "cli": "CLI Args",
    "default": "Default Host",
    "ai_dynamic": "AI Dynamic",
    "runtime": "Runtime",
}

STATUS_CLASS = {
    "connected": "ok",
    "pending": "warn",
    "degraded": "warn",
    "disconnected": "err",
    "error": "err",
    "auth_failed": "err",
}

STATUS_REFRESH_INTERVAL_MS = 5000


def _format_source(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def _format_scope(instance: dict[str, Any]) -> str:
    if instance.get("owner"):
        return f"user:{instance['owner']}"
    if instance.get("is_dynamic"):
        return "dynamic"
    return "shared"


def _format_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def _format_scheduler_counts(counts: dict[str, Any]) -> str:
    return (
        f"m:{counts.get('metadata_inflight', 0)} "
        f"c:{counts.get('code_read_inflight', 0)}/{counts.get('active_limit', 0)} "
        f"x:{counts.get('exclusive_inflight', 0)} "
        f"q:{counts.get('queue_depth', 0)}/{counts.get('queue_limit', 0)}"
    )


def _format_scheduler(instance: dict[str, Any]) -> str:
    scheduler = instance.get("scheduler") or {}
    return _format_scheduler_counts(scheduler)


def _cookie_settings() -> dict[str, Any]:
    return {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "max_age": 86400,
    }


def build_status_snapshot(
    *,
    server_host: str,
    server_port: int,
    require_auth: bool,
    viewer: AuthenticatedUser,
    auth_source: str,
) -> dict[str, Any]:
    if viewer.is_admin:
        instances = InstanceRegistry.list_instances()
    else:
        instances = InstanceRegistry.list_instances_for_user(viewer.name, False)

    default = InstanceRegistry.get_default()
    visible_instance_names = {inst["name"] for inst in instances}

    status_counts = Counter(inst.get("status", "unknown") for inst in instances)
    source_counts = Counter(inst.get("registration_source", "runtime") for inst in instances)
    scheduler_totals = {
        "metadata_inflight": 0,
        "code_read_inflight": 0,
        "exclusive_inflight": 0,
        "queue_depth": 0,
        "queue_limit": 0,
        "active_limit": 0,
    }

    warnings: list[str] = []
    if not instances:
        warnings.append(
            "No visible JADX instances. Pure pull mode requires config, CLI args, or add_jadx_instance()."
        )
    if status_counts.get("pending", 0):
        warnings.append("Some instances are still pending initial connection.")
    if status_counts.get("disconnected", 0):
        warnings.append("Some instances are disconnected and need operator attention.")
    if status_counts.get("auth_failed", 0):
        warnings.append("Some instances have authentication failures. Check jadx_token in config.")

    rendered_instances = []
    for inst in sorted(instances, key=lambda item: (item.get("registration_source", ""), item["name"])):
        apk_info = inst.get("apk_info") or {}
        scheduler = InstanceBusyTracker.get_snapshot(inst["name"])
        scheduler_totals["metadata_inflight"] += scheduler["metadata_inflight"]
        scheduler_totals["code_read_inflight"] += scheduler["code_read_inflight"]
        scheduler_totals["exclusive_inflight"] += scheduler["exclusive_inflight"]
        scheduler_totals["queue_depth"] += scheduler["queue_depth"]
        scheduler_totals["queue_limit"] += scheduler["queue_limit"]
        scheduler_totals["active_limit"] += scheduler["active_limit"]
        rendered_instances.append(
            {
                **inst,
                "source_label": _format_source(inst.get("registration_source", "runtime")),
                "scope_label": _format_scope(inst),
                "apk_package": apk_info.get("apk_package") or "-",
                "version_name": apk_info.get("version_name") or "-",
                "class_count": apk_info.get("class_count") or "-",
                "loaded": apk_info.get("loaded"),
                "scheduler": scheduler,
                "scheduler_label": _format_scheduler_counts(scheduler),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "server": {
            "host": server_host,
            "port": server_port,
            "health_monitor_running": HealthMonitor.is_running(),
            "mode": "pure_pull",
        },
        "viewer": {
            "name": viewer.name,
            "is_admin": viewer.is_admin,
            "auth_source": auth_source,
        },
        "auth": {
            "required": require_auth,
            "anonymous_allowed": UserAuthManager.allows_anonymous(),
            "configured_users": UserAuthManager.get_user_count(),
        },
        "instances": rendered_instances,
        "summary": {
            "total_instances": len(rendered_instances),
            "default_instance": default.name if default and default.name in visible_instance_names else None,
            "status_counts": dict(status_counts),
            "source_counts": dict(source_counts),
            "scheduler_counts": scheduler_totals,
        },
        "warnings": warnings,
    }


def _render_warning_list(warnings: list[str]) -> str:
    if not warnings:
        return '<p class="muted">No active warnings.</p>'
    return "".join(f"<li>{escape(item)}</li>" for item in warnings)


def _render_instances_table(instances: list[dict[str, Any]]) -> str:
    if not instances:
        return '<tr><td colspan="11" class="empty">No instances registered.</td></tr>'

    rows = []
    for inst in instances:
        badge_class = STATUS_CLASS.get(inst.get("status", ""), "")
        default_badge = " <span class=\"chip\">default</span>" if inst.get("is_default") else ""
        loaded = "yes" if inst.get("loaded") else "no"
        last_check = inst.get("last_health_check") or "-"
        scheduler = inst.get("scheduler") or {}
        busy_hint = scheduler.get("last_busy_reason") or "-"
        rows.append(
            "<tr>"
            f"<td><strong>{escape(inst['name'])}</strong>{default_badge}</td>"
            f"<td><span class=\"badge {badge_class}\">{escape(inst.get('status', '-'))}</span></td>"
            f"<td>{escape(inst.get('source_label', '-'))}</td>"
            f"<td>{escape(inst.get('scope_label', '-'))}</td>"
            f"<td>{escape(inst.get('host', '-'))}:{escape(str(inst.get('port', '-')))}</td>"
            f"<td>{escape(inst.get('apk_package', '-'))}</td>"
            f"<td>{escape(inst.get('version_name', '-'))}</td>"
            f"<td>{escape(str(inst.get('class_count', '-')))}</td>"
            f"<td>{loaded}</td>"
            f"<td title=\"m=metadata c=code_read x=exclusive q=queue\">{escape(inst.get('scheduler_label', '-'))}<div class=\"muted\">busy: {escape(busy_hint)}</div></td>"
            f"<td>{escape(last_check)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_session_panel(snapshot: dict[str, Any], csrf_token: str = "") -> str:
    viewer = snapshot["viewer"]
    auth = snapshot["auth"]

    if viewer["name"] == "anonymous":
        if auth["configured_users"] == 0:
            return (
                '<section class="card session-card">'
                "<h2>Session</h2>"
                "<div>Mode: anonymous</div>"
                "<div class=\"muted\">No MCP users configured. Browser access is open.</div>"
                "</section>"
            )

        return (
            '<section class="card session-card">'
            "<h2>Status Login</h2>"
            '<form method="post" action="/status/login" class="token-form">'
            f'<input type="hidden" name="csrf_token" value="{escape(csrf_token)}">'
            '<input type="password" name="token" placeholder="Enter user token" autocomplete="off" required>'
            '<button type="submit">Log In</button>'
            "</form>"
            "<div class=\"muted\">Use your MCP user token to view your instances.</div>"
            "</section>"
        )

    role = "admin" if viewer["is_admin"] else "user"
    source = viewer.get("auth_source", "unknown")
    return (
        '<section class="card session-card">'
        "<h2>Session</h2>"
        f"<div>User: {escape(viewer['name'])}</div>"
        f"<div>Role: {escape(role)}</div>"
        f"<div>Auth source: {escape(source)}</div>"
        '<form method="post" action="/status/logout" class="token-form logout-form">'
        '<button type="submit">Log Out</button>'
        "</form>"
        "</section>"
    )


def _snapshot_payload(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, ensure_ascii=True).replace("</", "<\\/")


CSRF_COOKIE_NAME = "csrf_token"


def render_login_html(
    *,
    error_message: str = "",
    configured_users: int,
    csrf_token: str = "",
) -> str:
    error_block = (
        f'<p class="login-error">{escape(error_message)}</p>'
        if error_message
        else '<p class="muted">Use your configured MCP user token to open the status page.</p>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JADX MCP Status Login</title>
  <style>
    :root {{
      --bg: #f7f4ec;
      --panel: #fffdf8;
      --ink: #1f1a15;
      --muted: #74685c;
      --line: #d9ccbb;
      --accent: #155eef;
      --err: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background: linear-gradient(180deg, #f3efe6 0%, var(--bg) 100%);
      color: var(--ink);
      font: 14px/1.5 Menlo, Monaco, Consolas, monospace;
    }}
    .card {{
      width: min(420px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 10px 24px rgba(31, 26, 21, 0.08);
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 0 0 12px; }}
    .muted {{ color: var(--muted); }}
    .login-error {{ color: var(--err); }}
    form {{ display: grid; gap: 12px; margin-top: 16px; }}
    input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
      font: inherit;
      background: #fff;
    }}
    button {{
      border: 0;
      border-radius: 12px;
      padding: 12px 14px;
      font: inherit;
      background: var(--accent);
      color: #fff;
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <section class="card">
    <h1>Status Login</h1>
    <p class="muted">Configured users: {configured_users}</p>
    {error_block}
    <form method="post" action="/status/login">
      <input type="hidden" name="csrf_token" value="{escape(csrf_token)}">
      <input type="password" name="token" placeholder="Enter user token" autocomplete="off" required>
      <button type="submit">Log In</button>
    </form>
  </section>
</body>
</html>"""


def render_status_html(snapshot: dict[str, Any], csrf_token: str = "") -> str:
    summary = snapshot["summary"]
    server = snapshot["server"]
    auth = snapshot["auth"]
    viewer = snapshot["viewer"]
    snapshot_json = _snapshot_payload(snapshot)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JADX MCP Status</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f4ec;
      --panel: #fffdf8;
      --ink: #1f1a15;
      --muted: #74685c;
      --line: #d9ccbb;
      --ok: #1f7a4c;
      --warn: #a35a00;
      --err: #b42318;
      --accent: #155eef;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      background: linear-gradient(180deg, #f3efe6 0%, var(--bg) 100%);
      color: var(--ink);
      font: 14px/1.5 Menlo, Monaco, Consolas, monospace;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 16px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 10px 24px rgba(31, 26, 21, 0.06);
    }}
    .muted {{ color: var(--muted); }}
    .warnbox {{
      background: #fff6e8;
      border: 1px solid #f2c98b;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .badge, .chip {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      border: 1px solid currentColor;
    }}
    .badge.ok {{ color: var(--ok); }}
    .badge.warn {{ color: var(--warn); }}
    .badge.err {{ color: var(--err); }}
    .chip {{ color: var(--accent); margin-left: 6px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      background: #faf5ec;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }}
    .toolbar a {{ color: var(--accent); text-decoration: none; }}
    .toolbar-meta {{ text-align: right; }}
    .session-wrap {{ margin-bottom: 18px; }}
    .session-card {{ max-width: 420px; }}
    .token-form {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .token-form input {{
      flex: 1 1 220px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      background: #fff;
    }}
    .token-form button {{
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font: inherit;
      background: var(--accent);
      color: #fff;
      cursor: pointer;
    }}
    .logout-form button {{
      background: #1f1a15;
    }}
    .empty {{
      padding: 20px;
      background: var(--panel);
      border: 1px dashed var(--line);
      border-radius: 14px;
      text-align: center;
      color: var(--muted);
    }}
    .refresh-error {{
      color: var(--err);
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="toolbar">
      <div>
        <h1>JADX MCP Status</h1>
        <div id="generated-at" class="muted">Generated at {escape(snapshot['generated_at'])}</div>
      </div>
      <div class="toolbar-meta">
        <div><a href="/status.json">JSON view</a></div>
        <div id="refresh-state" class="muted">Auto refresh every {STATUS_REFRESH_INTERVAL_MS // 1000}s</div>
      </div>
    </div>

    <div class="session-wrap">
      {_render_session_panel(snapshot, csrf_token=csrf_token)}
    </div>

    <div class="grid">
      <section class="card">
        <h2>Server</h2>
        <div id="server-bind">Bind: {escape(server['host'])}:{server['port']}</div>
        <div id="server-mode">Mode: {escape(server['mode'])}</div>
        <div id="server-health">Health monitor: {str(server['health_monitor_running']).lower()}</div>
      </section>
      <section class="card">
        <h2>Viewer</h2>
        <div id="viewer-name">User: {escape(viewer['name'])}</div>
        <div id="viewer-admin">Admin: {str(viewer['is_admin']).lower()}</div>
        <div id="viewer-source">Auth source: {escape(viewer.get('auth_source', 'anonymous'))}</div>
      </section>
      <section class="card">
        <h2>Auth</h2>
        <div id="auth-required">Required: {str(auth['required']).lower()}</div>
        <div id="auth-anonymous">Anonymous: {str(auth['anonymous_allowed']).lower()}</div>
        <div id="auth-users">Configured users: {auth['configured_users']}</div>
      </section>
      <section class="card">
        <h2>Registry</h2>
        <div id="registry-total">Total instances: {summary['total_instances']}</div>
        <div id="registry-default">Default instance: {escape(summary['default_instance'] or '-')}</div>
        <div id="registry-status">Status counts: {escape(_format_counts(summary['status_counts']))}</div>
        <div id="registry-source">Source counts: {escape(_format_counts(summary['source_counts']))}</div>
        <div id="registry-scheduler">Scheduler: {escape(_format_scheduler_counts(summary['scheduler_counts']))}</div>
      </section>
    </div>

    <section class="warnbox" id="warnbox"{' style="display:none"' if not snapshot['warnings'] else ''}>
      <h2>Warnings</h2>
      <ul id="warnings-list">{_render_warning_list(snapshot['warnings'])}</ul>
    </section>

    <section>
      <h2>Instances</h2>
      <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Source</th>
            <th>Scope</th>
            <th>Endpoint</th>
            <th>Package</th>
            <th>Version</th>
            <th>Classes</th>
            <th>Loaded</th>
            <th title="m=metadata c=code_read x=exclusive q=queue">Scheduler</th>
            <th>Last Check</th>
          </tr>
        </thead>
        <tbody id="instances-body">{_render_instances_table(snapshot['instances'])}</tbody>
      </table>
      </div>
    </section>
  </div>

  <script id="status-data" type="application/json">{snapshot_json}</script>
  <script>
    const STATUS_REFRESH_MS = {STATUS_REFRESH_INTERVAL_MS};

    function escapeHtml(value) {{
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function formatCounts(counts) {{
      const entries = Object.entries(counts || {{}}).sort((a, b) => a[0].localeCompare(b[0]));
      if (!entries.length) {{
        return "-";
      }}
      return entries.map(([key, value]) => `${{key}}:${{value}}`).join(", ");
    }}

    function renderWarnings(warnings) {{
      if (!warnings || warnings.length === 0) {{
        return '<p class="muted">No active warnings.</p>';
      }}
      return warnings.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("");
    }}

    function renderInstances(instances) {{
      if (!instances || instances.length === 0) {{
        return '<tr><td colspan="11" class="empty">No instances registered.</td></tr>';
      }}

      return instances.map((inst) => {{
        const badgeClass = {{
          connected: "ok",
          pending: "warn",
          degraded: "warn",
          disconnected: "err",
          error: "err",
          auth_failed: "err",
        }}[inst.status] || "";
        const defaultBadge = inst.is_default ? ' <span class="chip">default</span>' : "";
        const loaded = inst.loaded ? "yes" : "no";
        const lastCheck = inst.last_health_check || "-";
        const scheduler = inst.scheduler || {{}};
        const schedulerLabel = inst.scheduler_label ||
          `m:${{scheduler.metadata_inflight || 0}} c:${{scheduler.code_read_inflight || 0}}/${{scheduler.active_limit || 0}} x:${{scheduler.exclusive_inflight || 0}} q:${{scheduler.queue_depth || 0}}/${{scheduler.queue_limit || 0}}`;
        const busyHint = scheduler.last_busy_reason || "-";
        return (
          "<tr>" +
          `<td><strong>${{escapeHtml(inst.name)}}</strong>${{defaultBadge}}</td>` +
          `<td><span class="badge ${{badgeClass}}">${{escapeHtml(inst.status || "-")}}</span></td>` +
          `<td>${{escapeHtml(inst.source_label || "-")}}</td>` +
          `<td>${{escapeHtml(inst.scope_label || "-")}}</td>` +
          `<td>${{escapeHtml(inst.host || "-")}}:${{escapeHtml(String(inst.port ?? "-"))}}</td>` +
          `<td>${{escapeHtml(inst.apk_package || "-")}}</td>` +
          `<td>${{escapeHtml(inst.version_name || "-")}}</td>` +
          `<td>${{escapeHtml(String(inst.class_count ?? "-"))}}</td>` +
          `<td>${{loaded}}</td>` +
          `<td title="m=metadata c=code_read x=exclusive q=queue">${{escapeHtml(schedulerLabel)}}<div class="muted">busy: ${{escapeHtml(busyHint)}}</div></td>` +
          `<td>${{escapeHtml(lastCheck)}}</td>` +
          "</tr>"
        );
      }}).join("");
    }}

    function renderSnapshot(snapshot) {{
      const schedulerCounts = snapshot.summary.scheduler_counts || {{}};
      document.getElementById("generated-at").textContent = `Generated at ${{snapshot.generated_at}}`;
      document.getElementById("server-bind").textContent =
        `Bind: ${{snapshot.server.host}}:${{snapshot.server.port}}`;
      document.getElementById("server-mode").textContent = `Mode: ${{snapshot.server.mode}}`;
      document.getElementById("server-health").textContent =
        `Health monitor: ${{String(snapshot.server.health_monitor_running).toLowerCase()}}`;
      document.getElementById("viewer-name").textContent = `User: ${{snapshot.viewer.name}}`;
      document.getElementById("viewer-admin").textContent =
        `Admin: ${{String(snapshot.viewer.is_admin).toLowerCase()}}`;
      document.getElementById("viewer-source").textContent =
        `Auth source: ${{snapshot.viewer.auth_source || "anonymous"}}`;
      document.getElementById("auth-required").textContent =
        `Required: ${{String(snapshot.auth.required).toLowerCase()}}`;
      document.getElementById("auth-anonymous").textContent =
        `Anonymous: ${{String(snapshot.auth.anonymous_allowed).toLowerCase()}}`;
      document.getElementById("auth-users").textContent =
        `Configured users: ${{snapshot.auth.configured_users}}`;
      document.getElementById("registry-total").textContent =
        `Total instances: ${{snapshot.summary.total_instances}}`;
      document.getElementById("registry-default").textContent =
        `Default instance: ${{snapshot.summary.default_instance || "-"}}`;
      document.getElementById("registry-status").textContent =
        `Status counts: ${{formatCounts(snapshot.summary.status_counts)}}`;
      document.getElementById("registry-source").textContent =
        `Source counts: ${{formatCounts(snapshot.summary.source_counts)}}`;
      document.getElementById("registry-scheduler").textContent =
        `Scheduler: m:${{schedulerCounts.metadata_inflight || 0}} c:${{schedulerCounts.code_read_inflight || 0}}/${{schedulerCounts.active_limit || 0}} x:${{schedulerCounts.exclusive_inflight || 0}} q:${{schedulerCounts.queue_depth || 0}}/${{schedulerCounts.queue_limit || 0}}`;
      document.getElementById("warnings-list").innerHTML = renderWarnings(snapshot.warnings);
      const warnbox = document.getElementById("warnbox");
      warnbox.style.display = (snapshot.warnings && snapshot.warnings.length > 0) ? "" : "none";
      document.getElementById("instances-body").innerHTML = renderInstances(snapshot.instances);
    }}

    async function refreshStatus() {{
      try {{
        const response = await fetch("/status.json", {{
          credentials: "same-origin",
          headers: {{ "Accept": "application/json" }},
        }});

        if (response.status === 401) {{
          window.location.href = "/status";
          return;
        }}
        if (!response.ok) {{
          throw new Error(`HTTP ${{response.status}}`);
        }}

        const snapshot = await response.json();
        renderSnapshot(snapshot);
        const refreshEl = document.getElementById("refresh-state");
        refreshEl.textContent = `Live refresh every ${{STATUS_REFRESH_MS / 1000}}s`;
        refreshEl.classList.remove("refresh-error");
      }} catch (error) {{
        const refreshEl = document.getElementById("refresh-state");
        refreshEl.textContent = `Refresh failed: ${{error.message}}`;
        refreshEl.classList.add("refresh-error");
      }}
    }}

    const initialSnapshot = JSON.parse(document.getElementById("status-data").textContent);
    renderSnapshot(initialSnapshot);
    window.setInterval(refreshStatus, STATUS_REFRESH_MS);
  </script>
</body>
</html>"""


async def status_login_response(request: Request):
    form = await request.form()
    token = str(form.get("token", "")).strip()

    # CSRF validation (double-submit cookie pattern)
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
    csrf_form = str(form.get("csrf_token", "")).strip()
    if not csrf_cookie or not csrf_form or csrf_cookie != csrf_form:
        csrf_token = secrets.token_urlsafe(32)
        response = HTMLResponse(
            render_login_html(
                error_message="Invalid request. Please try again.",
                configured_users=UserAuthManager.get_user_count(),
                csrf_token=csrf_token,
            ),
            status_code=403,
        )
        response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, samesite="lax", path="/", max_age=600)
        return response

    user = UserAuthManager.authenticate(token)

    if not token or user is None or user.name == "anonymous":
        csrf_token = secrets.token_urlsafe(32)
        response = HTMLResponse(
            render_login_html(
                error_message="Invalid token. Use a configured user token.",
                configured_users=UserAuthManager.get_user_count(),
                csrf_token=csrf_token,
            ),
            status_code=401,
        )
        response.delete_cookie(STATUS_AUTH_COOKIE, path="/")
        response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, samesite="lax", path="/", max_age=600)
        return response

    response = RedirectResponse(url="/status", status_code=303)
    response.set_cookie(STATUS_AUTH_COOKIE, token, **_cookie_settings())
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return response


async def status_logout_response(_: Request):
    response = RedirectResponse(url="/status", status_code=303)
    response.delete_cookie(STATUS_AUTH_COOKIE, path="/")
    return response


async def status_json_response(
    request: Request,
    *,
    server_host: str,
    server_port: int,
    require_auth: bool,
):
    viewer, auth_source = authenticate_http_request(request, require_auth)
    if viewer is None:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    snapshot = build_status_snapshot(
        server_host=server_host,
        server_port=server_port,
        require_auth=require_auth,
        viewer=viewer,
        auth_source=auth_source,
    )
    return JSONResponse(snapshot)


async def status_html_response(
    request: Request,
    *,
    server_host: str,
    server_port: int,
    require_auth: bool,
):
    viewer, auth_source = authenticate_http_request(request, require_auth)
    csrf_token = secrets.token_urlsafe(32)

    if viewer is None:
        response = HTMLResponse(
            render_login_html(
                error_message="Status page requires a valid user token.",
                configured_users=UserAuthManager.get_user_count(),
                csrf_token=csrf_token,
            ),
            status_code=401,
        )
        response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, samesite="lax", path="/", max_age=600)
        if request.cookies.get(STATUS_AUTH_COOKIE):
            response.delete_cookie(STATUS_AUTH_COOKIE, path="/")
        return response

    snapshot = build_status_snapshot(
        server_host=server_host,
        server_port=server_port,
        require_auth=require_auth,
        viewer=viewer,
        auth_source=auth_source,
    )
    response = HTMLResponse(render_status_html(snapshot, csrf_token=csrf_token))
    response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, samesite="lax", path="/", max_age=600)
    return response
