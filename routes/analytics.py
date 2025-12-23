from flask import Blueprint, render_template, jsonify, make_response
from database import db
from models import (
    Event,
    EventPass,
    EventAnalytics,
    ValidationLog,
    PassType
)
from flask_login import login_required
import csv
import io
from datetime import datetime

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


# ---------------- CSV EXPORT ROUTES ---------------- #

@bp.route('/export/attendees/<int:event_id>')
@login_required
def export_attendees(event_id):
    """Export attendee list as CSV"""
    event = Event.query.get_or_404(event_id)
    passes = EventPass.query.filter_by(event_id=event_id).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Pass Code', 'Participant Name', 'Email', 'Phone',
        'Pass Type', 'Status', 'Validated', 'Created At'
    ])

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

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=attendees_{event.event_name}_'
        f'{datetime.now().strftime("%Y%m%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/validation-logs/<int:event_id>')
@login_required
def export_validation_logs(event_id):
    """Export validation logs as CSV"""
    event = Event.query.get_or_404(event_id)

    validation_logs = (
        db.session.query(ValidationLog)
        .join(EventPass)
        .filter(EventPass.event_id == event_id)
        .order_by(ValidationLog.validation_time.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Validation Time', 'Pass Code', 'Participant Name',
        'Validator', 'Status', 'Message', 'IP Address'
    ])

    for log in validation_logs:
        writer.writerow([
            log.validation_time.strftime('%Y-%m-%d %H:%M:%S'),
            log.event_pass.pass_code if log.event_pass else 'N/A',
            log.event_pass.participant_name if log.event_pass else 'N/A',
            log.validator.full_name if log.validator else 'N/A',
            log.validation_status.upper(),
            log.validation_message or 'N/A',
            log.ip_address or 'N/A'
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=validation_logs_{event.event_name}_'
        f'{datetime.now().strftime("%Y%m%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/analytics/<int:event_id>')
@login_required
def export_analytics(event_id):
    """Export event analytics as CSV"""
    event = Event.query.get_or_404(event_id)
    analytics = EventAnalytics.query.filter_by(event_id=event_id).first()

    pass_type_stats = (
        db.session.query(
            PassType.type_name,
            db.func.count(EventPass.id).label('total'),
            db.func.sum(
                db.case([(EventPass.is_validated == True, 1)], else_=0)
            ).label('validated')
        )
        .join(EventPass)
        .filter(EventPass.event_id == event_id)
        .group_by(PassType.type_name)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Metric', 'Value'])

    if analytics:
        writer.writerow(['Total Passes Generated', analytics.total_passes_generated])
        writer.writerow(['Total Passes Validated', analytics.total_passes_validated])
        rate = (
            analytics.total_passes_validated /
            analytics.total_passes_generated * 100
            if analytics.total_passes_generated > 0 else 0
        )
        writer.writerow(['Validation Rate', f'{rate:.2f}%'])

    writer.writerow([])
    writer.writerow(['Pass Type', 'Total Generated', 'Validated', 'Validation Rate'])

    for stat in pass_type_stats:
        rate = (stat.validated / stat.total * 100) if stat.total > 0 else 0
        writer.writerow([
            stat.type_name,
            stat.total,
            stat.validated,
            f'{rate:.2f}%'
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=analytics_{event.event_name}_'
        f'{datetime.now().strftime("%Y%m%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/gate-statistics/<int:event_id>')
@login_required
def export_gate_statistics(event_id):
    """Export gate statistics as CSV"""
    event = Event.query.get_or_404(event_id)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Gate Name', 'Gate Type',
        'Total Entries', 'Access Granted', 'Access Denied'
    ])

    writer.writerow([
        'Gate statistics will be available after gates are configured'
    ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=gate_statistics_{event.event_name}_'
        f'{datetime.now().strftime("%Y%m%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response
