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
