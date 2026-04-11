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
