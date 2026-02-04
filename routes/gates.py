from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from database import db
from models import (
    Event, Gate, GateAccessRule, PassType,
    EventPass, ValidationLog, GateValidationLog,
    OfflineValidationQueue, RealtimeAlert, DuplicateAlertSetting
)
from flask_login import login_required, current_user
from datetime import datetime
import json

bp = Blueprint('gates', __name__, url_prefix='/gates')


# =========================
# API: Active gates for scanner dropdown
# =========================
@bp.route('/api/active', methods=['GET'])
@login_required
def active_gates_api():
    """Return all active gates (for scanner dropdown)."""
    gates = Gate.query.filter_by(is_active=True).all()

    gate_list = []
    for g in gates:
        gate_list.append({
            "id": g.id,
            "name": g.gate_name,
            "type": g.gate_type,
            "event_id": g.event_id
        })

    return jsonify({"success": True, "gates": gate_list}), 200


# =========================
# Gate Management Routes
# =========================
@bp.route('/event/<int:event_id>')
@login_required
def event_gates(event_id):
    """View all gates for an event"""
    event = Event.query.get_or_404(event_id)

    # Permission check
    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to manage gates for this event', 'danger')
        return redirect(url_for('dashboard.home'))

    gates = Gate.query.filter_by(event_id=event_id).all()

    # ✅ OPTION A FIX:
    # Show ONLY pass types that exist for THIS event
    # (pass types used by EventPass rows for this event)
    pass_types = (
        db.session.query(PassType)
        .join(EventPass, EventPass.pass_type_id == PassType.id)
        .filter(EventPass.event_id == event_id)
        .distinct()
        .order_by(PassType.type_name.asc())
        .all()
    )

    return render_template('gates/index.html', event=event, gates=gates, pass_types=pass_types)


@bp.route('/create/<int:event_id>', methods=['POST'])
@login_required
def create_gate(event_id):
    """Create a new gate for an event"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to manage gates for this event', 'danger')
        return redirect(url_for('dashboard.home'))

    gate = Gate(
        event_id=event_id,
        gate_name=request.form.get('gate_name'),
        gate_type=request.form.get('gate_type', 'General'),
        gate_description=request.form.get('gate_description'),
        is_active=(request.form.get('is_active') == 'on')
    )

    db.session.add(gate)
    db.session.commit()

    # Create access rules for selected pass types
    selected_pass_types = request.form.getlist('pass_types')
    for pass_type_id in selected_pass_types:
        rule = GateAccessRule(
            gate_id=gate.id,
            pass_type_id=int(pass_type_id),
            can_access=True
        )
        db.session.add(rule)

    db.session.commit()
    flash(f'Gate "{gate.gate_name}" created successfully!', 'success')
    return redirect(url_for('gates.event_gates', event_id=event_id))


@bp.route('/update/<int:gate_id>', methods=['POST'])
@login_required
def update_gate(gate_id):
    """Update gate settings"""
    gate = Gate.query.get_or_404(gate_id)
    event = Event.query.get_or_404(gate.event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to manage gates for this event', 'danger')
        return redirect(url_for('dashboard.home'))

    gate.gate_name = request.form.get('gate_name')
    gate.gate_type = request.form.get('gate_type')
    gate.gate_description = request.form.get('gate_description')
    gate.is_active = (request.form.get('is_active') == 'on')

    # Update access rules
    GateAccessRule.query.filter_by(gate_id=gate_id).delete()

    selected_pass_types = request.form.getlist('pass_types')
    for pass_type_id in selected_pass_types:
        rule = GateAccessRule(
            gate_id=gate.id,
            pass_type_id=int(pass_type_id),
            can_access=True
        )
        db.session.add(rule)

    db.session.commit()
    flash(f'Gate "{gate.gate_name}" updated successfully!', 'success')
    return redirect(url_for('gates.event_gates', event_id=gate.event_id))


@bp.route('/delete/<int:gate_id>', methods=['POST'])
@login_required
def delete_gate(gate_id):
    """Delete a gate"""
    gate = Gate.query.get_or_404(gate_id)
    event = Event.query.get_or_404(gate.event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to manage gates for this event', 'danger')
        return redirect(url_for('dashboard.home'))

    event_id = gate.event_id

    db.session.delete(gate)
    db.session.commit()

    flash(f'Gate "{gate.gate_name}" deleted successfully!', 'success')
    return redirect(url_for('gates.event_gates', event_id=event_id))


@bp.route('/api/check-access/<int:gate_id>/<int:pass_type_id>')
@login_required
def check_gate_access(gate_id, pass_type_id):
    """Check if a pass type can access a gate"""
    rule = GateAccessRule.query.filter_by(gate_id=gate_id, pass_type_id=pass_type_id).first()

    return jsonify({
        'can_access': rule.can_access if rule else False,
        'gate_id': gate_id,
        'pass_type_id': pass_type_id
    })


# =========================
# Offline Validation Routes
# =========================
@bp.route('/offline/download/<int:event_id>')
@login_required
def download_offline_database(event_id):
    """Download ticket database for offline validation"""
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return make_response("Not authorized", 403)

    passes = EventPass.query.filter_by(event_id=event_id).all()
    gates = Gate.query.filter_by(event_id=event_id).all()

    offline_data = {
        'event': {
            'id': event.id,
            'name': event.event_name,
            'date': event.event_date.strftime('%Y-%m-%d') if event.event_date else None,
            'time': event.event_time.strftime('%H:%M:%S') if event.event_time else None,
            'location': event.location
        },
        'passes': [],
        'gates': [],
        'pass_types': {},
        'download_time': datetime.utcnow().isoformat()
    }

    for pass_obj in passes:
        offline_data['passes'].append({
            'id': pass_obj.id,
            'pass_code': pass_obj.pass_code,
            'encrypted_data': pass_obj.encrypted_data,
            'participant_name': pass_obj.participant_name,
            'pass_type_id': pass_obj.pass_type_id,
            'is_validated': pass_obj.is_validated,
            'validation_count': pass_obj.validation_count
        })

    for gate in gates:
        gate_data = {
            'id': gate.id,
            'name': gate.gate_name,
            'type': gate.gate_type,
            'is_active': gate.is_active,
            'allowed_pass_types': [rule.pass_type_id for rule in gate.access_rules if rule.can_access]
        }
        offline_data['gates'].append(gate_data)

    pass_types_all = PassType.query.all()
    for pt in pass_types_all:
        offline_data['pass_types'][pt.id] = pt.type_name

    response = make_response(json.dumps(offline_data, indent=2))
    response.headers['Content-Disposition'] = (
        f'attachment; filename=offline_db_event_{event_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.json'
    )
    response.headers['Content-Type'] = 'application/json'

    return response


@bp.route('/offline/sync', methods=['POST'])
@login_required
def sync_offline_validations():
    """Sync offline validation logs back to server"""
    data = request.get_json()

    if not data or 'validations' not in data:
        return jsonify({'success': False, 'message': 'No validation data provided'}), 400

    synced_count = 0
    failed_count = 0

    for validation_data in data['validations']:
        try:
            pass_obj = EventPass.query.filter_by(pass_code=validation_data['pass_code']).first()

            if not pass_obj:
                failed_count += 1
                continue

            validation_log = ValidationLog(
                pass_id=pass_obj.id,
                validator_id=validation_data.get('validator_id', current_user.id),
                validation_time=datetime.fromisoformat(validation_data['validation_time']),
                validation_status=validation_data['validation_status'],
                validation_message=validation_data.get('validation_message'),
                ip_address=validation_data.get('ip_address', request.remote_addr)
            )
            db.session.add(validation_log)
            db.session.flush()

            if 'gate_id' in validation_data:
                gate_log = GateValidationLog(
                    validation_log_id=validation_log.id,
                    gate_id=validation_data['gate_id'],
                    gate_access_granted=validation_data.get('gate_access_granted', True),
                    gate_access_message=validation_data.get('gate_access_message')
                )
                db.session.add(gate_log)

            if validation_data['validation_status'] == 'success':
                pass_obj.is_validated = True
                pass_obj.validation_count += 1

            synced_count += 1

        except Exception as e:
            failed_count += 1
            print(f"Error syncing validation: {str(e)}")

    db.session.commit()

    return jsonify({
        'success': True,
        'synced': synced_count,
        'failed': failed_count,
        'message': f'Synced {synced_count} validations, {failed_count} failed'
    })


# =========================
# Real-time Alert Routes
# =========================
@bp.route('/alerts/<int:event_id>')
@login_required
def get_alerts(event_id):
    alerts = RealtimeAlert.query.filter_by(
        event_id=event_id,
        is_acknowledged=False
    ).order_by(RealtimeAlert.created_at.desc()).limit(50).all()

    alert_list = []
    for alert in alerts:
        alert_list.append({
            'id': alert.id,
            'type': alert.alert_type,
            'message': alert.alert_message,
            'severity': alert.severity,
            'created_at': alert.created_at.isoformat(),
            'pass_id': alert.pass_id,
            'gate_id': alert.gate_id
        })

    return jsonify({'alerts': alert_list})


@bp.route('/alerts/acknowledge/<int:alert_id>', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    alert = RealtimeAlert.query.get_or_404(alert_id)

    alert.is_acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.utcnow()

    db.session.commit()

    return jsonify({'success': True, 'message': 'Alert acknowledged'})


# =========================
# Duplicate Detection Settings
# =========================
@bp.route('/duplicate-settings/<int:event_id>')
@login_required
def duplicate_settings(event_id):
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    settings = DuplicateAlertSetting.query.filter_by(event_id=event_id).first()

    if not settings:
        settings = DuplicateAlertSetting(
            event_id=event_id,
            time_window_minutes=5,
            alert_enabled=True
        )
        db.session.add(settings)
        db.session.commit()

    return jsonify({
        'event_id': event_id,
        'time_window_minutes': settings.time_window_minutes,
        'alert_enabled': settings.alert_enabled,
        'notification_method': settings.notification_method
    })


@bp.route('/duplicate-settings/<int:event_id>', methods=['POST'])
@login_required
def update_duplicate_settings(event_id):
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    settings = DuplicateAlertSetting.query.filter_by(event_id=event_id).first()

    if not settings:
        settings = DuplicateAlertSetting(event_id=event_id)
        db.session.add(settings)

    data = request.get_json()
    settings.time_window_minutes = data.get('time_window_minutes', 5)
    settings.alert_enabled = data.get('alert_enabled', True)
    settings.notification_method = data.get('notification_method', 'dashboard')

    db.session.commit()

    return jsonify({'success': True, 'message': 'Settings updated'})
