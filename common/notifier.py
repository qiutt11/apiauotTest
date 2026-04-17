"""通知模块。

支持两种通知渠道：
    - 邮件通知：通过 SMTP_SSL 发送，支持 HTML 报告附件
    - 飞书通知：通过 Webhook 发送富文本卡片消息，支持 @指定用户

统一入口：maybe_send_notification() 根据配置决定是否发送、发送哪个渠道。
"""

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


# ---------------------------------------------------------------------------
# 通用：构建纯文本摘要（邮件和飞书共用）
# ---------------------------------------------------------------------------
def build_summary_text(stats: dict) -> str:
    """构建测试结果纯文本摘要。

    Args:
        stats: 统计字典，包含 total, passed, failed, skipped, pass_rate, duration, env, failures

    Returns:
        格式化的纯文本摘要
    """
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


# 保持向后兼容
build_email_body = build_summary_text


# ---------------------------------------------------------------------------
# 邮件通知
# ---------------------------------------------------------------------------
def send_email(email_config: dict, stats: dict, report_path: str = None):
    """通过 SMTP_SSL 发送邮件通知。

    Args:
        email_config: 邮件配置（smtp_host, smtp_port, sender, password, receivers）
        stats: 测试统计数据
        report_path: HTML 报告文件路径（可选，作为附件发送）
    """
    subject = (
        f"[autotest] 测试报告 - {stats.get('env', '')}环境 - "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    body = build_summary_text(stats)

    # 构建邮件
    msg = MIMEMultipart()
    msg["From"] = email_config["sender"]
    msg["To"] = ", ".join(email_config["receivers"])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # 附加 HTML 报告文件（如果存在）
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

    # 发送（异常不向上抛出，只记录日志）
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
# 飞书 Webhook 通知
# ---------------------------------------------------------------------------
def send_feishu(feishu_config: dict, stats: dict):
    """通过飞书自定义机器人 Webhook 发送测试结果卡片消息。

    卡片效果：
        - 失败时红色标题，全部通过时绿色标题
        - 显示环境、时间、统计数据
        - 列出失败用例（最多 10 条）
        - 失败时 @指定用户（通过 at_user_ids 配置）

    Args:
        feishu_config: 飞书配置（webhook_url, at_user_ids）
        stats: 测试统计数据

    飞书 Webhook 文档：
        https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
    """
    webhook_url = feishu_config.get("webhook_url", "")
    if not webhook_url:
        logger.error("Feishu webhook_url is empty, skip sending")
        return

    # 提取统计数据
    env = stats.get("env", "unknown")
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)
    skipped = stats.get("skipped", 0)
    pass_rate = stats.get("pass_rate", "0%")
    duration = stats.get("duration", "unknown")

    # 构建失败用例列表（最多显示 10 条）
    failure_lines = ""
    if stats.get("failures"):
        items = []
        for i, f in enumerate(stats["failures"][:10], 1):
            items.append(f"{i}. {f['module']} > {f['name']}")
        failure_lines = "\n".join(items)
        if len(stats["failures"]) > 10:
            failure_lines += f"\n... 共 {len(stats['failures'])} 个失败用例"

    # 根据结果决定卡片颜色
    if failed > 0:
        header_color = "red"
        header_title = f"接口自动化测试报告 - {env}环境 - 有失败"
    else:
        header_color = "green"
        header_title = f"接口自动化测试报告 - {env}环境 - 全部通过"

    # 构建飞书 interactive card 消息
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

    # 添加失败用例详情
    if failure_lines:
        card["card"]["elements"].append({"tag": "hr"})  # 分隔线
        card["card"]["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**失败用例：**\n{failure_lines}"},
        })

    # 失败时 @指定用户
    at_user_ids = feishu_config.get("at_user_ids", [])
    if at_user_ids and failed > 0:
        at_text = " ".join([f"<at id={uid}></at>" for uid in at_user_ids])
        card["card"]["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": at_text},
        })

    # 发送请求（异常不向上抛出）
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
# 统一通知调度器
# ---------------------------------------------------------------------------
def maybe_send_notification(
    email_config: dict, stats: dict, send_on: str = "fail", report_path: str = None,
    feishu_config: dict = None,
):
    """根据配置决定是否发送通知，以及通过哪些渠道发送。

    Args:
        email_config: 邮件配置字典
        stats: 测试统计数据
        send_on: 发送时机 "always" / "fail" / "never"
        report_path: HTML 报告路径（邮件附件用）
        feishu_config: 飞书配置字典（可选）
    """
    # 判断是否需要发送
    should_send = False
    if send_on == "always":
        should_send = True
    elif send_on == "fail" and stats.get("failed", 0) > 0:
        should_send = True

    if not should_send:
        return

    # 邮件通知
    if email_config.get("enabled", False):
        send_email(email_config, stats, report_path)

    # 飞书通知
    if feishu_config and feishu_config.get("enabled", False):
        send_feishu(feishu_config, stats)
