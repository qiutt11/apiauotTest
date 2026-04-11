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
