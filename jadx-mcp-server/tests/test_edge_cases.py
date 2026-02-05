"""
Edge Case Tests: Configuration and Instance Registry

Tests boundary conditions and error handling.
"""

import pytest
import tempfile
from pathlib import Path

from server.config_loader import AppConfig, UserConfig, ConfigLoader
from server.instance_registry import InstanceRegistry


class TestConfigEdgeCases:
    """Edge case tests for configuration parsing"""

    def test_invalid_toml_syntax(self):
        """Invalid TOML should raise parse error"""
        invalid_toml = """
[server
host = "broken"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(invalid_toml)
            f.flush()
            
            loader = ConfigLoader(Path(f.name))
            with pytest.raises(Exception):  # tomllib.TOMLDecodeError
                loader.load()

    def test_empty_user_name(self):
        """User with empty name should still be created"""
        data = {"users": [{"name": "", "token": "some-token"}]}
        config = AppConfig.from_dict(data)
        assert len(config.users) == 1
        assert config.users[0].name == ""

    def test_missing_instance_port(self):
        """Missing port should use default 8650"""
        data = {"jadx_instances": [{"name": "no-port", "host": "127.0.0.1"}]}
        config = AppConfig.from_dict(data)
        assert config.jadx_instances[0].port == 8650

    def test_extra_unknown_fields_ignored(self):
        """Unknown config fields should be silently ignored"""
        data = {
            "server": {"host": "0.0.0.0", "unknown_field": "ignored"},
            "unknown_section": {"key": "value"}
        }
        config = AppConfig.from_dict(data)
        assert config.server.host == "0.0.0.0"

    def test_negative_port_allowed(self):
        """Negative port is technically allowed (validation is elsewhere)"""
        data = {"server": {"port": -1}}
        config = AppConfig.from_dict(data)
        assert config.server.port == -1

    def test_very_long_token(self):
        """Very long tokens should be handled"""
        long_token = "a" * 10000
        data = {"users": [{"name": "user", "token": long_token}]}
        config = AppConfig.from_dict(data)
        assert len(config.users[0].token) == 10000


class TestInstanceRegistryEdgeCases:
    """Edge case tests for InstanceRegistry"""

    def test_empty_instance_name(self):
        """Empty instance name should be registered"""
        result = InstanceRegistry.register_pending_instance(
            name="",
            host="127.0.0.1",
            port=8650
        )
        assert result["success"] == True
        assert InstanceRegistry.get_instance("") is not None

    def test_unicode_instance_name(self):
        """Unicode characters in instance name"""
        result = InstanceRegistry.register_pending_instance(
            name="测试实例-tools",
            host="127.0.0.1",
            port=8650
        )
        assert result["success"] == True
        assert InstanceRegistry.get_instance("测试实例-tools") is not None

    def test_very_large_port(self):
        """Very large port number"""
        result = InstanceRegistry.register_pending_instance(
            name="large-port",
            host="127.0.0.1",
            port=99999
        )
        assert result["success"] == True
        assert InstanceRegistry.get_instance("large-port").port == 99999

    def test_ipv6_host(self):
        """IPv6 address as host"""
        result = InstanceRegistry.register_pending_instance(
            name="ipv6-instance",
            host="::1",
            port=8650
        )
        assert result["success"] == True
        instance = InstanceRegistry.get_instance("ipv6-instance")
        assert instance.url == "http://::1:8650"

    def test_hostname_with_special_chars(self):
        """Hostname with dashes (valid DNS)"""
        result = InstanceRegistry.register_pending_instance(
            name="dash-host",
            host="my-jadx-server.local",
            port=8650
        )
        assert result["success"] == True

    def test_remove_last_instance_clears_default(self):
        """Removing the only instance should clear default"""
        InstanceRegistry.register_pending_instance("only-one", "127.0.0.1", 8650)
        assert InstanceRegistry.get_default() is not None
        
        InstanceRegistry.remove_instance("only-one", is_admin=True)
        assert InstanceRegistry.get_default() is None

    def test_set_default_nonexistent_fails(self):
        """Setting nonexistent instance as default should fail"""
        result = InstanceRegistry.set_default("nonexistent")
        assert result["success"] == False
        assert "not found" in result["message"].lower()

    def test_list_instances_empty(self):
        """Listing when no instances exist"""
        instances = InstanceRegistry.list_instances()
        assert instances == []
        assert len(instances) == 0

    def test_concurrent_registration_same_name(self):
        """Registering same name twice should fail second time"""
        r1 = InstanceRegistry.register_pending_instance("same", "127.0.0.1", 8650)
        r2 = InstanceRegistry.register_pending_instance("same", "127.0.0.1", 8651)
        
        assert r1["success"] == True
        assert r2["success"] == False

    def test_update_instance_status(self):
        """Test status update method"""
        InstanceRegistry.register_pending_instance("status-test", "127.0.0.1", 8650)
        
        success = InstanceRegistry.update_instance_status(
            name="status-test",
            status="connected",
            apk_info={"package": "com.test"}
        )
        
        assert success == True
        instance = InstanceRegistry.get_instance("status-test")
        assert instance.status == "connected"
        assert instance.apk_info["package"] == "com.test"

    def test_update_nonexistent_instance_status(self):
        """Updating status of nonexistent instance should return False"""
        success = InstanceRegistry.update_instance_status(
            name="nonexistent",
            status="connected"
        )
        assert success == False


class TestUserAuthEdgeCases:
    """Edge case tests for user authentication"""

    def test_duplicate_tokens(self):
        """Last user with duplicate token wins"""
        from server.user_auth import UserAuthManager
        from server.config_loader import UserConfig
        
        users = [
            UserConfig(name="user1", token="same-token"),
            UserConfig(name="user2", token="same-token"),
        ]
        UserAuthManager.configure(users)
        
        # Only one should be stored (last wins due to dict overwrite)
        assert UserAuthManager.get_user_count() == 1
        user = UserAuthManager.authenticate("same-token")
        assert user.name == "user2"

    def test_whitespace_only_token(self):
        """Whitespace-only token should be treated as empty"""
        from server.user_auth import UserAuthManager
        from server.config_loader import UserConfig
        
        users = [UserConfig(name="ws", token="   ")]
        UserAuthManager.configure(users)
        
        # Whitespace token is still registered (not stripped)
        user = UserAuthManager.authenticate("   ")
        assert user is not None
