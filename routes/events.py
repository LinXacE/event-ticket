from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import Event, EventPass
from datetime import datetime

events_bp = Blueprint('events', __name__)

@events_bp.route('/events', methods=['GET'])
@login_required
def list_events():
    """
    (Optional / legacy)
    Display all events using events/list.html.
    Your dashboard uses /dashboard/events, so this is not the main UI.
    """
    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('events/list.html', events=events)


@events_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """
    Create a new event.

    IMPORTANT FIX:
    - We DO NOT render templates/events/create.html anymore.
    - On GET: redirect to dashboard events (modal is the UI).
    - On POST: validate, create, and redirect back to dashboard events.
    """
    if request.method == 'GET':
        return redirect(url_for('dashboard.events'))

    # POST
    try:
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        date_str = (request.form.get('date') or '').strip()
        time_str = (request.form.get('time') or '').strip()
        location = (request.form.get('location') or '').strip()
        max_participants = (request.form.get('max_participants') or '').strip()

        # Validate required fields
        if not all([name, date_str, time_str, location, max_participants]):
            flash('Please fill in all required fields', 'danger')
            return redirect(url_for('dashboard.events'))

        # Parse date and time
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Handle HH:MM and HH:MM:SS (just in case)
        try:
            event_time = datetime.strptime(time_str, '%H:%M:%S').time()
        except ValueError:
            event_time = datetime.strptime(time_str, '%H:%M').time()

        # Validate max participants is a positive int
        try:
            capacity = int(max_participants)
            if capacity < 1:
                raise ValueError()
        except ValueError:
            flash('Maximum participants must be a number (>= 1)', 'danger')
            return redirect(url_for('dashboard.events'))

        # Create event
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
    """View event details"""
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

    return render_template(
        'events/details.html',
        event=event,
        passes=passes,
        stats=stats
    )


@events_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Edit an existing event"""
    event = Event.query.get_or_404(event_id)

    # Permission check
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to edit this event', 'danger')
        return redirect(url_for('events.event_details', event_id=event_id))

    if request.method == 'POST':
        try:
            event.event_name = request.form.get('name')
            event.event_description = request.form.get('description')

            event.event_date = datetime.strptime(
                request.form.get('date'),
                '%Y-%m-%d'
            ).date()

            time_str = request.form.get('time')

            try:
                event.event_time = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError:
                event.event_time = datetime.strptime(time_str, '%H:%M').time()

            event.location = request.form.get('location')

            max_participants = request.form.get('max_participants')
            event.total_capacity = int(max_participants)

            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('events.event_details', event_id=event_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'danger')

    return render_template('events/edit.html', event=event)


@events_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete an event"""
    try:
        event = Event.query.get_or_404(event_id)

        pass_count = EventPass.query.filter_by(event_id=event_id).count()
        if pass_count > 0:
            flash(f'Cannot delete event with {pass_count} existing passes.', 'danger')
            return redirect(url_for('dashboard.events'))

        db.session.delete(event)
        db.session.commit()

        flash('Event deleted successfully!', 'success')
        return redirect(url_for('dashboard.events'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {str(e)}', 'danger')
        return redirect(url_for('dashboard.events'))


@events_bp.route('/events/<int:event_id>/passes', methods=['GET'])
@login_required
def event_passes(event_id):
    """View all passes for an event"""
    event = Event.query.get_or_404(event_id)
    passes = (
        EventPass.query
        .filter_by(event_id=event_id)
        .order_by(EventPass.created_at.desc())
        .all()
    )

    return render_template('events/passes.html', event=event, passes=passes)


@events_bp.route('/events/upcoming', methods=['GET'])
@login_required
def upcoming_events():
    """View upcoming events"""
    today = datetime.utcnow().date()
    events = (
        Event.query
        .filter(Event.event_date >= today)
        .order_by(Event.event_date.asc())
        .all()
    )

    return render_template('events/upcoming.html', events=events)


@events_bp.route('/events/past', methods=['GET'])
@login_required
def past_events():
    """View past events"""
    today = datetime.utcnow().date()
    events = (
        Event.query
        .filter(Event.event_date < today)
        .order_by(Event.event_date.desc())
        .all()
    )

    return render_template('events/past.html', events=events)
