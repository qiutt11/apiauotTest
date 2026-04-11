from common.extractor import extract_by_jsonpath


def test_extract_simple_field():
    data = {"code": 0, "data": {"token": "abc123"}}
    result = extract_by_jsonpath(data, "$.data.token")
    assert result == "abc123"


def test_extract_nested_field():
    data = {"data": {"user": {"id": 42, "name": "test"}}}
    result = extract_by_jsonpath(data, "$.data.user.id")
    assert result == 42


def test_extract_array_element():
    data = {"data": {"list": [{"id": 1}, {"id": 2}]}}
    result = extract_by_jsonpath(data, "$.data.list[0].id")
    assert result == 1


def test_extract_not_found():
    data = {"code": 0}
    result = extract_by_jsonpath(data, "$.data.token")
    assert result is None


def test_extract_from_response():
    from common.extractor import extract_fields

    response_body = {"code": 0, "data": {"token": "xyz", "user_id": 99}}
    extract_config = {"token": "$.data.token", "uid": "$.data.user_id"}
    result = extract_fields(response_body, extract_config)
    assert result == {"token": "xyz", "uid": 99}
