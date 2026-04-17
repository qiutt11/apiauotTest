"""CLI 入口模块。

提供命令行接口运行测试，支持以下参数：
    --env       选择测试环境（dev/test/staging/prod）
    --path      指定用例路径（目录或文件）
    --report    报告类型（allure/html/both）
    --level     优先级过滤（P0/P0,P1/blocker,critical）
    --workers   并行进程数（数字或 auto）

使用示例：
    python run.py                                          # 运行全部用例
    python run.py --env dev --level P0,P1 --workers 4      # 开发环境跑核心用例
    python run.py --report both                             # 生成两种报告
"""

import argparse
import json
import os
import sys
import time

import pytest

from common.config_loader import load_config
from common.notifier import maybe_send_notification


# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    """框架主入口：解析参数 → 构建 pytest 命令 → 执行 → 聚合统计 → 发送通知。"""

    # ---- 解析命令行参数 ----
    parser = argparse.ArgumentParser(description="API Autotest Framework")
    parser.add_argument("--env", default=None, help="Test environment (dev/test/staging/prod)")
    parser.add_argument("--path", default="testcases", help="Test case path (directory or file)")
    parser.add_argument("--report", default=None, help="Report type: allure / html / both")
    parser.add_argument("--level", default=None,
                        help="Filter by priority: P0,P1 or blocker,critical (comma-separated)")
    parser.add_argument("--workers", default=None,
                        help="Parallel workers: number (e.g., 4) or 'auto' for CPU count. "
                             "Same YAML file's cases always run sequentially in one worker.")
    args = parser.parse_args()

    # ---- 加载配置 ----
    config_dir = os.path.join(PROJECT_ROOT, "config")
    config = load_config(config_dir, env=args.env)

    # ---- 构建 pytest 参数列表 ----
    pytest_args = [args.path, "-v"]

    # 报告参数
    report_type = args.report or config.get("report_type", "allure")
    reports_dir = os.path.join(PROJECT_ROOT, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    report_path = None
    if report_type in ("html", "both"):
        report_path = os.path.join(reports_dir, "report.html")
        pytest_args.extend([f"--html={report_path}", "--self-contained-html"])
    if report_type in ("allure", "both"):
        allure_dir = os.path.join(reports_dir, "allure-results")
        pytest_args.extend([f"--alluredir={allure_dir}", "--clean-alluredir"])

    # 传递自定义参数给 conftest.py
    if args.env:
        pytest_args.extend(["--env", args.env])
    if args.report:
        pytest_args.extend(["--report", args.report])
    if args.level:
        pytest_args.extend(["--level", args.level])
    if args.workers:
        # xdist loadfile 模式：同一文件的用例在同一 worker 中顺序执行
        pytest_args.extend([f"-n={args.workers}", "--dist=loadfile"])

    # ---- 执行测试 ----
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    duration = round(time.time() - start_time, 1)

    # ---- 聚合统计数据 ----
    # 单进程：读取 .stats.json
    # 多进程（xdist）：聚合所有 .stats_gw{N}.json 文件
    stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "pass_rate": "0%", "duration": f"{duration}s",
        "env": config.get("current_env", "unknown"), "failures": [],
    }

    # 收集所有统计文件
    stats_files = []
    main_stats = os.path.join(reports_dir, ".stats.json")
    if os.path.exists(main_stats):
        stats_files.append(main_stats)
    for f in os.listdir(reports_dir):
        if f.startswith(".stats_gw") and f.endswith(".json"):
            stats_files.append(os.path.join(reports_dir, f))

    # 聚合各 worker 的统计
    for sf in stats_files:
        with open(sf, "r", encoding="utf-8") as f:
            worker_stats = json.load(f)
        stats["total"] += worker_stats.get("total", 0)
        stats["passed"] += worker_stats.get("passed", 0)
        stats["failed"] += worker_stats.get("failed", 0)
        stats["skipped"] += worker_stats.get("skipped", 0)
        stats["failures"].extend(worker_stats.get("failures", []))
        # 清理 worker 统计文件（保留主统计文件）
        if sf != main_stats:
            os.remove(sf)

    # 计算汇总
    total = stats["total"]
    stats["pass_rate"] = f"{(stats['passed'] / total * 100):.1f}%" if total > 0 else "0%"
    stats["duration"] = f"{duration}s"
    stats["env"] = config.get("current_env", "unknown")

    # 写入聚合后的统计文件
    with open(main_stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)

    # ---- 发送通知（邮件 + 飞书）----
    email_cfg = config.get("email", {})
    feishu_cfg = config.get("feishu", {})
    send_on = email_cfg.get("send_on", feishu_cfg.get("send_on", "fail"))
    if email_cfg.get("enabled") or feishu_cfg.get("enabled"):
        maybe_send_notification(
            email_config=email_cfg,
            stats=stats,
            send_on=send_on,
            report_path=report_path,
            feishu_config=feishu_cfg,
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
