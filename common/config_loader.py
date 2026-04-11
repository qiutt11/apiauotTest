import os

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, preserving nested keys."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_dir: str, env: str = None) -> dict:
    main_path = os.path.join(config_dir, "config.yaml")
    with open(main_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    env_name = env or config.get("current_env", "test")
    env_path = os.path.join(config_dir, f"{env_name}.yaml")

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, env_config)

    config["current_env"] = env_name
    return config
