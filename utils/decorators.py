from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

def role_required(*roles):
    """Decorator to restrict routes to specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in first.', 'error')
                return redirect(url_for('auth.login'))
            
            if current_user.role not in roles:
                flash(f'Access denied. Required role(s): {", ".join(roles)}', 'error')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_only(f):
    """Restrict route to admin only with dedicated admin login redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in as admin.', 'warning')
            return redirect(url_for('rbac.admin_login'))

        if current_user.role != 'admin':
            flash('Admin access only.', 'danger')
            return redirect(url_for('dashboard.home'))

        return f(*args, **kwargs)
    return decorated_function

def organizer_or_admin(f):
    """Restrict to organizer or admin."""
    return role_required('organizer', 'admin')(f)

def security_or_admin(f):
    """Restrict to security staff or admin."""
    return role_required('security', 'admin')(f)
