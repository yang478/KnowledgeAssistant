# -*- coding: utf-8 -*-
"""配置管理器模块 (ConfigManager)。

负责加载、管理和提供整个系统的配置信息，
包括数据库连接、API密钥、模块行为参数等。
"""
from .config_manager import ConfigManager

__all__ = ["ConfigManager"]
