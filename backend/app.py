from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import torch
import numpy as np
import pandas as pd
import json
import logging
from pathlib import Path
import os
from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional

# Import model from trainer and define local preprocessing helpers
from trainrl import DQN_MLP

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve important paths relative to this file
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "best_model.pth"

# Alternative checkpoint paths to try
CHECKPOINT_PATHS = [
    PROJECT_ROOT / "checkpoints" / "best_model.pth",
    PROJECT_ROOT / "checkpoints" / "dqn_ids_binary_kaggle_v1" / "best_model.pth",
    PROJECT_ROOT / "runs" / "best_model.pth",
]

# Local utility helpers for inference
def safe_numeric_conversion(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Convert specified columns to numeric, handling errors gracefully."""
    cols = columns if columns is not None else df.columns
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def downcast_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """Downcast numeric columns to save memory."""
    for c in df.select_dtypes(include=[np.number]).columns:
        df[c] = pd.to_numeric(df[c], downcast='float')
    return df

def clean_col_names(df: pd.DataFrame) -> pd.DataFrame:
    """Clean column names consistently with training preprocessing."""
    cols = df.columns
    new_cols = []
    for col in cols:
        new_col = col.strip().replace(' ', '_').replace('-', '_').replace('/', '_')
        new_col = ''.join(ch for ch in new_col if ord(ch) < 128)
        new_cols.append(new_col)
    df.columns = new_cols
    return df

# Global variables for model and preprocessing
model = None
features = None
label_classes = None
action_map = None
idx_to_label = None
means = None
stds = None
device = None

def load_model():
    """Load the trained model and preprocessing stats from trainrl.py checkpoint."""
    global model, features, label_classes, action_map, idx_to_label, means, stds, device

    try:
        # Set device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Resolve checkpoint path: env override or common locations
        checkpoint_path: Optional[Path] = None
        checkpoint_env = os.getenv("MODEL_CHECKPOINT")
        if checkpoint_env:
            env_path = Path(checkpoint_env).resolve()
            if env_path.exists():
                checkpoint_path = env_path
            else:
                logger.warning(f"Environment checkpoint path not found: {env_path}")
        if checkpoint_path is None:
            candidates = [
                PROJECT_ROOT / "checkpoints" / "best_model.pth",
                PROJECT_ROOT / "checkpoints" / "final_model.pth",
                PROJECT_ROOT / "runs" / "best_model.pth",
            ]
            for p in candidates:
                if p.exists():
                    checkpoint_path = p
                    break
        if checkpoint_path is None:
            logger.error("No model checkpoint found. Expected one of best_model.pth/final_model.pth under checkpoints/ or runs/.")
            return False

        # PyTorch 2.6+: explicitly set weights_only=False since checkpoint contains numpy/sklearn objects
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)

        # Extract training meta/config
        meta = ckpt.get('meta')
        label_classes = ckpt.get('label_classes')
        cfg = ckpt.get('cfg', {})
        if meta is None or label_classes is None:
            logger.error("Checkpoint missing required keys: 'meta' and 'label_classes'")
            return False

        # Features and normalization stats
        features = meta.get('feature_names') or None
        n_features = int(meta['n_features'])
        means = np.array(meta['means'], dtype=np.float32)
        stds = np.array(meta['stds'], dtype=np.float32)
        if features is None:
            # Fallback to positional features if names not available
            features = [f"feature_{i}" for i in range(n_features)]
        if means.shape[0] != n_features or stds.shape[0] != n_features:
            logger.error("Meta stats size mismatch with n_features")
            return False

        # Label mapping
        action_map = {label: i for i, label in enumerate(label_classes)}
        idx_to_label = {i: label for label, i in action_map.items()}

        # Model params
        hidden_dims = cfg.get('hidden_dims', '256,128')
        if isinstance(hidden_dims, str):
            hidden_dims = [int(x.strip()) for x in hidden_dims.split(',') if x.strip()]
        dropout = cfg.get('dropout', 0.2)

        # Initialize model
        model = DQN_MLP(n_features, len(label_classes), hidden_dims, dropout).to(device)
        model.load_state_dict(ckpt['model_state_dict'])
        model.eval()

        logger.info(f"Model loaded: features={n_features}, classes={len(label_classes)}, path={checkpoint_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def predict_single_sample(data: Dict) -> Dict:
    """Make prediction for a single network traffic sample."""
    global model, features, action_map, idx_to_label, means, stds, device

    if model is None or features is None or means is None or stds is None:
        return {"error": "Model not loaded"}

    try:
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/predict', methods=['POST'])
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

@app.route('/api/alerts', methods=['GET'])
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

@app.route('/api/incidents', methods=['GET'])
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

@app.route('/api/dashboard/stats', methods=['GET'])
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

@app.route('/api/model/retrain', methods=['POST'])
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

@app.route('/api/model/metrics', methods=['GET'])
def get_model_metrics():
    """Get model performance metrics."""
    try:
        metrics = generate_model_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Model metrics endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts/<alert_id>', methods=['GET'])
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

@app.route('/api/incidents/<incident_id>', methods=['GET'])
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

@app.route('/api/alerts/<alert_id>/status', methods=['PATCH'])
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

@app.route('/api/incidents/<incident_id>/status', methods=['PATCH'])
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

# Serve frontend static files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve the frontend application."""
    dist_dir = FRONTEND_DIST
    if path and (dist_dir / path).exists():
        return send_from_directory(str(dist_dir), path)
    else:
        index_file = dist_dir / 'index.html'
        if index_file.exists():
            return send_from_directory(str(dist_dir), 'index.html')
        return jsonify({"error": "Frontend build not found"}), 404

if __name__ == '__main__':
    # Load model on startup
    logger.info("Loading model...")
    if load_model():
        logger.info("Model loaded successfully")
    else:
        logger.warning("Failed to load model - some features may not work")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)