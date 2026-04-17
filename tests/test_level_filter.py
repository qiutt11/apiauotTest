"""Tests for --level priority filtering in conftest.py."""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


def _run(level=None, extra_args=None):
    """Run pytest against testcases with optional --level filter."""
    tc_dir = os.path.join(PROJECT_ROOT, "testcases", "_level_test")
    os.makedirs(tc_dir, exist_ok=True)
    yaml_path = os.path.join(tc_dir, "levels.yaml")

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

        args = [
            PYTHON, "-m", "pytest", tc_dir,
            "-v", "--tb=short", "--no-header",
            f"--rootdir={PROJECT_ROOT}",
            f"-c={os.path.join(PROJECT_ROOT, 'pytest.ini')}",
        ]
        if level:
            args.extend(["--level", level])
        if extra_args:
            args.extend(extra_args)

        # Use a temp config pointing to httpbin
        config_dir = os.path.join(PROJECT_ROOT, "config")
        tmp_env = os.path.join(config_dir, "_leveltest.yaml")
        with open(tmp_env, "w") as f:
            f.write(
                "base_url: https://httpbin.org\n"
                "global_headers:\n  Accept: application/json\n"
                "global_variables: {}\n"
            )

        env = os.environ.copy()
        env["AUTOTEST_CONFIG_DIR"] = config_dir
        result = subprocess.run(
            args + ["--env", "_leveltest"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
        )
        return result
    finally:
        if os.path.exists(yaml_path):
            os.remove(yaml_path)
        if os.path.exists(tc_dir):
            os.rmdir(tc_dir)
        tmp_env = os.path.join(config_dir, "_leveltest.yaml")
        if os.path.exists(tmp_env):
            os.remove(tmp_env)


def test_no_level_filter_runs_all():
    """Without --level, all 4 cases should be collected."""
    result = _run(level=None)
    assert "4 passed" in result.stdout, f"stdout: {result.stdout}"


def test_filter_p0_only():
    """--level P0 should only run the blocker case."""
    result = _run(level="P0")
    assert "P0_blocker" in result.stdout
    assert "P1_critical" not in result.stdout
    assert "P2_normal" not in result.stdout
    assert "1 passed" in result.stdout, f"stdout: {result.stdout}"


def test_filter_p0_p1():
    """--level P0,P1 should run blocker + critical cases."""
    result = _run(level="P0,P1")
    assert "P0_blocker" in result.stdout
    assert "P1_critical" in result.stdout
    assert "P2_normal" not in result.stdout
    assert "2 passed" in result.stdout, f"stdout: {result.stdout}"


def test_filter_by_name_blocker():
    """--level blocker should work the same as --level P0."""
    result = _run(level="blocker")
    assert "P0_blocker" in result.stdout
    assert "1 passed" in result.stdout, f"stdout: {result.stdout}"


def test_filter_normal_includes_default():
    """--level P2 should include cases with level=P2 and default (normal) cases."""
    result = _run(level="P2")
    assert "P2_normal" in result.stdout
    assert "无level" in result.stdout  # default level is normal = P2
    assert "2 passed" in result.stdout, f"stdout: {result.stdout}"
