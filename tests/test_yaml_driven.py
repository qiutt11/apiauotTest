"""YAML 数据驱动用例的单元测试。

覆盖范围：
    - load_yaml_datasets()：加载、空文件、非列表
    - _get_by_path()：简单路径、嵌套路径、不存在路径
    - _build_yaml_validations()：简单映射、嵌套映射、数组映射、缺失字段跳过
    - _flatten_value()：dict/list/标量 递归展开
"""

import os
import pytest


# ==========================================================================
# load_yaml_datasets() 测试
# ==========================================================================
class TestLoadYamlDatasets:

    def test_basic_load(self, tmp_path):
        from common.data_loader import load_yaml_datasets

        (tmp_path / "data.yaml").write_text(
            "- label: 张三\n  name: 张三\n  age: 25\n"
            "- label: 李四\n  name: 李四\n  age: 30\n",
            encoding="utf-8",
        )
        result = load_yaml_datasets(str(tmp_path / "data.yaml"))
        assert len(result) == 2
        assert result[0]["label"] == "张三"
        assert result[0]["name"] == "张三"
        assert result[1]["age"] == 30

    def test_nested_data(self, tmp_path):
        from common.data_loader import load_yaml_datasets

        (tmp_path / "data.yaml").write_text(
            "- label: test\n"
            "  userInfo:\n"
            "    name: 张三\n"
            "    contacts:\n"
            "      - type: phone\n"
            "        value: '138xxx'\n",
            encoding="utf-8",
        )
        result = load_yaml_datasets(str(tmp_path / "data.yaml"))
        assert result[0]["userInfo"]["name"] == "张三"
        assert result[0]["userInfo"]["contacts"][0]["type"] == "phone"

    def test_empty_file(self, tmp_path):
        from common.data_loader import load_yaml_datasets

        (tmp_path / "data.yaml").write_text("", encoding="utf-8")
        result = load_yaml_datasets(str(tmp_path / "data.yaml"))
        assert result == []

    def test_non_list_returns_empty(self, tmp_path):
        from common.data_loader import load_yaml_datasets

        (tmp_path / "data.yaml").write_text("key: value\n", encoding="utf-8")
        result = load_yaml_datasets(str(tmp_path / "data.yaml"))
        assert result == []


# ==========================================================================
# _get_by_path() 测试
# ==========================================================================
class TestGetByPath:

    def test_simple_path(self):
        from conftest import _get_by_path
        assert _get_by_path({"name": "张三"}, "name") == "张三"

    def test_nested_path(self):
        from conftest import _get_by_path
        data = {"userInfo": {"name": "张三", "age": 25}}
        assert _get_by_path(data, "userInfo.name") == "张三"
        assert _get_by_path(data, "userInfo.age") == 25

    def test_deep_nested(self):
        from conftest import _get_by_path
        data = {"a": {"b": {"c": {"d": 42}}}}
        assert _get_by_path(data, "a.b.c.d") == 42

    def test_path_not_found(self):
        from conftest import _get_by_path, _MISSING
        assert _get_by_path({"name": "张三"}, "age") is _MISSING

    def test_partial_path_not_found(self):
        from conftest import _get_by_path, _MISSING
        assert _get_by_path({"a": {"b": 1}}, "a.c.d") is _MISSING

    def test_returns_list(self):
        from conftest import _get_by_path
        data = {"tags": ["vip", "new"]}
        assert _get_by_path(data, "tags") == ["vip", "new"]


# ==========================================================================
# _build_yaml_validations() 测试
# ==========================================================================
class TestBuildYamlValidations:

    def test_simple_mapping(self):
        """简单字段映射：status → $.data.userStatus"""
        from conftest import _build_yaml_validations
        dataset = {"status": 1, "label": "test"}
        mapping = {"status": "$.data.userStatus"}
        result = _build_yaml_validations(dataset, mapping)
        assert {"eq": ["$.data.userStatus", 1]} in result

    def test_nested_mapping(self):
        """嵌套字段映射：userInfo.name → $.data.basicInfo.userName"""
        from conftest import _build_yaml_validations
        dataset = {"userInfo": {"name": "张三", "age": 25}}
        mapping = {
            "userInfo.name": "$.data.basicInfo.userName",
            "userInfo.age": "$.data.basicInfo.userAge",
        }
        result = _build_yaml_validations(dataset, mapping)
        assert {"eq": ["$.data.basicInfo.userName", "张三"]} in result
        assert {"eq": ["$.data.basicInfo.userAge", 25]} in result

    def test_array_mapping(self):
        """数组映射：tags[] → $.data.tagNames[]"""
        from conftest import _build_yaml_validations
        dataset = {"tags": ["vip", "new"]}
        mapping = {"tags[]": "$.data.tagNames[]"}
        result = _build_yaml_validations(dataset, mapping)
        assert {"eq": ["$.data.tagNames[0]", "vip"]} in result
        assert {"eq": ["$.data.tagNames[1]", "new"]} in result

    def test_array_object_mapping(self):
        """数组内对象映射：contacts[].type → $.data.contactList[].contactType"""
        from conftest import _build_yaml_validations
        dataset = {
            "userInfo": {
                "contacts": [
                    {"type": "phone", "value": "138xxx"},
                    {"type": "email", "value": "zs@test.com"},
                ]
            }
        }
        mapping = {
            "userInfo.contacts[].type": "$.data.contactList[].contactType",
            "userInfo.contacts[].value": "$.data.contactList[].contactValue",
        }
        result = _build_yaml_validations(dataset, mapping)
        assert {"eq": ["$.data.contactList[0].contactType", "phone"]} in result
        assert {"eq": ["$.data.contactList[0].contactValue", "138xxx"]} in result
        assert {"eq": ["$.data.contactList[1].contactType", "email"]} in result
        assert {"eq": ["$.data.contactList[1].contactValue", "zs@test.com"]} in result

    def test_missing_field_skipped(self):
        """数据中不存在的字段自动跳过，不报错。"""
        from conftest import _build_yaml_validations
        dataset = {"name": "张三"}
        mapping = {
            "name": "$.data.userName",
            "remark": "$.data.remark",  # dataset 中没有 remark
        }
        result = _build_yaml_validations(dataset, mapping)
        assert len(result) == 1
        assert {"eq": ["$.data.userName", "张三"]} in result

    def test_missing_array_skipped(self):
        """数据中不存在的数组字段自动跳过。"""
        from conftest import _build_yaml_validations
        dataset = {"name": "张三"}
        mapping = {
            "name": "$.data.userName",
            "contacts[].type": "$.data.contactList[].contactType",
        }
        result = _build_yaml_validations(dataset, mapping)
        assert len(result) == 1

    def test_complex_mixed(self):
        """复杂场景：混合简单字段、嵌套字段、数组。"""
        from conftest import _build_yaml_validations
        dataset = {
            "label": "张三-完整",
            "userInfo": {"name": "张三", "age": 25},
            "tags": ["vip", "new"],
            "status": 1,
        }
        mapping = {
            "userInfo.name": "$.data.basicInfo.userName",
            "userInfo.age": "$.data.basicInfo.userAge",
            "tags[]": "$.data.tagNames[]",
            "status": "$.data.userStatus",
        }
        result = _build_yaml_validations(dataset, mapping)
        assert len(result) == 5  # name + age + tags[0] + tags[1] + status
        assert {"eq": ["$.data.basicInfo.userName", "张三"]} in result
        assert {"eq": ["$.data.tagNames[0]", "vip"]} in result
        assert {"eq": ["$.data.userStatus", 1]} in result


# ==========================================================================
# _flatten_value() 测试
# ==========================================================================
class TestFlattenValue:

    def test_scalar(self):
        from conftest import _flatten_value
        result = []
        _flatten_value("$.data.name", "张三", result)
        assert result == [{"eq": ["$.data.name", "张三"]}]

    def test_dict(self):
        from conftest import _flatten_value
        result = []
        _flatten_value("$.data.addr", {"city": "北京", "street": "xx路"}, result)
        assert {"eq": ["$.data.addr.city", "北京"]} in result
        assert {"eq": ["$.data.addr.street", "xx路"]} in result

    def test_list(self):
        from conftest import _flatten_value
        result = []
        _flatten_value("$.data.tags", ["vip", "new"], result)
        assert result == [
            {"eq": ["$.data.tags[0]", "vip"]},
            {"eq": ["$.data.tags[1]", "new"]},
        ]

    def test_nested(self):
        from conftest import _flatten_value
        result = []
        _flatten_value("$.data", {"items": [{"id": 1}]}, result)
        assert {"eq": ["$.data.items[0].id", 1]} in result
