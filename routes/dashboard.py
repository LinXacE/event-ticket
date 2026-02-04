from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Event, EventPass, PassType, ValidationLog
from database import db
from sqlalchemy import func
from flask_bcrypt import Bcrypt

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
bcrypt = Bcrypt()

DELETE_PREFIX = "[DELETED_AT="

def is_recycled(event: Event) -> bool:
    return event.status == "cancelled" and (event.event_description or "").startswith(DELETE_PREFIX)


@bp.route('/')
@login_required
def home():
    if current_user.role == 'admin':
        all_events = Event.query.order_by(Event.created_at.desc()).all()
        events = [e for e in all_events if not is_recycled(e)][:5]
        total_events = len([e for e in all_events if not is_recycled(e)])
    else:
        all_events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).all()
        events = [e for e in all_events if not is_recycled(e)][:5]
        total_events = len([e for e in all_events if not is_recycled(e)])

    total_passes = EventPass.query.count()
    validated_passes = EventPass.query.filter_by(is_validated=True).count()

    recent_validations = ValidationLog.query.order_by(
        ValidationLog.validation_time.desc()
    ).limit(10).all()

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

    return render_template(
        'dashboard/index.html',
        events=events,
        stats=stats,
        pass_stats=pass_stats,
        recent_validations=recent_validations
    )


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone', '')

        if request.form.get('password'):
            current_user.password = bcrypt.generate_password_hash(
                request.form.get('password')
            ).decode('utf-8')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard.profile'))

    return render_template('dashboard/profile.html', user=current_user)


@bp.route('/settings')
@login_required
def settings():
    return render_template('dashboard/settings.html')


@bp.route('/events')
@login_required
def events():
    if current_user.role == 'admin':
        all_events = Event.query.order_by(Event.created_at.desc()).all()
    else:
        all_events = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.created_at.desc()).all()

    # ✅ Hide recycled events from main list
    events = [e for e in all_events if not is_recycled(e)]

    return render_template('dashboard/events.html', events=events)


@bp.route('/events/<int:event_id>')
@login_required
def event_details(event_id):
    event = Event.query.get_or_404(event_id)

    if current_user.role != 'admin' and event.organizer_id != current_user.id:
        flash('You do not have permission to view this event.', 'danger')
        return redirect(url_for('dashboard.home'))

    passes = EventPass.query.filter_by(event_id=event_id).all()
    return render_template('dashboard/event_details.html', event=event, passes=passes)


@bp.route('/analytics')
@login_required
def analytics():
    if current_user.role == 'admin':
        total_events = Event.query.count()
        total_passes = EventPass.query.count()
    else:
        total_events = Event.query.filter_by(organizer_id=current_user.id).count()
        total_passes = EventPass.query.join(Event).filter(Event.organizer_id == current_user.id).count()

    validated_passes = EventPass.query.filter_by(is_validated=True).count()

    return render_template(
        'dashboard/analytics.html',
        total_events=total_events,
        total_passes=total_passes,
        validated_passes=validated_passes
    )
