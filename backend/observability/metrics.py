"""
Prometheus Metrics for Adaptive IDS
Defines all metrics used across services for monitoring throughput, latency, lag, and error rates.
"""

import logging
from typing import Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)


def init_metrics(registry: Optional[CollectorRegistry] = None) -> CollectorRegistry:
    """
    Initialize metrics registry.
    
    Args:
        registry: Optional custom registry. Defaults to prometheus_client.REGISTRY.
    
    Returns:
        The metrics registry (always REGISTRY for simplicity)
    """
    logger.info("Prometheus metrics initialized (using default REGISTRY)")
    return REGISTRY


def get_metrics_registry() -> CollectorRegistry:
    """Get the metrics registry (always returns default REGISTRY)."""
    return REGISTRY


# ============================================================================
# Packet Processing Metrics
# ============================================================================

packets_processed = Counter(
    'ids_packets_processed_total',
    'Total number of packets processed',
    ['service', 'status'],
    registry=get_metrics_registry()
)

flows_created = Counter(
    'ids_flows_created_total',
    'Total number of flows created',
    ['service'],
    registry=get_metrics_registry()
)

flows_expired = Counter(
    'ids_flows_expired_total',
    'Total number of flows expired',
    ['service', 'reason'],
    registry=get_metrics_registry()
)

features_extracted = Counter(
    'ids_features_extracted_total',
    'Total number of feature vectors extracted',
    ['service', 'feature_version'],
    registry=get_metrics_registry()
)

active_flows_gauge = Gauge(
    'ids_active_flows',
    'Current number of active flows',
    ['service'],
    registry=get_metrics_registry()
)

# ============================================================================
# Model Inference Metrics
# ============================================================================

predictions_made = Counter(
    'ids_predictions_total',
    'Total number of predictions made',
    ['service', 'status', 'class_name'],
    registry=get_metrics_registry()
)

inference_latency = Histogram(
    'ids_inference_latency_seconds',
    'Model inference latency in seconds',
    ['service', 'batch_size_bucket'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0],
    registry=get_metrics_registry()
)

batch_processing_time = Histogram(
    'ids_batch_processing_seconds',
    'Time to process a batch of samples',
    ['service', 'stage'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=get_metrics_registry()
)

model_ready_gauge = Gauge(
    'ids_model_ready',
    'Model readiness status (1=ready, 0=not ready)',
    ['service', 'model_version'],
    registry=get_metrics_registry()
)

scaler_samples_gauge = Gauge(
    'ids_scaler_samples',
    'Number of samples seen by online scaler',
    ['service', 'feature_version'],
    registry=get_metrics_registry()
)

# ============================================================================
# Alerting Metrics
# ============================================================================

alerts_created = Counter(
    'ids_alerts_created_total',
    'Total number of alerts created',
    ['service', 'severity', 'class_name'],
    registry=get_metrics_registry()
)

alerts_dispatched = Counter(
    'ids_alerts_dispatched_total',
    'Total number of alerts dispatched to integrations',
    ['service', 'destination', 'status'],
    registry=get_metrics_registry()
)

alerts_suppressed = Counter(
    'ids_alerts_suppressed_total',
    'Total number of alerts suppressed by filters',
    ['service', 'reason'],
    registry=get_metrics_registry()
)

external_integration_latency = Histogram(
    'ids_external_integration_latency_seconds',
    'Latency of external integration calls',
    ['service', 'integration', 'operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=get_metrics_registry()
)

# ============================================================================
# Kafka Metrics
# ============================================================================

kafka_messages_consumed = Counter(
    'ids_kafka_messages_consumed_total',
    'Total Kafka messages consumed',
    ['service', 'topic', 'status'],
    registry=get_metrics_registry()
)

kafka_messages_produced = Counter(
    'ids_kafka_messages_produced_total',
    'Total Kafka messages produced',
    ['service', 'topic', 'status'],
    registry=get_metrics_registry()
)

kafka_consumer_lag = Gauge(
    'ids_kafka_consumer_lag',
    'Kafka consumer lag in messages',
    ['service', 'topic', 'partition'],
    registry=get_metrics_registry()
)

kafka_produce_latency = Histogram(
    'ids_kafka_produce_latency_seconds',
    'Kafka message production latency',
    ['service', 'topic'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=get_metrics_registry()
)

kafka_consume_latency = Histogram(
    'ids_kafka_consume_latency_seconds',
    'Kafka message consumption latency',
    ['service', 'topic'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=get_metrics_registry()
)

# ============================================================================
# Database Metrics
# ============================================================================

db_operation_time = Histogram(
    'ids_db_operation_seconds',
    'Database operation latency',
    ['service', 'operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=get_metrics_registry()
)

db_operations_total = Counter(
    'ids_db_operations_total',
    'Total database operations',
    ['service', 'operation', 'table', 'status'],
    registry=get_metrics_registry()
)

db_pool_connections = Gauge(
    'ids_db_pool_connections',
    'Database connection pool status',
    ['service', 'state'],
    registry=get_metrics_registry()
)

# ============================================================================
# Drift Detection Metrics
# ============================================================================

drift_detected = Counter(
    'ids_drift_detected_total',
    'Total drift events detected',
    ['service', 'detector_type', 'severity'],
    registry=get_metrics_registry()
)

drift_score = Gauge(
    'ids_drift_score',
    'Current drift score',
    ['service', 'detector_type', 'feature'],
    registry=get_metrics_registry()
)

# ============================================================================
# Error Metrics
# ============================================================================

errors_total = Counter(
    'ids_errors_total',
    'Total errors encountered',
    ['service', 'error_type', 'component'],
    registry=get_metrics_registry()
)

# ============================================================================
# System Health Metrics
# ============================================================================

service_health = Gauge(
    'ids_service_health',
    'Service health status (1=healthy, 0=unhealthy)',
    ['service', 'component'],
    registry=get_metrics_registry()
)

# ============================================================================
# False Positive Rate Tracking
# ============================================================================

false_positives = Counter(
    'ids_false_positives_total',
    'Total false positives marked by analysts',
    ['service', 'class_name', 'severity'],
    registry=get_metrics_registry()
)

true_positives = Counter(
    'ids_true_positives_total',
    'Total true positives confirmed',
    ['service', 'class_name', 'severity'],
    registry=get_metrics_registry()
)

# ============================================================================
# Helper Functions
# ============================================================================

def export_metrics() -> bytes:
    """
    Export metrics in Prometheus text format.
    
    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest(get_metrics_registry())


def get_content_type() -> str:
    """
    Get Prometheus metrics content type.
    
    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
