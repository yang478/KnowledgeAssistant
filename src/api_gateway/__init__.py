# -*- coding: utf-8 -*-
"""API 网关模块。

作为整个后端服务的统一入口点，负责请求路由、协议转换、认证授权等。
"""
from .gateway import APIGateway

__all__ = ["APIGateway"]
