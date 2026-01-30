from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from database import db
from models import User, Event, ValidationLog, Ticket
from utils.decorators import admin_only, organizer_or_admin
from datetime import datetime, timedelta

rbac_bp = Blueprint('rbac', __name__, url_prefix='/admin')

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
    users = User.query.all()
    return render_template('admin/manage_users.html', users=users)

@rbac_bp.route('/users/<int:user_id>/role', methods=['POST'])
@admin_only
def update_user_role(user_id):
    """Change user role."""
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    
    if new_role not in ['admin', 'organizer', 'security']:
        flash('Invalid role selected.', 'error')
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
    username = user.username
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
