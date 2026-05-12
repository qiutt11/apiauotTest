"""depends 跨文件依赖机制测试。"""
import os

import responses as responses_mock
import pytest

from common.config_loader import load_config
from common.variable_pool import VariablePool
from common.data_loader import load_testcases
from common.runner import run_testcase
from common.hook_manager import HookManager


def _make_config(tmp_path, base_url="http://mock-api.local"):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "current_env: test\ntimeout: 10\nreport_type: html\n"
        "email:\n  enabled: false\n"
    )
    (config_dir / "test.yaml").write_text(
        f"base_url: {base_url}\n"
        f"global_variables:\n  admin_user: admin\n  admin_pass: '123456'\n"
    )
    return str(config_dir)


def _setup_mock_config(tmp_path):
    """Create config and return (cfg, pool, hooks)."""
    config_dir = _make_config(tmp_path)
    cfg = load_config(config_dir)
    pool = VariablePool()
    for k, v in cfg.get("global_variables", {}).items():
        pool.set_global(k, v)
    hooks = HookManager(str(tmp_path / "hooks"))
    return cfg, pool, hooks


class TestResolveDepends:
    """Test _resolve_depends function from conftest."""

    def test_single_dependency(self, tmp_path):
        """依赖文件执行后，变量应注入当前文件的 module scope。"""
        responses_mock.start()
        try:
            responses_mock.add(
                responses_mock.POST, "http://mock-api.local/api/login",
                json={"code": 0, "data": {"token": "dep-token-abc"}},
                status=200,
            )

            # 创建依赖文件
            tc_dir = tmp_path / "testcases" / "login"
            tc_dir.mkdir(parents=True)
            (tc_dir / "login.yaml").write_text(
                "module: 登录\n"
                "testcases:\n"
                "  - name: 登录\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body: {username: admin, password: '123456'}\n"
                "    extract:\n"
                "      token: $.data.token\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"
            )

            cfg, pool, hooks = _setup_mock_config(tmp_path)

            # 模拟 _resolve_depends 的核心逻辑
            from conftest import _resolve_depends, _find_testcases_dir_from_path

            class FakeConfig:
                pass

            fake_config = FakeConfig()
            fake_config._autotest_config = cfg
            fake_config._autotest_pool = pool
            fake_config._autotest_logger = __import__("loguru").logger
            fake_config._autotest_hooks = hooks
            fake_config._autotest_db = None
            fake_config._autotest_depends_cache = {}

            dep_path = str(tc_dir / "login.yaml")
            _resolve_depends([dep_path], fake_config)

            # 验证变量已注入
            assert pool.get("token") == "dep-token-abc"
            # 验证已缓存
            assert dep_path in fake_config._autotest_depends_cache
            assert fake_config._autotest_depends_cache[dep_path]["token"] == "dep-token-abc"
        finally:
            responses_mock.stop()
            responses_mock.reset()

    def test_dependency_cached(self, tmp_path):
        """同一个依赖文件只执行一次，第二次从缓存读取。"""
        responses_mock.start()
        try:
            responses_mock.add(
                responses_mock.POST, "http://mock-api.local/api/login",
                json={"code": 0, "data": {"token": "cached-token"}},
                status=200,
            )

            tc_dir = tmp_path / "testcases" / "login"
            tc_dir.mkdir(parents=True)
            (tc_dir / "login.yaml").write_text(
                "module: 登录\n"
                "testcases:\n"
                "  - name: 登录\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body: {username: admin, password: '123456'}\n"
                "    extract:\n"
                "      token: $.data.token\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"
            )

            cfg, pool, hooks = _setup_mock_config(tmp_path)

            from conftest import _resolve_depends

            class FakeConfig:
                pass

            fake_config = FakeConfig()
            fake_config._autotest_config = cfg
            fake_config._autotest_pool = pool
            fake_config._autotest_logger = __import__("loguru").logger
            fake_config._autotest_hooks = hooks
            fake_config._autotest_db = None
            fake_config._autotest_depends_cache = {}

            dep_path = str(tc_dir / "login.yaml")

            # 第一次执行
            _resolve_depends([dep_path], fake_config)
            assert len(responses_mock.calls) == 1

            # 清掉 module 变量模拟文件切换
            pool.clear_module()

            # 第二次执行（应从缓存读取，不发 HTTP）
            _resolve_depends([dep_path], fake_config)
            assert len(responses_mock.calls) == 1  # 没有新请求
            assert pool.get("token") == "cached-token"  # 变量仍然注入了
        finally:
            responses_mock.stop()
            responses_mock.reset()

    def test_chain_dependency(self, tmp_path):
        """链式依赖：A depends B depends C，变量逐级传递。"""
        responses_mock.start()
        try:
            responses_mock.add(
                responses_mock.POST, "http://mock-api.local/api/login",
                json={"code": 0, "data": {"token": "chain-token"}},
                status=200,
            )
            responses_mock.add(
                responses_mock.POST, "http://mock-api.local/api/user",
                json={"code": 0, "data": {"id": 42}},
                status=200,
            )

            tc_dir = tmp_path / "testcases"
            login_dir = tc_dir / "login"
            login_dir.mkdir(parents=True)
            user_dir = tc_dir / "user"
            user_dir.mkdir(parents=True)

            # login.yaml（无依赖）
            (login_dir / "login.yaml").write_text(
                "module: 登录\n"
                "testcases:\n"
                "  - name: 登录\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body: {username: admin, password: '123456'}\n"
                "    extract:\n"
                "      token: $.data.token\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"
            )

            # create_user.yaml（依赖 login）
            (user_dir / "create_user.yaml").write_text(
                "module: 创建用户\n"
                "depends: login/login.yaml\n"
                "testcases:\n"
                "  - name: 创建用户\n"
                "    method: POST\n"
                "    url: /api/user\n"
                "    headers:\n"
                "      Authorization: Bearer ${token}\n"
                "    body: {name: test}\n"
                "    extract:\n"
                "      user_id: $.data.id\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"
            )

            cfg, pool, hooks = _setup_mock_config(tmp_path)

            from conftest import _resolve_depends

            class FakeConfig:
                pass

            fake_config = FakeConfig()
            fake_config._autotest_config = cfg
            fake_config._autotest_pool = pool
            fake_config._autotest_logger = __import__("loguru").logger
            fake_config._autotest_hooks = hooks
            fake_config._autotest_db = None
            fake_config._autotest_depends_cache = {}

            # 执行 create_user 的依赖（它会递归先执行 login）
            dep_path = str(user_dir / "create_user.yaml")
            _resolve_depends([dep_path], fake_config)

            # login 的 token 和 create_user 的 user_id 都应可用
            assert pool.get("token") == "chain-token"
            assert pool.get("user_id") == 42
        finally:
            responses_mock.stop()
            responses_mock.reset()

    def test_dependency_failure_raises(self, tmp_path):
        """依赖文件中用例失败时应抛出 TestCaseFailure。"""
        responses_mock.start()
        try:
            responses_mock.add(
                responses_mock.POST, "http://mock-api.local/api/login",
                json={"code": 500, "msg": "error"},
                status=200,
            )

            tc_dir = tmp_path / "testcases" / "login"
            tc_dir.mkdir(parents=True)
            (tc_dir / "login.yaml").write_text(
                "module: 登录\n"
                "testcases:\n"
                "  - name: 登录\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body: {username: admin, password: '123456'}\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"  # 会失败，实际返回 500
            )

            cfg, pool, hooks = _setup_mock_config(tmp_path)

            from conftest import _resolve_depends, TestCaseFailure

            class FakeConfig:
                pass

            fake_config = FakeConfig()
            fake_config._autotest_config = cfg
            fake_config._autotest_pool = pool
            fake_config._autotest_logger = __import__("loguru").logger
            fake_config._autotest_hooks = hooks
            fake_config._autotest_db = None
            fake_config._autotest_depends_cache = {}

            with pytest.raises(TestCaseFailure, match="Dependency failed"):
                _resolve_depends([str(tc_dir / "login.yaml")], fake_config)
        finally:
            responses_mock.stop()
            responses_mock.reset()


class TestDependsYamlParsing:
    """Test depends field parsing in YAML."""

    def test_depends_string_format(self, tmp_path):
        """depends 支持字符串格式（单个依赖）。"""
        tc_dir = tmp_path / "testcases" / "user"
        tc_dir.mkdir(parents=True)
        (tc_dir / "test.yaml").write_text(
            "module: 测试\n"
            "depends: login/login.yaml\n"
            "testcases:\n"
            "  - name: test\n"
            "    method: GET\n"
            "    url: /api/test\n"
        )

        data = load_testcases(str(tc_dir / "test.yaml"))
        depends = data.get("depends", [])
        if isinstance(depends, str):
            depends = [depends]
        assert depends == ["login/login.yaml"]

    def test_depends_list_format(self, tmp_path):
        """depends 支持列表格式（多个依赖）。"""
        tc_dir = tmp_path / "testcases" / "order"
        tc_dir.mkdir(parents=True)
        (tc_dir / "test.yaml").write_text(
            "module: 测试\n"
            "depends:\n"
            "  - login/login.yaml\n"
            "  - user/create_user.yaml\n"
            "testcases:\n"
            "  - name: test\n"
            "    method: GET\n"
            "    url: /api/test\n"
        )

        data = load_testcases(str(tc_dir / "test.yaml"))
        depends = data.get("depends", [])
        assert depends == ["login/login.yaml", "user/create_user.yaml"]

    def test_no_depends(self, tmp_path):
        """没有 depends 字段时返回空列表。"""
        tc_dir = tmp_path / "testcases" / "basic"
        tc_dir.mkdir(parents=True)
        (tc_dir / "test.yaml").write_text(
            "module: 测试\n"
            "testcases:\n"
            "  - name: test\n"
            "    method: GET\n"
            "    url: /api/test\n"
        )

        data = load_testcases(str(tc_dir / "test.yaml"))
        depends = data.get("depends", [])
        assert depends == []
