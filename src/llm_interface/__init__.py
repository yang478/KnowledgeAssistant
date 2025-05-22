# -*- coding: utf-8 -*-
"""大模型接口模块 (LLMInterface)。

封装与大语言模型（LLM）的交互细节，提供统一的API调用、
认证管理、请求发送、响应解析和错误处理功能。
"""
from .llm_interface import LLMInterface

__all__ = ["LLMInterface"]
