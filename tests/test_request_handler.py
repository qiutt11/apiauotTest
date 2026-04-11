import json
from unittest.mock import patch, MagicMock

from common.request_handler import send_request


def _mock_response(status_code=200, body=None, elapsed_ms=50):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body or {}
    mock_resp.text = json.dumps(body or {})
    mock_resp.elapsed.total_seconds.return_value = elapsed_ms / 1000
    mock_resp.headers = {"Content-Type": "application/json"}
    return mock_resp


@patch("common.request_handler.requests.request")
def test_send_get_request(mock_request):
    mock_request.return_value = _mock_response(200, {"code": 0})
    result = send_request(method="GET", url="https://test.com/api/users", timeout=30)
    assert result["status_code"] == 200
    assert result["body"] == {"code": 0}
    assert "elapsed_ms" in result
    mock_request.assert_called_once()


@patch("common.request_handler.requests.request")
def test_send_post_request_with_body(mock_request):
    mock_request.return_value = _mock_response(200, {"code": 0, "data": {"id": 1}})
    result = send_request(method="POST", url="https://test.com/api/users", headers={"Content-Type": "application/json"}, body={"username": "test"}, timeout=30)
    assert result["status_code"] == 200
    assert result["body"]["data"]["id"] == 1
    call_kwargs = mock_request.call_args
    assert call_kwargs[1]["json"] == {"username": "test"}


@patch("common.request_handler.requests.request")
def test_send_request_with_headers(mock_request):
    mock_request.return_value = _mock_response(200, {})
    send_request(method="GET", url="https://test.com/api/test", headers={"Authorization": "Bearer abc"}, timeout=30)
    call_kwargs = mock_request.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer abc"


@patch("common.request_handler.requests.request")
def test_send_request_timeout(mock_request):
    import requests as req_lib
    mock_request.side_effect = req_lib.exceptions.Timeout("Connection timed out")
    result = send_request(method="GET", url="https://test.com/api/slow", timeout=5)
    assert result["status_code"] is None
    assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()


@patch("common.request_handler.requests.request")
def test_send_request_connection_error(mock_request):
    import requests as req_lib
    mock_request.side_effect = req_lib.exceptions.ConnectionError("Connection refused")
    result = send_request(method="GET", url="https://test.com/api/down", timeout=5)
    assert result["status_code"] is None
    assert result["error"] is not None
