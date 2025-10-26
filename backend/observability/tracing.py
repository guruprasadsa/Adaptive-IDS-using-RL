"""
OpenTelemetry Tracing for Adaptive IDS
Provides distributed tracing across all services with flow_id correlation.
"""

import os
import logging
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

# Global tracer
_tracer: Optional[trace.Tracer] = None
_propagator = TraceContextTextMapPropagator()


def init_tracing(
    service_name: str,
    service_version: str = "2.0.0",
    otlp_endpoint: Optional[str] = None,
    enable_console: bool = False
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service (e.g., "feature-extractor")
        service_version: Service version
        otlp_endpoint: OTLP collector endpoint (e.g., "localhost:4317")
        enable_console: If True, also export to console
    
    Returns:
        Tracer instance
    """
    global _tracer
    
    # Create resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    
    # Create provider
    provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter if endpoint provided
    if otlp_endpoint is None:
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP tracing exporter initialized: {otlp_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to initialize OTLP exporter: {e}")
    
    # Add console exporter for debugging
    if enable_console or os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console tracing exporter enabled")
    
    # Set global provider
    trace.set_tracer_provider(provider)
    
    # Create tracer
    _tracer = trace.get_tracer(service_name, service_version)
    
    logger.info(f"OpenTelemetry tracing initialized for {service_name}")
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    if _tracer is None:
        # Initialize with default settings
        return init_tracing("adaptive-ids", enable_console=False)
    return _tracer


@contextmanager
def trace_kafka_consumption(
    topic: str,
    partition: int,
    offset: int,
    flow_id: Optional[str] = None,
    **attributes
):
    """
    Trace Kafka message consumption.
    
    Args:
        topic: Kafka topic
        partition: Partition number
        offset: Message offset
        flow_id: Optional flow ID for correlation
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        f"kafka.consume.{topic}",
        kind=SpanKind.CONSUMER,
    ) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", topic)
        span.set_attribute("messaging.destination_kind", "topic")
        span.set_attribute("messaging.kafka.partition", partition)
        span.set_attribute("messaging.kafka.offset", offset)
        
        if flow_id:
            span.set_attribute("ids.flow_id", flow_id)
        
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_kafka_production(
    topic: str,
    flow_id: Optional[str] = None,
    **attributes
):
    """
    Trace Kafka message production.
    
    Args:
        topic: Kafka topic
        flow_id: Optional flow ID for correlation
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        f"kafka.produce.{topic}",
        kind=SpanKind.PRODUCER,
    ) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", topic)
        span.set_attribute("messaging.destination_kind", "topic")
        
        if flow_id:
            span.set_attribute("ids.flow_id", flow_id)
        
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_flow_processing(
    flow_id: str,
    operation: str,
    **attributes
):
    """
    Trace flow processing operation.
    
    Args:
        flow_id: Flow identifier for correlation
        operation: Operation name (e.g., "feature_extraction", "aggregation")
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        f"flow.{operation}",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute("ids.flow_id", flow_id)
        span.set_attribute("ids.operation", operation)
        
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_inference(
    flow_id: str,
    batch_size: int,
    model_version: str,
    **attributes
):
    """
    Trace model inference operation.
    
    Args:
        flow_id: Flow identifier for correlation
        batch_size: Batch size
        model_version: Model version
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        "model.inference",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute("ids.flow_id", flow_id)
        span.set_attribute("ml.model.version", model_version)
        span.set_attribute("ml.batch_size", batch_size)
        
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_alert_dispatch(
    alert_id: str,
    flow_id: str,
    severity: str,
    destination: str,
    **attributes
):
    """
    Trace alert dispatching to external integration.
    
    Args:
        alert_id: Alert identifier
        flow_id: Flow identifier for correlation
        severity: Alert severity
        destination: Integration destination (e.g., "syslog", "splunk")
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        f"alert.dispatch.{destination}",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("ids.alert_id", alert_id)
        span.set_attribute("ids.flow_id", flow_id)
        span.set_attribute("ids.alert.severity", severity)
        span.set_attribute("ids.alert.destination", destination)
        
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_function(operation_name: Optional[str] = None):
    """
    Decorator to trace a function.
    
    Args:
        operation_name: Optional operation name (defaults to function name)
    
    Example:
        @trace_function("process_packet")
        def my_function(packet):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            op_name = operation_name or func.__name__
            
            with tracer.start_as_current_span(op_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def inject_trace_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """
    Inject current trace context into carrier (e.g., Kafka headers).
    
    Args:
        carrier: Dictionary to inject trace context into
    
    Returns:
        Carrier with trace context
    """
    _propagator.inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]):
    """
    Extract trace context from carrier and set as current context.
    
    Args:
        carrier: Dictionary containing trace context
    """
    return _propagator.extract(carrier)
