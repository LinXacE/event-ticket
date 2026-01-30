from database import db
from flask_login import UserMixin
from datetime import datetime


# ================= USER MODEL =================

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)

    role = db.Column(db.Enum('admin', 'organizer', 'security', name='user_roles'), default='organizer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    events = db.relationship('Event', backref='organizer', lazy=True)
    validation_logs = db.relationship('ValidationLog', backref='validator', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


# ================= EVENT MODEL =================

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(200), nullable=False)
    event_description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(255), nullable=False)
    total_capacity = db.Column(db.Integer, nullable=False)

    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Enum('active', 'completed', 'cancelled', name='event_status'), default='active')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    passes = db.relationship('EventPass', backref='event', lazy=True, cascade='all, delete-orphan')
    analytics = db.relationship('EventAnalytics', backref='event', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.event_name}>'


# ================= PASS TYPE =================

class PassType(db.Model):
    __tablename__ = 'pass_types'

    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    access_level = db.Column(db.Integer, default=1)
    color_code = db.Column(db.String(7), default='#007bff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    passes = db.relationship('EventPass', backref='pass_type', lazy=True)

    def __repr__(self):
        return f'<PassType {self.type_name}>'


# ================= EVENT PASS =================

class EventPass(db.Model):
    __tablename__ = 'event_passes'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    pass_type_id = db.Column(db.Integer, db.ForeignKey('pass_types.id'), nullable=False)

    pass_code = db.Column(db.String(255), unique=True, nullable=False)
    encrypted_data = db.Column(db.Text, nullable=False)

    participant_name = db.Column(db.String(100), nullable=False)
    participant_email = db.Column(db.String(100))
    participant_phone = db.Column(db.String(20))

    qr_code_path = db.Column(db.String(255))
    barcode_path = db.Column(db.String(255))

    is_validated = db.Column(db.Boolean, default=False)
    validation_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    validation_logs = db.relationship('ValidationLog', backref='pass_obj', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<EventPass {self.pass_code}>'


# ================= VALIDATION LOG =================

class ValidationLog(db.Model):
    __tablename__ = 'validation_logs'

    id = db.Column(db.Integer, primary_key=True)
    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    validation_time = db.Column(db.DateTime, default=datetime.utcnow)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate', name='validation_status'), nullable=False)
    validation_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))

    def __repr__(self):
        return f'<ValidationLog {self.id} - {self.validation_status}>'


# ================= EVENT ANALYTICS =================

class EventAnalytics(db.Model):
    __tablename__ = 'event_analytics'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    total_passes_generated = db.Column(db.Integer, default=0)
    total_passes_validated = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<EventAnalytics Event:{self.event_id}>'


# ================= REALTIME ALERT =================

class RealtimeAlert(db.Model):
    __tablename__ = 'realtime_alerts'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    alert_type = db.Column(db.Enum('duplicate_entry', 'suspicious_activity', 'gate_violation', 'system_error', name='alert_types'), nullable=False)
    alert_message = db.Column(db.Text, nullable=False)

    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'))
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'))

    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical', name='alert_severity'), default='medium')
    is_acknowledged = db.Column(db.Boolean, default=False)

    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    acknowledged_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RealtimeAlert {self.alert_type} - {self.severity}>'


# ================= EVENT ANALYTICS SNAPSHOT =================

class EventAnalyticsSnapshot(db.Model):
    __tablename__ = 'event_analytics_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    total_tickets_generated = db.Column(db.Integer, default=0)
    total_tickets_scanned = db.Column(db.Integer, default=0)
    no_show_count = db.Column(db.Integer, default=0)
    duplicate_attempts = db.Column(db.Integer, default=0)

    # SQLite safe (use Text instead of JSON)
    scan_by_gate = db.Column(db.Text)
    scan_by_type = db.Column(db.Text)

    peak_scan_hour = db.Column(db.String(5))
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EventAnalyticsSnapshot Event:{self.event_id}>'

# ================= TICKET BATCH =================

class TicketBatch(db.Model):
    __tablename__ = 'ticket_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    batch_name = db.Column(db.String(100), nullable=False)
    batch_type = db.Column(db.Enum('normal', 'gamify', name='batch_types'), default='normal')
    seat_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TicketBatch {self.batch_name}>'
