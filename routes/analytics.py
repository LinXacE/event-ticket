from flask import Blueprint, render_template, jsonify, make_response
from database import db
from models import (
    Event,
    EventPass,
    EventAnalytics,
    ValidationLog,
    PassType
)
from flask_login import login_required, current_user
import csv
import io
from datetime import datetime

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@bp.route('/')
@login_required
def index():
    """Analytics dashboard page"""
    if current_user.role == 'admin':
        events = Event.query.all()
    else:
        events = Event.query.filter_by(organizer_id=current_user.id).all()

    return render_template('analytics/index.html', events=events)


@bp.route('/data/<int:event_id>')
@login_required
def event_data(event_id):
    """
    Return analytics for event_id using REAL DB data (EventPass),
    so it works even if EventAnalytics row is missing.
    """
    # Permission: organizers only see their own events (admins can see all)
    event = Event.query.get_or_404(event_id)
    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    total_passes = EventPass.query.filter_by(event_id=event_id).count()
    validated_passes = EventPass.query.filter_by(event_id=event_id, is_validated=True).count()

    # Pass type breakdown (by PassType.type_name)
    pass_type_stats = (
        db.session.query(
            PassType.type_name.label("type_name"),
            db.func.count(EventPass.id).label("total")
        )
        .join(EventPass, EventPass.pass_type_id == PassType.id)
        .filter(EventPass.event_id == event_id)
        .group_by(PassType.type_name)
        .all()
    )

    type_labels = [row.type_name for row in pass_type_stats]
    type_counts = [int(row.total) for row in pass_type_stats]

    # If there are no passes, keep chart safe
    if not type_labels:
        type_labels = []
        type_counts = []

    return jsonify({
        "success": True,
        "data": {
            "event_id": event_id,
            "total_passes": int(total_passes),
            "validated_passes": int(validated_passes),
            "pass_type_labels": type_labels,
            "pass_type_counts": type_counts
        }
    }), 200


# ---------------- CSV EXPORT ROUTES ---------------- #

@bp.route('/export/attendees/<int:event_id>')
@login_required
def export_attendees(event_id):
    """Export attendee list as CSV"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

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
        f'{datetime.now().strftime("%%Y%%m%%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/validation-logs/<int:event_id>')
@login_required
def export_validation_logs(event_id):
    """Export validation logs as CSV"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

    validation_logs = (
        db.session.query(ValidationLog)
        .join(EventPass, ValidationLog.pass_id == EventPass.id)
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
            log.pass_obj.pass_code if log.pass_obj else 'N/A',
            log.pass_obj.participant_name if log.pass_obj else 'N/A',
            log.validator.full_name if log.validator else 'N/A',
            log.validation_status.upper(),
            log.validation_message or 'N/A',
            log.ip_address or 'N/A'
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=validation_logs_{event.event_name}_'
        f'{datetime.now().strftime("%%Y%%m%%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/analytics/<int:event_id>')
@login_required
def export_analytics(event_id):
    """Export event analytics as CSV"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

    total_passes = EventPass.query.filter_by(event_id=event_id).count()
    validated_passes = EventPass.query.filter_by(event_id=event_id, is_validated=True).count()

    pass_type_stats = (
        db.session.query(
            PassType.type_name,
            db.func.count(EventPass.id).label('total'),
            db.func.sum(
                db.case((EventPass.is_validated == True, 1), else_=0)  # noqa: E712
            ).label('validated')
        )
        .join(EventPass, EventPass.pass_type_id == PassType.id)
        .filter(EventPass.event_id == event_id)
        .group_by(PassType.type_name)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Passes', total_passes])
    writer.writerow(['Validated Passes', validated_passes])

    rate = (validated_passes / total_passes * 100) if total_passes > 0 else 0
    writer.writerow(['Validation Rate', f'{rate:.2f}%'])

    writer.writerow([])
    writer.writerow(['Pass Type', 'Total Generated', 'Validated', 'Validation Rate'])

    for stat in pass_type_stats:
        r = (stat.validated / stat.total * 100) if stat.total > 0 else 0
        writer.writerow([stat.type_name, stat.total, stat.validated, f'{r:.2f}%'])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=analytics_{event.event_name}_'
        f'{datetime.now().strftime("%%Y%%m%%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response


@bp.route('/export/gate-statistics/<int:event_id>')
@login_required
def export_gate_statistics(event_id):
    """Export gate statistics as CSV (placeholder)"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

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
        f'{datetime.now().strftime("%%Y%%m%%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response
