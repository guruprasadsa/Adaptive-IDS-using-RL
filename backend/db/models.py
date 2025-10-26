"""
SQLAlchemy Models for Adaptive IDS
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

db = SQLAlchemy()


class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(64), unique=True, nullable=False)
    flow_id = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    
    # Attack Classification
    class_idx = db.Column(db.Integer, nullable=False)
    class_name = db.Column(db.String(64), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    
    # Network Context
    src_ip = db.Column(db.String(45), nullable=False)
    dst_ip = db.Column(db.String(45), nullable=False)
    src_port = db.Column(db.Integer, nullable=False)
    dst_port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(16), nullable=False)
    
    # Model Metadata
    model_version = db.Column(db.String(32), nullable=False)
    feature_version = db.Column(db.String(32), nullable=False)
    
    # Workflow Management
    status = db.Column(db.String(32), nullable=False, default='NEW')
    assigned_to = db.Column(db.String(128))
    notes = db.Column(db.Text)
    
    # Raw Data
    raw_payload = db.Column(JSONB)
    
    # Enrichment
    src_geo = db.Column(db.String(8))
    dst_geo = db.Column(db.String(8))
    src_reputation = db.Column(db.Float)
    dst_reputation = db.Column(db.Float)
    tags = db.Column(ARRAY(db.Text))
    
    # Dispatch tracking
    destinations = db.Column(ARRAY(db.Text))
    dispatch_status = db.Column(JSONB, default={})
    
    # Legacy fields (for backward compatibility)
    priority = db.Column(db.String(16))
    description = db.Column(db.Text)
    source = db.Column(db.String(64))
    destination = db.Column(db.String(64))
    alert_type = db.Column(db.String(64))
    prediction = db.Column(db.String(128))
    metadata = db.Column(JSONB)
    acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    acknowledged_by = db.Column(db.String(128))
    
    def to_dict(self):
        return {
            'id': self.alert_id,
            'flow_id': self.flow_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'class_idx': self.class_idx,
            'class_name': self.class_name,
            'confidence': self.confidence,
            'severity': self.severity,
            'src_ip': self.src_ip,
            'dst_ip': self.dst_ip,
            'src_port': self.src_port,
            'dst_port': self.dst_port,
            'protocol': self.protocol,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'priority': self.priority,
            'description': self.description,
            'source': self.source,
            'destination': self.destination,
            'prediction': self.prediction,
        }


class Incident(db.Model):
    __tablename__ = 'incidents'
    
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    severity = db.Column(db.String(32), nullable=False)
    assigned_to = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    affected_systems = db.Column(db.Integer, nullable=False, default=0)
    alerts_count = db.Column(db.Integer, nullable=False, default=0)
    related_alerts = db.Column(JSONB, nullable=False, default=[])
    
    def to_dict(self):
        return {
            'id': self.incident_id,
            'title': self.title,
            'status': self.status,
            'severity': self.severity,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_updated_at': self.last_updated_at.isoformat() if self.last_updated_at else None,
            'summary': self.summary,
            'description': self.description,
            'affected_systems': self.affected_systems,
            'alerts_count': self.alerts_count,
            'related_alerts': self.related_alerts if isinstance(self.related_alerts, list) else [],
        }


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='analyst')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime(timezone=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='refresh_tokens')
