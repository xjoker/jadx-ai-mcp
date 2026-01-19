"""
Layer 1 Unit Tests: UserAuth

Tests user authentication and permission logic without external dependencies.
"""

import pytest

from server.user_auth import UserAuthManager, AuthenticatedUser
from server.config_loader import UserConfig


class TestAuthenticatedUser:
    """Tests for AuthenticatedUser dataclass"""

    def test_str_representation_user(self):
        """Regular user should show 'user' role"""
        user = AuthenticatedUser(name="alice", token="xxx", is_admin=False)
        assert str(user) == "alice (user)"

    def test_str_representation_admin(self):
        """Admin should show 'admin' role"""
        user = AuthenticatedUser(name="admin", token="xxx", is_admin=True)
        assert str(user) == "admin (admin)"


class TestUserAuthManager:
    """Tests for UserAuthManager singleton"""

    def test_configure_users(self):
        """Should configure users from config list"""
        users = [
            UserConfig(name="alice", token="token-alice"),
            UserConfig(name="bob", token="token-bob", is_admin=True),
        ]
        UserAuthManager.configure(users)
        
        assert UserAuthManager.get_user_count() == 2
        assert "alice" in UserAuthManager.list_users()
        assert "bob" in UserAuthManager.list_users()

    def test_authenticate_valid_token(self):
        """Valid token should return user"""
        users = [UserConfig(name="alice", token="token-alice")]
        UserAuthManager.configure(users)
        
        user = UserAuthManager.authenticate("token-alice")
        assert user is not None
        assert user.name == "alice"

    def test_authenticate_invalid_token(self):
        """Invalid token should return None"""
        users = [UserConfig(name="alice", token="token-alice")]
        UserAuthManager.configure(users)
        
        user = UserAuthManager.authenticate("bad-token")
        assert user is None

    def test_authenticate_anonymous_disabled(self):
        """Empty token should fail when anonymous disabled"""
        UserAuthManager.configure([], allow_anonymous=False)
        
        user = UserAuthManager.authenticate("")
        assert user is None

    def test_authenticate_anonymous_enabled(self):
        """Empty token should return anonymous user when enabled"""
        UserAuthManager.configure([], allow_anonymous=True)
        
        user = UserAuthManager.authenticate("")
        assert user is not None
        assert user.name == "anonymous"
        assert user.is_admin == False

    def test_current_user_context(self):
        """Should track current user in request context"""
        test_user = AuthenticatedUser(name="test", token="xxx")
        
        UserAuthManager.set_current_user(test_user)
        assert UserAuthManager.get_current_user() == test_user
        assert UserAuthManager.get_current_username() == "test"
        
        UserAuthManager.set_current_user(None)
        assert UserAuthManager.get_current_user() is None
        assert UserAuthManager.get_current_username() is None

    def test_is_current_user_admin(self):
        """Should correctly identify admin status"""
        # No user
        assert UserAuthManager.is_current_user_admin() == False
        
        # Regular user
        UserAuthManager.set_current_user(AuthenticatedUser(name="user", token="x", is_admin=False))
        assert UserAuthManager.is_current_user_admin() == False
        
        # Admin user
        UserAuthManager.set_current_user(AuthenticatedUser(name="admin", token="x", is_admin=True))
        assert UserAuthManager.is_current_user_admin() == True

    def test_default_jadx_token(self):
        """Should store and return default JADX token"""
        UserAuthManager.configure([], default_jadx_token="secret-jadx-token")
        assert UserAuthManager.get_default_jadx_token() == "secret-jadx-token"

    def test_empty_token_user_skipped(self):
        """Users with empty tokens should be skipped"""
        users = [
            UserConfig(name="valid", token="token-valid"),
            UserConfig(name="empty", token=""),
        ]
        UserAuthManager.configure(users)
        
        assert UserAuthManager.get_user_count() == 1
        assert "valid" in UserAuthManager.list_users()
        assert "empty" not in UserAuthManager.list_users()
