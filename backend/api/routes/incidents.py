"""
Incidents API Routes
Manage security incidents, status updates, and alert correlation
"""

import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from backend.db.models import db, Incident, Alert
from backend.api.middleware.auth_middleware import require_auth, require_permission
from sqlalchemy import desc

incidents_bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')


@incidents_bp.route('', methods=['POST'])
@require_auth
@require_permission('create_incidents')
def create_incident():
    """
    Create a new security incident
    
    Request Body:
        title: str - Incident title
        description: str - Detailed description
        severity: str - critical, high, medium, low
        alert_ids: list[str] - Related alert IDs (optional)
        assigned_to: str - Username/email (optional)
    
    Returns:
        201: Created incident
        400: Validation error
        500: Server error
    """
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        if not data.get('description'):
            return jsonify({'error': 'Description is required'}), 400
        
        severity = data.get('severity', 'medium').lower()
        if severity not in ['critical', 'high', 'medium', 'low']:
            return jsonify({'error': 'Invalid severity level'}), 400
        
        # Generate incident ID
        incident_id = f"INC-{uuid.uuid4().hex[:12].upper()}"
        
        # Get current user from request (set by auth middleware)
        current_user = getattr(request, 'current_user', None)
        assigned_to = data.get('assigned_to', current_user.get('username') if current_user else 'Unassigned')
        
        # Process related alerts
        alert_ids = data.get('alert_ids', [])
        related_alerts = []
        alerts_count = 0
        
        if alert_ids:
            alerts = Alert.query.filter(Alert.alert_id.in_(alert_ids)).all()
            related_alerts = [alert.alert_id for alert in alerts]
            alerts_count = len(related_alerts)
        
        # Create incident
        now = datetime.now(timezone.utc)
        incident = Incident(
            incident_id=incident_id,
            title=data['title'],
            description=data['description'],
            severity=severity.upper(),
            status='OPEN',
            assigned_to=assigned_to,
            summary=data.get('summary', f"Security incident: {data['title']}"),
            created_at=now,
            last_updated_at=now,
            related_alerts=related_alerts,
            alerts_count=alerts_count,
            affected_systems=data.get('affected_systems', 0)
        )
        
        db.session.add(incident)
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'title': incident.title,
            'status': incident.status,
            'severity': incident.severity,
            'assigned_to': incident.assigned_to,
            'created_at': incident.created_at.isoformat(),
            'alerts_count': incident.alerts_count,
            'message': 'Incident created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/status', methods=['PATCH'])
@require_auth
@require_permission('update_incidents')
def update_incident_status(incident_id: str):
    """
    Update incident status
    
    Request Body:
        status: str - open, investigating, contained, resolved
        notes: str - Optional status update notes
    
    Returns:
        200: Updated incident
        404: Incident not found
        400: Invalid status
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        new_status = data.get('status', '').upper()
        
        valid_statuses = ['OPEN', 'INVESTIGATING', 'CONTAINED', 'RESOLVED']
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        incident.status = new_status
        incident.last_updated_at = datetime.now(timezone.utc)
        
        # Optional: Add notes/comments (would require comments table)
        notes = data.get('notes')
        if notes:
            # For now, append to description or implement comments table
            incident.description += f"\n\n[{datetime.now(timezone.utc).isoformat()}] Status updated to {new_status}: {notes}"
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'status': incident.status,
            'last_updated_at': incident.last_updated_at.isoformat(),
            'message': 'Incident status updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/assign', methods=['PATCH'])
@require_auth
@require_permission('update_incidents')
def assign_incident(incident_id: str):
    """
    Assign incident to a user
    
    Request Body:
        assigned_to: str - Username or email
    
    Returns:
        200: Updated incident
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        assigned_to = data.get('assigned_to')
        
        if not assigned_to:
            return jsonify({'error': 'assigned_to is required'}), 400
        
        incident.assigned_to = assigned_to
        incident.last_updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'assigned_to': incident.assigned_to,
            'last_updated_at': incident.last_updated_at.isoformat(),
            'message': f'Incident assigned to {assigned_to}'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/alerts', methods=['POST'])
@require_auth
@require_permission('update_incidents')
def link_alerts_to_incident(incident_id: str):
    """
    Link alerts to an incident
    
    Request Body:
        alert_ids: list[str] - Alert IDs to link
    
    Returns:
        200: Updated incident
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        alert_ids = data.get('alert_ids', [])
        
        if not alert_ids:
            return jsonify({'error': 'alert_ids array is required'}), 400
        
        # Verify alerts exist
        alerts = Alert.query.filter(Alert.alert_id.in_(alert_ids)).all()
        valid_alert_ids = [alert.alert_id for alert in alerts]
        
        # Get current related alerts
        current_alerts = incident.related_alerts if isinstance(incident.related_alerts, list) else []
        
        # Add new alerts (avoid duplicates)
        updated_alerts = list(set(current_alerts + valid_alert_ids))
        
        incident.related_alerts = updated_alerts
        incident.alerts_count = len(updated_alerts)
        incident.last_updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'related_alerts': incident.related_alerts,
            'alerts_count': incident.alerts_count,
            'message': f'{len(valid_alert_ids)} alerts linked to incident'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/alerts/<alert_id>', methods=['DELETE'])
@require_auth
@require_permission('update_incidents')
def unlink_alert_from_incident(incident_id: str, alert_id: str):
    """
    Unlink an alert from an incident
    
    Returns:
        200: Alert unlinked
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        # Remove alert from related_alerts
        current_alerts = incident.related_alerts if isinstance(incident.related_alerts, list) else []
        
        if alert_id in current_alerts:
            current_alerts.remove(alert_id)
            incident.related_alerts = current_alerts
            incident.alerts_count = len(current_alerts)
            incident.last_updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'id': incident.incident_id,
                'message': f'Alert {alert_id} unlinked from incident'
            }), 200
        else:
            return jsonify({'error': 'Alert not linked to this incident'}), 404
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
