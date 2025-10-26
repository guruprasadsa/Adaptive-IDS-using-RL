"""
Observability Module
Centralized Prometheus metrics and OpenTelemetry tracing for Adaptive IDS
"""

from .metrics import (
    init_metrics,
    get_metrics_registry,
    # Metric instances
    packets_processed,
    flows_created,
    flows_expired,
    features_extracted,
    predictions_made,
    alerts_created,
    alerts_dispatched,
    kafka_messages_consumed,
    kafka_messages_produced,
    kafka_consumer_lag,
    inference_latency,
    batch_processing_time,
    db_operation_time,
    external_integration_latency,
    active_flows_gauge,
    scaler_samples_gauge,
    model_ready_gauge,
)

from .tracing import (
    init_tracing,
    get_tracer,
    trace_kafka_consumption,
    trace_kafka_production,
    trace_flow_processing,
    trace_inference,
    trace_alert_dispatch,
)

__all__ = [
    # Initialization
    'init_metrics',
    'init_tracing',
    'get_metrics_registry',
    'get_tracer',
    
    # Metrics
    'packets_processed',
    'flows_created',
    'flows_expired',
    'features_extracted',
    'predictions_made',
    'alerts_created',
    'alerts_dispatched',
    'kafka_messages_consumed',
    'kafka_messages_produced',
    'kafka_consumer_lag',
    'inference_latency',
    'batch_processing_time',
    'db_operation_time',
    'external_integration_latency',
    'active_flows_gauge',
    'scaler_samples_gauge',
    'model_ready_gauge',
    
    # Tracing helpers
    'trace_kafka_consumption',
    'trace_kafka_production',
    'trace_flow_processing',
    'trace_inference',
    'trace_alert_dispatch',
]
