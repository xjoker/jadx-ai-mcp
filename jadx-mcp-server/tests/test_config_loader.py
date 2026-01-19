"""
Layer 1 Unit Tests: ConfigLoader

Tests configuration parsing and validation without any external dependencies.
"""

import pytest
from pathlib import Path
import tempfile

from server.config_loader import (
    AppConfig,
    UserConfig,
    JadxInstanceConfig,
    ServerConfig,
    DefaultsConfig,
    SecurityConfig,
    ConfigLoader,
)


class TestUserConfig:
    """Tests for UserConfig class"""

    def test_admin_has_add_permission_by_default(self):
        """Admin users should have add_instances permission by default"""
        user = UserConfig(name="admin", token="token-admin", is_admin=True)
        assert user.has_add_instances_permission == True

    def test_regular_user_no_permission_by_default(self):
        """Regular users should NOT have add_instances permission by default"""
        user = UserConfig(name="alice", token="token-alice", is_admin=False)
        assert user.has_add_instances_permission == False

    def test_explicit_permission_overrides_default(self):
        """Explicit can_add_instances should override defaults"""
        # Regular user with explicit permission
        user1 = UserConfig(name="bob", token="token-bob", can_add_instances=True)
        assert user1.has_add_instances_permission == True

        # Admin with explicit denial (edge case)
        user2 = UserConfig(name="admin", token="token-admin", is_admin=True, can_add_instances=False)
        assert user2.has_add_instances_permission == False


class TestAppConfig:
    """Tests for AppConfig.from_dict parsing"""

    def test_empty_config(self):
        """Empty dict should create default config"""
        config = AppConfig.from_dict({})
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8651
        assert len(config.users) == 0
        assert len(config.jadx_instances) == 0

    def test_server_config_parsing(self):
        """Server config should be parsed correctly"""
        data = {
            "server": {"host": "127.0.0.1", "port": 9000}
        }
        config = AppConfig.from_dict(data)
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000

    def test_users_config_parsing(self):
        """Users list should be parsed correctly"""
        data = {
            "users": [
                {"name": "alice", "token": "token-alice"},
                {"name": "admin", "token": "token-admin", "is_admin": True},
            ]
        }
        config = AppConfig.from_dict(data)
        assert len(config.users) == 2
        assert config.users[0].name == "alice"
        assert config.users[0].is_admin == False
        assert config.users[1].name == "admin"
        assert config.users[1].is_admin == True

    def test_jadx_instances_parsing(self):
        """JADX instances should be parsed correctly"""
        data = {
            "jadx_instances": [
                {"name": "local", "host": "127.0.0.1", "port": 8650},
                {"name": "remote", "host": "192.168.1.10", "port": 8650, "enabled": False},
            ]
        }
        config = AppConfig.from_dict(data)
        assert len(config.jadx_instances) == 2
        assert config.jadx_instances[0].name == "local"
        assert config.jadx_instances[0].enabled == True
        assert config.jadx_instances[1].enabled == False

    def test_security_config_parsing(self):
        """Security config should be parsed correctly"""
        data = {
            "security": {"allow_dynamic_instances": True}
        }
        config = AppConfig.from_dict(data)
        assert config.security.allow_dynamic_instances == True

    def test_defaults_config_parsing(self):
        """Defaults config should be parsed correctly"""
        data = {
            "defaults": {
                "request_timeout": 60,
                "jadx_token": "secret-token",
                "health_check_interval": 15,
            }
        }
        config = AppConfig.from_dict(data)
        assert config.defaults.request_timeout == 60
        assert config.defaults.jadx_token == "secret-token"
        assert config.defaults.health_check_interval == 15

    def test_get_user_by_token(self):
        """Should find user by token"""
        data = {
            "users": [
                {"name": "alice", "token": "token-alice"},
                {"name": "bob", "token": "token-bob"},
            ]
        }
        config = AppConfig.from_dict(data)
        
        user = config.get_user_by_token("token-alice")
        assert user is not None
        assert user.name == "alice"
        
        user = config.get_user_by_token("invalid-token")
        assert user is None


class TestConfigLoader:
    """Tests for ConfigLoader file loading"""

    def test_load_valid_toml(self):
        """Should load valid TOML config file"""
        toml_content = """
[server]
host = "0.0.0.0"
port = 8651

[[users]]
name = "testuser"
token = "test-token"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            
            loader = ConfigLoader(Path(f.name))
            config = loader.load()
            
            assert config.server.port == 8651
            assert len(config.users) == 1
            assert config.users[0].name == "testuser"

    def test_load_nonexistent_file(self):
        """Missing config file should return default config (not raise)"""
        loader = ConfigLoader(Path("/nonexistent/config.toml"))
        config = loader.load()
        
        # Should return default config
        assert config.server.port == 8651
        assert len(config.users) == 0
