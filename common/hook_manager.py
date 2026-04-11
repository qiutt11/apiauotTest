import importlib.util
import os
from typing import Any, Callable

from loguru import logger


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
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # Only register functions defined in the hook file itself
                    if (callable(attr)
                            and not attr_name.startswith("_")
                            and getattr(attr, "__module__", None) == module_name):
                        self._hooks[attr_name] = attr
            except Exception as e:
                logger.warning(f"Failed to load hook file {filename}: {e}")

    def has_hook(self, name: str) -> bool:
        return name in self._hooks

    def call(self, name: str, data: Any) -> Any:
        if name not in self._hooks:
            return data
        return self._hooks[name](data)
