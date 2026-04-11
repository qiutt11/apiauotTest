import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os


def build_email_body(stats: dict) -> str:
    lines = [
        f"测试环境：{stats.get('env', 'unknown')}",
        f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "─" * 40,
        f"总用例：{stats['total']}",
        f"通过：{stats['passed']}",
        f"失败：{stats['failed']}",
        f"跳过：{stats['skipped']}",
        f"通过率：{stats['pass_rate']}",
        f"耗时：{stats['duration']}",
    ]

    if stats.get("failures"):
        lines.append("")
        lines.append("失败用例：")
        for i, f in enumerate(stats["failures"], 1):
            lines.append(f"  {i}. {f['module']} > {f['name']} - {f['error']}")

    return "\n".join(lines)


def send_email(email_config: dict, stats: dict, report_path: str = None):
    subject = (
        f"[autotest] 测试报告 - {stats.get('env', '')}环境 - "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    body = build_email_body(stats)

    msg = MIMEMultipart()
    msg["From"] = email_config["sender"]
    msg["To"] = ", ".join(email_config["receivers"])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(report_path)}",
            )
            msg.attach(attachment)

    with smtplib.SMTP_SSL(email_config["smtp_host"], email_config["smtp_port"]) as server:
        server.login(email_config["sender"], email_config["password"])
        server.sendmail(
            email_config["sender"],
            email_config["receivers"],
            msg.as_string(),
        )


def maybe_send_notification(
    email_config: dict, stats: dict, send_on: str = "fail", report_path: str = None
):
    if not email_config.get("enabled", False):
        return

    should_send = False
    if send_on == "always":
        should_send = True
    elif send_on == "fail" and stats.get("failed", 0) > 0:
        should_send = True

    if should_send:
        send_email(email_config, stats, report_path)
