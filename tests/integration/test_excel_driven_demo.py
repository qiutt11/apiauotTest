"""Excel 驱动用例的端到端演示测试。

通过 subprocess 调用 pytest，使用 responses mock HTTP，
验证 Excel 驱动用例在真实 conftest.py 流水线中能正确：
  - 收集用例（每行 Excel 数据生成一个 ExcelDrivenItem）
  - 执行 steps（保存 → 提取 ID → 查看详情）
  - body_from_excel 构建请求 body（直接映射 + field_mapping）
  - validate_from_excel 生成断言（简单值 + 嵌套对象 + 数组）
  - 变量在 step 间传递（save 提取的 id 在 detail 中使用）
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYTHON = sys.executable


def _make_config(tmp_path, base_url="http://mock-api.local"):
    """Create minimal config files in tmp_path."""
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


class TestExcelDrivenDemo:
    """端到端演示：Excel 驱动用例的完整流水线。"""

    def test_basic_save_and_detail(self, tmp_path):
        """示例1：body_from_excel: true + validate_from_excel，两行 Excel 数据。

        流程：
          1. 登录 → 提取 token
          2. Excel 第1行（张三）→ save → detail → 校验所有字段
          3. Excel 第2行（李四）→ save → detail → 校验所有字段
        """
        import responses

        responses.start()
        try:
            # ---- Mock API ----
            # 登录
            responses.add(responses.POST, "http://mock-api.local/api/login",
                          json={"code": 0, "data": {"token": "test-token"}}, status=200)
            # 张三: save → detail
            responses.add(responses.POST, "http://mock-api.local/api/user/save",
                          json={"code": 0, "data": {"id": 1001}}, status=200)
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1001",
                          json={"code": 0, "data": {
                              "name": "张三", "age": 25, "phone": "138xxx",
                              "tags": ["vip", "new"],
                              "address": {"city": "北京", "street": "xx路"},
                          }}, status=200)
            # 李四: save → detail
            responses.add(responses.POST, "http://mock-api.local/api/user/save",
                          json={"code": 0, "data": {"id": 1002}}, status=200)
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1002",
                          json={"code": 0, "data": {
                              "name": "李四", "age": 30, "phone": "139xxx",
                              "tags": ["normal"],
                              "address": {"city": "上海", "street": "yy路"},
                          }}, status=200)

            # ---- 创建 Excel ----
            from openpyxl import Workbook
            data_dir = tmp_path / "testcases" / "user" / "data"
            data_dir.mkdir(parents=True)

            wb = Workbook()
            ws = wb.active
            ws.append(["name", "age", "phone", "tags", "address"])
            ws.append(["张三", 25, "138xxx", '["vip","new"]', '{"city":"北京","street":"xx路"}'])
            ws.append(["李四", 30, "139xxx", '["normal"]', '{"city":"上海","street":"yy路"}'])
            wb.save(str(data_dir / "user_data.xlsx"))

            # ---- 创建 YAML ----
            tc_dir = tmp_path / "testcases" / "user"
            (tc_dir / "demo.yaml").write_text(
                "module: Excel驱动演示\n"
                "testcases:\n"
                "  - name: 登录获取token\n"
                "    method: POST\n"
                "    url: /api/login\n"
                "    body:\n"
                "      username: ${admin_user}\n"
                "      password: ${admin_pass}\n"
                "    extract:\n"
                "      token: $.data.token\n"
                "    validate:\n"
                "      - eq: [$.code, 0]\n"
                "\n"
                "  - name: 保存并验证用户详情\n"
                "    excel_source: data/user_data.xlsx\n"
                "    steps:\n"
                "      - name: 保存用户\n"
                "        method: POST\n"
                "        url: /api/user/save\n"
                "        headers:\n"
                "          Authorization: Bearer ${token}\n"
                "        body_from_excel: true\n"
                "        extract:\n"
                "          id: $.data.id\n"
                "        validate:\n"
                "          - eq: [$.code, 0]\n"
                "\n"
                "      - name: 查看用户详情\n"
                "        method: GET\n"
                "        url: /api/user/detail/${id}\n"
                "        headers:\n"
                "          Authorization: Bearer ${token}\n"
                "        validate_from_excel:\n"
                "          prefix: $.data\n"
                "        validate:\n"
                "          - eq: [$.code, 0]\n"
            )

            # ---- 执行 ----
            config_dir = _make_config(tmp_path)

            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.data_loader import load_testcases, load_excel_rows
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_body_from_excel, _build_excel_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            # Step 0: 登录
            data = load_testcases(str(tc_dir / "demo.yaml"))
            login_case = data["testcases"][0]
            r_login = run_testcase(login_case, cfg["base_url"], pool, 10, hooks,
                                   global_headers=cfg.get("global_headers", {}))
            assert r_login["passed"] is True, f"登录失败: {r_login}"
            assert pool.get("token") == "test-token"

            # Step 1+2: Excel 驱动
            excel_case = data["testcases"][1]
            rows = load_excel_rows(str(data_dir / "user_data.xlsx"))
            assert len(rows) == 2

            for row_data in rows:
                # 注入 Excel 行数据到变量池
                for col, val in row_data.items():
                    pool.set_module(col, val)

                # save
                save_body = _build_body_from_excel(row_data, True)
                save_case = dict(excel_case["steps"][0])
                save_case["body"] = save_body
                r_save = run_testcase(save_case, cfg["base_url"], pool, 10, hooks,
                                      global_headers=cfg.get("global_headers", {}))
                assert r_save["passed"] is True, f"保存失败({row_data['name']}): {r_save}"

                # detail
                detail_validations = _build_excel_validations(row_data, {"prefix": "$.data"})
                detail_case = dict(excel_case["steps"][1])
                detail_case["validate"] = detail_case.get("validate", []) + detail_validations
                r_detail = run_testcase(detail_case, cfg["base_url"], pool, 10, hooks,
                                        global_headers=cfg.get("global_headers", {}))
                assert r_detail["passed"] is True, f"详情校验失败({row_data['name']}): {r_detail}"

            # ---- 验证请求 ----
            # 共 5 次请求：1 登录 + 2×(save+detail)
            assert len(responses.calls) == 5

            # 第1次 save body 应包含张三的数据
            save1_body = json.loads(responses.calls[1].request.body)
            assert save1_body["name"] == "张三"
            assert save1_body["age"] == 25
            assert save1_body["tags"] == ["vip", "new"]
            assert save1_body["address"] == {"city": "北京", "street": "xx路"}

            # 第2次 save body 应包含李四的数据
            save2_body = json.loads(responses.calls[3].request.body)
            assert save2_body["name"] == "李四"
            assert save2_body["age"] == 30

        finally:
            responses.stop()
            responses.reset()

    def test_field_mapping_save_and_detail(self, tmp_path):
        """示例2：field_mapping 映射，Excel 中文列名 → 接口英文字段名。

        Excel 列名：姓名、年龄、手机号
        保存接口字段名：name、age、phone
        详情响应字段名：user_name、user_age、user_phone
        """
        import responses

        responses.start()
        try:
            # Mock API
            responses.add(responses.POST, "http://mock-api.local/api/login",
                          json={"code": 0, "data": {"token": "test-token"}}, status=200)
            responses.add(responses.POST, "http://mock-api.local/api/user/save",
                          json={"code": 0, "data": {"id": 2001}}, status=200)
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/2001",
                          json={"code": 0, "data": {
                              "user_name": "王五", "user_age": 28, "user_phone": "13700003333",
                          }}, status=200)

            # 创建 Excel（中文列名）
            from openpyxl import Workbook
            data_dir = tmp_path / "testcases" / "user" / "data"
            data_dir.mkdir(parents=True)

            wb = Workbook()
            ws = wb.active
            ws.append(["姓名", "年龄", "手机号"])
            ws.append(["王五", 28, "13700003333"])
            wb.save(str(data_dir / "mapping.xlsx"))

            # 执行
            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.data_loader import load_excel_rows
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_body_from_excel, _build_excel_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            for k, v in cfg.get("global_variables", {}).items():
                pool.set_global(k, v)
            hooks = HookManager(str(tmp_path / "hooks"))

            # 登录
            login_case = {
                "name": "登录", "method": "POST", "url": "/api/login",
                "body": {"username": "${admin_user}", "password": "${admin_pass}"},
                "extract": {"token": "$.data.token"},
                "validate": [{"eq": ["$.code", 0]}],
            }
            r_login = run_testcase(login_case, cfg["base_url"], pool, 10, hooks,
                                   global_headers=cfg.get("global_headers", {}))
            assert r_login["passed"] is True

            # 加载 Excel
            rows = load_excel_rows(str(data_dir / "mapping.xlsx"))
            assert len(rows) == 1
            row_data = rows[0]
            # row_data = {"姓名": "王五", "年龄": 28, "手机号": "13700003333"}

            for col, val in row_data.items():
                pool.set_module(col, val)

            # save（用 field_mapping 映射中文列名 → 英文字段名）
            body = _build_body_from_excel(row_data, {
                "field_mapping": {"姓名": "name", "年龄": "age", "手机号": "phone"},
            })
            assert body == {"name": "王五", "age": 28, "phone": "13700003333"}

            save_case = {
                "name": "保存", "method": "POST", "url": "/api/user/save",
                "headers": {"Authorization": "Bearer ${token}"},
                "body": body,
                "extract": {"id": "$.data.id"},
                "validate": [{"eq": ["$.code", 0]}],
            }
            r_save = run_testcase(save_case, cfg["base_url"], pool, 10, hooks,
                                  global_headers=cfg.get("global_headers", {}))
            assert r_save["passed"] is True
            assert pool.get("id") == 2001

            # detail（用另一套 mapping 映射到响应字段名）
            detail_validations = _build_excel_validations(row_data, {
                "prefix": "$.data",
                "field_mapping": {"姓名": "user_name", "年龄": "user_age", "手机号": "user_phone"},
            })
            # 验证生成的断言
            assert {"eq": ["$.data.user_name", "王五"]} in detail_validations
            assert {"eq": ["$.data.user_age", 28]} in detail_validations
            assert {"eq": ["$.data.user_phone", "13700003333"]} in detail_validations

            detail_case = {
                "name": "详情", "method": "GET", "url": "/api/user/detail/${id}",
                "headers": {"Authorization": "Bearer ${token}"},
                "validate": [{"eq": ["$.code", 0]}] + detail_validations,
            }
            r_detail = run_testcase(detail_case, cfg["base_url"], pool, 10, hooks,
                                    global_headers=cfg.get("global_headers", {}))
            assert r_detail["passed"] is True

            # 验证 save 请求的 body
            sent_body = json.loads(responses.calls[1].request.body)
            assert sent_body == {"name": "王五", "age": 28, "phone": "13700003333"}

        finally:
            responses.stop()
            responses.reset()

    def test_detail_mismatch_reports_failure(self, tmp_path):
        """示例3：详情返回值与 Excel 不一致时，断言报错并展示差异。"""
        import responses

        responses.start()
        try:
            # Mock：详情返回「错误」的数据
            responses.add(responses.GET, "http://mock-api.local/api/user/detail/1",
                          json={"code": 0, "data": {
                              "name": "张三改了名", "age": 99,
                          }}, status=200)

            config_dir = _make_config(tmp_path)
            from common.config_loader import load_config
            from common.variable_pool import VariablePool
            from common.runner import run_testcase
            from common.hook_manager import HookManager
            from conftest import _build_excel_validations

            cfg = load_config(config_dir)
            pool = VariablePool()
            pool.set_module("id", 1)
            hooks = HookManager(str(tmp_path / "hooks"))

            # Excel 期望：name=张三, age=25
            row_data = {"name": "张三", "age": 25}
            validations = _build_excel_validations(row_data, {"prefix": "$.data"})

            detail_case = {
                "name": "详情校验应失败",
                "method": "GET",
                "url": "/api/user/detail/${id}",
                "validate": validations,
            }
            r = run_testcase(detail_case, cfg["base_url"], pool, 10, hooks,
                             global_headers=cfg.get("global_headers", {}))

            # 应该失败
            assert r["passed"] is False

            # 检查失败详情
            failed = [v for v in r["validations"] if not v["passed"]]
            assert len(failed) == 2  # name 和 age 都不匹配

            # 失败信息中能看到期望值和实际值
            name_fail = next(v for v in failed if "name" in v.get("expression", ""))
            assert name_fail["actual"] == "张三改了名"
            assert name_fail["expect"] == "张三"

            age_fail = next(v for v in failed if "age" in v.get("expression", ""))
            assert age_fail["actual"] == 99
            assert age_fail["expect"] == 25

        finally:
            responses.stop()
            responses.reset()
