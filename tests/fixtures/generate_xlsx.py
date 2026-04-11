import json
import os
from openpyxl import Workbook

fixtures_dir = os.path.dirname(os.path.abspath(__file__))

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

wb.save(os.path.join(fixtures_dir, "sample.xlsx"))
print("Excel fixture created successfully")
