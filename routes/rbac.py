from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user, login_user, logout_user
from database import db
from models import (
    User, Event, ValidationLog, Ticket, EventPass, Gate, TicketBatch,
    EventScannerAssignment, EventScannerInvite, TicketGateValidationLog
)
from utils.decorators import admin_only, organizer_or_admin
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import os

rbac_bp = Blueprint('rbac', __name__, url_prefix='/admin')
bcrypt = Bcrypt()

DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'Admin')


@rbac_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Dedicated admin login page."""
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('rbac.admin_dashboard'))

    if current_user.is_authenticated and current_user.role != 'admin':
        logout_user()
        flash('Switched to admin portal. Please log in as admin.', 'info')

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        admin_user = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME, role='admin').first()
        if not admin_user:
            flash('Admin account is not configured on server.', 'danger')
            return render_template('admin/login.html')

        if username != admin_user.username:
            flash('Invalid admin credentials.', 'danger')
            return render_template('admin/login.html')

        if not bcrypt.check_password_hash(admin_user.password_hash, password):
            flash('Invalid admin credentials.', 'danger')
            return render_template('admin/login.html')

        login_user(admin_user, remember=False)
        admin_user.last_login = datetime.utcnow()
        db.session.commit()
        flash('Admin login successful.', 'success')
        return redirect(url_for('rbac.admin_dashboard'))

    return render_template('admin/login.html')


@rbac_bp.route('/logout', methods=['GET'])
@login_required
def admin_logout():
    logout_user()
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('rbac.admin_login'))


@rbac_bp.route('/', methods=['GET'])
@admin_only
def admin_index():
    return redirect(url_for('rbac.admin_dashboard'))

# ========== ADMIN DASHBOARD ==========
@rbac_bp.route('/dashboard', methods=['GET'])
@admin_only
def admin_dashboard():
    """System-wide admin dashboard showing all metrics."""
    total_users = User.query.count()
    total_events = Event.query.count()
    active_events = Event.query.filter_by(status='active').count()
    
    admin_count = User.query.filter_by(role='admin').count()
    organizer_count = User.query.filter_by(role='organizer').count()
    security_count = User.query.filter_by(role='security').count()
    
    total_tickets = Ticket.query.count()
    total_scanned = Ticket.query.filter_by(status='used').count()
    
    recent_events = Event.query.order_by(Event.created_at.desc()).limit(5).all()
    recent_validations = ValidationLog.query.order_by(
        ValidationLog.validation_time.desc()
    ).limit(10).all()
    
    stats = {
        'total_users': total_users,
        'total_events': total_events,
        'active_events': active_events,
        'total_tickets': total_tickets,
        'total_scanned': total_scanned,
        'admin_count': admin_count,
        'organizer_count': organizer_count,
        'security_count': security_count,
        'scan_rate': f'{(total_scanned/total_tickets*100):.1f}%' if total_tickets > 0 else '0%'
    }
    
    return render_template('admin/dashboard.html', 
                         stats=stats,
                         recent_events=recent_events,
                         recent_validations=recent_validations)

# ========== USER MANAGEMENT ==========
@rbac_bp.route('/users', methods=['GET'])
@admin_only
def manage_users():
    """List and manage all users with role assignment."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template(
        'admin/manage_users.html',
        users=users,
        default_admin_username=DEFAULT_ADMIN_USERNAME
    )

@rbac_bp.route('/users/<int:user_id>/role', methods=['POST'])
@admin_only
def update_user_role(user_id):
    """Change user role."""
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    
    if new_role not in ['admin', 'organizer', 'security']:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    if user.username == DEFAULT_ADMIN_USERNAME and new_role != 'admin':
        flash('Default admin account must keep admin role.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    if user.username != DEFAULT_ADMIN_USERNAME and new_role == 'admin':
        flash('Only the default admin account can have admin role.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    # Prevent self-demotion from admin to avoid lockout
    if user.id == current_user.id and current_user.role == 'admin' and new_role != 'admin':
        flash('You cannot remove your own admin role.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    # Ensure system always has at least one admin
    if user.role == 'admin' and new_role != 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot remove the last admin account.', 'danger')
            return redirect(url_for('rbac.manage_users'))
    
    old_role = user.role
    user.role = new_role
    db.session.commit()
    
    flash(f'User {user.username} role updated: {old_role} to {new_role}', 'success')
    return redirect(url_for('rbac.manage_users'))

@rbac_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_only
def delete_user(user_id):
    """Delete a user account."""
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot delete your own account while logged in.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    if user.username == DEFAULT_ADMIN_USERNAME:
        flash('Default admin account cannot be deleted.', 'danger')
        return redirect(url_for('rbac.manage_users'))

    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last admin account.', 'danger')
            return redirect(url_for('rbac.manage_users'))

    username = user.username
    EventScannerAssignment.query.filter(
        (EventScannerAssignment.scanner_user_id == user.id) |
        (EventScannerAssignment.assigned_by_user_id == user.id)
    ).delete(synchronize_session=False)
    EventScannerInvite.query.filter(
        (EventScannerInvite.inviter_user_id == user.id) |
        (EventScannerInvite.invitee_user_id == user.id)
    ).delete(synchronize_session=False)
    TicketGateValidationLog.query.filter_by(validator_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" has been deleted.', 'success')
    return redirect(url_for('rbac.manage_users'))

# ========== EVENT OVERSIGHT ==========
@rbac_bp.route('/events', methods=['GET'])
@admin_only
def admin_events():
    """Admin view of all events in system."""
    events = Event.query.all()
    return render_template('admin/events.html', events=events)


@rbac_bp.route('/events/<int:event_id>', methods=['GET'])
@admin_only
def admin_event_details(event_id):
    """Admin-only event details without exposing user dashboard routes."""
    event = Event.query.get_or_404(event_id)
    total_passes = EventPass.query.filter_by(event_id=event_id).count()
    validated_passes = EventPass.query.filter_by(event_id=event_id, is_validated=True).count()

    total_tickets = (
        Ticket.query
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(TicketBatch.event_id == event_id)
        .count()
    )
    used_tickets = (
        Ticket.query
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(TicketBatch.event_id == event_id, Ticket.status == 'used')
        .count()
    )
    gates = Gate.query.filter_by(event_id=event_id).order_by(Gate.gate_name.asc()).all()

    return render_template(
        'admin/event_details.html',
        event=event,
        total_passes=total_passes,
        validated_passes=validated_passes,
        total_tickets=total_tickets,
        used_tickets=used_tickets,
        gates=gates,
    )

# ========== STATISTICS API ==========
@rbac_bp.route('/api/users-by-role', methods=['GET'])
@admin_only
def api_users_by_role():
    """Get user count by role for dashboard charts."""
    return jsonify({
        'admin': User.query.filter_by(role='admin').count(),
        'organizer': User.query.filter_by(role='organizer').count(),
        'security': User.query.filter_by(role='security').count(),
    })

@rbac_bp.route('/api/tickets-summary', methods=['GET'])
@admin_only
def api_tickets_summary():
    """Get global ticket summary stats."""
    total = Ticket.query.count()
    used = Ticket.query.filter_by(status='used').count()
    available = Ticket.query.filter_by(status='available').count()
    expired = Ticket.query.filter_by(status='expired').count()
    
    return jsonify({
        'total': total,
        'used': used,
        'available': available,
        'expired': expired,
    })
