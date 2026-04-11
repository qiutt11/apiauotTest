# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

A data-driven API automation testing framework built with Python + pytest. Users write test cases in YAML/JSON/Excel files — no Python code required for standard testing.

## Tech Stack

- Python 3.10+
- pytest (test engine)
- requests (HTTP client)
- PyYAML / openpyxl (data parsing)
- jsonpath-ng (response extraction)
- allure-pytest / pytest-html (reporting)
- loguru (logging)
- PyMySQL (database operations)

## Project Structure

```
common/              # Core framework modules (DO NOT modify for normal use)
  config_loader.py   # Multi-environment config loading
  data_loader.py     # YAML/JSON/Excel test case parsing
  variable_pool.py   # Three-tier variable storage and ${xxx} resolution
  extractor.py       # JSONPath response data extraction
  validator.py       # 10 assertion keywords (eq, neq, gt, lt, gte, lte, contains, not_null, type, length)
  request_handler.py # HTTP request wrapper with error handling
  db_handler.py      # Database setup/extract/teardown operations
  hook_manager.py    # Dynamic loading of user-defined hook functions
  runner.py          # Core execution engine orchestrating all modules
  logger.py          # Loguru-based logging
  notifier.py        # Email notification with SMTP
config/              # Environment configs (config.yaml + per-env files)
testcases/           # Test case data files (YAML/JSON/Excel)
hooks/               # User-defined hook functions
tests/               # Unit tests (79 tests, 96% coverage)
conftest.py          # pytest integration: auto-discovery, execution, stats, allure
run.py               # CLI entry point (--env, --path, --report)
```

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all unit tests
python3 -m pytest tests/ -v -o "python_files=test_*.py" -o "python_functions=test_*"

# Run API test cases
python3 run.py
python3 run.py --env dev --path testcases/login/ --report both

# Check coverage
python3 -m coverage run --source=common -m pytest tests/ -o "python_files=test_*.py" -o "python_functions=test_*"
python3 -m coverage report --show-missing
```

## Key Architecture Decisions

- **Data-driven**: Test cases are pure data files. The framework parses and executes them automatically via `conftest.py` custom collector (`TestCaseFile` / `TestCaseItem`).
- **Variable pool**: Three-tier priority (temp > module > global). Variables are resolved via `${xxx}` syntax in any string field.
- **Execution flow per test case**: resolve vars → db_setup → before hook → HTTP request → after hook → extract → db_extract → validate → db_teardown → log.
- **pytest integration**: Custom `pytest_collect_file` discovers YAML/JSON/Excel files under `testcases/`. Each test case becomes a `TestCaseItem`.

## Conventions

- All framework code lives in `common/`. Each file has one responsibility.
- Unit tests live in `tests/test_<module>.py` and use `unittest.mock` for external dependencies.
- Git commits require `REVIEWED=1` env var. Commits with >5 files need `[scope-ack]` in message.
- Config uses YAML format. Environment configs are merged on top of `config/config.yaml`.
- Database config is optional — framework gracefully handles missing DB connection.

## Testing Notes

- pytest.ini sets `python_files = conftest.py` (for the framework's data-driven collection). To run unit tests, override with `-o "python_files=test_*.py" -o "python_functions=test_*"`.
- DB handler tests use `unittest.mock` — no real database connection needed.
- The `tests/fixtures/` directory contains sample YAML/JSON/Excel files for data_loader tests.
