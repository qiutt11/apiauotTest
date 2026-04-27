"""YAML 数据驱动用例的端到端集成测试。

验证完整流水线：YAML 数据加载 → 保存 → 提取 ID → 详情 → 路径映射断言。
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_config(tmp_path, base_url="http://mock-api.local"):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "current_env: test\ntimeout: 10\nreport_type: html\n"
        "email:\n  enabled: false\n"
    )
    (config_dir / "test.yaml").write_text(
        f"base_url: {base_url}\n"
        f"global_headers:\n  Content-Type: application/json\n"
        f"global_variables:\n  admin_user: admin\n  admin_pass: '123456'\n"
    )
    return str(config_dir)


class TestYamlDrivenPipeline:

    def test_save_and_verify_nested(self, tmp_path):
        """完整流程：嵌套 body → 保存 → 详情 → 路径映射断言（字段名不同）。"""
        import responses

        responses.start()
        try:
            # Mock: save → detail
            responses.add(responses.POST, "http://mock-api.local/api/user/save",
                          json={"code": 0, "data": {"id": 1001}}, status=200)
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1001",
                          json={"code": 0, "data": {
                              "basicInfo": {"userName": "张三", "userAge": 25},
                              "contactList": [
                                  {"contactType": "phone", "contactValue": "138xxx"},
                              ],
                              "tagNames": ["vip", "new"],
                              "userStatus": 1,
                          }}, status=200)

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_yaml_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            # 测试数据（嵌套结构）
            dataset = {
                "label": "张三",
                "userInfo": {
                    "name": "张三",
                    "age": 25,
                    "contacts": [{"type": "phone", "value": "138xxx"}],
                },
                "tags": ["vip", "new"],
                "status": 1,
            }

            # Step 1: 保存（body = dataset 去掉 label）
            body = {k: v for k, v in dataset.items() if k != "label"}
            save_case = {
                "name": "保存", "method": "POST", "url": "/api/user/save",
                "body": body, "extract": {"id": "$.data.id"},
                "validate": [{"eq": ["$.code", 0]}],
            }
            r1 = run_testcase(save_case, cfg["base_url"], pool, 10, hooks,
                              global_headers=cfg.get("global_headers", {}))
            assert r1["passed"] is True

            # 验证 body 是嵌套结构
            sent_body = json.loads(responses.calls[0].request.body)
            assert sent_body["userInfo"]["name"] == "张三"
            assert sent_body["userInfo"]["contacts"][0]["type"] == "phone"
            assert sent_body["tags"] == ["vip", "new"]

            # Step 2: 详情验证（路径映射）
            mapping = {
                "userInfo.name": "$.data.basicInfo.userName",
                "userInfo.age": "$.data.basicInfo.userAge",
                "userInfo.contacts[].type": "$.data.contactList[].contactType",
                "userInfo.contacts[].value": "$.data.contactList[].contactValue",
                "tags[]": "$.data.tagNames[]",
                "status": "$.data.userStatus",
            }
            yaml_validations = _build_yaml_validations(dataset, mapping)
            detail_case = {
                "name": "详情", "method": "GET",
                "url": f"/api/user/detail/{pool.get('id')}",
                "validate": [{"eq": ["$.code", 0]}] + yaml_validations,
            }
            r2 = run_testcase(detail_case, cfg["base_url"], pool, 10, hooks,
                              global_headers=cfg.get("global_headers", {}))
            assert r2["passed"] is True
            # 1(code) + 2(name,age) + 2(contact type,value) + 2(tags) + 1(status) = 8
            assert len(r2["validations"]) == 8
            assert all(v["passed"] for v in r2["validations"])
        finally:
            responses.stop()
            responses.reset()

    def test_missing_fields_skipped(self, tmp_path):
        """数据集中缺少某些字段时，对应的映射自动跳过。"""
        import responses

        responses.start()
        try:
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1",
                          json={"code": 0, "data": {
                              "basicInfo": {"userName": "王五"},
                              "userStatus": 0,
                          }}, status=200)

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_yaml_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            pool.set_module("id", 1)
            hooks = HookManager(str(tmp_path / "hooks"))

            # 王五没有 contacts、没有 tags
            dataset = {
                "userInfo": {"name": "王五"},
                "status": 0,
            }
            mapping = {
                "userInfo.name": "$.data.basicInfo.userName",
                "userInfo.contacts[].type": "$.data.contactList[].contactType",
                "tags[]": "$.data.tagNames[]",
                "status": "$.data.userStatus",
                "remark": "$.data.remark",
            }
            validations = _build_yaml_validations(dataset, mapping)
            # 只应该生成 name + status = 2 条（contacts/tags/remark 都跳过）
            assert len(validations) == 2

            detail_case = {
                "name": "详情", "method": "GET", "url": "/api/user/detail/${id}",
                "validate": validations,
            }
            r = run_testcase(detail_case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))
            assert r["passed"] is True
        finally:
            responses.stop()
            responses.reset()

    def test_validation_failure_reports_detail(self, tmp_path):
        """详情返回值与数据不匹配时，断言正确报告失败。"""
        import responses

        responses.start()
        try:
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1",
                          json={"code": 0, "data": {
                              "basicInfo": {"userName": "错误名字", "userAge": 99},
                          }}, status=200)

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_yaml_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            pool.set_module("id", 1)
            hooks = HookManager(str(tmp_path / "hooks"))

            dataset = {"userInfo": {"name": "张三", "age": 25}}
            mapping = {
                "userInfo.name": "$.data.basicInfo.userName",
                "userInfo.age": "$.data.basicInfo.userAge",
            }
            validations = _build_yaml_validations(dataset, mapping)
            r = run_testcase(
                {"name": "详情", "method": "GET", "url": "/api/user/detail/${id}",
                 "validate": validations},
                cfg["base_url"], pool, 10, hooks,
                global_headers=cfg.get("global_headers", {}),
            )
            assert r["passed"] is False
            failed = [v for v in r["validations"] if not v["passed"]]
            assert len(failed) == 2
        finally:
            responses.stop()
            responses.reset()
