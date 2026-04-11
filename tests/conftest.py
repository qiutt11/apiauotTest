import json
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def generate_excel_fixture():
    """Generate sample.xlsx fixture before tests run."""
    from openpyxl import Workbook

    fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    xlsx_path = os.path.join(fixtures_dir, "sample.xlsx")

    if not os.path.exists(xlsx_path):
        os.makedirs(fixtures_dir, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "测试模块"

        headers = ["name", "method", "url", "headers", "body", "extract", "validate"]
        ws.append(headers)
        ws.append([
            "测试用例1", "GET", "/api/test", "", "", "",
            json.dumps([{"eq": ["status_code", 200]}], ensure_ascii=False)
        ])
        ws.append([
            "测试用例2", "POST", "/api/test", "",
            json.dumps({"key": "value"}, ensure_ascii=False), "",
            json.dumps([{"eq": ["$.code", 0]}], ensure_ascii=False)
        ])

        wb.save(xlsx_path)
