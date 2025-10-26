"""
Pydantic models for Adaptive IDS data schemas.
Mirrors Avro schemas for runtime validation and serialization.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Severity(str, Enum):
    """Alert severity levels"""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Alert workflow status"""
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class FlowFeatures(BaseModel):
    """
    Network flow features for ML inference.
    Corresponds to flow_features.avsc schema.
    """
    flow_id: str = Field(..., description="Unique 5-tuple flow identifier")
    timestamp: int = Field(..., description="Flow start time in milliseconds since epoch")
    src_ip: str = Field(..., description="Source IP address")
    dst_ip: str = Field(..., description="Destination IP address")
    src_port: int = Field(..., ge=0, le=65535, description="Source port")
    dst_port: int = Field(..., ge=0, le=65535, description="Destination port")
    protocol: str = Field(..., description="Transport protocol (TCP/UDP/ICMP)")
    features: List[float] = Field(..., description="41+ normalized feature vector")
    feature_names: List[str] = Field(default_factory=list, description="Optional feature names")
    feature_version: str = Field(..., description="Feature extraction algorithm version")
    schema_version: int = Field(default=1, description="Schema version")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Optional metadata")

    @field_validator('features')
    @classmethod
    def validate_features_length(cls, v: List[float]) -> List[float]:
        """Ensure features array has at least 41 elements"""
        if len(v) < 41:
            raise ValueError(f"Features array must have at least 41 elements, got {len(v)}")
        return v

    @field_validator('protocol')
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        """Normalize protocol to uppercase"""
        return v.upper()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowFeatures":
        """Create from dictionary"""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.model_dump(exclude_none=True)

    @staticmethod
    def create_flow_id(src_ip: str, src_port: int, dst_ip: str, dst_port: int, protocol: str) -> str:
        """Generate standard flow_id from 5-tuple"""
        return f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol.upper()}"


class Prediction(BaseModel):
    """
    Model inference prediction.
    Corresponds to prediction.avsc schema.
    """
    flow_id: str = Field(..., description="Flow identifier from FlowFeatures")
    timestamp: int = Field(..., description="Prediction time in milliseconds since epoch")
    class_idx: int = Field(..., ge=0, description="Numeric class index")
    class_name: str = Field(..., description="Human-readable attack class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score")
    model_version: str = Field(..., description="Model version identifier")
    feature_version: str = Field(..., description="Feature extraction version")
    agent_type: Optional[str] = Field(default=None, description="Specialist agent type")
    all_class_probs: Optional[Dict[str, float]] = Field(default=None, description="Full probability distribution")
    inference_latency_ms: Optional[float] = Field(default=None, ge=0, description="Inference latency")
    schema_version: int = Field(default=1, description="Schema version")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is in valid range"""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prediction":
        """Create from dictionary"""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.model_dump(exclude_none=True)

    def is_attack(self) -> bool:
        """Check if prediction indicates an attack (not normal traffic)"""
        return self.class_name.upper() != "NORMAL" and self.class_name.upper() != "BENIGN"


class Enrichment(BaseModel):
    """
    Alert enrichment data from external sources.
    """
    src_geo: Optional[str] = Field(default=None, description="Source IP geolocation")
    dst_geo: Optional[str] = Field(default=None, description="Destination IP geolocation")
    src_reputation: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Source IP reputation")
    dst_reputation: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Destination IP reputation")
    tags: Optional[List[str]] = Field(default=None, description="Custom tags")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.model_dump(exclude_none=True)


class Alert(BaseModel):
    """
    Enriched security alert.
    Corresponds to alert.avsc schema.
    """
    alert_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique alert UUID")
    flow_id: str = Field(..., description="Flow identifier")
    timestamp: int = Field(..., description="Alert creation time in milliseconds since epoch")
    class_idx: int = Field(..., ge=0, description="Attack class index")
    class_name: str = Field(..., description="Attack class name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    severity: Severity = Field(..., description="Alert severity level")
    src_ip: str = Field(..., description="Source IP address")
    dst_ip: str = Field(..., description="Destination IP address")
    src_port: int = Field(..., ge=0, le=65535, description="Source port")
    dst_port: int = Field(..., ge=0, le=65535, description="Destination port")
    protocol: str = Field(..., description="Transport protocol")
    model_version: str = Field(..., description="Model version")
    feature_version: str = Field(..., description="Feature version")
    enrichment: Optional[Enrichment] = Field(default=None, description="Enrichment data")
    status: AlertStatus = Field(default=AlertStatus.NEW, description="Alert status")
    assigned_to: Optional[str] = Field(default=None, description="Assigned user/team")
    notes: Optional[str] = Field(default=None, description="Analyst notes")
    destinations: List[str] = Field(default_factory=list, description="Dispatch targets")
    schema_version: int = Field(default=1, description="Schema version")

    @classmethod
    def from_prediction(
        cls,
        prediction: Prediction,
        severity: Severity,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        protocol: str,
        enrichment: Optional[Enrichment] = None,
        destinations: Optional[List[str]] = None
    ) -> "Alert":
        """
        Create Alert from Prediction and flow metadata.
        
        Args:
            prediction: Source prediction
            severity: Computed severity level
            src_ip, dst_ip, src_port, dst_port, protocol: Flow 5-tuple
            enrichment: Optional enrichment data
            destinations: Optional dispatch targets
        """
        return cls(
            flow_id=prediction.flow_id,
            timestamp=prediction.timestamp,
            class_idx=prediction.class_idx,
            class_name=prediction.class_name,
            confidence=prediction.confidence,
            severity=severity,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            model_version=prediction.model_version,
            feature_version=prediction.feature_version,
            enrichment=enrichment,
            destinations=destinations or []
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create from dictionary"""
        # Convert enrichment dict to Enrichment object if present
        if data.get("enrichment") and isinstance(data["enrichment"], dict):
            data["enrichment"] = Enrichment(**data["enrichment"])
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = self.model_dump(exclude_none=True)
        # Convert enums to strings
        if "severity" in data:
            data["severity"] = data["severity"].value if isinstance(data["severity"], Severity) else data["severity"]
        if "status" in data:
            data["status"] = data["status"].value if isinstance(data["status"], AlertStatus) else data["status"]
        return data

    def is_critical(self) -> bool:
        """Check if alert is critical severity"""
        return self.severity == Severity.CRITICAL

    def is_resolved(self) -> bool:
        """Check if alert has been resolved"""
        return self.status in (AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE)


# Utility functions for timestamp conversion
def timestamp_to_ms(dt: datetime) -> int:
    """Convert datetime to milliseconds since epoch"""
    return int(dt.timestamp() * 1000)


def ms_to_timestamp(ms: int) -> datetime:
    """Convert milliseconds since epoch to datetime"""
    return datetime.fromtimestamp(ms / 1000)


# Severity mapping helper
def compute_severity(class_name: str, confidence: float) -> Severity:
    """
    Compute alert severity based on attack class and confidence.
    
    Args:
        class_name: Attack class name
        confidence: Prediction confidence [0.0, 1.0]
    
    Returns:
        Severity level
    """
    class_upper = class_name.upper()
    
    # Normal traffic
    if class_upper in ("NORMAL", "BENIGN"):
        return Severity.INFO
    
    # Critical attacks
    critical_attacks = {"DDOS", "DOS", "BOTNET", "INFILTRATION", "RANSOMWARE"}
    if any(crit in class_upper for crit in critical_attacks):
        if confidence >= 0.9:
            return Severity.CRITICAL
        elif confidence >= 0.7:
            return Severity.HIGH
        else:
            return Severity.MEDIUM
    
    # High-impact attacks
    high_attacks = {"BRUTEFORCE", "SQLINJECTION", "XSS", "WEBATTACK"}
    if any(high in class_upper for high in high_attacks):
        if confidence >= 0.8:
            return Severity.HIGH
        elif confidence >= 0.6:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    # Reconnaissance and probing
    recon_attacks = {"PORTSCAN", "SCAN", "PROBE"}
    if any(recon in class_upper for recon in recon_attacks):
        if confidence >= 0.8:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    # Default: medium for unknown attacks with high confidence
    if confidence >= 0.8:
        return Severity.MEDIUM
    else:
        return Severity.LOW
