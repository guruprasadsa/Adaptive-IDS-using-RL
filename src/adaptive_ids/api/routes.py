"""
API routes for Adaptive IDS

This module contains all the API endpoints for the Adaptive IDS system,
including prediction, alerts, incidents, and dashboard endpoints.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List

from flask import Blueprint, request, jsonify, current_app

from ..utils.preprocessing import safe_numeric_conversion, downcast_numeric_df, clean_col_names

# Create blueprint
api_bp = Blueprint('api', __name__)

# Setup logging
logger = logging.getLogger(__name__)

# Global variables for model and preprocessing (would be managed by a service in production)
model = None
features = None
label_classes = None
action_map = None
idx_to_label = None
means = None
stds = None
device = None


def load_model():
    """Load the trained model and preprocessing stats."""
    global model, features, label_classes, action_map, idx_to_label, means, stds, device
    
    # This would be implemented to load the actual model
    # For now, return True to indicate "loaded"
    logger.info("Model loading would be implemented here")
    return True


def predict_single_sample(data: Dict) -> Dict:
    """Make prediction for a single network traffic sample."""
    global model, features, action_map, idx_to_label, means, stds, device

    if model is None or features is None or means is None or stds is None:
        return {"error": "Model not loaded"}

    try:
        import pandas as pd
        import numpy as np
        import torch
        
        # Create DataFrame with the input data
        df = pd.DataFrame([data])
        df = clean_col_names(df)

        # Prepare features in the correct order
        X = pd.DataFrame(columns=features)
        for feat in features:
            if feat in df.columns:
                X[feat] = df[feat]
            else:
                X[feat] = 0  # default for missing

        # Convert to numeric and handle errors
        X = safe_numeric_conversion(X)
        X = downcast_numeric_df(X)
        X.replace([np.inf, -np.inf], np.nan, inplace=True)

        # Fill NaN and normalize using training statistics
        for i, col in enumerate(features):
            mean_val = means[i] if i < len(means) and not np.isnan(means[i]) else 0.0
            X[col].fillna(mean_val, inplace=True)
        X_scaled = ((X.values.astype(np.float32) - means) / (stds + 1e-9)).astype(np.float32)

        # Make prediction
        with torch.no_grad():
            states = torch.tensor(X_scaled, device=device)
            q_values = model(states)
            probs = torch.softmax(q_values, dim=1).cpu().numpy()
            preds = q_values.argmax(dim=1).cpu().numpy()

        # Get prediction details
        pred_idx = int(preds[0])
        pred_label = idx_to_label.get(pred_idx, str(pred_idx))
        confidence = float(probs[0][pred_idx])

        # Probabilities dict in index order
        probabilities = {idx_to_label[i]: float(probs[0][i]) for i in range(len(probs[0]))}

        return {
            "prediction": pred_label,
            "prediction_index": pred_idx,
            "confidence": confidence,
            "probabilities": probabilities,
            "features_used": list(X.columns)
        }

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)}


def generate_mock_alerts() -> List[Dict]:
    """Generate mock alerts for demonstration."""
    alert_types = [
        "Suspicious Network Activity",
        "Potential DDoS Attack",
        "Unauthorized Access Attempt",
        "Malware Detection",
        "Data Exfiltration Attempt"
    ]
    
    sources = [
        "192.168.1.100",
        "10.0.0.50",
        "172.16.0.25",
        "203.0.113.10",
        "198.51.100.5"
    ]
    
    alerts = []
    for i in range(50):
        alert = {
            "id": f"ALT-{i+1:04d}",
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 1440))).isoformat(),
            "type": random.choice(alert_types),
            "source": random.choice(sources),
            "priority": random.choice(["low", "medium", "high", "critical"]),
            "status": random.choice(["new", "investigating", "resolved", "false_positive"]),
            "description": f"Detected {random.choice(['unusual', 'suspicious', 'anomalous'])} activity from {random.choice(sources)}",
            "confidence": round(random.uniform(0.6, 0.95), 2)
        }
        alerts.append(alert)
    
    return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)


def generate_mock_incidents() -> List[Dict]:
    """Generate mock incidents for demonstration."""
    incident_types = [
        "Data Breach",
        "Ransomware Attack",
        "Insider Threat",
        "Advanced Persistent Threat",
        "Zero-day Exploit"
    ]
    
    incidents = []
    for i in range(10):
        incident = {
            "id": f"INC-{i+1:04d}",
            "title": f"{random.choice(incident_types)} Incident",
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "status": random.choice(["open", "investigating", "contained", "resolved"]),
            "createdAt": (datetime.now() - timedelta(hours=random.randint(1, 168))).isoformat(),
            "lastUpdatedAt": (datetime.now() - timedelta(minutes=random.randint(1, 1440))).isoformat(),
            "description": f"Investigation of {random.choice(['suspicious', 'malicious', 'unauthorized'])} activity",
            "affectedSystems": random.randint(1, 10),
            "alertsCount": random.randint(1, 25)
        }
        incidents.append(incident)
    
    return sorted(incidents, key=lambda x: x["createdAt"], reverse=True)


def generate_model_metrics() -> Dict:
    """Generate mock model performance metrics."""
    return {
        "accuracy": round(random.uniform(0.75, 0.95), 3),
        "precision_macro": round(random.uniform(0.70, 0.90), 3),
        "recall_macro": round(random.uniform(0.65, 0.85), 3),
        "f1_macro": round(random.uniform(0.70, 0.88), 3),
        "roc_auc": round(random.uniform(0.75, 0.95), 3),
        "balanced_accuracy": round(random.uniform(0.70, 0.90), 3),
        "total_predictions": random.randint(10000, 100000),
        "false_positives": random.randint(100, 1000),
        "false_negatives": random.randint(50, 500),
        "true_positives": random.randint(5000, 15000),
        "true_negatives": random.randint(8000, 20000)
    }


# API Routes

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "timestamp": datetime.now().isoformat()
    })


@api_bp.route('/predict', methods=['POST'])
def predict():
    """Make prediction for network traffic data."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        result = predict_single_sample(data)
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Prediction endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Get alerts with optional filtering."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        priority = request.args.get('priority', 'all')
        status = request.args.get('status', 'all')
        search = request.args.get('search', '')
        
        # Generate mock alerts
        alerts = generate_mock_alerts()
        
        # Apply filters
        filtered_alerts = alerts
        if priority != 'all':
            filtered_alerts = [a for a in filtered_alerts if a['priority'] == priority]
        if status != 'all':
            filtered_alerts = [a for a in filtered_alerts if a['status'] == status]
        if search:
            filtered_alerts = [
                a for a in filtered_alerts 
                if search.lower() in a['description'].lower() or 
                   search.lower() in a['source'].lower()
            ]
        
        # Pagination
        total = len(filtered_alerts)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_alerts = filtered_alerts[start_idx:end_idx]
        
        return jsonify({
            "alerts": paginated_alerts,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        })
        
    except Exception as e:
        logger.error(f"Alerts endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/incidents', methods=['GET'])
def get_incidents():
    """Get incidents with optional filtering."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        severity = request.args.get('severity', 'all')
        status = request.args.get('status', 'all')
        search = request.args.get('search', '')
        
        # Generate mock incidents
        incidents = generate_mock_incidents()
        
        # Apply filters
        filtered_incidents = incidents
        if severity != 'all':
            filtered_incidents = [i for i in filtered_incidents if i['severity'] == severity]
        if status != 'all':
            filtered_incidents = [i for i in filtered_incidents if i['status'] == status]
        if search:
            filtered_incidents = [
                i for i in filtered_incidents 
                if search.lower() in i['title'].lower() or 
                   search.lower() in i['id'].lower()
            ]
        
        # Pagination
        total = len(filtered_incidents)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_incidents = filtered_incidents[start_idx:end_idx]
        
        return jsonify({
            "incidents": paginated_incidents,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        })
        
    except Exception as e:
        logger.error(f"Incidents endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics."""
    try:
        # Generate mock stats
        alerts = generate_mock_alerts()
        incidents = generate_mock_incidents()
        model_metrics = generate_model_metrics()
        
        # Calculate stats
        critical_alerts = len([a for a in alerts if a['priority'] == 'critical'])
        open_incidents = len([i for i in incidents if i['status'] in ['open', 'investigating']])
        
        return jsonify({
            "total_alerts": len(alerts),
            "critical_alerts": critical_alerts,
            "open_incidents": open_incidents,
            "total_incidents": len(incidents),
            "model_metrics": model_metrics,
            "recent_alerts": alerts[:5],
            "recent_incidents": incidents[:5]
        })
        
    except Exception as e:
        logger.error(f"Dashboard stats endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/model/retrain', methods=['POST'])
def retrain_model():
    """Trigger model retraining."""
    try:
        # This would typically trigger an async retraining process
        # For now, just return a success message
        return jsonify({
            "message": "Model retraining initiated",
            "status": "started",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Retrain endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/model/metrics', methods=['GET'])
def get_model_metrics():
    """Get model performance metrics."""
    try:
        metrics = generate_model_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Model metrics endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/alerts/<alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Get a specific alert by ID."""
    try:
        alerts = generate_mock_alerts()
        alert = next((a for a in alerts if a['id'] == alert_id), None)
        if alert:
            return jsonify(alert)
        else:
            return jsonify({"error": "Alert not found"}), 404
    except Exception as e:
        logger.error(f"Get alert endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/incidents/<incident_id>', methods=['GET'])
def get_incident(incident_id):
    """Get a specific incident by ID."""
    try:
        incidents = generate_mock_incidents()
        incident = next((i for i in incidents if i['id'] == incident_id), None)
        if incident:
            return jsonify(incident)
        else:
            return jsonify({"error": "Incident not found"}), 404
    except Exception as e:
        logger.error(f"Get incident endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/alerts/<alert_id>/status', methods=['PATCH'])
def update_alert_status(alert_id):
    """Update alert status."""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({"error": "Status is required"}), 400
        
        # In a real implementation, this would update the database
        # For now, return a mock updated alert
        alerts = generate_mock_alerts()
        alert = next((a for a in alerts if a['id'] == alert_id), None)
        if alert:
            alert['status'] = data['status']
            return jsonify(alert)
        else:
            return jsonify({"error": "Alert not found"}), 404
    except Exception as e:
        logger.error(f"Update alert status endpoint error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/incidents/<incident_id>/status', methods=['PATCH'])
def update_incident_status(incident_id):
    """Update incident status."""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({"error": "Status is required"}), 400
        
        # In a real implementation, this would update the database
        # For now, return a mock updated incident
        incidents = generate_mock_incidents()
        incident = next((i for i in incidents if i['id'] == incident_id), None)
        if incident:
            incident['status'] = data['status']
            return jsonify(incident)
        else:
            return jsonify({"error": "Incident not found"}), 404
    except Exception as e:
        logger.error(f"Update incident status endpoint error: {e}")
        return jsonify({"error": str(e)}), 500
