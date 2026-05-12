import pytest

from common.validator import validate_case


def _make_response(status_code, body):
    return {"status_code": status_code, "body": body}


def test_eq_status_code():
    resp = _make_response(200, {"code": 0})
    results = validate_case(resp, [{"eq": ["status_code", 200]}])
    assert all(r["passed"] for r in results)


def test_eq_jsonpath():
    resp = _make_response(200, {"code": 0, "msg": "success"})
    results = validate_case(resp, [{"eq": ["$.code", 0]}])
    assert all(r["passed"] for r in results)


def test_neq():
    resp = _make_response(200, {"code": 0})
    results = validate_case(resp, [{"neq": ["$.code", -1]}])
    assert all(r["passed"] for r in results)


def test_gt():
    resp = _make_response(200, {"data": {"total": 10}})
    results = validate_case(resp, [{"gt": ["$.data.total", 5]}])
    assert all(r["passed"] for r in results)


def test_lt():
    resp = _make_response(200, {"data": {"total": 3}})
    results = validate_case(resp, [{"lt": ["$.data.total", 5]}])
    assert all(r["passed"] for r in results)


def test_gte():
    resp = _make_response(200, {"data": {"total": 5}})
    results = validate_case(resp, [{"gte": ["$.data.total", 5]}])
    assert all(r["passed"] for r in results)


def test_lte():
    resp = _make_response(200, {"data": {"total": 5}})
    results = validate_case(resp, [{"lte": ["$.data.total", 5]}])
    assert all(r["passed"] for r in results)


def test_contains():
    resp = _make_response(200, {"msg": "操作成功"})
    results = validate_case(resp, [{"contains": ["$.msg", "成功"]}])
    assert all(r["passed"] for r in results)


def test_not_null():
    resp = _make_response(200, {"data": {"token": "abc"}})
    results = validate_case(resp, [{"not_null": ["$.data.token"]}])
    assert all(r["passed"] for r in results)


def test_not_null_fails():
    resp = _make_response(200, {"data": {"token": None}})
    results = validate_case(resp, [{"not_null": ["$.data.token"]}])
    assert not results[0]["passed"]


def test_type_int():
    resp = _make_response(200, {"data": {"id": 42}})
    results = validate_case(resp, [{"type": ["$.data.id", "int"]}])
    assert all(r["passed"] for r in results)


def test_type_str():
    resp = _make_response(200, {"data": {"name": "test"}})
    results = validate_case(resp, [{"type": ["$.data.name", "str"]}])
    assert all(r["passed"] for r in results)


def test_length():
    resp = _make_response(200, {"data": {"list": [1, 2, 3]}})
    results = validate_case(resp, [{"length": ["$.data.list", 3]}])
    assert all(r["passed"] for r in results)


def test_multiple_validations():
    resp = _make_response(200, {"code": 0, "msg": "success", "data": {"id": 1}})
    validations = [
        {"eq": ["status_code", 200]},
        {"eq": ["$.code", 0]},
        {"contains": ["$.msg", "success"]},
        {"not_null": ["$.data.id"]},
    ]
    results = validate_case(resp, validations)
    assert len(results) == 4
    assert all(r["passed"] for r in results)


def test_failed_validation_has_detail():
    resp = _make_response(200, {"code": 1})
    results = validate_case(resp, [{"eq": ["$.code", 0]}])
    assert not results[0]["passed"]
    assert "actual" in results[0]
    assert "expect" in results[0]


def test_validate_with_variable_pool_values():
    resp = _make_response(200, {"code": 0})
    results = validate_case(resp, [{"eq": ["$.code", 0]}], extra_vars={"db_status": "pending"})
    assert all(r["passed"] for r in results)


def test_validate_extra_var_reference():
    resp = _make_response(200, {"code": 0})
    results = validate_case(resp, [{"eq": ["${db_status}", "pending"]}], extra_vars={"db_status": "pending"})
    assert all(r["passed"] for r in results)


def test_gt_with_none_actual():
    """Fix #14: gt should not crash when actual is None."""
    resp = _make_response(200, {"data": {}})
    results = validate_case(resp, [{"gt": ["$.data.missing", 0]}])
    assert not results[0]["passed"]


def test_length_with_none():
    """Fix #14: length should not crash on None."""
    resp = _make_response(200, {"data": {"items": None}})
    results = validate_case(resp, [{"length": ["$.data.items", 0]}])
    assert not results[0]["passed"]


def test_length_with_non_sized():
    """Fix #14: length should not crash on int."""
    resp = _make_response(200, {"data": {"count": 5}})
    results = validate_case(resp, [{"length": ["$.data.count", 5]}])
    assert not results[0]["passed"]


# ---------------------------------------------------------------------------
# is_null
# ---------------------------------------------------------------------------
def test_is_null_pass():
    resp = _make_response(200, {"data": {"deletedAt": None}})
    results = validate_case(resp, [{"is_null": ["$.data.deletedAt"]}])
    assert results[0]["passed"]


def test_is_null_fail():
    resp = _make_response(200, {"data": {"deletedAt": "2026-01-01"}})
    results = validate_case(resp, [{"is_null": ["$.data.deletedAt"]}])
    assert not results[0]["passed"]


def test_is_null_missing_field():
    """Missing field via JSONPath returns None, so is_null should pass."""
    resp = _make_response(200, {"data": {}})
    results = validate_case(resp, [{"is_null": ["$.data.missing"]}])
    assert results[0]["passed"]


# ---------------------------------------------------------------------------
# not_empty / is_empty (str, list, dict)
# ---------------------------------------------------------------------------
def test_not_empty_str():
    resp = _make_response(200, {"data": {"name": "hello"}})
    results = validate_case(resp, [{"not_empty": ["$.data.name"]}])
    assert results[0]["passed"]


def test_not_empty_str_fail():
    resp = _make_response(200, {"data": {"name": ""}})
    results = validate_case(resp, [{"not_empty": ["$.data.name"]}])
    assert not results[0]["passed"]


def test_not_empty_list():
    resp = _make_response(200, {"data": {"items": [1, 2]}})
    results = validate_case(resp, [{"not_empty": ["$.data.items"]}])
    assert results[0]["passed"]


def test_not_empty_list_fail():
    resp = _make_response(200, {"data": {"items": []}})
    results = validate_case(resp, [{"not_empty": ["$.data.items"]}])
    assert not results[0]["passed"]


def test_not_empty_dict():
    resp = _make_response(200, {"data": {"info": {"k": "v"}}})
    results = validate_case(resp, [{"not_empty": ["$.data.info"]}])
    assert results[0]["passed"]


def test_not_empty_dict_fail():
    resp = _make_response(200, {"data": {"info": {}}})
    results = validate_case(resp, [{"not_empty": ["$.data.info"]}])
    assert not results[0]["passed"]


def test_not_empty_none():
    resp = _make_response(200, {"data": {"val": None}})
    results = validate_case(resp, [{"not_empty": ["$.data.val"]}])
    assert not results[0]["passed"]


def test_not_empty_int():
    """int has no length, treat as non-empty."""
    resp = _make_response(200, {"data": {"count": 0}})
    results = validate_case(resp, [{"not_empty": ["$.data.count"]}])
    assert results[0]["passed"]


def test_is_empty_str():
    resp = _make_response(200, {"data": {"name": ""}})
    results = validate_case(resp, [{"is_empty": ["$.data.name"]}])
    assert results[0]["passed"]


def test_is_empty_list():
    resp = _make_response(200, {"data": {"items": []}})
    results = validate_case(resp, [{"is_empty": ["$.data.items"]}])
    assert results[0]["passed"]


def test_is_empty_dict():
    resp = _make_response(200, {"data": {"info": {}}})
    results = validate_case(resp, [{"is_empty": ["$.data.info"]}])
    assert results[0]["passed"]


def test_is_empty_none():
    resp = _make_response(200, {"data": {"val": None}})
    results = validate_case(resp, [{"is_empty": ["$.data.val"]}])
    assert results[0]["passed"]


def test_is_empty_fail():
    resp = _make_response(200, {"data": {"items": [1]}})
    results = validate_case(resp, [{"is_empty": ["$.data.items"]}])
    assert not results[0]["passed"]


# ---------------------------------------------------------------------------
# regex
# ---------------------------------------------------------------------------
def test_regex_email():
    resp = _make_response(200, {"data": {"email": "test@example.com"}})
    results = validate_case(resp, [{"regex": ["$.data.email", "email"]}])
    assert results[0]["passed"]


def test_regex_email_fail():
    resp = _make_response(200, {"data": {"email": "not-an-email"}})
    results = validate_case(resp, [{"regex": ["$.data.email", "email"]}])
    assert not results[0]["passed"]


def test_regex_phone():
    resp = _make_response(200, {"data": {"phone": "13812345678"}})
    results = validate_case(resp, [{"regex": ["$.data.phone", "phone"]}])
    assert results[0]["passed"]


def test_regex_phone_fail():
    resp = _make_response(200, {"data": {"phone": "12345"}})
    results = validate_case(resp, [{"regex": ["$.data.phone", "phone"]}])
    assert not results[0]["passed"]


def test_regex_url():
    resp = _make_response(200, {"data": {"url": "https://example.com/path"}})
    results = validate_case(resp, [{"regex": ["$.data.url", "url"]}])
    assert results[0]["passed"]


def test_regex_date():
    resp = _make_response(200, {"data": {"date": "2026-05-12"}})
    results = validate_case(resp, [{"regex": ["$.data.date", "date"]}])
    assert results[0]["passed"]


def test_regex_datetime():
    resp = _make_response(200, {"data": {"dt": "2026-05-12T10:30:00"}})
    results = validate_case(resp, [{"regex": ["$.data.dt", "datetime"]}])
    assert results[0]["passed"]


def test_regex_uuid():
    resp = _make_response(200, {"data": {"id": "550e8400-e29b-41d4-a716-446655440000"}})
    results = validate_case(resp, [{"regex": ["$.data.id", "uuid"]}])
    assert results[0]["passed"]


def test_regex_id_card():
    resp = _make_response(200, {"data": {"id_card": "110101199001011234"}})
    results = validate_case(resp, [{"regex": ["$.data.id_card", "id_card"]}])
    assert results[0]["passed"]


def test_regex_ip():
    resp = _make_response(200, {"data": {"ip": "192.168.1.1"}})
    results = validate_case(resp, [{"regex": ["$.data.ip", "ip"]}])
    assert results[0]["passed"]


def test_regex_custom_pattern():
    """Custom regex pattern (not a built-in alias)."""
    resp = _make_response(200, {"data": {"code": "ABC-1234"}})
    results = validate_case(resp, [{"regex": ["$.data.code", r"^[A-Z]{3}-\d{4}$"]}])
    assert results[0]["passed"]


def test_regex_custom_fail():
    resp = _make_response(200, {"data": {"code": "ab-12"}})
    results = validate_case(resp, [{"regex": ["$.data.code", r"^[A-Z]{3}-\d{4}$"]}])
    assert not results[0]["passed"]


def test_regex_none_value():
    resp = _make_response(200, {"data": {}})
    results = validate_case(resp, [{"regex": ["$.data.missing", "email"]}])
    assert not results[0]["passed"]


def test_regex_integer_pattern():
    resp = _make_response(200, {"data": {"num": "12345"}})
    results = validate_case(resp, [{"regex": ["$.data.num", "integer"]}])
    assert results[0]["passed"]


def test_regex_number_pattern():
    resp = _make_response(200, {"data": {"price": "99.99"}})
    results = validate_case(resp, [{"regex": ["$.data.price", "number"]}])
    assert results[0]["passed"]
