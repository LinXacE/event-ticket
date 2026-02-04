from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import Event, EventPass
from datetime import datetime, timedelta
from typing import Optional

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
            event.event_name = request.form.get('name')
            event.event_description = request.form.get('description')

            event.event_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()

            time_str = request.form.get('time')
            try:
                event.event_time = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError:
                event.event_time = datetime.strptime(time_str, '%H:%M').time()

            event.location = request.form.get('location')
            event.total_capacity = int(request.form.get('max_participants'))

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
