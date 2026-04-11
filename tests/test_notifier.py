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


def test_should_not_send_when_disabled():
    email_config = {
        "enabled": False,
    }
    from common.notifier import maybe_send_notification
    maybe_send_notification(email_config, {}, send_on="always", report_path=None)
