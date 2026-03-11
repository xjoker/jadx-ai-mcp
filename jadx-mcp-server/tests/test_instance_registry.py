"""
Layer 2 Unit Tests: InstanceRegistry

Tests instance management with mocked HTTP calls.
No real JADX container required.
"""

import pytest
from datetime import datetime

from server.instance_registry import InstanceRegistry, JadxInstance


class TestJadxInstance:
    """Tests for JadxInstance dataclass"""

    def test_url_property(self):
        """URL should be constructed from host and port"""
        instance = JadxInstance(name="test", host="192.168.1.10", port=8650)
        assert instance.url == "http://192.168.1.10:8650"

    def test_to_dict(self):
        """to_dict should return all relevant fields"""
        instance = JadxInstance(
            name="test",
            host="127.0.0.1",
            port=8650,
            status="connected",
            owner="alice",
            is_dynamic=True,
        )
        d = instance.to_dict()
        
        assert d["name"] == "test"
        assert d["host"] == "127.0.0.1"
        assert d["port"] == 8650
        assert d["url"] == "http://127.0.0.1:8650"
        assert d["status"] == "connected"
        assert d["owner"] == "alice"
        assert d["is_dynamic"] == True
        assert d["registration_source"] == "runtime"


class TestInstanceRegistryBasic:
    """Tests for InstanceRegistry without async operations"""

    def test_register_pending_instance(self):
        """Should register instance without connection"""
        result = InstanceRegistry.register_pending_instance(
            name="test-instance",
            host="192.168.1.10",
            port=8650,
            owner="alice"
        )
        
        assert result["success"] == True
        assert "pending" in result["message"]
        
        instance = InstanceRegistry.get_instance("test-instance")
        assert instance is not None
        assert instance.status == "pending"
        assert instance.owner == "alice"

    def test_register_duplicate_fails(self):
        """Should reject duplicate instance names"""
        InstanceRegistry.register_pending_instance("dup", "127.0.0.1", 8650)
        result = InstanceRegistry.register_pending_instance("dup", "127.0.0.1", 8651)
        
        assert result["success"] == False
        assert "already" in result["message"]

    def test_first_instance_becomes_default(self):
        """First registered instance should be default"""
        InstanceRegistry.register_pending_instance("first", "127.0.0.1", 8650)
        default = InstanceRegistry.get_default()
        
        assert default is not None
        assert default.name == "first"

    def test_remove_nonexistent_instance(self):
        """Removing nonexistent instance should fail"""
        result = InstanceRegistry.remove_instance("nonexistent")
        assert result["success"] == False
        assert "not found" in result["message"]


class TestInstanceRegistryPermissions:
    """Tests for permission-based instance access"""

    def test_user_can_remove_own_dynamic_instance(self):
        """User should be able to remove their own dynamic instance"""
        InstanceRegistry.register_pending_instance(
            name="alice-inst",
            host="127.0.0.1",
            port=8650,
            owner="alice",
            is_dynamic=True
        )
        
        result = InstanceRegistry.remove_instance("alice-inst", username="alice", is_admin=False)
        assert result["success"] == True

    def test_user_cannot_remove_others_instance(self):
        """User should NOT be able to remove other users' instances"""
        InstanceRegistry.register_pending_instance(
            name="bob-inst",
            host="127.0.0.1",
            port=8650,
            owner="bob",
            is_dynamic=True
        )
        
        result = InstanceRegistry.remove_instance("bob-inst", username="alice", is_admin=False)
        assert result["success"] == False
        assert "own instances" in result["message"]

    def test_user_cannot_remove_shared_instance(self):
        """User should NOT be able to remove shared instances"""
        InstanceRegistry.register_pending_instance(
            name="shared",
            host="127.0.0.1",
            port=8650,
            owner=None  # Shared instance
        )
        
        result = InstanceRegistry.remove_instance("shared", username="alice", is_admin=False)
        assert result["success"] == False
        # Precise message check: should mention that only admins can remove shared instances
        assert "admin" in result["message"].lower() or "shared" in result["message"].lower()

    def test_admin_can_remove_any_instance(self):
        """Admin should be able to remove any instance"""
        InstanceRegistry.register_pending_instance("bob-inst", "127.0.0.1", 8650, owner="bob")
        InstanceRegistry.register_pending_instance("shared", "127.0.0.1", 8651, owner=None)
        
        result1 = InstanceRegistry.remove_instance("bob-inst", username="admin", is_admin=True)
        assert result1["success"] == True
        
        result2 = InstanceRegistry.remove_instance("shared", username="admin", is_admin=True)
        assert result2["success"] == True


class TestInstanceRegistryUserVisibility:
    """Tests for user-based instance visibility"""

    def test_user_sees_shared_and_own_instances(self):
        """User should see shared instances + their own"""
        InstanceRegistry.register_pending_instance("shared", "127.0.0.1", 8650, owner=None)
        InstanceRegistry.register_pending_instance("alice-inst", "127.0.0.1", 8651, owner="alice")
        InstanceRegistry.register_pending_instance("bob-inst", "127.0.0.1", 8652, owner="bob")
        
        alice_list = InstanceRegistry.list_instances_for_user("alice", is_admin=False)
        names = [inst["name"] for inst in alice_list]
        
        assert "shared" in names
        assert "alice-inst" in names
        assert "bob-inst" not in names
        assert len(alice_list) == 2

    def test_admin_sees_all_instances(self):
        """Admin should see all instances"""
        InstanceRegistry.register_pending_instance("shared", "127.0.0.1", 8650, owner=None)
        InstanceRegistry.register_pending_instance("alice-inst", "127.0.0.1", 8651, owner="alice")
        InstanceRegistry.register_pending_instance("bob-inst", "127.0.0.1", 8652, owner="bob")
        
        admin_list = InstanceRegistry.list_instances_for_user("admin", is_admin=True)
        assert len(admin_list) == 3

    def test_get_instance_for_user_respects_access(self):
        """get_instance_for_user should check access rights"""
        InstanceRegistry.register_pending_instance("bob-inst", "127.0.0.1", 8650, owner="bob")
        
        # Alice cannot access Bob's instance
        assert InstanceRegistry.get_instance_for_user("bob-inst", "alice", False) is None
        
        # Bob can access his own
        assert InstanceRegistry.get_instance_for_user("bob-inst", "bob", False) is not None
        
        # Admin can access any
        assert InstanceRegistry.get_instance_for_user("bob-inst", "admin", True) is not None


class TestInstanceRegistryDefaults:
    """Tests for default instance management"""

    def test_set_default_instance(self):
        """Should be able to set default instance"""
        InstanceRegistry.register_pending_instance("inst1", "127.0.0.1", 8650)
        InstanceRegistry.register_pending_instance("inst2", "127.0.0.1", 8651)
        
        result = InstanceRegistry.set_default("inst2")
        assert result["success"] == True
        
        default = InstanceRegistry.get_default()
        assert default.name == "inst2"

    def test_removing_default_selects_new_default(self):
        """Removing default instance should auto-select another"""
        InstanceRegistry.register_pending_instance("inst1", "127.0.0.1", 8650)
        InstanceRegistry.register_pending_instance("inst2", "127.0.0.1", 8651)
        
        # inst1 is default (first added)
        assert InstanceRegistry.get_default().name == "inst1"
        
        # Remove default
        InstanceRegistry.remove_instance("inst1", is_admin=True)
        
        # inst2 should become default
        new_default = InstanceRegistry.get_default()
        assert new_default is not None
        assert new_default.name == "inst2"
