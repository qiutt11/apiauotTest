import json
import os
from typing import Any

import yaml
from openpyxl import load_workbook


def load_testcases(file_path: str) -> dict[str, Any]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".yaml", ".yml"):
        return _load_yaml(file_path)
    elif ext == ".json":
        return _load_json(file_path)
    elif ext == ".xlsx":
        return _load_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def _load_yaml(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_excel(file_path: str) -> dict:
    wb = load_workbook(file_path, read_only=True)
    try:
        ws = wb.active
        module_name = ws.title

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return {"module": module_name, "testcases": []}

        headers = [str(h).strip() for h in rows[0]]
        testcases = []

        for row in rows[1:]:
            case = {}
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else None
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    continue
                if header in ("headers", "body", "extract", "validate",
                              "db_setup", "db_extract", "db_teardown"):
                    case[header] = json.loads(str(value))
                else:
                    case[header] = value
            if case:  # Skip empty rows
                testcases.append(case)

        return {"module": module_name, "testcases": testcases}
    finally:
        wb.close()


def scan_testcase_files(directory: str) -> list[str]:
    valid_extensions = {".yaml", ".yml", ".json", ".xlsx"}
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext in valid_extensions:
                files.append(os.path.join(root, filename))
    return files
