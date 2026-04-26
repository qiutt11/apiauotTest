"""核心执行引擎。

编排单个测试用例的完整执行流程：
    1. 解析变量 ${xxx}
    2. db_setup 数据库前置操作（支持 extract 提取变量）
    3. 用 db_setup 提取的变量重新解析请求参数
    4. before hook 请求前处理
    5. 发送 HTTP 请求（带重试机制）
    6. after hook 响应后处理
    7. extract 提取响应变量
    8. db_extract 数据库查询校验
    9. validate 断言校验
    10. db_teardown 数据库清理（始终执行，finally 语义）

重试机制：
    - 请求异常或断言失败时自动重试
    - 重试次数：全局 config.retry + 用例级 case.retry 覆盖
    - 递增退避：2s → 4s → 6s → ... 最大 10s
    - db_setup / hook 失败不触发重试
"""

import time
from typing import Any

from loguru import logger as _logger

from common.request_handler import send_request
from common.extractor import extract_fields, get_extract_scope
from common.validator import validate_case
from common.variable_pool import VariablePool


def run_testcase(
    case: dict,
    base_url: str,
    pool: VariablePool,
    timeout: int = 30,
    hook_manager=None,
    db_handler=None,
    global_headers: dict = None,
    default_retry: int = 0,
) -> dict[str, Any]:
    """执行单个测试用例，返回执行结果。

    Args:
        case: 用例字典（从 YAML/JSON/Excel 解析而来）。
              可包含 base_url 字段覆盖全局 base_url（支持跨系统场景），
              支持 ${变量名} 引用，如 base_url: ${system_b_url}。
        base_url: 接口基础地址（如 https://api.example.com），
                  当 case 中未指定 base_url 时使用此值。
        pool: 变量池实例
        timeout: HTTP 请求超时时间（秒）
        hook_manager: Hook 管理器实例（可选）
        db_handler: 数据库处理器实例（可选）
        global_headers: 全局请求头（可选，会被用例 headers 覆盖）
        default_retry: 全局默认重试次数

    Returns:
        结果字典：{name, passed, response, extracts, db_vars, validations, error}
    """
    name = case.get("name", "unnamed")
    # 用例级 base_url 优先于全局 base_url（支持多系统场景）
    # 用例中可写 base_url: https://other-system.com 或 base_url: ${system_b_url}
    case_base_url = case.get("base_url")
    if case_base_url:
        base_url = str(pool.resolve(case_base_url))
    # 用例级 retry 优先于全局 default_retry
    retry_count = case.get("retry", default_retry)

    # ---- 第 1 步：解析变量 ----
    resolved = pool.resolve({
        "method": case.get("method", "GET"),
        "url": case.get("url", ""),
        "headers": case.get("headers", {}),
        "body": case.get("body"),
    })

    method = resolved["method"]
    url = base_url + resolved["url"]
    # 全局 headers（低优先级）+ 用例 headers（高优先级）
    headers = {**(global_headers or {}), **resolved["headers"]}
    body = resolved["body"]

    try:
        # ---- 第 2 步：db_setup 数据库前置操作 ----
        setup_vars = {}
        if db_handler and case.get("db_setup"):
            try:
                # 逐条解析 SQL 中的变量
                resolved_sql_list = []
                for sql_item in case["db_setup"]:
                    resolved_item = pool.resolve(sql_item)
                    resolved_sql_list.append(resolved_item)
                # 执行 SQL 并提取变量
                setup_vars = db_handler.execute_setup(resolved_sql_list)
                for k, v in setup_vars.items():
                    pool.set_module(k, v)

                # ---- 第 3 步：用 db_setup 提取的变量重新解析请求参数 ----
                # base_url 也需要重新解析（可能引用了 db_setup 提取的变量）
                if case_base_url:
                    base_url = str(pool.resolve(case_base_url))
                resolved = pool.resolve({
                    "method": case.get("method", "GET"),
                    "url": case.get("url", ""),
                    "headers": case.get("headers", {}),
                    "body": case.get("body"),
                })
                method = resolved["method"]
                url = base_url + resolved["url"]
                headers = {**(global_headers or {}), **resolved["headers"]}
                body = resolved["body"]
            except Exception as e:
                _logger.error(f"db_setup failed: {e}")
                return {
                    "name": name,
                    "passed": False,
                    "response": {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": None},
                    "extracts": {},
                    "db_vars": {},
                    "validations": [],
                    "error": f"db_setup failed: {e}",
                }

        # ---- 第 4 步：before hook 请求前处理 ----
        if hook_manager and case.get("hook", {}).get("before"):
            request_data = {"method": method, "url": url, "headers": headers, "body": body}
            try:
                request_data = hook_manager.call(case["hook"]["before"], request_data)
                method = request_data["method"]
                url = request_data["url"]
                headers = request_data["headers"]
                body = request_data["body"]
            except Exception as e:
                _logger.error(f"before hook failed: {e}")
                return {
                    "name": name,
                    "passed": False,
                    "response": {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": None},
                    "extracts": {},
                    "db_vars": {},
                    "validations": [],
                    "error": f"before hook failed: {e}",
                }

        # ---- 第 5~9 步：请求 + 校验（带重试） ----
        result = _execute_with_retry(
            name=name,
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
            case=case,
            pool=pool,
            hook_manager=hook_manager,
            db_handler=db_handler,
            setup_vars=setup_vars,
            retry_count=retry_count,
        )
        return result

    finally:
        # ---- 第 10 步：db_teardown 始终执行 ----
        _run_db_teardown(case, pool, db_handler)


def _execute_with_retry(
    name: str,
    method: str,
    url: str,
    headers: dict,
    body: dict,
    timeout: int,
    case: dict,
    pool: VariablePool,
    hook_manager,
    db_handler,
    setup_vars: dict,
    retry_count: int,
) -> dict[str, Any]:
    """执行 HTTP 请求 + 提取 + 校验，失败时按配置重试。

    重试触发条件：
        - 请求异常（超时、连接失败等）
        - 断言失败（请求成功但校验不通过）

    重试间隔：递增退避 2s, 4s, 6s, ..., 最大 10s
    """
    last_result = None

    for attempt in range(retry_count + 1):  # 0 = 首次执行, 1~N = 重试
        if attempt > 0:
            wait = min(attempt * 2, 10)
            _logger.warning(f"Retry {attempt}/{retry_count} for [{name}] after {wait}s")
            time.sleep(wait)

        # ---- 第 5 步：发送 HTTP 请求 ----
        response = send_request(
            method=method, url=url, headers=headers, body=body, timeout=timeout,
        )

        # 请求异常 → 记录失败并尝试重试
        if response["error"]:
            last_result = {
                "name": name, "passed": False, "response": response,
                "extracts": {}, "db_vars": {}, "validations": [],
                "error": response["error"],
            }
            if attempt < retry_count:
                continue  # 还有重试机会
            return last_result

        # ---- 第 6 步：after hook 响应后处理 ----
        if hook_manager and case.get("hook", {}).get("after"):
            try:
                response = hook_manager.call(case["hook"]["after"], response)
            except Exception as e:
                _logger.error(f"after hook failed: {e}")

        # ---- 第 7 步：extract 提取响应变量 ----
        extracts = {}
        if case.get("extract") and response["body"]:
            extracts = extract_fields(response["body"], case["extract"])
            for k, v in extracts.items():
                # scope: global → 存全局变量池（跨文件可用）
                # scope: module → 存模块变量池（默认，文件内共享）
                if get_extract_scope(case["extract"], k) == "global":
                    pool.set_global(k, v)
                else:
                    pool.set_module(k, v)

        # ---- 第 8 步：db_extract 数据库查询校验 ----
        db_vars = {}
        if db_handler and case.get("db_extract"):
            try:
                db_extract_resolved = pool.resolve(case["db_extract"])
                db_vars = db_handler.execute_extract(db_extract_resolved)
                for k, v in db_vars.items():
                    pool.set_module(k, v)
            except Exception as e:
                _logger.error(f"db_extract failed: {e}")

        # ---- 第 9 步：validate 断言校验 ----
        validations = []
        all_passed = True
        if case.get("validate"):
            extra_vars = {**extracts, **db_vars}
            validations = validate_case(response, case["validate"], extra_vars=extra_vars)
            all_passed = all(v["passed"] for v in validations)

        last_result = {
            "name": name, "passed": all_passed, "response": response,
            "extracts": extracts, "db_vars": db_vars, "validations": validations,
            "error": None,
        }

        # 全部通过 → 无需重试
        if all_passed:
            if attempt > 0:
                _logger.info(f"[{name}] passed on retry {attempt}")
            return last_result

        # 断言失败 → 尝试重试
        if attempt < retry_count:
            continue

    return last_result


def _run_db_teardown(case: dict, pool: VariablePool, db_handler):
    """执行数据库清理操作（即使前面的步骤失败也会执行）。"""
    if db_handler and case.get("db_teardown"):
        try:
            db_teardown_resolved = pool.resolve(case["db_teardown"])
            db_handler.execute_teardown(db_teardown_resolved)
        except Exception as e:
            _logger.error(f"db_teardown failed: {e}")
