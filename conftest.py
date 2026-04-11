import json
import os

import allure
import pytest

from common.config_loader import load_config
from common.data_loader import scan_testcase_files, load_testcases
from common.variable_pool import VariablePool
from common.runner import run_testcase
from common.hook_manager import HookManager
from common.db_handler import DBHandler
from common.logger import setup_logger, log_request


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def pytest_addoption(parser):
    parser.addoption("--env", default=None, help="Test environment (dev/test/staging/prod)")
    parser.addoption("--path", default="testcases", help="Test case directory or file path")
    parser.addoption("--report", default=None, help="Report type (allure/html/both)")


def pytest_configure(config):
    env = config.getoption("--env", default=None)
    config_dir = os.path.join(PROJECT_ROOT, "config")
    cfg = load_config(config_dir, env=env)

    report_type = config.getoption("--report", default=None) or cfg.get("report_type", "allure")
    cfg["report_type"] = report_type

    config._autotest_config = cfg
    config._autotest_pool = VariablePool()
    config._autotest_logger = setup_logger(os.path.join(PROJECT_ROOT, "logs"))

    hooks_dir = os.path.join(PROJECT_ROOT, "hooks")
    config._autotest_hooks = HookManager(hooks_dir)

    config._autotest_db = None
    if cfg.get("database"):
        try:
            config._autotest_db = DBHandler(cfg["database"])
        except Exception as e:
            config._autotest_logger.warning(f"Database connection failed: {e}")

    # Set global variables
    for k, v in cfg.get("global_variables", {}).items():
        config._autotest_pool.set_global(k, v)

    # Stats collection — stored on config (accessible from report hooks)
    config._autotest_stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0, "failures": []
    }


def pytest_unconfigure(config):
    if hasattr(config, "_autotest_db") and config._autotest_db:
        config._autotest_db.close()


def pytest_collect_file(parent, file_path):
    ext = file_path.suffix.lower()
    if ext in (".yaml", ".yml", ".json", ".xlsx"):
        if any(part == "testcases" for part in file_path.parts):
            return TestCaseFile.from_parent(parent, path=file_path)


class TestCaseFile(pytest.File):
    def collect(self):
        # Clear module-scope variables when entering a new test file
        pool = self.config._autotest_pool
        pool.clear_module()

        data = load_testcases(str(self.path))
        module_name = data.get("module", self.path.stem)
        for i, case in enumerate(data.get("testcases", [])):
            name = case.get("name", f"case_{i}")
            yield TestCaseItem.from_parent(
                self, name=name, callobj=case, module_name=module_name
            )


class TestCaseItem(pytest.Item):
    def __init__(self, name, parent, callobj, module_name=""):
        super().__init__(name, parent)
        self._case = callobj
        self._module_name = module_name
        level = callobj.get("level", "normal")
        self.user_properties.append(("module", module_name))
        self.user_properties.append(("level", level))

    def runtest(self):
        config = self.config
        cfg = config._autotest_config
        pool = config._autotest_pool
        logger = config._autotest_logger
        hooks = config._autotest_hooks
        db = config._autotest_db

        module_name = self._module_name

        result = run_testcase(
            case=self._case,
            base_url=cfg["base_url"],
            pool=pool,
            timeout=cfg.get("timeout", 30),
            hook_manager=hooks,
            db_handler=db,
            global_headers=cfg.get("global_headers", {}),
        )

        # Log
        log_request(
            logger=logger,
            module=module_name,
            name=self._case.get("name", ""),
            method=self._case.get("method", ""),
            url=cfg["base_url"] + self._case.get("url", ""),
            headers=self._case.get("headers"),
            body=self._case.get("body"),
            status_code=result["response"]["status_code"] if result["response"] else None,
            elapsed_ms=result["response"]["elapsed_ms"] if result["response"] else 0,
            response=result["response"]["body"] if result["response"] else None,
            extracts=result.get("extracts"),
            validations=[
                f"{v['keyword']}: {'PASS' if v['passed'] else 'FAIL'}"
                for v in result.get("validations", [])
            ],
        )

        # Allure reporting
        allure.dynamic.feature(module_name)
        allure.dynamic.story(self._case.get("name", ""))
        if self._case.get("description"):
            allure.dynamic.description(self._case["description"])
        level_map = {
            "blocker": allure.severity_level.BLOCKER,
            "critical": allure.severity_level.CRITICAL,
            "normal": allure.severity_level.NORMAL,
            "minor": allure.severity_level.MINOR,
            "trivial": allure.severity_level.TRIVIAL,
        }
        severity = level_map.get(self._case.get("level", "normal"), allure.severity_level.NORMAL)
        allure.dynamic.severity(severity)

        if not result["passed"]:
            failures = []
            if result.get("error"):
                failures.append(f"Request error: {result['error']}")
            for v in result.get("validations", []):
                if not v["passed"]:
                    failures.append(
                        f"{v['keyword']}: {v.get('expression', '')} "
                        f"actual={v.get('actual')} expect={v.get('expect', '')}"
                    )
            raise TestCaseFailure("\n".join(failures))

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, TestCaseFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, None, f"{self._module_name} > {self.name}"


class TestCaseFailure(Exception):
    pass


# Stats collection — use pytest_runtest_makereport hook which has access to item
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    stats = getattr(item.config, "_autotest_stats", None)
    if stats is None:
        return

    # Count skips from setup phase (e.g., skipif markers)
    if report.when == "setup" and report.skipped:
        stats["total"] += 1
        stats["skipped"] += 1
        return

    if report.when != "call":
        return

    stats["total"] += 1
    if report.passed:
        stats["passed"] += 1
    elif report.failed:
        stats["failed"] += 1
        stats["failures"].append({
            "module": dict(report.user_properties).get("module", ""),
            "name": report.nodeid.split("::")[-1],
            "error": str(report.longrepr)[:200],
        })
    elif report.skipped:
        stats["skipped"] += 1


def pytest_sessionfinish(session, exitstatus):
    stats = getattr(session.config, "_autotest_stats", None)
    if stats:
        total = stats["total"]
        stats["pass_rate"] = f"{(stats['passed'] / total * 100):.1f}%" if total > 0 else "0%"
        # duration will be patched by run.py; set a default here for standalone use
        stats.setdefault("duration", "unknown")
        stats_path = os.path.join(PROJECT_ROOT, "reports", ".stats.json")
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False)
