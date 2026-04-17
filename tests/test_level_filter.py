"""Tests for --level priority filtering in conftest.py.

These tests verify that the --level filter correctly includes/excludes test cases
based on their priority level. They use subprocess + httpbin.org, so assertions
focus on COLLECTION (which cases were discovered), not on pass/fail status
(which depends on network availability).
"""

import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


def _run(level=None):
    """Run pytest --collect-only against testcases with optional --level filter.

    Uses --collect-only to avoid actually executing HTTP requests,
    making tests fast and network-independent.
    """
    tc_dir = os.path.join(PROJECT_ROOT, "testcases", "_level_test")
    os.makedirs(tc_dir, exist_ok=True)
    yaml_path = os.path.join(tc_dir, "levels.yaml")
    config_dir = os.path.join(PROJECT_ROOT, "config")
    tmp_env = os.path.join(config_dir, "_leveltest.yaml")

    try:
        with open(yaml_path, "w") as f:
            f.write(
                "module: 优先级测试\n"
                "testcases:\n"
                "  - name: P0_blocker用例\n"
                "    level: P0\n"
                "    method: GET\n"
                "    url: /get\n"
                "    validate:\n"
                "      - eq: [status_code, 200]\n"
                "  - name: P1_critical用例\n"
                "    level: P1\n"
                "    method: GET\n"
                "    url: /get\n"
                "    validate:\n"
                "      - eq: [status_code, 200]\n"
                "  - name: P2_normal用例\n"
                "    level: P2\n"
                "    method: GET\n"
                "    url: /get\n"
                "    validate:\n"
                "      - eq: [status_code, 200]\n"
                "  - name: 无level用例\n"
                "    method: GET\n"
                "    url: /get\n"
                "    validate:\n"
                "      - eq: [status_code, 200]\n"
            )

        with open(tmp_env, "w") as f:
            f.write(
                "base_url: https://httpbin.org\n"
                "global_headers:\n  Accept: application/json\n"
                "global_variables: {}\n"
            )

        args = [
            PYTHON, "-m", "pytest", tc_dir,
            "--collect-only", "-q", "--no-header",
            f"--rootdir={PROJECT_ROOT}",
            f"-c={os.path.join(PROJECT_ROOT, 'pytest.ini')}",
            "--env", "_leveltest",
        ]
        if level:
            args.extend(["--level", level])

        env = os.environ.copy()
        env["AUTOTEST_CONFIG_DIR"] = config_dir
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30,
        )
        return result
    finally:
        for p in [yaml_path, tmp_env]:
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(tc_dir):
            os.rmdir(tc_dir)


def _count_collected(result):
    """Extract the number of collected items from pytest output."""
    match = re.search(r"(\d+) tests? collected", result.stdout)
    if match:
        return int(match.group(1))
    # Fallback: count lines with test names
    return sum(1 for line in result.stdout.splitlines() if "用例" in line)


def test_no_level_filter_collects_all():
    """Without --level, all 4 cases should be collected."""
    result = _run(level=None)
    assert _count_collected(result) == 4, f"stdout: {result.stdout}"


def test_filter_p0_only():
    """--level P0 should only collect the blocker case."""
    result = _run(level="P0")
    assert "P0_blocker" in result.stdout
    assert "P1_critical" not in result.stdout
    assert "P2_normal" not in result.stdout
    assert _count_collected(result) == 1, f"stdout: {result.stdout}"


def test_filter_p0_p1():
    """--level P0,P1 should collect blocker + critical cases."""
    result = _run(level="P0,P1")
    assert "P0_blocker" in result.stdout
    assert "P1_critical" in result.stdout
    assert "P2_normal" not in result.stdout
    assert _count_collected(result) == 2, f"stdout: {result.stdout}"


def test_filter_by_name_blocker():
    """--level blocker should work the same as --level P0."""
    result = _run(level="blocker")
    assert "P0_blocker" in result.stdout
    assert _count_collected(result) == 1, f"stdout: {result.stdout}"


def test_filter_normal_includes_default():
    """--level P2 should include cases with level=P2 and default (normal) cases."""
    result = _run(level="P2")
    assert "P2_normal" in result.stdout
    assert "无level" in result.stdout  # default level is normal = P2
    assert "P0_blocker" not in result.stdout
    assert _count_collected(result) == 2, f"stdout: {result.stdout}"
