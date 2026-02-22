from flask import Blueprint, render_template, jsonify, make_response
from database import db
from models import (
    Event,
    EventPass,
    EventAnalytics,
    ValidationLog,
    PassType,
    Gate,
    GateValidationLog,
    TicketGateValidationLog,
    Ticket,
    TicketBatch
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
    Return analytics for event_id using REAL DB data (passes + batch tickets),
    so it works even if EventAnalytics row is missing.
    """
    # Permission: organizers only see their own events (admins can see all)
    event = Event.query.get_or_404(event_id)
    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    total_event_passes = EventPass.query.filter_by(event_id=event_id).count()
    validated_event_passes = EventPass.query.filter_by(event_id=event_id, is_validated=True).count()

    total_batch_tickets = (
        db.session.query(db.func.count(Ticket.id))
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(TicketBatch.event_id == event_id)
        .scalar()
    ) or 0
    validated_batch_tickets = (
        db.session.query(db.func.count(Ticket.id))
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(
            TicketBatch.event_id == event_id,
            Ticket.status == 'used'
        )
        .scalar()
    ) or 0

    total_entries = int(total_event_passes) + int(total_batch_tickets)
    validated_entries = int(validated_event_passes) + int(validated_batch_tickets)

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

    if int(total_batch_tickets) > 0:
        type_labels.append('Batch Ticket')
        type_counts.append(int(total_batch_tickets))

    return jsonify({
        "success": True,
        "data": {
            "event_id": event_id,
            "total_passes": int(total_entries),
            "validated_passes": int(validated_entries),
            "pending_passes": int(total_entries - validated_entries),
            "total_event_passes": int(total_event_passes),
            "validated_event_passes": int(validated_event_passes),
            "total_batch_tickets": int(total_batch_tickets),
            "validated_batch_tickets": int(validated_batch_tickets),
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
        f'{datetime.now().strftime("%Y%m%d")}.csv'
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
        f'{datetime.now().strftime("%Y%m%d")}.csv'
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

    total_event_passes = EventPass.query.filter_by(event_id=event_id).count()
    validated_event_passes = EventPass.query.filter_by(event_id=event_id, is_validated=True).count()

    total_batch_tickets = (
        db.session.query(db.func.count(Ticket.id))
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(TicketBatch.event_id == event_id)
        .scalar()
    ) or 0
    validated_batch_tickets = (
        db.session.query(db.func.count(Ticket.id))
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(
            TicketBatch.event_id == event_id,
            Ticket.status == 'used'
        )
        .scalar()
    ) or 0

    total_entries = int(total_event_passes) + int(total_batch_tickets)
    validated_entries = int(validated_event_passes) + int(validated_batch_tickets)

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
    writer.writerow(['Total Entries (Passes + Batch Tickets)', total_entries])
    writer.writerow(['Validated Entries (Passes + Batch Tickets)', validated_entries])
    writer.writerow(['Total Passes', total_event_passes])
    writer.writerow(['Validated Passes', validated_event_passes])
    writer.writerow(['Total Batch Tickets', total_batch_tickets])
    writer.writerow(['Validated Batch Tickets', validated_batch_tickets])

    rate = (validated_entries / total_entries * 100) if total_entries > 0 else 0
    writer.writerow(['Validation Rate', f'{rate:.2f}%'])

    writer.writerow([])
    writer.writerow(['Entry Type', 'Total Generated', 'Validated', 'Validation Rate'])

    for stat in pass_type_stats:
        r = (stat.validated / stat.total * 100) if stat.total > 0 else 0
        writer.writerow([stat.type_name, stat.total, stat.validated, f'{r:.2f}%'])

    batch_rate = (validated_batch_tickets / total_batch_tickets * 100) if total_batch_tickets > 0 else 0
    writer.writerow(['Batch Ticket', total_batch_tickets, validated_batch_tickets, f'{batch_rate:.2f}%'])

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
    """Export real gate statistics as CSV."""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

    gates = Gate.query.filter_by(event_id=event_id).order_by(Gate.gate_name.asc()).all()

    pass_stats_rows = (
        db.session.query(
            GateValidationLog.gate_id.label('gate_id'),
            db.func.count(GateValidationLog.id).label('total'),
            db.func.sum(
                db.case((GateValidationLog.gate_access_granted == True, 1), else_=0)  # noqa: E712
            ).label('granted'),
            db.func.sum(
                db.case((GateValidationLog.gate_access_granted == False, 1), else_=0)  # noqa: E712
            ).label('denied'),
            db.func.max(GateValidationLog.created_at).label('last_scan_at')
        )
        .join(Gate, Gate.id == GateValidationLog.gate_id)
        .filter(Gate.event_id == event_id)
        .group_by(GateValidationLog.gate_id)
        .all()
    )
    pass_stats_by_gate = {
        row.gate_id: {
            'total': int(row.total or 0),
            'granted': int(row.granted or 0),
            'denied': int(row.denied or 0),
            'last_scan_at': row.last_scan_at,
        }
        for row in pass_stats_rows
    }

    ticket_stats_rows = (
        db.session.query(
            TicketGateValidationLog.gate_id.label('gate_id'),
            db.func.count(TicketGateValidationLog.id).label('total'),
            db.func.sum(
                db.case((TicketGateValidationLog.validation_status == 'success', 1), else_=0)
            ).label('granted'),
            db.func.sum(
                db.case((TicketGateValidationLog.validation_status != 'success', 1), else_=0)
            ).label('denied'),
            db.func.max(TicketGateValidationLog.created_at).label('last_scan_at')
        )
        .join(Gate, Gate.id == TicketGateValidationLog.gate_id)
        .filter(Gate.event_id == event_id)
        .group_by(TicketGateValidationLog.gate_id)
        .all()
    )
    ticket_stats_by_gate = {
        row.gate_id: {
            'total': int(row.total or 0),
            'granted': int(row.granted or 0),
            'denied': int(row.denied or 0),
            'last_scan_at': row.last_scan_at,
        }
        for row in ticket_stats_rows
    }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'Gate Name', 'Gate Type',
        'Total Entries', 'Access Granted', 'Access Denied',
        'Pass Attempts', 'Ticket Attempts', 'Last Scan At'
    ])

    if not gates:
        writer.writerow(['No gates configured for this event'])
    else:
        for gate in gates:
            pass_stats = pass_stats_by_gate.get(gate.id, {})
            ticket_stats = ticket_stats_by_gate.get(gate.id, {})

            pass_total = int(pass_stats.get('total', 0))
            pass_granted = int(pass_stats.get('granted', 0))
            pass_denied = int(pass_stats.get('denied', 0))

            ticket_total = int(ticket_stats.get('total', 0))
            ticket_granted = int(ticket_stats.get('granted', 0))
            ticket_denied = int(ticket_stats.get('denied', 0))

            total_entries = pass_total + ticket_total
            total_granted = pass_granted + ticket_granted
            total_denied = pass_denied + ticket_denied

            pass_last = pass_stats.get('last_scan_at')
            ticket_last = ticket_stats.get('last_scan_at')
            last_scan_at = max(
                [dt for dt in [pass_last, ticket_last] if dt is not None],
                default=None
            )

            writer.writerow([
                gate.gate_name,
                gate.gate_type,
                total_entries,
                total_granted,
                total_denied,
                pass_total,
                ticket_total,
                last_scan_at.strftime('%Y-%m-%d %H:%M:%S') if last_scan_at else 'N/A'
            ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = (
        f'attachment; filename=gate_statistics_{event.event_name}_'
        f'{datetime.now().strftime("%Y%m%d")}.csv'
    )
    response.headers['Content-Type'] = 'text/csv'
    return response
