"""Integration tests: full pipeline from YAML → conftest collection → runner → report.

Uses the `responses` library to mock HTTP at the requests level.
Includes subprocess tests that exercise the full conftest.py pipeline.
"""

import json
import os
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYTHON = sys.executable


def _make_config(tmp_path, base_url="http://mock-api.local", extra_env=None):
    """Create minimal config files in tmp_path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "config.yaml").write_text(
        f"current_env: test\ntimeout: 10\nreport_type: html\n"
        f"email:\n  enabled: false\n"
    )
    env_content = (
        f"base_url: {base_url}\n"
        f"global_headers:\n  Content-Type: application/json\n"
        f"global_variables:\n  admin_user: admin\n  admin_pass: '123456'\n"
    )
    if extra_env:
        env_content += extra_env
    (config_dir / "test.yaml").write_text(env_content)
    return str(config_dir)


# ---------------------------------------------------------------------------
# Test 1: Full pipeline — YAML collection → variable extract → chained request
# ---------------------------------------------------------------------------
class TestFullPipeline:
    """Test runner execution with real YAML loading and mocked HTTP."""

    def test_yaml_load_and_runner_execution(self, tmp_path):
        """YAML data loaded by data_loader should execute correctly through runner."""
        import responses

        # Setup mock API
        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/login",
                json={"code": 0, "msg": "success", "data": {"token": "test-token-123"}},
                status=200,
            )

            # Create testcase
            tc_dir = tmp_path / "testcases" / "login"
            tc_dir.mkdir(parents=True)
            (tc_dir / "login.yaml").write_text(
                "module: 登录测试\n"
                "testcases:\n"
                "  - name: 登录成功\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body:\n"
                "      username: admin\n"
                "      password: '123456'\n"
                "    extract:\n"
                "      token: $.data.token\n"
                "    validate:\n"
                "      - eq: [status_code, 200]\n"
                "      - eq: [$.code, 0]\n"
                "      - not_null: [$.data.token]\n"
            )

            # Create config
            config_dir = _make_config(tmp_path)

            # Run via runner directly (to stay in-process with mocked HTTP)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.data_loader import load_testcases
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            data = load_testcases(str(tc_dir / "login.yaml"))
            assert data["module"] == "登录测试"
            assert len(data["testcases"]) == 1

            case = data["testcases"][0]
            result = run_testcase(
                case=case,
                base_url=cfg["base_url"],
                pool=pool,
                timeout=cfg.get("timeout", 10),
                hook_manager=hooks,
                global_headers=cfg.get("global_headers", {}),
            )

            assert result["passed"] is True
            assert result["error"] is None
            assert pool.get("token") == "test-token-123"
        finally:
            responses.stop()
            responses.reset()

    def test_variable_chaining_across_cases(self, tmp_path):
        """Variables extracted in case 1 should be available in case 2."""
        import responses

        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/login",
                json={"code": 0, "data": {"token": "chain-token"}},
                status=200,
            )
            responses.add(
                responses.GET, "http://mock-api.local/api/users",
                json={"code": 0, "data": {"total": 5, "list": []}},
                status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            # Case 1: login and extract token
            case1 = {
                "name": "登录",
                "method": "POST",
                "url": "/api/login",
                "body": {"username": "${admin_user}", "password": "${admin_pass}"},
                "extract": {"token": "$.data.token"},
                "validate": [{"eq": ["$.code", 0]}],
            }
            r1 = run_testcase(case1, cfg["base_url"], pool, 10, hooks,
                              global_headers=cfg.get("global_headers", {}))
            assert r1["passed"] is True
            assert pool.get("token") == "chain-token"

            # Case 2: use token in Authorization header
            case2 = {
                "name": "查用户",
                "method": "GET",
                "url": "/api/users",
                "headers": {"Authorization": "Bearer ${token}"},
                "validate": [
                    {"eq": ["status_code", 200]},
                    {"eq": ["$.code", 0]},
                    {"gt": ["$.data.total", 0]},
                ],
            }
            r2 = run_testcase(case2, cfg["base_url"], pool, 10, hooks,
                              global_headers=cfg.get("global_headers", {}))
            assert r2["passed"] is True

            # Verify the actual request had the token
            assert responses.calls[1].request.headers["Authorization"] == "Bearer chain-token"
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 2: Variable isolation between files
# ---------------------------------------------------------------------------
class TestVariableIsolation:
    """Variables from one YAML file should not leak into another."""

    def test_clear_module_between_files(self, tmp_path):
        """Simulates the conftest clear_module logic between files."""
        import responses

        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/login",
                json={"code": 0, "data": {"token": "file1-token"}},
                status=200,
            )
            responses.add(
                responses.GET, "http://mock-api.local/api/health",
                json={"code": 0, "status": "ok"},
                status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            # File 1: login → extracts token
            case1 = {
                "name": "登录",
                "method": "POST",
                "url": "/api/login",
                "body": {"username": "admin", "password": "123"},
                "extract": {"token": "$.data.token"},
                "validate": [{"eq": ["$.code", 0]}],
            }
            r1 = run_testcase(case1, cfg["base_url"], pool, 10, hooks,
                              global_headers=cfg.get("global_headers", {}))
            assert r1["passed"] is True
            assert pool.get("token") == "file1-token"

            # Simulate transitioning to a new file (conftest does this)
            pool.clear_module()

            # File 2: token should be gone
            assert pool.get("token") is None

            # Global variables should still work
            assert pool.get("admin_user") == "admin"
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 3: Global headers merge
# ---------------------------------------------------------------------------
class TestGlobalHeaders:
    """global_headers from config should be applied and overridable."""

    def test_global_headers_applied(self, tmp_path):
        import responses

        responses.start()
        try:
            responses.add(
                responses.GET, "http://mock-api.local/api/test",
                json={"code": 0}, status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            hooks = HookManager(str(tmp_path / "hooks"))

            case = {
                "name": "测试全局头",
                "method": "GET",
                "url": "/api/test",
                "validate": [{"eq": ["status_code", 200]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is True

            # Verify global Content-Type was applied
            assert responses.calls[0].request.headers["Content-Type"] == "application/json"
        finally:
            responses.stop()
            responses.reset()

    def test_case_headers_override_global(self, tmp_path):
        import responses

        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/upload",
                json={"code": 0}, status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            hooks = HookManager(str(tmp_path / "hooks"))

            case = {
                "name": "覆盖全局头",
                "method": "POST",
                "url": "/api/upload",
                "headers": {"Content-Type": "multipart/form-data"},
                "validate": [{"eq": ["status_code", 200]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is True

            # Case header should override global
            assert responses.calls[0].request.headers["Content-Type"] == "multipart/form-data"
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 4: Hook integration
# ---------------------------------------------------------------------------
class TestHookIntegration:
    """Hooks should be loaded and called during test execution."""

    def test_before_hook_modifies_request(self, tmp_path):
        import responses

        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/pay",
                json={"code": 0}, status=200,
            )

            # Create hook file
            hooks_dir = tmp_path / "hooks"
            hooks_dir.mkdir()
            (hooks_dir / "pay_hooks.py").write_text(
                "def add_sign(request_data):\n"
                "    body = request_data.get('body', {})\n"
                "    body['sign'] = 'test-signature'\n"
                "    request_data['body'] = body\n"
                "    return request_data\n"
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            hooks = HookManager(str(hooks_dir))

            case = {
                "name": "签名测试",
                "method": "POST",
                "url": "/api/pay",
                "body": {"order_id": "123"},
                "hook": {"before": "add_sign"},
                "validate": [{"eq": ["status_code", 200]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is True

            # Verify hook added the sign field
            sent_body = json.loads(responses.calls[0].request.body)
            assert sent_body["sign"] == "test-signature"
            assert sent_body["order_id"] == "123"
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 5: Failure handling
# ---------------------------------------------------------------------------
class TestFailureHandling:
    """Test that failures are properly reported, not silently swallowed."""

    def test_validation_failure_returns_passed_false(self, tmp_path):
        import responses

        responses.start()
        try:
            responses.add(
                responses.GET, "http://mock-api.local/api/test",
                json={"code": 500, "msg": "server error"}, status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            hooks = HookManager(str(tmp_path / "hooks"))

            case = {
                "name": "应该失败",
                "method": "GET",
                "url": "/api/test",
                "validate": [{"eq": ["$.code", 0]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is False
            assert any(not v["passed"] for v in r["validations"])
        finally:
            responses.stop()
            responses.reset()

    def test_connection_error_returns_error(self, tmp_path):
        """When the server is unreachable, error should be captured, not crash."""
        import responses

        responses.start()
        try:
            responses.add(
                responses.GET, "http://mock-api.local/api/test",
                body=ConnectionError("Connection refused"),
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            hooks = HookManager(str(tmp_path / "hooks"))

            case = {
                "name": "连接失败",
                "method": "GET",
                "url": "/api/test",
                "validate": [{"eq": ["status_code", 200]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 3, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is False
            assert r["error"] is not None
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 6: Data loader integration (all formats produce same result)
# ---------------------------------------------------------------------------
class TestDataLoaderFormats:
    """YAML, JSON, and Excel should produce equivalent test case structures."""

    def test_yaml_json_equivalence(self, tmp_path):
        from common.data_loader import load_testcases

        yaml_content = (
            "module: 测试\n"
            "testcases:\n"
            "  - name: 用例1\n"
            "    method: GET\n"
            "    url: /api/test\n"
            "    validate:\n"
            "      - eq: [status_code, 200]\n"
        )
        json_content = json.dumps({
            "module": "测试",
            "testcases": [{
                "name": "用例1",
                "method": "GET",
                "url": "/api/test",
                "validate": [{"eq": ["status_code", 200]}],
            }]
        }, ensure_ascii=False)

        (tmp_path / "test.yaml").write_text(yaml_content)
        (tmp_path / "test.json").write_text(json_content)

        yaml_data = load_testcases(str(tmp_path / "test.yaml"))
        json_data = load_testcases(str(tmp_path / "test.json"))

        assert yaml_data["module"] == json_data["module"]
        assert len(yaml_data["testcases"]) == len(json_data["testcases"])
        assert yaml_data["testcases"][0]["name"] == json_data["testcases"][0]["name"]
        assert yaml_data["testcases"][0]["method"] == json_data["testcases"][0]["method"]

    def test_excel_format(self, tmp_path):
        """Excel loading should produce valid test case dicts."""
        from openpyxl import Workbook
        from common.data_loader import load_testcases

        wb = Workbook()
        ws = wb.active
        ws.title = "测试模块"
        ws.append(["name", "method", "url", "headers", "body", "extract", "validate"])
        ws.append([
            "用例1", "POST", "/api/login", "",
            '{"username":"admin"}', '{"token":"$.data.token"}',
            '[{"eq":["$.code",0]}]'
        ])
        xlsx_path = str(tmp_path / "test.xlsx")
        wb.save(xlsx_path)

        data = load_testcases(xlsx_path)
        assert data["module"] == "测试模块"
        assert len(data["testcases"]) == 1
        case = data["testcases"][0]
        assert case["name"] == "用例1"
        assert case["method"] == "POST"
        assert case["body"] == {"username": "admin"}
        assert case["extract"] == {"token": "$.data.token"}
        assert case["validate"] == [{"eq": ["$.code", 0]}]


# ---------------------------------------------------------------------------
# Test 7: Config deep merge
# ---------------------------------------------------------------------------
class TestConfigIntegration:
    """Config loading with environment override should deep-merge correctly."""

    def test_deep_merge_preserves_nested(self, tmp_path):
        from common.config_loader import load_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "config.yaml").write_text(
            "current_env: test\n"
            "timeout: 30\n"
            "email:\n"
            "  enabled: false\n"
            "  smtp_host: smtp.qq.com\n"
            "  smtp_port: 465\n"
            "  send_on: fail\n"
        )
        (config_dir / "test.yaml").write_text(
            "base_url: http://test.local\n"
            "email:\n"
            "  enabled: true\n"
        )

        cfg = load_config(str(config_dir))
        # Overridden
        assert cfg["email"]["enabled"] is True
        assert cfg["base_url"] == "http://test.local"
        # Preserved (not lost by shallow merge)
        assert cfg["email"]["smtp_host"] == "smtp.qq.com"
        assert cfg["email"]["smtp_port"] == 465
        assert cfg["email"]["send_on"] == "fail"
        assert cfg["timeout"] == 30

    def test_env_override_via_parameter(self, tmp_path):
        from common.config_loader import load_config

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        (config_dir / "config.yaml").write_text("current_env: test\ntimeout: 30\n")
        (config_dir / "test.yaml").write_text("base_url: http://test.local\n")
        (config_dir / "dev.yaml").write_text("base_url: http://dev.local\n")

        cfg_test = load_config(str(config_dir), env="test")
        cfg_dev = load_config(str(config_dir), env="dev")

        assert cfg_test["base_url"] == "http://test.local"
        assert cfg_dev["base_url"] == "http://dev.local"


# ---------------------------------------------------------------------------
# Test 8: CLI entry point (run.py)
# ---------------------------------------------------------------------------
class TestCLI:
    """run.py should accept CLI args and invoke pytest."""

    def test_help_output(self):
        result = subprocess.run(
            [PYTHON, "run.py", "--help"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10,
        )
        assert result.returncode == 0
        assert "--env" in result.stdout
        assert "--path" in result.stdout
        assert "--report" in result.stdout

    def test_nonexistent_path_fails(self):
        result = subprocess.run(
            [PYTHON, "run.py", "--path", "nonexistent_dir"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30,
        )
        # pytest should return non-zero when no tests found or path invalid
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Test 9: Variable type preservation in full flow
# ---------------------------------------------------------------------------
class TestVariableTypePreservation:
    """${var} should preserve int/bool types when used as entire field value."""

    def test_int_preserved_in_body(self, tmp_path):
        import responses

        responses.start()
        try:
            responses.add(
                responses.POST, "http://mock-api.local/api/users/100/update",
                json={"code": 0}, status=200,
            )

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager

            cfg = load_config(config_dir)
            pool = VariablePool()
            pool.set_module("user_id", 100)  # int, not string
            hooks = HookManager(str(tmp_path / "hooks"))

            case = {
                "name": "类型保留测试",
                "method": "POST",
                "url": "/api/users/${user_id}/update",
                "body": {"id": "${user_id}", "name": "User ${user_id}"},
                "validate": [{"eq": ["status_code", 200]}],
            }
            r = run_testcase(case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is True

            sent_body = json.loads(responses.calls[0].request.body)
            # body.id should be int (single ${var})
            assert sent_body["id"] == 100
            assert isinstance(sent_body["id"], int)
            # body.name should be string (embedded ${var})
            assert sent_body["name"] == "User 100"
            assert isinstance(sent_body["name"], str)
        finally:
            responses.stop()
            responses.reset()


# ---------------------------------------------------------------------------
# Test 10: Subprocess conftest pipeline (real pytest collection → execution → stats)
# ---------------------------------------------------------------------------
class TestConftestPipeline:
    """Test the full conftest.py pipeline via subprocess — collection, execution, stats."""

    def _run_subprocess(self, testcase_dir, config_dir, extra_args=None):
        """Run pytest as a subprocess with AUTOTEST_CONFIG_DIR set.

        Uses --rootdir and -c to ensure the project's conftest.py is loaded.
        """
        args = [
            PYTHON, "-m", "pytest",
            testcase_dir,
            "-v", "--tb=short", "--no-header",
            f"--rootdir={PROJECT_ROOT}",
            f"-c={os.path.join(PROJECT_ROOT, 'pytest.ini')}",
        ]
        if extra_args:
            args.extend(extra_args)
        env = os.environ.copy()
        env["AUTOTEST_CONFIG_DIR"] = config_dir
        return subprocess.run(
            args, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
        )

    def test_conftest_collects_and_runs_yaml(self):
        """conftest.py should discover YAML files under testcases/ and execute them.

        Uses the project's own testcases directory with a temporary YAML file.
        """
        tc_dir = os.path.join(PROJECT_ROOT, "testcases", "_integration_tmp")
        os.makedirs(tc_dir, exist_ok=True)
        yaml_path = os.path.join(tc_dir, "smoke.yaml")

        try:
            with open(yaml_path, "w") as f:
                f.write(
                    "module: SmokeTest\n"
                    "testcases:\n"
                    "  - name: httpbin_get\n"
                    "    method: GET\n"
                    "    url: /get\n"
                    "    validate:\n"
                    "      - eq: [status_code, 200]\n"
                )

            # Use the project's own config, pointing to httpbin
            config_dir = os.path.join(PROJECT_ROOT, "config")
            # Create a temporary env override
            tmp_env = os.path.join(config_dir, "_inttest.yaml")
            with open(tmp_env, "w") as f:
                f.write(
                    "base_url: https://httpbin.org\n"
                    "global_headers:\n  Accept: application/json\n"
                    "global_variables: {}\n"
                )

            result = self._run_subprocess(
                str(tc_dir), config_dir,
                extra_args=["--env", "_inttest"],
            )

            assert "httpbin_get" in result.stdout, (
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
            # The test case should be collected and executed (pass or fail)
            assert "1 passed" in result.stdout or "1 failed" in result.stdout
        finally:
            if os.path.exists(yaml_path):
                os.remove(yaml_path)
            if os.path.exists(tc_dir):
                os.rmdir(tc_dir)
            tmp_env = os.path.join(config_dir, "_inttest.yaml")
            if os.path.exists(tmp_env):
                os.remove(tmp_env)

    def test_stats_json_written(self):
        """pytest_sessionfinish should write .stats.json with correct counts."""
        tc_dir = os.path.join(PROJECT_ROOT, "testcases", "_integration_tmp2")
        os.makedirs(tc_dir, exist_ok=True)
        yaml_path = os.path.join(tc_dir, "mixed.yaml")
        config_dir = os.path.join(PROJECT_ROOT, "config")
        tmp_env = os.path.join(config_dir, "_inttest2.yaml")

        try:
            with open(yaml_path, "w") as f:
                f.write(
                    "module: Mixed\n"
                    "testcases:\n"
                    "  - name: should_pass\n"
                    "    method: GET\n"
                    "    url: /get\n"
                    "    validate:\n"
                    "      - eq: [status_code, 200]\n"
                    "  - name: should_fail\n"
                    "    method: GET\n"
                    "    url: /get\n"
                    "    validate:\n"
                    "      - eq: [status_code, 999]\n"
                )
            with open(tmp_env, "w") as f:
                f.write(
                    "base_url: https://httpbin.org\n"
                    "global_headers:\n  Accept: application/json\n"
                    "global_variables: {}\n"
                )

            self._run_subprocess(
                str(tc_dir), config_dir,
                extra_args=["--env", "_inttest2"],
            )

            stats_path = os.path.join(PROJECT_ROOT, "reports", ".stats.json")
            assert os.path.exists(stats_path), f"Stats file not found at {stats_path}"

            with open(stats_path) as f:
                stats = json.load(f)

            assert stats["total"] == 2
            assert stats["passed"] == 1
            assert stats["failed"] == 1
            assert "pass_rate" in stats
            assert len(stats["failures"]) == 1
            assert stats["failures"][0]["name"] == "should_fail"
        finally:
            if os.path.exists(yaml_path):
                os.remove(yaml_path)
            if os.path.exists(tc_dir):
                os.rmdir(tc_dir)
            if os.path.exists(tmp_env):
                os.remove(tmp_env)
