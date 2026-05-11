"""飞书机器人服务。

功能：
    1. 接收飞书群消息，识别指令触发测试执行
    2. 托管 reports 目录，提供 HTML 报告在线访问

支持的指令（在飞书群 @机器人 或直接发送）：
    /run                        运行全部用例（默认环境）
    /run --env dev              指定环境
    /run --env test --level P0  指定环境和优先级
    /status                     查看当前执行状态

启动：
    python scripts/feishu_bot.py

配置：
    修改下方 CONFIG 区域，或通过环境变量覆盖。
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory

# ==========================================================================
# CONFIG
# ==========================================================================

# 项目根目录（feishu_bot.py 在 scripts/ 下，向上一级就是项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

# 服务端口
PORT = int(os.environ.get("BOT_PORT", 9090))

# 飞书 Webhook URL（用于主动推送消息到群）
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")

# 飞书事件验证 token（在飞书开放平台 → 事件订阅中获取，用于验证请求来源）
FEISHU_VERIFY_TOKEN = os.environ.get("FEISHU_VERIFY_TOKEN", "")

# 报告访问地址前缀（部署后改为服务器 IP 或域名）
REPORT_BASE_URL = os.environ.get("REPORT_BASE_URL", f"http://127.0.0.1:{PORT}")

# ==========================================================================
# APP
# ==========================================================================
app = Flask(__name__)

# 执行状态跟踪
_run_lock = threading.Lock()
_run_status = {
    "running": False,
    "started_at": None,
    "args": "",
    "pid": None,
}


# --------------------------------------------------------------------------
# 报告托管：访问 /reports/report.html 即可查看
# --------------------------------------------------------------------------
@app.route("/reports/<path:filename>")
def serve_report(filename):
    """托管 reports 目录下的静态文件。"""
    return send_from_directory(REPORTS_DIR, filename)


@app.route("/")
def index():
    """首页，重定向到报告。"""
    return (
        "<h3>Autotest Bot</h3>"
        '<p><a href="/reports/report.html">查看最新测试报告</a></p>'
        '<p>POST /feishu/event 接收飞书事件</p>'
    )


# --------------------------------------------------------------------------
# 飞书事件接收
# --------------------------------------------------------------------------
@app.route("/feishu/event", methods=["POST"])
def feishu_event():
    """接收飞书事件回调。

    飞书开放平台配置：
        请求地址：http://服务器IP:9090/feishu/event
        事件类型：接收消息 (im.message.receive_v1)
    """
    data = request.json or {}

    # 飞书 URL 验证（首次配置回调地址时飞书会发送验证请求）
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge", "")})

    # 验证 token（可选，防止伪造请求）
    if FEISHU_VERIFY_TOKEN:
        token = data.get("token") or data.get("header", {}).get("token", "")
        if token != FEISHU_VERIFY_TOKEN:
            return jsonify({"code": 403, "msg": "invalid token"}), 403

    # 提取消息内容
    event = data.get("event", {})
    message = event.get("message", {})
    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str)
    except json.JSONDecodeError:
        content = {}

    text = content.get("text", "").strip()

    # 去掉 @机器人 的部分（飞书 @mention 格式为 @_user_xxx）
    # 只保留实际文本
    import re
    text = re.sub(r"@_user_\w+", "", text).strip()

    # 分发指令
    if text.startswith("/run"):
        return handle_run(text)
    elif text.startswith("/status"):
        return handle_status()

    return jsonify({"code": 0})


# --------------------------------------------------------------------------
# 指令处理
# --------------------------------------------------------------------------
def handle_run(text):
    """处理 /run 指令，后台执行测试。"""
    if _run_status["running"]:
        send_feishu_message(
            f"测试正在执行中，开始时间：{_run_status['started_at']}\n"
            f"参数：{_run_status['args']}\n"
            f"请等待执行完成。"
        )
        return jsonify({"code": 0})

    # 解析参数：/run --env dev --level P0 → ["--env", "dev", "--level", "P0"]
    parts = text.split()[1:]  # 去掉 /run
    extra_args = " ".join(parts)

    # 后台执行
    t = threading.Thread(target=_run_tests, args=(extra_args,), daemon=True)
    t.start()

    send_feishu_message(
        f"测试开始执行\n"
        f"参数：{extra_args or '默认'}\n"
        f"完成后会自动推送结果。"
    )
    return jsonify({"code": 0})


def handle_status():
    """处理 /status 指令。"""
    if _run_status["running"]:
        msg = (
            f"状态：执行中\n"
            f"开始时间：{_run_status['started_at']}\n"
            f"参数：{_run_status['args']}"
        )
    else:
        msg = "状态：空闲，没有正在执行的测试。"
    send_feishu_message(msg)
    return jsonify({"code": 0})


def _run_tests(extra_args: str):
    """在子进程中执行测试，完成后推送结果。"""
    with _run_lock:
        _run_status["running"] = True
        _run_status["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _run_status["args"] = extra_args or "默认"

        cmd = f"cd {PROJECT_ROOT} && python run.py {extra_args}"
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=1800,
            )
            duration = round(time.time() - start_time, 1)
            exit_code = result.returncode

            # 读取统计数据
            stats_path = os.path.join(REPORTS_DIR, ".stats.json")
            stats = {}
            if os.path.exists(stats_path):
                with open(stats_path, "r", encoding="utf-8") as f:
                    stats = json.load(f)

            total = stats.get("total", 0)
            passed = stats.get("passed", 0)
            failed = stats.get("failed", 0)
            skipped = stats.get("skipped", 0)
            pass_rate = stats.get("pass_rate", "0%")

            report_url = f"{REPORT_BASE_URL}/reports/report.html"

            if failed > 0:
                title = f"测试完成 - 有 {failed} 个失败"
            else:
                title = "测试完成 - 全部通过"

            msg = (
                f"{title}\n"
                f"总计：{total}  通过：{passed}  失败：{failed}  跳过：{skipped}\n"
                f"通过率：{pass_rate}  耗时：{duration}s\n"
                f"报告：{report_url}"
            )

            # 列出失败用例
            failures = stats.get("failures", [])
            if failures:
                msg += "\n\n失败用例："
                for i, f in enumerate(failures[:5], 1):
                    msg += f"\n  {i}. {f.get('module', '')} > {f.get('name', '')}"
                if len(failures) > 5:
                    msg += f"\n  ... 共 {len(failures)} 个"

            send_feishu_message(msg)

        except subprocess.TimeoutExpired:
            send_feishu_message("测试执行超时（30分钟），已终止。")
        except Exception as e:
            send_feishu_message(f"测试执行异常：{e}")
        finally:
            _run_status["running"] = False
            _run_status["pid"] = None


# --------------------------------------------------------------------------
# 飞书消息发送
# --------------------------------------------------------------------------
def send_feishu_message(text: str):
    """通过 Webhook 发送文本消息到飞书群。"""
    if not FEISHU_WEBHOOK_URL:
        print(f"[WARN] FEISHU_WEBHOOK_URL 未配置，消息未发送：{text}")
        return

    import requests
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    try:
        resp = requests.post(
            FEISHU_WEBHOOK_URL, json=payload,
            headers={"Content-Type": "application/json"}, timeout=10,
        )
        result = resp.json()
        if result.get("code", -1) != 0 and result.get("StatusCode", -1) != 0:
            print(f"[WARN] 飞书发送失败：{result}")
    except Exception as e:
        print(f"[ERROR] 飞书发送异常：{e}")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)
    print(f"Autotest Bot 启动")
    print(f"  报告访问：http://0.0.0.0:{PORT}/reports/report.html")
    print(f"  飞书回调：http://0.0.0.0:{PORT}/feishu/event")
    print(f"  项目目录：{PROJECT_ROOT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
