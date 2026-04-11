# API 接口自动化测试框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data-driven API automation testing framework where users write only YAML/JSON/Excel data files to define and run tests — no Python code required.

**Architecture:** A pytest-based engine reads test case data files, resolves variable dependencies (from API responses and database queries), executes HTTP requests, validates responses, and generates reports. Core modules (data_loader, request_handler, variable_pool, validator, extractor, db_handler) are loosely coupled and communicate through a shared variable pool.

**Tech Stack:** Python 3.10+, pytest, requests, PyYAML, openpyxl, jsonpath-ng, allure-pytest, pytest-html, loguru, PyMySQL

---

## File Structure

### New Files to Create

| File | Responsibility |
|------|----------------|
| `common/__init__.py` | Package init |
| `common/logger.py` | Configure loguru, console + file output |
| `common/variable_pool.py` | Three-tier variable storage and `${xxx}` resolution |
| `common/data_loader.py` | Load test cases from YAML, JSON, Excel |
| `common/extractor.py` | Extract values from JSON responses via JSONPath |
| `common/validator.py` | Execute assertion keywords (eq, neq, gt, contains, etc.) |
| `common/request_handler.py` | Send HTTP requests via requests library |
| `common/db_handler.py` | Database operations (setup, extract, teardown) |
| `common/hook_manager.py` | Load and invoke user-defined hook functions |
| `common/notifier.py` | Send email notifications with test summary |
| `config/config.yaml` | Main config (env, timeout, email settings) |
| `config/test.yaml` | Test environment config (base_url, db, variables) |
| `conftest.py` | pytest integration: collect data files, generate test items |
| `run.py` | CLI entry point with argparse |
| `pytest.ini` | pytest configuration |
| `requirements.txt` | Python dependencies |
| `hooks/__init__.py` | Hooks package init |
| `hooks/custom_hooks.py` | Example hook functions |
| `Jenkinsfile` | Jenkins pipeline config |
| `.gitlab-ci.yml` | GitLab CI config |
| `tests/test_variable_pool.py` | Unit tests for variable_pool |
| `tests/test_data_loader.py` | Unit tests for data_loader |
| `tests/test_extractor.py` | Unit tests for extractor |
| `tests/test_validator.py` | Unit tests for validator |
| `tests/test_request_handler.py` | Unit tests for request_handler |
| `tests/test_db_handler.py` | Unit tests for db_handler |
| `tests/test_hook_manager.py` | Unit tests for hook_manager |
| `testcases/login/login.yaml` | Example: login test cases |
| `testcases/user/user_crud.yaml` | Example: user CRUD with dependencies |

---

### Task 1: Project Scaffolding and Logger

**Files:**
- Create: `requirements.txt`
- Create: `common/__init__.py`
- Create: `common/logger.py`
- Create: `pytest.ini`
- Create: `hooks/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
requests>=2.28.0
pytest>=7.0.0
pyyaml>=6.0
jsonpath-ng>=1.5.0
openpyxl>=3.0.0
allure-pytest>=2.12.0
pytest-html>=3.2.0
loguru>=0.7.0
pymysql>=1.1.0
```

- [ ] **Step 2: Install dependencies**

Run: `cd /Volumes/MySpace/autotest && pip install -r requirements.txt`
Expected: All packages installed successfully

- [ ] **Step 3: Create package init files**

`common/__init__.py`:
```python
```

`hooks/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 4: Create pytest.ini**

```ini
[pytest]
testpaths = .
python_files = conftest.py
python_classes =
python_functions =
addopts = -v --tb=short
markers =
    smoke: Smoke tests
    regression: Regression tests
```

- [ ] **Step 5: Write the failing test for logger**

`tests/test_logger.py`:
```python
import os
import re


def test_logger_creates_log_file(tmp_path):
    from common.logger import setup_logger

    log_dir = str(tmp_path / "logs")
    logger = setup_logger(log_dir=log_dir)
    logger.info("test message")

    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "test message" in content


def test_logger_formats_request(tmp_path):
    from common.logger import setup_logger, log_request

    log_dir = str(tmp_path / "logs")
    logger = setup_logger(log_dir=log_dir)
    log_request(
        logger=logger,
        module="用户登录",
        name="登录成功",
        method="POST",
        url="https://test.com/api/login",
        headers={"Content-Type": "application/json"},
        body={"username": "admin"},
        status_code=200,
        elapsed_ms=128,
        response={"code": 0},
    )

    log_files = os.listdir(log_dir)
    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "用户登录" in content
    assert "登录成功" in content
    assert "POST" in content
    assert "200" in content
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_logger.py -v`
Expected: FAIL — ModuleNotFoundError: No module named 'common.logger'

- [ ] **Step 7: Implement common/logger.py**

```python
import os
from datetime import datetime

from loguru import logger as _loguru_logger


def setup_logger(log_dir: str = "logs") -> _loguru_logger.__class__:
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    _loguru_logger.remove()
    _loguru_logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        encoding="utf-8",
        rotation="1 day",
        retention="7 days",
    )
    _loguru_logger.add(
        lambda msg: print(msg, end=""),
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        colorize=True,
    )
    return _loguru_logger


def log_request(
    logger,
    module: str,
    name: str,
    method: str,
    url: str,
    headers: dict = None,
    body: dict = None,
    status_code: int = None,
    elapsed_ms: float = None,
    response: dict = None,
    extracts: dict = None,
    validations: list = None,
):
    logger.info(f"{'=' * 10} {module} > {name} {'=' * 10}")
    logger.info(f"→ {method} {url}")
    if headers:
        logger.info(f"→ Headers: {headers}")
    if body:
        logger.info(f"→ Body: {body}")
    if status_code is not None:
        logger.info(f"← Status: {status_code} | Time: {elapsed_ms}ms")
    if response is not None:
        logger.info(f"← Response: {response}")
    if extracts:
        for k, v in extracts.items():
            logger.info(f"✓ Extract: {k} = {v}")
    if validations:
        for v in validations:
            logger.info(f"✓ Validate: {v}")
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_logger.py -v`
Expected: 2 passed

- [ ] **Step 9: Commit**

```bash
git init && git add requirements.txt pytest.ini common/__init__.py common/logger.py hooks/__init__.py tests/__init__.py tests/test_logger.py
git commit -m "feat: project scaffolding and logger module"
```

---

### Task 2: Variable Pool

**Files:**
- Create: `common/variable_pool.py`
- Create: `tests/test_variable_pool.py`

- [ ] **Step 1: Write the failing test**

`tests/test_variable_pool.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_variable_pool.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/variable_pool.py**

```python
import re
from typing import Any


class VariablePool:
    def __init__(self):
        self._global: dict[str, Any] = {}
        self._module: dict[str, Any] = {}
        self._temp: dict[str, Any] = {}

    def set_global(self, key: str, value: Any):
        self._global[key] = value

    def set_module(self, key: str, value: Any):
        self._module[key] = value

    def set_temp(self, key: str, value: Any):
        self._temp[key] = value

    def get(self, key: str) -> Any:
        if key in self._temp:
            return self._temp[key]
        if key in self._module:
            return self._module[key]
        if key in self._global:
            return self._global[key]
        return None

    def resolve(self, data: Any) -> Any:
        if isinstance(data, str):
            return self._resolve_string(data)
        if isinstance(data, dict):
            return {k: self.resolve(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.resolve(item) for item in data]
        return data

    def _resolve_string(self, text: str) -> str:
        def replacer(match):
            key = match.group(1)
            value = self.get(key)
            if value is None:
                return match.group(0)
            return str(value)
        return re.sub(r'\$\{(\w+)}', replacer, text)

    def clear_temp(self):
        self._temp.clear()

    def clear_module(self):
        self._module.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_variable_pool.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add common/variable_pool.py tests/test_variable_pool.py
git commit -m "feat: variable pool with three-tier priority and resolve"
```

---

### Task 3: Data Loader (YAML, JSON, Excel)

**Files:**
- Create: `common/data_loader.py`
- Create: `tests/test_data_loader.py`
- Create: `tests/fixtures/sample.yaml`
- Create: `tests/fixtures/sample.json`
- Create: `tests/fixtures/sample.xlsx`

- [ ] **Step 1: Create test fixture files**

`tests/fixtures/sample.yaml`:
```yaml
module: 测试模块
testcases:
  - name: 测试用例1
    method: GET
    url: /api/test
    validate:
      - eq: [status_code, 200]
  - name: 测试用例2
    method: POST
    url: /api/test
    body:
      key: value
    validate:
      - eq: [$.code, 0]
```

`tests/fixtures/sample.json`:
```json
{
  "module": "测试模块",
  "testcases": [
    {
      "name": "测试用例1",
      "method": "GET",
      "url": "/api/test",
      "validate": [{"eq": ["status_code", 200]}]
    },
    {
      "name": "测试用例2",
      "method": "POST",
      "url": "/api/test",
      "body": {"key": "value"},
      "validate": [{"eq": ["$.code", 0]}]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_data_loader.py`:
```python
import os
import json

import pytest


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_load_yaml():
    from common.data_loader import load_testcases

    result = load_testcases(os.path.join(FIXTURES_DIR, "sample.yaml"))
    assert result["module"] == "测试模块"
    assert len(result["testcases"]) == 2
    assert result["testcases"][0]["name"] == "测试用例1"
    assert result["testcases"][0]["method"] == "GET"


def test_load_json():
    from common.data_loader import load_testcases

    result = load_testcases(os.path.join(FIXTURES_DIR, "sample.json"))
    assert result["module"] == "测试模块"
    assert len(result["testcases"]) == 2
    assert result["testcases"][1]["body"] == {"key": "value"}


def test_load_excel():
    from common.data_loader import load_testcases

    result = load_testcases(os.path.join(FIXTURES_DIR, "sample.xlsx"))
    assert result["module"] == "测试模块"
    assert len(result["testcases"]) == 2
    assert result["testcases"][0]["name"] == "测试用例1"
    assert result["testcases"][0]["method"] == "GET"
    assert result["testcases"][1]["body"] == {"key": "value"}


def test_load_unsupported_format():
    from common.data_loader import load_testcases

    with pytest.raises(ValueError, match="Unsupported file format"):
        load_testcases("test.txt")


def test_scan_directory(tmp_path):
    from common.data_loader import scan_testcase_files

    sub = tmp_path / "login"
    sub.mkdir()
    (sub / "login.yaml").write_text("module: login\ntestcases: []")
    (sub / "login.json").write_text('{"module":"login","testcases":[]}')
    (tmp_path / "other.txt").write_text("ignore")

    files = scan_testcase_files(str(tmp_path))
    extensions = {os.path.splitext(f)[1] for f in files}
    assert extensions <= {".yaml", ".yml", ".json", ".xlsx"}
    assert len(files) == 2
```

- [ ] **Step 3: Create Excel test fixture programmatically**

`tests/create_excel_fixture.py` (run once to generate the xlsx):
```python
import json
import os

from openpyxl import Workbook

fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
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

wb.save(os.path.join(fixtures_dir, "sample.xlsx"))
print("Created sample.xlsx")
```

Run: `cd /Volumes/MySpace/autotest && python tests/create_excel_fixture.py`

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_data_loader.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 5: Implement common/data_loader.py**

```python
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
        testcases.append(case)

    wb.close()
    return {"module": module_name, "testcases": testcases}


def scan_testcase_files(directory: str) -> list[str]:
    valid_extensions = {".yaml", ".yml", ".json", ".xlsx"}
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in sorted(filenames):
            ext = os.path.splitext(filename)[1].lower()
            if ext in valid_extensions:
                files.append(os.path.join(root, filename))
    return files
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_data_loader.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add common/data_loader.py tests/test_data_loader.py tests/fixtures/ tests/create_excel_fixture.py
git commit -m "feat: data loader supporting YAML, JSON, and Excel formats"
```

---

### Task 4: Extractor (JSONPath)

**Files:**
- Create: `common/extractor.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Write the failing test**

`tests/test_extractor.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_extractor.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/extractor.py**

```python
from typing import Any

from jsonpath_ng.ext import parse


def extract_by_jsonpath(data: dict, expression: str) -> Any:
    try:
        matches = parse(expression).find(data)
        if matches:
            return matches[0].value
        return None
    except Exception:
        return None


def extract_fields(response_body: dict, extract_config: dict[str, str]) -> dict[str, Any]:
    result = {}
    for var_name, jsonpath_expr in extract_config.items():
        result[var_name] = extract_by_jsonpath(response_body, jsonpath_expr)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_extractor.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add common/extractor.py tests/test_extractor.py
git commit -m "feat: JSONPath extractor for response data extraction"
```

---

### Task 5: Validator (Assertion Keywords)

**Files:**
- Create: `common/validator.py`
- Create: `tests/test_validator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_validator.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_validator.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/validator.py**

```python
import re
from typing import Any

from common.extractor import extract_by_jsonpath


TYPE_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "bool": bool,
}


def _get_value(expression: str, response: dict, extra_vars: dict = None) -> Any:
    if expression == "status_code":
        return response["status_code"]

    # Check for ${var} references to extra_vars
    if extra_vars and isinstance(expression, str):
        match = re.fullmatch(r'\$\{(\w+)}', expression)
        if match:
            var_name = match.group(1)
            if var_name in extra_vars:
                return extra_vars[var_name]

    if isinstance(expression, str) and expression.startswith("$."):
        return extract_by_jsonpath(response["body"], expression)

    return expression


def validate_case(
    response: dict,
    validations: list[dict],
    extra_vars: dict = None,
) -> list[dict]:
    results = []
    for validation in validations:
        for keyword, args in validation.items():
            result = _execute_validation(keyword, args, response, extra_vars)
            results.append(result)
    return results


def _execute_validation(
    keyword: str, args: list, response: dict, extra_vars: dict = None
) -> dict:
    try:
        if keyword == "not_null":
            actual = _get_value(args[0], response, extra_vars)
            passed = actual is not None
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": actual,
                "passed": passed,
            }

        if keyword in ("eq", "neq", "gt", "lt", "gte", "lte", "contains", "length"):
            actual = _get_value(args[0], response, extra_vars)
            expect = args[1]
            # Resolve expect if it's a variable reference
            if extra_vars and isinstance(expect, str):
                match = re.fullmatch(r'\$\{(\w+)}', expect)
                if match and match.group(1) in extra_vars:
                    expect = extra_vars[match.group(1)]

            if keyword == "eq":
                passed = actual == expect
            elif keyword == "neq":
                passed = actual != expect
            elif keyword == "gt":
                passed = actual > expect
            elif keyword == "lt":
                passed = actual < expect
            elif keyword == "gte":
                passed = actual >= expect
            elif keyword == "lte":
                passed = actual <= expect
            elif keyword == "contains":
                passed = str(expect) in str(actual)
            elif keyword == "length":
                passed = len(actual) == expect

            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": actual,
                "expect": expect,
                "passed": passed,
            }

        if keyword == "type":
            actual = _get_value(args[0], response, extra_vars)
            expected_type = TYPE_MAP.get(args[1])
            passed = isinstance(actual, expected_type) if expected_type else False
            return {
                "keyword": keyword,
                "expression": args[0],
                "actual": type(actual).__name__,
                "expect": args[1],
                "passed": passed,
            }

        return {"keyword": keyword, "passed": False, "error": f"Unknown keyword: {keyword}"}

    except Exception as e:
        return {"keyword": keyword, "passed": False, "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_validator.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add common/validator.py tests/test_validator.py
git commit -m "feat: validator with 10 assertion keywords"
```

---

### Task 6: Request Handler

**Files:**
- Create: `common/request_handler.py`
- Create: `tests/test_request_handler.py`

- [ ] **Step 1: Write the failing test**

`tests/test_request_handler.py`:
```python
import json
from unittest.mock import patch, MagicMock

from common.request_handler import send_request


def _mock_response(status_code=200, body=None, elapsed_ms=50):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body or {}
    mock_resp.text = json.dumps(body or {})
    mock_resp.elapsed.total_seconds.return_value = elapsed_ms / 1000
    mock_resp.headers = {"Content-Type": "application/json"}
    return mock_resp


@patch("common.request_handler.requests.request")
def test_send_get_request(mock_request):
    mock_request.return_value = _mock_response(200, {"code": 0})

    result = send_request(
        method="GET",
        url="https://test.com/api/users",
        timeout=30,
    )

    assert result["status_code"] == 200
    assert result["body"] == {"code": 0}
    assert "elapsed_ms" in result
    mock_request.assert_called_once()


@patch("common.request_handler.requests.request")
def test_send_post_request_with_body(mock_request):
    mock_request.return_value = _mock_response(200, {"code": 0, "data": {"id": 1}})

    result = send_request(
        method="POST",
        url="https://test.com/api/users",
        headers={"Content-Type": "application/json"},
        body={"username": "test"},
        timeout=30,
    )

    assert result["status_code"] == 200
    assert result["body"]["data"]["id"] == 1
    call_kwargs = mock_request.call_args
    assert call_kwargs[1]["json"] == {"username": "test"}


@patch("common.request_handler.requests.request")
def test_send_request_with_headers(mock_request):
    mock_request.return_value = _mock_response(200, {})

    send_request(
        method="GET",
        url="https://test.com/api/test",
        headers={"Authorization": "Bearer abc"},
        timeout=30,
    )

    call_kwargs = mock_request.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer abc"


@patch("common.request_handler.requests.request")
def test_send_request_timeout(mock_request):
    import requests as req_lib
    mock_request.side_effect = req_lib.exceptions.Timeout("Connection timed out")

    result = send_request(
        method="GET",
        url="https://test.com/api/slow",
        timeout=5,
    )

    assert result["status_code"] is None
    assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()


@patch("common.request_handler.requests.request")
def test_send_request_connection_error(mock_request):
    import requests as req_lib
    mock_request.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

    result = send_request(
        method="GET",
        url="https://test.com/api/down",
        timeout=5,
    )

    assert result["status_code"] is None
    assert result["error"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_request_handler.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/request_handler.py**

```python
from typing import Any

import requests


def send_request(
    method: str,
    url: str,
    headers: dict = None,
    body: dict = None,
    timeout: int = 30,
) -> dict[str, Any]:
    try:
        kwargs = {
            "method": method.upper(),
            "url": url,
            "headers": headers or {},
            "timeout": timeout,
        }
        if body is not None:
            kwargs["json"] = body

        resp = requests.request(**kwargs)
        elapsed_ms = round(resp.elapsed.total_seconds() * 1000, 2)

        try:
            body_json = resp.json()
        except Exception:
            body_json = resp.text

        return {
            "status_code": resp.status_code,
            "body": body_json,
            "headers": dict(resp.headers),
            "elapsed_ms": elapsed_ms,
            "error": None,
        }

    except requests.exceptions.Timeout as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Timeout: {e}"}
    except requests.exceptions.ConnectionError as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"ConnectionError: {e}"}
    except Exception as e:
        return {"status_code": None, "body": None, "headers": None, "elapsed_ms": 0, "error": f"Error: {e}"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_request_handler.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add common/request_handler.py tests/test_request_handler.py
git commit -m "feat: request handler with timeout and error handling"
```

---

### Task 7: Database Handler

**Files:**
- Create: `common/db_handler.py`
- Create: `tests/test_db_handler.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db_handler.py`:
```python
from unittest.mock import patch, MagicMock

from common.db_handler import DBHandler


def _make_db_config():
    return {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "123456",
        "database": "test_db",
        "charset": "utf8mb4",
    }


@patch("common.db_handler.pymysql.connect")
def test_execute_setup_sql(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    handler.execute_setup([
        {"sql": "INSERT INTO users (id, name) VALUES (1, 'test')"},
        {"sql": "INSERT INTO roles (id, name) VALUES (1, 'admin')"},
    ])

    assert mock_cursor.execute.call_count == 2
    mock_conn.commit.assert_called()
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_teardown_sql(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    handler.execute_teardown([
        {"sql": "DELETE FROM users WHERE id = 1"},
    ])

    mock_cursor.execute.assert_called_once_with("DELETE FROM users WHERE id = 1")
    mock_conn.commit.assert_called()
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_extract(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"status": "pending", "total_price": 99.9}
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    result = handler.execute_extract([
        {
            "sql": "SELECT status, total_price FROM orders WHERE id = 1",
            "extract": {"db_status": "status", "db_price": "total_price"},
        }
    ])

    assert result == {"db_status": "pending", "db_price": 99.9}
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_execute_extract_no_result(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    result = handler.execute_extract([
        {
            "sql": "SELECT status FROM orders WHERE id = 999",
            "extract": {"db_status": "status"},
        }
    ])

    assert result == {"db_status": None}
    handler.close()


@patch("common.db_handler.pymysql.connect")
def test_close_connection(mock_connect):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    handler = DBHandler(_make_db_config())
    handler.close()

    mock_conn.close.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_db_handler.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/db_handler.py**

```python
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


class DBHandler:
    def __init__(self, config: dict):
        self._conn = pymysql.connect(
            host=config["host"],
            port=config.get("port", 3306),
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config.get("charset", "utf8mb4"),
            cursorclass=DictCursor,
        )

    def execute_setup(self, sql_list: list[dict]):
        with self._conn.cursor() as cursor:
            for item in sql_list:
                cursor.execute(item["sql"])
        self._conn.commit()

    def execute_teardown(self, sql_list: list[dict]):
        with self._conn.cursor() as cursor:
            for item in sql_list:
                cursor.execute(item["sql"])
        self._conn.commit()

    def execute_extract(self, extract_list: list[dict]) -> dict[str, Any]:
        result = {}
        with self._conn.cursor() as cursor:
            for item in extract_list:
                cursor.execute(item["sql"])
                row = cursor.fetchone()
                for var_name, column_name in item["extract"].items():
                    result[var_name] = row[column_name] if row else None
        return result

    def close(self):
        if self._conn:
            self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_db_handler.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add common/db_handler.py tests/test_db_handler.py
git commit -m "feat: database handler for setup, extract, and teardown"
```

---

### Task 8: Hook Manager

**Files:**
- Create: `common/hook_manager.py`
- Create: `tests/test_hook_manager.py`

- [ ] **Step 1: Write the failing test**

`tests/test_hook_manager.py`:
```python
import os
import sys

import pytest

from common.hook_manager import HookManager


@pytest.fixture
def hooks_dir(tmp_path):
    hook_file = tmp_path / "custom_hooks.py"
    hook_file.write_text(
        "def before_add_sign(request_data):\n"
        "    request_data['body']['sign'] = 'abc'\n"
        "    return request_data\n"
        "\n"
        "def after_upper_msg(response):\n"
        "    response['body']['msg'] = response['body']['msg'].upper()\n"
        "    return response\n"
    )
    return str(tmp_path)


def test_load_hooks(hooks_dir):
    manager = HookManager(hooks_dir)
    assert manager.has_hook("before_add_sign")
    assert manager.has_hook("after_upper_msg")


def test_call_before_hook(hooks_dir):
    manager = HookManager(hooks_dir)
    request_data = {"body": {"username": "admin"}}
    result = manager.call("before_add_sign", request_data)
    assert result["body"]["sign"] == "abc"
    assert result["body"]["username"] == "admin"


def test_call_after_hook(hooks_dir):
    manager = HookManager(hooks_dir)
    response = {"body": {"msg": "success"}}
    result = manager.call("after_upper_msg", response)
    assert result["body"]["msg"] == "SUCCESS"


def test_missing_hook(hooks_dir):
    manager = HookManager(hooks_dir)
    assert not manager.has_hook("nonexistent")


def test_call_missing_hook_returns_input(hooks_dir):
    manager = HookManager(hooks_dir)
    data = {"key": "value"}
    result = manager.call("nonexistent", data)
    assert result == data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_hook_manager.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/hook_manager.py**

```python
import importlib.util
import os
from typing import Any, Callable


class HookManager:
    def __init__(self, hooks_dir: str):
        self._hooks: dict[str, Callable] = {}
        self._load_hooks(hooks_dir)

    def _load_hooks(self, hooks_dir: str):
        if not os.path.isdir(hooks_dir):
            return
        for filename in os.listdir(hooks_dir):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            filepath = os.path.join(hooks_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith("_"):
                    self._hooks[attr_name] = attr

    def has_hook(self, name: str) -> bool:
        return name in self._hooks

    def call(self, name: str, data: Any) -> Any:
        if name not in self._hooks:
            return data
        return self._hooks[name](data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_hook_manager.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add common/hook_manager.py tests/test_hook_manager.py
git commit -m "feat: hook manager for before/after request processing"
```

---

### Task 9: Config Loader

**Files:**
- Create: `common/config_loader.py`
- Create: `tests/test_config_loader.py`
- Create: `config/config.yaml`
- Create: `config/test.yaml`

- [ ] **Step 1: Create config files**

`config/config.yaml`:
```yaml
current_env: test
timeout: 30
retry: 0
report_type: allure

email:
  enabled: false
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: test@qq.com
  password: ""
  receivers: []
  send_on: fail
```

`config/test.yaml`:
```yaml
base_url: https://test-api.example.com
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: admin
  admin_pass: "123456"

database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: test_db
  charset: utf8mb4
```

- [ ] **Step 2: Write the failing test**

`tests/test_config_loader.py`:
```python
import os

import pytest

from common.config_loader import load_config


@pytest.fixture
def config_dir(tmp_path):
    main_config = tmp_path / "config.yaml"
    main_config.write_text(
        "current_env: test\n"
        "timeout: 30\n"
        "retry: 0\n"
        "report_type: allure\n"
        "email:\n"
        "  enabled: false\n"
        "  smtp_host: smtp.qq.com\n"
        "  smtp_port: 465\n"
        "  sender: test@qq.com\n"
        "  password: ''\n"
        "  receivers: []\n"
        "  send_on: fail\n"
    )
    env_config = tmp_path / "test.yaml"
    env_config.write_text(
        "base_url: https://test-api.example.com\n"
        "global_headers:\n"
        "  Content-Type: application/json\n"
        "global_variables:\n"
        "  admin_user: admin\n"
        "  admin_pass: '123456'\n"
        "database:\n"
        "  host: 127.0.0.1\n"
        "  port: 3306\n"
        "  user: root\n"
        "  password: '123456'\n"
        "  database: test_db\n"
        "  charset: utf8mb4\n"
    )
    return str(tmp_path)


def test_load_default_env(config_dir):
    config = load_config(config_dir)
    assert config["current_env"] == "test"
    assert config["timeout"] == 30
    assert config["base_url"] == "https://test-api.example.com"
    assert config["global_headers"]["Content-Type"] == "application/json"


def test_load_override_env(config_dir):
    config = load_config(config_dir, env="test")
    assert config["base_url"] == "https://test-api.example.com"


def test_load_global_variables(config_dir):
    config = load_config(config_dir)
    assert config["global_variables"]["admin_user"] == "admin"


def test_load_database_config(config_dir):
    config = load_config(config_dir)
    assert config["database"]["host"] == "127.0.0.1"
    assert config["database"]["port"] == 3306


def test_load_email_config(config_dir):
    config = load_config(config_dir)
    assert config["email"]["enabled"] is False
    assert config["email"]["send_on"] == "fail"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_config_loader.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Implement common/config_loader.py**

```python
import os

import yaml


def load_config(config_dir: str, env: str = None) -> dict:
    main_path = os.path.join(config_dir, "config.yaml")
    with open(main_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    env_name = env or config.get("current_env", "test")
    env_path = os.path.join(config_dir, f"{env_name}.yaml")

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_config = yaml.safe_load(f)
        config.update(env_config)

    config["current_env"] = env_name
    return config
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_config_loader.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add common/config_loader.py tests/test_config_loader.py config/config.yaml config/test.yaml
git commit -m "feat: config loader with multi-environment support"
```

---

### Task 10: Email Notifier

**Files:**
- Create: `common/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write the failing test**

`tests/test_notifier.py`:
```python
from unittest.mock import patch, MagicMock

from common.notifier import build_email_body, send_email


def test_build_email_body():
    stats = {
        "total": 10,
        "passed": 8,
        "failed": 1,
        "skipped": 1,
        "pass_rate": "80.0%",
        "duration": "15s",
        "env": "test",
        "failures": [
            {"module": "用户管理", "name": "删除用户", "error": "$.code 期望 0 实际 500"},
        ],
    }
    body = build_email_body(stats)
    assert "10" in body
    assert "80.0%" in body
    assert "删除用户" in body
    assert "test" in body


@patch("common.notifier.smtplib.SMTP_SSL")
def test_send_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    email_config = {
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "sender": "test@qq.com",
        "password": "abc",
        "receivers": ["dev@company.com"],
    }
    stats = {
        "total": 5, "passed": 5, "failed": 0, "skipped": 0,
        "pass_rate": "100.0%", "duration": "10s", "env": "test",
        "failures": [],
    }

    send_email(email_config, stats, report_path=None)
    mock_smtp.sendmail.assert_called_once()


def test_should_not_send_when_disabled():
    email_config = {
        "enabled": False,
    }
    # Should not raise, just return
    from common.notifier import maybe_send_notification
    maybe_send_notification(email_config, {}, send_on="always", report_path=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_notifier.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/notifier.py**

```python
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os


def build_email_body(stats: dict) -> str:
    lines = [
        f"测试环境：{stats.get('env', 'unknown')}",
        f"执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "─" * 40,
        f"总用例：{stats['total']}",
        f"通过：{stats['passed']}",
        f"失败：{stats['failed']}",
        f"跳过：{stats['skipped']}",
        f"通过率：{stats['pass_rate']}",
        f"耗时：{stats['duration']}",
    ]

    if stats.get("failures"):
        lines.append("")
        lines.append("失败用例：")
        for i, f in enumerate(stats["failures"], 1):
            lines.append(f"  {i}. {f['module']} > {f['name']} - {f['error']}")

    return "\n".join(lines)


def send_email(email_config: dict, stats: dict, report_path: str = None):
    subject = (
        f"[autotest] 测试报告 - {stats.get('env', '')}环境 - "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    body = build_email_body(stats)

    msg = MIMEMultipart()
    msg["From"] = email_config["sender"]
    msg["To"] = ", ".join(email_config["receivers"])
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if report_path and os.path.exists(report_path):
        with open(report_path, "rb") as f:
            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(report_path)}",
            )
            msg.attach(attachment)

    with smtplib.SMTP_SSL(email_config["smtp_host"], email_config["smtp_port"]) as server:
        server.login(email_config["sender"], email_config["password"])
        server.sendmail(
            email_config["sender"],
            email_config["receivers"],
            msg.as_string(),
        )


def maybe_send_notification(
    email_config: dict, stats: dict, send_on: str = "fail", report_path: str = None
):
    if not email_config.get("enabled", False):
        return

    should_send = False
    if send_on == "always":
        should_send = True
    elif send_on == "fail" and stats.get("failed", 0) > 0:
        should_send = True

    if should_send:
        send_email(email_config, stats, report_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_notifier.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add common/notifier.py tests/test_notifier.py
git commit -m "feat: email notifier with configurable send conditions"
```

---

### Task 11: Test Case Runner (Core Engine)

**Files:**
- Create: `common/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

`tests/test_runner.py`:
```python
from unittest.mock import patch, MagicMock

from common.runner import run_testcase
from common.variable_pool import VariablePool


@patch("common.runner.send_request")
def test_run_simple_testcase(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "msg": "success"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "测试用例",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["status_code", 200]}, {"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert result["response"]["status_code"] == 200


@patch("common.runner.send_request")
def test_run_testcase_with_extract(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0, "data": {"token": "abc123"}},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "登录",
        "method": "POST",
        "url": "/api/login",
        "body": {"username": "admin", "password": "123456"},
        "extract": {"token": "$.data.token"},
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    assert pool.get("token") == "abc123"


@patch("common.runner.send_request")
def test_run_testcase_with_variable_resolve(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 0},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    pool.set_module("token", "xyz")
    case = {
        "name": "带token请求",
        "method": "GET",
        "url": "/api/users",
        "headers": {"Authorization": "Bearer ${token}"},
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is True
    call_kwargs = mock_send.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer xyz"


@patch("common.runner.send_request")
def test_run_testcase_validation_failure(mock_send):
    mock_send.return_value = {
        "status_code": 200,
        "body": {"code": 500, "msg": "server error"},
        "headers": {},
        "elapsed_ms": 50,
        "error": None,
    }

    pool = VariablePool()
    case = {
        "name": "失败用例",
        "method": "GET",
        "url": "/api/test",
        "validate": [{"eq": ["$.code", 0]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=30)

    assert result["passed"] is False


@patch("common.runner.send_request")
def test_run_testcase_request_error(mock_send):
    mock_send.return_value = {
        "status_code": None,
        "body": None,
        "headers": None,
        "elapsed_ms": 0,
        "error": "Timeout: connection timed out",
    }

    pool = VariablePool()
    case = {
        "name": "超时用例",
        "method": "GET",
        "url": "/api/slow",
        "validate": [{"eq": ["status_code", 200]}],
    }
    result = run_testcase(case, base_url="https://test.com", pool=pool, timeout=5)

    assert result["passed"] is False
    assert result["error"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_runner.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement common/runner.py**

```python
from typing import Any

from common.request_handler import send_request
from common.extractor import extract_fields
from common.validator import validate_case
from common.variable_pool import VariablePool


def run_testcase(
    case: dict,
    base_url: str,
    pool: VariablePool,
    timeout: int = 30,
    hook_manager=None,
    db_handler=None,
) -> dict[str, Any]:
    name = case.get("name", "unnamed")

    # 1. Resolve variables in case data
    resolved = pool.resolve({
        "method": case.get("method", "GET"),
        "url": case.get("url", ""),
        "headers": case.get("headers", {}),
        "body": case.get("body"),
    })

    method = resolved["method"]
    url = base_url + resolved["url"]
    headers = resolved["headers"]
    body = resolved["body"]

    # 2. Execute db_setup
    if db_handler and case.get("db_setup"):
        db_setup_resolved = pool.resolve(case["db_setup"])
        db_handler.execute_setup(db_setup_resolved)

    # 3. Execute before hook
    if hook_manager and case.get("hook", {}).get("before"):
        request_data = {"method": method, "url": url, "headers": headers, "body": body}
        request_data = hook_manager.call(case["hook"]["before"], request_data)
        method = request_data["method"]
        url = request_data["url"]
        headers = request_data["headers"]
        body = request_data["body"]

    # 4. Send HTTP request
    response = send_request(
        method=method,
        url=url,
        headers=headers,
        body=body,
        timeout=timeout,
    )

    # Check for request error
    if response["error"]:
        _run_db_teardown(case, pool, db_handler)
        return {
            "name": name,
            "passed": False,
            "response": response,
            "validations": [],
            "error": response["error"],
        }

    # 5. Execute after hook
    if hook_manager and case.get("hook", {}).get("after"):
        response = hook_manager.call(case["hook"]["after"], response)

    # 6. Extract variables from response
    extracts = {}
    if case.get("extract") and response["body"]:
        extracts = extract_fields(response["body"], case["extract"])
        for k, v in extracts.items():
            pool.set_module(k, v)

    # 7. Execute db_extract
    db_vars = {}
    if db_handler and case.get("db_extract"):
        db_extract_resolved = pool.resolve(case["db_extract"])
        db_vars = db_handler.execute_extract(db_extract_resolved)
        for k, v in db_vars.items():
            pool.set_module(k, v)

    # 8. Validate
    validations = []
    all_passed = True
    if case.get("validate"):
        extra_vars = {**extracts, **db_vars}
        validations = validate_case(response, case["validate"], extra_vars=extra_vars)
        all_passed = all(v["passed"] for v in validations)

    # 9. Execute db_teardown
    _run_db_teardown(case, pool, db_handler)

    return {
        "name": name,
        "passed": all_passed,
        "response": response,
        "extracts": extracts,
        "db_vars": db_vars,
        "validations": validations,
        "error": None,
    }


def _run_db_teardown(case: dict, pool: VariablePool, db_handler):
    if db_handler and case.get("db_teardown"):
        db_teardown_resolved = pool.resolve(case["db_teardown"])
        db_handler.execute_teardown(db_teardown_resolved)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/test_runner.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add common/runner.py tests/test_runner.py
git commit -m "feat: core test case runner with full execution pipeline"
```

---

### Task 12: Pytest Integration (conftest.py)

**Files:**
- Create: `conftest.py`

- [ ] **Step 1: Implement conftest.py**

```python
import os

import allure
import pytest

from common.config_loader import load_config
from common.data_loader import scan_testcase_files, load_testcases
from common.variable_pool import VariablePool
from common.runner import run_testcase
from common.hook_manager import HookManager
from common.db_handler import DBHandler
from common.logger import setup_logger, log_request


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def pytest_addoption(parser):
    parser.addoption("--env", default=None, help="Test environment (dev/test/staging/prod)")
    parser.addoption("--path", default="testcases", help="Test case directory or file path")
    parser.addoption("--report", default=None, help="Report type (allure/html/both)")


def pytest_configure(config):
    env = config.getoption("--env")
    config_dir = os.path.join(PROJECT_ROOT, "config")
    cfg = load_config(config_dir, env=env)

    report_type = config.getoption("--report") or cfg.get("report_type", "allure")
    cfg["report_type"] = report_type

    config._autotest_config = cfg
    config._autotest_pool = VariablePool()
    config._autotest_logger = setup_logger(os.path.join(PROJECT_ROOT, "logs"))

    hooks_dir = os.path.join(PROJECT_ROOT, "hooks")
    config._autotest_hooks = HookManager(hooks_dir)

    config._autotest_db = None
    if cfg.get("database"):
        try:
            config._autotest_db = DBHandler(cfg["database"])
        except Exception as e:
            config._autotest_logger.warning(f"Database connection failed: {e}")

    # Set global variables
    for k, v in cfg.get("global_variables", {}).items():
        config._autotest_pool.set_global(k, v)


def pytest_unconfigure(config):
    if hasattr(config, "_autotest_db") and config._autotest_db:
        config._autotest_db.close()


def pytest_collect_file(parent, file_path):
    ext = file_path.suffix.lower()
    if ext in (".yaml", ".yml", ".json", ".xlsx"):
        if "testcases" in str(file_path):
            return TestCaseFile.from_parent(parent, path=file_path)


class TestCaseFile(pytest.File):
    def collect(self):
        data = load_testcases(str(self.path))
        module_name = data.get("module", self.path.stem)
        for i, case in enumerate(data.get("testcases", [])):
            case["_module"] = module_name
            name = case.get("name", f"case_{i}")
            yield TestCaseItem.from_parent(self, name=name, callobj=case)


class TestCaseItem(pytest.Item):
    def __init__(self, name, parent, callobj):
        super().__init__(name, parent)
        self._case = callobj
        module_name = callobj.get("_module", "")
        level = callobj.get("level", "normal")
        self.user_properties.append(("module", module_name))
        self.user_properties.append(("level", level))

    def runtest(self):
        config = self.config
        cfg = config._autotest_config
        pool = config._autotest_pool
        logger = config._autotest_logger
        hooks = config._autotest_hooks
        db = config._autotest_db

        module_name = self._case.get("_module", "")

        result = run_testcase(
            case=self._case,
            base_url=cfg["base_url"],
            pool=pool,
            timeout=cfg.get("timeout", 30),
            hook_manager=hooks,
            db_handler=db,
        )

        # Log
        log_request(
            logger=logger,
            module=module_name,
            name=self._case.get("name", ""),
            method=self._case.get("method", ""),
            url=cfg["base_url"] + self._case.get("url", ""),
            headers=self._case.get("headers"),
            body=self._case.get("body"),
            status_code=result["response"]["status_code"] if result["response"] else None,
            elapsed_ms=result["response"]["elapsed_ms"] if result["response"] else 0,
            response=result["response"]["body"] if result["response"] else None,
            extracts=result.get("extracts"),
            validations=[
                f"{v['keyword']}: {'PASS' if v['passed'] else 'FAIL'}"
                for v in result.get("validations", [])
            ],
        )

        # Allure reporting
        allure.dynamic.feature(module_name)
        allure.dynamic.story(self._case.get("name", ""))
        if self._case.get("description"):
            allure.dynamic.description(self._case["description"])
        level_map = {
            "blocker": allure.severity_level.BLOCKER,
            "critical": allure.severity_level.CRITICAL,
            "normal": allure.severity_level.NORMAL,
            "minor": allure.severity_level.MINOR,
            "trivial": allure.severity_level.TRIVIAL,
        }
        severity = level_map.get(self._case.get("level", "normal"), allure.severity_level.NORMAL)
        allure.dynamic.severity(severity)

        if not result["passed"]:
            failures = []
            if result.get("error"):
                failures.append(f"Request error: {result['error']}")
            for v in result.get("validations", []):
                if not v["passed"]:
                    failures.append(
                        f"{v['keyword']}: {v.get('expression', '')} "
                        f"actual={v.get('actual')} expect={v.get('expect', '')}"
                    )
            raise TestCaseFailure("\n".join(failures))

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, TestCaseFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        module_name = self._case.get("_module", "")
        return self.path, None, f"{module_name} > {self.name}"


class TestCaseFailure(Exception):
    pass
```

- [ ] **Step 2: Create example test case files**

`testcases/login/login.yaml`:
```yaml
module: 用户登录
testcases:
  - name: 登录成功
    description: 使用正确账号密码登录
    method: POST
    url: /api/login
    headers:
      Content-Type: application/json
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - not_null: [$.data.token]

  - name: 密码错误
    description: 密码输入错误应返回错误码
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: wrong_password
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 1001]
      - contains: [$.msg, "密码"]
```

`testcases/user/user_crud.yaml`:
```yaml
module: 用户管理
testcases:
  - name: 登录获取token
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [$.code, 0]

  - name: 查询用户列表
    method: GET
    url: /api/users
    headers:
      Authorization: Bearer ${token}
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
```

- [ ] **Step 3: Verify pytest can discover test cases**

Run: `cd /Volumes/MySpace/autotest && python -m pytest --collect-only testcases/ 2>&1 | head -20`
Expected: Shows collected test items from YAML files (may fail on actual HTTP requests, but collection should work)

- [ ] **Step 4: Commit**

```bash
git add conftest.py testcases/
git commit -m "feat: pytest integration with auto-discovery of data-driven test cases"
```

---

### Task 13: CLI Entry Point (run.py)

**Files:**
- Create: `run.py`

- [ ] **Step 1: Implement run.py**

```python
import argparse
import os
import sys
import time

import pytest

from common.config_loader import load_config
from common.notifier import maybe_send_notification


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="API Autotest Framework")
    parser.add_argument("--env", default=None, help="Test environment (dev/test/staging/prod)")
    parser.add_argument("--path", default="testcases", help="Test case path (directory or file)")
    parser.add_argument("--report", default=None, help="Report type: allure / html / both")
    args = parser.parse_args()

    # Load config for email settings
    config_dir = os.path.join(PROJECT_ROOT, "config")
    config = load_config(config_dir, env=args.env)

    # Build pytest args
    pytest_args = [args.path, "-v"]

    report_type = args.report or config.get("report_type", "allure")
    reports_dir = os.path.join(PROJECT_ROOT, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    report_path = None
    if report_type in ("html", "both"):
        report_path = os.path.join(reports_dir, "report.html")
        pytest_args.extend([f"--html={report_path}", "--self-contained-html"])
    if report_type in ("allure", "both"):
        allure_dir = os.path.join(reports_dir, "allure-results")
        pytest_args.extend([f"--alluredir={allure_dir}", "--clean-alluredir"])

    if args.env:
        pytest_args.extend(["--env", args.env])
    if args.report:
        pytest_args.extend(["--report", args.report])

    # Run tests
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    duration = round(time.time() - start_time, 1)

    # Send notification
    if config.get("email", {}).get("enabled"):
        # Parse results from exit code (simplified)
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration": f"{duration}s",
            "env": config.get("current_env", "unknown"),
            "failures": [],
        }
        maybe_send_notification(
            email_config=config["email"],
            stats=stats,
            send_on=config["email"].get("send_on", "fail"),
            report_path=report_path,
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help works**

Run: `cd /Volumes/MySpace/autotest && python run.py --help`
Expected: Shows usage with --env, --path, --report options

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "feat: CLI entry point with env/path/report options"
```

---

### Task 14: Pytest Plugin for Stats Collection

**Files:**
- Modify: `conftest.py` (add session stats for email notification)
- Modify: `run.py` (read stats from result file)

- [ ] **Step 1: Add stats collector to conftest.py**

Append to the end of `conftest.py`:

```python
import json


def pytest_sessionstart(session):
    session._autotest_stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0, "failures": []
    }


def pytest_runtest_logreport(report):
    if report.when == "call":
        session = report.session if hasattr(report, "session") else None
        if session is None:
            return
        stats = session._autotest_stats
        stats["total"] += 1
        if report.passed:
            stats["passed"] += 1
        elif report.failed:
            stats["failed"] += 1
            stats["failures"].append({
                "module": dict(report.user_properties).get("module", ""),
                "name": report.nodeid.split("::")[-1],
                "error": str(report.longreprtext)[:200],
            })
        elif report.skipped:
            stats["skipped"] += 1


def pytest_sessionfinish(session, exitstatus):
    stats = getattr(session, "_autotest_stats", None)
    if stats:
        total = stats["total"]
        stats["pass_rate"] = f"{(stats['passed'] / total * 100):.1f}%" if total > 0 else "0%"
        stats_path = os.path.join(PROJECT_ROOT, "reports", ".stats.json")
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False)
```

- [ ] **Step 2: Update run.py to read stats**

Replace the stats section in `run.py` (after `exit_code = pytest.main(pytest_args)`):

```python
    # Read stats from pytest session
    stats_path = os.path.join(reports_dir, ".stats.json")
    stats = {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "pass_rate": "0%", "duration": f"{duration}s",
        "env": config.get("current_env", "unknown"), "failures": [],
    }
    if os.path.exists(stats_path):
        import json
        with open(stats_path, "r", encoding="utf-8") as f:
            file_stats = json.load(f)
        stats.update(file_stats)
        stats["duration"] = f"{duration}s"
        stats["env"] = config.get("current_env", "unknown")
```

- [ ] **Step 3: Commit**

```bash
git add conftest.py run.py
git commit -m "feat: stats collection and email notification integration"
```

---

### Task 15: CI/CD Configuration

**Files:**
- Create: `Jenkinsfile`
- Create: `.gitlab-ci.yml`
- Create: `hooks/custom_hooks.py` (example)

- [ ] **Step 1: Create Jenkinsfile**

```groovy
pipeline {
    agent any
    parameters {
        choice(name: 'ENV', choices: ['test', 'dev', 'staging'], description: '测试环境')
        string(name: 'TEST_PATH', defaultValue: 'testcases/', description: '用例路径')
        choice(name: 'REPORT', choices: ['allure', 'html', 'both'], description: '报告类型')
    }
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh "python run.py --env ${params.ENV} --path ${params.TEST_PATH} --report ${params.REPORT}"
            }
        }
        stage('Report') {
            steps {
                allure includeProperties: false, results: [[path: 'reports/allure-results']]
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'reports/**', fingerprint: true
            archiveArtifacts artifacts: 'logs/**', fingerprint: true
        }
    }
}
```

- [ ] **Step 2: Create .gitlab-ci.yml**

```yaml
stages:
  - test

api_test:
  stage: test
  image: python:3.10
  variables:
    ENV: test
    TEST_PATH: testcases/
    REPORT: both
  script:
    - pip install -r requirements.txt
    - python run.py --env $ENV --path $TEST_PATH --report $REPORT
  artifacts:
    paths:
      - reports/
      - logs/
    when: always
    expire_in: 7 days
```

- [ ] **Step 3: Create example hooks file**

`hooks/custom_hooks.py`:
```python
"""
Example hook functions.

Hook functions receive a dict and must return a dict.
- before hooks receive: {"method": str, "url": str, "headers": dict, "body": dict}
- after hooks receive: {"status_code": int, "body": dict, "headers": dict, "elapsed_ms": float, "error": None}

Usage in test case YAML:
  hook:
    before: my_before_function
    after: my_after_function
"""


def example_add_timestamp(request_data):
    """Example: add timestamp to request body before sending."""
    import time
    if request_data.get("body") and isinstance(request_data["body"], dict):
        request_data["body"]["_timestamp"] = int(time.time())
    return request_data
```

- [ ] **Step 4: Create additional environment configs**

`config/dev.yaml`:
```yaml
base_url: https://dev-api.example.com
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: admin
  admin_pass: "dev123"

database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "dev123"
  database: dev_db
  charset: utf8mb4
```

`config/staging.yaml`:
```yaml
base_url: https://staging-api.example.com
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: admin
  admin_pass: "staging123"

database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "staging123"
  database: staging_db
  charset: utf8mb4
```

`config/prod.yaml`:
```yaml
base_url: https://api.example.com
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: admin
  admin_pass: "prod123"
```

- [ ] **Step 5: Commit**

```bash
git add Jenkinsfile .gitlab-ci.yml hooks/custom_hooks.py config/dev.yaml config/staging.yaml config/prod.yaml
git commit -m "feat: CI/CD configs, example hooks, and environment configs"
```

---

### Task 16: Usage Documentation

**Files:**
- Create: `docs/usage.md`

- [ ] **Step 1: Write usage documentation**

`docs/usage.md`:
```markdown
# API 接口自动化测试框架 - 使用文档

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

编辑 `config/config.yaml` 设置当前环境：

```yaml
current_env: test    # 修改为你的环境：dev / test / staging / prod
```

编辑对应环境文件（如 `config/test.yaml`）：

```yaml
base_url: https://your-api.example.com   # 你的接口地址
global_headers:
  Content-Type: application/json
global_variables:
  admin_user: your_username
  admin_pass: your_password

database:                                  # 数据库配置（可选）
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: your_db
  charset: utf8mb4
```

### 3. 编写用例

在 `testcases/` 目录下创建 YAML 文件：

```yaml
module: 用户登录
testcases:
  - name: 登录成功
    method: POST
    url: /api/login
    body:
      username: ${admin_user}
      password: ${admin_pass}
    extract:
      token: $.data.token
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
```

### 4. 运行测试

```bash
python run.py                           # 运行全部用例
python run.py --env dev                 # 指定环境
python run.py --path testcases/login/   # 指定用例路径
python run.py --report both             # 指定报告类型
```

---

## 用例编写指南

### 基础结构

```yaml
module: 模块名称
testcases:
  - name: 用例名称
    description: 用例描述（可选）
    level: normal          # 优先级：blocker/critical/normal/minor/trivial（可选）
    method: POST           # 请求方法：GET/POST/PUT/DELETE/PATCH
    url: /api/path         # 接口路径（会自动拼接 base_url）
    headers:               # 请求头（可选）
      Authorization: Bearer ${token}
    body:                  # 请求体（可选）
      key: value
    extract:               # 提取响应数据（可选）
      变量名: JSONPath表达式
    validate:              # 断言（至少一个）
      - eq: [表达式, 期望值]
```

### 断言关键字

| 关键字 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `eq: [$.code, 0]` |
| `neq` | 不等于 | `neq: [$.code, -1]` |
| `gt` | 大于 | `gt: [$.data.total, 0]` |
| `lt` | 小于 | `lt: [$.data.total, 100]` |
| `gte` | 大于等于 | `gte: [status_code, 200]` |
| `lte` | 小于等于 | `lte: [status_code, 299]` |
| `contains` | 包含 | `contains: [$.msg, "成功"]` |
| `not_null` | 不为空 | `not_null: [$.data.token]` |
| `type` | 类型校验 | `type: [$.data.id, int]` |
| `length` | 长度校验 | `length: [$.data.list, 10]` |

### 变量引用

使用 `${变量名}` 引用变量。变量来源：

1. **全局变量**：`config/{env}.yaml` 中的 `global_variables`
2. **接口提取**：`extract` 从响应中提取的值
3. **数据库提取**：`db_extract` 从数据库查询的值

```yaml
- name: 登录
  method: POST
  url: /api/login
  body:
    username: ${admin_user}      # 引用全局变量
  extract:
    token: $.data.token          # 提取到变量池

- name: 查询用户
  method: GET
  url: /api/users
  headers:
    Authorization: Bearer ${token}  # 引用上一步提取的变量
```

### 数据库操作

#### 前置数据准备（db_setup）

```yaml
- name: 测试删除用户
  db_setup:
    - sql: "INSERT INTO users (id, name) VALUES (9999, 'test_user')"
  method: DELETE
  url: /api/users/9999
  validate:
    - eq: [$.code, 0]
  db_teardown:
    - sql: "DELETE FROM users WHERE id = 9999"
```

#### 数据库校验（db_extract）

```yaml
- name: 创建订单后验证数据库
  method: POST
  url: /api/orders
  body:
    product_id: 100
  extract:
    order_id: $.data.order_id
  db_extract:
    - sql: "SELECT status FROM orders WHERE id = ${order_id}"
      extract:
        db_status: status
  validate:
    - eq: [$.code, 0]
    - eq: [${db_status}, "pending"]
```

### Hook 扩展

在 `hooks/custom_hooks.py` 中定义函数，用例中通过 `hook` 字段调用：

```python
# hooks/custom_hooks.py
def encrypt_body(request_data):
    # request_data = {"method": ..., "url": ..., "headers": ..., "body": ...}
    request_data["body"]["sign"] = calculate_sign(request_data["body"])
    return request_data
```

```yaml
- name: 需要签名的接口
  method: POST
  url: /api/pay
  body:
    order_id: "12345"
  hook:
    before: encrypt_body     # 请求前调用
    after: decrypt_response  # 响应后调用（可选）
  validate:
    - eq: [$.code, 0]
```

### Excel 格式用例

Excel 文件的 Sheet 名称作为模块名，第一行为表头：

| name | method | url | headers | body | extract | validate |
|------|--------|-----|---------|------|---------|----------|
| 登录成功 | POST | /api/login | | {"username":"admin"} | {"token":"$.data.token"} | [{"eq":["$.code",0]}] |

headers/body/extract/validate 列使用 JSON 字符串。

---

## 报告

### Allure 报告

```bash
python run.py --report allure
# 查看报告：
allure serve reports/allure-results
```

### HTML 报告

```bash
python run.py --report html
# 报告生成在 reports/report.html
```

---

## 邮件通知

在 `config/config.yaml` 中配置：

```yaml
email:
  enabled: true
  smtp_host: smtp.qq.com
  smtp_port: 465
  sender: your_email@qq.com
  password: your_smtp_password
  receivers:
    - receiver1@company.com
    - receiver2@company.com
  send_on: fail    # always=每次发送 / fail=失败时发送 / never=不发送
```

---

## 目录说明

```
autotest/
├── config/          # 环境配置（需要修改）
├── testcases/       # 测试用例（需要编写）
├── hooks/           # 自定义扩展函数（按需编写）
├── common/          # 框架核心代码（无需修改）
├── reports/         # 报告输出（自动生成）
├── logs/            # 日志输出（自动生成）
├── run.py           # 运行入口
└── conftest.py      # pytest 配置
```

日常使用只需关注 `config/`、`testcases/`、`hooks/` 三个目录。
```

- [ ] **Step 2: Commit**

```bash
git add docs/usage.md
git commit -m "docs: add usage documentation"
```

---

### Task 17: Final Verification

- [ ] **Step 1: Run all unit tests**

Run: `cd /Volumes/MySpace/autotest && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify pytest collection of test cases**

Run: `cd /Volumes/MySpace/autotest && python -m pytest --collect-only testcases/`
Expected: Shows collected items from YAML files

- [ ] **Step 3: Verify CLI works**

Run: `cd /Volumes/MySpace/autotest && python run.py --help`
Expected: Shows help with --env, --path, --report

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final verification - all tests pass"
```
