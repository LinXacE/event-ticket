from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import db
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Security config (IMPROVED)
# FIXED: Stable secret key (stops session resets on restart)
import secrets
import hashlib

# Generate stable SECRET_KEY from env or create one
if not os.getenv('SECRET_KEY'):
    # Create stable key based on machine-specific data
    machine_id = str(BASE_DIR) + str(os.getuid() if hasattr(os, 'getuid') else 'windows')
    app.config['SECRET_KEY'] = hashlib.sha256(machine_id.encode()).hexdigest()
else:
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Database config (keep MySQL commented for reference)
# app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
db_path_env = os.getenv('DATABASE_PATH')
if db_path_env:
    db_path = db_path_env if os.path.isabs(db_path_env) else os.path.join(BASE_DIR, db_path_env)
else:
    preferred_db_path = os.path.join(BASE_DIR, 'site.db')
    legacy_cwd_db_path = os.path.join(os.getcwd(), 'site.db')
    if os.path.exists(preferred_db_path) or not os.path.exists(legacy_cwd_db_path):
        db_path = preferred_db_path
    else:
        db_path = legacy_cwd_db_path

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}  # FIXED: SQLAlchemy 2.0 compatibility
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)

# Import all models BEFORE creating tables
from models import (User, Event, PassType, EventPass, ValidationLog, EventAnalytics, 
                   RealtimeAlert, EventAnalyticsSnapshot, TicketBatch, Promotion, 
                   Ticket, Gate, GateAccessRule, GateValidationLog, TicketGateValidationLog,
                   EventScannerAssignment, EventScannerInvite, OfflineValidationQueue, DuplicateAlertSetting)

# Fixed pass types (global) to avoid unbounded custom types.
DEFAULT_PASS_TYPES = [
    ('VIP', 'VIP access pass', 5, '#d4af37'),
    ('Judge', 'Judge access pass', 4, '#dc3545'),
    ('Mentor', 'Mentor access pass', 3, '#17a2b8'),
    ('Staff', 'Staff access pass', 3, '#6f42c1'),
    ('Participant', 'Participant access pass', 2, '#007bff'),
    ('Volunteer', 'Volunteer access pass', 2, '#20c997'),
    ('Speaker', 'Speaker access pass', 3, '#fd7e14'),
    ('Sponsor', 'Sponsor access pass', 3, '#28a745'),
]

DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'Admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin0000')
DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@smartevents.local')

# Initialize database tables
with app.app_context():
    db.create_all()
    for type_name, description, access_level, color_code in DEFAULT_PASS_TYPES:
        exists = PassType.query.filter_by(type_name=type_name).first()
        if exists:
            continue
        db.session.add(PassType(
            type_name=type_name,
            description=description,
            access_level=access_level,
            color_code=color_code,
        ))

    # Enforce dedicated default admin account only.
    other_admins = User.query.filter(
        User.role == 'admin',
        User.username != DEFAULT_ADMIN_USERNAME
    ).all()
    for user in other_admins:
        user.role = 'organizer'

    admin_user = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if not admin_user:
        email_to_use = DEFAULT_ADMIN_EMAIL
        email_owner = User.query.filter_by(email=email_to_use).first()
        if email_owner and email_owner.username != DEFAULT_ADMIN_USERNAME:
            email_to_use = f'{DEFAULT_ADMIN_USERNAME.lower()}@local.admin'

        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=email_to_use,
            full_name='System Administrator',
            role='admin',
            password_hash=bcrypt.generate_password_hash(DEFAULT_ADMIN_PASSWORD).decode('utf-8')
        )
        db.session.add(admin_user)
    else:
        admin_user.role = 'admin'
        # Keep admin credentials deterministic for university demo.
        admin_user.password_hash = bcrypt.generate_password_hash(DEFAULT_ADMIN_PASSWORD).decode('utf-8')
        if not admin_user.email:
            fallback_email = DEFAULT_ADMIN_EMAIL
            email_owner = User.query.filter_by(email=fallback_email).first()
            if email_owner and email_owner.id != admin_user.id:
                fallback_email = f'{DEFAULT_ADMIN_USERNAME.lower()}@local.admin'
            admin_user.email = fallback_email

    db.session.commit()

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'  # FIXED: Added 'auth.' prefix
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


# User loader function
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Import routes after app initialization
from routes import auth, events, passes, validation, analytics, dashboard, tickets, gates
from routes.rbac import rbac_bp  # NEW: Admin dashboard and user management

# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(events.events_bp)
app.register_blueprint(passes.bp)
app.register_blueprint(validation.validation_bp)
app.register_blueprint(analytics.bp)
app.register_blueprint(dashboard.bp)
app.register_blueprint(tickets.tickets_bp)
app.register_blueprint(gates.bp)
app.register_blueprint(rbac_bp)  # NEW


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('rbac.admin_dashboard'))
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('auth.login'))


@app.before_request
def enforce_admin_portal():
    """
    Admin users should use admin portal routes only.
    Redirect any non-admin endpoint access to admin dashboard.
    """
    if not current_user.is_authenticated:
        return None

    if current_user.role != 'admin':
        return None

    endpoint = request.endpoint or ''

    # Keep normal 404 behavior for unknown routes.
    if not endpoint:
        return None

    # Allow admin routes and static assets
    if endpoint.startswith('rbac.') or endpoint == 'static':
        return None

    # Send admin logout attempts to admin logout route
    if endpoint == 'auth.logout':
        return redirect(url_for('rbac.admin_logout'))

    return redirect(url_for('rbac.admin_dashboard'))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@app.context_processor
def utility_processor():
    def format_datetime(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ''
        return value.strftime(format)

    def static_path(path_value):
        if not path_value:
            return ''
        normalized = str(path_value).replace('\\', '/')

        if normalized.startswith('static/'):
            return normalized[7:]

        if os.path.isabs(path_value):
            static_root = os.path.abspath(app.static_folder or os.path.join(BASE_DIR, 'static'))
            absolute_value = os.path.abspath(path_value)
            try:
                relative = os.path.relpath(absolute_value, static_root)
                if not relative.startswith('..'):
                    return relative.replace('\\', '/')
            except ValueError:
                pass

        return normalized.lstrip('/')

    return dict(format_datetime=format_datetime, static_path=static_path)


if __name__ == '__main__':
    # Create directories if they don't exist
    static_root = os.path.join(BASE_DIR, 'static')
    os.makedirs(os.path.join(static_root, 'qr_codes'), exist_ok=True)
    os.makedirs(os.path.join(static_root, 'barcodes'), exist_ok=True)
    os.makedirs(os.path.join(static_root, 'uploads'), exist_ok=True)

    app.run(debug=os.getenv('DEBUG', 'False') == 'True', host='0.0.0.0', port=5000)
