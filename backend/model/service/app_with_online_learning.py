"""
Example integration of drift detection and online learning
with the existing inference service.

This shows how to integrate the components into the FastAPI model service.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging
import json

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.stream.drift_detector import DriftDetectionSystem
from backend.model.service.online_learning import create_service
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IDS Model Service with Online Learning")

# Global state
drift_detector: DriftDetectionSystem = None
online_learning_service = None
model = None

# Prometheus metrics
prediction_counter = Counter('ids_predictions_total', 'Total predictions', ['class'])
prediction_latency = Histogram('ids_prediction_latency_seconds', 'Prediction latency')
drift_severity_gauge = Gauge('ids_current_drift_severity', 'Current drift severity', ['severity'])


class PredictionRequest(BaseModel):
    """Prediction request schema"""
    features: List[float]
    flow_id: str = None
    metadata: Dict = {}


class FeedbackRequest(BaseModel):
    """Analyst feedback schema"""
    flow_id: str
    correct_label: int
    notes: str = ""


class PredictionResponse(BaseModel):
    """Prediction response schema"""
    flow_id: str
    predicted_class: int
    predicted_class_name: str
    confidence: float
    confidence_distribution: List[float]
    drift_severity: str
    timestamp: str


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global drift_detector, online_learning_service, model
    
    logger.info("Initializing model service with online learning...")
    
    # Load configuration
    config_path = Path("config/online_learning.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {}
    
    # Initialize drift detector
    drift_config = config.get('drift_detection', {})
    drift_detector = DriftDetectionSystem({
        'adwin_delta': drift_config.get('adwin', {}).get('delta', 0.002),
        'ddm_warning': drift_config.get('ddm', {}).get('warning_level', 2.0),
        'ddm_drift': drift_config.get('ddm', {}).get('drift_level', 3.0),
        'psi_threshold': drift_config.get('psi', {}).get('threshold', 0.2),
        'js_threshold': drift_config.get('js_divergence', {}).get('threshold', 0.1),
    })
    
    # Initialize baseline from training data
    try:
        X_train = np.load('data/processed/X_train.npy')
        # Use first 1000 samples for baseline
        baseline_features = X_train[:1000]
        feature_names = [f"feat_{i}" for i in range(baseline_features.shape[1])]
        
        # Mock confidence distributions (in production, use actual model outputs)
        baseline_confidences = np.random.dirichlet([1]*15, size=1000)
        
        drift_detector.initialize_baseline(
            baseline_features,
            feature_names,
            baseline_confidences
        )
        logger.info("Drift detector initialized with baseline")
    except Exception as e:
        logger.warning(f"Could not initialize drift baseline: {e}")
    
    # Initialize online learning service
    online_config = config.get('online_learning', {})
    online_learning_service = create_service(str(config_path))
    
    if online_config.get('enabled', True):
        online_learning_service.start()
        logger.info("Online learning service started")
    
    # Load model (placeholder - use your actual model loading)
    logger.info("Model service initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global online_learning_service
    
    if online_learning_service:
        online_learning_service.stop()
        logger.info("Online learning service stopped")


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks
):
    """
    Make prediction with drift detection and buffer update.
    """
    global drift_detector, online_learning_service, model
    
    with prediction_latency.time():
        # Convert features to tensor
        features_array = np.array(request.features)
        features_tensor = torch.FloatTensor(features_array).unsqueeze(0)
        
        # Get prediction (placeholder - use your actual model)
        # output = model(features_tensor)
        # For demo, mock the output
        output = torch.randn(1, 15)  # 15 classes
        softmax_output = torch.softmax(output, dim=1)
        
        predicted_class = output.argmax(dim=1).item()
        confidence = softmax_output.max().item()
        confidence_dist = softmax_output.squeeze().tolist()
        
        # Class names (should match your label_classes.json)
        class_names = [
            'BENIGN', 'DDoS', 'DoS Hulk', 'DoS GoldenEye', 'DoS Slowloris',
            'DoS Slowhttptest', 'FTP-Patator', 'SSH-Patator', 'PortScan',
            'Bot', 'Web Attack Brute Force', 'Web Attack XSS', 
            'Web Attack Sql Injection', 'Infiltration', 'Heartbleed'
        ]
        predicted_class_name = class_names[predicted_class]
        
        # Check drift (non-blocking)
        drift_metrics = None
        if drift_detector:
            try:
                drift_metrics = drift_detector.check_drift(
                    confidence=confidence,
                    is_error=False,  # Unknown until feedback
                    features=features_array,
                    confidence_dist=np.array(confidence_dist)
                )
                
                # Update severity gauge
                severity_map = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
                for sev, val in severity_map.items():
                    drift_severity_gauge.labels(severity=sev).set(
                        1 if drift_metrics.severity == sev else 0
                    )
            except Exception as e:
                logger.error(f"Drift detection failed: {e}")
                drift_metrics = None
        
        # Add to buffer (background task to avoid blocking)
        if online_learning_service:
            background_tasks.add_task(
                add_to_buffer,
                features_array,
                predicted_class,
                confidence,
                request.flow_id
            )
        
        # Update metrics
        prediction_counter.labels(class=predicted_class_name).inc()
        
        # Generate flow_id if not provided
        flow_id = request.flow_id or f"flow_{datetime.utcnow().timestamp()}"
        
        return PredictionResponse(
            flow_id=flow_id,
            predicted_class=predicted_class,
            predicted_class_name=predicted_class_name,
            confidence=confidence,
            confidence_distribution=confidence_dist,
            drift_severity=drift_metrics.severity if drift_metrics else 'unknown',
            timestamp=datetime.utcnow().isoformat()
        )


def add_to_buffer(features: np.ndarray, label: int, confidence: float, flow_id: str):
    """Background task to add sample to buffer"""
    global online_learning_service
    
    try:
        online_learning_service.sample_buffer.add_sample(
            features=features,
            label=label,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )
        logger.debug(f"Added {flow_id} to buffer")
    except Exception as e:
        logger.error(f"Failed to add to buffer: {e}")


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit analyst feedback for a prediction.
    If incorrect, add to false positive buffer.
    """
    global online_learning_service
    
    # In production, retrieve the original prediction from database
    # For demo, we'll accept features in the feedback
    
    # Placeholder: retrieve prediction
    # original_prediction = get_prediction_from_db(feedback.flow_id)
    
    # For demo, assume we have the data
    logger.info(f"Received feedback for {feedback.flow_id}: correct_label={feedback.correct_label}")
    
    # If this was a false positive, add to FP buffer
    # if original_prediction['class'] != feedback.correct_label:
    #     online_learning_service.sample_buffer.add_false_positive(
    #         features=original_prediction['features'],
    #         true_label=feedback.correct_label,
    #         pred_label=original_prediction['class'],
    #         timestamp=datetime.utcnow()
    #     )
    
    return {"status": "success", "message": "Feedback recorded"}


@app.post("/training/trigger")
async def trigger_training(background_tasks: BackgroundTasks):
    """
    Manually trigger a training cycle.
    """
    global online_learning_service
    
    if not online_learning_service:
        raise HTTPException(status_code=503, detail="Online learning service not initialized")
    
    # Run training in background
    background_tasks.add_task(online_learning_service.run_training_cycle)
    
    return {"status": "training_triggered", "message": "Training cycle started in background"}


@app.get("/status")
async def get_status():
    """
    Get service status including drift and online learning stats.
    """
    global drift_detector, online_learning_service
    
    status = {
        "service": "running",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Drift detection status
    if drift_detector:
        drift_summary = drift_detector.get_summary()
        status["drift_detection"] = drift_summary
    
    # Online learning status
    if online_learning_service:
        ol_status = online_learning_service.get_status()
        status["online_learning"] = ol_status
    
    return status


@app.get("/versions")
async def list_versions():
    """
    List all model versions in registry.
    """
    global online_learning_service
    
    if not online_learning_service:
        raise HTTPException(status_code=503, detail="Online learning service not initialized")
    
    versions = online_learning_service.registry.list_versions()
    
    return {
        "total_versions": len(versions),
        "active_version": online_learning_service.registry.active_version,
        "versions": [
            {
                "version_id": v.version_id,
                "timestamp": v.timestamp.isoformat(),
                "status": v.status,
                "metrics": v.validation_metrics,
                "training_samples": v.training_samples
            }
            for v in versions[:10]  # Last 10
        ]
    }


@app.post("/versions/{version_id}/promote")
async def promote_version(version_id: str):
    """
    Promote a specific version to active (rollback).
    """
    global online_learning_service
    
    if not online_learning_service:
        raise HTTPException(status_code=503, detail="Online learning service not initialized")
    
    try:
        online_learning_service.registry.promote_to_active(version_id)
        return {
            "status": "success",
            "message": f"Version {version_id} promoted to active",
            "note": "Restart inference service to load new checkpoint"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    """
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "drift_detector": drift_detector is not None,
        "online_learning": online_learning_service is not None and online_learning_service.running,
        "model_loaded": model is not None
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
