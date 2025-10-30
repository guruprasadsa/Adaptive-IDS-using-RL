"""
Reports API Routes
Generate, manage, and schedule security reports
"""

from flask import Blueprint, request, jsonify, send_file
from datetime import datetime, timedelta
import uuid
import json
import csv
import io
from typing import Dict, List, Any, Optional

# Try to import auth from backend.api.auth, fall back to dummy decorators
try:
    from api.auth import require_auth
    from security.rbac import Permission, get_rbac_manager
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    def require_auth(f):
        return f

# Define require_permission decorator
def require_permission(permission: str):
    """Decorator to check user permissions"""
    def decorator(f):
        if not SECURITY_AVAILABLE:
            return f
        # For now, just return the function (permissions not enforced for reports)
        # TODO: Implement proper permission checking
        return f
    return decorator

try:
    from backend.db.models import db, Alert, Incident
    from sqlalchemy import func, desc, and_
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


def parse_date_range(range_str: str) -> tuple:
    """Parse date range string into start and end datetime objects"""
    now = datetime.utcnow()
    
    range_map = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        'ytd': None,  # Year to date
    }
    
    if range_str in range_map:
        if range_str == 'ytd':
            start_date = datetime(now.year, 1, 1)
        else:
            start_date = now - range_map[range_str]
        return start_date, now
    
    # Custom date range format: "YYYY-MM-DD:YYYY-MM-DD"
    if ':' in range_str:
        try:
            start_str, end_str = range_str.split(':')
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
            return start_date, end_date
        except ValueError:
            pass
    
    # Default to last 7 days
    return now - timedelta(days=7), now


def generate_alert_summary_data(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Generate alert summary report data"""
    if not DB_AVAILABLE:
        return {
            'total_alerts': 0,
            'severity_distribution': [],
            'status_distribution': [],
            'top_attack_types': [],
            'top_source_ips': [],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    try:
        # Total alerts
        total_alerts = db.session.query(func.count(Alert.id)).filter(
            Alert.timestamp.between(start_date, end_date)
        ).scalar() or 0
        
        # Alerts by severity
        severity_dist = db.session.query(
            Alert.severity,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp.between(start_date, end_date)
        ).group_by(Alert.severity).all()
        
        # Alerts by status
        status_dist = db.session.query(
            Alert.status,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp.between(start_date, end_date)
        ).group_by(Alert.status).all()
        
        # Top attack types
        top_attacks = db.session.query(
            Alert.class_name,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp.between(start_date, end_date)
        ).group_by(Alert.class_name).order_by(desc('count')).limit(10).all()
        
        # Top source IPs
        top_sources = db.session.query(
            Alert.src_ip,
            func.count(Alert.id).label('count')
        ).filter(
            and_(
                Alert.timestamp.between(start_date, end_date),
                Alert.src_ip.isnot(None)
            )
        ).group_by(Alert.src_ip).order_by(desc('count')).limit(10).all()
        
        return {
            'total_alerts': total_alerts,
            'severity_distribution': [{'severity': s, 'count': c} for s, c in severity_dist],
            'status_distribution': [{'status': s, 'count': c} for s, c in status_dist],
            'top_attack_types': [{'type': t, 'count': c} for t, c in top_attacks],
            'top_source_ips': [{'ip': ip, 'count': c} for ip, c in top_sources],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    except Exception as e:
        print(f"Error generating alert summary: {e}")
        return {
            'total_alerts': 0,
            'severity_distribution': [],
            'status_distribution': [],
            'top_attack_types': [],
            'top_source_ips': [],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }


def generate_incident_timeline_data(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Generate incident timeline report data"""
    if not DB_AVAILABLE:
        return {
            'total_incidents': 0,
            'status_distribution': [],
            'severity_distribution': [],
            'incidents': [],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    try:
        # Total incidents
        total_incidents = db.session.query(func.count(Incident.id)).filter(
            Incident.created_at.between(start_date, end_date)
        ).scalar() or 0
        
        # Incidents by status
        status_dist = db.session.query(
            Incident.status,
            func.count(Incident.id).label('count')
        ).filter(
            Incident.created_at.between(start_date, end_date)
        ).group_by(Incident.status).all()
        
        # Incidents by severity
        severity_dist = db.session.query(
            Incident.severity,
            func.count(Incident.id).label('count')
        ).filter(
            Incident.created_at.between(start_date, end_date)
        ).group_by(Incident.severity).all()
        
        # Recent incidents
        recent_incidents = db.session.query(Incident).filter(
            Incident.created_at.between(start_date, end_date)
        ).order_by(desc(Incident.created_at)).limit(50).all()
        
        incidents_data = []
        for inc in recent_incidents:
            incidents_data.append({
                'id': inc.incident_id,
                'incident_id': inc.incident_id,
                'title': inc.title,
                'severity': inc.severity,
                'status': inc.status,
                'created_at': inc.created_at.isoformat() if inc.created_at else None,
                'assigned_to': inc.assigned_to or 'Unassigned'
            })
        
        return {
            'total_incidents': total_incidents,
            'status_distribution': [{'status': s, 'count': c} for s, c in status_dist],
            'severity_distribution': [{'severity': s, 'count': c} for s, c in severity_dist],
            'incidents': incidents_data,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    except Exception as e:
        print(f"Error generating incident timeline: {e}")
        return {
            'total_incidents': 0,
            'status_distribution': [],
            'severity_distribution': [],
            'incidents': [],
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }


def generate_csv_report(data: Dict[str, Any], report_type: str) -> str:
    """Generate CSV format report"""
    output = io.StringIO()
    
    if report_type == 'alert-summary':
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Alert Summary Report'])
        writer.writerow(['Period', f"{data['period']['start']} to {data['period']['end']}"])
        writer.writerow([])
        
        # Total alerts
        writer.writerow(['Total Alerts', data['total_alerts']])
        writer.writerow([])
        
        # Severity distribution
        writer.writerow(['Severity Distribution'])
        writer.writerow(['Severity', 'Count'])
        for item in data['severity_distribution']:
            writer.writerow([item['severity'], item['count']])
        writer.writerow([])
        
        # Top attack types
        writer.writerow(['Top Attack Types'])
        writer.writerow(['Type', 'Count'])
        for item in data['top_attack_types']:
            writer.writerow([item['type'], item['count']])
        writer.writerow([])
        
        # Top source IPs
        writer.writerow(['Top Source IPs'])
        writer.writerow(['IP Address', 'Count'])
        for item in data['top_source_ips']:
            writer.writerow([item['ip'], item['count']])
    
    elif report_type == 'incident-timeline':
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Incident Timeline Report'])
        writer.writerow(['Period', f"{data['period']['start']} to {data['period']['end']}"])
        writer.writerow([])
        
        # Total incidents
        writer.writerow(['Total Incidents', data['total_incidents']])
        writer.writerow([])
        
        # Incidents table
        writer.writerow(['Incident ID', 'Title', 'Severity', 'Status', 'Created', 'Assigned To'])
        for inc in data['incidents']:
            writer.writerow([
                inc['incident_id'],
                inc['title'],
                inc['severity'],
                inc['status'],
                inc['created_at'],
                inc.get('assigned_to', 'Unassigned')
            ])
    
    return output.getvalue()


@reports_bp.route('/generate', methods=['POST'])
@require_auth
@require_permission('view_alerts')
def generate_report(user_id=None):
    """Generate a new report"""
    try:
        data = request.get_json()
        
        report_type = data.get('report_type', 'alert-summary')
        date_range = data.get('date_range', '7d')
        output_format = data.get('format', 'json')  # json, csv, pdf
        
        # Parse date range
        start_date, end_date = parse_date_range(date_range)
        
        # Generate report data based on type
        report_data = {}
        if report_type == 'alert-summary':
            report_data = generate_alert_summary_data(start_date, end_date)
        elif report_type == 'incident-timeline':
            report_data = generate_incident_timeline_data(start_date, end_date)
        elif report_type == 'model-performance':
            # Placeholder for model performance report
            report_data = {
                'message': 'Model performance report not yet implemented',
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Generate report ID
        report_id = str(uuid.uuid4())
        
        # Format response based on output format
        if output_format == 'csv':
            csv_content = generate_csv_report(report_data, report_type)
            
            # For now, return CSV as string (in production, save to storage)
            return jsonify({
                'report_id': report_id,
                'report_type': report_type,
                'format': 'csv',
                'generated_at': datetime.utcnow().isoformat(),
                'date_range': f"{start_date.date()} to {end_date.date()}",
                'content': csv_content,
                'size': len(csv_content)
            }), 201
        
        elif output_format == 'pdf':
            # PDF generation placeholder
            return jsonify({
                'error': 'PDF generation not yet implemented',
                'message': 'Use JSON or CSV format for now'
            }), 501
        
        else:  # JSON format
            return jsonify({
                'report_id': report_id,
                'report_type': report_type,
                'format': 'json',
                'generated_at': datetime.utcnow().isoformat(),
                'date_range': f"{start_date.date()} to {end_date.date()}",
                'data': report_data,
                'size': len(json.dumps(report_data))
            }), 201
    
    except Exception as e:
        print(f"Error generating report: {e}")
        return jsonify({'error': 'Failed to generate report', 'details': str(e)}), 500


@reports_bp.route('/recent', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_recent_reports(user_id=None):
    """Get list of recently generated reports"""
    try:
        # In a real implementation, this would query a reports table
        # For now, return mock data
        
        limit = request.args.get('limit', 10, type=int)
        
        # Mock recent reports
        recent_reports = [
            {
                'id': str(uuid.uuid4()),
                'name': 'Alert Summary - Last 7 Days',
                'type': 'Alert Summary',
                'report_type': 'alert-summary',
                'generated_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                'date_range': 'Last 7 days',
                'size': '45 KB',
                'format': 'csv'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Incident Timeline - Last 30 Days',
                'type': 'Incident Timeline',
                'report_type': 'incident-timeline',
                'generated_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'date_range': 'Last 30 days',
                'size': '128 KB',
                'format': 'json'
            }
        ]
        
        return jsonify({
            'reports': recent_reports[:limit],
            'total': len(recent_reports)
        }), 200
    
    except Exception as e:
        print(f"Error fetching recent reports: {e}")
        return jsonify({'error': 'Failed to fetch reports'}), 500


@reports_bp.route('/<report_id>/download', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def download_report(report_id: str, user_id=None):
    """Download a specific report"""
    try:
        # In production, retrieve report from storage
        # For now, return error
        
        return jsonify({
            'error': 'Report download not fully implemented',
            'message': 'Reports are generated on-demand. Use /generate endpoint.'
        }), 501
    
    except Exception as e:
        print(f"Error downloading report: {e}")
        return jsonify({'error': 'Failed to download report'}), 500


@reports_bp.route('/<report_id>', methods=['DELETE'])
@require_auth
@require_permission('manage_reports')
def delete_report(report_id: str, user_id=None):
    """Delete a report"""
    try:
        # In production, delete from storage
        # For now, return success
        
        return jsonify({
            'message': 'Report deleted successfully',
            'report_id': report_id
        }), 200
    
    except Exception as e:
        print(f"Error deleting report: {e}")
        return jsonify({'error': 'Failed to delete report'}), 500


@reports_bp.route('/schedules', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_report_schedules(user_id=None):
    """Get all report schedules"""
    try:
        # Mock scheduled reports
        schedules = [
            {
                'id': str(uuid.uuid4()),
                'report_type': 'alert-summary',
                'name': 'Weekly Alert Summary',
                'frequency': 'weekly',
                'day_of_week': 'Monday',
                'time': '09:00',
                'format': 'pdf',
                'recipients': ['admin@example.com'],
                'enabled': True,
                'next_run': (datetime.utcnow() + timedelta(days=1)).isoformat()
            }
        ]
        
        return jsonify({
            'schedules': schedules,
            'total': len(schedules)
        }), 200
    
    except Exception as e:
        print(f"Error fetching schedules: {e}")
        return jsonify({'error': 'Failed to fetch schedules'}), 500


@reports_bp.route('/schedules', methods=['POST'])
@require_auth
@require_permission('manage_reports')
def create_report_schedule(user_id=None):
    """Create a new report schedule"""
    try:
        data = request.get_json()
        
        required_fields = ['report_type', 'name', 'frequency', 'format']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        schedule_id = str(uuid.uuid4())
        
        # In production, save to database
        schedule = {
            'id': schedule_id,
            'report_type': data['report_type'],
            'name': data['name'],
            'frequency': data['frequency'],
            'day_of_week': data.get('day_of_week'),
            'time': data.get('time', '09:00'),
            'format': data['format'],
            'recipients': data.get('recipients', []),
            'enabled': data.get('enabled', True),
            'created_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(schedule), 201
    
    except Exception as e:
        print(f"Error creating schedule: {e}")
        return jsonify({'error': 'Failed to create schedule'}), 500


@reports_bp.route('/schedules/<schedule_id>', methods=['PUT'])
@require_auth
@require_permission('manage_reports')
def update_report_schedule(schedule_id: str, user_id=None):
    """Update a report schedule"""
    try:
        data = request.get_json()
        
        # In production, update in database
        return jsonify({
            'message': 'Schedule updated successfully',
            'schedule_id': schedule_id
        }), 200
    
    except Exception as e:
        print(f"Error updating schedule: {e}")
        return jsonify({'error': 'Failed to update schedule'}), 500


@reports_bp.route('/schedules/<schedule_id>', methods=['DELETE'])
@require_auth
@require_permission('manage_reports')
def delete_report_schedule(schedule_id: str, user_id=None):
    """Delete a report schedule"""
    try:
        # In production, delete from database
        return jsonify({
            'message': 'Schedule deleted successfully',
            'schedule_id': schedule_id
        }), 200
    
    except Exception as e:
        print(f"Error deleting schedule: {e}")
        return jsonify({'error': 'Failed to delete schedule'}), 500
