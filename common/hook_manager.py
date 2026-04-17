"""Hook 管理模块。

动态加载 hooks/ 目录下的 Python 文件，注册其中定义的函数作为 hook。
用例中通过 hook.before / hook.after 字段调用。

安全机制：
    - 只注册 hook 文件中直接定义的函数（通过 __module__ 过滤）
    - import 的第三方函数（如 os.system）不会被注册
    - 以 _ 开头的文件和函数会被跳过
    - 加载异常不会崩溃框架，只记录 warning 日志

示例：
    # hooks/custom_hooks.py
    def add_sign(request_data):
        request_data["body"]["sign"] = "xxx"
        return request_data

    # YAML 用例中
    hook:
      before: add_sign
"""

import importlib.util
import os
from typing import Any, Callable

from loguru import logger


class HookManager:
    """Hook 函数管理器。"""

    def __init__(self, hooks_dir: str):
        """初始化并加载指定目录下的所有 hook 文件。

        Args:
            hooks_dir: hooks 目录路径
        """
        self._hooks: dict[str, Callable] = {}  # {函数名: 函数对象}
        self._load_hooks(hooks_dir)

    def _load_hooks(self, hooks_dir: str):
        """扫描目录下的 .py 文件，注册其中定义的公共函数。"""
        if not os.path.isdir(hooks_dir):
            return
        for filename in os.listdir(hooks_dir):
            # 跳过非 Python 文件和以 _ 开头的文件（如 __init__.py）
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            filepath = os.path.join(hooks_dir, filename)
            module_name = filename[:-3]  # 去掉 .py 后缀
            try:
                # 动态加载 Python 模块
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # 注册模块中定义的公共函数
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # 安全过滤：只注册该文件中直接定义的函数
                    # （排除 import 的第三方函数如 os.system）
                    if (callable(attr)
                            and not attr_name.startswith("_")
                            and getattr(attr, "__module__", None) == module_name):
                        self._hooks[attr_name] = attr
            except Exception as e:
                logger.warning(f"Failed to load hook file {filename}: {e}")

    def has_hook(self, name: str) -> bool:
        """检查指定名称的 hook 是否存在。"""
        return name in self._hooks

    def call(self, name: str, data: Any) -> Any:
        """调用指定的 hook 函数。

        Args:
            name: hook 函数名
            data: 传入 hook 的数据（before hook 接收请求数据，after hook 接收响应数据）

        Returns:
            hook 函数的返回值。如果 hook 不存在，原样返回 data。
        """
        if name not in self._hooks:
            return data
        return self._hooks[name](data)
