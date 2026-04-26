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


def test_extract_fields_with_scope_format():
    """完整格式 {jsonpath: ..., scope: global} 也能正确提取。"""
    from common.extractor import extract_fields

    response_body = {"code": 0, "data": {"token": "abc", "user_id": 42}}
    extract_config = {
        "token": {"jsonpath": "$.data.token", "scope": "global"},
        "uid": "$.data.user_id",  # 混合简写格式
    }
    result = extract_fields(response_body, extract_config)
    assert result == {"token": "abc", "uid": 42}


def test_get_extract_scope():
    """get_extract_scope 正确返回 scope 配置。"""
    from common.extractor import get_extract_scope

    config = {
        "token": {"jsonpath": "$.data.token", "scope": "global"},
        "uid": "$.data.user_id",
        "name": {"jsonpath": "$.data.name"},  # 无 scope，默认 module
    }
    assert get_extract_scope(config, "token") == "global"
    assert get_extract_scope(config, "uid") == "module"
    assert get_extract_scope(config, "name") == "module"
