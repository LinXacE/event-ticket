from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from database import db
from models import Event, EventPass
from datetime import datetime

events_bp = Blueprint('events', __name__)

@events_bp.route('/events', methods=['GET'])
@login_required
def list_events():
    """Display all events"""
    events = Event.query.order_by(Event.event_date.desc()).all()
    return render_template('events/list.html', events=events)

@events_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """Create a new event"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description')
            date_str = request.form.get('date')
            time_str = request.form.get('time')
            location = request.form.get('location')
            max_participants = request.form.get('max_participants')
            
            # Validate required fields
            if not all([name, date_str, time_str, location]):
                flash('Please fill in all required fields', 'error')
                return render_template('events/create.html')
            
            # Parse date and time
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            event_time = datetime.strptime(time_str, '%H:%M').time()
            
            # Create event
            event = Event(
                event_name=name,
                event_description=description,
                event_date=event_date,
                event_time=event_time,
                location=location,
                total_capacity=int(max_participants) if max_participants else None,
                organizer_id=current_user.id
            )
            
            db.session.add(event)
            db.session.commit()
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('events.list_events'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {str(e)}', 'error')
            return render_template('events/create.html')
    
    return render_template('events/create.html')

@events_bp.route('/events/<int:event_id>', methods=['GET'])
@login_required
def event_details(event_id):
    """View event details"""
    event = Event.query.get_or_404(event_id)
    
    # Get passes for this event
    passes = EventPass.query.filter_by(event_id=event_id).all()
    
    # Calculate statistics
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
    """Edit an existing event"""
    event = Event.query.get_or_404(event_id)

    
    # Check permission: only event organizer or admin can edit
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to edit this event', 'error')
        return redirect(url_for('events.event_details', event_id=event_id))
        
    if request.method == 'POST':
        try:
            event.event_name = request.form.get('name')
            event.event_description = request.form.get('description')
            event.event_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
                        time_str = request.form.get('time')
            # Handle both HH:MM and HH:MM:SS formats
            try:
                event.event_time = datetime.strptime(time_str, '%H:%M:%S').time()
            except ValueError:
                event.event_time = datetime.strptime(time_str, '%H:%M').time()
            event.location = request.form.get('location')
            max_participants = request.form.get('max_participants')
            event.total_capacity = int(max_participants) if max_participants else None
            
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('events.event_details', event_id=event_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'error')
    
    return render_template('events/edit.html', event=event)

@events_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete an event"""
    try:
        event = Event.query.get_or_404(event_id)
        
        # Check if event has passes
        pass_count = EventPass.query.filter_by(event_id=event_id).count()
        if pass_count > 0:
            flash(f'Cannot delete event with {pass_count} existing passes. Please delete passes first.', 'error')
            return redirect(url_for('events.event_details', event_id=event_id))
        
        db.session.delete(event)
        db.session.commit()
        
        flash('Event deleted successfully!', 'success')
        return redirect(url_for('events.list_events'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {str(e)}', 'error')
        return redirect(url_for('events.event_details', event_id=event_id))

@events_bp.route('/events/<int:event_id>/passes', methods=['GET'])
@login_required
def event_passes(event_id):
    """View all passes for an event"""
    event = Event.query.get_or_404(event_id)
    passes = EventPass.query.filter_by(event_id=event_id).order_by(EventPass.created_at.desc()).all()
    
    return render_template('events/passes.html', event=event, passes=passes)

@events_bp.route('/events/upcoming', methods=['GET'])
@login_required
def upcoming_events():
    """View upcoming events"""
    today = datetime.utcnow().date()
    events = Event.query.filter(Event.event_date >= today).order_by(Event.event_date.asc()).all()
    
    return render_template('events/upcoming.html', events=events)

@events_bp.route('/events/past', methods=['GET'])
@login_required
def past_events():
    """View past events"""
    today = datetime.utcnow().date()
    events = Event.query.filter(Event.event_date < today).order_by(Event.event_date.desc()).all()
    
    return render_template('events/past.html', events=events)
