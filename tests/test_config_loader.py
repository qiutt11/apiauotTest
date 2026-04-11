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
