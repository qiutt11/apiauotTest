"""JSONPath 提取模块。

从 API 响应的 JSON body 中，通过 JSONPath 表达式提取指定字段的值。

示例：
    data = {"code": 0, "data": {"token": "abc123"}}
    extract_by_jsonpath(data, "$.data.token")  → "abc123"

常用 JSONPath 语法：
    $.code              → 根级 code 字段
    $.data.token        → 嵌套字段
    $.data.list[0].id   → 数组第一个元素的 id
"""

from typing import Any

from jsonpath_ng.ext import parse


def extract_by_jsonpath(data: dict, expression: str) -> Any:
    """通过 JSONPath 表达式从字典中提取值。

    Args:
        data: 要提取的字典（通常是 API 响应 body）
        expression: JSONPath 表达式（如 "$.data.token"）

    Returns:
        匹配到的第一个值，未匹配到返回 None
    """
    try:
        matches = parse(expression).find(data)
        if matches:
            return matches[0].value
        return None
    except Exception:
        return None


def extract_fields(response_body: dict, extract_config: dict[str, str]) -> dict[str, Any]:
    """批量提取多个字段。

    支持两种配置格式：
        1. 简写：{变量名: JSONPath表达式}
           示例：{"token": "$.data.token"}
        2. 完整：{变量名: {"jsonpath": JSONPath表达式, "scope": "global"}}
           示例：{"token": {"jsonpath": "$.data.token", "scope": "global"}}

    Args:
        response_body: API 响应 body
        extract_config: 提取配置

    Returns:
        提取结果字典，格式为 {变量名: 提取到的值}
    """
    result = {}
    for var_name, config in extract_config.items():
        # 完整格式：{"jsonpath": "$.data.token", "scope": "global"}
        if isinstance(config, dict):
            jsonpath_expr = config.get("jsonpath", "")
        else:
            # 简写格式：直接是 JSONPath 字符串
            jsonpath_expr = config
        result[var_name] = extract_by_jsonpath(response_body, jsonpath_expr)
    return result


def get_extract_scope(extract_config: dict, var_name: str) -> str:
    """获取指定变量的 scope 配置。

    Args:
        extract_config: 原始 extract 配置
        var_name: 变量名

    Returns:
        "global" 或 "module"（默认）
    """
    config = extract_config.get(var_name)
    if isinstance(config, dict):
        return config.get("scope", "module")
    return "module"
