from typing import Any

from loguru import logger as _logger

from common.request_handler import send_request
from common.extractor import extract_fields
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
) -> dict[str, Any]:
    name = case.get("name", "unnamed")

    # 1. Resolve variables in case data
    resolved = pool.resolve({
        "method": case.get("method", "GET"),
        "url": case.get("url", ""),
        "headers": case.get("headers", {}),
        "body": case.get("body"),
    })

    method = resolved["method"]
    url = base_url + resolved["url"]
    # Merge global_headers (lower priority) with per-case headers (higher priority)
    headers = {**(global_headers or {}), **resolved["headers"]}
    body = resolved["body"]

    try:
        # 2. Execute db_setup
        if db_handler and case.get("db_setup"):
            try:
                db_setup_resolved = pool.resolve(case["db_setup"])
                db_handler.execute_setup(db_setup_resolved)
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

        # 3. Execute before hook
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

        # 4. Send HTTP request
        response = send_request(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
        )

        # Check for request error
        if response["error"]:
            return {
                "name": name,
                "passed": False,
                "response": response,
                "extracts": {},
                "db_vars": {},
                "validations": [],
                "error": response["error"],
            }

        # 5. Execute after hook
        if hook_manager and case.get("hook", {}).get("after"):
            try:
                response = hook_manager.call(case["hook"]["after"], response)
            except Exception as e:
                _logger.error(f"after hook failed: {e}")

        # 6. Extract variables from response
        extracts = {}
        if case.get("extract") and response["body"]:
            extracts = extract_fields(response["body"], case["extract"])
            for k, v in extracts.items():
                pool.set_module(k, v)

        # 7. Execute db_extract
        db_vars = {}
        if db_handler and case.get("db_extract"):
            try:
                db_extract_resolved = pool.resolve(case["db_extract"])
                db_vars = db_handler.execute_extract(db_extract_resolved)
                for k, v in db_vars.items():
                    pool.set_module(k, v)
            except Exception as e:
                _logger.error(f"db_extract failed: {e}")

        # 8. Validate
        validations = []
        all_passed = True
        if case.get("validate"):
            extra_vars = {**extracts, **db_vars}
            validations = validate_case(response, case["validate"], extra_vars=extra_vars)
            all_passed = all(v["passed"] for v in validations)

        return {
            "name": name,
            "passed": all_passed,
            "response": response,
            "extracts": extracts,
            "db_vars": db_vars,
            "validations": validations,
            "error": None,
        }

    finally:
        # 9. db_teardown always runs, even if earlier steps failed
        _run_db_teardown(case, pool, db_handler)


def _run_db_teardown(case: dict, pool: VariablePool, db_handler):
    if db_handler and case.get("db_teardown"):
        try:
            db_teardown_resolved = pool.resolve(case["db_teardown"])
            db_handler.execute_teardown(db_teardown_resolved)
        except Exception as e:
            _logger.error(f"db_teardown failed: {e}")
