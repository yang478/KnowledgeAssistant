# -*- coding: utf-8 -*-
"""更新与同步管理器模块 (UpdateManager)。

负责处理系统状态的后台更新、数据同步（未来功能）和自动备份，
响应系统事件或调度执行相应操作。
"""
from .update_manager import UpdateManager

__all__ = ["UpdateManager"]
