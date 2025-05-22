# -*- coding: utf-8 -*-
"""复习模块 (ReviewerModule)。

负责处理与知识复习相关的逻辑，根据遗忘曲线、知识点重要性、
历史评估等因素智能推荐复习内容，并提供复习材料。
"""
from .reviewer_module import ReviewerModule

__all__ = ["ReviewerModule"]
