from unittest.mock import patch, MagicMock

from common.runner import run_testcase
from common.variable_pool import VariablePool


@patch("common.runner.send_request")
def test_run_simple_testcase(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "msg": "success"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "测试用例",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["status_code", 200]}, {"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert result["response"]["status_code"] == 200


@patch("common.runner.send_request")
def test_run_testcase_with_extract(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"token": "abc123"}},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "登录",
        "method": "POST",
        "url": "/api/login",
        "body": {"username": "admin", "password": "123456"},
        "extract": {"token": "$.data.token"},
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert pool.get("token") == "abc123"


@patch("common.runner.send_request")
def test_run_testcase_with_variable_resolve(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    pool.set_module("token", "xyz")
    case = {
        "name": "带token请求",
        "method": "GET",
        "url": "/api/users",
        "headers": {"Authorization": "Bearer ${token}"},
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    call_kwargs = mock_send.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer xyz"


@patch("common.runner.send_request")
def test_run_testcase_validation_failure(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 500, "msg": "server error"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "失败用例",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is False


@patch("common.runner.send_request")
def test_run_testcase_request_error(mock_send):
    mock_send.return_value = {
        "status_code": None,
        "body": None,
        "headers": None,
        "elapsed_ms": 0,
        "error": "Timeout: connection timed out",
    }

    pool = VariablePool()
    case = {
        "name": "超时用例",
        "method": "GET",
        "url": "/api/slow",
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=5)

    assert result["passed"] is False
    assert result["error"] is not None


@patch("common.runner.send_request")
def test_run_testcase_with_db_setup_and_teardown(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    mock_db = MagicMock()
    mock_db.execute_setup.return_value = {}  # No extract
    case = {
        "name": "DB测试",
        "method": "DELETE",
        "url": "/api/users/9999",
        "db_setup": [{"sql": "INSERT INTO users VALUES (9999, 'test')"}],
        "db_teardown": [{"sql": "DELETE FROM users WHERE id = 9999"}],
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, db_handler=mock_db)

    assert result["passed"] is True
    mock_db.execute_setup.assert_called_once()
    mock_db.execute_teardown.assert_called_once()


@patch("common.runner.send_request")
def test_run_testcase_with_db_setup_extract(mock_send):
    """db_setup with extract should inject variables into pool and re-resolve request."""
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    mock_db = MagicMock()
    mock_db.execute_setup.return_value = {"phone": "13800001111"}
    case = {
        "name": "DB Setup提取",
        "method": "POST",
        "url": "/api/register",
        "body": {"phone": "${phone}"},
        "db_setup": [
            {"sql": "SELECT '13800001111' AS phone", "extract": {"phone": "phone"}},
            {"sql": "INSERT INTO users (phone) VALUES (%s)", "params": ["${phone}"]},
        ],
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, db_handler=mock_db)

    assert result["passed"] is True
    assert pool.get("phone") == "13800001111"
    # Verify the request body was re-resolved with the extracted phone
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["body"]["phone"] == "13800001111"


@patch("common.runner.send_request")
def test_run_testcase_with_db_extract(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"order_id": 123}},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    mock_db = MagicMock()
    mock_db.execute_extract.return_value = {"db_status": "pending"}
    case = {
        "name": "DB提取",
        "method": "POST",
        "url": "/api/orders",
        "extract": {"order_id": "$.data.order_id"},
        "db_extract": [{"sql": "SELECT status FROM orders WHERE id = 123", "extract": {"db_status": "status"}}],
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, db_handler=mock_db)

    assert result["passed"] is True
    assert pool.get("db_status") == "pending"
    mock_db.execute_extract.assert_called_once()


@patch("common.runner.send_request")
def test_run_testcase_with_before_hook(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    mock_hook = MagicMock()
    mock_hook.call.return_value = {
        "method": "POST",
        "url": "https://test.com/api/pay",
        "headers": {"X-Sign": "abc"},
        "body": {"order_id": "123", "sign": "abc"},
    }

    case = {
        "name": "Hook测试",
        "method": "POST",
        "url": "/api/pay",
        "body": {"order_id": "123"},
        "hook": {"before": "add_sign"},
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, hook_manager=mock_hook)

    assert result["passed"] is True
    mock_hook.call.assert_called_once()
    # Verify the modified request was sent
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["headers"]["X-Sign"] == "abc"


@patch("common.runner.send_request")
def test_run_testcase_with_after_hook(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "msg": "encrypted"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    mock_hook = MagicMock()
    mock_hook.call.return_value = {
        "status_code": 200,
        "body": {"code": 0, "msg": "decrypted"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    case = {
        "name": "AfterHook测试",
        "method": "GET",
        "url": "/api/data",
        "hook": {"after": "decrypt_response"},
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, hook_manager=mock_hook)

    assert result["passed"] is True
    mock_hook.call.assert_called_once()


@patch("common.runner.send_request")
def test_run_testcase_error_with_db_teardown(mock_send):
    """When request fails, db_teardown should still run."""
    mock_send.return_value = {
        "status_code": None,
        "body": None,
        "headers": None,
        "elapsed_ms": 0,
        "error": "Timeout",
    }

    pool = VariablePool()
    mock_db = MagicMock()
    case = {
        "name": "错误+清理",
        "method": "GET",
        "url": "/api/slow",
        "db_teardown": [{"sql": "DELETE FROM tmp WHERE id = 1"}],
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=5, db_handler=mock_db)

    assert result["passed"] is False
    mock_db.execute_teardown.assert_called_once()


# ---------------------------------------------------------------------------
# Retry mechanism tests
# ---------------------------------------------------------------------------
@patch("common.runner.time.sleep")  # Skip actual sleep in tests
@patch("common.runner.send_request")
def test_retry_on_request_error(mock_send, mock_sleep):
    """Request error should trigger retry, then succeed."""
    mock_send.side_effect = [
        # First attempt: connection error
        {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": "ConnectionError"},
        # Second attempt: success
        {"status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None},
    ]

    pool = VariablePool()
    case = {
        "name": "重试成功",
        "retry": 1,
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert mock_send.call_count == 2
    mock_sleep.assert_called_once()


@patch("common.runner.time.sleep")
@patch("common.runner.send_request")
def test_retry_on_validation_failure(mock_send, mock_sleep):
    """Validation failure should trigger retry."""
    mock_send.side_effect = [
        # First attempt: wrong code
        {"status_code": 200, "body": {"code": 500}, "headers": {}, "elapsed_ms": 50, "error": None},
        # Second attempt: correct code
        {"status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None},
    ]

    pool = VariablePool()
    case = {
        "name": "断言重试",
        "retry": 1,
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert mock_send.call_count == 2


@patch("common.runner.time.sleep")
@patch("common.runner.send_request")
def test_retry_exhausted_returns_last_failure(mock_send, mock_sleep):
    """When all retries are exhausted, return the last failure result."""
    mock_send.return_value = {
        "status_code": None, "body": None, "headers": None, "elapsed_ms": 0,
        "error": "ConnectionError: refused",
    }

    pool = VariablePool()
    case = {
        "name": "全部失败",
        "retry": 2,
        "method": "GET",
        "url": "/api/down",
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is False
    assert result["error"] is not None
    assert mock_send.call_count == 3  # 1 initial + 2 retries


@patch("common.runner.send_request")
def test_no_retry_when_retry_is_zero(mock_send):
    """retry=0 means no retry (default behavior)."""
    mock_send.return_value = {
        "status_code": 200, "body": {"code": 500}, "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "不重试",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is False
    assert mock_send.call_count == 1


@patch("common.runner.send_request")
def test_case_retry_overrides_default(mock_send):
    """Case-level retry should override default_retry."""
    mock_send.return_value = {
        "status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "用例级重试",
        "retry": 3,  # Case says 3
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    # default_retry=1 but case says 3, should use 3
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30, default_retry=1)

    assert result["passed"] is True
    assert mock_send.call_count == 1  # Passed on first try, no retry needed


# ---------------------------------------------------------------------------
# Case-level base_url override tests
# ---------------------------------------------------------------------------
@patch("common.runner.send_request")
def test_case_base_url_overrides_global(mock_send):
    """case.base_url should override the global base_url parameter."""
    mock_send.return_value = {
        "status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "跨系统请求",
        "base_url": "https://other-system.com",
        "method": "GET",
        "url": "/api/data",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://default.com", pool=pool, timeout=30)

    assert result["passed"] is True
    # 验证实际请求使用了 case 级别的 base_url
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["url"] == "https://other-system.com/api/data"


@patch("common.runner.send_request")
def test_case_base_url_with_variable(mock_send):
    """case.base_url supports ${variable} resolution."""
    mock_send.return_value = {
        "status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    pool.set_global("system_b_url", "https://system-b.example.com")
    case = {
        "name": "变量base_url",
        "base_url": "${system_b_url}",
        "method": "POST",
        "url": "/api/save",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://system-a.com", pool=pool, timeout=30)

    assert result["passed"] is True
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["url"] == "https://system-b.example.com/api/save"


@patch("common.runner.send_request")
def test_no_case_base_url_uses_global(mock_send):
    """Without case.base_url, global base_url is used as before."""
    mock_send.return_value = {
        "status_code": 200, "body": {"code": 0}, "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "默认base_url",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://default.com", pool=pool, timeout=30)

    assert result["passed"] is True
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["url"] == "https://default.com/api/test"


# ---------------------------------------------------------------------------
# Extract scope tests (global vs module)
# ---------------------------------------------------------------------------
@patch("common.runner.send_request")
def test_extract_scope_global_stores_in_global_pool(mock_send):
    """extract with scope: global should store in global pool, surviving clear_module."""
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"token": "global-token-123"}},
        "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "登录",
        "method": "POST",
        "url": "/api/login",
        "body": {"username": "admin"},
        "extract": {
            "token": {"jsonpath": "$.data.token", "scope": "global"},
        },
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)
    assert result["passed"] is True

    # token 应存在全局池中
    assert pool.get("token") == "global-token-123"

    # 清空模块变量后，token 仍然可用（因为存在全局池）
    pool.clear_module()
    assert pool.get("token") == "global-token-123"


@patch("common.runner.send_request")
def test_extract_scope_module_cleared_on_file_switch(mock_send):
    """extract without scope (default module) should be cleared on clear_module."""
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"token": "module-token"}},
        "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "登录",
        "method": "POST",
        "url": "/api/login",
        "extract": {"token": "$.data.token"},  # 默认 scope: module
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)
    assert result["passed"] is True
    assert pool.get("token") == "module-token"

    # 清空模块变量后，token 消失
    pool.clear_module()
    assert pool.get("token") is None


@patch("common.runner.send_request")
def test_extract_mixed_scope(mock_send):
    """同一个 extract 中混合 global 和 module scope。"""
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"token": "t123", "request_id": "req-456"}},
        "headers": {}, "elapsed_ms": 50, "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "登录",
        "method": "POST",
        "url": "/api/login",
        "extract": {
            "token": {"jsonpath": "$.data.token", "scope": "global"},
            "request_id": "$.data.request_id",  # 默认 module
        },
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)
    assert result["passed"] is True

    # 两个都能取到
    assert pool.get("token") == "t123"
    assert pool.get("request_id") == "req-456"

    # clear_module 后：global 的保留，module 的消失
    pool.clear_module()
    assert pool.get("token") == "t123"
    assert pool.get("request_id") is None
