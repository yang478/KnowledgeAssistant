# -*- coding: utf-8 -*-
"""记忆库管理器模块 (MemoryBankManager)。

负责抽象和管理所有与学习记忆库相关的持久化数据操作，
是数据存储的唯一入口，屏蔽底层存储细节。
"""
from .memory_bank_manager import MemoryBankManager

__all__ = ["MemoryBankManager"]
