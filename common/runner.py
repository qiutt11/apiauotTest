import time
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
    default_retry: int = 0,
) -> dict[str, Any]:
    name = case.get("name", "unnamed")
    # Case-level retry overrides global default
    retry_count = case.get("retry", default_retry)

    # 1. Resolve variables in case data
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

    try:
        # 2. Execute db_setup
        setup_vars = {}
        if db_handler and case.get("db_setup"):
            try:
                resolved_sql_list = []
                for sql_item in case["db_setup"]:
                    resolved_item = pool.resolve(sql_item)
                    resolved_sql_list.append(resolved_item)
                setup_vars = db_handler.execute_setup(resolved_sql_list)
                for k, v in setup_vars.items():
                    pool.set_module(k, v)
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

        # 4. Send request + validate (with retry)
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
        # db_teardown always runs
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
    """Execute request + extract + validate, retry on failure."""
    last_result = None

    for attempt in range(retry_count + 1):
        if attempt > 0:
            wait = min(attempt * 2, 10)  # 2s, 4s, 6s, ..., max 10s
            _logger.warning(
                f"Retry {attempt}/{retry_count} for [{name}] after {wait}s"
            )
            time.sleep(wait)

        # Send HTTP request
        response = send_request(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=timeout,
        )

        # Request error → retry
        if response["error"]:
            last_result = {
                "name": name,
                "passed": False,
                "response": response,
                "extracts": {},
                "db_vars": {},
                "validations": [],
                "error": response["error"],
            }
            if attempt < retry_count:
                continue
            return last_result

        # Execute after hook
        if hook_manager and case.get("hook", {}).get("after"):
            try:
                response = hook_manager.call(case["hook"]["after"], response)
            except Exception as e:
                _logger.error(f"after hook failed: {e}")

        # Extract variables from response
        extracts = {}
        if case.get("extract") and response["body"]:
            extracts = extract_fields(response["body"], case["extract"])
            for k, v in extracts.items():
                pool.set_module(k, v)

        # Execute db_extract
        db_vars = {}
        if db_handler and case.get("db_extract"):
            try:
                db_extract_resolved = pool.resolve(case["db_extract"])
                db_vars = db_handler.execute_extract(db_extract_resolved)
                for k, v in db_vars.items():
                    pool.set_module(k, v)
            except Exception as e:
                _logger.error(f"db_extract failed: {e}")

        # Validate
        validations = []
        all_passed = True
        if case.get("validate"):
            extra_vars = {**extracts, **db_vars}
            validations = validate_case(response, case["validate"], extra_vars=extra_vars)
            all_passed = all(v["passed"] for v in validations)

        last_result = {
            "name": name,
            "passed": all_passed,
            "response": response,
            "extracts": extracts,
            "db_vars": db_vars,
            "validations": validations,
            "error": None,
        }

        # All passed → no retry needed
        if all_passed:
            if attempt > 0:
                _logger.info(f"[{name}] passed on retry {attempt}")
            return last_result

        # Validation failed → retry
        if attempt < retry_count:
            continue

    return last_result


def _run_db_teardown(case: dict, pool: VariablePool, db_handler):
    if db_handler and case.get("db_teardown"):
        try:
            db_teardown_resolved = pool.resolve(case["db_teardown"])
            db_handler.execute_teardown(db_teardown_resolved)
        except Exception as e:
            _logger.error(f"db_teardown failed: {e}")
