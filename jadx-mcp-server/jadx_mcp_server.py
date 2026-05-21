#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastmcp==3.1.0",
#   "httpx==0.28.1",
#   "tomli==2.4.0; python_version < '3.11'",
# ]
# ///

"""
Copyright (c) 2025 jadx mcp server developer(s) (https://github.com/zinja-coder/jadx-ai-mcp)
See the file 'LICENSE' for copying permission
"""

import argparse
import sys
from fastmcp import FastMCP
from src.banner import jadx_mcp_server_banner
from src.server import config
from src.server.mcp_auth import (
    ReloadableStaticTokenVerifier,
    SwitchableTokenVerifier,
    build_auth_provider,
    build_legacy_cli_user,
)

# Initialize MCP Server with stateless HTTP mode (no session required)
# Instructions are shown to AI when connecting to help with proper tool usage
MCP_INSTRUCTIONS = """
JADX AI MCP Server - Android APK Reverse Engineering Tools

IMPORTANT: Before using any resource-intensive operation, always call get_decompile_status() first!

DECISION GUIDE based on get_decompile_status() response:
- If cached_percentage < 20%: Use search_in='class' or 'method' only (avoid 'code')
- If memory.usage_percentage > 85%: Reduce batch size to 5, avoid get_smali_of_class
- If search_lock.locked = true: Wait 5 seconds and retry

PERFORMANCE EXPECTATIONS:
| Operation              | Expected Time | Notes                          |
|------------------------|--------------|--------------------------------|
| search_in=class/method | <100ms       | Always fast, no cache needed   |
| search_in=code         | 1-60s        | Slow, may timeout on large APK |
| get_class_source       | <1s          | Fast when cached               |
| batch_get_*            | <3s          | Up to 20 items per batch       |

RECOMMENDED WORKFLOW:
1. Call get_decompile_status() to check system status
2. Use metadata searches first (class, method, field)
3. Use code search only when cache is ready (cached_percentage > 50%)
4. Use package filter to narrow search scope for better performance

TRANSFER API - Bypass MCP Size Limits:
When batch operations might exceed MCP message limits (~16KB):
1. Call create_transfer_token(resource_type="batch_classes")
2. Use HTTP client to download directly from transfer_url
3. Supports JSON and ZIP formats, Brotli/GZIP compression
4. Example: GET {transfer_url}/download/batch-classes?classes=A,B&token=xxx&format=zip

For detailed guidance, use the 'status-check' or 'search-code' prompts.
"""


mcp = FastMCP(
    "JADX-AI-MCP Plugin Reverse Engineering Server",
    instructions=MCP_INSTRUCTIONS
)

# Tool registration uses register_*_tools() pattern from each module
from src.server.prompts import register_prompts
from src.server.resources import register_resources
from src.server.tools import (
    register_class_tools,
    register_search_tools,
    register_resource_tools,
    register_xrefs_tools,
    register_refactor_tools,
    register_instance_tools,
    register_transfer_tools,
    register_frida_tools,
    register_annotation_tools,
    register_digest_tools,
    register_security_tools,
    register_session_tools,
    register_export_tools,
    register_diff_tools,
    register_dataflow_tools,
    register_decompile_tools,
    register_scaling_tools,
    register_file_management_tools,
)
from src.server.instance_registry import InstanceRegistry
from src.server.busy_tracker import with_busy_check, InstanceBusyTracker
from src.server.auth_middleware import BearerAuthMiddleware
from src.server.health_monitor import HealthMonitor
from src.server.logging_config import configure_logging, get_logger
from src.server.status_page import (
    status_html_response,
    status_json_response,
    status_login_response,
    status_logout_response,
)
from src.server import transfer_server
from src.server.mcp_server_config import set_mcp_server_url_from_config

# Register Transfer API custom routes
# Using @mcp.custom_route() to add HTTP endpoints alongside MCP
@mcp.custom_route("/transfer/download/batch-classes", methods=["GET"])
async def transfer_download_batch_classes(request):
    """Transfer API: Download batch classes bypassing MCP size limits"""
    return await transfer_server.download_batch_classes(request)

@mcp.custom_route("/transfer/health", methods=["GET"])
async def transfer_health(request):
    """Transfer API: Health check endpoint"""
    return await transfer_server.download_health(request)

logger = get_logger("main")

# Register all MCP tools from their respective modules
register_class_tools(mcp, with_busy_check)
register_search_tools(mcp, with_busy_check)
register_resource_tools(mcp, with_busy_check)
register_xrefs_tools(mcp, with_busy_check)
register_refactor_tools(mcp, with_busy_check)
register_instance_tools(mcp)
register_transfer_tools(mcp)
register_frida_tools(mcp, with_busy_check)
register_annotation_tools(mcp, with_busy_check)
register_digest_tools(mcp, with_busy_check)
register_security_tools(mcp, with_busy_check)
register_session_tools(mcp, with_busy_check)
register_export_tools(mcp, with_busy_check)
register_diff_tools(mcp, with_busy_check)
register_dataflow_tools(mcp, with_busy_check)
register_decompile_tools(mcp, with_busy_check)
register_scaling_tools(mcp)
register_file_management_tools(mcp, with_busy_check)

# Load balancer status tool
from src.server.load_balancer import register_loadbalancer_tools
register_loadbalancer_tools(mcp)


def main():
    parser = argparse.ArgumentParser(
        "MCP Server for Jadx",
        description="JADX AI MCP Server - Connect Claude AI with JADX decompiler"
    )
    parser.add_argument(
        "--http",
        help="Serve MCP Server over HTTP stream.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--port",
        help="Port for --http (default:8651)",
        default=8651,
        type=int
    )
    parser.add_argument(
        "--host",
        help="Bind address for MCP server (default:127.0.0.1). Use 0.0.0.0 to allow external connections",
        default="127.0.0.1",
        type=str
    )
    parser.add_argument(
        "--jadx-host",
        help="JADX AI MCP Plugin host address (default:127.0.0.1)",
        default="127.0.0.1",
        type=str
    )
    parser.add_argument(
        "--jadx-port",
        help="JADX AI MCP Plugin port (default:8650)",
        default=8650,
        type=int,
    )
    parser.add_argument(
        "--auth-token",
        help="Authentication token for JADX plugin (shared across all instances)",
        default=None,
        type=str
    )
    parser.add_argument(
        "--jadx-instances",
        help="Initial JADX instances to connect: host:port[:name],host:port[:name]...",
        default=None,
        type=str
    )
    parser.add_argument(
        "--max-busy-timeout",
        help="Maximum time (seconds) an instance can be busy before auto-release (default: 300)",
        default=300,
        type=int
    )
    parser.add_argument(
        "--request-timeout",
        help="HTTP request timeout in seconds for JADX plugin requests (default: 120)",
        default=120,
        type=int
    )
    parser.add_argument(
        "--config",
        help="Path to TOML configuration file (e.g., data/config/jadx-config.toml)",
        default=None,
        type=str
    )
    parser.add_argument(
        "--mcp-auth-token",
        help="Authentication token for MCP clients connecting to this server",
        default=None,
        type=str
    )
    args = parser.parse_args()

    # ========== Load Configuration File (if provided) ==========
    from pathlib import Path
    from src.server.config_loader import ConfigLoader, set_config_loader, AppConfig
    
    loaded_config: AppConfig = None
    config_loader: ConfigLoader = None
    
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config_loader = ConfigLoader(config_path)
            loaded_config = config_loader.load()
            set_config_loader(config_loader)
            print(f"[OK] Loaded configuration from {config_path}")
            
            # Apply config file values only when CLI uses defaults (CLI takes precedence)
            if loaded_config.server.host and args.host == parser.get_default("host"):
                args.host = loaded_config.server.host
            if loaded_config.server.port and args.port == parser.get_default("port"):
                args.port = loaded_config.server.port
            if (
                loaded_config.defaults.request_timeout
                and args.request_timeout == parser.get_default("request_timeout")
            ):
                args.request_timeout = loaded_config.defaults.request_timeout
            if (
                loaded_config.defaults.busy_timeout
                and args.max_busy_timeout == parser.get_default("max_busy_timeout")
            ):
                args.max_busy_timeout = loaded_config.defaults.busy_timeout
        else:
            print(f"[WARN] Config file not found: {config_path}, using CLI arguments")

    # Configure busy timeout
    InstanceBusyTracker.set_timeout(args.max_busy_timeout)
    print(f"[OK] Busy timeout set to {args.max_busy_timeout} seconds")

    # Configure request timeout
    config.set_request_timeout(args.request_timeout)
    print(f"[OK] Request timeout set to {args.request_timeout} seconds")

    # Configure JADX connection (for backward compatibility)
    config.set_jadx_config(host=args.jadx_host, port=args.jadx_port)

    # ========== Multi-User Authentication Setup ==========
    from src.server.user_auth import UserAuthManager
    
    # Get default JADX token from config or CLI
    default_jadx_token = ""
    if loaded_config and loaded_config.defaults.jadx_token:
        default_jadx_token = loaded_config.defaults.jadx_token
    if args.auth_token:  # CLI overrides config
        default_jadx_token = args.auth_token
    
    # Set shared JADX token
    _default_tokens = {"admin-secret-token", "jadx-plugin-secret-token"}
    if default_jadx_token:
        config.set_auth_token(default_jadx_token)
        InstanceRegistry.set_auth_token(default_jadx_token)
        print(f"[OK] Default JADX plugin token configured")
        # Warn about default tokens in production
        if default_jadx_token in _default_tokens:
            logger.warning("Default JADX plugin token detected — change it for production use")
    else:
        print("[WARN] No default JADX plugin token (instances may need individual tokens)")
    
    # Configure multi-user authentication
    auth_users = [user for user in (loaded_config.users if loaded_config and loaded_config.users else []) if user.token]
    allow_anonymous = True  # Allow anonymous if no users configured
    if auth_users:
        UserAuthManager.configure(
            users=auth_users,
            default_jadx_token=default_jadx_token,
            allow_anonymous=False  # Require auth if users are configured
        )
        print(f"[OK] Multi-user authentication enabled ({len(auth_users)} users)")
        for user in auth_users:
            role = "admin" if user.is_admin else "user"
            print(f"  - {user.name} ({role})")
            if user.token in _default_tokens:
                logger.warning(f"User '{user.name}' uses a default token — change it for production use")
        allow_anonymous = False
    elif args.mcp_auth_token:
        # Single token mode (legacy)
        auth_users = [build_legacy_cli_user(args.mcp_auth_token)]
        UserAuthManager.configure(
            users=auth_users,
            default_jadx_token=default_jadx_token,
            allow_anonymous=False
        )
        print(f"[OK] Single-token authentication mode")
        allow_anonymous = False
    else:
        # No authentication
        UserAuthManager.configure(
            users=[],
            default_jadx_token=default_jadx_token,
            allow_anonymous=True
        )
        print("[WARN] No MCP authentication configured — /mcp endpoint is open")
        print("  This is only safe for local development. For network deployments,")
        print("  add [[users]] to config or use --mcp-auth-token to enable auth.")

    # Banner & Health Check
    try:
        print(jadx_mcp_server_banner())
    except Exception:
        from src.banner import SERVER_VERSION
        print(
            f"[JADX AI MCP Server] v{SERVER_VERSION} | MCP: {args.host}:{args.port} | JADX: {args.jadx_host}:{args.jadx_port}"
        )

    # ========== Initialize JADX Instances ==========
    import asyncio
    
    async def init_all_instances():
        """Initialize JADX instances from config file and/or CLI"""
        instances_added = 0
        
        # 1. Load instances from config file (register as pending, health monitor will connect)
        if loaded_config and loaded_config.jadx_instances:
            print(f"\nRegistering JADX instances from config file...")
            for inst_cfg in loaded_config.jadx_instances:
                if not inst_cfg.enabled:
                    print(f"  [-] Skipped (disabled): {inst_cfg.name}")
                    continue
                
                # Register as pending - health monitor will attempt connection
                result = InstanceRegistry.register_pending_instance(
                    name=inst_cfg.name,
                    host=inst_cfg.host, 
                    port=inst_cfg.port,
                    token=inst_cfg.token if inst_cfg.token else None,
                    registration_source="config",
                )
                if result["success"]:
                    print(f"  [OK] Registered: {inst_cfg.name} ({inst_cfg.host}:{inst_cfg.port}) [pending]")
                    instances_added += 1
                else:
                    print(f"  [FAIL] Failed: {inst_cfg.name}: {result['message']}")
        
        # 2. Load instances from CLI --jadx-instances
        if args.jadx_instances:
            print(f"\nLoading JADX instances from CLI...")
            for inst_str in args.jadx_instances.split(","):
                parts = inst_str.strip().split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    try:
                        port = int(parts[1])
                        name = parts[2] if len(parts) > 2 else None
                        result = await InstanceRegistry.add_instance(
                            host, port, name, registration_source="cli"
                        )
                        if result["success"]:
                            print(f"  [OK] Added: {result['instance']['name']} ({host}:{port})")
                            instances_added += 1
                        else:
                            print(f"  [FAIL] Failed: {host}:{port}: {result['message']}")
                    except ValueError:
                        print(f"  [FAIL] Invalid port: {inst_str}")
                else:
                    print(f"  [FAIL] Invalid format: {inst_str}")
        
        # 3. If no instances configured, try default connection
        if instances_added == 0 and not args.jadx_instances and not (loaded_config and loaded_config.jadx_instances):
            print(f"\nTesting default JADX connection at {args.jadx_host}:{args.jadx_port}...")
            try:
                result = await InstanceRegistry.add_instance(
                    args.jadx_host, args.jadx_port, registration_source="default"
                )
                if result["success"]:
                    print(f"[OK] Default JADX instance connected")
                    instances_added += 1
                else:
                    print(f"[WARN] Could not connect to default JADX: {result['message']}")
                    default_name = f"default-{args.jadx_host.replace('.', '-').replace(':', '-')}-{args.jadx_port}"
                    pending = InstanceRegistry.register_pending_instance(
                        name=default_name,
                        host=args.jadx_host,
                        port=args.jadx_port,
                        registration_source="default",
                    )
                    if pending["success"]:
                        print(f"[OK] Registered default JADX instance as pending: {default_name}")
                        print("  Health monitor will keep retrying until the plugin becomes available.")
                        instances_added += 1
            except Exception as e:
                print(f"[WARN] Default connection failed: {e}")
                default_name = f"default-{args.jadx_host.replace('.', '-').replace(':', '-')}-{args.jadx_port}"
                pending = InstanceRegistry.register_pending_instance(
                    name=default_name,
                    host=args.jadx_host,
                    port=args.jadx_port,
                    registration_source="default",
                )
                if pending["success"]:
                    print(f"[OK] Registered default JADX instance as pending: {default_name}")
                    print("  Health monitor will keep retrying until the plugin becomes available.")
                    instances_added += 1
        
        return instances_added
    
    try:
        instance_count = asyncio.run(init_all_instances())
        print(f"\n[OK] Total JADX instances: {instance_count}")
    except Exception as e:
        print(f"[WARN] Instance initialization error: {e}")

    # ========== Config Hot-Reload Callback ==========
    async def on_config_change(new_config: AppConfig):
        """Handle configuration file changes"""
        nonlocal auth_users, allow_anonymous, require_auth
        print(f"\n[Hot-Reload] Configuration changed, updating instances...")
        
        current_instances = InstanceRegistry.list_instances()
        current_names = {inst["name"] for inst in current_instances}
        current_config_names = {
            inst["name"]
            for inst in current_instances
            if inst.get("registration_source") == "config"
        }
        
        # Get new enabled instance names from config
        new_names = {inst.name for inst in new_config.jadx_instances if inst.enabled}
        
        # Remove config-managed instances no longer in config (system-level operation)
        for name in current_config_names - new_names:
            result = InstanceRegistry.remove_instance(name, username="system", is_admin=True)
            print(f"  [Hot-Reload] Removed: {name}")
        
        # Add new instances from config
        for inst_cfg in new_config.jadx_instances:
            if inst_cfg.enabled and inst_cfg.name not in current_names:
                result = await InstanceRegistry.add_instance(
                    inst_cfg.host,
                    inst_cfg.port,
                    inst_cfg.name,
                    token=inst_cfg.token if inst_cfg.token else None,
                    registration_source="config",
                )
                if result["success"]:
                    print(f"  [Hot-Reload] Added: {inst_cfg.name}")
                else:
                    print(f"  [Hot-Reload] Failed to add {inst_cfg.name}: {result['message']}")

        # Reload MCP auth/users via SwitchableTokenVerifier (no restart needed).
        if args.mcp_auth_token:
            print("  [Hot-Reload] MCP auth unchanged (CLI --mcp-auth-token takes precedence)")
        else:
            new_auth_users = [user for user in new_config.users if user.token]
            auth_users = new_auth_users
            allow_anonymous = not bool(new_auth_users)
            require_auth = bool(new_auth_users)

            UserAuthManager.configure(
                users=auth_users,
                default_jadx_token=default_jadx_token,
                allow_anonymous=allow_anonymous,
            )

            if require_auth:
                if mcp.auth is switchable_verifier:
                    # Auth was already enabled at startup — reload users in place
                    new_inner = build_auth_provider(auth_users)
                    switchable_verifier.set_inner(new_inner)
                    print(f"  [Hot-Reload] Reloaded MCP auth users: {len(auth_users)}")
                else:
                    # Auth was disabled at startup — can't add OAuth middleware dynamically
                    print("  [Hot-Reload] Auth users added but OAuth middleware not active.")
                    print("  [Hot-Reload] *** Restart required to enable MCP auth ***")
            else:
                if mcp.auth is switchable_verifier:
                    # Auth was enabled at startup — can't remove OAuth middleware dynamically
                    switchable_verifier.set_inner(None)
                    print("  [Hot-Reload] Auth users removed. Existing OAuth sessions still work.")
                    print("  [Hot-Reload] *** Restart required to fully disable MCP auth ***")
                else:
                    print("  [Hot-Reload] Auth remains disabled (no users configured)")
        
        print(f"  [Hot-Reload] Complete. Instances: {InstanceRegistry.get_instance_count()}")

    # ========== Run MCP Server ==========
    # Note: MCP tools are registered at module level via register_*_tools()

    # Register Prompts
    register_prompts(mcp)

    # Register Resources (usage guide, decision matrix, benchmarks)
    register_resources(mcp)
    
    # Register official FastMCP auth provider for the MCP endpoint.
    #
    # IMPORTANT: Only set mcp.auth when users are actually configured.
    # FastMCP's HTTP transport wraps /mcp with RequireAuthMiddleware when
    # auth is set, which rejects ALL requests without a valid OAuth Bearer
    # token — even if our verifier would accept anonymous access.
    # Setting mcp.auth = None keeps /mcp open (no OAuth flow required).
    require_auth = bool(auth_users) and not allow_anonymous
    inner_verifier = build_auth_provider(auth_users)
    switchable_verifier = SwitchableTokenVerifier(inner=inner_verifier)
    if inner_verifier:
        mcp.auth = switchable_verifier
        print("[OK] FastMCP TokenVerifier enabled for /mcp")
    else:
        # No auth users — leave mcp.auth unset so /mcp is open
        print("[WARN] MCP endpoint is OPEN — no authentication required")
        print("  Only safe for local use. Configure [[users]] for network deployments.")

    # Register user-context middleware for tool permission checks
    auth_middleware = BearerAuthMiddleware(require_auth=require_auth)
    mcp.add_middleware(auth_middleware)
    if require_auth:
        print(f"[OK] User context middleware enabled (required)")
    else:
        print(f"[OK] User context middleware enabled (optional)")

    @mcp.custom_route("/health", methods=["GET"])
    async def health_endpoint(request):
        """Lightweight health check endpoint (no auth required)."""
        return await transfer_server.download_health(request)

    @mcp.custom_route("/status", methods=["GET"])
    async def status_page(request):
        """Human-readable operational status page."""
        return await status_html_response(
            request,
            server_host=args.host,
            server_port=args.port,
            require_auth=require_auth,
        )

    @mcp.custom_route("/status.json", methods=["GET"])
    async def status_page_json(request):
        """Machine-readable operational status page."""
        return await status_json_response(
            request,
            server_host=args.host,
            server_port=args.port,
            require_auth=require_auth,
        )

    @mcp.custom_route("/status/login", methods=["POST"])
    async def status_page_login(request):
        """Browser login for the status page."""
        return await status_login_response(request)

    @mcp.custom_route("/status/logout", methods=["POST"])
    async def status_page_logout(request):
        """Browser logout for the status page."""
        return await status_logout_response(request)

    if args.http:
        # Set MCP Server URL for Transfer API (read from config file)
        if loaded_config and loaded_config.server.mcp_url:
            set_mcp_server_url_from_config(loaded_config.server.mcp_url)
            print(f"[OK] Transfer API URL: {loaded_config.server.mcp_url}")
        
        print(f"\nStarting MCP server in HTTP mode on {args.host}:{args.port}...")
        if require_auth:
            print(f"  Clients must provide: Authorization: Bearer <token>")

        import threading
        
        # Start config watcher in background (for HTTP mode only)
        if config_loader:
            def run_config_watcher():
                """Run the config file watcher in a dedicated event loop."""
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    config_loader.add_change_callback(on_config_change)
                    loop.run_until_complete(config_loader.start_watching())
                    loop.run_forever()
                except Exception as e:
                    print(f"Config watcher error: {e}")
                finally:
                    loop.close()

            config_thread = threading.Thread(target=run_config_watcher, daemon=True)
            config_thread.start()
            print(f"  Config hot-reload: enabled")
        
        # Start background health monitor for JADX instances
        health_interval = loaded_config.defaults.health_check_interval if loaded_config else 30
        HealthMonitor.configure(interval=health_interval)
        
        # Start health monitor in a background thread with its own event loop
        import signal
        
        def run_health_monitor():
            """Run health monitor in a separate thread with its own event loop."""
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(HealthMonitor.start())
                loop.run_forever()
            except Exception as e:
                print(f"Health monitor error: {e}")
            finally:
                loop.close()
        
        health_thread = threading.Thread(target=run_health_monitor, daemon=True)
        health_thread.start()
        
        print(f"  Health monitor: enabled (interval: {health_interval}s)")
        
        # Stateless HTTP: no session tracking, survives server restarts.
        # Trade-off: no SSE streaming / server-initiated notifications (GET /mcp disabled).
        mcp.run(transport="http", host=args.host, port=args.port, stateless_http=True)
    else:
        print("\nStarting MCP server in stdio mode...")
        mcp.run()


if __name__ == "__main__":
    main()
