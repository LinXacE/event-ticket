from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Event, Pass
from datetime import datetime

events_bp = Blueprint('events', __name__)

@events_bp.route('/events', methods=['GET'])
def list_events():
    """Display all events"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    events = Event.query.order_by(Event.date.desc()).all()
    return render_template('events/list.html', events=events)

@events_bp.route('/events/create', methods=['GET', 'POST'])
def create_event():
    """Create a new event"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description')
            date_str = request.form.get('date')
            location = request.form.get('location')
            max_participants = request.form.get('max_participants')
            
            # Validate required fields
            if not all([name, date_str, location]):
                flash('Please fill in all required fields', 'error')
                return render_template('events/create.html')
            
            # Parse date
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Create event
            event = Event(
                name=name,
                description=description,
                date=event_date,
                location=location,
                max_participants=int(max_participants) if max_participants else None,
                created_by=session.get('user_id'),
                created_at=datetime.utcnow()
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
def event_details(event_id):
    """View event details"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    event = Event.query.get_or_404(event_id)
    
    # Get passes for this event
    passes = Pass.query.filter_by(event_id=event_id).all()
    
    # Calculate statistics
    total_passes = len(passes)
    validated_passes = len([p for p in passes if p.is_validated])
    pass_types = {}
    for p in passes:
        pass_types[p.pass_type] = pass_types.get(p.pass_type, 0) + 1
    
    stats = {
        'total_passes': total_passes,
        'validated_passes': validated_passes,
        'pending_passes': total_passes - validated_passes,
        'pass_types': pass_types
    }
    
    return render_template('events/details.html', event=event, passes=passes, stats=stats)

@events_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    """Edit an existing event"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        try:
            event.name = request.form.get('name')
            event.description = request.form.get('description')
            event.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            event.location = request.form.get('location')
            max_participants = request.form.get('max_participants')
            event.max_participants = int(max_participants) if max_participants else None
            
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('events.event_details', event_id=event_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'error')
    
    return render_template('events/edit.html', event=event)

@events_bp.route('/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    """Delete an event"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        event = Event.query.get_or_404(event_id)
        
        # Check if event has passes
        pass_count = Pass.query.filter_by(event_id=event_id).count()
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
def event_passes(event_id):
    """View all passes for an event"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    event = Event.query.get_or_404(event_id)
    passes = Pass.query.filter_by(event_id=event_id).order_by(Pass.created_at.desc()).all()
    
    return render_template('events/passes.html', event=event, passes=passes)

@events_bp.route('/events/upcoming', methods=['GET'])
def upcoming_events():
    """View upcoming events"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    today = datetime.utcnow().date()
    events = Event.query.filter(Event.date >= today).order_by(Event.date.asc()).all()
    
    return render_template('events/upcoming.html', events=events)

@events_bp.route('/events/past', methods=['GET'])
def past_events():
    """View past events"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    today = datetime.utcnow().date()
    events = Event.query.filter(Event.date < today).order_by(Event.date.desc()).all()
    
    return render_template('events/past.html', events=events)
