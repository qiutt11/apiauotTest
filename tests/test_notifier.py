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
