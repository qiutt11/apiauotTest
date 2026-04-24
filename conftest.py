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

import copy
import json
import os

import allure
import pytest

from common.config_loader import load_config
from common.data_loader import load_testcases, load_excel_rows
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

            # ---- Excel 驱动用例 ----
            # 当 YAML 中的 testcase 同时包含 excel_source 和 steps 字段时，
            # 视为"Excel 数据驱动"用例：从 Excel 加载每行数据，每行生成一个
            # ExcelDrivenItem，在运行时按 steps 顺序执行（如：保存→查看详情）。
            if case.get("excel_source") and case.get("steps"):
                excel_path = case["excel_source"]
                # excel_source 支持相对路径，基于 YAML 文件所在目录解析
                if not os.path.isabs(excel_path):
                    excel_path = os.path.join(os.path.dirname(str(self.path)), excel_path)
                if not os.path.exists(excel_path):
                    raise FileNotFoundError(
                        f"Excel data file not found: {excel_path} "
                        f"(referenced by excel_source in {self.path})"
                    )
                rows = load_excel_rows(excel_path)
                for row_idx, row_data in enumerate(rows):
                    # 用 Excel 行的第一列值作为用例名后缀，方便在报告中区分不同行数据
                    # 例如："保存并验证详情[张三]"、"保存并验证详情[李四]"
                    first_val = next(iter(row_data.values()), row_idx)
                    item_name = f"{name}[{first_val}]"
                    yield ExcelDrivenItem.from_parent(
                        self, name=item_name,
                        steps=case["steps"], row_data=row_data,
                        row_index=row_idx, module_name=module_name,
                    )
                continue

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


# ==========================================================================
# Excel 驱动用例的辅助函数
# ==========================================================================
def _flatten_excel_validations(prefix: str, value) -> list[dict]:
    """递归展开 Excel 值为 eq 断言列表。

    根据值的类型递归生成 JSONPath 断言：
        - 简单值（str/int/float/bool）→ 直接生成 eq 断言
        - dict 嵌套对象 → 递归展开每个 key，如 $.data.address.city
        - list 数组 → 按下标展开，如 $.data.tags[0]
        - 数组内嵌套对象 → 继续递归，如 $.data.items[0].name

    示例：
        prefix="$.data", value={"name": "张三", "tags": ["vip"]}
        → [{"eq": ["$.data.name", "张三"]}, {"eq": ["$.data.tags[0]", "vip"]}]

    Args:
        prefix: JSONPath 前缀（如 "$.data.name"）
        value: Excel 单元格解析后的值

    Returns:
        断言列表，如 [{"eq": ["$.data.name", "张三"]}, ...]
    """
    validations = []
    if isinstance(value, dict):
        for k, v in value.items():
            validations.extend(_flatten_excel_validations(f"{prefix}.{k}", v))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            validations.extend(_flatten_excel_validations(f"{prefix}[{i}]", item))
    else:
        validations.append({"eq": [prefix, value]})
    return validations


def _build_body_from_excel(row_data: dict, body_from_excel) -> dict:
    """根据 body_from_excel 配置，将 Excel 行数据转换为请求 body。

    两种用法：
        1. body_from_excel: true
           → 所有 Excel 列直接作为 body 字段（列名 = 字段名）
        2. body_from_excel: + field_mapping:
           → Excel 列名通过 mapping 映射到接口字段名，未映射的列仍用原名
           示例：field_mapping: {name: userName} → Excel 的 name 列 → body 的 userName 字段

    Args:
        row_data: Excel 行数据字典（{列名: 值}）
        body_from_excel: True 或 dict（含 field_mapping）

    Returns:
        请求 body 字典
    """
    # body_from_excel: true → 直接使用 Excel 列名作为字段名
    if body_from_excel is True:
        return dict(row_data)

    # body_from_excel: {field_mapping: {excel列名: 接口字段名}} → 映射后作为 body
    if isinstance(body_from_excel, dict):
        mapping = body_from_excel.get("field_mapping", {})
        body = {}
        for col, val in row_data.items():
            # 在 mapping 中查找映射名，找不到则用原列名
            field_name = mapping.get(col, col)
            body[field_name] = val
        return body

    return dict(row_data)


def _build_excel_validations(row_data: dict, validate_from_excel: dict) -> list[dict]:
    """根据 validate_from_excel 配置，将 Excel 行数据转换为 eq 断言列表。

    工作方式：
        1. 从配置中读取 prefix（JSONPath 前缀，默认 $.data）和可选的 field_mapping
        2. 遍历 Excel 行的每列数据
        3. 通过 field_mapping 将 Excel 列名映射为响应字段名（未映射则用原列名）
        4. 调用 _flatten_excel_validations 递归展开为 eq 断言

    示例：
        Excel 列 name="张三"，mapping={name: user_name}，prefix=$.data
        → 生成断言 {"eq": ["$.data.user_name", "张三"]}

    Args:
        row_data: Excel 行数据字典（{列名: 值}）
        validate_from_excel: 配置字典，含 prefix 和可选 field_mapping

    Returns:
        断言列表，如 [{"eq": ["$.data.name", "张三"]}, ...]
    """
    prefix = validate_from_excel.get("prefix", "$.data")
    mapping = validate_from_excel.get("field_mapping", {})
    validations = []
    for col, val in row_data.items():
        field_name = mapping.get(col, col)
        validations.extend(_flatten_excel_validations(f"{prefix}.{field_name}", val))
    return validations


class ExcelDrivenItem(pytest.Item):
    """Excel 驱动的多步骤测试用例执行器。

    每个实例对应 Excel 中的一行数据，按 steps 顺序执行保存→详情等多步操作。
    """

    def __init__(self, name, parent, steps, row_data, row_index, module_name=""):
        """初始化 Excel 驱动用例。

        Args:
            name: 用例名（含 Excel 行标识，如 "保存并验证详情[张三]"）
            parent: 父 pytest 节点（TestCaseFile）
            steps: YAML 中定义的步骤列表（每个 step 是一个 case 字典）
            row_data: 当前 Excel 行的数据字典（{列名: 值}）
            row_index: Excel 行号（从 0 开始，用于调试）
            module_name: 所属模块名（显示在 Allure 报告中）
        """
        super().__init__(name, parent)
        self._steps = steps          # YAML 中定义的步骤列表
        self._row_data = row_data    # 当前 Excel 行数据
        self._row_index = row_index  # Excel 行索引
        self._module_name = module_name
        self.user_properties.append(("module", module_name))

    def runtest(self):
        """执行 Excel 驱动的多步骤用例（由 pytest 调用）。

        执行流程：
            1. 将 Excel 行数据注入变量池（可通过 ${列名} 引用）
            2. 遍历 steps，对每个 step：
               a. 若有 body_from_excel，将 Excel 行数据转换为请求 body
               b. 若有 validate_from_excel，将 Excel 行数据展开为 eq 断言
               c. 调用 run_testcase() 执行
               d. 任一 step 失败则整体失败，停止后续 step
        """
        config = self.config
        cfg = config._autotest_config
        pool = config._autotest_pool
        logger = config._autotest_logger
        hooks = config._autotest_hooks
        db = config._autotest_db

        # 文件切换时清空模块变量（与 TestCaseItem 保持一致的隔离逻辑）
        current_file = str(self.path)
        if config._autotest_current_file != current_file:
            pool.clear_module()
            config._autotest_current_file = current_file

        # 将 Excel 行数据写入变量池，使 step 中可通过 ${列名} 引用
        # 例如 Excel 有 name 列，则 url: /api/user/${name} 会被替换
        for col, val in self._row_data.items():
            pool.set_module(col, val)

        # 设置 Allure 报告标签
        allure.dynamic.feature(self._module_name)
        allure.dynamic.story(self.name)

        # ---- 逐步执行 steps ----
        for step_index, step in enumerate(self._steps):
            # 深拷贝 step，避免修改 YAML 原始数据（多行数据共享同一 steps 定义，
            # 浅拷贝会导致嵌套 dict 如 headers 在行间共享引用）
            step_case = copy.deepcopy(step)
            step_name = step_case.get("name", f"step_{step_index}")

            # body_from_excel：将 Excel 行数据转换为请求 body
            # 支持直接映射（true）或字段名映射（field_mapping）
            if step_case.get("body_from_excel"):
                step_case["body"] = _build_body_from_excel(
                    self._row_data, step_case.pop("body_from_excel")
                )

            # validate_from_excel：将 Excel 行数据递归展开为 eq 断言
            # 生成的断言追加到 validate 列表末尾（保留原有的 validate 断言）
            if step_case.get("validate_from_excel"):
                excel_validations = _build_excel_validations(
                    self._row_data, step_case.pop("validate_from_excel")
                )
                existing = step_case.get("validate", [])
                step_case["validate"] = existing + excel_validations

            # 调用现有的核心执行引擎（与 TestCaseItem 使用同一套逻辑）
            result = run_testcase(
                case=step_case,
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
                module=self._module_name,
                name=step_name,
                method=step_case.get("method", ""),
                url=cfg["base_url"] + step_case.get("url", ""),
                headers=step_case.get("headers"),
                body=step_case.get("body"),
                status_code=result["response"]["status_code"] if result["response"] else None,
                elapsed_ms=result["response"]["elapsed_ms"] if result["response"] else 0,
                response=result["response"]["body"] if result["response"] else None,
                extracts=result.get("extracts"),
                validations=[
                    f"{v['keyword']}: {'PASS' if v['passed'] else 'FAIL'}"
                    for v in result.get("validations", [])
                ],
            )

            # 任一 step 失败则整体失败，停止执行后续 step
            if not result["passed"]:
                failures = []
                if result.get("error"):
                    failures.append(f"[{step_name}] Request error: {result['error']}")
                for v in result.get("validations", []):
                    if not v["passed"]:
                        failures.append(
                            f"[{step_name}] {v['keyword']}: {v.get('expression', '')} "
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
