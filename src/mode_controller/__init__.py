# -*- coding: utf-8 -*-
"""模式控制器模块 (ModeController)。

负责接收API网关的请求，判断并切换学习模式（规划、学习、评估、复习），
管理模式生命周期，并将请求路由到当前激活的模式模块。
"""
from .mode_controller import ModeController

__all__ = ["ModeController"]
