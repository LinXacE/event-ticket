from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import Event, EventPass, User, Gate, EventScannerAssignment, EventScannerInvite
from datetime import datetime, timedelta
from typing import Optional
from utils.capacity import get_event_capacity_snapshot

events_bp = Blueprint('events', __name__)

# -----------------------------------------
# Helpers for recycle bin (NO DB migration)
# -----------------------------------------
DELETE_PREFIX = "[DELETED_AT="

def mark_deleted_description(desc: Optional[str], deleted_at: datetime) -> str:
    desc = desc or ""
    desc = remove_deleted_marker(desc)
    return f"{DELETE_PREFIX}{deleted_at.isoformat()}]\n{desc}".strip()

def remove_deleted_marker(desc: Optional[str]) -> str:
    desc = desc or ""
    if desc.startswith(DELETE_PREFIX):
        end = desc.find("]\n")
        if end != -1:
            return desc[end + 2:].lstrip()
        end2 = desc.find("]")
        if end2 != -1:
            return desc[end2 + 1:].lstrip()
    return desc

def get_deleted_at(event: Event):
    desc = event.event_description or ""
    if desc.startswith(DELETE_PREFIX):
        end = desc.find("]")
        if end != -1:
            raw = desc[len(DELETE_PREFIX):end]
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None
    return None

def is_in_recycle_bin(event: Event) -> bool:
    return event.status == "cancelled" and (event.event_description or "").startswith(DELETE_PREFIX)


@events_bp.route('/events', methods=['GET'])
@login_required
def list_events():
    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('events/list.html', events=events)


@events_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    # Your UI creates events from dashboard modal, so redirect GET
    if request.method == 'GET':
        return redirect(url_for('dashboard.events'))

    try:
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        date_str = (request.form.get('date') or '').strip()
        time_str = (request.form.get('time') or '').strip()
        location = (request.form.get('location') or '').strip()
        max_participants = (request.form.get('max_participants') or '').strip()

        if not all([name, date_str, time_str, location, max_participants]):
            flash('Please fill in all required fields', 'danger')
            return redirect(url_for('dashboard.events'))

        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        try:
            event_time = datetime.strptime(time_str, '%H:%M:%S').time()
        except ValueError:
            event_time = datetime.strptime(time_str, '%H:%M').time()

        try:
            capacity = int(max_participants)
            if capacity < 1:
                raise ValueError()
        except ValueError:
            flash('Maximum participants must be a number (>= 1)', 'danger')
            return redirect(url_for('dashboard.events'))

        event = Event(
            event_name=name,
            event_description=description,
            event_date=event_date,
            event_time=event_time,
            location=location,
            total_capacity=capacity,
            organizer_id=current_user.id
        )

        db.session.add(event)
        db.session.commit()

        flash('Event created successfully!', 'success')
        return redirect(url_for('dashboard.events'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating event: {str(e)}', 'danger')
        return redirect(url_for('dashboard.events'))


@events_bp.route('/events/<int:event_id>', methods=['GET'])
@login_required
def event_details(event_id):
    event = Event.query.get_or_404(event_id)

    passes = EventPass.query.filter_by(event_id=event_id).all()
    total_passes = len(passes)
    validated_passes = len([p for p in passes if p.is_validated])

    pass_types = {}
    for p in passes:
        pass_type_name = p.pass_type.type_name if p.pass_type else 'Unknown'
        pass_types[pass_type_name] = pass_types.get(pass_type_name, 0) + 1

    stats = {
        'total_passes': total_passes,
        'validated_passes': validated_passes,
        'pending_passes': total_passes - validated_passes,
        'pass_types': pass_types
    }

    return render_template('events/details.html', event=event, passes=passes, stats=stats)


@events_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to edit this event', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))

    if request.method == 'POST':
        try:
            event.event_name = (request.form.get('name') or '').strip()
            event.event_description = request.form.get('description')

            event.event_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()

            time_str = request.form.get('time')
            try:
                event.event_time = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError:
                event.event_time = datetime.strptime(time_str, '%H:%M').time()

            event.location = (request.form.get('location') or '').strip()

            try:
                new_capacity = int((request.form.get('max_participants') or '').strip())
            except ValueError:
                flash('Maximum participants must be a number (>= 1)', 'danger')
                return render_template('events/edit.html', event=event)

            if new_capacity < 1:
                flash('Maximum participants must be at least 1', 'danger')
                return render_template('events/edit.html', event=event)

            capacity = get_event_capacity_snapshot(event)
            if new_capacity < capacity['allocated_total']:
                flash(
                    (
                        f'Cannot set capacity to {new_capacity}. '
                        f'This event already has {capacity["allocated_total"]} allocated '
                        f'({capacity["pass_count"]} passes + {capacity["ticket_count"]} tickets).'
                    ),
                    'danger'
                )
                return render_template('events/edit.html', event=event)

            event.total_capacity = new_capacity

            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('events.event_details', event_id=event_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'danger')

    return render_template('events/edit.html', event=event)


# -----------------------------------------
# ✅ RECYCLE BIN: Soft delete (Archive)
# -----------------------------------------
@events_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """
    - If event has passes -> move to Recycle Bin (soft delete)
    - If event has NO passes -> delete permanently
    """
    try:
        event = Event.query.get_or_404(event_id)

        if event.organizer_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to delete this event', 'danger')
            return redirect(url_for('dashboard.events'))

        pass_count = EventPass.query.filter_by(event_id=event_id).count()

        if pass_count > 0:
            now = datetime.utcnow()
            event.status = "cancelled"
            event.event_description = mark_deleted_description(event.event_description, now)
            db.session.commit()

            flash(f'Event moved to Recycle Bin (has {pass_count} passes). You can restore within 30 days.', 'warning')
            return redirect(url_for('dashboard.events'))

        db.session.delete(event)
        db.session.commit()

        flash('Event deleted permanently (no passes existed).', 'success')
        return redirect(url_for('dashboard.events'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {str(e)}', 'danger')
        return redirect(url_for('dashboard.events'))


@events_bp.route('/events/recycle-bin', methods=['GET'])
@login_required
def recycle_bin():
    q = Event.query
    if current_user.role != 'admin':
        q = q.filter(Event.organizer_id == current_user.id)

    all_events = q.order_by(Event.updated_at.desc()).all()
    recycled = [e for e in all_events if is_in_recycle_bin(e)]

    rows = []
    now = datetime.utcnow()

    for e in recycled:
        deleted_at = get_deleted_at(e) or e.updated_at
        days_left = 30 - (now - deleted_at).days
        rows.append({
            "event": e,
            "deleted_at": deleted_at,
            "days_left": days_left
        })

    return render_template('events/recycle_bin.html', rows=rows)


@events_bp.route('/events/<int:event_id>/restore', methods=['POST'])
@login_required
def restore_event(event_id):
    try:
        event = Event.query.get_or_404(event_id)

        if event.organizer_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to restore this event', 'danger')
            return redirect(url_for('events.recycle_bin'))

        if not is_in_recycle_bin(event):
            flash('This event is not in the Recycle Bin.', 'danger')
            return redirect(url_for('events.recycle_bin'))

        deleted_at = get_deleted_at(event) or event.updated_at
        if datetime.utcnow() - deleted_at > timedelta(days=30):
            flash('Restore period expired (30 days). Please purge permanently.', 'danger')
            return redirect(url_for('events.recycle_bin'))

        event.status = "active"
        event.event_description = remove_deleted_marker(event.event_description)
        db.session.commit()

        flash('Event restored successfully!', 'success')
        return redirect(url_for('dashboard.events'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring event: {str(e)}', 'danger')
        return redirect(url_for('events.recycle_bin'))


@events_bp.route('/events/<int:event_id>/purge', methods=['POST'])
@login_required
def purge_event(event_id):
    try:
        event = Event.query.get_or_404(event_id)

        if event.organizer_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to purge this event', 'danger')
            return redirect(url_for('events.recycle_bin'))

        if not is_in_recycle_bin(event):
            flash('This event is not in the Recycle Bin.', 'danger')
            return redirect(url_for('events.recycle_bin'))

        db.session.delete(event)
        db.session.commit()

        flash('Event permanently deleted.', 'success')
        return redirect(url_for('events.recycle_bin'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error purging event: {str(e)}', 'danger')
        return redirect(url_for('events.recycle_bin'))


@events_bp.route('/events/<int:event_id>/scanners', methods=['GET'])
@login_required
def manage_scanners(event_id):
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to manage scanner assignments for this event.', 'danger')
        return redirect(url_for('dashboard.events'))

    gates = Gate.query.filter_by(event_id=event_id, is_active=True).order_by(Gate.gate_name.asc()).all()
    assignments = (
        EventScannerAssignment.query
        .filter_by(event_id=event_id, is_active=True)
        .order_by(EventScannerAssignment.created_at.desc())
        .all()
    )

    pending_invites = (
        EventScannerInvite.query
        .filter_by(event_id=event_id, status='pending')
        .order_by(EventScannerInvite.created_at.desc())
        .all()
    )

    invite_history = (
        EventScannerInvite.query
        .filter(
            EventScannerInvite.event_id == event_id,
            EventScannerInvite.status != 'pending'
        )
        .order_by(EventScannerInvite.updated_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        'events/scanners.html',
        event=event,
        gates=gates,
        assignments=assignments,
        pending_invites=pending_invites,
        invite_history=invite_history
    )


def _resolve_invitee_user(identifier: str):
    """
    Find invitee by numeric user id or exact username.
    """
    ident = (identifier or '').strip()
    if not ident:
        return None

    if ident.isdigit():
        user_by_id = User.query.get(int(ident))
        if user_by_id:
            return user_by_id

    return User.query.filter_by(username=ident).first()


@events_bp.route('/events/<int:event_id>/scanners/invite', methods=['POST'])
@login_required
def send_scanner_invite(event_id):
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to manage scanner invites for this event.', 'danger')
        return redirect(url_for('dashboard.events'))

    invitee_identifier = (request.form.get('invitee_identifier') or '').strip()
    invite_message = (request.form.get('invite_message') or '').strip()[:255]
    gate_id_raw = (request.form.get('gate_id') or '').strip()

    if not invitee_identifier:
        flash('Please provide username or user ID to invite.', 'danger')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    scanner_user = _resolve_invitee_user(invitee_identifier)
    if not scanner_user:
        flash('Invite target user was not found. Use exact username or numeric user ID.', 'danger')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    if scanner_user.role not in ('organizer', 'security'):
        flash('Only organizer or security accounts can be invited as scanner.', 'danger')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    if scanner_user.id == event.organizer_id:
        flash('Event owner already has full scanner access.', 'warning')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    if scanner_user.id == current_user.id:
        flash('You cannot invite yourself.', 'warning')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    gate_id = None
    if gate_id_raw:
        try:
            gate_id = int(gate_id_raw)
        except ValueError:
            flash('Invalid gate selected.', 'danger')
            return redirect(url_for('events.manage_scanners', event_id=event_id))

    gate = None
    if gate_id:
        gate = Gate.query.get(gate_id)
        if not gate or gate.event_id != event_id:
            flash('Selected gate is invalid for this event.', 'danger')
            return redirect(url_for('events.manage_scanners', event_id=event_id))

    existing_assignments = EventScannerAssignment.query.filter_by(
        event_id=event_id,
        scanner_user_id=scanner_user.id,
        is_active=True
    ).all()

    if gate_id is None:
        if existing_assignments:
            flash('This user already has scanner assignment(s). Remove them first before assigning all gates.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))
    else:
        if any(item.gate_id is None for item in existing_assignments):
            flash('This user already has all-gates access for this event.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))
        if any(item.gate_id == gate_id for item in existing_assignments):
            flash('This user is already assigned to that gate.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))

    existing_pending = EventScannerInvite.query.filter_by(
        event_id=event_id,
        invitee_user_id=scanner_user.id,
        status='pending'
    ).all()

    if gate_id is None:
        if existing_pending:
            flash('This user already has pending scanner invite(s) for this event.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))
    else:
        if any(item.gate_id is None for item in existing_pending):
            flash('This user already has a pending all-gates invite for this event.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))
        if any(item.gate_id == gate_id for item in existing_pending):
            flash('This user already has a pending invite for that gate.', 'warning')
            return redirect(url_for('events.manage_scanners', event_id=event_id))

    invite = EventScannerInvite(
        event_id=event_id,
        inviter_user_id=current_user.id,
        invitee_user_id=scanner_user.id,
        gate_id=gate_id,
        status='pending',
        invite_message=invite_message or None
    )

    db.session.add(invite)
    db.session.commit()

    if gate:
        flash(f'Invite sent to {scanner_user.username} for gate "{gate.gate_name}".', 'success')
    else:
        flash(f'Invite sent to {scanner_user.username} for all gates in this event.', 'success')

    return redirect(url_for('events.manage_scanners', event_id=event_id))


@events_bp.route('/events/<int:event_id>/scanners/invites/<int:invite_id>/cancel', methods=['POST'])
@login_required
def cancel_scanner_invite(event_id, invite_id):
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to manage scanner invites for this event.', 'danger')
        return redirect(url_for('dashboard.events'))

    invite = EventScannerInvite.query.get_or_404(invite_id)
    if invite.event_id != event_id:
        flash('Invite does not belong to this event.', 'danger')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    if invite.status != 'pending':
        flash('Only pending invites can be canceled.', 'warning')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    invite.status = 'cancelled'
    invite.responded_at = datetime.utcnow()
    db.session.commit()
    flash('Scanner invite canceled.', 'success')
    return redirect(url_for('events.manage_scanners', event_id=event_id))


@events_bp.route('/events/<int:event_id>/scanners/<int:assignment_id>/delete', methods=['POST'])
@login_required
def remove_scanner_assignment(event_id, assignment_id):
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to manage scanner assignments for this event.', 'danger')
        return redirect(url_for('dashboard.events'))

    assignment = EventScannerAssignment.query.get_or_404(assignment_id)
    if assignment.event_id != event_id:
        flash('Assignment does not belong to this event.', 'danger')
        return redirect(url_for('events.manage_scanners', event_id=event_id))

    db.session.delete(assignment)
    db.session.commit()
    flash('Scanner assignment removed.', 'success')
    return redirect(url_for('events.manage_scanners', event_id=event_id))


def _apply_scanner_assignment_from_invite(invite: EventScannerInvite):
    """
    Accepting an invite creates (or broadens) scanner assignment.
    """
    current_rows = EventScannerAssignment.query.filter_by(
        event_id=invite.event_id,
        scanner_user_id=invite.invitee_user_id,
        is_active=True
    ).all()

    if invite.gate_id is None:
        # All-gates access supersedes all specific-gate assignments
        EventScannerAssignment.query.filter_by(
            event_id=invite.event_id,
            scanner_user_id=invite.invitee_user_id,
            is_active=True
        ).delete(synchronize_session=False)

        db.session.add(EventScannerAssignment(
            event_id=invite.event_id,
            scanner_user_id=invite.invitee_user_id,
            gate_id=None,
            assigned_by_user_id=invite.inviter_user_id,
            is_active=True
        ))
        return

    if any(row.gate_id is None for row in current_rows):
        # Already has all-gates assignment; no need to add specific gate
        return

    if any(row.gate_id == invite.gate_id for row in current_rows):
        # Already assigned to this specific gate
        return

    db.session.add(EventScannerAssignment(
        event_id=invite.event_id,
        scanner_user_id=invite.invitee_user_id,
        gate_id=invite.gate_id,
        assigned_by_user_id=invite.inviter_user_id,
        is_active=True
    ))


@events_bp.route('/scanner-invites', methods=['GET'])
@login_required
def my_scanner_invites():
    pending_invites = (
        EventScannerInvite.query
        .filter_by(invitee_user_id=current_user.id, status='pending')
        .order_by(EventScannerInvite.created_at.desc())
        .all()
    )

    invite_history = (
        EventScannerInvite.query
        .filter(
            EventScannerInvite.invitee_user_id == current_user.id,
            EventScannerInvite.status != 'pending'
        )
        .order_by(EventScannerInvite.updated_at.desc())
        .limit(100)
        .all()
    )

    return render_template(
        'events/my_invites.html',
        pending_invites=pending_invites,
        invite_history=invite_history
    )


@events_bp.route('/scanner-invites/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_scanner_invite(invite_id):
    invite = EventScannerInvite.query.get_or_404(invite_id)

    if invite.invitee_user_id != current_user.id:
        flash('You do not have permission to respond to this invite.', 'danger')
        return redirect(url_for('events.my_scanner_invites'))

    if invite.status != 'pending':
        flash('This invite is no longer pending.', 'warning')
        return redirect(url_for('events.my_scanner_invites'))

    event = Event.query.get(invite.event_id)
    if not event or event.status != 'active':
        invite.status = 'declined'
        invite.responded_at = datetime.utcnow()
        db.session.commit()
        flash('Invite could not be accepted because event is no longer active.', 'danger')
        return redirect(url_for('events.my_scanner_invites'))

    if invite.gate_id:
        gate = Gate.query.get(invite.gate_id)
        if not gate or gate.event_id != invite.event_id or not gate.is_active:
            invite.status = 'declined'
            invite.responded_at = datetime.utcnow()
            db.session.commit()
            flash('Invite could not be accepted because gate is no longer available.', 'danger')
            return redirect(url_for('events.my_scanner_invites'))

    _apply_scanner_assignment_from_invite(invite)
    invite.status = 'accepted'
    invite.responded_at = datetime.utcnow()
    db.session.commit()

    flash('Scanner invite accepted. You now have scanning access for the assigned scope.', 'success')
    return redirect(url_for('events.my_scanner_invites'))


@events_bp.route('/scanner-invites/<int:invite_id>/decline', methods=['POST'])
@login_required
def decline_scanner_invite(invite_id):
    invite = EventScannerInvite.query.get_or_404(invite_id)

    if invite.invitee_user_id != current_user.id:
        flash('You do not have permission to respond to this invite.', 'danger')
        return redirect(url_for('events.my_scanner_invites'))

    if invite.status != 'pending':
        flash('This invite is no longer pending.', 'warning')
        return redirect(url_for('events.my_scanner_invites'))

    invite.status = 'declined'
    invite.responded_at = datetime.utcnow()
    db.session.commit()
    flash('Scanner invite declined.', 'info')
    return redirect(url_for('events.my_scanner_invites'))
