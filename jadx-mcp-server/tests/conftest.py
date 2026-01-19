"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def reset_user_auth():
    """Reset UserAuthManager state before each test"""
    from server.user_auth import UserAuthManager
    UserAuthManager._users.clear()
    UserAuthManager._default_jadx_token = ""
    UserAuthManager._allow_anonymous = False
    UserAuthManager.set_current_user(None)
    yield


@pytest.fixture(autouse=True)
def reset_instance_registry():
    """Reset InstanceRegistry state before each test"""
    from server.instance_registry import InstanceRegistry
    InstanceRegistry.clear_all()
    InstanceRegistry._shared_auth_token = None
    yield
