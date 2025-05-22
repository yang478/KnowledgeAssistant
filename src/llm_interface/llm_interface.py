# -*- coding: utf-8 -*-
"""大模型接口 (LLMInterface) 的主实现文件。

包含 LLMInterface 类，该类封装了与不同大语言模型服务提供商
（如 OpenAI, Anthropic）交互的通用逻辑，包括构建API请求、
处理认证、发送请求、解析响应和错误处理。
"""
import json
import time
import requests # 新增

from src.config_manager.config_manager import ConfigManager


class LLMInterface:
    """
    封装与大语言模型的交互，处理 API 请求、认证、错误处理和结果解析。
    """

    def __init__(self, config_manager: ConfigManager):
        """
        初始化 LLMInterface。

        Args:
            config_manager: ConfigManager 实例，用于获取配置。
        """
        self.config_manager = config_manager
        self.api_key = self.config_manager.get_config("llm.api_key")
        self.api_endpoint = self.config_manager.get_config("llm.api_endpoint")
        self.default_model = self.config_manager.get_config(
            "llm.default_model", "default-model"
        )
        self.request_timeout = self.config_manager.get_config(
            "llm.request_timeout", 60
        )
        self.retry_attempts = self.config_manager.get_config(
            "llm.retry_attempts", 3
        )
        self.retry_delay = self.config_manager.get_config(
            "llm.retry_delay", 5
        )
        self.retry_on_status_codes = self.config_manager.get_config(
            "llm.retry_on_status_codes", [429, 500, 502, 503, 504]
        )
        self.default_max_tokens = self.config_manager.get_config(
            "llm.default_max_tokens", 1024
        )
        self.default_temperature = self.config_manager.get_config(
            "llm.default_temperature", 0.7
        )

        if not self.api_key:
            print("Warning: LLM_API_KEY not found in configuration.")
        if not self.api_endpoint:
            print("Warning: LLM_API_ENDPOINT not found in configuration. Real HTTP calls will fail.")

    def generate_text(self, prompt: str, model_config: dict = None) -> dict:
        """
        调用大语言模型生成文本。

        Args:
            prompt: 发送给模型的Prompt文本。
            model_config: 可选的模型配置，如 {"model_name": "gpt-4", "max_tokens": 500, "temperature": 0.7}。
                          如果提供，将覆盖默认配置。

        Returns:
            一个字典，包含状态、生成文本和使用情况等信息，格式如下：
            {
              "status": "success", // or "error"
              "data": {
                "text": "...", // 生成的文本
                "usage": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...} // 使用情况
              },
              "message": "" // 错误详情（如果状态是"error"）
            }
        """
        if not self.api_key or not self.api_endpoint:
            return {
                "status": "error",
                "data": None,
                "message": "LLM API key or endpoint not configured.",
            }

        current_model_config = model_config or {}
        model_name = current_model_config.get("model_name", self.default_model)
        max_tokens = current_model_config.get("max_tokens", self.default_max_tokens)
        temperature = current_model_config.get("temperature", self.default_temperature)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            # "stream": False, # 假设非流式
        }
        
        # 可选地添加stream参数，如果模型配置中提供了
        if "stream" in current_model_config:
            payload["stream"] = current_model_config["stream"]
        else:
            payload["stream"] = False # 默认为非流式


        for attempt in range(self.retry_attempts):
            try:
                print(f"Attempt {attempt + 1}/{self.retry_attempts} to call LLM API: {self.api_endpoint}")
                http_response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout,
                )

                if http_response.status_code == 200:
                    try:
                        response_data = http_response.json()
                        # 假设 OpenAI 兼容的响应结构
                        text_content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        usage_data = response_data.get("usage", {})
                        
                        if not text_content and not payload["stream"]: # 对于非流式，内容为空则认为有问题
                             return {
                                "status": "error",
                                "data": None,
                                "message": "LLM response missing content.",
                            }


                        return {
                            "status": "success",
                            "data": {"text": text_content, "usage": usage_data},
                            "message": "",
                        }
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        print(f"Error parsing LLM JSON response: {e}")
                        return {
                            "status": "error",
                            "data": None,
                            "message": f"Error parsing LLM JSON response: {e}",
                        }

                elif http_response.status_code in self.retry_on_status_codes:
                    print(f"LLM API returned {http_response.status_code}. Retrying in {self.retry_delay}s...")
                    if attempt < self.retry_attempts - 1: # 只有在不是最后一次尝试时才休眠
                        time.sleep(self.retry_delay)
                    continue # 转到下一次重试
                else:
                    # 不可重试的HTTP错误
                    error_message = f"LLM API request failed with status {http_response.status_code}: {http_response.text}"
                    print(error_message)
                    return {"status": "error", "data": None, "message": error_message}

            except requests.exceptions.Timeout:
                print(f"LLM API request timed out after {self.request_timeout}s.")
                if attempt < self.retry_attempts - 1:
                    print(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    return {
                        "status": "error",
                        "data": None,
                        "message": "LLM API request timed out after multiple retries.",
                    }
            except requests.exceptions.RequestException as e:
                print(f"LLM API request failed: {e}")
                if attempt < self.retry_attempts - 1:
                    print(f"Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    return {
                        "status": "error",
                        "data": None,
                        "message": f"LLM API request failed after multiple retries: {e}",
                    }
        
        # 如果所有重试都失败了
        return {
            "status": "error",
            "data": None,
            "message": "LLM API request failed after all retry attempts.",
        }
