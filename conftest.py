"""pytest 集成模块（conftest.py）。

实现框架与 pytest 的对接，包括：
    - 自定义命令行参数（--env, --path, --report, --level）
    - 框架初始化（加载配置、创建变量池、连接数据库等）
    - 自动发现 testcases/ 目录下的 YAML/JSON/Excel 文件
    - 按优先级过滤用例（--level P0,P1）
    - 执行用例并生成 Allure 报告标签
    - 收集测试统计数据（用于邮件/飞书通知）
    - 多进程并行时每个 worker 独立写入统计文件
"""

import json
import os

import allure
import pytest

from common.config_loader import load_config
from common.data_loader import load_testcases
from common.variable_pool import VariablePool
from common.runner import run_testcase
from common.hook_manager import HookManager
from common.db_handler import DBHandler
from common.logger import setup_logger, log_request


# 项目根目录（conftest.py 所在目录）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# ==========================================================================
# pytest 钩子：注册自定义命令行参数
# ==========================================================================
def pytest_addoption(parser):
    """注册框架的命令行参数。"""
    parser.addoption("--env", default=None, help="Test environment (dev/test/staging/prod)")
    parser.addoption("--path", default="testcases", help="Test case directory or file path")
    parser.addoption("--report", default=None, help="Report type (allure/html/both)")
    parser.addoption("--level", default=None,
                     help="Filter by priority level, comma-separated (e.g., P0,P1 or blocker,critical)")


# ==========================================================================
# pytest 钩子：框架初始化（加载配置、创建各组件实例）
# ==========================================================================
def pytest_configure(config):
    """pytest 启动时初始化框架。

    创建并挂载到 config 对象上的实例：
        config._autotest_config   → 合并后的配置字典
        config._autotest_pool     → 变量池
        config._autotest_logger   → 日志实例
        config._autotest_hooks    → Hook 管理器
        config._autotest_db       → 数据库处理器（可选）
        config._autotest_stats    → 统计数据
    """
    env = config.getoption("--env", default=None)
    # 支持通过环境变量覆盖配置目录（用于集成测试）
    config_dir = os.environ.get("AUTOTEST_CONFIG_DIR") or os.path.join(PROJECT_ROOT, "config")
    cfg = load_config(config_dir, env=env)

    report_type = config.getoption("--report", default=None) or cfg.get("report_type", "allure")
    cfg["report_type"] = report_type

    # 挂载各组件到 config 对象
    config._autotest_config = cfg
    config._autotest_pool = VariablePool()
    config._autotest_logger = setup_logger(os.path.join(PROJECT_ROOT, "logs"))

    # 加载 Hook 函数
    hooks_dir = os.path.join(PROJECT_ROOT, "hooks")
    config._autotest_hooks = HookManager(hooks_dir)

    # 连接数据库（可选，连接失败不影响运行）
    config._autotest_db = None
    if cfg.get("database"):
        try:
            config._autotest_db = DBHandler(cfg["database"])
        except Exception as e:
            config._autotest_logger.warning(f"Database connection failed: {e}")

    # 将全局变量写入变量池
    for k, v in cfg.get("global_variables", {}).items():
        config._autotest_pool.set_global(k, v)

    # 初始化统计数据（用于邮件/飞书通知）
    config._autotest_stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0, "failures": []
    }

    # 跟踪当前测试文件路径（用于文件切换时清理模块变量）
    config._autotest_current_file = None


def pytest_unconfigure(config):
    """pytest 退出时清理资源。"""
    if hasattr(config, "_autotest_db") and config._autotest_db:
        config._autotest_db.close()


# ==========================================================================
# pytest 钩子：自动发现 testcases/ 下的用例文件
# ==========================================================================
def pytest_collect_file(parent, file_path):
    """自定义文件收集器：发现 testcases/ 目录下的 YAML/JSON/Excel 文件。

    只收集路径中包含 "testcases" 目录的文件，避免误收集配置文件等。
    """
    ext = file_path.suffix.lower()
    if ext in (".yaml", ".yml", ".json", ".xlsx"):
        # 检查路径组件中是否包含 "testcases" 目录
        if any(part == "testcases" for part in file_path.parts):
            return TestCaseFile.from_parent(parent, path=file_path)


# ==========================================================================
# 优先级别名映射：P0/P1/P2/P3/P4 → 标准名称
# ==========================================================================
LEVEL_ALIASES = {
    "p0": "blocker",
    "p1": "critical",
    "p2": "normal",
    "p3": "minor",
    "p4": "trivial",
}


# ==========================================================================
# 自定义 pytest 收集器和执行器
# ==========================================================================
class TestCaseFile(pytest.File):
    """用例文件收集器：解析单个 YAML/JSON/Excel 文件，生成 TestCaseItem。"""

    def collect(self):
        """解析文件中的用例列表，按 --level 过滤后逐个生成 TestCaseItem。"""
        data = load_testcases(str(self.path))
        module_name = data.get("module", self.path.stem)

        # 解析 --level 过滤参数（如 "P0,P1" → {"blocker", "critical"}）
        level_filter = self.config.getoption("--level", default=None)
        allowed_levels = None
        if level_filter:
            raw_levels = [l.strip().lower() for l in level_filter.split(",")]
            allowed_levels = set()
            for l in raw_levels:
                allowed_levels.add(LEVEL_ALIASES.get(l, l))

        for i, case in enumerate(data.get("testcases", [])):
            # 按优先级过滤
            if allowed_levels is not None:
                case_level = case.get("level", "normal").lower()
                normalized = LEVEL_ALIASES.get(case_level, case_level)
                if normalized not in allowed_levels:
                    continue

            name = case.get("name", f"case_{i}")
            yield TestCaseItem.from_parent(
                self, name=name, callobj=case, module_name=module_name
            )


class TestCaseItem(pytest.Item):
    """单个测试用例的 pytest 执行器。"""

    def __init__(self, name, parent, callobj, module_name=""):
        super().__init__(name, parent)
        self._case = callobj             # 用例数据字典
        self._module_name = module_name  # 所属模块名（显示在报告中）
        level = callobj.get("level", "normal")
        # 添加用户属性（用于统计和报告）
        self.user_properties.append(("module", module_name))
        self.user_properties.append(("level", level))

    def runtest(self):
        """执行测试用例（由 pytest 调用）。"""
        config = self.config
        cfg = config._autotest_config
        pool = config._autotest_pool
        logger = config._autotest_logger
        hooks = config._autotest_hooks
        db = config._autotest_db

        # 文件切换时清空模块变量（实现文件间变量隔离）
        current_file = str(self.path)
        if config._autotest_current_file != current_file:
            pool.clear_module()
            config._autotest_current_file = current_file

        module_name = self._module_name

        # 调用核心执行引擎
        result = run_testcase(
            case=self._case,
            base_url=cfg["base_url"],
            pool=pool,
            timeout=cfg.get("timeout", 30),
            hook_manager=hooks,
            db_handler=db,
            global_headers=cfg.get("global_headers", {}),
            default_retry=cfg.get("retry", 0),
        )

        # 记录完整的请求/响应日志
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

        # 设置 Allure 报告标签
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

        # 用例失败时抛出异常（pytest 通过异常判断用例状态）
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
        """自定义失败信息的显示格式。"""
        if isinstance(excinfo.value, TestCaseFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        """pytest 报告中显示的用例标识。"""
        return self.path, None, f"{self._module_name} > {self.name}"


class TestCaseFailure(Exception):
    """用例执行失败时抛出的自定义异常。"""
    pass


# ==========================================================================
# pytest 钩子：收集测试统计数据（用于邮件/飞书通知）
# ==========================================================================
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """每个用例执行完后收集统计数据。

    使用 hookwrapper 模式获取测试报告对象，统计 passed/failed/skipped 数量。
    数据存储在 item.config._autotest_stats 中。
    """
    outcome = yield
    report = outcome.get_result()

    stats = getattr(item.config, "_autotest_stats", None)
    if stats is None:
        return

    # setup 阶段的 skip（如 @pytest.mark.skipif）
    if report.when == "setup" and report.skipped:
        stats["total"] += 1
        stats["skipped"] += 1
        return

    # 只统计 call 阶段（实际执行阶段）
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
            "error": str(report.longrepr)[:200],  # 截取前 200 字符
        })
    elif report.skipped:
        stats["skipped"] += 1


def pytest_sessionfinish(session, exitstatus):
    """pytest 会话结束时将统计数据写入 JSON 文件。

    单进程模式：写入 reports/.stats.json
    多进程模式（xdist）：每个 worker 写入 reports/.stats_gw{N}.json，
                        由 run.py 聚合。
    """
    stats = getattr(session.config, "_autotest_stats", None)
    if stats:
        total = stats["total"]
        stats["pass_rate"] = f"{(stats['passed'] / total * 100):.1f}%" if total > 0 else "0%"
        stats.setdefault("duration", "unknown")

        reports_dir = os.path.join(PROJECT_ROOT, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        # xdist 多进程：每个 worker 写独立文件
        worker_id = os.environ.get("PYTEST_XDIST_WORKER")
        if worker_id:
            stats_path = os.path.join(reports_dir, f".stats_{worker_id}.json")
        else:
            stats_path = os.path.join(reports_dir, ".stats.json")

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False)
