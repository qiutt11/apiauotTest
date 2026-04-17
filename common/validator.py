"""断言校验模块。

提供 10 个断言关键字，用于验证 API 响应是否符合预期：
    eq / neq / gt / lt / gte / lte / contains / not_null / type / length

支持的表达式类型：
    - "status_code"    → HTTP 状态码
    - "$.xxx"          → JSONPath 表达式（从响应 body 提取）
    - "${var}"         → 变量引用（从 extra_vars 中查找）
    - 其他             → 原值返回

示例 YAML：
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - not_null: [$.data.token]
      - gt: [$.data.total, 0]
      - type: [$.data.id, int]
"""

import re
from typing import Any

from common.extractor import extract_by_jsonpath

# type 关键字支持的类型名 → Python 类型映射
TYPE_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "bool": bool,
}


def _get_value(expression: str, response: dict, extra_vars: dict = None) -> Any:
    """将表达式解析为实际值。

    解析优先级：
    1. "status_code" → 直接返回 HTTP 状态码
    2. "${var}" → 从 extra_vars 中查找
    3. "$.xxx" → JSONPath 提取
    4. 其他 → 原值返回

    Args:
        expression: 表达式字符串
        response: 标准响应字典 {"status_code": ..., "body": ...}
        extra_vars: 额外变量（来自 extract / db_extract）

    Returns:
        解析后的实际值
    """
    # HTTP 状态码
    if expression == "status_code":
        return response["status_code"]

    # ${var} 变量引用
    if extra_vars and isinstance(expression, str):
        match = re.fullmatch(r'\$\{(\w+)}', expression)
        if match:
            var_name = match.group(1)
            if var_name in extra_vars:
                return extra_vars[var_name]

    # JSONPath 表达式
    if isinstance(expression, str) and expression.startswith("$."):
        return extract_by_jsonpath(response["body"], expression)

    # 原值返回
    return expression


def validate_case(
    response: dict,
    validations: list[dict],
    extra_vars: dict = None,
) -> list[dict]:
    """执行一个用例的所有断言，返回结果列表。

    Args:
        response: 标准响应字典
        validations: 断言列表，如 [{"eq": ["$.code", 0]}, {"not_null": ["$.data.token"]}]
        extra_vars: 额外变量字典（可选）

    Returns:
        结果列表，每项包含 keyword, expression, actual, expect, passed 等字段
    """
    results = []
    for validation in validations:
        for keyword, args in validation.items():
            result = _execute_validation(keyword, args, response, extra_vars)
            results.append(result)
    return results


def _execute_validation(
    keyword: str, args: list, response: dict, extra_vars: dict = None
) -> dict:
    """执行单个断言关键字。

    Args:
        keyword: 断言关键字（eq/neq/gt/lt/gte/lte/contains/not_null/type/length）
        args: 参数列表，如 ["$.code", 0] 或 ["$.data.token"]
        response: 标准响应字典
        extra_vars: 额外变量字典（可选）

    Returns:
        结果字典：{"keyword": ..., "expression": ..., "actual": ..., "expect": ..., "passed": bool}
    """
    try:
        # ---------- not_null: 检查值不为 None ----------
        if keyword == "not_null":
            actual = _get_value(args[0], response, extra_vars)
            passed = actual is not None
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": actual,
                "passed": passed,
            }

        # ---------- 比较类断言 ----------
        if keyword in ("eq", "neq", "gt", "lt", "gte", "lte", "contains", "length"):
            actual = _get_value(args[0], response, extra_vars)
            expect = args[1]

            # 期望值也可能是 ${var} 引用
            if extra_vars and isinstance(expect, str):
                match = re.fullmatch(r'\$\{(\w+)}', expect)
                if match and match.group(1) in extra_vars:
                    expect = extra_vars[match.group(1)]

            # 执行比较
            if keyword == "eq":
                passed = actual == expect
            elif keyword == "neq":
                passed = actual != expect
            elif keyword in ("gt", "lt", "gte", "lte"):
                # None 值无法比较，直接判定失败
                if actual is None or expect is None:
                    passed = False
                elif keyword == "gt":
                    passed = actual > expect
                elif keyword == "lt":
                    passed = actual < expect
                elif keyword == "gte":
                    passed = actual >= expect
                elif keyword == "lte":
                    passed = actual <= expect
            elif keyword == "contains":
                passed = str(expect) in str(actual)
            elif keyword == "length":
                # 非可迭代类型（None、int 等）直接判定失败
                passed = len(actual) == expect if actual is not None and hasattr(actual, '__len__') else False
            else:
                passed = False

            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": actual,
                "expect": expect,
                "passed": passed,
            }

        # ---------- type: 类型校验 ----------
        if keyword == "type":
            actual = _get_value(args[0], response, extra_vars)
            expected_type = TYPE_MAP.get(args[1])  # "int" → int
            passed = isinstance(actual, expected_type) if expected_type else False
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": type(actual).__name__,
                "expect": args[1],
                "passed": passed,
            }

        # ---------- 未知关键字 ----------
        return {"keyword": keyword, "passed": False, "error": f"Unknown keyword: {keyword}"}

    except Exception as e:
        # 任何异常都不向上抛出，返回失败结果
        return {"keyword": keyword, "passed": False, "error": str(e)}
