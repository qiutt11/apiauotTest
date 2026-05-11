"""飞书机器人服务测试。"""
import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def app():
    """Create test Flask app."""
    from scripts.feishu_bot import app, _run_status
    app.config["TESTING"] = True
    _run_status["running"] = False
    _run_status["started_at"] = None
    _run_status["args"] = ""
    _run_status["pid"] = None
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_page(client):
    """Index page should return 200 and contain links."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Autotest Bot" in resp.data
    assert b"report.html" in resp.data


def test_feishu_url_verification(client):
    """Should respond to Feishu URL verification challenge."""
    payload = {
        "type": "url_verification",
        "challenge": "test-challenge-token",
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["challenge"] == "test-challenge-token"


@patch("scripts.feishu_bot.FEISHU_VERIFY_TOKEN", "valid-token")
def test_feishu_invalid_token(client):
    """Should reject requests with invalid verify token."""
    payload = {
        "token": "wrong-token",
        "event": {"message": {"content": '{"text": "/status"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 403


@patch("scripts.feishu_bot.send_feishu_message")
def test_status_command_idle(mock_send, client):
    """Should report idle status when no test is running."""
    payload = {
        "event": {"message": {"content": '{"text": "/status"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "空闲" in mock_send.call_args[0][0]


@patch("scripts.feishu_bot.send_feishu_message")
@patch("scripts.feishu_bot.threading.Thread")
def test_run_command(mock_thread, mock_send, client):
    """Should start test execution on /run command."""
    mock_thread_instance = MagicMock()
    mock_thread.return_value = mock_thread_instance

    payload = {
        "event": {"message": {"content": '{"text": "/run --env dev"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_thread.assert_called_once()
    mock_thread_instance.start.assert_called_once()
    mock_send.assert_called_once()
    assert "测试开始执行" in mock_send.call_args[0][0]


@patch("scripts.feishu_bot.send_feishu_message")
def test_run_command_already_running(mock_send, client):
    """Should reject /run when test is already running."""
    from scripts.feishu_bot import _run_status
    _run_status["running"] = True
    _run_status["started_at"] = "2026-05-11 10:00:00"
    _run_status["args"] = "--env test"

    payload = {
        "event": {"message": {"content": '{"text": "/run"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "正在执行中" in mock_send.call_args[0][0]

    # cleanup
    _run_status["running"] = False


def test_feishu_unknown_command(client):
    """Should ignore unknown commands without error."""
    payload = {
        "event": {"message": {"content": '{"text": "hello"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200


@patch("scripts.feishu_bot.send_feishu_message")
def test_run_strips_at_mention(mock_send, client):
    """Should strip @mention tags from command text."""
    mock_thread_patcher = patch("scripts.feishu_bot.threading.Thread")
    mock_thread = mock_thread_patcher.start()
    mock_thread.return_value = MagicMock()

    payload = {
        "event": {"message": {"content": '{"text": "@_user_abc123 /run --env test"}'}},
    }
    resp = client.post(
        "/feishu/event",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "测试开始执行" in mock_send.call_args[0][0]

    mock_thread_patcher.stop()
