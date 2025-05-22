# -*- coding: utf-8 -*-
"""监控管理器 (MonitoringManager) 的主实现文件。

包含 MonitoringManager 类，该类封装了系统监控的各项功能，
包括结构化日志记录、性能指标收集与暴露（如通过Prometheus）、
以及可选的分布式追踪和审计日志功能。
"""
import json
import logging
import logging.handlers
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

# 明确导入 ConfigManager
from src.config_manager.config_manager import ConfigManager

# from src.memory_bank_manager.memory_bank_manager import MemoryBankManager # 保持注释，因为当前任务不直接使用

# 外部库依赖 (根据功能启用情况，实际安装由 requirements.txt 或类似机制管理)
# prometheus_client, opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http (或 grpc)


class StructuredJsonFormatter(logging.Formatter):
    """
    自定义 Formatter 以输出 JSON 格式的日志。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "context") and record.context:
            if isinstance(record.context, dict):
                log_record.update(record.context)
            else:
                log_record["context"] = str(record.context)  # 以防 context 不是字典

        # 处理日志消息中可能存在的参数
        if isinstance(record.args, dict):
            log_record.update(record.args)
        elif record.args:
            log_record["args"] = record.args

        return json.dumps(log_record, ensure_ascii=False)


class MonitoringManager:
    """
    统一管理系统的可观测性数据，包括日志收集、性能指标监控、分布式追踪和审计日志。
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        memory_bank_manager: Optional[Any] = None,  # MemoryBankManager 暂时可选且未使用
    ):
        """
        初始化 MonitoringManager。

        Args:
            config_manager: ConfigManager 实例，用于获取监控配置。
            memory_bank_manager: MemoryBankManager 实例 (当前未使用)。
        """
        self.config_manager = config_manager
        self.memory_bank_manager = memory_bank_manager  # 未在此次实现中使用
        self.logger = logging.getLogger(
            __name__
        )  # 基础 logger，会被 _setup_logging 修改

        self._setup_logging()
        self._setup_prometheus()
        self._setup_opentelemetry()

        self.metrics: Dict[str, Any] = {}  # 用于存储 Prometheus 指标对象

        self.logger.info("MonitoringManager initialized.")

    def _setup_logging(self):
        """
        根据配置设置日志记录器。
        """
        log_enabled = self.config_manager.get_config("monitoring.logging.enabled", True)
        log_level_str = self.config_manager.get_config(
            "monitoring.logging.level", "INFO"
        )
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)

        # MonitoringManager 使用自身的 logger 实例
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        # 阻止日志事件传播到根 logger，以避免双重日志记录或与应用级配置冲突
        self.logger.propagate = False

        # 移除已存在的 self.logger handlers，避免重复添加 (例如在重新初始化时)
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)

        if not log_enabled:
            self.logger.info(
                "File logging for MonitoringManager is disabled via configuration."
            )
            # 如果禁用了文件日志，可以考虑添加一个 NullHandler 以避免 "No handlers could be found" 警告
            # 或者依赖于 self.logger.propagate = False 来阻止消息传播
            # self.logger.addHandler(logging.NullHandler()) # 可选
            return

        log_filepath_str = self.config_manager.get_config(
            "monitoring.logging.filepath", "logs/monitoring_manager.log"
        )
        structured_json = self.config_manager.get_config(
            "monitoring.logging.structured_json", True
        )
        rotation_config_raw = self.config_manager.get_config(
            "monitoring.logging.rotation", {}
        )

        if not isinstance(rotation_config_raw, dict):
            self.logger.warning(
                f"Configuration 'monitoring.logging.rotation' is not a dictionary (got {type(rotation_config_raw)}). Using default rotation config {{}}.",
                extra={"context": {"loaded_rotation_config": rotation_config_raw}} # Use extra for context
            )
            rotation_config = {} # Use default empty dict
        else:
            rotation_config = rotation_config_raw # Use the loaded dict

        log_filepath = Path(log_filepath_str)
        log_filepath.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在

        # 文件 Handler (仅用于 MonitoringManager 自身的 logger)
        handler: Union[
            logging.handlers.RotatingFileHandler,
            logging.handlers.TimedRotatingFileHandler,
            logging.FileHandler,
        ]
        rotation_type = rotation_config.get("type", "size").lower()

        if rotation_type == "size":
            max_bytes = rotation_config.get("max_bytes", 1024 * 1024 * 10)  # 10MB
            backup_count = rotation_config.get("backup_count", 5)
            handler = logging.handlers.RotatingFileHandler(
                log_filepath,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        elif rotation_type == "time":
            when = rotation_config.get(
                "when", "D"
            )  # 'S', 'M', 'H', 'D', 'W0'-'W6', 'midnight'
            interval = rotation_config.get("interval", 1)
            backup_count = rotation_config.get("backup_count", 7)
            handler = logging.handlers.TimedRotatingFileHandler(
                log_filepath,
                when=when,
                interval=interval,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:  # No rotation or unknown type
            handler = logging.FileHandler(log_filepath, encoding="utf-8")

        if structured_json:
            formatter = StructuredJsonFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        handler.setFormatter(formatter)
        self.logger.addHandler(
            handler
        )  # 将文件 handler 添加到 MonitoringManager 的 logger

        self.logger.info(
            f"MonitoringManager file logging setup complete. Level: {log_level_str}, Path: {log_filepath}, Structured: {structured_json}, Rotation: {rotation_type}"
        )

    def _log(
        self,
        level: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info=None,
        **kwargs,
    ):
        """通用日志记录方法，支持将 context 和 kwargs 合并到日志记录中。"""
        # 对于 structured_json=True 的情况，StructuredJsonFormatter 会处理 context
        # 对于非结构化日志，context 和 kwargs 可能不会很好地展示，除非消息字符串中包含占位符

        # 将 context 和 kwargs 合并，优先使用 kwargs 中的值
        extra_info = {}
        if context:
            extra_info.update(context)
        if kwargs:
            extra_info.update(kwargs)

        # 如果使用标准 Formatter，且消息中没有占位符，extra_info 不会直接显示
        # 但 StructuredJsonFormatter 会将它们作为顶级字段添加
        if extra_info:
            # logging 模块的 logger 方法接受 kwargs 作为 extra 参数的一部分
            # 或者，如果 formatter 支持，可以直接传递
            self.logger.log(
                level, message, exc_info=exc_info, extra={"context": extra_info}
            )
        else:
            self.logger.log(level, message, exc_info=exc_info)

    def log_debug(
        self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """记录调试级别日志。"""
        self._log(logging.DEBUG, message, context, **kwargs)

    def log_info(
        self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """记录信息级别日志。"""
        self._log(logging.INFO, message, context, **kwargs)

    def log_warning(
        self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """记录警告级别日志。"""
        self._log(logging.WARNING, message, context, **kwargs)

    def log_error(
        self, message: str, context: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """记录错误级别日志。"""
        self._log(logging.ERROR, message, context, **kwargs)

    def log_exception(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info=True,
        **kwargs,
    ):
        """记录异常信息。"""
        self._log(logging.ERROR, message, context, exc_info=exc_info, **kwargs)

    def _setup_prometheus(self):
        """
        根据配置设置 Prometheus 指标导出。
        """
        prometheus_enabled = self.config_manager.get_config(
            "monitoring.prometheus.enabled", False
        )
        if not prometheus_enabled:
            self.logger.info("Prometheus metrics export is disabled.")
            return

        try:
            from prometheus_client import (
                Counter,
                Gauge,
                Histogram,  # noqa
                start_http_server,
            )

            port = self.config_manager.get_config("monitoring.prometheus.port", 9091)
            start_http_server(port)
            self.logger.info(f"Prometheus metrics server started on port {port}.")
            # 初始化一些常见的系统级指标（可选）
            # self.metrics['app_info'] = Gauge('app_info', 'Application information', ['version'])
            # self.metrics['app_info'].labels(version="1.0.0").set(1)
        except ImportError:
            self.logger.error(
                "prometheus_client library not found. Prometheus export disabled. Please install it."
            )
        except Exception as e:
            self.logger.error(f"Failed to start Prometheus server: {e}", exc_info=True)

    def record_metric(
        self,
        metric_name: str,
        value: float,
        metric_type: str = "gauge",  # 'gauge', 'counter', 'histogram'
        tags: Optional[Dict[str, str]] = None,
        description: str = "",
    ):
        """
        记录性能指标。
        """
        prometheus_enabled = self.config_manager.get_config(
            "monitoring.prometheus.enabled", False
        )
        if not prometheus_enabled:
            # 简单地记录到日志 (如果 Prometheus 未启用)
            metric_data = {
                "metric_name": metric_name,
                "value": value,
                "tags": tags,
                "type": metric_type,
            }
            self.log_debug(f"Record metric (Prometheus disabled): {metric_data}")
            return

        try:
            from prometheus_client import Counter, Gauge, Histogram  # noqa

            # 规范化标签键，Prometheus 不允许标签键与保留字冲突
            label_names = sorted(list(tags.keys())) if tags else []

            # 创建唯一的指标键，包含名称和标签名，以支持相同名称但不同标签集的指标
            metric_key = f"{metric_name}_{'_'.join(label_names)}"

            if metric_key not in self.metrics:
                actual_description = (
                    description
                    if description
                    else f"{metric_type.capitalize()} metric: {metric_name}"
                )
                if metric_type.lower() == "counter":
                    self.metrics[metric_key] = Counter(
                        metric_name, actual_description, label_names
                    )
                elif metric_type.lower() == "histogram":
                    # 默认 buckets，可以从配置中读取
                    buckets = self.config_manager.get_config(
                        f"monitoring.prometheus.metrics.{metric_name}.buckets"
                    )
                    if buckets:
                        self.metrics[metric_key] = Histogram(
                            metric_name,
                            actual_description,
                            label_names,
                            buckets=tuple(buckets),
                        )
                    else:
                        self.metrics[metric_key] = Histogram(
                            metric_name, actual_description, label_names
                        )
                else:  # Default to Gauge
                    self.metrics[metric_key] = Gauge(
                        metric_name, actual_description, label_names
                    )
                self.log_debug(
                    f"Prometheus metric '{metric_name}' (type: {metric_type}) with labels {label_names} registered."
                )

            metric_obj = self.metrics[metric_key]

            # 获取标签值
            label_values = {k: str(tags[k]) for k in label_names} if tags else {}

            if metric_type.lower() == "counter":
                metric_obj.labels(**label_values).inc(value)
            elif metric_type.lower() == "histogram":
                metric_obj.labels(**label_values).observe(value)
            else:  # Gauge
                metric_obj.labels(**label_values).set(value)

            # self.log_debug(f"Metric '{metric_name}' updated with value {value} and tags {tags}")

        except ImportError:
            # 已在 _setup_prometheus 中记录错误
            pass
        except Exception as e:
            self.log_error(
                f"Failed to record metric '{metric_name}': {e}", exc_info=True
            )

    def _setup_opentelemetry(self):
        """
        根据配置设置 OpenTelemetry 分布式追踪。
        """
        otel_enabled = self.config_manager.get_config(
            "monitoring.opentelemetry.enabled", False
        )
        if not otel_enabled:
            self.logger.info("OpenTelemetry tracing is disabled.")
            self.tracer = None
            return

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import (
                SERVICE_NAME as ResourceAttributesServiceName,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )

            # Exporter-specific imports will be conditional

            service_name = self.config_manager.get_config(
                "monitoring.opentelemetry.service_name", "AIKnowledgeAssistant"
            )
            exporter_type = self.config_manager.get_config(
                "monitoring.opentelemetry.exporter_type", "console"
            ).lower()
            sampling_rate = self.config_manager.get_config(
                "monitoring.opentelemetry.sampling_rate", 1.0
            )

            resource = Resource(
                attributes={ResourceAttributesServiceName: service_name}
            )

            provider = TracerProvider(
                resource=resource
            )  # sampler can be added here if needed based on sampling_rate

            exporter = None
            if exporter_type == "console":
                exporter = ConsoleSpanExporter()
            elif exporter_type == "otlp_http":
                try:
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                        OTLPSpanExporter as OTLPHttpSpanExporter,
                    )  # noqa

                    otlp_endpoint = self.config_manager.get_config(
                        "monitoring.opentelemetry.otlp_endpoint"
                    )
                    if otlp_endpoint:
                        exporter = OTLPHttpSpanExporter(endpoint=otlp_endpoint)
                    else:
                        self.logger.warning(
                            "OTLP HTTP exporter enabled but 'monitoring.opentelemetry.otlp_endpoint' is not set. Using console exporter as fallback."
                        )
                        exporter = ConsoleSpanExporter()
                except ImportError:
                    self.logger.error(
                        "opentelemetry-exporter-otlp-proto-http library not found for OTLP HTTP exporter. Using console exporter. Please install it."
                    )
                    exporter = ConsoleSpanExporter()
            # Add other exporters like otlp_grpc, jaeger_thrift as needed
            else:
                self.logger.warning(
                    f"Unsupported OpenTelemetry exporter type: {exporter_type}. Using console exporter."
                )
                exporter = ConsoleSpanExporter()

            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

            self.tracer = trace.get_tracer(__name__)
            self.logger.info(
                f"OpenTelemetry tracing initialized. Service: {service_name}, Exporter: {exporter_type}, Sampling Rate: {sampling_rate}"
            )

        except ImportError as e:
            self.logger.error(
                f"OpenTelemetry library not found ({e}). Tracing disabled. Please install required opentelemetry packages."
            )
            self.tracer = None
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
            self.tracer = None

    def start_span(
        self,
        span_name: str,
        parent_context: Optional[
            Any
        ] = None,  # Can be trace.Context or propagation format
        attributes: Optional[Dict[str, Any]] = None,
        kind: Optional[Any] = None,
    ):  # trace.SpanKind
        """
        开始一个新的追踪 Span。
        `parent_context` can be an OpenTelemetry Context object or a context propagated
        from another service (e.g., headers from an HTTP request).
        """
        if not self.tracer:
            # self.log_debug(f"Tracer not available. Cannot start span '{span_name}'.")
            return None  # Or a NoOpSpan

        # Import trace here to avoid issues if otel is not installed
        from opentelemetry import context as otel_context
        from opentelemetry import trace

        actual_kind = kind
        if kind and isinstance(kind, str):  # Allow string for kind for easier config
            try:
                actual_kind = getattr(trace.SpanKind, kind.upper())
            except AttributeError:
                self.log_warning(f"Invalid span kind string: {kind}. Using default.")
                actual_kind = None

        # Handle parent context. If it's a dict (e.g. from headers), try to extract.
        # For simplicity, this example assumes parent_context is either None or a valid OTel Context.
        # Real-world scenarios might need W3CTraceContextPropagator.
        active_context = (
            parent_context if parent_context else otel_context.get_current()
        )

        span = self.tracer.start_span(
            span_name,
            context=active_context,  # otel_context.set_parent(active_context, parent_span_context) if parent_span_context
            kind=actual_kind if actual_kind else trace.SpanKind.INTERNAL,
            attributes=attributes,
        )
        # self.log_debug(f"Started span '{span_name}' with ID {span.get_span_context().span_id if span else 'N/A'}")
        return span

    def end_span(self, span: Optional[Any], exc: Optional[Exception] = None):
        """
        结束一个追踪 Span。
        """
        if not span or not self.tracer:
            return

        from opentelemetry import trace  # Import here

        try:
            if exc:
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            else:
                span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            self.log_error(
                f"Error setting span status or recording exception: {e}", exc_info=True
            )
        finally:
            if hasattr(span, "end"):
                span.end()
                # self.log_debug(f"Ended span '{span.name if hasattr(span, 'name') else 'Unknown'}'")

    def log_audit_event(
        self, event_type: str, user_id: Optional[str], details: Dict[str, Any]
    ):
        """
        记录审计事件。
        TODO: 实现审计日志的持久化，可能存储到 MemoryBankManager 或独立的审计日志系统。
        """
        audit_data = {
            "event_type": event_type,
            "user_id": user_id,
            "details": details,
            "timestamp_iso": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.gmtime(time.time())
            ),  # ISO 8601
        }
        # For now, log audit events as structured info logs
        self.log_info(f"Audit Event: {event_type}", context=audit_data)
        # TODO: 将审计事件存储到 MemoryBankManager 或其他存储 (as per original TODO)
        # if self.memory_bank_manager:
        #     try:
        #         # Assuming memory_bank_manager has a method like store_audit_log
        #         # self.memory_bank_manager.store_audit_log(audit_data)
        #         pass
        #     except Exception as e:
        #         self.log_error(f"Failed to store audit event via MemoryBankManager: {e}", exc_info=True)


# No if __name__ == "__main__": block for production code
