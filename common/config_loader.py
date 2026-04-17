"""配置加载模块。

负责加载主配置文件 (config.yaml) 和环境配置文件 ({env}.yaml)，
并通过深合并将环境配置覆盖到主配置上，保留未覆盖的嵌套字段。

示例：
    config = load_config("config/", env="test")
    # config["base_url"] → 来自 test.yaml
    # config["email"]["smtp_host"] → 来自 config.yaml（未被 test.yaml 覆盖）
"""

import os

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深合并两个字典。

    override 中的值会覆盖 base 中的同名键。
    如果两边都是 dict，则递归合并（不会丢失 base 中的嵌套键）。

    Args:
        base: 基础字典（如主配置）
        override: 覆盖字典（如环境配置）

    Returns:
        合并后的新字典
    """
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            # 两边都是 dict → 递归合并
            result[k] = _deep_merge(result[k], v)
        else:
            # 直接覆盖
            result[k] = v
    return result


def load_config(config_dir: str, env: str = None) -> dict:
    """加载框架配置。

    1. 读取 config_dir/config.yaml 作为主配置
    2. 根据 env 参数（或主配置中的 current_env）加载对应的环境配置
    3. 将环境配置深合并到主配置上

    Args:
        config_dir: 配置文件目录路径
        env: 指定环境名（可选，默认读取 config.yaml 中的 current_env）

    Returns:
        合并后的完整配置字典
    """
    # 读取主配置
    main_path = os.path.join(config_dir, "config.yaml")
    with open(main_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}  # 空文件返回 {} 而非 None

    # 确定环境名：命令行参数 > config.yaml 中的 current_env > 默认 "test"
    env_name = env or config.get("current_env", "test")
    env_path = os.path.join(config_dir, f"{env_name}.yaml")

    # 加载并深合并环境配置
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            env_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, env_config)

    config["current_env"] = env_name
    return config
