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

    # Run tests
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    duration = round(time.time() - start_time, 1)

    # Read stats from pytest session
    stats_path = os.path.join(reports_dir, ".stats.json")
    stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "pass_rate": "0%", "duration": f"{duration}s",
        "env": config.get("current_env", "unknown"), "failures": [],
    }
    if os.path.exists(stats_path):
        with open(stats_path, "r", encoding="utf-8") as f:
            file_stats = json.load(f)
        stats.update(file_stats)
        stats["duration"] = f"{duration}s"
        stats["env"] = config.get("current_env", "unknown")

    # Send notification
    if config.get("email", {}).get("enabled"):
        maybe_send_notification(
            email_config=config["email"],
            stats=stats,
            send_on=config["email"].get("send_on", "fail"),
            report_path=report_path,
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
