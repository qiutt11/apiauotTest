"""Validator module – assertion keywords for API response validation."""

import re
from typing import Any

from common.extractor import extract_by_jsonpath


TYPE_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "bool": bool,
}


def _get_value(expression: str, response: dict, extra_vars: dict = None) -> Any:
    """Resolve *expression* to a concrete value.

    Supports:
    - ``"status_code"`` – returns the HTTP status code from *response*.
    - ``"${var}"`` – returns the value of *var* from *extra_vars*.
    - ``"$.xxx"`` – evaluates a JSONPath expression against the response body.
    - Anything else is returned as-is.
    """
    if expression == "status_code":
        return response["status_code"]

    if extra_vars and isinstance(expression, str):
        match = re.fullmatch(r'\$\{(\w+)}', expression)
        if match:
            var_name = match.group(1)
            if var_name in extra_vars:
                return extra_vars[var_name]

    if isinstance(expression, str) and expression.startswith("$."):
        return extract_by_jsonpath(response["body"], expression)

    return expression


def validate_case(
    response: dict,
    validations: list[dict],
    extra_vars: dict = None,
) -> list[dict]:
    """Run all *validations* against *response* and return a list of result dicts."""
    results = []
    for validation in validations:
        for keyword, args in validation.items():
            result = _execute_validation(keyword, args, response, extra_vars)
            results.append(result)
    return results


def _execute_validation(
    keyword: str, args: list, response: dict, extra_vars: dict = None
) -> dict:
    """Execute a single validation keyword and return the result dict."""
    try:
        if keyword == "not_null":
            actual = _get_value(args[0], response, extra_vars)
            passed = actual is not None
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": actual,
                "passed": passed,
            }

        if keyword in ("eq", "neq", "gt", "lt", "gte", "lte", "contains", "length"):
            actual = _get_value(args[0], response, extra_vars)
            expect = args[1]
            if extra_vars and isinstance(expect, str):
                match = re.fullmatch(r'\$\{(\w+)}', expect)
                if match and match.group(1) in extra_vars:
                    expect = extra_vars[match.group(1)]

            if keyword == "eq":
                passed = actual == expect
            elif keyword == "neq":
                passed = actual != expect
            elif keyword in ("gt", "lt", "gte", "lte"):
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

        if keyword == "type":
            actual = _get_value(args[0], response, extra_vars)
            expected_type = TYPE_MAP.get(args[1])
            passed = isinstance(actual, expected_type) if expected_type else False
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": type(actual).__name__,
                "expect": args[1],
                "passed": passed,
            }

        return {"keyword": keyword, "passed": False, "error": f"Unknown keyword: {keyword}"}

    except Exception as e:
        return {"keyword": keyword, "passed": False, "error": str(e)}
