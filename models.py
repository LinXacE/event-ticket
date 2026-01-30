from database import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('admin', 'organizer', 'security'), default='organizer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    events = db.relationship('Event', backref='organizer', lazy=True)
    validation_logs = db.relationship('ValidationLog', backref='validator', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

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
    status = db.Column(db.Enum('active', 'completed', 'cancelled'), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    passes = db.relationship('EventPass', backref='event', lazy=True, cascade='all, delete-orphan')
    analytics = db.relationship('EventAnalytics', backref='event', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Event {self.event_name}>'
    
    @property
    def date(self):
        return self.event_date
    
    @property
    def time(self):
        return self.event_time

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
    
    validation_logs = db.relationship('ValidationLog', backref='pass', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<EventPass {self.pass_code}>'

class ValidationLog(db.Model):
    __tablename__ = 'validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    validation_time = db.Column(db.DateTime, default=datetime.utcnow)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate'), nullable=False)
    validation_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    
    def __repr__(self):
        return f'<ValidationLog {self.id} - {self.validation_status}>'

class EventAnalytics(db.Model):
    __tablename__ = 'event_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    total_passes_generated = db.Column(db.Integer, default=0)
    total_passes_validated = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EventAnalytics Event:{self.event_id}>'

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemSetting {self.setting_key}>'

class TicketBatch(db.Model):
    __tablename__ = 'ticket_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    batch_name = db.Column(db.String(100), nullable=False)
    batch_type = db.Column(db.Enum('normal', 'gamify'), default='normal')
    seat_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tickets = db.relationship('Ticket', backref='batch', lazy=True, cascade='all, delete-orphan')
    event = db.relationship('Event', backref='batches', lazy=True)
    
    def __repr__(self):
        return f'<TicketBatch {self.batch_name}>'

class Promotion(db.Model):
    __tablename__ = 'promotions'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    promotion_name = db.Column(db.String(100), nullable=False)
    promotion_type = db.Column(db.Enum('free_item', 'discount_percent', 'discount_amount'), nullable=False)
    value = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    event = db.relationship('Event', backref='promotions', lazy=True)
    
    def __repr__(self):
        return f'<Promotion {self.promotion_name}>'

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('ticket_batches.id'), nullable=False)
    ticket_code = db.Column(db.String(255), unique=True, nullable=False)
    barcode = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.Enum('available', 'used', 'expired'), default='available')
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.id'))
    price = db.Column(db.Float, default=0.0)
    scanned_by = db.Column(db.String(100))
    scanned_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    promotion = db.relationship('Promotion', backref='tickets', lazy=True)
    
    def __repr__(self):
        return f'<Ticket {self.ticket_code}>'

class Gate(db.Model):
    __tablename__ = 'gates'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    gate_name = db.Column(db.String(100), nullable=False)
    gate_type = db.Column(db.Enum('VIP', 'Staff', 'General', 'Participant', 'Judge', 'Custom'), default='General')
    gate_description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    event = db.relationship('Event', backref='gates', lazy=True)
    access_rules = db.relationship('GateAccessRule', backref='gate', lazy=True, cascade='all, delete-orphan')
    validation_logs = db.relationship('GateValidationLog', backref='gate', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Gate {self.gate_name}>'

class GateAccessRule(db.Model):
    __tablename__ = 'gate_access_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    pass_type_id = db.Column(db.Integer, db.ForeignKey('pass_types.id'), nullable=False)
    can_access = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    pass_type = db.relationship('PassType', backref='access_rules', lazy=True)
    
    def __repr__(self):
        return f'<GateAccessRule Gate:{self.gate_id} PassType:{self.pass_type_id}>'

class GateValidationLog(db.Model):
    __tablename__ = 'gate_validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    validation_log_id = db.Column(db.Integer, db.ForeignKey('validation_logs.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    gate_access_granted = db.Column(db.Boolean, default=True)
    gate_access_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    validation_log = db.relationship('ValidationLog', backref='gate_logs', lazy=True)
    
    def __repr__(self):
        return f'<GateValidationLog {self.id}>'

class OfflineValidationQueue(db.Model):
    __tablename__ = 'offline_validation_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    pass_code = db.Column(db.String(255), nullable=False)
    validator_id = db.Column(db.Integer, nullable=False)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate'), nullable=False)
    validation_message = db.Column(db.Text)
    gate_id = db.Column(db.Integer)
    validation_time = db.Column(db.DateTime, nullable=False)
    sync_status = db.Column(db.Enum('pending', 'synced', 'failed'), default='pending')
    synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<OfflineValidationQueue {self.pass_code} - {self.sync_status}>'

class DuplicateAlertSetting(db.Model):
    __tablename__ = 'duplicate_alert_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    time_window_minutes = db.Column(db.Integer, default=5)
    alert_enabled = db.Column(db.Boolean, default=True)
    notification_method = db.Column(db.Enum('dashboard', 'email', 'both'), default='dashboard')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    event = db.relationship('Event', backref='duplicate_alert_setting', lazy=True, uselist=False)
    
    def __repr__(self):
        return f'<DuplicateAlertSetting Event:{self.event_id}>'

class RealtimeAlert(db.Model):
    __tablename__ = 'realtime_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    alert_type = db.Column(db.Enum('duplicate_entry', 'suspicious_activity', 'gate_violation', 'system_error'), nullable=False)
    alert_message = db.Column(db.Text, nullable=False)
    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'))
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'))
    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical'), default='medium')
    is_acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    event = db.relationship('Event', backref='alerts', lazy=True)
    event_pass = db.relationship('EventPass', backref='alerts', lazy=True)
    gate_rel = db.relationship('Gate', backref='alerts', lazy=True)
    acknowledger = db.relationship('User', backref='acknowledged_alerts', lazy=True, foreign_keys=[acknowledged_by])
    
    def __repr__(self):

# ==================== NEW MODELS FOR UNIVERSITY-LEVEL FEATURES ====================

class TicketType(db.Model):
    """Different ticket types per event (Normal, VIP, Student, Early Bird, etc.)"""
    __tablename__ = 'ticket_types'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    type_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    max_quantity = db.Column(db.Integer, nullable=False)
    quantity_generated = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0.0)
    color_code = db.Column(db.String(7), default='#007bff')
    access_level = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    event = db.relationship('Event', backref='ticket_types', lazy=True)
    
    def __repr__(self):
        return f'<TicketType {self.type_name}>'
    
    @property
    def remaining_quantity(self):
        return self.max_quantity - self.quantity_generated


class TicketValidationLog(db.Model):
    """Enhanced validation logging with detailed tracking."""
    __tablename__ = 'ticket_validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gate_name = db.Column(db.String(100))
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate', 'expired'), default='success')
    validation_message = db.Column(db.Text)
    validation_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    
    ticket = db.relationship('Ticket', backref='detailed_logs', lazy=True)
    event = db.relationship('Event', backref='validation_logs_detailed', lazy=True)
    validator = db.relationship('User', backref='ticket_validations', lazy=True)
    
    def __repr__(self):
        return f'<TicketValidationLog {self.validation_status}>'


class EventAnalyticsSnapshot(db.Model):
    """Analytics snapshots for events (for reports and dashboards)."""
    __tablename__ = 'event_analytics_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    total_tickets_generated = db.Column(db.Integer, default=0)
    total_tickets_scanned = db.Column(db.Integer, default=0)
    no_show_count = db.Column(db.Integer, default=0)
    duplicate_attempts = db.Column(db.Integer, default=0)
    scan_by_gate = db.Column(db.JSON)
    scan_by_type = db.Column(db.JSON)
    peak_scan_hour = db.Column(db.String(5))
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    event = db.relationship('Event', backref='analytics_snapshots', lazy=True)
    
    def __repr__(self):
        return f'<EventAnalyticsSnapshot Event:{self.event_id}>'
        return f'<RealtimeAlert {self.alert_type} - {self.severity}>'
