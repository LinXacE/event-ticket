from flask import Blueprint, render_template, jsonify
from database import db
from models import Event, EventPass, EventAnalytics
from flask_login import login_required
import csv
import io
from datetime import datetime
from models import ValidationLog, PassType
, make_response
bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/')
@login_required
def index():
    """Analytics dashboard page"""
    return render_template('analytics/index.html')

@bp.route('/data/<int:event_id>')
@login_required
def event_data(event_id):
    """Get analytics data for a specific event"""
    analytics = EventAnalytics.query.filter_by(event_id=event_id).first()
    
    if analytics:
        return jsonify({
            'success': True,
            'data': {
                'total_passes': analytics.total_passes_generated,
                'validated_passes': analytics.total_passes_validated,
                'judges': analytics.judges_count,
                'mentors': analytics.mentors_count,
                'participants': analytics.participants_count,
                'volunteers': analytics.volunteers_count,
                'guests': analytics.guests_count
            }
        }), 200
    
    return jsonify({
        'success': False,
        'message': 'No analytics data found for this event'
    }), 404


# CSV Export Routes

@bp.route('/export/attendees/<int:event_id>')
@login_required
def export_attendees(event_id):
    """Export attendee list as CSV"""
    event = Event.query.get_or_404(event_id)
    passes = EventPass.query.filter_by(event_id=event_id).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Pass Code', 'Participant Name', 'Email', 'Phone', 'Pass Type', 'Status', 'Validated', 'Created At'])
    
    # Write data
    for pass_obj in passes:
        writer.writerow([
            pass_obj.pass_code,
            pass_obj.participant_name,
            pass_obj.participant_email or 'N/A',
            pass_obj.participant_phone or 'N/A',
            pass_obj.pass_type.type_name if pass_obj.pass_type else 'N/A',
            'Used' if pass_obj.is_validated else 'Available',
            'Yes' if pass_obj.is_validated else 'No',
            pass_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=attendees_{event.event_name}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@bp.route('/export/validation-logs/<int:event_id>')
@login_required
def export_validation_logs(event_id):
    """Export validation logs as CSV"""
    event = Event.query.get_or_404(event_id)
    
    # Get all validation logs for this event's passes
    validation_logs = db.session.query(ValidationLog).join(EventPass).filter(
        EventPass.event_id == event_id
    ).order_by(ValidationLog.validation_time.desc()).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Validation Time', 'Pass Code', 'Participant Name', 'Validator', 'Status', 'Message', 'IP Address'])
    
    # Write data
    for log in validation_logs:
        writer.writerow([
            log.validation_time.strftime('%Y-%m-%d %H:%M:%S'),
            log.pass.pass_code if log.pass else 'N/A',
            log.pass.participant_name if log.pass else 'N/A',
            log.validator.full_name if log.validator else 'N/A',
            log.validation_status.upper(),
            log.validation_message or 'N/A',
            log.ip_address or 'N/A'
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=validation_logs_{event.event_name}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@bp.route('/export/analytics/<int:event_id>')
@login_required
def export_analytics(event_id):
    """Export event analytics as CSV"""
    event = Event.query.get_or_404(event_id)
    analytics = EventAnalytics.query.filter_by(event_id=event_id).first()
    
    # Get pass type breakdown
    pass_type_stats = db.session.query(
        PassType.type_name,
        db.func.count(EventPass.id).label('total'),
        db.func.sum(db.case([(EventPass.is_validated == True, 1)], else_=0)).label('validated')
    ).join(EventPass).filter(
        EventPass.event_id == event_id
    ).group_by(PassType.type_name).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Metric', 'Value'])
    
    # Write analytics data
    if analytics:
        writer.writerow(['Total Passes Generated', analytics.total_passes_generated])
        writer.writerow(['Total Passes Validated', analytics.total_passes_validated])
        writer.writerow(['Validation Rate', f"{(analytics.total_passes_validated / analytics.total_passes_generated * 100):.2f}%" if analytics.total_passes_generated > 0 else '0%'])
    
    writer.writerow([])  # Empty row
    writer.writerow(['Pass Type Breakdown', ''])
    writer.writerow(['Pass Type', 'Total Generated', 'Validated', 'Validation Rate'])
    
    for stat in pass_type_stats:
        validation_rate = (stat.validated / stat.total * 100) if stat.total > 0 else 0
        writer.writerow([stat.type_name, stat.total, stat.validated, f"{validation_rate:.2f}%"])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=analytics_{event.event_name}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@bp.route('/export/gate-statistics/<int:event_id>')
@login_required
def export_gate_statistics(event_id):
    """Export gate statistics as CSV"""
    event = Event.query.get_or_404(event_id)
    
    # This will work after gates table is populated
    # For now, create a placeholder
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Gate Name', 'Gate Type', 'Total Entries', 'Access Granted', 'Access Denied'])
    
    # Placeholder data - will be populated after gates are configured
    writer.writerow(['Gate statistics will be available after gates are configured for this event'])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=gate_statistics_{event.event_name}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response
