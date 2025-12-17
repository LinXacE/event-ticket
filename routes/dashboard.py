from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Event, EventPass, EventAnalytics, PassType, ValidationLog
from database import db
from sqlalchemy import func

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def home():
    # Get user's events
    if current_user.role == 'admin':
        events = Event.query.order_by(Event.created_at.desc()).limit(5).all()
        total_events = Event.query.count()
    else:
        events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).limit(5).all()
        total_events = Event.query.filter_by(organizer_id=current_user.id).count()
    
    # Get total passes generated
    total_passes = EventPass.query.count()
    
    # Get total validated passes
    validated_passes = EventPass.query.filter_by(is_validated=True).count()
    
    # Get recent validations
    recent_validations = ValidationLog.query.order_by(ValidationLog.validation_time.desc()).limit(10).all()
    
    # Get pass type statistics
    pass_stats = db.session.query(
        PassType.type_name,
        func.count(EventPass.id).label('count')
    ).join(EventPass).group_by(PassType.type_name).all()
    
    stats = {
        'total_events': total_events,
        'total_passes': total_passes,
        'validated_passes': validated_passes,
        'validation_rate': round((validated_passes / total_passes * 100) if total_passes > 0 else 0, 1)
    }
    
    return render_template('dashboard/index.html', 
                          events=events, 
                          stats=stats, 
                          pass_stats=pass_stats,
                          recent_validations=recent_validations)

@bp.route('/profile')
@login_required
def profile():
    return render_template('dashboard/profile.html', user=current_user)

@bp.route('/settings')
@login_required
def settings():
    return render_template('dashboard/settings.html')

@bp.route('/events')
@login_required
def events():
    # Get all events for the current user
    if current_user.role == 'admin':
        events = Event.query.order_by(Event.created_at.desc()).all()
    else:
        events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).all()
    
    return render_template('dashboard/events.html', events=events)

@bp.route('/events/<int:event_id>')
@login_required
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    
    # Check if user has permission to view this event
    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to view this event.', 'danger')
        return redirect(url_for('dashboard.home'))
    
    # Get passes for this event
    passes = EventPass.query.filter_by(event_id=event_id).all()
    
    return render_template('dashboard/event_details.html', event=event, passes=passes)

@bp.route('/analytics')
@login_required
def analytics():
    # Get analytics data
    if current_user.role == 'admin':
        total_events = Event.query.count()
        total_passes = EventPass.query.count()
    else:
        total_events = Event.query.filter_by(organizer_id=current_user.id).count()
        total_passes = EventPass.query.join(Event).filter(Event.organizer_id == current_user.id).count()
    
    validated_passes = EventPass.query.filter_by(is_validated=True).count()
    
    return render_template('dashboard/analytics.html', 
                         total_events=total_events,
                         total_passes=total_passes,
                         validated_passes=validated_passes)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
        if request.method == 'POST':
                    current_user.full_name = request.form.get('full_name')
                    current_user.email = request.form.get('email')
                    current_user.phone = request.form.get('phone', '')

        if request.form.get('password'):
                        from flask_bcrypt import Bcrypt
                        bcrypt = Bcrypt()
                        current_user.password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')

        db.session.commit()
            flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard.profile'))

    return render_template('dashboard/profile.html', user=current_user)
