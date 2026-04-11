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
