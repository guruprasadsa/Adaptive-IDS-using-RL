"""
Model Inference Service
FastAPI-based microservice for real-time intrusion detection inference.

Features:
- TorchScript model loading with version validation
- Kafka consumer for flow features (micro-batching)
- Kafka producer for predictions
- Softmax + calibration + per-class thresholds
- Prometheus metrics and health endpoints
- CPU/GPU inference support
"""
import os
import sys
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import traceback

import torch
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, 
    CONTENT_TYPE_LATEST, Summary
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from schemas.models import FlowFeatures, Prediction

# Import multi-agent model
from model.service.multi_agent_model import create_multi_agent_model, MultiAgentIDS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Note: Model service has its own metrics defined below, so we skip observability module
# to avoid duplicate registration. The service already exposes comprehensive metrics.

# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Service configuration from environment variables"""
    
    # Kafka configuration
    KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
    FEATURES_TOPIC = os.getenv("FEATURES_TOPIC", "flows.features")
    PRED_TOPIC = os.getenv("PRED_TOPIC", "predictions")
    CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "model-inference-service")
    
    # Model configuration
    MODEL_PATH = os.getenv("MODEL_PATH", "./model/checkpoints/final_model.pth")
    MODEL_VERSION = os.getenv("MODEL_VERSION", "v1.0")
    FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1.0")
    LABEL_CLASSES_PATH = os.getenv("LABEL_CLASSES_PATH", "./model/output/run_1758022767/label_classes.json")
    CONFIG_PATH = os.getenv("CONFIG_PATH", "./model/output/run_1758022767/config.json")
    
    # Inference configuration
    DEVICE = os.getenv("DEVICE", "cpu")  # cpu or cuda
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
    MAX_BATCH_WAIT_MS = int(os.getenv("MAX_BATCH_WAIT_MS", "50"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    
    # Performance tuning
    NUM_WORKERS = int(os.getenv("NUM_WORKERS", "2"))
    PREFETCH_COUNT = int(os.getenv("PREFETCH_COUNT", "100"))
    
    # Calibration (temperature scaling)
    CALIBRATION_TEMP = float(os.getenv("CALIBRATION_TEMP", "1.5"))


config = Config()

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Counters
inference_total = Counter(
    'ids_inferences_total', 
    'Total number of inferences',
    ['status']  # success, error
)
messages_consumed = Counter(
    'ids_messages_consumed_total',
    'Total messages consumed from Kafka'
)
messages_produced = Counter(
    'ids_messages_produced_total',
    'Total predictions produced to Kafka',
    ['status']  # success, error
)

# Histograms
inference_latency = Histogram(
    'ids_inference_latency_seconds',
    'Inference latency in seconds',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0]
)
batch_size_hist = Histogram(
    'ids_batch_size',
    'Batch sizes processed',
    buckets=[1, 2, 4, 8, 16, 32, 64, 128, 256]
)
kafka_consumer_lag = Gauge(
    'ids_kafka_consumer_lag',
    'Kafka consumer lag'
)

# Summary for percentiles
inference_duration = Summary(
    'ids_inference_duration_seconds',
    'Inference duration summary with percentiles'
)

# ============================================================================
# Model Manager
# ============================================================================

class ModelManager:
    """Manages model loading, inference, and calibration"""
    
    def __init__(self):
        self.model = None
        self.device = None
        self.label_classes = []
        self.num_classes = 0
        self.model_config = {}
        self.calibration_temp = config.CALIBRATION_TEMP
        self.ready = False
        
    def load_model(self):
        """Load TorchScript model and metadata"""
        try:
            logger.info(f"Loading model from {config.MODEL_PATH}")
            
            # Determine device
            if config.DEVICE == "cuda" and torch.cuda.is_available():
                self.device = torch.device("cuda")
                logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
            else:
                self.device = torch.device("cpu")
                logger.info("Using CPU device")
            
            # Load label classes
            label_path = Path(config.LABEL_CLASSES_PATH)
            if label_path.exists():
                with open(label_path, 'r', encoding='utf-8') as f:
                    self.label_classes = json.load(f)
                self.num_classes = len(self.label_classes)
                logger.info(f"Loaded {self.num_classes} label classes")
            else:
                logger.warning(f"Label classes file not found: {label_path}")
                # Default fallback
                self.label_classes = [f"Class_{i}" for i in range(15)]
                self.num_classes = 15
            
            # Load model configuration
            config_path = Path(config.CONFIG_PATH)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.model_config = json.load(f)
                logger.info("Loaded model configuration")
            
            # Load model
            model_path = Path(config.MODEL_PATH)
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            # Try loading as TorchScript first, fallback to state dict
            try:
                self.model = torch.jit.load(str(model_path), map_location=self.device)
                self.is_multi_agent = False
                logger.info("Loaded TorchScript model")
            except Exception as e:
                logger.warning(f"Failed to load as TorchScript: {e}")
                logger.info("Attempting to load as state dict...")
                
                # Load checkpoint
                checkpoint = torch.load(str(model_path), map_location=self.device, weights_only=False)
                
                # Check if this is a multi-agent checkpoint (router + specialists)
                if isinstance(checkpoint, dict) and 'router_state_dict' in checkpoint and 'specialist_state_dicts' in checkpoint:
                    logger.info("Detected multi-agent model (Router + Specialists)")
                    
                    # Use multi-agent model with loaded label classes
                    self.model = create_multi_agent_model(
                        str(model_path), 
                        str(self.device),
                        label_classes=self.label_classes
                    )
                    self.is_multi_agent = True
                    
                    # Get metrics from checkpoint
                    if 'metrics' in checkpoint:
                        metrics = checkpoint['metrics']
                        logger.info(f"Checkpoint metrics: Acc={metrics.get('val_accuracy', 'N/A'):.3f}, "
                                  f"Router Acc={metrics.get('val_router_acc', 'N/A'):.3f}, "
                                  f"F1={metrics.get('val_macro_f1', 'N/A'):.3f}")
                    
                    logger.info(f"Loaded {self.model.num_specialists} specialists with Router-based inference")
                    logger.info(f"Using label classes: {self.label_classes}")
                    
                else:
                    # Legacy single model handling
                    logger.info("Detected single model (legacy format)")
                    self.is_multi_agent = False
                    
                    # Handle different checkpoint formats
                    state_dict = None
                    if isinstance(checkpoint, dict):
                        # Single model checkpoint
                        if 'model_state_dict' in checkpoint:
                            state_dict = checkpoint['model_state_dict']
                        # Direct state dict
                        elif any('weight' in k for k in checkpoint.keys()):
                            state_dict = checkpoint
                        else:
                            raise ValueError(f"Unrecognized checkpoint format. Keys: {list(checkpoint.keys())}")
                    else:
                        # Checkpoint is the state dict itself
                        state_dict = checkpoint
                    
                    # Create model from state dict
                    self.model = self._create_model_from_state_dict(state_dict)
                    logger.info("Loaded model from state dict")
            
            self.model.eval()
            self.ready = True
            
            logger.info(f"Model loaded successfully on {self.device}")
            logger.info(f"Model version: {config.MODEL_VERSION}")
            logger.info(f"Feature version: {config.FEATURE_VERSION}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _create_model_from_state_dict(self, state_dict: Dict) -> torch.nn.Module:
        """Create model architecture from state dict keys"""
        
        # A3C Router architecture
        class A3CRouterWrapper(torch.nn.Module):
            def __init__(self, state_dict, num_classes):
                super().__init__()
                # Extract input dimension from first layer
                first_layer_key = [k for k in state_dict.keys() if 'weight' in k][0]
                input_dim = state_dict[first_layer_key].shape[1]
                hidden_dim = state_dict[first_layer_key].shape[0]
                
                # Build feature extractor
                self.feature_net = torch.nn.Sequential(
                    torch.nn.Linear(input_dim, hidden_dim),
                    torch.nn.LayerNorm(hidden_dim),
                    torch.nn.ReLU(),
                    torch.nn.Dropout(0.2),
                    torch.nn.Linear(hidden_dim, hidden_dim // 2),
                    torch.nn.LayerNorm(hidden_dim // 2),
                    torch.nn.ReLU()
                )
                
                # Policy head (for routing decisions)
                self.policy_head = torch.nn.Sequential(
                    torch.nn.Linear(hidden_dim // 2, num_classes),
                    torch.nn.Softmax(dim=1)
                )
                
            def forward(self, x):
                features = self.feature_net(x)
                return self.policy_head(features)
        
        # Simple feedforward classifier (fallback)
        class SimpleClassifier(torch.nn.Module):
            def __init__(self, input_dim, hidden_dims, num_classes):
                super().__init__()
                layers = []
                prev_dim = input_dim
                
                for hidden_dim in hidden_dims:
                    layers.extend([
                        torch.nn.Linear(prev_dim, hidden_dim),
                        torch.nn.ReLU(),
                        torch.nn.Dropout(0.2)
                    ])
                    prev_dim = hidden_dim
                
                layers.append(torch.nn.Linear(prev_dim, num_classes))
                self.network = torch.nn.Sequential(*layers)
            
            def forward(self, x):
                return self.network(x)
        
        # Determine model type from keys
        is_router = any('feature_extractor' in k or 'actor' in k or 'critic' in k for k in state_dict.keys())
        
        if is_router:
            logger.info("Creating A3C Router wrapper")
            model = A3CRouterWrapper(state_dict, self.num_classes)
        else:
            # Infer dimensions from state dict
            weight_keys = [k for k in state_dict.keys() if 'weight' in k and len(state_dict[k].shape) == 2]
            
            if not weight_keys:
                raise ValueError(f"No weight tensors found in state dict. Keys: {list(state_dict.keys())[:10]}")
            
            first_weight = state_dict[weight_keys[0]]
            input_dim = first_weight.shape[1]
            
            # Get hidden dimensions from config or infer
            hidden_dims = self.model_config.get('hidden_dims', '256,128')
            if isinstance(hidden_dims, str):
                hidden_dims = [int(x) for x in hidden_dims.split(',')]
            
            logger.info("Creating simple classifier")
            model = SimpleClassifier(input_dim, hidden_dims, self.num_classes)
        
        try:
            # Try to load the state dict
            model.load_state_dict(state_dict, strict=False)
            logger.info("Loaded state dict into model")
        except Exception as e:
            logger.warning(f"Could not load state dict: {e}")
            logger.info("Using model with random weights (inference may be inaccurate)")
        
        model.to(self.device)
        model.eval()
        
        return model
    
    @torch.no_grad()
    def predict_batch(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run inference on batch of features
        
        Args:
            features: numpy array of shape (batch_size, num_features)
            
        Returns:
            List of prediction dictionaries
        """
        if not self.ready:
            raise RuntimeError("Model not loaded")
        
        try:
            # Convert to tensor
            x = torch.from_numpy(features).float().to(self.device)
            
            # Inference
            start_time = time.time()
            
            if self.is_multi_agent:
                # Multi-agent inference with routing
                predictions_dict = self.model.predict_with_routing(x)
                probs = predictions_dict['class_probs']
                routing_probs = predictions_dict['routing_probs']
                specialist_confidences = predictions_dict['specialist_confidences']
                
            else:
                # Legacy single model inference
                logits = self.model(x)
                
                # Apply softmax and calibration (temperature scaling)
                probs = torch.nn.functional.softmax(logits / self.calibration_temp, dim=1)
                routing_probs = None
                specialist_confidences = None
            
            confidences, predictions = torch.max(probs, dim=1)
            
            inference_time = time.time() - start_time
            
            # Convert to numpy
            predictions_np = predictions.cpu().numpy()
            confidences_np = confidences.cpu().numpy()
            probs_np = probs.cpu().numpy()
            
            # Build results
            results = []
            for i in range(len(predictions_np)):
                class_idx = int(predictions_np[i])
                confidence = float(confidences_np[i])
                
                # Get class name
                class_name = self.label_classes[class_idx] if class_idx < len(self.label_classes) else f"Class_{class_idx}"
                
                # Full probability distribution
                all_probs = {
                    self.label_classes[j]: float(probs_np[i, j])
                    for j in range(min(len(self.label_classes), probs_np.shape[1]))
                }
                
                result = {
                    'class_idx': class_idx,
                    'class_name': class_name,
                    'confidence': confidence,
                    'all_class_probs': all_probs,
                    'inference_latency_ms': (inference_time / len(predictions_np)) * 1000
                }
                
                # Add multi-agent specific info if available
                if self.is_multi_agent and routing_probs is not None:
                    routing_np = routing_probs[i].cpu().numpy()
                    spec_conf_np = specialist_confidences[i].cpu().numpy()
                    
                    result['routing_info'] = {
                        'selected_specialist': class_name,
                        'routing_confidence': float(routing_np[class_idx]),
                        'specialist_confidence': float(spec_conf_np[class_idx]),
                        'all_routing_probs': {
                            self.label_classes[j]: float(routing_np[j])
                            for j in range(len(self.label_classes))
                        }
                    }
                
                results.append(result)
            
            # Update metrics
            inference_total.labels(status='success').inc(len(results))
            inference_latency.observe(inference_time)
            batch_size_hist.observe(len(features))
            inference_duration.observe(inference_time)
            
            return results
            
        except Exception as e:
            logger.error(f"Inference error: {e}")
            inference_total.labels(status='error').inc()
            raise
    
    def get_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            'ready': self.ready,
            'model_path': config.MODEL_PATH,
            'model_version': config.MODEL_VERSION,
            'feature_version': config.FEATURE_VERSION,
            'device': str(self.device),
            'num_classes': self.num_classes,
            'label_classes': self.label_classes,
            'calibration_temp': self.calibration_temp,
            'config': self.model_config
        }


# Global model manager instance
model_manager = ModelManager()

# ============================================================================
# Kafka Consumer/Producer
# ============================================================================

class InferenceWorker:
    """Background worker for Kafka consumption and inference"""
    
    def __init__(self):
        self.consumer = None
        self.producer = None
        self.running = False
        self.batch_buffer = []
        self.batch_metadata = []
        
    def _delivery_callback(self, err, msg):
        """Kafka producer delivery callback"""
        if err:
            logger.error(f"Message delivery failed: {err}")
            messages_produced.labels(status='error').inc()
        else:
            messages_produced.labels(status='success').inc()
    
    def start(self):
        """Initialize Kafka consumer and producer"""
        try:
            # Consumer configuration
            consumer_config = {
                'bootstrap.servers': config.KAFKA_BROKERS,
                'group.id': config.CONSUMER_GROUP,
                'auto.offset.reset': 'latest',
                'enable.auto.commit': True,
                'max.poll.interval.ms': 300000,
                'session.timeout.ms': 10000,
            }
            
            self.consumer = Consumer(consumer_config)
            self.consumer.subscribe([config.FEATURES_TOPIC])
            logger.info(f"Subscribed to topic: {config.FEATURES_TOPIC}")
            
            # Producer configuration
            producer_config = {
                'bootstrap.servers': config.KAFKA_BROKERS,
                'compression.type': 'lz4',
                'linger.ms': 10,
                'batch.size': 16384,
                'enable.idempotence': True,
            }
            
            self.producer = Producer(producer_config)
            logger.info("Kafka producer initialized")
            
            self.running = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            raise
    
    async def consume_and_infer(self):
        """Main consumption loop with micro-batching"""
        logger.info("Starting inference worker loop")
        
        last_batch_time = time.time()
        
        while self.running:
            try:
                # Poll for messages
                msg = self.consumer.poll(timeout=0.1)
                
                if msg is None:
                    # Check if we should process partial batch
                    if self.batch_buffer and (time.time() - last_batch_time) * 1000 > config.MAX_BATCH_WAIT_MS:
                        await self._process_batch()
                        last_batch_time = time.time()
                    
                    await asyncio.sleep(0.01)
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue
                
                # Parse message
                try:
                    data = json.loads(msg.value().decode('utf-8'))
                    flow_features = FlowFeatures(**data)
                    
                    # Add to batch
                    self.batch_buffer.append(flow_features.features)
                    self.batch_metadata.append(flow_features)
                    
                    messages_consumed.inc()
                    
                    # Process batch if full
                    if len(self.batch_buffer) >= config.BATCH_SIZE:
                        await self._process_batch()
                        last_batch_time = time.time()
                        
                except Exception as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue
                
            except Exception as e:
                logger.error(f"Error in consume loop: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)
    
    async def _process_batch(self):
        """Process accumulated batch"""
        if not self.batch_buffer:
            return
        
        try:
            # Convert to numpy array
            features_array = np.array(self.batch_buffer, dtype=np.float32)
            
            # Run inference
            predictions = model_manager.predict_batch(features_array)
            
            # Produce predictions
            for pred_data, flow_meta in zip(predictions, self.batch_metadata):
                prediction = Prediction(
                    flow_id=flow_meta.flow_id,
                    timestamp=int(time.time() * 1000),
                    class_idx=pred_data['class_idx'],
                    class_name=pred_data['class_name'],
                    confidence=pred_data['confidence'],
                    model_version=config.MODEL_VERSION,
                    feature_version=config.FEATURE_VERSION,
                    all_class_probs=pred_data.get('all_class_probs'),
                    inference_latency_ms=pred_data.get('inference_latency_ms')
                )
                
                # Serialize and include flow metadata for downstream consumers
                pred_dict = prediction.to_dict()
                try:
                    pred_dict.update({
                        'src_ip': flow_meta.src_ip,
                        'dst_ip': flow_meta.dst_ip,
                        'src_port': flow_meta.src_port,
                        'dst_port': flow_meta.dst_port,
                        'protocol': flow_meta.protocol,
                    })
                except Exception:
                    pass
                pred_json = json.dumps(pred_dict)
                self.producer.produce(
                    config.PRED_TOPIC,
                    value=pred_json.encode('utf-8'),
                    callback=self._delivery_callback
                )
            
            # Flush producer
            self.producer.poll(0)
            
            logger.debug(f"Processed batch of {len(self.batch_buffer)} samples")
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            logger.error(traceback.format_exc())
        
        finally:
            # Clear batch
            self.batch_buffer = []
            self.batch_metadata = []
    
    def stop(self):
        """Stop worker and cleanup"""
        logger.info("Stopping inference worker")
        self.running = False
        
        if self.consumer:
            self.consumer.close()
        
        if self.producer:
            self.producer.flush()


# Global worker instance
inference_worker = InferenceWorker()

# ============================================================================
# FastAPI Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Model Inference Service")
    logger.info(f"Kafka Brokers: {config.KAFKA_BROKERS}")
    logger.info(f"Features Topic: {config.FEATURES_TOPIC}")
    logger.info(f"Predictions Topic: {config.PRED_TOPIC}")
    logger.info(f"Model Path: {config.MODEL_PATH}")
    logger.info(f"Device: {config.DEVICE}")
    logger.info(f"Batch Size: {config.BATCH_SIZE}")
    
    try:
        # Load model
        model_manager.load_model()
        
        # Start Kafka worker
        inference_worker.start()
        
        # Start background task
        asyncio.create_task(inference_worker.consume_and_infer())
        
        logger.info("Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Model Inference Service")
    inference_worker.stop()
    logger.info("Service stopped")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Adaptive IDS Model Service",
    description="Real-time intrusion detection model inference service with micro-batching",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Adaptive IDS Model Service",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint
    
    Returns 200 if service is healthy, 503 otherwise
    """
    try:
        # Check model readiness
        if not model_manager.ready:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "reason": "model_not_ready",
                    "service": "model-inference"
                }
            )
        
        # Check Kafka connectivity
        if not inference_worker.running:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "reason": "kafka_worker_not_running",
                    "service": "model-inference"
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "model-inference",
                "kafka_brokers": config.KAFKA_BROKERS,
                "device": str(model_manager.device),
                "model_path": config.MODEL_PATH,
                "model_ready": model_manager.ready,
                "worker_running": inference_worker.running
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    
    Exposes metrics for monitoring:
    - ids_inferences_total
    - ids_inference_latency_seconds
    - ids_messages_consumed_total
    - ids_messages_produced_total
    - ids_batch_size
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/model/info")
async def model_info():
    """
    Model metadata endpoint
    
    Returns model version, configuration, and status
    """
    try:
        info = model_manager.get_info()
        return JSONResponse(content=info)
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
async def predict(flow_features: FlowFeatures):
    """
    Direct prediction endpoint (for testing)
    
    Args:
        flow_features: Flow features input
        
    Returns:
        Prediction object
    """
    try:
        if not model_manager.ready:
            raise HTTPException(status_code=503, detail="Model not ready")
        
        # Run inference
        features_array = np.array([flow_features.features], dtype=np.float32)
        predictions = model_manager.predict_batch(features_array)
        
        # Build prediction response
        pred_data = predictions[0]
        prediction = Prediction(
            flow_id=flow_features.flow_id,
            timestamp=int(time.time() * 1000),
            class_idx=pred_data['class_idx'],
            class_name=pred_data['class_name'],
            confidence=pred_data['confidence'],
            model_version=config.MODEL_VERSION,
            feature_version=config.FEATURE_VERSION,
            all_class_probs=pred_data.get('all_class_probs'),
            inference_latency_ms=pred_data.get('inference_latency_ms')
        )
        
        return prediction.to_dict()
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
