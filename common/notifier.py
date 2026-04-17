import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

import requests as http_requests
from loguru import logger


def build_summary_text(stats: dict) -> str:
    """Build a plain text summary shared by email and feishu."""
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


# Keep backward compatibility
build_email_body = build_summary_text


# ---------------------------------------------------------------------------
# Email notification
# ---------------------------------------------------------------------------
def send_email(email_config: dict, stats: dict, report_path: str = None):
    subject = (
        f"[autotest] 测试报告 - {stats.get('env', '')}环境 - "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    body = build_summary_text(stats)

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
                f'attachment; filename="{os.path.basename(report_path)}"',
            )
            msg.attach(attachment)

    try:
        with smtplib.SMTP_SSL(email_config["smtp_host"], email_config["smtp_port"]) as server:
            server.login(email_config["sender"], email_config["password"])
            server.sendmail(
                email_config["sender"],
                email_config["receivers"],
                msg.as_string(),
            )
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


# ---------------------------------------------------------------------------
# Feishu (飞书) webhook notification
# ---------------------------------------------------------------------------
def send_feishu(feishu_config: dict, stats: dict):
    """Send test result to Feishu group chat via webhook bot.

    Feishu webhook docs: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

    Supports two message formats:
    - text: simple plain text
    - interactive: rich card with color-coded header
    """
    webhook_url = feishu_config.get("webhook_url", "")
    if not webhook_url:
        logger.error("Feishu webhook_url is empty, skip sending")
        return

    env = stats.get("env", "unknown")
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)
    skipped = stats.get("skipped", 0)
    pass_rate = stats.get("pass_rate", "0%")
    duration = stats.get("duration", "unknown")

    # Build failure details
    failure_lines = ""
    if stats.get("failures"):
        items = []
        for i, f in enumerate(stats["failures"][:10], 1):  # Max 10 failures
            items.append(f"{i}. {f['module']} > {f['name']}")
        failure_lines = "\n".join(items)
        if len(stats["failures"]) > 10:
            failure_lines += f"\n... 共 {len(stats['failures'])} 个失败用例"

    # Determine header color based on result
    if failed > 0:
        header_color = "red"
        header_title = f"接口自动化测试报告 - {env}环境 - 有失败"
    else:
        header_color = "green"
        header_title = f"接口自动化测试报告 - {env}环境 - 全部通过"

    # Build interactive card message
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": header_color,
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**测试环境：**{env}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**执行时间：**{datetime.now().strftime('%Y-%m-%d %H:%M')}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**总用例：**{total}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**通过率：**{pass_rate}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**通过：**{passed}  |  **失败：**{failed}  |  **跳过：**{skipped}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**耗时：**{duration}"}},
                    ],
                },
            ],
        },
    }

    # Add failure details section if any
    if failure_lines:
        card["card"]["elements"].append({"tag": "hr"})
        card["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**失败用例：**\n{failure_lines}",
            },
        })

    # Add @mentions if configured
    at_user_ids = feishu_config.get("at_user_ids", [])
    if at_user_ids and failed > 0:
        at_text = " ".join([f"<at id={uid}></at>" for uid in at_user_ids])
        card["card"]["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": at_text},
        })

    try:
        resp = http_requests.post(
            webhook_url,
            json=card,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("Feishu notification sent successfully")
        else:
            logger.error(f"Feishu API returned error: {result}")
    except Exception as e:
        logger.error(f"Failed to send Feishu notification: {e}")


# ---------------------------------------------------------------------------
# Unified notification dispatcher
# ---------------------------------------------------------------------------
def maybe_send_notification(
    email_config: dict, stats: dict, send_on: str = "fail", report_path: str = None,
    feishu_config: dict = None,
):
    should_send = False
    if send_on == "always":
        should_send = True
    elif send_on == "fail" and stats.get("failed", 0) > 0:
        should_send = True

    if not should_send:
        return

    # Email
    if email_config.get("enabled", False):
        send_email(email_config, stats, report_path)

    # Feishu
    if feishu_config and feishu_config.get("enabled", False):
        send_feishu(feishu_config, stats)
