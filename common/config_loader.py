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
