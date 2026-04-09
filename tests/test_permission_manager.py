import pytest

from services.permission_manager import PermissionManager


@pytest.fixture
def pm() -> PermissionManager:
    return PermissionManager()


class TestGlobalBlacklist:
    def test_blocked_user_denied_command(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=["user1"],
            command_user_list=["user1"],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, reason = pm.check_command_permission("user1")
        assert ok is False
        assert "全局禁止" in reason

    def test_blocked_user_denied_action(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=["user1"],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, reason = pm.check_action_permission("user1")
        assert ok is False
        assert "全局禁止" in reason


class TestWhitelistMode:
    def test_user_in_whitelist_allowed(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=[],
            command_user_list=["user1"],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, _ = pm.check_command_permission("user1")
        assert ok is True

    def test_user_not_in_whitelist_denied(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=[],
            command_user_list=["user1"],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, reason = pm.check_command_permission("user2")
        assert ok is False
        assert "没有使用" in reason


class TestBlacklistMode:
    def test_user_in_blacklist_denied(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=[],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=["user1"],
            action_user_list_mode="blacklist",
        )
        ok, reason = pm.check_action_permission("user1")
        assert ok is False
        assert "没有使用" in reason

    def test_user_not_in_blacklist_allowed(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=[],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=["user1"],
            action_user_list_mode="blacklist",
        )
        ok, _ = pm.check_action_permission("user2")
        assert ok is True


class TestUserIdNormalization:
    def test_whitespace_stripped(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=["  user1  "],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, _ = pm.check_command_permission("user1")
        assert ok is False

    def test_empty_ids_filtered(self, pm: PermissionManager):
        pm.configure(
            global_blacklist=["", "  "],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        assert pm.global_blacklist == set()


class TestDefaultBehavior:
    def test_default_command_whitelist_empty_denies_all(self):
        pm = PermissionManager()
        pm.configure(
            global_blacklist=[],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, _ = pm.check_command_permission("anyone")
        assert ok is False

    def test_default_action_blacklist_empty_allows_all(self):
        pm = PermissionManager()
        pm.configure(
            global_blacklist=[],
            command_user_list=[],
            command_user_list_mode="whitelist",
            action_user_list=[],
            action_user_list_mode="blacklist",
        )
        ok, _ = pm.check_action_permission("anyone")
        assert ok is True
