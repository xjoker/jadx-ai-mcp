"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
import importlib
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def reset_user_auth():
    """Reset UserAuthManager state before each test"""
    for module_name in ("server.user_auth", "src.server.user_auth"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        UserAuthManager = module.UserAuthManager
        UserAuthManager._users.clear()
        UserAuthManager._default_jadx_token = ""
        UserAuthManager._allow_anonymous = False
        UserAuthManager.set_current_user(None)
    yield


@pytest.fixture(autouse=True)
def reset_instance_registry():
    """Reset InstanceRegistry state before each test"""
    for module_name in ("server.instance_registry", "src.server.instance_registry"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        InstanceRegistry = module.InstanceRegistry
        InstanceRegistry.clear_all()
        InstanceRegistry._shared_auth_token = None
    yield


@pytest.fixture(autouse=True)
def reset_response_cache():
    """Reset the global response cache before each test."""
    for module_name in ("server.response_cache", "src.server.response_cache"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        module.clear_response_cache()
    yield
