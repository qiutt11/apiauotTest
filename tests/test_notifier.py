from unittest.mock import patch, MagicMock

from common.notifier import build_email_body, send_email


def test_build_email_body():
    stats = {
        "total": 10,
        "passed": 8,
        "failed": 1,
        "skipped": 1,
        "pass_rate": "80.0%",
        "duration": "15s",
        "env": "test",
        "failures": [
            {"module": "用户管理", "name": "删除用户", "error": "$.code 期望 0 实际 500"},
        ],
    }
    body = build_email_body(stats)
    assert "10" in body
    assert "80.0%" in body
    assert "删除用户" in body
    assert "test" in body


@patch("common.notifier.smtplib.SMTP_SSL")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    email_config = {
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "sender": "test@qq.com",
        "password": "abc",
        "receivers": ["dev@company.com"],
    }
    stats = {
        "total": 5, "passed": 5, "failed": 0, "skipped": 0,
        "pass_rate": "100.0%", "duration": "10s", "env": "test",
        "failures": [],
    }

    send_email(email_config, stats, report_path=None)
    mock_smtp.sendmail.assert_called_once()


@patch("common.notifier.smtplib.SMTP_SSL")
def test_send_email_with_attachment(mock_smtp_class, tmp_path):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    report_file = tmp_path / "report.html"
    report_file.write_text("<html><body>Test Report</body></html>")

    email_config = {
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "sender": "test@qq.com",
        "password": "abc",
        "receivers": ["dev@company.com"],
    }
    stats = {
        "total": 5, "passed": 5, "failed": 0, "skipped": 0,
        "pass_rate": "100.0%", "duration": "10s", "env": "test",
        "failures": [],
    }

    send_email(email_config, stats, report_path=str(report_file))
    mock_smtp.sendmail.assert_called_once()


def test_should_not_send_when_disabled():
    from common.notifier import maybe_send_notification
    email_config = {"enabled": False}
    maybe_send_notification(email_config, {}, send_on="always", report_path=None)


@patch("common.notifier.send_email")
def test_maybe_send_on_always(mock_send):
    from common.notifier import maybe_send_notification
    email_config = {"enabled": True}
    stats = {"total": 5, "passed": 5, "failed": 0, "skipped": 0,
             "pass_rate": "100%", "duration": "5s", "env": "test", "failures": []}
    maybe_send_notification(email_config, stats, send_on="always", report_path=None)
    mock_send.assert_called_once()


@patch("common.notifier.send_email")
def test_maybe_send_on_fail_with_failures(mock_send):
    from common.notifier import maybe_send_notification
    email_config = {"enabled": True}
    stats = {"total": 5, "passed": 4, "failed": 1, "skipped": 0,
             "pass_rate": "80%", "duration": "5s", "env": "test", "failures": []}
    maybe_send_notification(email_config, stats, send_on="fail", report_path=None)
    mock_send.assert_called_once()


@patch("common.notifier.send_email")
def test_maybe_send_on_fail_no_failures(mock_send):
    from common.notifier import maybe_send_notification
    email_config = {"enabled": True}
    stats = {"total": 5, "passed": 5, "failed": 0, "skipped": 0,
             "pass_rate": "100%", "duration": "5s", "env": "test", "failures": []}
    maybe_send_notification(email_config, stats, send_on="fail", report_path=None)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Feishu notification tests
# ---------------------------------------------------------------------------
@patch("common.notifier.http_requests.post")
def test_send_feishu_success(mock_post):
    from common.notifier import send_feishu

    mock_post.return_value = MagicMock(
        json=MagicMock(return_value={"code": 0, "msg": "success"})
    )

    feishu_config = {
        "enabled": True,
        "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
    }
    stats = {
        "total": 10, "passed": 8, "failed": 2, "skipped": 0,
        "pass_rate": "80.0%", "duration": "15s", "env": "test",
        "failures": [
            {"module": "用户管理", "name": "删除用户", "error": "$.code 期望 0 实际 500"},
            {"module": "订单模块", "name": "创建订单", "error": "Timeout"},
        ],
    }

    send_feishu(feishu_config, stats)
    mock_post.assert_called_once()

    # Verify the card message structure
    call_kwargs = mock_post.call_args
    payload = call_kwargs[1]["json"]
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["template"] == "red"  # Has failures
    assert "失败" in payload["card"]["header"]["title"]["content"]


@patch("common.notifier.http_requests.post")
def test_send_feishu_all_pass(mock_post):
    from common.notifier import send_feishu

    mock_post.return_value = MagicMock(
        json=MagicMock(return_value={"code": 0})
    )

    feishu_config = {
        "enabled": True,
        "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
    }
    stats = {
        "total": 10, "passed": 10, "failed": 0, "skipped": 0,
        "pass_rate": "100.0%", "duration": "10s", "env": "test",
        "failures": [],
    }

    send_feishu(feishu_config, stats)

    payload = mock_post.call_args[1]["json"]
    assert payload["card"]["header"]["template"] == "green"  # All pass
    assert "通过" in payload["card"]["header"]["title"]["content"]


@patch("common.notifier.http_requests.post")
def test_send_feishu_with_at_users(mock_post):
    from common.notifier import send_feishu

    mock_post.return_value = MagicMock(
        json=MagicMock(return_value={"code": 0})
    )

    feishu_config = {
        "enabled": True,
        "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
        "at_user_ids": ["ou_xxx", "ou_yyy"],
    }
    stats = {
        "total": 5, "passed": 4, "failed": 1, "skipped": 0,
        "pass_rate": "80%", "duration": "5s", "env": "test",
        "failures": [{"module": "M", "name": "N", "error": "E"}],
    }

    send_feishu(feishu_config, stats)

    payload = mock_post.call_args[1]["json"]
    elements = payload["card"]["elements"]
    # Last element should contain @mentions
    at_element = elements[-1]
    assert "ou_xxx" in at_element["text"]["content"]
    assert "ou_yyy" in at_element["text"]["content"]


def test_send_feishu_empty_webhook():
    """Should not crash when webhook_url is empty."""
    from common.notifier import send_feishu

    feishu_config = {"enabled": True, "webhook_url": ""}
    stats = {"total": 1, "passed": 0, "failed": 1, "skipped": 0,
             "pass_rate": "0%", "duration": "1s", "env": "test", "failures": []}
    # Should return without error
    send_feishu(feishu_config, stats)


@patch("common.notifier.http_requests.post")
def test_send_feishu_api_error(mock_post):
    """Should log error when Feishu API returns non-zero code."""
    from common.notifier import send_feishu

    mock_post.return_value = MagicMock(
        json=MagicMock(return_value={"code": 9499, "msg": "invalid token"})
    )

    feishu_config = {
        "enabled": True,
        "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/bad-token",
    }
    stats = {"total": 1, "passed": 1, "failed": 0, "skipped": 0,
             "pass_rate": "100%", "duration": "1s", "env": "test", "failures": []}
    # Should not raise, just log
    send_feishu(feishu_config, stats)


@patch("common.notifier.send_email")
@patch("common.notifier.send_feishu")
def test_maybe_send_both_email_and_feishu(mock_feishu, mock_email):
    """When both email and feishu are enabled, both should be called."""
    from common.notifier import maybe_send_notification

    email_config = {"enabled": True}
    feishu_config = {"enabled": True, "webhook_url": "https://hook.test"}
    stats = {"total": 5, "passed": 4, "failed": 1, "skipped": 0,
             "pass_rate": "80%", "duration": "5s", "env": "test", "failures": []}

    maybe_send_notification(email_config, stats, send_on="fail",
                            report_path=None, feishu_config=feishu_config)

    mock_email.assert_called_once()
    mock_feishu.assert_called_once()


@patch("common.notifier.send_feishu")
def test_maybe_send_feishu_only(mock_feishu):
    """Feishu-only notification (email disabled)."""
    from common.notifier import maybe_send_notification

    email_config = {"enabled": False}
    feishu_config = {"enabled": True, "webhook_url": "https://hook.test"}
    stats = {"total": 5, "passed": 4, "failed": 1, "skipped": 0,
             "pass_rate": "80%", "duration": "5s", "env": "test", "failures": []}

    maybe_send_notification(email_config, stats, send_on="fail",
                            report_path=None, feishu_config=feishu_config)

    mock_feishu.assert_called_once()
