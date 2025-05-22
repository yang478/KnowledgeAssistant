# -*- coding: utf-8 -*-
"""监控管理器模块 (MonitoringManager)。

负责统一管理系统的可观测性，包括日志收集、性能指标监控、
分布式追踪（可选）和审计日志记录。
"""
from .monitoring_manager import MonitoringManager

__all__ = ["MonitoringManager"]
