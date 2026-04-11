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
