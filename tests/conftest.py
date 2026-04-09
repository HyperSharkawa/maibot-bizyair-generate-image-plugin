"""
conftest.py — 在任何 service 模块被导入前 mock MaiBot 框架依赖，
并设置虚拟父包使得 services/ 和 clients/ 的相对 import 能正常工作。
"""

import importlib
import logging
import sys
import types
from pathlib import Path


# ──────────────── 1. Mock MaiBot 框架依赖 ────────────────

def _ensure_module(dotted_name: str) -> types.ModuleType:
    """确保 dotted_name 及其所有父级在 sys.modules 中存在。"""
    parts = dotted_name.split(".")
    for i in range(1, len(parts) + 1):
        partial = ".".join(parts[:i])
        if partial not in sys.modules:
            sys.modules[partial] = types.ModuleType(partial)
    return sys.modules[dotted_name]


def _setup_framework_mocks() -> None:
    """注入所有需要的 MaiBot 框架 mock。"""
    from unittest.mock import MagicMock

    # src.common.logger
    logger_mod = _ensure_module("src.common.logger")
    logger_mod.get_logger = lambda name: logging.getLogger(name)  # type: ignore[attr-defined]

    # src.common.toml_utils
    toml_mod = _ensure_module("src.common.toml_utils")
    toml_mod.save_toml_with_format = MagicMock()  # type: ignore[attr-defined]

    # src.plugin_system.apis.message_api
    message_api_mod = _ensure_module("src.plugin_system.apis.message_api")
    message_api_mod.get_recent_messages = MagicMock(return_value=[])  # type: ignore[attr-defined]
    message_api_mod.build_readable_messages_to_str = MagicMock(return_value="")  # type: ignore[attr-defined]

    apis_mod = sys.modules["src.plugin_system.apis"]
    apis_mod.message_api = message_api_mod  # type: ignore[attr-defined]

    # 其余 src.* stub：让任何 from ... import xxx 不报错
    for name in [
        "src.plugin_system",
        "src.plugin_system.base",
        "src.plugin_system.base.component_types",
        "src.plugin_system.base.config_types",
        "src.plugin_system.base.base_plugin",
        "src.plugin_system.base.base_tool",
        "src.plugin_system.base.base_events_handler",
        "src.plugin_system.base.plugin_base",
        "src.plugin_system.apis.llm_api",
        "src.plugin_system.apis.generator_api",
        "src.config",
        "src.config.config",
        "src.config.api_ada_configs",
    ]:
        mod = _ensure_module(name)
        if not isinstance(getattr(mod, "__getattr__", None), types.FunctionType):
            mod.__getattr__ = lambda attr, _m=mod: MagicMock()  # type: ignore[attr-defined]


# ──────────────── 2. 设置虚拟父包（解决相对 import） ────────────────

def _setup_plugin_package() -> None:
    """
    创建虚拟父包 _bizyair_plugin，使 services/ 和 clients/ 成为其子包。
    这样 services 内的 `from ..clients import ...` 就能正确解析。
    同时在 sys.modules 中注册别名，使测试文件可以用 `from services.xxx import ...`。
    """
    project_root = Path(__file__).resolve().parent.parent

    _PKG = "_bizyair_plugin"
    root = types.ModuleType(_PKG)
    root.__path__ = [str(project_root)]
    root.__package__ = _PKG
    sys.modules[_PKG] = root

    # 以子包身份导入 clients 和 services，使相对 import 生效
    clients_mod = importlib.import_module(f"{_PKG}.clients")
    services_mod = importlib.import_module(f"{_PKG}.services")

    # 注册顶层别名，使 `from services.xxx import ...` 和 `from clients.xxx import ...` 可用
    sys.modules["services"] = services_mod
    sys.modules["clients"] = clients_mod

    # 同步子模块别名
    for key, mod in list(sys.modules.items()):
        if key.startswith(f"{_PKG}.services."):
            alias = key[len(f"{_PKG}."):]
            sys.modules[alias] = mod
        elif key.startswith(f"{_PKG}.clients."):
            alias = key[len(f"{_PKG}."):]
            sys.modules[alias] = mod


# 按顺序执行：先 mock 框架，再设置包结构
_setup_framework_mocks()
_setup_plugin_package()
