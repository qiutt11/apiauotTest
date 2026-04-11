from typing import Any

from jsonpath_ng.ext import parse


def extract_by_jsonpath(data: dict, expression: str) -> Any:
    try:
        matches = parse(expression).find(data)
        if matches:
            return matches[0].value
        return None
    except Exception:
        return None


def extract_fields(response_body: dict, extract_config: dict[str, str]) -> dict[str, Any]:
    result = {}
    for var_name, jsonpath_expr in extract_config.items():
        result[var_name] = extract_by_jsonpath(response_body, jsonpath_expr)
    return result
