from common.variable_pool import VariablePool


def test_set_and_get_global():
    pool = VariablePool()
    pool.set_global("base_url", "https://test.com")
    assert pool.get("base_url") == "https://test.com"


def test_set_and_get_module():
    pool = VariablePool()
    pool.set_module("token", "abc123")
    assert pool.get("token") == "abc123"


def test_set_and_get_temp():
    pool = VariablePool()
    pool.set_temp("override", "temp_value")
    assert pool.get("override") == "temp_value"


def test_priority_temp_over_module():
    pool = VariablePool()
    pool.set_module("var", "module_val")
    pool.set_temp("var", "temp_val")
    assert pool.get("var") == "temp_val"


def test_priority_module_over_global():
    pool = VariablePool()
    pool.set_global("var", "global_val")
    pool.set_module("var", "module_val")
    assert pool.get("var") == "module_val"


def test_resolve_string():
    pool = VariablePool()
    pool.set_module("token", "abc123")
    pool.set_module("user_id", "42")
    result = pool.resolve("Bearer ${token} for user ${user_id}")
    assert result == "Bearer abc123 for user 42"


def test_resolve_dict():
    pool = VariablePool()
    pool.set_module("token", "abc123")
    data = {"Authorization": "Bearer ${token}", "id": "${token}"}
    result = pool.resolve(data)
    assert result == {"Authorization": "Bearer abc123", "id": "abc123"}


def test_resolve_nested_dict():
    pool = VariablePool()
    pool.set_module("name", "test")
    data = {"body": {"username": "${name}"}}
    result = pool.resolve(data)
    assert result == {"body": {"username": "test"}}


def test_resolve_list():
    pool = VariablePool()
    pool.set_module("code", "0")
    data = ["eq", ["$.code", "${code}"]]
    result = pool.resolve(data)
    assert result == ["eq", ["$.code", "0"]]


def test_get_missing_returns_none():
    pool = VariablePool()
    assert pool.get("nonexistent") is None


def test_resolve_unmatched_variable_kept():
    pool = VariablePool()
    result = pool.resolve("${unknown}")
    assert result == "${unknown}"


def test_clear_temp():
    pool = VariablePool()
    pool.set_temp("var", "val")
    pool.clear_temp()
    assert pool.get("var") is None


def test_clear_module():
    pool = VariablePool()
    pool.set_module("var", "val")
    pool.clear_module()
    assert pool.get("var") is None


def test_resolve_single_var_preserves_int():
    """Fix #4: Single ${var} should preserve original type."""
    pool = VariablePool()
    pool.set_module("user_id", 42)
    result = pool.resolve({"id": "${user_id}"})
    assert result["id"] == 42
    assert isinstance(result["id"], int)


def test_resolve_single_var_preserves_none():
    pool = VariablePool()
    pool.set_module("val", None)
    # None variable should keep ${val} as-is (not found behavior)
    result = pool.resolve("${val}")
    assert result == "${val}"


def test_resolve_embedded_var_becomes_string():
    """Embedded ${var} in a larger string should stringify."""
    pool = VariablePool()
    pool.set_module("port", 8080)
    result = pool.resolve("http://localhost:${port}/api")
    assert result == "http://localhost:8080/api"
    assert isinstance(result, str)
