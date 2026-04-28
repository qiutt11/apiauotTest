# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A data-driven API automation testing framework built with Python + pytest. Users write test cases in YAML/JSON/Excel files — no Python code required for standard testing.

## Tech Stack

- Python 3.10+
- pytest (test engine)
- pytest-xdist (parallel execution)
- requests (HTTP client)
- PyYAML / openpyxl (data parsing)
- jsonpath-ng (response extraction)
- allure-pytest / pytest-html (reporting)
- loguru (logging)
- PyMySQL (database operations)
- responses (HTTP mocking for tests)

## Project Structure

```
common/              # Core framework modules (DO NOT modify for normal use)
  config_loader.py   # Multi-environment config loading (deep merge)
  data_loader.py     # YAML/JSON/Excel test case parsing + load_yaml_datasets() for data-driven
  variable_pool.py   # Three-tier variable storage, ${xxx} resolution, type preservation
  extractor.py       # JSONPath response data extraction
  validator.py       # 10 assertion keywords (eq, neq, gt, lt, gte, lte, contains, not_null, type, length)
  request_handler.py # HTTP request wrapper with error handling
  db_handler.py      # Database setup(with extract)/extract/teardown, parameterized queries, rollback
  hook_manager.py    # Dynamic loading of user-defined hook functions (__module__ filtered)
  runner.py          # Core execution engine orchestrating all modules
  logger.py          # Loguru-based logging
  notifier.py        # Email + Feishu webhook notification
config/              # Environment configs (config.yaml + per-env files)
testcases/           # Test case data files (YAML/JSON/Excel)
hooks/               # User-defined hook functions
tests/               # 154 tests (128 unit + 21 integration + 5 level filter)
conftest.py          # pytest integration: auto-discovery, execution, stats, allure, level filter, DataDrivenItem
run.py               # CLI entry point (--env, --path, --report, --level, --workers)
```

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all unit tests
python3 -m pytest tests/ -v -o "python_files=test_*.py" -o "python_functions=test_*" -o "python_classes=Test*"

# Run API test cases
python3 run.py
python3 run.py --env dev --path testcases/login/ --level P0,P1 --workers 4 --report both

# Check coverage
python3 -m coverage run --source=common -m pytest tests/ -o "python_files=test_*.py" -o "python_functions=test_*" -o "python_classes=Test*"
python3 -m coverage report --show-missing
```

## Key Architecture Decisions

- **Data-driven**: Test cases are pure data files. The framework parses and executes them automatically via `conftest.py` custom collector (`TestCaseFile` / `TestCaseItem`).
- **Variable pool**: Three-tier priority (temp > module > global). Variables resolved via `${xxx}`. Single `${var}` preserves original type; embedded in string converts to str. Extract supports `scope: global` to store variables in global pool (survives file switches, used for cross-file token sharing).
- **Execution flow per test case**: resolve vars (including case-level `base_url`) → db_setup (with extract) → re-resolve vars → before hook → (request → after hook → extract → db_extract → resolve validate ${xxx} → validate) with retry → db_teardown → log (with resolved request data).
- **pytest integration**: Custom `pytest_collect_file` discovers YAML/JSON/Excel files under `testcases/` (skips `data/` subdirectories). Each test case becomes a `TestCaseItem`. YAML data-driven cases (with `yaml_source` + `steps`) become `DataDrivenItem` (one per dataset). `--level` filters at collection time. `--workers` uses xdist `loadfile` distribution.
- **YAML data-driven testing**: YAML testcase with `yaml_source` + `steps` triggers data-driven mode. Data file stores nested body structures. `body_from_yaml` sends dataset as request body. `validate_from_yaml` uses path mapping (data_path → response_jsonpath) to auto-generate assertions. Supports nested objects, arrays with `[]` wildcard, and missing field auto-skip. Each dataset generates an independent test item.
- **Notifications**: Email (SMTP_SSL) and Feishu (webhook card with color-coded header and @mentions).

## Conventions

- All framework code lives in `common/`. Each file has one responsibility.
- Unit tests in `tests/test_<module>.py`, integration tests in `tests/integration/`.
- Git commits require `REVIEWED=1` env var. Commits with >5 files need `[scope-ack]` in message.
- Config uses YAML format. Environment configs deep-merged on top of `config/config.yaml`.
- Database config is optional — framework gracefully handles missing DB connection.
- `AUTOTEST_CONFIG_DIR` env var overrides the config directory path.

## Testing Notes

- pytest.ini sets `python_files = conftest.py` (for the framework's data-driven collection). To run unit tests, override with `-o "python_files=test_*.py" -o "python_functions=test_*" -o "python_classes=Test*"`.
- DB handler tests use `unittest.mock` — no real database connection needed.
- Integration tests use `responses` library to mock HTTP at the requests level.
- Subprocess integration tests (TestConftestPipeline, test_level_filter) use httpbin.org — require network.
- The `tests/fixtures/` directory contains sample YAML/JSON/Excel files for data_loader tests.
