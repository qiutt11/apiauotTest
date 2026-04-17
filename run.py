import argparse
import json
import os
import sys
import time

import pytest

from common.config_loader import load_config
from common.notifier import maybe_send_notification


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
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

    # Load config for email settings
    config_dir = os.path.join(PROJECT_ROOT, "config")
    config = load_config(config_dir, env=args.env)

    # Build pytest args
    pytest_args = [args.path, "-v"]

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

    if args.env:
        pytest_args.extend(["--env", args.env])
    if args.report:
        pytest_args.extend(["--report", args.report])
    if args.level:
        pytest_args.extend(["--level", args.level])
    if args.workers:
        # --dist loadfile: same file's cases stay in one worker (preserves variable dependencies)
        pytest_args.extend([f"-n={args.workers}", "--dist=loadfile"])

    # Run tests
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    duration = round(time.time() - start_time, 1)

    # Read stats — aggregate worker stats if xdist was used
    stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "pass_rate": "0%", "duration": f"{duration}s",
        "env": config.get("current_env", "unknown"), "failures": [],
    }

    # Collect all stats files (single process: .stats.json, xdist: .stats_gw0.json, .stats_gw1.json, ...)
    stats_files = []
    main_stats = os.path.join(reports_dir, ".stats.json")
    if os.path.exists(main_stats):
        stats_files.append(main_stats)
    for f in os.listdir(reports_dir):
        if f.startswith(".stats_gw") and f.endswith(".json"):
            stats_files.append(os.path.join(reports_dir, f))

    for sf in stats_files:
        with open(sf, "r", encoding="utf-8") as f:
            worker_stats = json.load(f)
        stats["total"] += worker_stats.get("total", 0)
        stats["passed"] += worker_stats.get("passed", 0)
        stats["failed"] += worker_stats.get("failed", 0)
        stats["skipped"] += worker_stats.get("skipped", 0)
        stats["failures"].extend(worker_stats.get("failures", []))
        # Clean up worker stats file
        if sf != main_stats:
            os.remove(sf)

    total = stats["total"]
    stats["pass_rate"] = f"{(stats['passed'] / total * 100):.1f}%" if total > 0 else "0%"
    stats["duration"] = f"{duration}s"
    stats["env"] = config.get("current_env", "unknown")

    # Write aggregated stats
    with open(main_stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)

    # Send notifications (email + feishu)
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
