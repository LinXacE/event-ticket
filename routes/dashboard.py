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
